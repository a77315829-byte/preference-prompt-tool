"""아이디/비밀번호 로그인. 표준 라이브러리만 쓴다.

Streamlit 을 import 하지 않는다 (`budget.py`, `team.py` 와 같은 층). HTTP 를 모른다 -
쿠키를 붙이고 읽는 것은 api_server.py 가 한다.

- 비밀번호는 저장하지 않는다. scrypt(느린 해시) + 사용자마다 다른 소금만 저장한다.
- 세션 토큰은 브라우저 쿠키에만 있고, DB 에는 토큰의 SHA-256 만 둔다. DB 파일이
  새어도 그 값으로 로그인할 수 없다.
- 없는 아이디로 로그인해도 같은 해시 계산을 한 번 한다. 응답 시간 차이로 가입된
  아이디를 알아내지 못하게.
- 로그인 실패는 아이디마다, 접속 주소마다 횟수를 제한한다. 메모리 카운터라 서버를
  다시 켜면 초기화된다 - 결제 상한처럼 다른 겹의 방어를 대신하지 않는다.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from app_db import Database

USERNAME = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
MIN_PASSWORD = 8
MAX_PASSWORD = 128

SESSION_DAYS = 14

# scrypt 설정. n=2**14 는 한 번에 수십 ms 로, 로그인 한 번에는 충분히 싸고 대량
# 추측에는 비싸다. 바꾸면 기존 해시는 저장된 설정으로 그대로 검증된다.
SCRYPT_N, SCRYPT_R, SCRYPT_P, SCRYPT_LEN = 2**14, 8, 1, 32

# 15분 안에 같은 아이디로 5번, 같은 주소에서 20번 틀리면 잠시 막는다.
FAIL_WINDOW_SECONDS = 15 * 60
MAX_FAILS_PER_USERNAME = 5
MAX_FAILS_PER_ADDRESS = 20


class AuthError(ValueError):
    """화면에 그대로 보여 줘도 되는 오류."""


class TooManyAttempts(AuthError):
    pass


@dataclass(frozen=True)
class User:
    id: int
    username: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
                            dklen=SCRYPT_LEN, maxmem=64 * 1024 * 1024)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt), n=int(n), r=int(r),
                                p=int(p), dklen=len(digest) // 2, maxmem=64 * 1024 * 1024)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual.hex(), digest)


# 없는 아이디로 로그인할 때 같은 비용의 계산을 하려고 쓰는 고정 해시.
_DUMMY_HASH = hash_password("not-a-real-password", salt=b"\0" * 16)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class FailureLimiter:
    """키(아이디·주소)별 최근 실패 시각. 스레드 안전."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._fails: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str) -> list[float]:
        cutoff = self._clock() - FAIL_WINDOW_SECONDS
        recent = [t for t in self._fails.get(key, []) if t > cutoff]
        if recent:
            self._fails[key] = recent
        else:
            self._fails.pop(key, None)
        return recent

    def blocked(self, key: str, limit: int) -> bool:
        with self._lock:
            return len(self._recent(key)) >= limit

    def fail(self, key: str) -> None:
        with self._lock:
            self._recent(key)
            self._fails.setdefault(key, []).append(self._clock())

    def clear(self, key: str) -> None:
        with self._lock:
            self._fails.pop(key, None)


class AuthService:
    def __init__(self, db: Database, limiter: FailureLimiter | None = None) -> None:
        self.db = db
        self.limiter = limiter or FailureLimiter()

    # --- 가입 · 로그인 ----------------------------------------------------------

    def signup(self, username: str, password: str) -> tuple[User, str]:
        """(사용자, 세션 토큰)."""
        username = (username or "").strip()
        if not USERNAME.match(username):
            raise AuthError("아이디는 영문·숫자·_ . - 로 3~30자여야 합니다.")
        if not isinstance(password, str) or not MIN_PASSWORD <= len(password) <= MAX_PASSWORD:
            raise AuthError(f"비밀번호는 {MIN_PASSWORD}~{MAX_PASSWORD}자여야 합니다.")
        if password.strip().lower() == username.lower():
            raise AuthError("비밀번호를 아이디와 다르게 정해 주세요.")
        password_hash = hash_password(password)
        try:
            with self.db.connect() as conn:
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                    (username, password_hash, _now().isoformat(timespec="seconds")),
                )
                user = User(cursor.lastrowid, username)
        except sqlite3.IntegrityError:
            # 대소문자만 다른 아이디도 같은 아이디로 본다 (COLLATE NOCASE). 동시에 두 번
            # 가입해도 UNIQUE 제약이 하나만 받는다.
            raise AuthError("이미 쓰이고 있는 아이디입니다.") from None
        return user, self._new_session(user)

    def login(self, username: str, password: str, address: str = "") -> tuple[User, str]:
        username = (username or "").strip()
        user_key, address_key = f"user:{username.lower()}", f"addr:{address}"
        if self.limiter.blocked(user_key, MAX_FAILS_PER_USERNAME) or (
            address and self.limiter.blocked(address_key, MAX_FAILS_PER_ADDRESS)
        ):
            raise TooManyAttempts("로그인 실패가 많아 잠시 막았습니다. 15분 뒤에 다시 시도해 주세요.")
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?", (username,)
            ).fetchone()
        ok = verify_password(str(password or ""), row["password_hash"] if row else _DUMMY_HASH)
        if not row or not ok:
            self.limiter.fail(user_key)
            if address:
                self.limiter.fail(address_key)
            # 아이디가 없는지 비밀번호가 틀렸는지 구분해 알려 주지 않는다.
            raise AuthError("아이디 또는 비밀번호가 맞지 않습니다.")
        self.limiter.clear(user_key)
        user = User(row["id"], row["username"])
        return user, self._new_session(user)

    # --- 세션 -------------------------------------------------------------------

    def _new_session(self, user: User) -> str:
        token = secrets.token_urlsafe(32)
        now = _now()
        with self.db.connect() as conn:
            # 만료된 세션은 새로 만들 때 같이 치운다.
            conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now.isoformat(timespec="seconds"),))
            conn.execute(
                "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (_token_hash(token), user.id, now.isoformat(timespec="seconds"),
                 (now + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds")),
            )
        return token

    def user_for(self, token: str | None) -> User | None:
        if not token:
            return None
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT users.id, users.username FROM sessions JOIN users ON users.id = sessions.user_id "
                "WHERE sessions.token_hash = ? AND sessions.expires_at > ?",
                (_token_hash(token), _now().isoformat(timespec="seconds")),
            ).fetchone()
        return User(row["id"], row["username"]) if row else None

    def logout(self, token: str | None) -> None:
        if not token:
            return
        with self.db.connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))

    # --- 계정 관리 ---------------------------------------------------------------

    def _recheck(self, user: User, password: str, address: str) -> None:
        """민감한 동작 전에 비밀번호를 다시 확인한다. 세션 쿠키만 훔친 사람이 비밀번호를
        바꾸거나 계정을 지우지 못하게. 실패는 로그인과 같은 횟수 제한을 받는다."""
        key = f"user:{user.username.lower()}"
        if self.limiter.blocked(key, MAX_FAILS_PER_USERNAME):
            raise TooManyAttempts("비밀번호 확인 실패가 많아 잠시 막았습니다. 15분 뒤에 다시 시도해 주세요.")
        with self.db.connect() as conn:
            row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user.id,)).fetchone()
        if row is None or not verify_password(str(password or ""), row["password_hash"]):
            self.limiter.fail(key)
            if address:
                self.limiter.fail(f"addr:{address}")
            raise AuthError("지금 비밀번호가 맞지 않습니다.")
        self.limiter.clear(key)

    def change_password(self, user: User, current: str, new: str, address: str = "") -> str:
        """비밀번호를 바꾸고 **모든 세션을 끊는다**(다른 기기 포함). 이 기기용 새 세션 토큰을
        돌려준다 - 비밀번호를 바꾸는 이유가 유출 의심일 때 다른 곳의 로그인이 남으면 안 된다."""
        self._recheck(user, current, address)
        if not isinstance(new, str) or not MIN_PASSWORD <= len(new) <= MAX_PASSWORD:
            raise AuthError(f"새 비밀번호는 {MIN_PASSWORD}~{MAX_PASSWORD}자여야 합니다.")
        if new.strip().lower() == user.username.lower():
            raise AuthError("비밀번호를 아이디와 다르게 정해 주세요.")
        if new == current:
            raise AuthError("새 비밀번호가 지금 비밀번호와 같습니다.")
        with self.db.connect() as conn:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new), user.id))
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user.id,))
        return self._new_session(user)

    def delete_account(self, user: User, password: str, address: str = "") -> None:
        """계정과 그 사람의 세션·프로젝트·버전·공유·자동 저장본을 지운다 (외래키 CASCADE).
        **그 사람이 소유한 프로젝트는 공유받은 사람에게서도 사라진다** - 화면이 미리 알린다."""
        self._recheck(user, password, address)
        with self.db.connect() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (user.id,))

    def owned_shared_count(self, user: User) -> int:
        """지우면 다른 사람에게서도 사라질 프로젝트 수 (내가 소유했고 공유한 것)."""
        with self.db.connect() as conn:
            return conn.execute(
                """
                SELECT COUNT(DISTINCT p.id) FROM workspace_projects p
                JOIN workspace_members m ON m.project_id = p.id WHERE p.owner_id = ?
                """,
                (user.id,),
            ).fetchone()[0]

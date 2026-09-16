"""requirements.txt 의 빌드 마커를 갱신해 배포 프로세스 재시작을 유발한다.

왜 필요한가: Streamlit Community Cloud 는 코드만 바뀐 푸시에서 메인
스크립트만 다시 실행한다. 이때 이미 import 된 모듈(engine/, demos/,
budget.py)은 옛 객체가 프로세스에 남을 수 있다. 실제로 두 번 물렸다.

1. engine/demo_generator.py 를 고쳤는데 배포는 지워진 ValueError 를
   계속 던졌다.
2. engine/generator.py 에 함수를 추가했는데 app.py 의 import 가
   ImportError 로 죽어 **앱 전체가 내려갔다.**

requirements.txt 가 바뀌면 "Processing dependencies" 를 거쳐 프로세스가
완전히 재시작된다. 그래서 감시 대상 파일들의 해시를 이 파일 주석에
적어두고, 내용이 바뀌면 마커도 바뀌게 한다. 버전은 건드리지 않는다.

사용법 (engine/ · demos/ · budget.py 를 고친 뒤 커밋 전에):

    python -m scripts.bump_build_marker

바뀐 게 없으면 아무것도 쓰지 않고 종료 코드 0으로 끝난다.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements.txt"

# 배포된 app.py 가 import 하는 경로. 이 안이 바뀌면 프로세스를 새로
# 띄워야 옛 모듈이 정리된다.
WATCHED_DIRS = ("engine", "demos", "optimize", "checks")

# 루트의 모듈은 이름을 나열하지 않고 전부 본다. budget.py 를 적어두고
# feedback.py 를 빼먹는 식의 누락이 곧 링크 사망으로 이어지기 때문이다.
# app.py 는 메인 스크립트라 Streamlit 이 항상 새로 읽으므로 제외한다.
ROOT_EXCLUDE = {"app.py"}

MARKER_PREFIX = "# build-marker:"


def _watched_files() -> list[Path]:
    files: list[Path] = [
        path for path in sorted(ROOT.glob("*.py")) if path.name not in ROOT_EXCLUDE
    ]
    for name in WATCHED_DIRS:
        target = ROOT / name
        if target.is_dir():
            files.extend(sorted(target.rglob("*.py")))
    return sorted(set(files))


def compute_marker() -> str:
    digest = hashlib.sha256()
    for path in _watched_files():
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def main() -> int:
    marker = compute_marker()
    text = REQUIREMENTS.read_text(encoding="utf-8")
    line = f"{MARKER_PREFIX} {marker}"

    if re.search(rf"^{re.escape(MARKER_PREFIX)} \S+$", text, flags=re.MULTILINE):
        updated = re.sub(
            rf"^{re.escape(MARKER_PREFIX)} \S+$", line, text, flags=re.MULTILINE
        )
    else:
        updated = text.rstrip("\n") + f"\n\n{line}\n"

    if updated == text:
        print(f"빌드 마커 그대로: {marker} (감시 대상 변경 없음)")
        return 0

    REQUIREMENTS.write_text(updated, encoding="utf-8")
    print(f"빌드 마커 갱신: {marker}")
    print("이 변경을 함께 커밋하면 배포가 프로세스를 새로 띄운다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

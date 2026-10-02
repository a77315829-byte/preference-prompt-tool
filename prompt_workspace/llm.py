"""작업 공간의 모델 호출. 캐싱한다 (절대 규칙 2).

engine/generator.generate_with_prompt 를 쓰지 않는 이유: 그 함수는 응답이
무엇이든 캐시에 쓴다. 여기서는 **검증을 통과한 응답만** 캐시에 남겨야 한다
(계획서 13절) - 깨진 JSON 을 캐시에 굳히면 같은 입력은 다시 시도해도 계속
깨진 결과가 나온다. engine/ 은 고치지 않는다는 조건이 있어 여기에 따로 둔다.
호출 상한(시간·출력)은 generator.py 와 같은 값을 쓴다.

캐시 키에는 결과에 영향을 주는 것을 전부 넣는다: 시스템 지침, 사용자 메시지,
모델, temperature, 그리고 이 모듈의 프롬프트 버전.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Callable

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "workspace"

REQUEST_TIMEOUT_SECONDS = 60
MAX_OUTPUT_TOKENS = 2048
# temperature=0 도 완전한 결정성을 보장하지 않는다. 그래서 실행 기록에 모델과
# 설정, 캐시 사용 여부를 같이 남긴다 (계획서 13절).
TEMPERATURE = 0


def completion(**kwargs):
    """litellm 을 호출 시점에 불러온다 (import 11초). 테스트가 바꿔 끼운다."""
    from litellm import completion as _completion

    return _completion(**kwargs)


def _cache_path(system: str, user: str, model: str, version: str) -> Path:
    payload = json.dumps(
        {"system": system, "user": user, "model": model, "temperature": TEMPERATURE, "version": version},
        sort_keys=True, ensure_ascii=False,
    )
    return CACHE_DIR / f"{hashlib.sha256(payload.encode('utf-8')).hexdigest()}.json"


def call(
    system: str,
    user: str,
    *,
    model: str,
    version: str,
    accept: Callable[[str], bool] = lambda text: True,
) -> dict:
    """{"text", "cached", "elapsed_seconds", "usage"}.

    accept 가 False 를 돌려주는 응답은 캐시에 쓰지 않고 그대로 돌려준다 -
    시험 실행에서는 깨진 출력도 결과로 보여 줘야 하기 때문이다. 빈 응답은
    결과로도 쓸 수 없으므로 예외다.
    """
    cache_file = _cache_path(system, user, model, version)
    if cache_file.exists():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        return {"text": cached["text"], "cached": True, "elapsed_seconds": 0.0, "usage": cached.get("usage")}

    started = time.monotonic()
    response = completion(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_tokens=MAX_OUTPUT_TOKENS,
        temperature=TEMPERATURE,
    )
    elapsed = round(time.monotonic() - started, 2)
    text = response.choices[0].message.content or ""
    if not text.strip():
        raise ValueError("모델이 빈 응답을 반환했습니다. 다시 시도해 주세요.")
    usage = None
    raw_usage = getattr(response, "usage", None)
    if raw_usage is not None:
        usage = {k: getattr(raw_usage, k, None) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}

    if accept(text):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = cache_file.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps({"text": text, "usage": usage}, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(cache_file)
    return {"text": text, "cached": False, "elapsed_seconds": elapsed, "usage": usage}

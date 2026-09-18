"""검증된 measure() 코드를 별도 프로세스에서, 타임아웃을 걸고 실행한다.

프로세스 분리와 시간 제한은 오류 전파를 줄이지만 OS 보안 격리가 아니다.
파일·네트워크·메모리 제한이 없으므로 공개 서비스에서 비신뢰 코드를 받지 않는다.
연구용 실행기이며 알려진 우회 경로에 대한 회귀 방어를 제공한다.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from agents.code_validator import ValidationError, validate_measure_code

_RUNNER = Path(__file__).with_name("_measure_runner.py")


class MeasureExecutionError(Exception):
    pass


def run_measure(code: str, text: str, source: str, timeout: float = 5.0) -> float:
    """code 안의 measure(text, source) -> float 를 격리된 프로세스에서 실행한다.
    검증 실패, 타임아웃, 런타임 오류는 전부 MeasureExecutionError로 통일해 던진다 -
    호출부(에이전트 루프)는 이 축 후보가 실패했다는 신호로만 다루면 된다."""
    try:
        validate_measure_code(code)
    except ValidationError as e:
        raise MeasureExecutionError(f"검증 실패: {e}") from e

    payload = json.dumps({"code": code, "text": text, "source": source})
    try:
        proc = subprocess.run(
            [sys.executable, "-I", str(_RUNNER)],
            input=payload,
            # 호출한 앱의 API 키·토큰을 자식 프로세스 환경으로 넘기지 않는다.
            # -I 는 PYTHONPATH와 사용자 site-package 주입도 무시한다.
            env={key: value for key, value in os.environ.items()
                 if key.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL"}},
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
        )
    except subprocess.TimeoutExpired as e:
        raise MeasureExecutionError(f"타임아웃 ({timeout}s 초과)") from e

    if proc.returncode != 0:
        raise MeasureExecutionError(f"프로세스 비정상 종료: {proc.stderr.strip()[:500]}")

    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise MeasureExecutionError(f"출력 파싱 실패: {proc.stdout[:200]}") from e

    if "error" in result:
        raise MeasureExecutionError(result["error"])
    return float(result["value"])

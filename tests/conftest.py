"""테스트 공통 설정.

API 키나 MACSum 데이터가 없는 환경에서도 `pytest tests/` 가 의미 있게
끝나도록, 필요한 자원이 없는 테스트는 건너뛴다. 조용히 통과시키지 않고
건너뛴 이유를 표시한다 - 예전에는 이 파일들이 assert 없는 출력 스크립트라
pytest 가 아예 수집하지 않았고, 초록색 결과가 실제로는 4개 파일만
검사하고 있었다.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent

# 기존 스크립트들이 쓰던 모델. 그대로 유지하면 cache/ 에 이미 있는 응답을
# 재사용해서 테스트가 빠르고 추가 비용이 들지 않는다. 앱은 별도로
# app.py 의 MODEL 을 쓴다.
API_MODEL = "openai/gpt-4.1-mini"

MACSUM_VAL = ROOT / "data" / "macsum" / "dataset" / "macdoc" / "val.json"


def _has_api_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def pytest_collection_modifyitems(config, items) -> None:
    skip_api = pytest.mark.skip(reason="OPENAI_API_KEY 가 없다 (.env 확인)")
    skip_macsum = pytest.mark.skip(
        reason=f"MACSum 데이터가 없다: {MACSUM_VAL.relative_to(ROOT)} "
        "(README 의 시작하기 참고)"
    )
    api_available = _has_api_key()
    macsum_available = MACSUM_VAL.exists()

    for item in items:
        if "api" in item.keywords and not api_available:
            item.add_marker(skip_api)
        if "macsum" in item.keywords and not macsum_available:
            item.add_marker(skip_macsum)


@pytest.fixture(scope="session")
def model() -> str:
    return API_MODEL


@pytest.fixture(scope="session")
def macsum_record() -> dict:
    return json.loads(MACSUM_VAL.read_text(encoding="utf-8"))[0]


@pytest.fixture(scope="session")
def macsum_source(macsum_record) -> str:
    return " ".join(macsum_record["source"])

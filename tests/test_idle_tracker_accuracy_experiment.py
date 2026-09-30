"""experiments/idle_tracker_accuracy.py 가 저장한 실제 API 결과를 고정한다.
API 없이, 커밋된 결과 파일만으로 돈다."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RESULT = Path(__file__).resolve().parents[1] / "experiments" / "results" / "idle_tracker_accuracy.json"


def _rows() -> list[dict]:
    if not RESULT.exists():
        pytest.skip(f"결과 파일이 없다: {RESULT.name}")
    return json.loads(RESULT.read_text(encoding="utf-8"))


def test_four_combos_recorded() -> None:
    rows = _rows()
    assert len(rows) == 4
    combos = [tuple(sorted(r["combo"].items())) for r in rows]
    assert len(set(combos)) == 4, "네 조합이 서로 달라야 한다"


def test_real_model_output_matches_the_real_cost_data() -> None:
    """sourceText 수정 전에는 이 값들을 보장할 수 없었다 - 생성기가 실제
    금액을 하나도 받지 못했기 때문이다. 수정 후 실제 API 결과를 고정한다."""
    rows = _rows()
    fabrication_failures = [r for r in rows if r["no_fabrication"] < 1.0]
    assert not fabrication_failures, (
        f"실제 모델이 데이터에 없는 값을 지어냈다: {fabrication_failures}"
    )
    accuracy_failures = [r for r in rows if r["total_cost_accuracy"] < 1.0]
    assert not accuracy_failures, (
        f"실제 모델이 합계를 잘못 말했다: {accuracy_failures}"
    )

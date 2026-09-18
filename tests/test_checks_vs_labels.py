"""검사 함수와 MACSum 사람 라벨의 일치율이 기록된 값과 같은지.

experiments/checks_vs_labels.py 의 결과가 experiments/results/ 에 커밋돼
있고, 문서가 그 수치를 인용한다. 검사 함수나 YAML 임계값을 고치면 이
수치가 움직이므로 - 문서를 같이 고치라고 테스트가 알려준다.

MACSum 이 없으면 저장된 결과 파일의 구조와 방향(평균의 단조성)만 검사한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "experiments" / "results" / "checks_vs_labels.json"


def _saved() -> dict:
    if not RESULT.exists():
        pytest.skip("결과 파일이 없다: experiments/results/checks_vs_labels.json")
    return json.loads(RESULT.read_text(encoding="utf-8"))


def test_raw_measurements_follow_labels() -> None:
    """측정값 평균이 라벨 순서대로 커야 한다. 이게 무너지면 검사 함수가
    라벨과 무관한 것을 재고 있다는 뜻이다 (specificity 가 그랬다)."""
    saved = _saved()
    length = saved["length"]["raw_mean"]
    assert length["short"] < length["normal"] < length["long"]
    overlap = saved["extractiveness"]["raw_mean"]
    assert overlap["normal"] < overlap["high"] < overlap["fully"]


def test_reported_agreement_numbers() -> None:
    """문서가 인용하는 수치. 검사 함수나 임계값을 바꾸면 여기가 먼저 깨진다."""
    saved = _saved()
    assert saved["length"]["balanced_accuracy"] == pytest.approx(0.446, abs=0.002)
    assert saved["extractiveness"]["balanced_accuracy"] == pytest.approx(0.598, abs=0.002)
    assert saved["length"]["pass_rate"]["normal"] == pytest.approx(0.204, abs=0.002)
    assert saved["_meta"]["summaries"] == 5379


@pytest.mark.macsum
def test_recompute_matches_saved() -> None:
    from experiments.checks_vs_labels import evaluate, load_summaries
    from engine.domain_loader import load_domain

    saved = _saved()
    fresh = evaluate(load_domain(ROOT / "domains" / "summarization.yaml"),
                     load_summaries(ROOT / "data" / "macsum" / "dataset" / "macdoc"))
    for axis in ("length", "extractiveness"):
        assert fresh[axis]["balanced_accuracy"] == pytest.approx(
            saved[axis]["balanced_accuracy"], abs=1e-6)
        assert fresh[axis]["n"] == saved[axis]["n"]

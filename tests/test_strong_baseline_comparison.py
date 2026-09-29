"""experiments/strong_baseline_comparison.py 결과가 README/CLAUDE.md 에 적은
수치와 일치하는지 고정한다. API·MACSum 없이 커밋된 CSV만으로 돈다.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

RESULT = Path(__file__).resolve().parents[1] / "experiments" / "results" / "strong_baseline_comparison.csv"


def _pivot() -> pd.DataFrame:
    if not RESULT.exists():
        pytest.skip(f"결과 파일이 없다: {RESULT.name}")
    df = pd.read_csv(RESULT)
    return df.pivot(index="doc", columns="condition", values="independent_score")


def test_five_documents_four_conditions() -> None:
    pivot = _pivot()
    assert len(pivot) == 5
    assert set(pivot.columns) == {
        "B_custom_instruction", "B_plus_knows_preference", "B_llm_generated", "D_our_tool",
    }


def test_d_beats_plain_b_on_every_document() -> None:
    """D vs B(기존): 5/5. 이건 원래 compare_baselines.py 결과와 같은 방향이어야 한다."""
    pivot = _pivot()
    diff = pivot["D_our_tool"] - pivot["B_custom_instruction"]
    assert (diff > 0).all(), f"D가 기존 B를 매 문서에서 이겨야 하는데 아니다: {diff.to_dict()}"


def test_knowing_the_preference_closes_most_of_the_gap() -> None:
    """B+(취향을 아는 사람의 지침) vs B(기존): 5/5 - 기존 B가 정말 약했다는 증거.
    그리고 D vs B+ 는 3/5 - 우위라고 부를 수 없는 수준이다."""
    pivot = _pivot()
    bplus_vs_b = pivot["B_plus_knows_preference"] - pivot["B_custom_instruction"]
    assert (bplus_vs_b > 0).all(), "B+가 기존 B를 모든 문서에서 이겨야 한다"

    d_vs_bplus = pivot["D_our_tool"] - pivot["B_plus_knows_preference"]
    wins = int((d_vs_bplus > 0).sum())
    assert wins <= 3, (
        f"D가 B+를 {wins}/5로 이겼다 - '사실상 동률'이라는 보고와 어긋난다. "
        "문서를 다시 읽고 README 2-2 절을 갱신할 것."
    )


def test_d_beats_the_realistic_alternative() -> None:
    """B-LLM(취향을 설명 → 모델이 지침 작성)은 실제 대안이고, D가 이걸 가장
    크게 이긴다. 이 결과가 무너지면 프로젝트의 핵심 주장이 흔들린다."""
    pivot = _pivot()
    diff = pivot["D_our_tool"] - pivot["B_llm_generated"]
    assert (diff > 0).all(), f"D가 B-LLM을 매 문서에서 이겨야 하는데 아니다: {diff.to_dict()}"
    assert diff.mean() > 0.03, f"D vs B-LLM 격차가 보고된 값(+0.057)보다 훨씬 작아졌다: {diff.mean():.4f}"

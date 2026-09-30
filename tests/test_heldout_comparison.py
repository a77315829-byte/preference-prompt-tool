"""experiments/heldout_comparison.py 결과가 README·CLAUDE.md 에 적은 수치와
맞는지 고정한다. API·MACSum 없이 커밋된 결과 파일만으로 돈다."""

import json
from pathlib import Path

import pandas as pd
import pytest

RESULTS = Path(__file__).resolve().parents[1] / "experiments" / "results"
CSV = RESULTS / "heldout_comparison.csv"
SUMMARY = RESULTS / "heldout_comparison.json"


@pytest.fixture(scope="module")
def data():
    if not CSV.exists():
        pytest.skip("결과 파일이 없다")
    return pd.read_csv(CSV), json.loads(SUMMARY.read_text(encoding="utf-8"))


def test_design_is_what_the_docs_say(data) -> None:
    df, summary = data
    personas = df.drop_duplicates("persona")
    assert len(personas) == 30 and summary["n"] == 30
    # 학습 문서와 채점 문서가 다르고, 한 문서는 한 번만 쓰였다.
    assert (personas["learn_doc"] != personas["eval_doc"]).all()
    docs = list(personas["learn_doc"]) + list(personas["eval_doc"])
    assert len(set(docs)) == len(docs)
    # MACSum 에서 topic 없는 요약은 추출성이 전부 normal 이다 - 길이 축만 시험했다.
    assert set(personas["extractiveness"]) == {"normal"}
    assert summary["model"] == "openai/gpt-4o-mini"
    assert summary["spend_dollars"] < 0.1


def _paired(df, metric, a, b):
    pivot = df.pivot(index="persona", columns="condition", values=metric)
    diff = pivot[a] - pivot[b]
    return int((diff > 0).sum()), int((diff < 0).sum()), round(float(diff.mean()), 4)


def test_reported_paired_results(data) -> None:
    df, _ = data
    assert _paired(df, "rouge_l", "D_our_tool", "A_no_prompt")[:2] == (27, 3)
    assert _paired(df, "rouge_l", "D_our_tool", "B_custom_instruction")[:2] == (19, 11)
    assert _paired(df, "rouge_l", "D_our_tool", "B_plus_knows_preference")[:2] == (15, 15)
    assert _paired(df, "checks_score", "D_our_tool", "B_custom_instruction")[:2] == (18, 4)
    assert _paired(df, "checks_score", "D_our_tool", "B_plus_knows_preference")[:2] == (0, 10)


def test_reported_means_and_learning_rate(data) -> None:
    df, summary = data
    rouge = df.groupby("condition")["rouge_l"].mean().to_dict()
    assert rouge == pytest.approx({"A_no_prompt": 0.130, "B_custom_instruction": 0.170,
                                   "B_plus_knows_preference": 0.183, "D_our_tool": 0.182}, abs=0.001)
    assert round(summary["learned_exact_rate"], 2) == 0.63

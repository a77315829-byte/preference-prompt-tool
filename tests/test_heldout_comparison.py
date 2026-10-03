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


V2_CSV = RESULTS / "heldout_comparison_summarization_v2.csv"
V2_SUMMARY = RESULTS / "heldout_comparison_summarization_v2.json"


def test_v2_ratio_instructions_did_not_help() -> None:
    """docs/length_v2_preregistration.md 2단계. 비율로 지시하면 모델이 따르지
    않아 선호 복원이 무너지고 ROUGE-L 도 오르지 않았다 - 이 음성 결과를 고정한다."""
    if not V2_CSV.exists():
        pytest.skip("결과 파일이 없다")
    summary = json.loads(V2_SUMMARY.read_text(encoding="utf-8"))
    assert summary["domain"] == "summarization_v2" and summary["n"] == 30
    assert round(summary["learned_exact_rate"], 1) == 0.1
    vs = summary["D_vs_baseline_D"]
    assert (vs["wins"], vs["losses"]) == (13, 17) and vs["sign_test_p"] > 0.05
    # A/B/B+ 는 같은 프롬프트라 v1 과 출력이 같다.
    v1, v2 = pd.read_csv(CSV), pd.read_csv(V2_CSV)
    for cond in ("A_no_prompt", "B_custom_instruction", "B_plus_knows_preference"):
        a = v1[v1.condition == cond].set_index("persona")["rouge_l"]
        b = v2[v2.condition == cond].set_index("persona")["rouge_l"]
        assert (a == b).all()


RC_SUMMARY = RESULTS / "heldout_comparison_summarization_ratio_check.json"


def test_ratio_check_keeps_v1_prompts_and_misses_its_criterion() -> None:
    """3단계 (가): 지시는 v1, 측정만 비율. D 프롬프트 문구가 v1 과 같으므로
    ROUGE-L 차이는 학습 결과가 달라진 몫뿐이다. 주 기준(길이 축 >= 27/30)은
    미달이었다 - 축별 수치는 문서에 있고 여기서는 요약 파일을 고정한다."""
    if not RC_SUMMARY.exists():
        pytest.skip("결과 파일이 없다")
    from engine.domain_loader import load_domain
    from engine.generator import build_prompt
    v1 = load_domain("domains/summarization.yaml")
    rc = load_domain("domains/summarization_ratio_check.yaml")
    for length in ("short", "normal", "long"):
        combo = {"length": length, "extractiveness": "normal", "topic": ""}
        assert build_prompt(v1, combo) == build_prompt(rc, combo)
    summary = json.loads(RC_SUMMARY.read_text(encoding="utf-8"))
    assert round(summary["learned_exact_rate"], 1) == 0.3
    vs = summary["D_vs_baseline_D"]
    assert (vs["wins"], vs["losses"], vs["ties"]) == (15, 11, 4) and vs["sign_test_p"] > 0.05


V3_SUMMARY = RESULTS / "heldout_comparison_summarization_v3.json"
V3_GATE = RESULTS / "length_v3_compliance.json"


def test_v3_word_count_instructions_pass_the_gate_and_the_criterion() -> None:
    """4단계 (나). 관문(출력 비율이 사람 중앙값 ±3%p)을 통과했고, 30쌍에서 D 의 ROUGE-L 은
    올랐지만 등록한 기준(p<0.05)에는 못 미쳤다 - 그 상태를 고정한다."""
    if not V3_SUMMARY.exists():
        pytest.skip("결과 파일이 없다")
    gate = json.loads(V3_GATE.read_text(encoding="utf-8"))
    assert gate["gate"]["passed"] is True
    v3 = gate["median_ratio"]["v3"]
    assert v3["short"] < v3["normal"] < v3["long"]
    summary = json.loads(V3_SUMMARY.read_text(encoding="utf-8"))
    vs = summary["D_vs_baseline_D"]
    assert (vs["wins"], vs["losses"]) == (20, 10) and 0.05 < vs["sign_test_p"] < 0.1
    assert summary["spend_dollars"] < 0.1

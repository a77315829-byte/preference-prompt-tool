"""experiments/length_ratio_labels.py 결과를 고정한다. 판단 기준은
docs/length_v2_preregistration.md 에 실행 전에 커밋했다. 커밋된 결과 파일만
읽으므로 API·MACSum 없이 돈다."""

import json
from pathlib import Path

import pytest

from experiments.length_ratio_labels import balanced_accuracy, classify, fit_cuts

RESULT = Path(__file__).resolve().parents[1] / "experiments" / "results" / "length_ratio_labels.json"


@pytest.fixture(scope="module")
def result():
    if not RESULT.exists():
        pytest.skip("결과 파일이 없다")
    return json.loads(RESULT.read_text(encoding="utf-8"))


def test_thresholds_never_saw_test_or_heldout_documents(result) -> None:
    leak = result["leak_check"]
    assert leak["train_test_overlap"] == 0
    assert leak["heldout_docs"] == 60 and leak["heldout_in_train"] == 0


def test_primary_criterion_as_registered(result) -> None:
    test = result["test"]
    assert test["v1_yaml"]["balanced_accuracy"] == pytest.approx(0.451, abs=0.001)
    assert test["v1_refit"]["balanced_accuracy"] == pytest.approx(0.494, abs=0.001)
    assert test["v2_ratio"]["balanced_accuracy"] == pytest.approx(0.710, abs=0.001)
    assert result["primary_criterion"]["met"] is True


def test_ratio_works_only_without_topic(result) -> None:
    """topic 이 없으면 원문 전체가 요약 대상이라 비율이 라벨을 거의 재현하고,
    topic 이 있으면 분모(관련 구간)를 모르므로 문장 수보다도 못하다."""
    no_topic = result["test_by_topic"]["no_topic"]
    with_topic = result["test_by_topic"]["with_topic"]
    assert no_topic["v2_ratio"]["balanced_accuracy"] > 0.95
    assert no_topic["v2_ratio"]["short_vs_normal"] > 0.95
    assert with_topic["v2_ratio"]["balanced_accuracy"] < with_topic["v1_refit"]["balanced_accuracy"]
    assert with_topic["v2_ratio"]["short_vs_normal"] < 0.60  # 등록한 기준: 구분되지 않는다


def test_fit_cuts_separates_clean_bands() -> None:
    xs = [0.05, 0.06, 0.10, 0.11, 0.15, 0.16]
    labels = ["short", "short", "normal", "normal", "long", "long"]
    cuts = fit_cuts(xs, labels)
    assert balanced_accuracy(labels, [classify(x, cuts) for x in xs]) == 1.0

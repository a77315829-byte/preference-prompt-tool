"""experiments/estimator_ablation.py 결과(가상 사용자, API 0회)를 고정한다.
docs/code_review_response.md 와 README 가 이 수치를 인용한다."""

import json
from pathlib import Path

import pytest

RESULT = Path(__file__).resolve().parents[1] / "experiments" / "results" / "estimator_ablation.json"


@pytest.fixture(scope="module")
def result():
    if not RESULT.exists():
        pytest.skip("결과 파일이 없다")
    return json.loads(RESULT.read_text(encoding="utf-8"))


def test_learning_rate_barely_matters_between_05_and_1(result) -> None:
    exp = result["experiment_selector"]
    for noise in (0.0, 0.1):
        at8 = [exp[f"lr={lr} noise={noise}"]["exact@8"] for lr in (0.25, 0.5, 0.75, 1.0)]
        assert max(at8) - min(at8) <= 0.07
    # 0.1 은 잡음이 없어도 6회차에 덜 맞힌다.
    assert exp["lr=0.1 noise=0.0"]["exact@6"] < exp["lr=0.5 noise=0.0"]["exact@6"]


def test_app_selector_stops_early_but_cannot_recover_from_a_misclick(result) -> None:
    app, exp = result["app_selector"], result["experiment_selector"]
    assert app["lr=0.5 noise=0.0"]["exact@8"] == 1.0
    assert app["lr=0.5 noise=0.0"]["mean_rounds"] == pytest.approx(4.0, abs=0.1)
    # 같은 질문을 다시 묻지 않으므로 잘못 누른 한 번이 굳는다 - '이전 선택 수정'의 근거.
    assert app["lr=0.5 noise=0.1"]["exact@8"] < exp["lr=0.5 noise=0.1"]["exact@8"] - 0.1

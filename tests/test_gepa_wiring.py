"""1주차 관통용 스크립트: 이 venv에서 gepa.optimize가 실제로 동작하는지
최소 비용(작은 trainset, max_metric_calls 제한)으로 배선만 확인한다."""

import gepa
from dotenv import load_dotenv

load_dotenv()

trainset = [
    {"input": "1 + 1 = ?", "answer": "2", "additional_context": {}},
    {"input": "프랑스의 수도는?", "answer": "파리", "additional_context": {}},
]


def main() -> None:
    result = gepa.optimize(
        seed_candidate={"system_prompt": "질문에 짧게 답하라."},
        trainset=trainset,
        valset=trainset,
        task_lm="openai/gpt-4.1-mini",
        reflection_lm="openai/gpt-4.1-mini",
        max_metric_calls=8,
        display_progress_bar=True,
    )
    print("best candidate:", result.best_candidate)


if __name__ == "__main__":
    main()


# --- 자동 회귀 테스트 ------------------------------------------------------

import pytest


@pytest.mark.api
def test_optimize_returns_a_candidate_with_our_key() -> None:
    """설치된 gepa 가 우리가 넘긴 seed_candidate 의 키를 그대로 돌려주는지.

    gepa 0.1.4 는 CLAUDE.md 초안의 metric= 인자를 받지 않아서 배선을
    DefaultAdapter 로 바꿔야 했다. 버전이 올라가며 이 계약이 바뀌면
    optimize/run_gepa.py 가 조용히 깨지므로 여기서 잡는다.
    """
    result = gepa.optimize(
        seed_candidate={"system_prompt": "질문에 짧게 답하라."},
        trainset=trainset,
        valset=trainset,
        task_lm="openai/gpt-4.1-mini",
        reflection_lm="openai/gpt-4.1-mini",
        max_metric_calls=4,
        display_progress_bar=False,
    )
    assert "system_prompt" in result.best_candidate
    assert result.best_candidate["system_prompt"].strip()

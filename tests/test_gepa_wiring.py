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

"""4~5주차 검증용: estimator+selector가 숨겨진 페르소나(축별 정답값)를
실제로 복원하는지, 3가지 알고리즘의 수렴 속도를 비교한다.

API 호출 없이 합성 오라클(정답값과 더 많이 일치하는 콤보를 선택)로
검증한다 - 실제 생성/사람 대행 실험은 9~10주차 experiments/run_all.py 몫."""

from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator
from engine.selector import RandomSelector, SequentialAxisSelector, UncertaintySelector


def synthetic_winner(hidden_combo: dict, combo_a: dict, combo_b: dict) -> str:
    def match_count(combo: dict) -> int:
        return sum(1 for k, v in hidden_combo.items() if combo.get(k) == v)

    return "a" if match_count(combo_a) >= match_count(combo_b) else "b"


def run(selector_cls, domain, hidden_combo: dict, n_rounds: int, seed: int = 0) -> list[int]:
    estimator = Estimator(domain)
    selector = selector_cls(domain, seed=seed)
    restored_counts = []

    for _ in range(n_rounds):
        combo_a, combo_b = selector.next_pair(estimator)
        winner = synthetic_winner(hidden_combo, combo_a, combo_b)
        estimator.update(Comparison(combo_a, combo_b, winner))
        restored = sum(
            1
            for name in estimator.enum_axis_names()
            if estimator.preferred_value(name) == hidden_combo[name]
        )
        restored_counts.append(restored)

    return restored_counts


def main() -> None:
    domain = load_domain("domains/summarization.yaml")
    hidden_combo = {"length": "short", "extractiveness": "fully"}
    n_axes = len(hidden_combo)
    n_rounds = 15

    algorithms = [
        ("random", RandomSelector),
        ("sequential", SequentialAxisSelector),
        ("uncertainty", UncertaintySelector),
    ]

    for name, cls in algorithms:
        # 여러 시드로 돌려서 평균 수렴 곡선을 본다.
        curves = [run(cls, domain, hidden_combo, n_rounds, seed=seed) for seed in range(10)]
        avg_curve = [sum(c[i] for c in curves) / len(curves) for i in range(n_rounds)]
        rounded = [round(v, 2) for v in avg_curve]
        print(f"{name:12s} restored/{n_axes} (10 seeds 평균): {rounded}")


if __name__ == "__main__":
    main()

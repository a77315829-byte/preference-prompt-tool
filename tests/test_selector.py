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


# --- 자동 회귀 테스트 ------------------------------------------------------
# main() 은 수렴 곡선을 눈으로 보기 위한 것이고, 아래가 실제로 실패할 수 있는
# 검사다. selector/estimator 는 라이브러리로 대체 불가능한 핵심 기여인데
# 자동 테스트가 없어서, 여기 값들은 전부 위 main() 출력으로 실측해 고정했다.
# API 호출은 없다 - 합성 오라클만 쓴다.

import statistics

import pytest

HIDDEN = {"length": "short", "extractiveness": "fully"}
N_AXES = len(HIDDEN)
N_ROUNDS = 15
SEEDS = range(10)


@pytest.fixture(scope="module")
def domain():
    return load_domain("domains/summarization.yaml")


def _final_restored(selector_cls, domain) -> list[int]:
    return [
        run(selector_cls, domain, HIDDEN, N_ROUNDS, seed=seed)[-1]
        for seed in SEEDS
    ]


@pytest.mark.parametrize("selector_cls", [SequentialAxisSelector, UncertaintySelector])
def test_targeted_selectors_fully_recover_and_stay(selector_cls, domain) -> None:
    """순차·불확실도는 숨긴 선호를 전부 복원하고 그 상태를 유지해야 한다.

    실측(10시드 평균)으로 둘 다 6회차에 2/2에 도달해 15회차까지 유지한다.
    """
    for seed in SEEDS:
        curve = run(selector_cls, domain, HIDDEN, N_ROUNDS, seed=seed)
        assert curve[-1] == N_AXES, f"seed={seed} 에서 복원 실패: {curve}"
        # 도달 후 다시 떨어지지 않아야 한다.
        first_full = curve.index(N_AXES)
        assert all(v == N_AXES for v in curve[first_full:]), f"seed={seed} 에서 되돌아감: {curve}"
        assert first_full <= 7, f"seed={seed} 수렴이 8회를 넘었다: {curve}"


def test_random_selection_is_measurably_worse(domain) -> None:
    """무작위 질의는 같은 횟수에서 복원을 유지하지 못한다.

    이 차이가 "질의를 고르는 것이 의미 있다"는 주장의 실체다. 평균으로
    비교한다 - 시드마다 들쭉날쭉해서 개별 시드로는 단정할 수 없다.
    """
    random_final = statistics.fmean(_final_restored(RandomSelector, domain))
    uncertainty_final = statistics.fmean(_final_restored(UncertaintySelector, domain))

    assert uncertainty_final == N_AXES
    assert random_final < N_AXES, f"무작위가 전부 복원했다({random_final}). 비교 주장이 무의미해진다."


@pytest.mark.parametrize(
    "selector_cls", [RandomSelector, SequentialAxisSelector, UncertaintySelector]
)
def test_same_seed_reproduces_same_curve(selector_cls, domain) -> None:
    """시드를 고정하면 결과가 재현돼야 한다. 실험 재현성의 전제다."""
    first = run(selector_cls, domain, HIDDEN, N_ROUNDS, seed=3)
    second = run(selector_cls, domain, HIDDEN, N_ROUNDS, seed=3)
    assert first == second


@pytest.mark.parametrize(
    "selector_cls", [RandomSelector, SequentialAxisSelector, UncertaintySelector]
)
def test_pairs_always_differ_on_some_axis(selector_cls, domain) -> None:
    """두 후보가 모든 축에서 같으면 사용자에게 똑같은 것을 두 개 보여주게 되고,
    그 선택에서는 아무 정보도 얻지 못한다."""
    estimator = Estimator(domain)
    selector = selector_cls(domain, seed=0)
    identical = 0
    for _ in range(30):
        combo_a, combo_b = selector.next_pair(estimator)
        if combo_a == combo_b:
            identical += 1
        estimator.update(Comparison(combo_a, combo_b, synthetic_winner(HIDDEN, combo_a, combo_b)))
    # 무작위 방식은 우연히 같은 조합을 뽑을 수 있다. 목표 방식은 그러면 안 된다.
    if selector_cls is RandomSelector:
        assert identical < 15
    else:
        assert identical == 0


if __name__ == "__main__":
    main()


# --- 사람용 옵션 (contrast_first / avoid_repeats) ---------------------------
# 앱이 켜는 옵션이다. 기본값은 꺼져 있고, 위 테스트들이 기본 동작을 고정한다.

import itertools

from engine.selector import _question_key

PEOPLE = {"contrast_first": True, "avoid_repeats": True}
PEOPLE_DOMAINS = ["summarization", "coding", "email", "review", "macsum_eval_agent"]


def _people_session(domain, choose, seed: int = 0, limit: int = 8):
    """질문이 떨어지거나 limit 에 닿을 때까지 돌린다. 물은 질문 목록을 돌려준다."""
    estimator = Estimator(domain)
    selector = UncertaintySelector(domain, seed=seed, **PEOPLE)
    asked = []
    for _ in range(limit):
        pair = selector.next_pair(estimator)
        if pair is None:
            break
        combo_a, combo_b = pair
        asked.append((combo_a, combo_b))
        estimator.update(Comparison(combo_a, combo_b, choose(combo_a, combo_b)))
    return estimator, asked


def _all_hidden(domain):
    axes = [a for a in domain.axes if a.type == "enum"]
    for values in itertools.product(*[[v.value for v in a.values] for a in axes]):
        yield dict(zip([a.name for a in axes], values))


@pytest.mark.parametrize("domain_file", PEOPLE_DOMAINS)
def test_people_mode_never_shows_the_same_question_twice(domain_file) -> None:
    """화면에는 묻는 축의 두 값만 보인다. 다른 축 값만 바꾼 쌍도 사람에게는
    같은 질문이라, 질문은 (축, 두 값) 단위로 한 번씩만 묻는다."""
    domain = load_domain(f"domains/{domain_file}.yaml")
    for hidden in _all_hidden(domain):
        for seed in range(3):
            for chooser in (lambda a, b: synthetic_winner(hidden, a, b), lambda a, b: "a"):
                _, asked = _people_session(domain, chooser, seed=seed)
                keys = [_question_key(a, b) for a, b in asked]
                assert None not in keys, "한 번에 축 하나만 달라야 한다"
                assert len(set(keys)) == len(keys), f"같은 질문이 반복됐다: {keys}"


@pytest.mark.parametrize("domain_file", PEOPLE_DOMAINS)
def test_people_mode_recovers_every_preference(domain_file) -> None:
    """반복을 없애고 일찍 끝내도 일관된 사용자의 선호는 전부 맞혀야 한다."""
    domain = load_domain(f"domains/{domain_file}.yaml")
    for hidden in _all_hidden(domain):
        for seed in range(3):
            estimator, _ = _people_session(
                domain, lambda a, b: synthetic_winner(hidden, a, b), seed=seed, limit=50
            )
            for name, value in hidden.items():
                assert estimator.preferred_value(name) == value, (hidden, seed)


def test_people_mode_always_includes_the_current_leader(domain) -> None:
    """이미 진 두 값끼리 붙이면 1위를 가리는 데 정보가 없다. 둘 다 싫은
    선택지를 받은 사용자가 이상하다고 느낀 원인이었다."""
    hidden = {"length": "normal", "extractiveness": "normal"}
    estimator = Estimator(domain)
    selector = UncertaintySelector(domain, seed=0, **PEOPLE)
    seen_axes = set()
    while (pair := selector.next_pair(estimator)) is not None:
        combo_a, combo_b = pair
        axis, values = _question_key(combo_a, combo_b)
        if axis in seen_axes:
            assert estimator.preferred_value(axis) in values
        seen_axes.add(axis)
        estimator.update(Comparison(combo_a, combo_b, synthetic_winner(hidden, combo_a, combo_b)))


def test_people_mode_ends_early_on_two_value_axes() -> None:
    coding = load_domain("domains/coding.yaml")
    selector = UncertaintySelector(coding, seed=0, **PEOPLE)
    assert selector.max_questions() == 3
    _, asked = _people_session(coding, lambda a, b: "a", limit=8)
    assert len(asked) == 3


def test_people_mode_asks_extremes_first(domain) -> None:
    """처음 묻는 축은 양 끝 값끼리여야 A/B 차이가 눈에 보인다."""
    combo_a, combo_b = UncertaintySelector(domain, seed=0, **PEOPLE).next_pair(Estimator(domain))
    axis, values = _question_key(combo_a, combo_b)
    all_values = [v.value for v in domain.axis(axis).values]
    assert values == {all_values[0], all_values[-1]}


def test_default_behaviour_is_unchanged(domain) -> None:
    """옵션을 명시적으로 끈 것과 안 넘긴 것이 같아야 실험 재현성이 유지된다."""
    for seed in range(3):
        assert run(UncertaintySelector, domain, HIDDEN, N_ROUNDS, seed=seed) == run(
            lambda d, seed: UncertaintySelector(d, seed=seed, contrast_first=False, avoid_repeats=False),
            domain, HIDDEN, N_ROUNDS, seed=seed,
        )

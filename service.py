"""비교 루프의 순수 레이어. Streamlit 을 전혀 import 하지 않는다.

**왜 분리하는가.** 나중에 FastAPI + Next.js 로 옮길 계획이라, UI 가 무엇이든
상관없는 층이 필요하다. 지금 `app.py` 는 UI 와 상태 관리가 섞여 있어서
옮길 때 다시 짜야 한다. 이 파일만 보면 화면이 Streamlit 인지 브라우저인지
알 수 없어야 한다 (`budget.py`, `feedback.py`, `expert_profile.py` 와 같은 방침).

노출하는 것은 세 함수와 상태 하나다.

    start_session(source_text, domain_key, ...) -> SessionState
    submit_choice(state, pair_id, chosen)       -> SessionState
    optimize(state, on_progress)                -> str

**`SessionState` 는 순수 데이터다.** 엔진 객체(Estimator·Selector)를 담지
않고, 선택 이력만 들고 있다가 필요할 때 **재생해서 복원한다**(`_rebuild`).
이유가 두 가지다.

1. 그대로 직렬화된다. FastAPI 로 옮길 때 세션 저장소가 dict 든 sqlite 든
   이 dataclass 를 그대로 넣으면 된다.
2. `UncertaintySelector` 는 내부 RNG 를 호출마다 진행시키므로, 이력을 같은
   순서로 재생하면 같은 쌍이 나온다. 객체를 들고 다닐 필요가 없다.

재생 비용은 8라운드짜리라 무시할 수 있다 (업데이트 8번).

**engine/ · checks/ · domains/ · optimize/ 는 한 줄도 고치지 않는다.**
호출만 한다. 그게 이 프로젝트의 확장성 주장의 실체다 (절대 규칙 1).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from typing import Callable

from engine.demo_generator import generate_demo
from engine.domain_loader import Domain, load_domain
from engine.estimator import Comparison, Estimator
from engine.generator import generate_all
from engine.metric_builder import build_metric
from engine.selector import UncertaintySelector
from optimize.run_gepa import MetricEvaluator, build_seed_prompt

# 비교 횟수. 8회로 고정한 근거는 실험 쪽에 있다 - 순차·불확실도 두 알고리즘
# 모두 6회차에 완전 복원했고, 그 이상은 사용자 노력만 늘린다.
TOTAL_ROUNDS = 8

# 선택기 시드. 고정해야 같은 이력이 같은 쌍을 낸다.
SELECTOR_SEED = 0

# GEPA 호출 예산. 진행률의 분모이기도 하다.
GEPA_METRIC_CALLS = 20


class StaleChoiceError(RuntimeError):
    """이미 지난 쌍에 대한 선택. HTTP 로 옮기면 409 에 해당한다."""


@dataclass(frozen=True)
class Candidate:
    """후보 하나. `combo` 는 화면에 보여주지 않는다 - 어느 축이 다른지
    알려주면 사용자가 내용이 아니라 축을 보고 고른다."""

    id: str
    text: str
    combo: dict[str, str]


@dataclass(frozen=True)
class PairView:
    pair_id: str
    a: Candidate
    b: Candidate


@dataclass(frozen=True)
class AxisView:
    """화면에 보여줄 축 하나의 상태.

    `discriminated` 가 게이지의 값이다. **`confidence` 를 게이지로 쓰지
    않는다** - 실측에서 3값 축은 비교를 24회까지 늘려도 0.06 에 머무는데
    선호는 9/9 정확히 복원했다. 차오르는 애니메이션을 걸면 6% 에서 6% 로
    움직이고, 맞힌 사용자에게 "확신도 6%"라고 말하게 된다.

    대신 **그 축이 갈린 비교 횟수**를 보여준다. 코드로 셀 수 있고, 단조
    증가하고, 축마다 다르게 차오르고(선택기가 축을 번갈아 고른다), 확률
    주장을 하지 않는다. 엔진이 이미 쓰는 개념과도 같다 -
    `Estimator.update` 는 두 후보의 축값이 같으면 그 축을 건너뛴다.

    `confidence` 는 수치로만 병기한다. 축끼리 상대 비교하는 원래 용도
    (metric_builder 의 축 가중치)로는 유효하다.
    """

    name: str
    estimate: str | None
    confidence: float
    discriminated: int
    total_rounds: int

    @property
    def fill(self) -> float:
        """게이지 채움 비율 0.0~1.0."""
        if self.total_rounds <= 0:
            return 0.0
        return min(1.0, self.discriminated / self.total_rounds)


@dataclass
class SessionState:
    """세션 하나의 전부. 엔진 객체를 담지 않아 그대로 직렬화된다."""

    session_id: str
    domain_key: str
    domain_path: str
    source_text: str
    model: str
    demo_mode: bool
    total_rounds: int = TOTAL_ROUNDS
    # (combo_a, combo_b, winner) 튜플들. Comparison 을 그대로 담지 않는
    # 이유는 직렬화 때문이다.
    history: list[tuple[dict[str, str], dict[str, str], str]] = field(default_factory=list)
    pair: PairView | None = None
    axes: list[AxisView] = field(default_factory=list)
    done: bool = False
    # 최적화 진행 상황. 스레드가 여기에만 쓴다.
    optimize_progress: float = 0.0
    optimize_status: str = "idle"  # idle | running | done | error
    prompt: str | None = None
    error: str | None = None

    @property
    def round(self) -> int:
        """지금 몇 번째 비교를 보여주는 중인가 (1부터)."""
        return min(len(self.history) + 1, self.total_rounds)

    @property
    def answered(self) -> int:
        return len(self.history)


def _rebuild(state: SessionState) -> tuple[Domain, Estimator, UncertaintySelector]:
    """이력을 재생해 엔진 객체를 복원한다.

    선택기의 RNG 를 이력과 같은 횟수만큼 진행시켜야 다음 쌍이 재현되므로,
    업데이트마다 `next_pair` 를 한 번씩 부른다. 그 결과는 버린다 - 목적은
    RNG 상태를 맞추는 것이다.
    """
    domain = load_domain(state.domain_path)
    estimator = Estimator(domain)
    selector = UncertaintySelector(domain, seed=SELECTOR_SEED)

    for combo_a, combo_b, winner in state.history:
        selector.next_pair(estimator)
        estimator.update(Comparison(combo_a=combo_a, combo_b=combo_b, winner=winner))
    return domain, estimator, selector


def _axis_views(state: SessionState, estimator: Estimator) -> list[AxisView]:
    """축별 추정값과 갈린 비교 횟수.

    자유 키워드 축(요약의 topic)은 빠진다 - `enum_axis_names()` 가 열거형만
    돌려주기 때문이고, 그 축은 추정값·확신도 모델에 맞지 않는다. 그래서
    요약 도메인의 게이지는 3개가 아니라 **2개**다. 도메인마다 개수가
    다르므로 화면이 개수를 하드코딩하면 안 된다.
    """
    views = []
    for name in estimator.enum_axis_names():
        discriminated = sum(
            1
            for combo_a, combo_b, _ in state.history
            if combo_a.get(name) is not None
            and combo_a.get(name) != combo_b.get(name)
        )
        views.append(
            AxisView(
                name=name,
                estimate=estimator.preferred_value(name) if state.history else None,
                confidence=round(estimator.confidence(name), 4),
                discriminated=discriminated,
                total_rounds=state.total_rounds,
            )
        )
    return views


def _generate_pair(
    state: SessionState,
    domain: Domain,
    combo_a: dict[str, str],
    combo_b: dict[str, str],
) -> PairView:
    """후보 두 개를 만든다. 데모 모드면 API 를 쓰지 않는다.

    API 모드는 `generate_all` 로 **동시에** 호출한다. 순차로 부르면
    라운드당 20.3초였던 것이 4.2초로 줄었다(배포 실측). 순서 보존이
    중요하다 - 먼저 끝난 것을 앞에 놓으면 A/B 가 뒤바뀌어 사용자가 고른
    것과 다른 축을 학습한다.
    """
    if state.demo_mode:
        texts = [
            generate_demo(domain, state.source_text, combo_a),
            generate_demo(domain, state.source_text, combo_b),
        ]
    else:
        texts = generate_all(
            domain, state.source_text, [combo_a, combo_b], model=state.model
        )

    pair_id = uuid.uuid4().hex[:12]
    return PairView(
        pair_id=pair_id,
        a=Candidate(id=f"{pair_id}-a", text=texts[0], combo=combo_a),
        b=Candidate(id=f"{pair_id}-b", text=texts[1], combo=combo_b),
    )


def start_session(
    source_text: str,
    domain_key: str,
    domain_path: str,
    *,
    model: str,
    demo_mode: bool,
    total_rounds: int = TOTAL_ROUNDS,
) -> SessionState:
    """세션을 열고 첫 쌍을 만든다."""
    state = SessionState(
        session_id=uuid.uuid4().hex[:12],
        domain_key=domain_key,
        domain_path=domain_path,
        source_text=source_text,
        model=model,
        demo_mode=demo_mode,
        total_rounds=total_rounds,
    )
    domain, estimator, selector = _rebuild(state)
    combo_a, combo_b = selector.next_pair(estimator)
    state.pair = _generate_pair(state, domain, combo_a, combo_b)
    state.axes = _axis_views(state, estimator)
    return state


def submit_choice(state: SessionState, pair_id: str, chosen: str) -> SessionState:
    """선택을 반영하고 다음 쌍을 만든다.

    `pair_id` 가 현재 쌍과 다르면 거부한다. 뒤로 가기나 중복 클릭으로
    이전 쌍의 선택이 늦게 도착하면, 그걸 그대로 받으면 엉뚱한 비교가
    이력에 들어간다.
    """
    if chosen not in ("a", "b"):
        raise ValueError(f"chosen 은 'a' 또는 'b' 여야 한다: {chosen!r}")
    if state.pair is None:
        # 끝난 세션에 늦게 도착한 선택도 만료로 다룬다. 호출하는 쪽이
        # 두 예외를 구분해 처리하게 만들 이유가 없다.
        raise StaleChoiceError("현재 쌍이 없다. 세션이 이미 끝났거나 시작되지 않았다.")
    if state.pair.pair_id != pair_id:
        raise StaleChoiceError(
            f"이 쌍은 더 이상 현재 쌍이 아니다 (받은 {pair_id}, 현재 {state.pair.pair_id})"
        )

    updated = replace(
        state,
        history=[*state.history, (state.pair.a.combo, state.pair.b.combo, chosen)],
        pair=None,
    )

    domain, estimator, selector = _rebuild(updated)
    updated.axes = _axis_views(updated, estimator)

    if len(updated.history) >= updated.total_rounds:
        updated.done = True
        return updated

    combo_a, combo_b = selector.next_pair(estimator)
    updated.pair = _generate_pair(updated, domain, combo_a, combo_b)
    return updated


def prefetch_branches(state: SessionState) -> None:
    """다음 라운드 후보를 a/b 두 분기 모두 미리 만들어 캐시에 넣는다.

    **비용이 두 배다.** 다음 쌍은 갱신된 추정에 따라 달라지므로 두 분기를
    다 만들어야 하고, 라운드당 4회 호출 중 2회는 버려진다. 공개 배포에서는
    공용 키에 하루 상한이 걸려 있어 동시 사용 인원이 절반으로 줄어든다.
    그래서 **호출하는 쪽이 켤지 말지 정한다** - 이 함수는 스스로 켜지지 않는다.

    데모 모드에서는 할 일이 없다 (API 를 쓰지 않는다).
    스레드에서 부를 수 있도록 상태를 바꾸지 않는다.
    """
    if state.demo_mode or state.pair is None or state.done:
        return
    if len(state.history) + 1 >= state.total_rounds:
        return

    for winner in ("a", "b"):
        branch = replace(
            state,
            history=[*state.history, (state.pair.a.combo, state.pair.b.combo, winner)],
            pair=None,
        )
        domain, estimator, selector = _rebuild(branch)
        combo_a, combo_b = selector.next_pair(estimator)
        # 결과는 버린다. generator 의 파일 캐시에 들어가는 것이 목적이다.
        _generate_pair(branch, domain, combo_a, combo_b)


def optimize(
    state: SessionState,
    on_progress: Callable[[float], None] | None = None,
    *,
    task_model: str | None = None,
    reflection_model: str | None = None,
    metric_calls: int = GEPA_METRIC_CALLS,
) -> str:
    """추정된 선호로 GEPA 를 돌려 최종 프롬프트를 만든다.

    **진행률은 평가 함수 호출 수를 세서 낸다.** gepa 0.1.4 는 진행률
    콜백을 주지 않는다 - `display_progress_bar` 로 자기 진행 바를 그릴
    뿐이다. 그래서 `build_metric` 이 만든 함수를 세는 껍데기로 감싸고
    호출 수 / 예산을 진행률로 쓴다. `optimize/run_gepa.py` 를 고치지 않고
    거기의 `MetricEvaluator` 만 가져다 쓴다.

    수십 초가 걸린다. 호출하는 쪽에서 스레드로 돌려야 한다 - 이 함수는
    동기로 끝까지 기다린다.
    """
    from gepa import optimize as gepa_optimize
    from gepa.adapters.default_adapter.default_adapter import DefaultAdapter

    domain, estimator, _ = _rebuild(state)
    metric = build_metric(domain, estimator)
    seed_prompt = build_seed_prompt(domain, estimator)

    calls = {"n": 0}

    def counting_metric(output: str, source: str):
        result = metric(output, source)
        calls["n"] += 1
        if on_progress is not None:
            on_progress(min(1.0, calls["n"] / max(metric_calls, 1)))
        return result

    adapter = DefaultAdapter(
        model=task_model or state.model,
        evaluator=MetricEvaluator(counting_metric),
    )
    trainset = [{"input": state.source_text}]

    result = gepa_optimize(
        seed_candidate={"system_prompt": seed_prompt},
        trainset=trainset,
        valset=trainset,
        adapter=adapter,
        reflection_lm=reflection_model or state.model,
        max_metric_calls=metric_calls,
        display_progress_bar=False,
    )
    if on_progress is not None:
        on_progress(1.0)
    return result.best_candidate["system_prompt"]


def load_domain_for(domain_path: str) -> Domain:
    """UI 가 라벨·문구를 읽어야 할 때 쓰는 통로. 엔진을 직접 부르지 않게."""
    return load_domain(domain_path)

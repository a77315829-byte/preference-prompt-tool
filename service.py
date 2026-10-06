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

import os
import re
import uuid
from dataclasses import dataclass, field, replace
from typing import Callable

from engine.demo_generator import generate_demo
from engine.domain_loader import Domain, load_domain
from engine.estimator import Comparison, Estimator
import exporters
import template_library
from engine import generator
from engine.generator import build_compact_prompt, build_final_prompt, build_prompt, build_template_prompt, generate_all
from engine.metric_builder import build_metric
from engine.selector import UncertaintySelector
from optimize.run_gepa import MetricEvaluator

# 현재 제품의 비교 예산. 모의 실험의 수렴 양상을 참고했지만 모든 사용자가
# 8회 안에 복원되거나 추가 질문이 무의미하다는 뜻은 아니다.
TOTAL_ROUNDS = 8

# 선택기 시드. 고정해야 같은 이력이 같은 쌍을 낸다.
SELECTOR_SEED = 0

# GEPA 호출 예산. 진행률의 분모이기도 하다.
GEPA_METRIC_CALLS = 20

# GEPA 가 후보 프롬프트를 고쳐 쓰는 성찰 모델. 후보 생성은 싼 모델로 하고
# 성찰만 강한 모델에 맡긴다 (CLAUDE.md 스택 절). 호출 수가 적어 비용 영향이 작다.
REFLECTION_MODEL = os.environ.get("PPT_REFLECTION_MODEL", "openai/gpt-5.6-luna")


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
    # 템플릿 라이브러리에서 "내 방식으로 바꾸기"로 시작했으면 그 id. 결과는
    # 템플릿 본문 + 추정한 선호 절이 된다.
    template_id: str | None = None
    # 시작할 때 정한 최대 질문 수. 물을 게 없어 일찍 끝나면 total_rounds 가 줄어드는데,
    # "이전 선택 수정"으로 되돌릴 때 이 값으로 되돌린다.
    round_limit: int | None = None

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
    # 사람을 상대하므로 양 끝 값부터 묻고 같은 쌍을 반복하지 않는다. 합성
    # 사용자로 전 조합을 재면 복원율은 기본 동작과 같고(요약 90/90, 코딩
    # 80/80) 8회 중 반복 질문만 2.6~3.8회에서 0회가 된다. 실험 스크립트는
    # 기본 동작을 그대로 쓴다.
    selector = UncertaintySelector(
        domain, seed=SELECTOR_SEED, contrast_first=True, avoid_repeats=True
    )

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
                # 정하지 못한 축은 추정값이 없다 (정의상 첫 값을 추정이라 보여 주지 않는다).
                estimate=estimator.preferred_value(name) if estimator.has_signal(name) else None,
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
    template_id: str | None = None,
) -> SessionState:
    """세션을 열고 첫 쌍을 만든다."""
    if template_id is not None:
        template = template_library.get(template_id)
        if template.domain != domain_key:
            raise ValueError(f"템플릿 '{template_id}' 은 '{template.domain}' 용이다 (요청: {domain_key}).")
    state = SessionState(
        session_id=uuid.uuid4().hex[:12],
        domain_key=domain_key,
        domain_path=domain_path,
        source_text=source_text,
        model=model,
        demo_mode=demo_mode,
        total_rounds=total_rounds,
        template_id=template_id,
    )
    domain, estimator, selector = _rebuild(state)
    # 물을 수 있는 질문이 그보다 적으면 그만큼만 묻는다. 코딩(값 2개짜리 축
    # 3개)은 3번이면 선호가 다 정해지는데, 8번을 채우느라 같은 질문이 나왔다.
    state.total_rounds = min(total_rounds, selector.max_questions())
    state.round_limit = state.total_rounds
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
    if chosen not in ("a", "b", "tie"):
        raise ValueError(f"chosen 은 'a', 'b', 'tie'(비슷함) 중 하나여야 한다: {chosen!r}")
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

    pair = selector.next_pair(estimator)
    if pair is None:
        # 더 물을 질문이 없다 - 모든 축에서 1위가 도전자를 다 이겼다.
        # 진행 표시가 맞도록 총 라운드를 실제로 물은 수로 줄인다.
        updated.total_rounds = len(updated.history)
        updated.done = True
        return updated
    combo_a, combo_b = pair
    updated.pair = _generate_pair(updated, domain, combo_a, combo_b)
    return updated


def undo_choice(state: SessionState) -> SessionState:
    """마지막 선택을 지우고 그 질문으로 돌아간다.

    앱 선택기는 같은 질문을 다시 묻지 않아서, 잘못 누른 한 번이 그대로 굳는다 - 가상
    사용자 실험에서 클릭 10% 를 잘못 누르면 정확 복원이 100% 에서 66% 로 떨어졌다
    (experiments/estimator_ablation.py). 이력에서 하나를 빼고 재생하면 선택기의 난수까지
    그때 상태로 돌아가 같은 질문이 다시 나온다. 끝난 세션이면 다시 열고, 만든 프롬프트와
    최적화 결과는 버린다 (선호가 바뀌므로)."""
    if not state.history:
        raise ValueError("되돌릴 선택이 없습니다.")
    if state.optimize_status == "running":
        raise ValueError("최적화가 도는 중에는 선택을 되돌릴 수 없습니다.")
    updated = replace(
        state,
        history=state.history[:-1],
        pair=None,
        done=False,
        prompt=None,
        optimize_status="idle",
        optimize_progress=0.0,
        total_rounds=state.round_limit or state.total_rounds,
    )
    domain, estimator, selector = _rebuild(updated)
    updated.axes = _axis_views(updated, estimator)
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
        pair = selector.next_pair(estimator)
        if pair is None:
            continue
        combo_a, combo_b = pair
        # 결과는 버린다. generator 의 파일 캐시에 들어가는 것이 목적이다.
        _generate_pair(branch, domain, combo_a, combo_b)


def optimize(
    state: SessionState,
    on_progress: Callable[[float], None] | None = None,
    *,
    task_model: str | None = None,
    reflection_model: str | None = None,
    metric_calls: int = GEPA_METRIC_CALLS,
    report: dict | None = None,
    language: str | None = None,
) -> str:
    """추정된 선호로 GEPA 를 돌려 최종 프롬프트를 만든다.

    report 에 dict 를 넘기면 화면에 보여 줄 근거를 채운다: 시드와 고른
    프롬프트의 평가 점수(예시 입력 평균, 0~1), 평가에 쓴 입력 수, 원문
    내용이 들어가 버린 후보 수.

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
    check_optimizable(estimator)
    undecided = undecided_axes(estimator)
    # 정하지 못한 축은 채점하지 않는다 - 채점하면 최적화가 그 축의 첫 값을 밀어 넣는다.
    metric = build_metric(domain, estimator, skip_axes=set(undecided))
    # GEPA 는 사용자에게 보여 준 것과 같은 최종 프롬프트에서 출발한다.
    seed_prompt = final_prompt(domain, estimator, template_id=state.template_id, language=language)
    examples = [e for e in domain.example_sources if e != state.source_text.strip()]

    calls = {"n": 0}

    def counting_metric(output: str, source: str):
        result = metric(output, source)
        calls["n"] += 1
        if on_progress is not None:
            on_progress(min(1.0, calls["n"] / max(metric_calls, 1)))
        return result

    adapter = DefaultAdapter(
        # 문자열 모델 이름을 주면 GEPA 가 litellm 을 직접 불러 캐시를 거치지 않는다 (절대 규칙 2).
        model=cached_task_model(task_model or state.model),
        evaluator=MetricEvaluator(counting_metric),
    )
    # 원문 하나로 학습하고 같은 원문으로 평가하면, 성찰 모델이 그 원문의
    # 내용을 프롬프트에 박아 넣는다 ("SK hynix 관련 내용이라면 ..." 이 실제로
    # 제안됐다). 후보를 고르는 평가 세트는 도메인의 예시 입력으로 채운다.
    trainset = [{"input": state.source_text}] + [{"input": e} for e in examples]
    valset = [{"input": e} for e in examples] or trainset

    result = gepa_optimize(
        seed_candidate={"system_prompt": seed_prompt},
        trainset=trainset,
        valset=valset,
        adapter=adapter,
        reflection_lm=reflection_model or REFLECTION_MODEL,
        max_metric_calls=metric_calls,
        display_progress_bar=False,
    )
    if on_progress is not None:
        on_progress(1.0)
    prompt, score, skipped = _best_without_leak(result, seed_prompt, state.source_text, domain)
    if report is not None:
        report.update(
            seed_score=float(result.val_aggregate_scores[0]),
            final_score=float(score),
            eval_inputs=len(valset),
            leaky_skipped=skipped,
        )
    return prompt


def _best_without_leak(result, seed_prompt: str, source: str, domain: Domain) -> tuple[str, float, int]:
    """점수 순으로 보면서 사용자 원문의 내용이 새어 들어가지 않은 첫 후보.

    예시 입력으로 평가해도 원문 내용이 든 후보가 점수로 걸러진다는 보장은
    없다 - 평가 함수는 길이·겹침 같은 형식만 잰다. 그래서 따로 잰다.
    시드는 YAML 문구로만 조립되므로 항상 통과한다.
    """
    order = sorted(
        range(len(result.candidates)),
        key=lambda i: result.val_aggregate_scores[i],
        reverse=True,
    )
    reference = " ".join([seed_prompt, domain.task_description, *domain.example_sources])
    skipped = 0
    for i in order:
        prompt = result.candidates[i]["system_prompt"]
        if not source_leak(prompt, source, reference):
            return prompt, result.val_aggregate_scores[i], skipped
        skipped += 1
    return seed_prompt, result.val_aggregate_scores[0], skipped


_WORD = re.compile(r"\w+")
_SENTENCE_START = re.compile(r"(?:^|[.!?]\s+)(\w+)")


def source_leak(prompt: str, source: str, reference: str = "", ngram: int = 5) -> list[str]:
    """프롬프트에 들어간 원문 고유 내용. 비어 있으면 새지 않은 것이다.

    두 가지를 코드로 잰다 (절대 규칙 6).
    - 원문과 연속 `ngram` 단어가 같은 구절 - 문장을 옮겨 적은 경우.
    - 원문의 고유 표지 - 숫자가 든 두 자 이상 단어, 문장 첫머리가 아닌데
      대문자로 시작하는 단어와 대문자 약어(고유명사), 비ASCII 원문의 3자
      이상 단어. 성찰 모델은
      원문을 번역·요약해 넣기도 해서 구절 비교만으로는 못 잡는다.
      reference(시드 프롬프트·과제 설명·예시 입력)에 이미 있는 단어는
      이 도메인의 흔한 말이라 뺀다.
    """
    source_words = _WORD.findall(source)
    prompt_words = [w.lower() for w in _WORD.findall(prompt)]
    prompt_set = set(prompt_words)
    common = {w.lower() for w in _WORD.findall(reference)}
    starts = {m.group(1) for m in _SENTENCE_START.finditer(source)}

    marks = set()
    for word in source_words:
        lower = word.lower()
        if lower in common or lower not in prompt_set:
            continue
        # 한 자리 숫자는 "3~4문장" 같은 지침과 우연히 겹친다.
        has_digit = any(ch.isdigit() for ch in word) and len(word) >= 2
        # 문장 첫 단어는 대문자라도 고유명사로 보지 않되, 전부 대문자인
        # 약어(SK, EU)는 문장 첫머리여도 고유명사다.
        proper = (word[:1].isupper() and word not in starts) or (word.isupper() and len(word) >= 2)
        non_ascii = not word.isascii() and len(word) >= 3
        if has_digit or proper or non_ascii:
            marks.add(word)

    lowered = [w.lower() for w in source_words]
    grams = {tuple(lowered[i:i + ngram]) for i in range(len(lowered) - ngram + 1)}
    copied = {
        " ".join(prompt_words[i:i + ngram])
        for i in range(len(prompt_words) - ngram + 1)
        if tuple(prompt_words[i:i + ngram]) in grams
    }
    return sorted(marks | copied)


# 모델 호출 예외를 화면에 보여 줄 문구로 바꾼다. 클래스 이름만 본다 -
# litellm 을 import 하지 않아도 되고(11초), 메시지 원문을 쓰지 않는다.
# 순서가 중요하다: 하위 클래스를 먼저 둔다 (Timeout 은 APIConnectionError 의,
# ContextWindowExceededError 는 BadRequestError 의 하위 클래스다).
_API_ERROR_KINDS = (
    ("AuthenticationError", "인증 실패", "API 키가 없거나 틀렸습니다. .env 의 OPENAI_API_KEY 를 확인해 주세요."),
    ("RateLimitError", "호출 한도 초과", "호출 한도나 결제 크레딧이 소진됐습니다. 잠시 뒤 다시 시도하거나 결제 설정을 확인해 주세요."),
    ("BudgetExceededError", "예산 초과", "설정된 지출 상한에 닿았습니다."),
    ("APITimeoutError", "응답 시간 초과", "모델 응답이 제한 시간 안에 오지 않았습니다. 잠시 뒤 다시 시도해 주세요."),
    ("Timeout", "응답 시간 초과", "모델 응답이 제한 시간 안에 오지 않았습니다. 잠시 뒤 다시 시도해 주세요."),
    ("APIConnectionError", "연결 실패", "모델 서버에 연결하지 못했습니다. 네트워크를 확인해 주세요."),
    ("ContextWindowExceededError", "입력이 너무 김", "입력한 글이 모델이 한 번에 읽을 수 있는 길이를 넘었습니다. 글을 줄여 주세요."),
    ("ContentPolicyViolationError", "콘텐츠 정책", "모델 공급자의 콘텐츠 정책에 걸렸습니다. 다른 글로 시도해 주세요."),
    ("NotFoundError", "모델 없음", "설정된 모델 이름을 찾을 수 없습니다. 모델 설정을 확인해 주세요."),
    ("UnsupportedParamsError", "설정 오류", "이 모델이 지원하지 않는 요청 설정입니다. 모델 설정을 확인해 주세요."),
    ("BadRequestError", "요청 오류", "모델이 요청을 거부했습니다. 모델 설정을 확인해 주세요."),
    ("ServiceUnavailableError", "공급자 장애", "모델 공급자 서버에 문제가 있습니다. 잠시 뒤 다시 시도해 주세요."),
    ("InternalServerError", "공급자 장애", "모델 공급자 서버에 문제가 있습니다. 잠시 뒤 다시 시도해 주세요."),
)


def exports_for(state: SessionState, prompt: str, language: str | None = None) -> list[exporters.Export]:
    """끝난 세션의 프롬프트를 도메인이 정한 도구 형식들로 바꾼다.

    prompt 는 화면에 보여 준 그 프롬프트(최종 조립본 또는 GEPA 결과)다.
    글자 수 한도가 있는 곳에서 넘치면 선호 지시만 담은 짧은 판을 같이 준다.
    """
    domain, estimator = current_estimate(state)
    return exports_for_estimate(domain, estimator, prompt, language=language)


def exports_for_estimate(
    domain: Domain, estimator: Estimator, prompt: str, *, slug_suffix: str = "", language: str | None = None
) -> list[exporters.Export]:
    """세션 없이 추정만으로 내보내기를 만든다 (팀 프롬프트가 쓴다)."""
    combo = final_combo(domain, estimator)
    return exporters.build_exports(
        prompt,
        slug=domain.name + slug_suffix,
        # 파일 머리의 제목도 프롬프트와 같은 언어로 (영어 파일에 한국어 제목이 섞이지 않게).
        title=(f"선호 기반 프롬프트 ({domain.name}{slug_suffix})" if language in (None, "ko")
               else f"Preference-based prompt ({domain.name}{slug_suffix})"),
        targets=domain.export_targets or None,
        # 짧은 판도 화면에 보인 프롬프트와 같은 언어로.
        compact_prompt=build_compact_prompt(domain, combo, language=None if language in (None, "ko") else language),
    )


def current_estimate(state: SessionState) -> tuple[Domain, Estimator]:
    """화면이 추정 결과를 읽는 공개 통로. 이력을 재생해 도메인과 추정기를
    돌려준다. 호출하는 쪽이 _rebuild 에 기대지 않게 한다."""
    domain, estimator, _ = _rebuild(state)
    return domain, estimator


def describe_api_error(exc: BaseException) -> str:
    """화면에 보여도 되는 오류 설명.

    예외 메시지를 그대로 보여 주면 안 된다. OpenAI 인증 오류 문구는 키
    일부("Incorrect API key provided: sk-abc*****wxyz")를 담고 있고, 공개
    링크에서는 아무나 그 화면을 본다. 원인 파악에 필요한 종류와 예외 이름만
    남긴다 - 원문은 서버 로그에서 본다.
    """
    names = [cls.__name__ for cls in type(exc).__mro__]
    for name, title, advice in _API_ERROR_KINDS:
        if name in names:
            return f"{title}: {advice} (오류 종류: {type(exc).__name__})"
    return f"알 수 없는 오류로 모델 호출이 실패했습니다. (오류 종류: {type(exc).__name__})"


def prompt_languages(domain: Domain) -> list[str]:
    """이 도메인의 최종 프롬프트를 낼 수 있는 언어. 번역판이 있으면 그것이 먼저(화면 기본값)다.
    원본 문구의 언어 키는 "ko" 로 부른다 - 지금 도메인들의 원본이 한국어다."""
    return [*domain.final_prompt_translations, "ko"]


def final_prompt(
    domain: Domain, estimator: Estimator, template_id: str | None = None, team: bool = False,
    language: str | None = None,
) -> str:
    """사용자에게 건네는 최종 프롬프트. 추정한 선호를 도메인 YAML 의
    final_prompt 틀(역할·선호·지킬 것·출력 형식)에 넣어 조립한다.

    optimize/run_gepa.build_seed_prompt 는 그대로 둔다 - 실험(비교군 D,
    피드백 어블레이션)이 그 짧은 형태로 결과를 냈다.
    """
    combo = final_combo(domain, estimator)
    if template_id is not None:
        # 템플릿의 과제·규칙은 그대로 두고 선호 절만 붙인다.
        return build_template_prompt(domain, combo, template_library.get(template_id).prompt)
    # "ko" 는 원본 문구다 (prompt_languages 참고).
    return build_final_prompt(domain, combo, team=team, language=None if language in (None, "ko") else language)


def check_optimizable(estimator: Estimator) -> None:
    """최적화할 기준이 있는가. 없으면 ValueError. API 서버가 하루·세션 횟수를 차감하기 **전에**
    부른다 - 거부될 요청이 횟수만 깎지 않게."""
    if not any(estimator.has_signal(name) for name in estimator.enum_axis_names()):
        raise ValueError("정한 선호가 하나도 없어 최적화할 기준이 없습니다. 비교에서 한쪽을 골라 주세요.")


def cached_task_model(model: str, cache_dir=None):
    """GEPA 가 후보 지침을 평가할 때 부르는 모델 함수. 후보 생성과 같은 파일 캐시
    (engine.generator.generate_with_prompt)를 거치므로, 같은 (지침, 입력)은 다시 부르지 않는다.

    대가: 함수로 넘기면 GEPA 는 평가 묶음을 동시에가 아니라 하나씩 부른다 (문자열이면
    litellm 으로 10개씩 동시). 같은 평가를 두 번 사지 않는 쪽을 택했다.

    모델이 빈 응답을 내면 생성기는 캐시하지 않고 RuntimeError 를 낸다. 여기서는 빈 문자열로
    돌려준다 - 평가 함수가 빈 결과를 0점 처리하므로 그 후보만 떨어지고 최적화는 계속된다.
    인증 오류 같은 다른 실패는 그대로 올라간다."""
    target = cache_dir or generator.CACHE_DIR

    def call(messages) -> str:
        system = next((m["content"] for m in messages if m.get("role") == "system"), "")
        user = next((m["content"] for m in messages if m.get("role") == "user"), "")
        try:
            return generator.generate_with_prompt(system, user, model, cache_dir=target)
        except RuntimeError:
            return ""

    return call


def undecided_axes(estimator: Estimator) -> list[str]:
    """선호를 정하지 못한 enum 축 - 효용이 모두 같다 (비교가 없었거나 "비슷하다"만 골랐다).
    최종 프롬프트와 최적화 채점에서 뺀다. 그 축의 1위는 정의상 첫 값일 뿐이라, 넣으면
    사용자가 하지 않은 선택을 했다고 적게 된다."""
    return [name for name in estimator.enum_axis_names() if not estimator.has_signal(name)]


def final_combo(domain: Domain, estimator: Estimator) -> dict[str, str]:
    """최종 프롬프트용 축 값. 정하지 못한 enum 축과 자유 키워드 축은 빈 값(=넣지 않음)."""
    undecided = set(undecided_axes(estimator))
    combo = {name: ("" if name in undecided else estimator.preferred_value(name))
             for name in estimator.enum_axis_names()}
    combo.update({axis.name: "" for axis in domain.axes if axis.type != "enum"})
    return combo


def load_domain_for(domain_path: str) -> Domain:
    """UI 가 라벨·문구를 읽어야 할 때 쓰는 통로. 엔진을 직접 부르지 않게."""
    return load_domain(domain_path)

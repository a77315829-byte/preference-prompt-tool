"""선호하는 결과를 고르면 재사용 가능한 시스템 프롬프트를 만드는 UI."""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from engine.demo_generator import generate_demo
from engine.domain_loader import Domain, load_domain
from engine.estimator import Comparison, Estimator
from engine.generator import generate
from engine.selector import UncertaintySelector
from optimize.run_gepa import build_seed_prompt, run as run_gepa

load_dotenv()

# 배포(Streamlit Community Cloud)에는 .env 파일이 없다. 키는 st.secrets로
# 넣고, litellm이 읽는 os.environ으로 옮겨준다. 로컬에서는 위의 load_dotenv()가
# 이미 채워놨으므로 이 블록은 건너뛴다.
if not os.environ.get("OPENAI_API_KEY"):
    try:
        # secrets.toml이 아예 없는 환경(로컬에서 .env도 없는 경우)에서는
        # st.secrets 접근 자체가 예외를 던지므로 감싼다.
        secret_key = st.secrets.get("OPENAI_API_KEY", "")
    except Exception:  # noqa: BLE001 - secrets 미설정은 정상 흐름으로 처리
        secret_key = ""
    if secret_key:
        os.environ["OPENAI_API_KEY"] = secret_key

# gpt-4.1-mini 대비 입력 50%·출력 25% 저렴하고(0.20/1.20 vs 0.40/1.60 per M),
# 실제 코딩 프롬프트 생성에서 더 빨랐다(6.3s vs 11.4s, 각 1회 측정).
# experiments/ 쪽은 README에 보고된 수치가 4.1-mini로 측정된 것이라 안 바꾼다.
MODEL = "openai/gpt-5.6-luna"
N_ROUNDS = 8

API_MODE_LABEL = "AI 실시간 생성 (GPT-5.6 Luna)"
DEMO_MODE_LABEL = "무료 데모 (API 없이 규칙 기반)"

# 공개 배포에서 팀 API 키가 무제한으로 소진되지 않도록 API 모드만 세션당
# 상한을 건다 (CLAUDE.md 주의사항: "공개 배포 시 사용자가 자기 키를 넣게
# 하거나 호출 상한을 건다"). 데모 모드는 API를 안 쓰므로 제한하지 않는다.
MAX_API_RUNS_PER_SESSION = 3

# 원문 입력 길이 상한. API 모드에서는 이 원문이 한 세션에 16번(8회 x 후보 2개)
# 전송되므로, 상한이 없으면 긴 문서 하나로 토큰 비용이 급증한다. 공개 링크에
# 불특정 트래픽이 들어오는 상황을 가정한 방어선이다. 뉴스 기사 한 편은
# 보통 6,000자 이내라 실사용을 막지 않는 값으로 잡았다.
MAX_SOURCE_CHARS = 12000

DOMAIN_OPTIONS = {
    "coding": {
        "label": "코딩 도움",
        "path": "domains/coding.yaml",
        "intro": (
            "만들고 싶은 기능을 적고, 작성 방식이 다른 TypeScript/React 코드 중 "
            f"마음에 드는 쪽을 {N_ROUNDS}회 골라주세요."
        ),
        "input_label": "어떤 기능을 만들고 싶나요?",
        "placeholder": "예: 클릭 횟수를 보여주는 버튼 컴포넌트를 만들어 주세요.",
        "demo_info": "API 없이 스타일 차이가 분명한 TypeScript/React 예시로 전체 흐름을 시험합니다.",
        "compare_help": "기능보다 평소 받고 싶은 코드 작성 방식에 가까운 쪽을 골라주세요.",
    },
    "summarization": {
        "label": "문서 요약 (영어)",
        "path": "domains/summarization.yaml",
        "intro": (
            f"영어 원문을 붙여넣고, 두 요약 중 마음에 드는 쪽을 {N_ROUNDS}회 골라주세요. "
            "요약은 영어로 나옵니다."
        ),
        "input_label": "요약할 원문 (영어 뉴스 기사 권장)",
        "placeholder": "영어 원문을 붙여넣어 주세요.",
        "demo_info": "API 없이 규칙 기반 요약 예시로 전체 흐름을 시험합니다.",
        "compare_help": "내용보다 길이와 표현 방식이 마음에 드는 쪽을 골라주세요.",
    },
    # 한국어 요약은 영어와 축 구성(length/extractiveness/topic)이 같고
    # checks 모듈만 다르다 - 한국어는 조사 때문에 표면형 어휘 겹침이
    # 겹침을 과소평가하므로 checks/summarization_ko.py 를 쓴다.
    "summarization_ko": {
        "label": "문서 요약 (한국어)",
        "path": "domains/summarization_ko.yaml",
        "intro": (
            f"한국어 원문을 붙여넣고, 두 요약 중 마음에 드는 쪽을 {N_ROUNDS}회 골라주세요. "
            "요약은 한국어로 나옵니다."
        ),
        "input_label": "요약할 원문 (한국어 뉴스 기사 권장)",
        "placeholder": "한국어 원문을 붙여넣어 주세요.",
        "demo_info": "API 없이 규칙 기반 한국어 요약 예시로 전체 흐름을 시험합니다.",
        "compare_help": "내용보다 길이와 표현 방식이 마음에 드는 쪽을 골라주세요.",
    },
}

CODING_PREFERENCE_LABELS = {
    "code_structure": {"title": "코드 구성", "compact": "간결하게 작성", "separated": "역할별 파일로 분리"},
    "style_management": {"title": "디자인 수정 방식", "direct": "스타일 값을 바로 작성", "theme": "나중에 전체 디자인을 쉽게 수정"},
    "type_detail": {"title": "타입 작성", "inferred": "필요한 타입만 작성", "explicit": "타입을 꼼꼼하게 작성"},
}

# 영어·한국어 요약 도메인은 축 구성이 같으므로 라벨을 공유한다.
SUMMARIZATION_PREFERENCE_LABELS = {
    "length": {
        "title": "요약 길이",
        "short": "아주 짧게 (2문장 이내)",
        "normal": "보통 (3~4문장)",
        "long": "상세하게 (5문장 이상)",
    },
    "extractiveness": {
        "title": "표현 방식",
        "normal": "내 표현으로 바꿔 쓰기",
        "high": "원문 표현을 살리기",
        "fully": "원문 문장을 그대로 발췌",
    },
}

# 도메인별 선호 라벨. 없는 도메인은 원시 값을 그대로 보여준다.
PREFERENCE_LABELS = {
    "coding": CODING_PREFERENCE_LABELS,
    "summarization": SUMMARIZATION_PREFERENCE_LABELS,
    "summarization_ko": SUMMARIZATION_PREFERENCE_LABELS,
}


def _domain_for(key: str) -> Domain:
    return load_domain(DOMAIN_OPTIONS[key]["path"])


def _reset_session() -> None:
    for key in ("stage", "domain_key", "source", "demo_mode", "estimator", "selector", "round", "current_pair", "optimized_prompt", "api_error", "gepa_error"):
        st.session_state.pop(key, None)


def _show_candidate(domain_key: str, candidate: str) -> None:
    # 삼항 표현식으로 쓰면 안 된다. Streamlit의 magic이 스크립트의 표현식
    # 문장을 자동으로 st.write()로 감싸기 때문에, 삼항식이 반환한
    # DeltaGenerator 객체가 화면에 그대로 찍힌다(배포 후 실제로 발생).
    if domain_key == "coding":
        st.markdown(candidate)
    else:
        st.write(candidate)


def _show_api_error_notice() -> None:
    """API 호출이 실패해 데모 모드로 내려왔음을 숨기지 않고 알린다."""
    error = st.session_state.get("api_error")
    if not error:
        return
    st.warning(
        "AI 실시간 생성에 실패해서 **무료 데모 모드로 전환했습니다.** "
        "지금까지 고른 선택은 그대로 유지되고, 남은 비교는 규칙 기반 예시로 진행됩니다. "
        "API 키나 결제 크레딧을 확인한 뒤 처음부터 다시 시작하면 실시간 생성을 쓸 수 있습니다."
    )
    with st.expander("오류 내용 보기"):
        st.caption(error)


def _show_preferences(domain_key: str, preferred: dict[str, str]) -> None:
    """추정된 선호를 축별로 보여준다.

    축별 확신도를 같이 띄우려다 되돌렸다. estimator.confidence()는
    1 - 정규화 엔트로피인데, 완벽히 일관되게 골라 선호를 9/9 전부 복원한
    경우에도 3값 축에서는 0.06에 머물고 비교를 24회까지 늘려도 그대로다
    (2값인 coding 축은 8회 0.18 -> 24회 0.49로 오르기는 한다). 맞힌
    경우에 "확신도 6%"라고 적으면 사용자를 오히려 오인시킨다.
    "추정 결과와 같은 쪽을 고른 비율"도 대안이 못 된다 - 3값 축에서는
    선호값이 아닌 두 값끼리 붙는 비교가 섞여서, 일관된 사용자 52% vs
    무작위 55%로 구분이 안 됐다.
    confidence()는 metric_builder의 축 가중치처럼 축끼리 상대 비교하는
    원래 용도로는 그대로 쓴다. 사용자에게 보여줄 보정된 확신도는 별도
    작업이 필요하다.
    """
    domain_labels = PREFERENCE_LABELS.get(domain_key)
    if not domain_labels:
        st.json(preferred)
        return
    for axis_name, value in preferred.items():
        labels = domain_labels.get(axis_name)
        if not labels or value not in labels:
            # 라벨이 없는 축은 감추지 않고 원시 값이라도 보여준다.
            st.markdown(f"- **{axis_name}**: {value}")
            continue
        st.markdown(f"- **{labels['title']}**: {labels[value]}")

st.set_page_config(page_title="선호 기반 프롬프트 생성기", page_icon="✨")
st.title("선택으로 만드는 나만의 프롬프트")
st.caption("직접 복잡한 프롬프트를 쓰지 않아도, 더 마음에 드는 결과를 고르면 됩니다.")

if "stage" not in st.session_state:
    st.session_state.stage = "input"
if "api_runs_used" not in st.session_state:
    st.session_state.api_runs_used = 0

# 코드 업데이트 전에 시작한 브라우저 세션에는 실행 모드 값이 없다.
# 그 상태로 compare 단계를 이어가면 다시 API를 호출하므로 안전하게 시작 화면으로 돌린다.
if st.session_state.stage != "input" and (
    "demo_mode" not in st.session_state or "domain_key" not in st.session_state
):
    _reset_session()
    st.session_state.stage = "input"

if st.session_state.stage == "input":
    labels_to_keys = {config["label"]: key for key, config in DOMAIN_OPTIONS.items()}
    selected_label = st.selectbox("무엇을 도와드릴까요?", list(labels_to_keys))
    domain_key = labels_to_keys[selected_label]
    config = DOMAIN_OPTIONS[domain_key]

    st.write(config["intro"])
    run_mode = st.radio(
        "실행 모드",
        (API_MODE_LABEL, DEMO_MODE_LABEL),
        help=(
            "AI 실시간 생성은 실제로 모델을 호출해 후보를 만듭니다. "
            "무료 데모는 API 키나 비용 없이 규칙 기반 예시로 흐름만 보여줍니다."
        ),
    )
    demo_mode = run_mode == DEMO_MODE_LABEL
    if demo_mode:
        st.info(config["demo_info"])

    api_quota_left = MAX_API_RUNS_PER_SESSION - st.session_state.api_runs_used
    api_blocked = not demo_mode and api_quota_left <= 0
    if api_blocked:
        st.warning(
            f"API 모드는 세션당 {MAX_API_RUNS_PER_SESSION}회까지입니다. "
            "무료 데모 모드는 계속 쓰실 수 있습니다."
        )

    source = st.text_area(
        config["input_label"],
        height=180 if domain_key == "coding" else 250,
        placeholder=config["placeholder"],
        max_chars=MAX_SOURCE_CHARS,
    )
    if st.button("비교 시작", type="primary", disabled=not source.strip() or api_blocked):
        if not demo_mode:
            st.session_state.api_runs_used += 1
        domain = _domain_for(domain_key)
        st.session_state.domain_key = domain_key
        st.session_state.source = source
        st.session_state.demo_mode = demo_mode
        st.session_state.estimator = Estimator(domain)
        st.session_state.selector = UncertaintySelector(domain, seed=0)
        st.session_state.round = 0
        st.session_state.stage = "compare"
        st.rerun()

elif st.session_state.stage == "compare":
    domain_key = st.session_state.domain_key
    domain = _domain_for(domain_key)
    config = DOMAIN_OPTIONS[domain_key]
    estimator = st.session_state.estimator
    selector = st.session_state.selector
    source = st.session_state.source

    if "current_pair" not in st.session_state:
        combo_a, combo_b = selector.next_pair(estimator)
        if st.session_state.demo_mode:
            candidate_a = generate_demo(domain, source, combo_a)
            candidate_b = generate_demo(domain, source, combo_b)
        else:
            with st.spinner("두 가지 버전을 생성하는 중..."):
                try:
                    candidate_a = generate(domain, source, combo_a, model=MODEL)
                    candidate_b = generate(domain, source, combo_b, model=MODEL)
                except Exception as exc:
                    # 막다른 길로 끝내지 않는다. 예전에는 st.stop()으로 멈춰서
                    # 화면에 에러만 남고 여기까지 한 선택이 다 버려졌다 - 키가
                    # 만료되거나 결제 한도에 걸리면 처음 보는 사람 눈에는 그냥
                    # 고장난 서비스다. 데모 모드로 내려서 남은 비교를 규칙 기반
                    # 후보로 이어가고, 지금까지의 선택은 그대로 살린다.
                    st.session_state.demo_mode = True
                    st.session_state.api_error = str(exc)
                    st.rerun()
        st.session_state.current_pair = (combo_a, combo_b, candidate_a, candidate_b)

    combo_a, combo_b, candidate_a, candidate_b = st.session_state.current_pair

    _show_api_error_notice()

    st.progress(st.session_state.round / N_ROUNDS)
    st.caption(f"{st.session_state.round + 1} / {N_ROUNDS} 번째 비교 · {config['compare_help']}")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("A")
        _show_candidate(domain_key, candidate_a)
        pick_a = st.button("A가 더 마음에 들어요", use_container_width=True)
    with col_b:
        st.subheader("B")
        _show_candidate(domain_key, candidate_b)
        pick_b = st.button("B가 더 마음에 들어요", use_container_width=True)

    if pick_a or pick_b:
        winner = "a" if pick_a else "b"
        estimator.update(Comparison(combo_a, combo_b, winner))
        st.session_state.round += 1
        del st.session_state["current_pair"]
        if st.session_state.round >= N_ROUNDS:
            st.session_state.stage = "done"
        st.rerun()

elif st.session_state.stage == "done":
    domain_key = st.session_state.domain_key
    domain = _domain_for(domain_key)
    estimator = st.session_state.estimator
    source = st.session_state.source

    preferred = {name: estimator.preferred_value(name) for name in estimator.enum_axis_names()}
    st.success("선택이 모두 끝났습니다.")
    _show_api_error_notice()
    st.subheader("내가 선호하는 방식")
    _show_preferences(domain_key, preferred)

    seed_prompt = build_seed_prompt(domain, estimator)
    prompt = st.session_state.get("optimized_prompt", seed_prompt)
    st.subheader("재사용 가능한 시스템 프롬프트")
    st.code(prompt, language=None)
    st.caption("코드 블록 오른쪽 위의 복사 아이콘으로 프롬프트를 복사할 수 있습니다.")

    if st.session_state.demo_mode:
        st.caption("무료 데모 결과이며, 추정된 선호를 조립해 프롬프트를 만들었습니다.")
    elif "optimized_prompt" not in st.session_state:
        st.caption("현재는 선택 결과로 만든 기본 프롬프트입니다. 원하면 API로 한 번 더 최적화할 수 있습니다.")
        # 최적화가 실패해도 위에서 이미 보여준 기본 프롬프트는 쓸 수 있는
        # 결과물이다. 예전에는 st.stop()으로 멈춰서 "처음부터 다시" 버튼까지
        # 사라졌는데, 실패를 알리되 결과물과 조작 수단은 남겨둔다.
        gepa_error = st.session_state.get("gepa_error")
        if gepa_error:
            st.warning(
                "최적화 중 API 호출이 실패했습니다. 위의 기본 프롬프트는 그대로 사용할 수 있습니다. "
                "API 키와 결제 크레딧을 확인해 주세요."
            )
            with st.expander("오류 내용 보기"):
                st.caption(gepa_error)

        if st.button("GEPA로 프롬프트 최적화"):
            with st.spinner("프롬프트를 최적화하는 중... 1~2분 정도 걸립니다."):
                try:
                    optimized_prompt, _ = run_gepa(
                        domain,
                        estimator,
                        train_sources=[source],
                        val_sources=[source],
                        task_lm=MODEL,
                        reflection_lm=MODEL,
                        max_metric_calls=20,
                    )
                except Exception as exc:
                    st.session_state.gepa_error = str(exc)
                    st.rerun()
                st.session_state.pop("gepa_error", None)
            st.session_state.optimized_prompt = optimized_prompt
            st.rerun()
    else:
        st.caption("API 최적화가 적용된 프롬프트입니다.")

    if st.button("처음부터 다시"):
        _reset_session()
        st.rerun()

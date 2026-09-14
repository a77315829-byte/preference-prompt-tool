"""선호 기반 프롬프트 자동 생성 도구 - Streamlit UI (얇게, 11주차 마지막에 작성).

원문을 붙여넣고 두 요약 중 마음에 드는 쪽을 N회 고르면, 그 선택 이력에서
추정한 선호로 GEPA가 최적화한 개인 전용 시스템 프롬프트를 보여준다.
"""

import os

import streamlit as st
from dotenv import load_dotenv

from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator
from engine.generator import generate
from engine.selector import UncertaintySelector
from optimize.run_gepa import run as run_gepa

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

MODEL = "openai/gpt-4.1-mini"
N_ROUNDS = 8

# 공개 배포에서 팀 API 키가 무제한으로 소진되지 않도록 세션당 상한을 건다
# (CLAUDE.md 주의사항: "공개 배포 시 사용자가 자기 키를 넣게 하거나 호출 상한을 건다").
MAX_RUNS_PER_SESSION = 3

st.set_page_config(page_title="선호 기반 프롬프트 생성기")
st.title("선호 기반 프롬프트 자동 생성 도구")

if not os.environ.get("OPENAI_API_KEY"):
    st.error(
        "OPENAI_API_KEY가 설정되지 않았습니다. 로컬에서는 `.env`에, "
        "Streamlit Cloud에서는 Settings > Secrets에 넣어주세요."
    )
    st.stop()

domain = load_domain("domains/summarization.yaml")

if "stage" not in st.session_state:
    st.session_state.stage = "input"
if "runs_used" not in st.session_state:
    st.session_state.runs_used = 0

if st.session_state.stage == "input":
    st.write(
        f"원문을 붙여넣고, 두 요약 중 마음에 드는 쪽을 {N_ROUNDS}회 골라주세요. "
        "그러면 당신 전용 요약 프롬프트를 만들어 드립니다."
    )
    source = st.text_area("원문 (영어 뉴스 기사 권장)", height=250)

    quota_left = MAX_RUNS_PER_SESSION - st.session_state.runs_used
    if quota_left <= 0:
        st.warning(
            f"데모 체험은 세션당 {MAX_RUNS_PER_SESSION}회까지입니다. "
            "더 써보시려면 페이지를 새로고침해 주세요."
        )

    if st.button("시작", disabled=not source.strip() or quota_left <= 0):
        st.session_state.runs_used += 1
        st.session_state.source = source
        st.session_state.estimator = Estimator(domain)
        st.session_state.selector = UncertaintySelector(domain, seed=0)
        st.session_state.round = 0
        st.session_state.stage = "compare"
        st.rerun()

elif st.session_state.stage == "compare":
    estimator = st.session_state.estimator
    selector = st.session_state.selector
    source = st.session_state.source

    if "current_pair" not in st.session_state:
        combo_a, combo_b = selector.next_pair(estimator)
        with st.spinner("두 가지 버전을 생성하는 중..."):
            candidate_a = generate(domain, source, combo_a, model=MODEL)
            candidate_b = generate(domain, source, combo_b, model=MODEL)
        st.session_state.current_pair = (combo_a, combo_b, candidate_a, candidate_b)

    combo_a, combo_b, candidate_a, candidate_b = st.session_state.current_pair

    st.progress(st.session_state.round / N_ROUNDS)
    st.caption(f"{st.session_state.round + 1} / {N_ROUNDS} 번째 비교")

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("A")
        st.write(candidate_a)
        pick_a = st.button("A가 더 좋음", use_container_width=True)
    with col_b:
        st.subheader("B")
        st.write(candidate_b)
        pick_b = st.button("B가 더 좋음", use_container_width=True)

    if pick_a or pick_b:
        winner = "a" if pick_a else "b"
        estimator.update(Comparison(combo_a, combo_b, winner))
        st.session_state.round += 1
        del st.session_state["current_pair"]
        if st.session_state.round >= N_ROUNDS:
            st.session_state.stage = "done"
        st.rerun()

elif st.session_state.stage == "done":
    estimator = st.session_state.estimator
    source = st.session_state.source

    preferred = {name: estimator.preferred_value(name) for name in estimator.enum_axis_names()}
    st.subheader("추정된 선호")
    st.json(preferred)

    if "optimized_prompt" not in st.session_state:
        if st.button("최종 프롬프트 생성 (GEPA 최적화 실행)"):
            with st.spinner("GEPA로 프롬프트 최적화 중... 1~2분 정도 걸립니다."):
                optimized_prompt, _ = run_gepa(
                    domain,
                    estimator,
                    train_sources=[source],
                    val_sources=[source],
                    max_metric_calls=20,
                )
            st.session_state.optimized_prompt = optimized_prompt
            st.rerun()
    else:
        st.subheader("당신 전용 시스템 프롬프트")
        st.code(st.session_state.optimized_prompt, language=None)

    if st.button("처음부터 다시"):
        for key in ("stage", "source", "estimator", "selector", "round", "current_pair", "optimized_prompt"):
            st.session_state.pop(key, None)
        st.rerun()

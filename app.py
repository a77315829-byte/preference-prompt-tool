"""선호하는 결과를 고르면 재사용 가능한 시스템 프롬프트를 만드는 UI."""

from __future__ import annotations

import os
import time
import threading
from dataclasses import replace

import streamlit as st
from dotenv import load_dotenv

from budget import DailyBudget
from agents.expert_onboarding import corpus_stats
from expert_profile import (
    DELIMITER_HINT,
    MAX_MATERIAL_CHARS,
    RECOMMENDED_ANSWERS,
    build_anchor,
    compose_prompt,
    parse_answers,
    profile_rows,
    readiness,
)
from feedback import FeedbackLog
import service
import theme

from engine.demo_generator import generate_demo
from engine.domain_loader import Domain, load_domain
from engine.estimator import Comparison, Estimator
from engine.generator import generate_all, generate_all_with_prompts
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

# 세션당 상한은 브라우저 세션을 새로 열면 우회된다. 공개 링크에 불특정
# 트래픽이 들어오는 상황에서는 그것만으로는 팀 API 키를 못 지킨다.
# 그래서 앱 인스턴스 전체가 공유하는 하루 상한을 따로 둔다.
# 한 번 실행 = 8회 x 후보 2개 = 16번 호출이므로, 60회는 하루 약 960번
# 호출에 해당한다. 이 상한은 OpenAI 쪽 월 지출 상한을 대체하지 않는다 -
# 앱이 재시작되면 카운터도 초기화되기 때문이다. 두 겹으로 둔다.
MAX_API_RUNS_PER_DAY = 60

# 결과 화면에서 "기본 프롬프트 vs 내 프롬프트"를 새 원문에 적용해 비교하는
# 기능의 상한. 한 번에 2번 호출이라 비교 실행(16번)보다 훨씬 싸므로 예산을
# 따로 둔다. 같은 예산에 넣으면 2번 쓰고 16번어치를 차감하게 된다.
MAX_TRIALS_PER_DAY = 200
MAX_TRIALS_PER_SESSION = 3

# 실패한 시도도 비용이 발생할 수 있으므로 시작 전에 차감한다.
# 비교 세션을 다시 시작해도 이 카운터는 초기화하지 않는다.
MAX_OPTIMIZATIONS_PER_SESSION = 2
MAX_OPTIMIZATIONS_PER_DAY = 30

# 의견 입력 길이 상한. feedback.py 가 기록 시 한 번 더 자른다.
MAX_COMMENT_CHARS = 300

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
    # review/email 은 전용 데모 생성기가 없다. demos/generic.py 가 공통 축
    # (length·sentiment·formality·structure)을 실제로 구현해 데모 모드를
    # 처리한다 - 새 도메인을 YAML만 추가해 붙일 수 있다는 근거다.
    "review": {
        "label": "고객 리뷰 작성",
        "path": "domains/review.yaml",
        "intro": (
            f"방문 경험이나 사용 후기를 적으면, 리뷰 두 개 중 마음에 드는 쪽을 {N_ROUNDS}회 "
            "골라주세요. 리뷰는 영어로 나옵니다."
        ),
        "input_label": "리뷰로 만들 메모 (영어 권장)",
        "placeholder": "예: Visited the new ramen place near the station. Waited 40 minutes. Broth was rich but the room was loud.",
        "demo_info": "API 없이 규칙 기반 리뷰 예시로 전체 흐름을 시험합니다.",
        "compare_help": "내용보다 길이와 어조가 마음에 드는 쪽을 골라주세요.",
    },
    "email": {
        "label": "이메일 초안",
        "path": "domains/email.yaml",
        "intro": (
            f"보내려는 내용을 적으면, 작성 방식이 다른 이메일 두 개 중 마음에 드는 쪽을 "
            f"{N_ROUNDS}회 골라주세요. 이메일은 영어로 나옵니다."
        ),
        "input_label": "이메일로 만들 요청 사항 (영어 권장)",
        "placeholder": "예: Ask the vendor to confirm the Q4 delivery date and share the updated invoice.",
        "demo_info": "API 없이 규칙 기반 이메일 예시로 전체 흐름을 시험합니다.",
        "compare_help": "내용보다 길이·격식·구조가 마음에 드는 쪽을 골라주세요.",
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

REVIEW_PREFERENCE_LABELS = {
    "length": {
        "title": "리뷰 길이",
        "short": "아주 짧게 (2문장 이내)",
        "normal": "보통 (3~5문장)",
        "long": "상세하게 (6문장 이상)",
    },
    "sentiment": {
        "title": "어조",
        "negative": "비판적으로",
        "neutral": "담담하게",
        "positive": "긍정적으로",
    },
}

EMAIL_PREFERENCE_LABELS = {
    "length": {
        "title": "이메일 길이",
        "short": "아주 짧게 (2문장 이내)",
        "normal": "보통 (3~5문장)",
        "long": "상세하게 (6문장 이상)",
    },
    "formality": {
        "title": "격식",
        "casual": "편하고 친근한 어조",
        "formal": "격식 있는 비즈니스 어조",
    },
    "structure": {
        "title": "본문 구조",
        "prose": "문단 형태의 산문",
        "bullets": "글머리 기호 목록",
    },
}

# 도메인별 선호 라벨. 없는 도메인은 원시 값을 그대로 보여준다.
PREFERENCE_LABELS = {
    "coding": CODING_PREFERENCE_LABELS,
    "summarization": SUMMARIZATION_PREFERENCE_LABELS,
    "summarization_ko": SUMMARIZATION_PREFERENCE_LABELS,
    "review": REVIEW_PREFERENCE_LABELS,
    "email": EMAIL_PREFERENCE_LABELS,
}


@st.cache_resource
def _daily_api_budget() -> DailyBudget:
    """앱 인스턴스 전체가 공유하는 하루 API 실행 카운터.

    st.cache_resource 는 세션이 아니라 프로세스 단위로 같은 객체를 돌려주므로,
    서로 다른 방문자의 세션이 이 카운터를 공유한다. 계산 로직은 budget.py 에
    있고 Streamlit을 모른다 - 그래서 UI 없이 단위 테스트가 된다.
    """
    return DailyBudget(MAX_API_RUNS_PER_DAY)


@st.cache_resource
def _feedback_log() -> FeedbackLog:
    """앱 인스턴스 전체가 공유하는 응답 기록기.

    print 로 찍으면 Streamlit Cloud 콘솔 로그에 남는다. 저장소가 없어도
    표본을 모을 수 있고 새 의존성이 0개다 - 자세한 이유는 feedback.py.
    """
    return FeedbackLog()


@st.cache_resource
def _daily_trial_budget() -> DailyBudget:
    """프롬프트 체험(2회 호출)용 하루 상한. 실행 예산과 분리되어 있다."""
    return DailyBudget(MAX_TRIALS_PER_DAY)


@st.cache_resource
def _daily_optimization_budget() -> DailyBudget:
    return DailyBudget(MAX_OPTIMIZATIONS_PER_DAY)


def _domain_for(key: str) -> Domain:
    return load_domain(DOMAIN_OPTIONS[key]["path"])


def _reset_session() -> None:
    for key in ("stage", "domain_key", "source", "demo_mode", "estimator", "selector", "round", "current_pair", "optimized_prompt", "api_error", "gepa_error", "trial_source", "trial_result", "trial_error", "trials_used", "feedback_sent", "feedback_comment", "session", "gauge_prev", "optimize_changed"):
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


def _show_prompt_trial(domain: Domain, personal_prompt: str) -> None:
    """만든 프롬프트를 새 원문에 적용해 기본 프롬프트와 나란히 보여준다.

    왜 필요한가: 이 앱의 산출물은 프롬프트 문자열이라, 예전에는 사용자가
    그걸 복사해 다른 도구로 가야 개인화가 실제로 먹혔는지 알 수 있었다.
    가치를 확인하는 순간이 앱 밖에 있었던 셈이다.

    기준선은 도메인의 task_description 만 쓴 프롬프트다. 축 지시문이 전부
    빠진, 개인화되지 않은 상태다. 과제와 출력 언어는 남겨둔다 - 그것까지
    빼면 기준선이 엉뚱한 언어로 답할 수 있고, 그건 공정한 비교가 아니라
    이기기 쉬운 비교가 된다.
    """
    st.subheader("만든 프롬프트를 새 원문에 적용해보기")

    if st.session_state.demo_mode:
        st.caption(
            "무료 데모 모드에서는 이 비교를 쓸 수 없습니다. 실제로 모델을 호출해야 하므로 "
            "처음부터 다시 시작해 AI 실시간 생성을 고르면 확인할 수 있습니다."
        )
        return

    used = st.session_state.get("trials_used", 0)
    session_left = MAX_TRIALS_PER_SESSION - used
    if session_left <= 0:
        st.caption(f"이 비교는 세션당 {MAX_TRIALS_PER_SESSION}회까지 쓸 수 있습니다.")
        return
    if _daily_trial_budget().left() <= 0:
        st.caption("오늘 배정된 비교 횟수를 모두 썼습니다. 내일 다시 열립니다.")
        return

    st.caption(
        "개인화하지 않은 기본 프롬프트와 방금 만든 프롬프트를 같은 원문에 적용해 "
        f"나란히 보여드립니다. 남은 횟수 {session_left}회."
    )

    trial_source = st.text_area(
        "새 원문",
        height=120,
        placeholder="위에서 쓴 것과 다른 원문을 넣어보세요.",
        max_chars=MAX_SOURCE_CHARS,
        key="trial_source",
    )

    if st.button("두 프롬프트로 생성해 비교", disabled=not trial_source.strip()):
        if not _daily_trial_budget().consume():
            st.warning("방금 오늘 배정된 비교 횟수가 소진됐습니다.")
        else:
            st.session_state.trials_used = used + 1
            with st.spinner("두 프롬프트로 생성하는 중..."):
                try:
                    baseline, personal = generate_all_with_prompts(
                        (domain.task_description, personal_prompt),
                        trial_source,
                        model=MODEL,
                    )
                except Exception as exc:  # noqa: BLE001 - 사용자에게 그대로 알린다
                    st.session_state.trial_error = str(exc)
                else:
                    st.session_state.pop("trial_error", None)
                    st.session_state.trial_result = (baseline, personal)
            st.rerun()

    trial_error = st.session_state.get("trial_error")
    if trial_error:
        st.warning("생성 중 API 호출이 실패했습니다. API 키와 결제 크레딧을 확인해 주세요.")
        with st.expander("오류 내용 보기"):
            st.caption(trial_error)

    result = st.session_state.get("trial_result")
    if not result:
        return

    baseline, personal = result
    col_base, col_personal = st.columns(2)
    with col_base:
        with st.container(border=True):
            st.markdown('<div class="ppt-ab ppt-ab-base">기본</div>', unsafe_allow_html=True)
            st.caption("개인화 없음")
            st.write(baseline)
    with col_personal:
        with st.container(border=True):
            st.markdown('<div class="ppt-ab">내 프롬프트</div>', unsafe_allow_html=True)
            st.caption("8회 선택으로 만든 프롬프트")
            st.write(personal)


def _show_feedback_form(domain_key: str, preferred: dict[str, str]) -> None:
    """이 결과가 취향에 맞았는지 한 줄로 묻는다.

    지금까지의 정량 결과는 전부 MACSum 페르소나 기반이라 "실제 사람도
    좋아했다"는 근거가 없었다. 공개 링크에 들어오는 방문자가 그 표본이 된다.

    원문과 생성 결과는 기록하지 않는다 - 자세한 이유는 feedback.py.
    """
    if st.session_state.get("feedback_sent"):
        st.success("의견 감사합니다. 개인화 품질을 판단하는 근거로 씁니다.")
        return

    st.subheader("이 프롬프트가 내 취향에 맞나요?")
    st.caption(
        "한 번만 답해주시면 개인화가 실제로 통하는지 판단하는 데 쓰겠습니다. "
        "피드백 로그에는 원문·생성 결과를 넣지 않고 아래 응답을 기록합니다. "
        "AI 생성 결과는 재사용을 위해 서버 캐시에 저장됩니다."
    )

    comment = st.text_input(
        "덧붙일 말 (선택)",
        placeholder="예: 길이는 맞는데 표현이 너무 딱딱해요",
        max_chars=MAX_COMMENT_CHARS,
        key="feedback_comment",
    )

    col_yes, col_no = st.columns(2)
    answered = None
    with col_yes:
        if st.button("네, 맞아요", use_container_width=True):
            answered = True
    with col_no:
        if st.button("아니요, 아쉬워요", use_container_width=True):
            answered = False

    if answered is None:
        return

    _feedback_log().record(
        domain=domain_key,
        demo_mode=bool(st.session_state.demo_mode),
        fits=answered,
        preferred=preferred,
        comment=comment,
        rounds=N_ROUNDS,
    )
    st.session_state.feedback_sent = True
    st.rerun()


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

STYLES = """
<style>
/* 다크 테크 톤. 색은 .streamlit/config.toml 의 테마와 맞춘다.
   여기 값을 바꾸면 그쪽도 같이 봐야 한다. */
:root {
    --ppt-bg: var(--bg);
    --ppt-panel: var(--surface);
    --ppt-line: rgba(124, 108, 255, 0.22);
    --ppt-line-soft: rgba(231, 233, 242, 0.10);
    --ppt-violet: var(--accent);
    --ppt-cyan: var(--axis-2);
    --ppt-text: var(--text-primary);
    --ppt-muted: rgba(231, 233, 242, 0.58);
    --ppt-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
}

/* 본문 폭을 좁혀 읽기 편하게. 기본값은 와이드해서 텍스트가 늘어진다. */
[data-testid="stMainBlockContainer"] {
    max-width: 880px;
    padding-top: 2.2rem;
    padding-bottom: 5.5rem;
}

/* 배경에 아주 약한 발광을 깔아 평평한 검정을 피한다. */
[data-testid="stAppViewContainer"] {
    background: var(--surface);
}

/* --- 히어로 --- */
.ppt-hero {
    position: relative;
    border: 1px solid var(--ppt-line);
    border-radius: 16px;
    padding: 1.7rem 1.8rem 1.6rem;
    margin-bottom: 1.1rem;
    background: var(--surface);
    overflow: hidden;
}
/* 상단에 얇은 네온 라인 */
.ppt-hero::before {
    content: "";
    position: absolute;
    inset: 0 0 auto 0;
    height: 1px;
    background: var(--accent);
}
.ppt-eyebrow {
    font-family: var(--ppt-mono);
    font-size: .72rem;
    letter-spacing: .14em;
    text-transform: uppercase;
    color: var(--ppt-cyan);
    margin-bottom: .8rem;
}
.ppt-hero h1 {
    font-size: 1.95rem;
    line-height: 1.3;
    font-weight: 800;
    letter-spacing: -.015em;
    margin: 0 0 .7rem;
    color: var(--ppt-text);
}
.ppt-rule {
    width: 46px;
    height: 2px;
    border-radius: 2px;
    background: var(--accent);
    margin: 0 0 .85rem;
}
.ppt-hero p {
    margin: 0;
    font-size: .95rem;
    line-height: 1.65;
    color: var(--ppt-muted);
}

/* --- 3단계 --- */
.ppt-steps {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: .6rem;
    margin-bottom: 1.7rem;
}
.ppt-step {
    border: 1px solid var(--ppt-line-soft);
    border-radius: 12px;
    padding: .8rem .9rem;
    background: rgba(255, 255, 255, 0.02);
}
.ppt-step-n {
    font-family: var(--ppt-mono);
    font-size: .68rem;
    letter-spacing: .1em;
    color: var(--ppt-violet);
    margin-bottom: .4rem;
}
.ppt-step-t {
    font-weight: 700;
    font-size: .87rem;
    margin-bottom: .22rem;
    color: var(--ppt-text);
}
.ppt-step-d {
    font-size: .76rem;
    line-height: 1.5;
    color: var(--ppt-muted);
}

/* --- 위젯 --- */
.stTextArea textarea, .stTextInput input {
    border-radius: 10px !important;
    font-size: .92rem !important;
    border: 1px solid var(--ppt-line-soft) !important;
}
.stTextArea textarea:focus, .stTextInput input:focus {
    border-color: var(--ppt-violet) !important;
}
[data-testid="stBaseButton-primary"] {
    border-radius: 10px;
    font-weight: 700;
    padding: .55rem 1.5rem;
    border: none;
    background: var(--accent);
    box-shadow: none;
}
/* 비활성 상태에서도 발광이 남으면 누를 수 있는 것처럼 보인다. */
[data-testid="stBaseButton-primary"]:disabled,
[data-testid="stBaseButton-primary"][disabled] {
    background: rgba(124, 108, 255, 0.16);
    box-shadow: none;
    color: rgba(231, 233, 242, 0.42);
}
[data-testid="stBaseButton-secondary"] {
    border-radius: 10px;
    font-weight: 600;
    border: 1px solid var(--ppt-line-soft);
}
[data-testid="stBaseButton-secondary"]:hover {
    border-color: var(--ppt-violet);
}

/* --- 카드 (A/B 후보, 프롬프트 비교) --- */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 14px;
}

/* --- 라벨 칩 --- */
.ppt-ab {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1.7rem;
    height: 1.7rem;
    padding: 0 .55rem;
    border-radius: 8px;
    font-family: var(--ppt-mono);
    font-weight: 700;
    font-size: .82rem;
    letter-spacing: .04em;
    margin-bottom: .5rem;
    color: var(--bg);
    background: var(--ppt-violet);
}
.ppt-ab-b { background: var(--ppt-cyan); }
.ppt-ab-base {
    background: transparent;
    color: var(--ppt-muted);
    border: 1px solid var(--ppt-line-soft);
}

/* 진행 막대를 조금 두껍게 */
[data-testid="stProgress"] div[role="progressbar"] > div { height: .4rem; }
</style>
"""

STEPS = (
    ("1", "주제 선택 &amp; 입력", "요약할 원문이나 만들고 싶은 기능을 적습니다."),
    ("2", f"A/B 비교 {N_ROUNDS}회", "어느 축이 다른지는 알려주지 않습니다. 마음에 드는 쪽만 고르세요."),
    ("3", "프롬프트 완성", "추정된 취향을 반영한 시스템 프롬프트를 복사해 갑니다."),
)


# 전문가 프롬프트 쪽에 붙이는 과제 서술. 사용자가 무슨 일을 하는지는
# 우리가 모르므로 분야를 지정하지 않고, 형식 앵커만 그 위에 얹는다.
#
# **예시를 가리키면 안 된다.** 처음에 "the way the examples below were
# written" 으로 썼는데, 이 경로는 사용자의 글을 프롬프트에 넣지 않으므로
# 가리킬 예시가 없다. 모델에게 존재하지 않는 것을 따르라고 하는 셈이었다.
#
# 검증 실험의 문구는 "Answer the following question from an online
# question-and-answer site" 였다. 여기서는 사용자의 과제가 Q&A 라고
# 가정할 수 없어 중립적으로 바꿨다 - 비교 실험에서 이 문장은 base 와
# stable 양쪽에 똑같이 들어갔으므로, 측정된 이득은 앵커의 몫이고
# 이 문구를 바꿔도 그 귀속은 유지된다.
EXPERT_TASK_DESCRIPTION = (
    "Answer the request below. Write the answer only, with no preamble."
)


EXPERT_STEPS = (
    ("1", "내가 쓴 글 붙여넣기", f"답변 사이를 `{DELIMITER_HINT}` 로 구분합니다. "
     f"{RECOMMENDED_ANSWERS}개를 권장합니다. 정확도를 보장하는 기준은 아닙니다."),
    ("2", "형식 측정", "길이·문장·문단·글머리 기호를 코드로 잽니다. 모델 호출이 없습니다."),
    ("3", "프롬프트 복사", "과제에 따라 바뀌지 않으니 그대로 붙여 쓰면 됩니다."),
)


def _show_expert_steps() -> None:
    """전문가 경로의 단계 안내.

    비교 경로에는 `_show_steps()` 가 있는데 이 경로에는 없어서, 붙여넣기
    전에 무엇을 하는 화면인지 알 수 없었다. 같은 마크업을 쓴다.
    """
    cards = "".join(
        f'<div class="ppt-step"><div class="ppt-step-n">0{n} /</div>'
        f'<div class="ppt-step-t">{title}</div>'
        f'<div class="ppt-step-d">{desc}</div></div>'
        for n, title, desc in EXPERT_STEPS
    )
    st.markdown(f'<div class="ppt-steps">{cards}</div>', unsafe_allow_html=True)


def _show_expert_feedback_form(answer_count: int, examples: list) -> None:
    """전문가 경로의 만족도를 묻는다.

    비교 경로와 **따로 집계한다**(mode="expert"). 두 기능은 하는 일이
    달라서 만족도를 한 숫자로 합치면 아무 것도 말하지 못한다.

    같이 남기는 숫자는 답변 개수와 잰 형식 수치다. 자료가 적은 사용자가
    덜 만족하는지 보려면 그게 있어야 한다 - 실측에서 12개와 30개의 차이가
    컸으므로(한 저자는 −0.122 에서 +0.187 로 뒤집혔다) 실사용에서도 그
    경계가 보이는지 확인할 값이다. `feedback.py` 가 숫자만 받으므로
    원문이 이 경로로 새지 않는다.
    """
    if st.session_state.get("expert_feedback_sent"):
        st.success("의견 감사합니다. 이 기능이 실제로 통하는지 판단하는 근거로 씁니다.")
        return

    st.subheader("이 프롬프트가 내 글쓰기 방식에 맞나요?")
    st.caption(
        "한 번만 답해주시면 판단 근거로 쓰겠습니다. 붙여넣은 글은 저장하지 않고, "
        "답변 개수와 측정된 수치만 익명으로 남깁니다."
    )

    comment = st.text_input(
        "덧붙일 말 (선택)",
        placeholder="예: 길이는 맞는데 문단이 너무 잘게 나뉘어요",
        max_chars=MAX_COMMENT_CHARS,
        key="expert_feedback_comment",
    )

    col_yes, col_no = st.columns(2)
    answered = None
    with col_yes:
        if st.button("네, 맞아요", use_container_width=True, key="expert_fits_yes"):
            answered = True
    with col_no:
        if st.button("아니요, 아쉬워요", use_container_width=True, key="expert_fits_no"):
            answered = False

    if answered is None:
        return

    stats = corpus_stats(examples)
    _feedback_log().record(
        domain="expert",
        mode="expert",
        fits=answered,
        comment=comment,
        extra={
            "answers": answer_count,
            "words_per_answer": stats.get("words_per_answer", 0.0),
            "sentences_per_answer": stats.get("sentences_per_answer", 0.0),
            "paragraphs_per_answer": stats.get("paragraphs_per_answer", 0.0),
        },
    )
    st.session_state.expert_feedback_sent = True
    st.rerun()


def _show_expert_flow() -> None:
    """자기 글을 붙여넣으면 그 사람 형식으로 쓰게 하는 프롬프트를 만든다.

    **API 를 한 번도 호출하지 않는다.** 실측에서 이 방법의 효과는 전부
    코드로 잰 수치 앵커에서 나왔다 - 저자 8명 x 홀드아웃 30개에서 형식
    거리 0.308 -> 0.146 (8/8 개선, p=0.008). 사용자의 실제 글을 예시로
    프롬프트에 넣어도 0.149 로 차이가 없었다(페어드 p=0.727). 그러니
    이 경로는 모델 API를 호출하지 않는다. 입력은 Streamlit 서버로
    전송되어 처리된다. 브라우저 안에서만 계산하는 기능은 아니다.

    비교 루프(기존 흐름)와 완전히 분리해서 넣는다. 저 쪽은 선호를
    추정하고 이 쪽은 이미 있는 자료를 측정한다 - 출발점이 다르다.
    """
    st.subheader("형식을 재서 프롬프트로")
    st.caption(
        "지금까지 쓴 답변·문서를 붙여넣으면 형식을 코드로 재서, 그 형식으로 쓰게 하는 "
        f"프롬프트를 만들어 드립니다. **모델을 호출하지 않습니다** - 붙여넣은 글은 "
        "Streamlit 서버로 전송되어 처리되며, 이 기능에서는 모델 API로 보내지 않습니다."
    )
    st.caption(
        "현재 검증 범위는 영어 Q&A 답변의 길이·문장 형식입니다. 한국어 효과나 "
        "전문 지식의 재현은 검증하지 않았습니다. 질문 원문을 받지 않으므로 "
        "원문 길이에 따른 적정 요약 분량은 추정할 수 없습니다."
    )
    _show_expert_steps()

    # max_chars 를 주지 않는다. Streamlit 이 그 카운터를 입력창 오른쪽
    # 아래에 겹쳐 그려서, 붙여넣은 글의 마지막 줄과 포개진다(스크린샷에서
    # 확인). 상한은 parse_answers 가 코드로 자르고, 넘었을 때만 아래에서
    # 따로 알린다.
    material = st.text_area(
        f"내가 쓴 글 (답변 사이를 하이픈 세 개 `{DELIMITER_HINT}` 만 있는 줄로 구분)",
        height=260,
        placeholder=(
            "첫 번째 답변 전문을 여기에 붙여넣습니다.\n"
            "여러 문단이어도 그대로 두세요 - 문단 수도 재는 항목입니다.\n"
            f"\n{DELIMITER_HINT}\n\n"
            "두 번째 답변...\n"
        ),
        help=(
            f"{RECOMMENDED_ANSWERS}개를 권장하지만 정확도를 보장하지 않습니다. 실측에서 12개만 넣었을 때 "
            "평균 길이를 40% 넘게 잘못 잡은 경우가 있었습니다."
        ),
    )

    examples = parse_answers(material)
    level, message = readiness(len(examples))
    if not material.strip():
        return
    if len(material) > MAX_MATERIAL_CHARS:
        st.caption(
            f"{len(material):,}자를 받았고 앞 {MAX_MATERIAL_CHARS:,}자까지만 계산에 씁니다."
        )
    if level == "none":
        st.info(message)
        return
    (st.warning if level == "thin" else st.success)(message)

    st.markdown("**코드로 잰 내 형식**")
    rows = profile_rows(examples)
    # 세 칸씩 끊는다. Streamlit 1.63 의 st.columns 는 좁은 화면에서
    # 자동으로 쌓이지 않고 줄어들기만 해서, 다섯 칸을 한 줄에 놓으면
    # 휴대폰에서 라벨이 뭉깬다.
    per_row = 3
    for start in range(0, len(rows), per_row):
        chunk = rows[start : start + per_row]
        for column, (label, value) in zip(st.columns(per_row), chunk):
            column.metric(label, value)

    anchor, kind, per_task = build_anchor(examples)
    if not anchor:
        st.warning("형식을 재지 못했습니다. 답변이 충분히 긴지 확인해 주세요.")
        return

    prompt = compose_prompt(EXPERT_TASK_DESCRIPTION, anchor)
    st.markdown("**만들어진 프롬프트**")
    st.code(prompt, language="text")

    if per_task:
        # 압축률이 뽑힌 경우. 목표가 과제 길이에 비례하므로 이 문구를
        # 그대로 다른 과제에 쓰면 틀린다. 모델이 백분율 규칙을 스스로
        # 적용하지 못한다는 것도 실측했다(길이 오차 3단어 -> 27~57단어).
        st.warning(
            "넣어주신 자료는 **원문을 받아 그 길이에 비례해 쓰는 종류**(요약 등)로 "
            "측정됐습니다. 그런 경우 목표 분량이 과제마다 달라지므로 위 프롬프트를 "
            "다른 과제에 그대로 쓰면 어긋납니다. 이 화면은 아직 고정된 문구만 "
            "만들어 드립니다."
        )
    else:
        st.caption(
            "입력한 글의 평균 분량으로 만든 고정 지침입니다. 새 과제에도 이 분량이 적합한지는 결과를 보고 확인해 주세요."
        )

    with st.expander("문단 수도 지시에 넣을까요?"):
        st.caption(
            "실측 결과를 그대로 알려드립니다. 문단 수를 같이 지시하면 문단은 잘 맞지만"
            "(평균 오차 1.90 → 0.88) 길이와 문장 수가 나빠집니다(형식 거리 0.158 → "
            "0.256). 위 프롬프트는 길이·문장만 지시하는, 저자 8명에게 검증된 조건입니다."
        )
        paragraphs = next(
            (value for label, value in rows if label == "답변당 문단"), None
        )
        if paragraphs:
            st.code(
                f"{prompt}\nAlso break it into about {paragraphs.rstrip('문단')} paragraphs.",
                language="text",
            )

    _show_expert_feedback_form(len(examples), examples)

    with st.expander("이 수치는 어떻게 검증했나요?"):
        st.caption(
            "Stack Exchange 네 분야(요리·글쓰기·수리·학계)의 저자 8명이 공개한 "
            "답변을 각 30개씩 측정해 프롬프트를 만든 뒤, **프롬프트 구성에 넣지 않은 "
            "질문 30개**에 적용해 그 사람의 실제 답변과 형식을 비교했습니다. "
            "형식 거리가 0.308에서 0.146으로 줄고 8명 전원에서 개선됐습니다 "
            "(탐색적 부호검정 p=0.008). 실제 저자가 참여한 만족도 실험은 아닙니다. "
            "이 결과만으로 내용 품질이나 전문 지식의 재현을 주장할 수 없습니다."
        )


def _rebuilt_estimator(session):
    """시드 프롬프트를 만들려면 Estimator 객체가 필요하다.

    `service.SessionState` 는 엔진 객체를 담지 않으므로(직렬화 가능해야
    한다) 여기서 이력을 재생해 꺼낸다. 재생 비용은 8라운드짜리다.
    """
    _, estimator, _ = service._rebuild(session)
    return estimator


def _run_optimize(session, seed_prompt: str) -> None:
    """GEPA 를 스레드로 돌리고 진행 바로 폴링한다.

    **스피너를 쓰지 않는다.** 게이지와 같은 시각 언어(가느다란 바)로
    보여주는 게 이 화면의 톤이고, 무엇보다 실제 진행률을 낼 수 있다 -
    `service.optimize` 가 평가 함수 호출 수를 세서 예산으로 나눈다.
    gepa 0.1.4 는 진행률 콜백을 주지 않으므로 그렇게 얻는다.

    스레드에서 `st.*` 를 부르지 않는다. 진행률은 공유 dict 에만 쓰고,
    화면은 여기서 폴링하며 그린다.
    """
    used = st.session_state.get("optimizations_used", 0)
    if used >= MAX_OPTIMIZATIONS_PER_SESSION:
        st.warning("이 브라우저 세션의 최적화 시도 횟수를 모두 썼습니다. 기본 프롬프트는 사용할 수 있습니다.")
        return
    if not _daily_optimization_budget().consume():
        st.warning("오늘 배정된 최적화 시도 횟수를 모두 썼습니다. 기본 프롬프트는 사용할 수 있습니다.")
        return
    st.session_state.optimizations_used = used + 1
    shared: dict = {"progress": 0.0, "prompt": None, "error": None}

    def work() -> None:
        try:
            shared["prompt"] = service.optimize(
                session, on_progress=lambda value: shared.__setitem__("progress", value)
            )
        except Exception as exc:  # noqa: BLE001 - 실패해도 기본 프롬프트는 쓸 수 있다
            shared["error"] = str(exc)

    worker = threading.Thread(target=work, daemon=True)
    worker.start()

    slot = st.empty()
    while worker.is_alive():
        with slot.container():
            st.markdown(
                theme.progress_html(
                    shared["progress"],
                    f"최적화 중 · 평가 {shared['progress'] * 100:.0f}%",
                ),
                unsafe_allow_html=True,
            )
        time.sleep(1)
    slot.empty()

    if shared["error"]:
        st.session_state.gepa_error = shared["error"]
    else:
        st.session_state.pop("gepa_error", None)
        st.session_state.optimized_prompt = shared["prompt"]
        # **바뀌지 않는 경우가 정상적으로 일어난다.** 시드는 추정된 선호로
        # 조립되고 평가 함수는 그 같은 선호를 검사하므로, 시드가 처음부터
        # 만점을 받아 GEPA 가 변이를 건너뛴다 (로그: "All subsample scores
        # perfect for parent 0. Skipping."). 피드백 풍부도 어블레이션 1차
        # 시도에서 이미 겪은 것과 같은 구조다.
        #
        # 그때 "최적화했습니다"라고 말하면 거짓이다. 같은지 여부를 기록해
        # 화면이 사실을 말하게 한다.
        st.session_state.optimize_changed = (
            shared["prompt"].strip() != seed_prompt.strip()
        )
    st.rerun()


def _inject_styles() -> None:
    """옛 스타일(히어로·단계 카드) 다음에 토큰·컴포넌트를 얹는다.

    순서가 중요하다. theme.base_css() 가 뒤에 와야 토큰 기반 규칙이
    이기고, Streamlit 기본 UI 제거도 거기 들어 있다.
    """
    st.markdown(STYLES, unsafe_allow_html=True)
    st.markdown(theme.base_css(), unsafe_allow_html=True)


def _show_hero() -> None:
    st.markdown(
        f"""
        <div class="ppt-hero">
          <div class="ppt-eyebrow">Preference Engine &middot; {N_ROUNDS}-shot</div>
          <h1>선택으로 만드는 나만의 프롬프트</h1>
          <div class="ppt-rule"></div>
          <p>복잡한 프롬프트를 직접 쓰지 않아도 됩니다. 더 마음에 드는 결과를
          고르면, 그 선택에서 취향을 추정해 재사용 가능한 시스템 프롬프트를 만들어 드립니다.
          이미 써둔 글이 있다면 그걸 넘겨 형식을 재는 방법도 있습니다.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _show_steps() -> None:
    cards = "".join(
        f'<div class="ppt-step"><div class="ppt-step-n">0{n} /</div>'
        f'<div class="ppt-step-t">{title}</div>'
        f'<div class="ppt-step-d">{desc}</div></div>'
        for n, title, desc in STEPS
    )
    st.markdown(f'<div class="ppt-steps">{cards}</div>', unsafe_allow_html=True)


st.set_page_config(page_title="선호 기반 프롬프트 생성기", page_icon="✨")
_inject_styles()
_show_hero()

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

COMPARE_PATH_LABEL = "비교해서 만들기 (자료가 없어도 됩니다)"
EXPERT_PATH_LABEL = "내가 쓴 글에서 만들기 (자료 필요)"

if st.session_state.stage == "input":
    # 두 경로는 출발점이 다르다. 비교 루프는 선호를 **추정**하고, 전문가
    # 경로는 이미 있는 자료를 **측정**한다. 그래서 하나의 흐름에 섞지 않고
    # 여기서 갈라놓는다 (규칙 10 - 신규 기능이 확보된 결과를 건드리지
    # 않아야 한다).
    path = st.radio(
        "어떻게 만들까요?",
        (COMPARE_PATH_LABEL, EXPERT_PATH_LABEL),
        horizontal=True,
        # key 를 준다. 테스트가 순서(radio[0])로 집으면 위젯을 하나
        # 추가할 때마다 깨진다 - 이 라디오를 넣으면서 실제로 깨뜨렸다.
        key="build_path",
        help=(
            "비교는 결과물 둘 중 나은 쪽을 고르는 방식입니다. "
            "내가 쓴 글에서 만들기는 지금까지 쓴 답변을 붙여넣으면 형식을 재서 "
            "바로 프롬프트를 만듭니다 - 모델 호출이 없습니다."
        ),
    )
    if path == EXPERT_PATH_LABEL:
        _show_expert_flow()
        st.stop()

    _show_steps()

    labels_to_keys = {config["label"]: key for key, config in DOMAIN_OPTIONS.items()}
    selected_label = st.selectbox("무엇을 도와드릴까요?", list(labels_to_keys))
    domain_key = labels_to_keys[selected_label]
    config = DOMAIN_OPTIONS[domain_key]

    st.caption(config["intro"])
    run_mode = st.radio(
        "실행 모드",
        (API_MODE_LABEL, DEMO_MODE_LABEL),
        key="run_mode",
        help=(
            "AI 실시간 생성은 실제로 모델을 호출해 후보를 만듭니다. "
            "무료 데모는 API 키나 비용 없이 규칙 기반 예시로 흐름만 보여줍니다."
        ),
    )
    demo_mode = run_mode == DEMO_MODE_LABEL
    if demo_mode:
        st.info(config["demo_info"])

    session_quota_left = MAX_API_RUNS_PER_SESSION - st.session_state.api_runs_used
    daily_quota_left = _daily_api_budget().left()
    api_blocked = not demo_mode and (session_quota_left <= 0 or daily_quota_left <= 0)
    if api_blocked:
        if session_quota_left <= 0:
            st.warning(
                f"AI 실시간 생성은 세션당 {MAX_API_RUNS_PER_SESSION}회까지입니다. "
                "무료 데모 모드는 계속 쓰실 수 있습니다."
            )
        else:
            st.warning(
                "오늘 배정된 AI 실시간 생성 횟수를 모두 썼습니다. "
                "무료 데모 모드는 계속 쓰실 수 있고, 실시간 생성은 내일 다시 열립니다."
            )

    source = st.text_area(
        config["input_label"],
        height=140 if domain_key == "coding" else 190,
        placeholder=config["placeholder"],
        max_chars=MAX_SOURCE_CHARS,
    )
    if st.button(
        "비교 시작", type="primary", key="start",
        disabled=not source.strip() or api_blocked,
    ):
        if not demo_mode:
            # 하루 예산을 먼저 차감한다. 화면을 그린 뒤 버튼을 누르기까지
            # 사이에 다른 방문자가 예산을 다 썼을 수 있으므로, 여기서
            # 실패하면 데모로 돌리지 않고 다시 고르게 한다.
            if not _daily_api_budget().consume():
                st.warning(
                    "방금 오늘 배정된 AI 실시간 생성 횟수가 모두 소진됐습니다. "
                    "무료 데모 모드로 진행해 주세요."
                )
                st.stop()
            st.session_state.api_runs_used += 1
        # 상태 관리는 service.py 로 넘긴다. 엔진 객체를 session_state 에
        # 담지 않으므로 나중에 FastAPI 세션 저장소로 그대로 옮겨진다.
        st.session_state.domain_key = domain_key
        st.session_state.demo_mode = demo_mode
        try:
            st.session_state.session = service.start_session(
                source,
                domain_key=domain_key,
                domain_path=config["path"],
                model=MODEL,
                demo_mode=demo_mode,
            )
        except Exception as exc:  # noqa: BLE001 - 첫 호출 실패는 데모로 내린다
            st.session_state.api_error = str(exc)
            st.session_state.demo_mode = True
            st.session_state.session = service.start_session(
                source,
                domain_key=domain_key,
                domain_path=config["path"],
                model=MODEL,
                demo_mode=True,
            )
        st.session_state.gauge_prev = [0.0 for _ in st.session_state.session.axes]
        st.session_state.stage = "compare"
        st.rerun()

elif st.session_state.stage == "compare":
    session = st.session_state.session
    config = DOMAIN_OPTIONS[session.domain_key]

    _show_api_error_notice()

    # 좌측 계기판 + 본문 카드. 좌측은 라운드 스테퍼와 축별 게이지다.
    side, main = st.columns([1, 4], gap="large")

    with side:
        st.markdown(
            f'<div class="ppt-label">round</div>'
            f'<div class="ppt-mono" style="font-size:28px">'
            f'{session.round:02d}<span style="color:var(--text-muted)">'
            f'/{session.total_rounds:02d}</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            theme.stepper_html(session.answered, session.total_rounds),
            unsafe_allow_html=True,
        )
        st.markdown('<div class="ppt-label">갈린 비교</div>', unsafe_allow_html=True)

        # 게이지는 확신도가 아니라 "그 축이 갈린 비교 횟수"를 보여준다.
        # 확신도는 3값 축에서 24회까지 0.06 에 머물러 차오르지 않는다(실측).
        current = [axis.fill for axis in session.axes]
        previous = st.session_state.get("gauge_prev") or [0.0] * len(current)
        if len(previous) != len(current):
            previous = [0.0] * len(current)
        st.markdown(
            theme.gauge_keyframes(previous, current, session.round),
            unsafe_allow_html=True,
        )
        for index, axis in enumerate(session.axes):
            st.markdown(
                theme.gauge_html(
                    axis.name, axis.estimate, axis.fill,
                    axis.discriminated, axis.total_rounds,
                    index=index, round_no=session.round,
                ),
                unsafe_allow_html=True,
            )
        st.session_state.gauge_prev = current

    with main:
        st.markdown(
            f'<div class="ppt-label">{config["compare_help"]}</div>',
            unsafe_allow_html=True,
        )
        col_a, col_b = st.columns(2, gap="medium")
        pair = session.pair
        for column, badge, candidate, key in (
            (col_a, "A", pair.a, "pick_a"),
            (col_b, "B", pair.b, "pick_b"),
        ):
            with column:
                # 높이를 st.container 로 고정한다. 넘치면 안에서 스크롤되고
                # 두 카드 높이가 절대 달라지지 않는다 - 후보 길이가
                # 레이아웃을 흔들면 사용자가 내용이 아니라 흔들림을 보고
                # 고르게 되고, 그게 length 축 판단 오염이다.
                #
                # 본문은 Streamlit 이 직접 그린다. HTML 로 넣으면 코딩
                # 도메인의 마크다운 코드 펜스가 이중 이스케이프돼
                # `&quot;` 가 글자로 보인다(실제로 겪음).
                with st.container(border=True, height=theme.CARD_MIN_HEIGHT):
                    st.markdown(
                        theme.card_badge_html(badge), unsafe_allow_html=True
                    )
                    _show_candidate(session.domain_key, candidate.text)
                st.button(f"{badge} 선택", key=key, use_container_width=True)
        st.markdown(
            '<div class="ppt-keyhint" style="margin-top:12px">'
            "왼쪽·오른쪽 카드 중 마음에 드는 쪽의 버튼을 누르세요</div>",
            unsafe_allow_html=True,
        )

    chosen = "a" if st.session_state.get("pick_a") else (
        "b" if st.session_state.get("pick_b") else None
    )
    if chosen:
        try:
            st.session_state.session = service.submit_choice(
                session, session.pair.pair_id, chosen
            )
        except service.StaleChoiceError:
            # 중복 클릭이나 뒤로 가기로 지난 쌍의 선택이 늦게 도착한 경우.
            # 조용히 무시한다 - 그걸 받으면 엉뚱한 비교가 이력에 들어간다.
            st.rerun()
        except Exception as exc:  # noqa: BLE001 - API 실패는 데모로 내린다
            # 막다른 길로 끝내지 않는다. 키가 만료되거나 결제 한도에 걸리면
            # 처음 보는 사람 눈에는 그냥 고장난 서비스다. 데모로 내려 남은
            # 비교를 이어가고 지금까지의 선택은 살린다.
            st.session_state.api_error = str(exc)
            st.session_state.demo_mode = True
            degraded = replace(session, demo_mode=True)
            st.session_state.session = service.submit_choice(
                degraded, degraded.pair.pair_id, chosen
            )

        if st.session_state.session.done:
            st.session_state.stage = "done"
        st.rerun()


elif st.session_state.stage == "done":
    session = st.session_state.session
    domain_key = session.domain_key
    domain = _domain_for(domain_key)
    source = session.source_text

    preferred = {axis.name: axis.estimate for axis in session.axes if axis.estimate}
    _show_api_error_notice()

    st.markdown(
        '<div class="ppt-eyebrow">converged</div>', unsafe_allow_html=True
    )
    st.markdown(
        theme.stepper_html(session.answered, session.total_rounds),
        unsafe_allow_html=True,
    )

    # 축별 추정값을 배지로. 옆에 그 축이 몇 번 갈렸는지 같이 적는다 -
    # 근거가 얼마나 모였는지가 추정값만큼 중요하다.
    st.markdown('<div class="ppt-label">추정된 선호</div>', unsafe_allow_html=True)
    st.markdown(
        theme.badges_html(
            [
                (axis.name, f"{axis.estimate} · 갈린 비교 {axis.discriminated}/{axis.total_rounds}")
                for axis in session.axes
                if axis.estimate
            ]
        ),
        unsafe_allow_html=True,
    )
    with st.expander("사람이 읽는 말로 보기"):
        _show_preferences(domain_key, preferred)

    seed_prompt = build_seed_prompt(domain, _rebuilt_estimator(session))
    prompt = st.session_state.get("optimized_prompt", seed_prompt)
    st.markdown(
        '<div class="ppt-label" style="margin-top:24px">시스템 프롬프트</div>',
        unsafe_allow_html=True,
    )
    st.code(prompt, language=None)
    st.caption("코드 블록 오른쪽 위의 복사 아이콘으로 복사할 수 있습니다.")

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

        optimize_left = max(0, MAX_OPTIMIZATIONS_PER_SESSION - st.session_state.get("optimizations_used", 0))
        st.caption(f"최적화 시도는 세션당 {MAX_OPTIMIZATIONS_PER_SESSION}회까지입니다. 남은 횟수 {optimize_left}회 (실패 포함).")
        if st.button(
            "GEPA로 프롬프트 최적화", key="optimize",
            disabled=optimize_left == 0 or _daily_optimization_budget().left() == 0,
        ):
            _run_optimize(session, seed_prompt)
    elif st.session_state.get("optimize_changed"):
        st.caption("API 최적화가 적용된 프롬프트입니다.")
    else:
        # 정직하게 적는다. 최적화를 돌렸지만 프롬프트가 그대로다.
        st.caption(
            "이번 실행에서는 초기 프롬프트가 그대로 선택됐습니다. "
            "프롬프트가 같다는 사실만으로 만점이나 최적성을 뜻하지는 않습니다. "
            "새 원문에서 결과를 비교해 주세요."
        )

    _show_prompt_trial(domain, prompt)
    _show_feedback_form(domain_key, preferred)

    if st.button("처음부터 다시"):
        _reset_session()
        st.rerun()

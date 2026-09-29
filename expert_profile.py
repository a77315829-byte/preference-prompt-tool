"""사용자가 붙여넣은 자기 글에서 형식 프로필과 앵커 프롬프트를 만든다.

Streamlit 을 import 하지 않는다. 그래서 UI 없이 그대로 단위 테스트할 수
있다 (`budget.py`, `feedback.py` 와 같은 방침).

**이 기능이 왜 API 를 쓰지 않는가.** 실측 결과 이 방법의 효과는 전부
코드로 잰 수치 앵커에서 나온다. 저자 8명 x 홀드아웃 30개에서 형식 거리
0.308 -> 0.146 (8/8 개선, p=0.008), 그리고 사용자의 실제 글을 예시로
프롬프트에 넣어도 0.149 로 차이가 없었다(페어드 p=0.727). 그러니 자료를
모델에 보낼 이유가 없다. 측정은 전부 파이썬이고 호출은 0회다.

이 경로는 모델 API를 호출하지 않는다. 다만 Streamlit 웹 입력은 서버로
전송되어 Python으로 처리되므로 브라우저 내부 처리라고 안내해서는 안 된다.
형식 측정 결과는 전문 지식이나 사실성의 재현을 검증한 것이 아니다.

**산출물이 정적 프롬프트 하나인 이유.** 앞선 실험에서 "비율을 규칙으로
적으면 모델이 못 따른다"는 결론을 냈고, 그래서 목표 단어 수를 과제마다
계산해 채워 넣어야 했다. 그건 압축률 모수화(요약처럼 답변 길이가 원문
길이를 따라가는 경우)에 해당한다. 실제 저자 16명은 **전원 절대 단어 수**
모수화가 뽑혔고, 그때 목표는 새 과제와 무관하므로 앵커가 고정된다 -
그대로 복사해 쓸 수 있는 프롬프트 한 덩어리다.

현재 앱은 답변만 받으므로 원문 대비 압축률을 계산할 수 없다. 항상 절대
분량으로 돌아간다. 요약 자료에서 비율 방식이 필요한지 자동 판별하지 못한다.
"""

from __future__ import annotations

from agents.expert_onboarding import (
    ExpertExample,
    corpus_stats,
    length_parameterization,
    stable_length_anchor,
)

# 답변을 나누는 구분선. 세 개 이상의 하이픈만 있는 줄로 쉽게 만들 수 있고,
# 마크다운을 쓰는 사람에게도 익숙하다.
DELIMITER_HINT = "---"

# 이보다 짧은 덩어리는 답변으로 보지 않는다. 구분선을 잘못 넣었을 때
# 생기는 빈 조각이나 한두 단어짜리 메모를 걸러낸다.
MIN_ANSWER_WORDS = 20

# 프로필을 계산할 수 있는 최소 개수. 이보다 적으면 평균이 답변 하나에
# 끌려다닌다.
MIN_ANSWERS = 5

# 권장 개수. 실측으로 정한 값이다 - 학습 12개에서는 앵커의 목표가
# 부정확해서(한 저자는 465단어로 추정, 실제 331단어) 형식 거리가
# 오히려 나빠졌고, 30개로 늘리면 그 저자가 -0.122 에서 +0.187 로 뒤집혔다.
RECOMMENDED_ANSWERS = 30

# 입력 상한. 브라우저와 세션 상태가 버틸 만한 크기로 묶는다.
MAX_MATERIAL_CHARS = 120_000


def parse_answers(text: str) -> list[ExpertExample]:
    """구분선으로 나눠 답변 목록을 만든다.

    과제(질문)는 받지 않는다. 절대 단어 수 모수화는 과제가 필요 없고,
    실제 저자 16명 전원이 그 모수화였다. 짝을 맞춰 입력하게 하면 부담이
    수십 배로 늘어나는데 얻는 것이 없다.
    """
    if not text:
        return []

    blocks, current = [], []
    for line in text[:MAX_MATERIAL_CHARS].splitlines():
        if line.strip() and set(line.strip()) == {"-"} and len(line.strip()) >= 3:
            blocks.append("\n".join(current))
            current = []
            continue
        current.append(line)
    blocks.append("\n".join(current))

    return [
        ExpertExample(output=block.strip())
        for block in blocks
        if len(block.split()) >= MIN_ANSWER_WORDS
    ]


def readiness(count: int) -> tuple[str, str]:
    """자료가 얼마나 모였는지 (수준, 안내문).

    수준은 "none" / "thin" / "ok" 중 하나다. 부족한데도 결과를 그냥
    보여주면 사용자가 그 수치를 믿는다 - 실측에서 학습 12개의 추정이
    실제와 40% 어긋난 저자가 있었다.
    """
    if count < MIN_ANSWERS:
        return "none", (
            f"답변 {MIN_ANSWERS}개 이상이 필요합니다. 지금 {count}개를 찾았습니다. "
            f"구분선은 하이픈 세 개(`{DELIMITER_HINT}`)만 있는 줄입니다."
        )
    if count < RECOMMENDED_ANSWERS:
        return "thin", (
            f"{count}개로 계산했습니다. {RECOMMENDED_ANSWERS}개를 권장하지만 정확도를 보장하지 않습니다. "
            "실측에서 12개만 넣었을 때 평균 길이를 40% 넘게 잘못 잡은 경우가 있었습니다."
        )
    return "ok", f"{count}개로 계산했습니다. 권장 분량을 넘겼습니다."


# 화면에 보여줄 항목. 판별력 진단을 통과한 것만 둔다 - 유보 표현·숫자·
# 1인칭 밀도는 실제 사람 16명 사이에서도 저자를 구분하지 못해 기각했다.
PROFILE_LABELS = (
    ("words_per_answer", "답변당 단어", "{value:.0f}단어"),
    ("sentences_per_answer", "답변당 문장", "{value:.1f}문장"),
    ("words_per_sentence", "문장당 단어", "{value:.1f}단어"),
    ("paragraphs_per_answer", "답변당 문단", "{value:.1f}문단"),
    ("bullet_line_ratio", "글머리 기호 줄", "{value:.0%}"),
)


def profile_rows(examples: list[ExpertExample]) -> list[tuple[str, str]]:
    """(항목 이름, 보여줄 값) 목록."""
    stats = corpus_stats(examples)
    return [
        (label, fmt.format(value=stats.get(key, 0.0)))
        for key, label, fmt in PROFILE_LABELS
    ]


def build_anchor(examples: list[ExpertExample]) -> tuple[str, str, bool]:
    """(앵커 문장, 고른 모수화, 과제마다 달라지는지).

    세 번째 값이 True 면 이 앵커는 그 과제에만 맞는 값이다. 압축률
    모수화가 뽑힌 경우이고, 그때는 정적 프롬프트로 내보내면 안 된다 -
    모델이 백분율 규칙을 스스로 적용하지 못한다는 것을 실측했다(길이
    오차가 3단어 이내에서 27~57단어로 벌어졌다).
    """
    kind, _ = length_parameterization(examples)
    # 절대 단어 수 모수화에서는 원문 길이가 목표에 영향을 주지 않는다.
    # 그래도 함수 시그니처가 원문을 요구하므로 빈 문자열을 넘긴다.
    line, kind, _ = stable_length_anchor(examples, "")
    return line, kind, kind == "ratio"


def compose_prompt(task_description: str, anchor: str) -> str:
    """사용자가 복사해 갈 최종 프롬프트."""
    parts = [part.strip() for part in (task_description, anchor) if part.strip()]
    return "\n".join(parts)

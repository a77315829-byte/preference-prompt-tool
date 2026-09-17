"""사용자의 전문 산출물 예시에서 "그 사람처럼 쓰는" 시스템 프롬프트를 만든다.

기존 `agents/domain_onboarding.py` 와 무엇이 다른가:

| | domain_onboarding | expert_onboarding (이 파일) |
|---|---|---|
| 입력 | 같은 원문 + 서로 다른 결과물 여러 개 | 한 사람의 (과제, 답변) 예시 여러 개 |
| 찾는 것 | 결과물들이 갈리는 문체 축 | 이 사람이 일관되게 쓰는 방식 |
| 산출 | domains/*.yaml + checks/*.py | 전문가 시스템 프롬프트 |

전자는 "무엇이 다른가"를 보고 축을 찾으므로 비교할 변이가 필요하다.
후자는 변이가 없는 자료 한 뭉치를 받아 "이 사람의 설정값"을 추정하고,
비교에 쓸 대안값은 LLM 이 만들어낸다.

**용어를 정확히 쓴다.** 산출물은 시스템 프롬프트이고 에이전트가 아니다.
CLAUDE.md 가 정의한 에이전트는 결과에 따라 다음 행동이 달라지고 도구를
쓰는 것이다. 프롬프트는 그 조건을 만족하지 않는다. 다만 이 프롬프트를
만드는 과정은 에이전트다 - 축을 제안하고, 판별력을 재고, 실패하면
스스로 버린다. 보고할 때는 "에이전트가 전문가 프롬프트를 만든다"로
쓴다.

**프롬프트로 되는 것과 안 되는 것.** 되는 것은 전문가의 *방식*이다.
구조, 용어, 무엇을 먼저 확인하는지, 어디서 단정하고 어디서 유보하는지.
안 되는 것은 전문가의 *지식*이다. 매뉴얼 500쪽을 프롬프트에 넣을 수
없고, 그건 검색 증강의 영역이다. 이 모듈은 전자만 다룬다.

규칙 10에 따라 기존 파이프라인과 분리한다. `engine/` 은 한 줄도 고치지
않고, 추출한 축으로 Domain 객체를 메모리에 만들어 기존 generator ·
selector · estimator 를 그대로 쓴다. 그게 확장성 주장의 실체다.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from engine.domain_loader import Axis, AxisValue, CheckSpec, Domain

# 축 후보 상한. 늘리면 비교 8회로 학습할 수 없다 (축 하나당 최소 몇 번의
# 비교가 필요하다).
MAX_AXES = 4

# 예시 하나에서 프롬프트에 넣을 최대 길이. 토큰 비용을 묶어둔다.
MAX_EXAMPLE_CHARS = 1200

# 축 추출에 쓸 예시 개수 상한.
MAX_EXAMPLES_IN_PROMPT = 6

EXTRACTION_MODEL = "openai/gpt-4.1-mini"


@dataclass
class ExpertExample:
    """전문가의 산출물 하나.

    task 는 그 산출물이 답한 과제·요청이다. 없어도 축 추출은 되지만,
    정량 검증(홀드아웃)은 task 가 있어야 가능하다 - 같은 과제를 다시
    풀려야 비교할 수 있기 때문이다.
    """

    output: str
    task: str | None = None


@dataclass
class ExpertAxisValue:
    value: str
    instruction: str


@dataclass
class ExpertAxis:
    name: str
    description: str
    author_value: str  # 이 전문가가 쓰는 값
    values: list[ExpertAxisValue] = field(default_factory=list)

    def value_names(self) -> list[str]:
        return [v.value for v in self.values]

    def instruction_for(self, value: str) -> str:
        for candidate in self.values:
            if candidate.value == value:
                return candidate.instruction
        raise ValueError(f"axis '{self.name}' has no value '{value}'")


@dataclass
class ExtractionReport:
    task_description: str
    axes: list[ExpertAxis]
    raw_response: dict = field(default_factory=dict)

    def author_combo(self) -> dict[str, str]:
        """전문가 자신의 설정값 조합. 비교 없이 바로 쓸 기준선이다."""
        return {axis.name: axis.author_value for axis in self.axes}


def _call_llm_json(system_prompt: str, user_prompt: str, model: str) -> dict:
    """JSON 을 요구하고 파싱해 돌려준다. litellm 은 호출 시점에 import 한다."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY 가 없다. .env 를 확인할 것.")

    from litellm import completion

    response = completion(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        # 온도를 고정한다. 같은 예시로 두 번 돌렸을 때 축이 완전히 달라져
        # 실험 결과가 비교 불가능해졌다 - 긴 글 저자에서 한 번은 277단어로
        # 과교정, 다음 실행은 104단어로 미달이었다. 재현되지 않으면 무엇을
        # 고쳤는지도 알 수 없다.
        temperature=0.0,
    )
    return json.loads(response.choices[0].message.content)


_EXTRACTION_SYSTEM = (
    "You analyse how one particular author writes, so that another model can be "
    "instructed to write the same way. You never guess at facts the author knows; "
    "you only describe observable habits of form, structure, wording and stance. "
    "You always answer with a single JSON object."
)


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def corpus_stats(examples: list[ExpertExample]) -> dict[str, float]:
    """예시 뭉치의 형태를 코드로 잰다.

    왜 LLM 에게 눈대중으로 맡기지 않는가: 절대 규칙 6("평가 지표는 가능한
    한 코드로 직접 잰다")이기도 하고, 실측에서 실패했기 때문이다. 긴 요약을
    쓰는 사람의 예시를 줬을 때 LLM 은 길이 축을 아예 제안하지 않고
    information_density 를 high 로 골랐다 - 긴 요약은 문장당 정보 밀도가
    오히려 낮은데 반대로 본 것이다. 그 결과 반대로 설정한 조건이 추정한
    조건보다 정답에 더 가까웠다(14문서에서 expert 승 1회).

    원인은 기준점 부재다. 한 사람의 글만 보면 "무엇에 비해 긴가"를 알 수
    없다. 하이브리드 라우팅 실험에서 얻은 교훈과 같다 - 기준점 없이 물으면
    LLM 이 자기 내부 기준을 쓴다. 그래서 수치를 재서 사실로 넘긴다.
    """
    sentence_counts, word_counts, compressions = [], [], []
    for example in examples:
        sentences = [s for s in _SENTENCE_SPLIT.split(example.output.strip()) if s.strip()]
        words = example.output.split()
        sentence_counts.append(len(sentences))
        word_counts.append(len(words))
        if example.task:
            task_words = len(example.task.split())
            if task_words:
                compressions.append(len(words) / task_words)

    mean = lambda xs: sum(xs) / len(xs) if xs else 0.0
    stats = {
        "sentences_per_answer": round(mean(sentence_counts), 1),
        "words_per_answer": round(mean(word_counts), 1),
        "words_per_sentence": round(
            mean(word_counts) / mean(sentence_counts) if mean(sentence_counts) else 0.0, 1
        ),
    }
    if compressions:
        stats["answer_to_task_word_ratio"] = round(mean(compressions), 3)
    stats.update(_style_densities(examples))
    return stats


# 길이 외에 코드로 잴 수 있는 형식 특징. 어블레이션에서 LLM 이 제안한
# 축(어조·서술 순서)이 세 경우 모두 형식을 악화시켰고, 코드로 잰 수치
# 앵커만 일관되게 작동했다. 그래서 LLM 판정을 넓히는 대신 측정 항목을
# 넓힌다. 절대 규칙 6 과 같은 방향이다.
#
# 목록은 영어 기준이다. 검증 말뭉치(MACSum)가 영어이고, 한국어까지
# 정확히 다루려면 형태소 분석이 필요해 범위를 나눈다.
_HEDGE_WORDS = frozenset(
    """
    may might could would seem seems seemed appear appears appeared likely
    unlikely possibly perhaps probably apparently reportedly allegedly
    suggests suggested indicates indicated estimated roughly approximately
    about around somewhat relatively arguably potentially
    """.split()
)

_FIRST_PERSON = frozenset("i me my mine we us our ours".split())

_BULLET_START = re.compile(r"^\s*(?:[-*•·]|\d+[.)])\s+")
_NUMERAL = re.compile(r"\b\d[\d,.]*\b")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _style_densities(examples: list[ExpertExample]) -> dict[str, float]:
    """100단어당 밀도로 재는 형식 특징들.

    밀도로 재는 이유: 길이가 다른 저자끼리 비교하려면 절대 개수가 아니라
    비율이어야 한다.
    """
    if not examples:
        return {
            "bullet_line_ratio": 0.0,
            "paragraphs_per_answer": 0.0,
            "hedges_per_100w": 0.0,
            "numerals_per_100w": 0.0,
            "first_person_per_100w": 0.0,
        }

    bullet_ratios, paragraph_counts = [], []
    hedges, numerals, first_person, totals = 0, 0, 0, 0
    for example in examples:
        text = example.output
        lines = [line for line in text.splitlines() if line.strip()]
        if lines:
            bullet_ratios.append(
                sum(1 for line in lines if _BULLET_START.match(line)) / len(lines)
            )
        paragraph_counts.append(
            len([block for block in re.split(r"\n\s*\n", text.strip()) if block.strip()])
        )

        words = [w.lower() for w in _WORD.findall(text)]
        totals += len(words)
        hedges += sum(1 for w in words if w in _HEDGE_WORDS)
        first_person += sum(1 for w in words if w in _FIRST_PERSON)
        numerals += len(_NUMERAL.findall(text))

    mean = lambda xs: sum(xs) / len(xs) if xs else 0.0
    per_100 = lambda count: round(100 * count / totals, 2) if totals else 0.0
    return {
        "bullet_line_ratio": round(mean(bullet_ratios), 3),
        "paragraphs_per_answer": round(mean(paragraph_counts), 1),
        "hedges_per_100w": per_100(hedges),
        "numerals_per_100w": per_100(numerals),
        "first_person_per_100w": per_100(first_person),
    }


# 형식 거리를 잴 때 쓰는 지표. compression ratio 는 같은 과제를 쓰면
# words_per_answer 에서 파생되므로 중복이라 넣지 않는다.
FORM_KEYS = ("sentences_per_answer", "words_per_answer", "words_per_sentence")


def form_distance(
    generated: list[ExpertExample], target: list[ExpertExample]
) -> float:
    """생성된 글의 형식이 목표 저자의 형식에서 얼마나 떨어져 있는가.

    0 이면 형식이 같고, 클수록 멀다. 지표별 상대 오차의 평균이다.

    왜 이 지표가 필요한가: 이 방법이 주장하는 것은 형식 복제인데, 검증을
    ROUGE-L 로만 하면 주장과 지표가 어긋난다. 실측에서 그 어긋남이
    드러났다 - 긴 글을 쓰는 저자에서 expert 조건이 목표 길이에 훨씬
    가까웠는데도(목표 128.4단어 대비 base +52.0, expert +18.2) ROUGE-L 은
    거의 같았다(0.177 vs 0.170). ROUGE-L 은 어떤 단어가 겹치는지를 보고,
    길이를 맞춘 것만으로는 같은 문장이 나오지 않는다.

    그래서 둘을 나란히 본다. 이 지표는 형식을 맞췄는지, ROUGE-L 은 내용이
    가까워졌는지를 각각 말한다. 형식은 이기고 내용은 못 이긴다면 그대로
    보고하는 것이 정직하다.
    """
    generated_stats = corpus_stats(generated)
    target_stats = corpus_stats(target)

    errors = []
    for key in FORM_KEYS:
        target_value = target_stats.get(key, 0.0)
        if not target_value:
            continue
        errors.append(abs(generated_stats.get(key, 0.0) - target_value) / target_value)
    return round(sum(errors) / len(errors), 3) if errors else 0.0


# 앵커 문장을 만들 수 있는 항목과 그 문구. 여기 없는 통계는 진단용이다.
_ANCHOR_TEMPLATES = {
    "sentences_per_answer": "write about {value:.0f} sentences",
    "words_per_answer": "use roughly {value:.0f} words in total",
    "bullet_line_ratio": "put about {pct:.0f}% of your lines in a bulleted list",
    "paragraphs_per_answer": "break it into about {value:.0f} paragraphs",
    "hedges_per_100w": "use about {value:.1f} hedging words per 100 words",
    "numerals_per_100w": "include about {value:.1f} numbers per 100 words",
    "first_person_per_100w": "use about {value:.1f} first-person words per 100 words",
}

# 저자와 모델 기본 출력의 상대 차이가 이 값을 넘는 항목만 앵커에 넣는다.
# 왜 골라 넣는가: 이득은 저자의 형식이 모델 기본값에서 얼마나 먼지에
# 비례한다는 것이 실측 결과다(base 형식 거리 1.776 / 0.721 / 0.238 순서가
# 그대로 이득 순서였다). 이미 기본값과 같은 항목까지 지시하면 지시문만
# 길어지고, 긴 글 저자에서 그게 과교정으로 돌아왔다.
ANCHOR_RELATIVE_THRESHOLD = 0.25


# 길이 계열 항목만. 넓힌 항목(불릿·문단·유보·숫자·1인칭)의 기여를
# 분리해 재려면 길이만 쓰는 조건이 필요하다.
LENGTH_ANCHOR_KEYS = ("sentences_per_answer", "words_per_answer")


def selective_form_anchor(
    author: list[ExpertExample],
    model_default: list[ExpertExample],
    keys: tuple[str, ...] | None = None,
) -> tuple[str, dict[str, float]]:
    """저자가 모델 기본값과 실제로 다른 항목만 골라 앵커를 만든다.

    model_default 는 과제 서술만 준 프롬프트로 생성한 결과물이다. 모델이
    가만히 뒀을 때 어떤 형식으로 쓰는지를 측정해 기준점으로 삼는다.
    한 사람의 글만 보면 "무엇에 비해 긴가"를 알 수 없다는 문제를 코드로
    푸는 방식이고, LLM 에게 눈대중을 맡기는 것과 반대다.

    keys 를 주면 그 항목만 후보로 본다. 넓힌 항목의 기여를 길이 계열과
    분리해 재는 데 쓴다.

    돌려주는 것은 (앵커 문장, 고른 항목별 상대 차이)다.
    """
    author_stats = corpus_stats(author)
    default_stats = corpus_stats(model_default)

    selected: dict[str, float] = {}
    parts = []
    allowed = _ANCHOR_TEMPLATES if keys is None else {
        k: v for k, v in _ANCHOR_TEMPLATES.items() if k in keys
    }
    for key, template in allowed.items():
        target = author_stats.get(key)
        baseline = default_stats.get(key)
        if target is None or baseline is None:
            continue
        # 분모가 0에 가까우면 상대 차이가 무의미하므로 절대 차이로 본다.
        scale = max(abs(baseline), abs(target), 1e-6)
        relative = abs(target - baseline) / scale
        if relative < ANCHOR_RELATIVE_THRESHOLD:
            continue
        selected[key] = round(relative, 3)
        parts.append(template.format(value=target, pct=100 * target))

    if not parts:
        return "", {}
    return "Match this form: " + ", ".join(parts) + ".", selected


# 보정 배율의 상·하한. 탐침 생성이 이상하게 나왔을 때 요청값이 터무니없이
# 커지는 것을 막는다.
CALIBRATION_MIN, CALIBRATION_MAX = 0.5, 3.0


def anchor_text(values: dict[str, float]) -> str:
    """항목별 목표값으로 앵커 문장을 만든다."""
    parts = [
        _ANCHOR_TEMPLATES[key].format(value=value, pct=100 * value)
        for key, value in values.items()
        if key in _ANCHOR_TEMPLATES
    ]
    return "Match this form: " + ", ".join(parts) + "." if parts else ""


def ratio_anchor(author: list[ExpertExample], source_text: str) -> str:
    """원문 길이에 비례해 과제마다 목표를 다시 계산한 앵커.

    왜 절대 단어 수가 아닌가: 저자의 길이는 상수가 아니다. 같은 사람이
    짧은 기사에는 40단어, 긴 기사에는 258단어를 쓴다. 실측에서 원문
    길이와 답변 길이의 상관이 0.94~0.995 였고, 절대 단어 수의 변동계수는
    0.56 인데 원문 대비 압축률의 변동계수는 0.08 이었다. 압축률이 7배
    안정적이다.

    그래서 학습 예시에서 압축률만 재고, 목표 단어 수는 새 과제의 원문
    길이에 곱해서 과제마다 따로 구한다. 예시 8개로도 압축률은 잘 잡히지만
    절대 단어 수는 안 잡힌다 - 그 차이 때문에 학습·홀드아웃 평균이
    25단어씩 어긋나 실험을 한참 헤맸다.
    """
    stats = corpus_stats(author)
    ratio = stats.get("answer_to_task_word_ratio")
    words_per_sentence = stats.get("words_per_sentence")
    if not ratio or not words_per_sentence:
        return ""

    target_words = ratio * len(source_text.split())
    target_sentences = max(1.0, target_words / words_per_sentence)
    return anchor_text(
        {
            "sentences_per_answer": target_sentences,
            "words_per_answer": target_words,
        }
    )


def ratio_rule_anchor(author: list[ExpertExample]) -> str:
    """압축률을 규칙으로 적은 앵커. 과제마다 다시 계산하지 않는다.

    왜 이것도 필요한가: ratio_anchor 는 과제마다 목표 단어 수를 다시
    계산하므로 프롬프트가 과제마다 달라진다. 그런데 이 도구의 산출물은
    사용자가 복사해 쓰는 프롬프트 한 덩어리다. 과제마다 다른 프롬프트는
    제품이 될 수 없다.

    그래서 계산을 모델에게 넘긴다 - "원문의 몇 %로 쓰라"고 규칙만 적는다.
    모델이 그 규칙을 따르는지는 실측해야 한다. 따라준다면 재사용 가능한
    프롬프트 하나로 끝나고, 아니면 앱이 과제마다 채워 넣어야 한다.
    """
    stats = corpus_stats(author)
    ratio = stats.get("answer_to_task_word_ratio")
    words_per_sentence = stats.get("words_per_sentence")
    if not ratio or not words_per_sentence:
        return ""

    percent = 100 * ratio
    # 1000단어 기준 예시를 같이 준다. 백분율만 주면 모델이 어림을 크게
    # 틀릴 수 있어서, 곱셈을 대신 해준 수치를 하나 붙인다.
    per_thousand = round(ratio * 1000)
    return (
        f"Match this form: write about {percent:.1f}% as many words as the source "
        f"text (roughly {per_thousand} words for a 1000-word source), "
        f"averaging about {words_per_sentence:.0f} words per sentence."
    )


def calibrate_targets(
    target: dict[str, float], achieved: dict[str, float], keys
) -> tuple[dict[str, float], dict[str, float]]:
    """요청한 값과 실제로 나온 값의 비율로 요청값을 역보정한다.

    왜 필요한가: 모델은 큰 길이 목표에 체계적으로 미달한다. 실측에서
    43단어를 요청하면 43.9가 나오는데 85단어는 71.9, 128단어는 97.9만
    나왔다. 요청값이 커질수록 미달 폭이 커진다. 지금까지 모든 실험에서
    반복된 short/long 비대칭이 여기서 설명된다.

    그러면 요청값을 그대로 넣을 이유가 없다. 학습 과제로 한 번 탐침
    생성을 해서 "128을 요청하면 98이 나온다"를 측정하고, 목표를 맞추려면
    얼마를 요청해야 하는지 역산한다. 128 * (128/98) = 167 을 요청하는 식이다.

    측정 결과에 따라 다음 요청이 달라지므로 이건 루프이고, 홀드아웃이
    아니라 학습 과제로 재므로 누출이 없다.

    돌려주는 것은 (보정된 목표값, 항목별 보정 배율)이다.
    """
    corrected: dict[str, float] = {}
    factors: dict[str, float] = {}
    for key in keys:
        wanted = target.get(key)
        got = achieved.get(key)
        if not wanted or not got:
            continue
        ratio = min(max(wanted / got, CALIBRATION_MIN), CALIBRATION_MAX)
        corrected[key] = round(wanted * ratio, 1)
        factors[key] = round(ratio, 3)
    return corrected, factors


def form_anchor(examples: list[ExpertExample]) -> str:
    """측정한 형식을 프롬프트에 그대로 박는 한 줄.

    왜 필요한가: 축 지시문은 LLM 이 수치를 형용사로 번역한 결과다. 그
    번역이 두 방향으로 다 틀렸다. 긴 글을 쓰는 저자에서 처음엔 길이 축을
    아예 제안하지 않아 짧게 나왔고(목표 128.4단어, anti 가 base 보다 높음),
    수치를 사실로 넘긴 뒤에는 "충분히 길게"를 과하게 적용해 277.7단어까지
    넘어갔다(형식 거리 0.325 -> 0.970).

    번역을 거치지 않고 수치를 직접 주면 그 왕복이 사라진다. 수치는
    사용자 자신의 예시에서 코드로 잰 것이므로 외부 지식이 아니다.

    이것만으로 길이가 맞는 것은 당연하므로, 축의 기여와 구분해서 보고해야
    한다. experiments/expert_prompt_eval.py 가 두 조건을 나눠 잰다.
    """
    stats = corpus_stats(examples)
    sentences = stats["sentences_per_answer"]
    words = stats["words_per_answer"]
    if not sentences or not words:
        return ""
    return (
        f"Match this length: about {sentences:.0f} sentences and roughly "
        f"{words:.0f} words in total."
    )


def _stats_block(examples: list[ExpertExample]) -> str:
    stats = corpus_stats(examples)
    lines = [f"  {key}: {value}" for key, value in stats.items()]
    return (
        "Measured facts about this author's answers, computed from the text rather than "
        "estimated:\n" + "\n".join(lines) + "\n"
        "Trust these numbers over your impression. You are seeing only one author, so you "
        "have no reference for what counts as long or dense; the numbers are that "
        "reference. For context, a typical news summary runs 2 to 4 sentences and 40 to "
        "80 words, at roughly 18 to 25 words per sentence.\n"
        "If the numbers show this author is unusually long, short, or elaborate, you must "
        "include an axis capturing that, and set author_value to the end that matches the "
        "numbers.\n\n"
    )


def _extraction_user_prompt(examples: list[ExpertExample], max_axes: int) -> str:
    blocks = []
    for index, example in enumerate(examples[:MAX_EXAMPLES_IN_PROMPT], start=1):
        block = [f"[Example {index}]"]
        if example.task:
            block.append(f"Task: {example.task[:300]}")
        block.append(f"Author's answer: {example.output[:MAX_EXAMPLE_CHARS]}")
        blocks.append("\n".join(block))

    return (
        "Below are answers written by one author working in their area of expertise.\n\n"
        + "\n\n".join(blocks)
        + "\n\n"
        + _stats_block(examples)
        + f"Identify at most {max_axes} axes that capture HOW this author works, not what "
        "they know. Good axes describe things like structure, level of hedging, ordering "
        "of concerns, density of domain terminology, or whether caveats come first. "
        "Do not propose axes about factual content or subject matter.\n\n"
        "For each axis give:\n"
        '  "name": short snake_case identifier\n'
        '  "description": one sentence, in Korean, for a Korean-speaking operator\n'
        '  "author_value": which value this author uses\n'
        '  "values": 2 or 3 entries, each {"value": short label, '
        '"instruction": one imperative sentence telling a model to write that way}\n'
        "The author_value must be one of the value labels. Include at least one value that "
        "clearly differs from the author, so the two can be compared side by side.\n\n"
        "Also give:\n"
        '  "task_description": imperative instructions addressed to a model that will DO '
        "the author's job on a new input of the same kind, telling it to produce the "
        "author's kind of output. This is the hard part, so check it against these rules "
        "before answering. It must NOT ask the model to analyse, describe, study or "
        "imitate a style. It must NOT mention the author, the examples, or style at all. "
        "It must read as a job instruction that would still make sense to someone who "
        "never saw the examples. State the output language explicitly.\n"
        "Critically, task_description must be STYLE-NEUTRAL: name the task and the "
        "output language and nothing else. Do not describe length, brevity, level of "
        "detail, tone, word choice, structure or objectivity there, because those belong "
        "to the axes. If the task_description already carries the style, the axes cannot "
        "be turned off and the two cannot be compared.\n"
        '  Good: "Summarise the given news article in English."\n'
        '  Bad, style leaked in: "Summarise the given news article in English using '
        'concise sentences with minimal detail."\n'
        '  Bad, meta instruction: "Analyse the style of the CNN article writer."\n\n'
        "Write task_description and every value instruction in the same language the "
        "author writes in, so the assembled prompt never mixes languages. The Korean "
        "descriptions are the only Korean fields.\n\n"
        'Respond as {"task_description": ..., "axes": [...]}.'
    )


# task_description 이 "문체를 분석하라" 같은 메타 지시로 나오는 일이 실제로
# 있었다. 그대로 쓰면 모델이 전문가의 일을 하는 대신 문체를 설명한다.
# 프롬프트에 "그러지 말라"고 적는 것만으로는 안 막힌다 - 같은 프롬프트가
# 어떤 호출에서는 맞고 어떤 호출에서는 틀렸다. 그래서 코드로 검사하고
# 실패 사유를 돌려주며 재시도한다 (agents/code_validator.py 와 같은 태도).
_META_MARKERS = (
    "스타일", "문체", "style",
    "분석하라", "분석해", "analyse", "analyze",
    "저자", "필자", "author", "writer's",
    "모방", "흉내", "imitate", "mimic",
    "예시", "example", "sample",
)

MAX_EXTRACTION_ATTEMPTS = 3


# 문체가 과제 서술에 새어 들어가면 기준선이 오염된다. 실측에서 실제로
# 겪었다 - 과제 서술이 "concise sentences with minimal elaboration" 까지
# 담아버려서, 축을 전부 끈 base 조건이 이미 개인화된 상태였다. 그 결과
# expert 와 base 의 차이가 +0.008 로 묻혔고, 반대로 설정한 anti 만
# -0.065 로 뚜렷했다. 축이 담당할 성질은 과제 서술에서 빠져 있어야
# 비교 자체가 성립한다.
_STYLE_LEAK_MARKERS = (
    "concise", "brief", "briefly", "succinct", "terse", "verbose",
    "minimal", "elaborate", "detailed", "lengthy",
    "tone", "objective", "subjective", "formal", "informal", "casual",
    "bullet", "plain language", "technical terminology",
    "간결", "짧게", "상세", "자세히", "어조", "객관", "주관", "격식",
)


def _task_description_problem(text: str) -> str | None:
    """과제 서술이 쓸 수 없는 형태면 사유를, 괜찮으면 None 을 돌려준다."""
    stripped = text.strip()
    if len(stripped) < 10:
        return "task_description is too short to be a usable instruction"
    lowered = stripped.lower()

    meta_hits = [m for m in _META_MARKERS if m.lower() in lowered]
    if meta_hits:
        return (
            "task_description must instruct the model to DO the job, but it mentions "
            f"{meta_hits}. Rewrite it as a standalone job instruction that never refers "
            "to the author, the examples, or style."
        )

    style_hits = [m for m in _STYLE_LEAK_MARKERS if m.lower() in lowered]
    if style_hits:
        return (
            f"task_description describes style ({style_hits}), which belongs to the "
            "axes. Rewrite it to name only the task and the output language, so the "
            "axes can be varied independently."
        )
    return None


def extract_axes(
    examples: list[ExpertExample],
    *,
    max_axes: int = MAX_AXES,
    model: str = EXTRACTION_MODEL,
) -> ExtractionReport:
    """예시에서 축과 이 전문가의 설정값을 추정한다."""
    if not examples:
        raise ValueError("예시가 최소 하나 필요하다")

    base_prompt = _extraction_user_prompt(examples, max_axes)
    payload: dict = {}
    problem: str | None = None
    for attempt in range(MAX_EXTRACTION_ATTEMPTS):
        user_prompt = base_prompt
        if problem:
            user_prompt += (
                "\n\nYour previous answer was rejected: "
                + problem
                + "\nAnswer again, fixing only that."
            )
        payload = _call_llm_json(_EXTRACTION_SYSTEM, user_prompt, model)
        problem = _task_description_problem(str(payload.get("task_description", "")))
        if problem is None:
            break
    else:
        raise ValueError(
            f"{MAX_EXTRACTION_ATTEMPTS}회 시도했지만 쓸 수 있는 task_description 을 "
            f"못 받았다. 마지막 사유: {problem}"
        )

    axes = []
    for raw in payload.get("axes", [])[:max_axes]:
        values = [
            ExpertAxisValue(value=str(v["value"]), instruction=str(v["instruction"]))
            for v in raw.get("values", [])
            if v.get("value") and v.get("instruction")
        ]
        if len(values) < 2:
            # 값이 하나면 비교할 대안이 없어 A/B 루프에 못 쓴다.
            continue
        author_value = str(raw.get("author_value", "")) or values[0].value
        if author_value not in [v.value for v in values]:
            author_value = values[0].value
        axes.append(
            ExpertAxis(
                name=str(raw["name"]),
                description=str(raw.get("description", "")),
                author_value=author_value,
                values=values,
            )
        )

    task_description = str(payload.get("task_description", "")).strip()
    if not axes:
        raise ValueError("쓸 수 있는 축을 하나도 못 뽑았다 (값이 2개 이상인 축이 없다)")

    return ExtractionReport(task_description=task_description, axes=axes, raw_response=payload)


# checks 를 붙이지 않는다. metric_builder 와 GEPA 최적화는 코드로 잴 수
# 있는 검사 함수가 있어야 의미가 있는데, 추출한 축에는 아직 그게 없다.
# 없는 측정을 있는 것처럼 배선하지 않는다 (절대 규칙 6). 비교 루프와
# 프롬프트 조립에는 checks 가 필요하지 않다.
_PLACEHOLDER_CHECK = CheckSpec(fn="", target={})


def to_domain(report: ExtractionReport, name: str = "expert") -> Domain:
    """추출 결과를 기존 엔진이 이해하는 Domain 으로 바꾼다.

    이 함수가 재사용의 접점이다. Domain 하나만 만들어주면
    generator(프롬프트 조립·생성), selector(다음 쌍 고르기),
    estimator(선호 추정)가 전부 수정 없이 돈다.
    """
    axes = [
        Axis(
            name=axis.name,
            type="enum",
            description=axis.description,
            values=[
                AxisValue(value=v.value, prompt=v.instruction, check=_PLACEHOLDER_CHECK)
                for v in axis.values
            ],
        )
        for axis in report.axes
    ]
    return Domain(
        name=name,
        task_description=report.task_description,
        checks_module="",  # 위 주석 참고. metric/GEPA 는 이 도메인에서 쓰지 않는다.
        axes=axes,
    )

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
import statistics
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


def ratio_anchor(
    author: list[ExpertExample],
    source_text: str,
    keys: tuple[str, ...] = ("sentences_per_answer", "words_per_answer"),
) -> str:
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

    `keys` 로 적을 항목을 고를 수 있다. 문장 수 목표는 단어 목표를
    문장당 단어 수로 나눈 값인데, 판별력 진단
    (`experiments/form_feature_spread.py`)에서 문장당 단어 수는 저자를
    가르지 못했다(평균기준 1.02, 압축률은 165.5). 그러면 문장 절은
    거의 보편 상수로 나눈 같은 정보의 반복일 수 있다 - 빼고 재본다.
    """
    stats = corpus_stats(author)
    ratio = stats.get("answer_to_task_word_ratio")
    words_per_sentence = stats.get("words_per_sentence")
    if not ratio or not words_per_sentence:
        return ""

    target_words = ratio * len(source_text.split())
    target_sentences = max(1.0, target_words / words_per_sentence)
    targets = {
        "sentences_per_answer": target_sentences,
        "words_per_answer": target_words,
    }
    return anchor_text({k: v for k, v in targets.items() if k in keys})


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


# 압축률로 바꾸려면 절대 단어 수보다 이 배수만큼 안정적이어야 한다.
# 실측으로 고른 값이다 (저자 11명 x 20개 분할: 요약 쪽 비율 최대 0.545,
# Q&A 쪽 최소 0.694 - 그 틈 사이라면 220개 전부 정답이다).
RATIO_MARGIN = 0.6


def _coefficient_of_variation(values: list[float]) -> float | None:
    """표준편차 / 평균. 평균이 0 이거나 표본이 1개면 못 잰다."""
    if len(values) < 2:
        return None
    mean = statistics.fmean(values)
    if mean <= 0:
        return None
    return statistics.stdev(values) / mean


def length_parameterization(author: list[ExpertExample]) -> tuple[str, dict[str, float]]:
    """길이를 절대 단어 수로 볼지 원문 대비 압축률로 볼지 재서 고른다.

    **왜 고르게 하나.** 3차에서 MACSum 으로 "압축률이 절대 단어 수보다
    7배 안정적"이라는 결론을 냈고 n=30 부호검정까지 붙였다. 그런데 실제
    Q&A 코퍼스(Stack Exchange 저자 4명)에서 방향이 반대였다.

    | 코퍼스 | 상관(과제,답변) | 절대 CV | 압축률 CV |
    |---|---|---|---|
    | MACSum 요약 | 0.91~0.996 | 0.53~0.56 | 0.08~0.10 |
    | SE Q&A | 0.04~0.25 | 0.54~0.68 | 0.77~1.03 |

    요약문은 원문에서 파생되므로 길이가 원문을 따라간다. 답변은 그렇지
    않다 - 길이를 정하는 건 질문의 난이도이고 질문의 길이가 아니다.
    그러니 어느 쪽이 맞는지는 과제 유형마다 다르고, **상수로 박으면
    한쪽에서 틀린다.** 학습 예시에서 변동계수를 재서 작은 쪽을 쓴다
    (절대 규칙 6 - 코드로 직접 재고 고른다).

    **마진이 필요하다.** 처음엔 그냥 작은 쪽을 골랐는데 n=12 에서
    불안정했다. 실제 저자 u67 은 전체 96쌍으로 보면 절대 쪽이 맞는데
    (절대 CV 0.511 대 압축률 0.961) 어떤 12개 분할에서는 뒤집혀
    압축률을 골랐고, 그 결과 형식 거리가 base 의 0.189 에서 0.797 로
    **아무것도 안 한 것보다 나빠졌다**(목표 180단어에 331단어).

    임계값은 실측으로 골랐다 - 두 코퍼스의 저자 11명 x 20개 분할 = 220
    케이스에서 압축률CV/절대CV 비율이 요약 쪽은 최대 0.545, Q&A 쪽은
    최소 0.694 로 틈이 벌어진다. 그 사이를 쓰면 220개 전부 정답이고,
    마진 없이(1.0) 고르면 13개를 틀린다.

    돌려주는 것은 ("absolute" | "ratio", 잰 변동계수들)이다.
    """
    word_counts = [float(len(example.output.split())) for example in author]
    ratios = [
        len(example.output.split()) / len(example.task.split())
        for example in author
        if example.task and example.task.split()
    ]

    absolute_cv = _coefficient_of_variation(word_counts)
    ratio_cv = _coefficient_of_variation(ratios) if len(ratios) == len(author) else None

    measured = {}
    if absolute_cv is not None:
        measured["absolute_cv"] = round(absolute_cv, 3)
    if ratio_cv is not None:
        measured["ratio_cv"] = round(ratio_cv, 3)

    # 압축률은 과제가 전부 있어야만 후보다. 일부만 있으면 두 값이 서로
    # 다른 표본에서 나와 비교가 성립하지 않는다.
    if ratio_cv is None or absolute_cv is None:
        return ("absolute" if ratio_cv is None else "ratio"), measured

    # 절대 단어 수가 완벽히 일정한 저자라면 바꿀 이유가 없다. 여기서
    # 나누면 0 으로 나눈다 - 테스트가 먼저 잡았다.
    if absolute_cv == 0:
        return "absolute", measured

    measured["ratio_over_absolute"] = round(ratio_cv / absolute_cv, 3)
    # 근소한 우위로는 바꾸지 않는다. 절대 단어 수가 기본값이고, 압축률은
    # 확실히 더 안정적일 때만 쓴다.
    if ratio_cv < absolute_cv * RATIO_MARGIN:
        return "ratio", measured
    return "absolute", measured


def stable_length_anchor(
    author: list[ExpertExample], source_text: str
) -> tuple[str, str, dict[str, float]]:
    """더 안정적인 모수화로 길이 앵커를 만든다.

    압축률을 골랐으면 목표 단어 수를 이 과제의 원문 길이에 곱해 구하고,
    절대 단어 수를 골랐으면 학습 예시의 평균을 그대로 목표로 쓴다.
    문장 목표는 두 경우 모두 함께 적는다 - 문장 절을 빼면 모델이 문장을
    잘게 쪼개서(문장당 13~17단어, 저자는 18~23) 형식 거리가 3~11배
    나빠진다는 것을 실측했다.

    돌려주는 것은 (앵커 문장, 고른 모수화, 잰 변동계수들)이다.
    """
    kind, measured = length_parameterization(author)
    stats = corpus_stats(author)
    words_per_sentence = stats.get("words_per_sentence")

    if kind == "ratio":
        ratio = stats.get("answer_to_task_word_ratio")
        if not ratio:
            return "", kind, measured
        target_words = ratio * len(source_text.split())
    else:
        target_words = stats.get("words_per_answer") or 0.0

    if not target_words or not words_per_sentence:
        return "", kind, measured

    return (
        anchor_text(
            {
                "sentences_per_answer": max(1.0, target_words / words_per_sentence),
                "words_per_answer": target_words,
            }
        ),
        kind,
        measured,
    )


# 길이 앵커 위에 더할 구조 항목 후보. 판별력 진단에서 살아남은 것만
# 둔다 - 유보 표현·숫자·1인칭 밀도는 실제 사람 8명 사이에서도 신호가
# 없어 기각했다.
STRUCTURE_KEYS = ("paragraphs_per_answer", "bullet_line_ratio")


def structure_anchor(
    author: list[ExpertExample],
    model_default: list[ExpertExample],
    source_text: str,
) -> tuple[str, list[str]]:
    """길이 앵커에, 모델 기본값과 실제로 다른 구조 항목만 더한다.

    **왜 골라서 더하나.** 문단 목표를 항상 붙이면 상충이 생긴다. 실제
    저자 4명에서 문단 오차는 1.90 → 0.88 로 좋아지는데 길이·문장 형식
    거리가 0.158 → 0.256 으로 나빠졌다 - base(0.233)보다도 나쁘다.
    지시를 하나 더 붙이면 앞의 것이 덜 지켜진다.

    그러면 **이득이 있을 때만** 붙이는 게 맞다. 이득은 저자가 모델
    기본값에서 얼마나 먼지에 비례한다는 것이 이미 확인된 관찰이고
    (`selective_form_anchor` 의 근거), 실제로 base 가 이미 저자의 문단
    수에 가까운 저자가 있었다(u19707: 실제 3.3, base 3.6).

    돌려주는 것은 (앵커 문장, 더한 항목 이름들)이다.
    """
    length_line, _, _ = stable_length_anchor(author, source_text)
    structure_line, selected = selective_form_anchor(
        author, model_default, keys=STRUCTURE_KEYS
    )
    parts = [part for part in (length_line, structure_line) if part]
    return "\n".join(parts), list(selected)


# few-shot 에 넣을 예시 수의 기본값. 사용자가 손으로 붙여 넣을 만한
# 분량이면서, 형식 평균이 어느 정도 잡히는 수로 잡았다.
FEWSHOT_COUNT = 3

# 예시 안의 과제 본문만 이 길이로 자른다. **답변은 자르지 않는다** -
# 답변을 자르면 이 방법이 전달하려는 형식(특히 길이)이 왜곡돼서, 재는
# 대상 자체가 달라진다. 과제는 길이가 형식에 영향을 주지 않으므로 잘라도
# 된다.
FEWSHOT_TASK_CHARS = 800


def fewshot_prompt(
    task_description: str,
    author: list[ExpertExample],
    count: int = FEWSHOT_COUNT,
) -> str:
    """저자의 실제 (과제, 답변) 쌍을 예시로 붙인 프롬프트.

    **왜 이 조건이 반드시 필요한가.** 지금까지의 방법은 저자의 형식을
    수치로 재서 지시문에 박는다. 그런데 "그냥 이 사람 답변 몇 개를
    보여주면 되지 않나"가 가장 먼저 나올 질문이고, 그 비교가 없으면
    측정 앵커의 값어치를 주장할 수 없다.

    또 이 조건은 앵커가 부딪힌 벽을 우회한다 - 수치 절을 쌓을수록 서로
    간섭해서(길이+문장+문단을 같이 주면 앞의 둘이 덜 지켜졌다) 지시문을
    늘리는 길이 막혔는데, 예시는 절이 아니라 본보기라서 간섭할 절 자체가
    없다.

    대신 비용이 든다 - 예시 3개면 프롬프트가 수천 토큰 늘어나고, 앵커는
    한 문장이다. 그러니 "이기는가"만이 아니라 "얼마를 더 써서 이기는가"도
    같이 봐야 한다.
    """
    chosen = [example for example in author if example.task][:count]
    if not chosen:
        return task_description

    blocks = []
    for index, example in enumerate(chosen, start=1):
        task = " ".join(example.task.split())[:FEWSHOT_TASK_CHARS]
        blocks.append(
            f"Example {index}\nQuestion: {task}\nAnswer: {example.output}"
        )
    return (
        task_description
        + "\n\nHere are answers this author has written. Match the way they write.\n\n"
        + "\n\n".join(blocks)
    )


# 저자 프로필로 점수를 낼 때 보는 항목. 판별력 진단에서 살아남은 것만
# 둔다 (길이 계열 + 문단·글머리 기호). 유보 표현·숫자·1인칭 밀도는 실제
# 사람 8명 사이에서도 신호가 없어 기각했다.
PROFILE_KEYS = (
    "words_per_answer",
    "sentences_per_answer",
    "paragraphs_per_answer",
    "bullet_line_ratio",
)

# 값 자체가 0~1 비율인 항목. 이런 항목은 상대 오차가 아니라 **절대
# 차이**로 본다.
#
# 왜 나눠야 하는가: 처음엔 전 항목을 상대 오차로 재고 1.0 에서 잘랐다.
# 그런데 목표가 0 에 가까운 항목에서는 어느 쪽으로 얼마나 벗어나도
# 오차가 상한에 붙어 **구분이 사라진다.** 실측에서 물렸다 - 저자의
# 글머리 기호 비율이 0.07 인데 GEPA 는 0.41 을 냈고(6배) 다른 조건은
# 0.00 을 냈는데, 둘 다 상대오차 1.0 을 넘어 똑같이 처리돼서 지표가
# 그 차이를 전혀 벌하지 못했다. 그래서 GEPA 는 글머리 기호를 마음껏
# 남발하면서 점수를 올렸다. **볼 수 없는 것은 최적화되지 않는다.**
#
# 비율 항목은 값이 이미 0~1 안에 있으므로 절대 차이가 곧 유계 오차다.
PROFILE_RATIO_KEYS = ("bullet_line_ratio",)


def _profile_error(key: str, got: float, target: float) -> float:
    """항목 하나의 0~1 오차.

    개수 항목은 상대 오차를 쓰되 `e / (1 + e)` 로 눌러 담는다. 하드
    상한과 달리 **끝에서 포화되지 않으므로** 크게 어긋난 정도가 계속
    반영되고, 동시에 한 항목이 점수를 독차지하지도 않는다.
    """
    if key in PROFILE_RATIO_KEYS:
        return min(abs(got - target), 1.0)
    scale = max(abs(target), 1e-6)
    relative = abs(got - target) / scale
    return relative / (1.0 + relative)


def profile_targets(author: list[ExpertExample], source_text: str) -> dict[str, float]:
    """이 과제에 대해 저자가 쓸 것으로 보이는 형식 목표값.

    길이는 `length_parameterization` 이 고른 모수화를 따른다 - 압축률을
    골랐으면 이 과제의 원문 길이에 곱하고, 절대 단어 수를 골랐으면 학습
    평균을 그대로 쓴다. 나머지 항목은 과제 길이와 무관하므로 평균이다.
    """
    stats = corpus_stats(author)
    kind, _ = length_parameterization(author)
    words_per_sentence = stats.get("words_per_sentence") or 0.0

    if kind == "ratio" and stats.get("answer_to_task_word_ratio"):
        target_words = stats["answer_to_task_word_ratio"] * len(source_text.split())
    else:
        target_words = stats.get("words_per_answer") or 0.0

    targets = {
        "words_per_answer": target_words,
        "sentences_per_answer": (
            max(1.0, target_words / words_per_sentence) if words_per_sentence else 0.0
        ),
    }
    for key in PROFILE_KEYS:
        if key not in targets:
            targets[key] = stats.get(key, 0.0)
    return {key: targets[key] for key in PROFILE_KEYS}


def expert_form_metric(author: list[ExpertExample]):
    """저자 프로필과의 형식 일치도를 (점수, 자연어 피드백)으로 돌려준다.

    **왜 이게 필요한가.** 수치 목표를 지시문 절로 쌓는 방식이 벽에 부딪혔다.
    실측된 현상이 세 번 같았다 - 단어만 지시하면 문장이 잘게 쪼개지고
    (문장당 13~17단어, 저자는 18~23), 길이만 지시하면 문단이 붕괴하고
    (저자 둘에서 1.0문단), 길이·문장·문단을 같이 주면 앞의 둘이 덜
    지켜진다(형식 거리 0.158 → 0.256, base 0.233 보다도 나쁘다).
    모델 기본값과 다른 항목만 골라 붙여도 안 됐다 - 실제 저자 4명 전원이
    문단·글머리 기호에서 기본값과 달라서 선별 게이트가 아예 작동하지
    않았다(0.264).

    즉 문제는 "무엇을 재는가"가 아니라 **여러 수치 목표를 한 프롬프트에
    쌓으면 서로 간섭한다**는 것이다. 그러면 문구를 사람이 조율하는 대신
    최적화기에 넘기는 것이 맞고, 이 프로젝트에는 이미 그 부품이 있다
    (GEPA + `engine/metric_builder.py`). 그쪽에 넘기려면 평가 함수가
    필요하고, 이 함수가 그것이다.

    피드백을 자연어로 같이 내는 것이 핵심이다 - 점수만 주는 조건과
    비교했을 때 같은 호출 예산에서 0.98 대 0.44 였다(피드백 풍부도
    어블레이션). 축별 위반 내역을 글로 적어주면 GEPA 가 적은 시도로
    좋은 문구를 찾는다.

    **순환 논증 주의.** 이 함수로 최적화한 결과를 이 함수로만 채점하면
    안 된다(절대 규칙 7). 보고할 때 ROUGE-L 을 반드시 병기한다.
    """

    def metric(output: str, source: str) -> tuple[float, str]:
        targets = profile_targets(author, source)
        achieved = corpus_stats([ExpertExample(output=output, task=source)])

        errors, notes = [], []
        for key, target in targets.items():
            got = achieved.get(key, 0.0)
            error = _profile_error(key, got, target)
            errors.append(error)
            if error > 0.12:
                notes.append(_profile_note(key, got, target))

        score = round(1.0 - sum(errors) / len(errors), 4) if errors else 0.0
        if not notes:
            return score, "Form matches this author on every measured feature."
        return score, "Form mismatches: " + " ".join(notes)

    return metric


_PROFILE_LABELS = {
    "words_per_answer": ("words", "{value:.0f}"),
    "sentences_per_answer": ("sentences", "{value:.0f}"),
    "paragraphs_per_answer": ("paragraphs", "{value:.0f}"),
    "bullet_line_ratio": ("share of lines bulleted", "{value:.0%}"),
}


def _profile_note(key: str, got: float, target: float) -> str:
    """위반 하나를 GEPA 가 읽을 문장으로 적는다.

    "어긋났다"가 아니라 **어느 방향으로 얼마나** 어긋났는지 적는다.
    방향이 없으면 최적화기가 어느 쪽으로 고쳐야 할지 모른다.
    """
    label, fmt = _PROFILE_LABELS[key]
    direction = "too many" if got > target else "too few"
    return (
        f"{direction} {label}: {fmt.format(value=got)} "
        f"against this author's {fmt.format(value=target)}."
    )


# 프롬프트가 학습 자료를 베꼈는지 볼 때 쓰는 n-gram 길이. 4 로 둔다 -
# 2~3 은 "in the oven" 같은 흔한 연결이 걸려서 아무 프롬프트나 높게
# 나오고, 5 이상은 살짝 바꿔 쓴 문구를 놓친다.
LEAKAGE_NGRAM = 4


def content_leakage(prompt: str, corpus: list[ExpertExample]) -> float:
    """프롬프트가 학습 자료에서 그대로 가져온 비율.

    **왜 재는가.** GEPA 가 찾아준 프롬프트에 학습 과제의 *내용*이 들어갔다 -
    suet(영국식 덤플링에 쓰는 신장 주변 지방)의 설명, 밀가루에 효모가
    있는지에 대한 해설 같은 것이 프롬프트 본문에 박혀 있었다. 그러면
    산출물이 문체 프롬프트가 아니라 문체 + 도메인 지식 프롬프트다.

    이 프로젝트는 "프롬프트로 되는 것은 전문가의 방식이고 지식은 아니다"를
    경계로 적어뒀다. GEPA 가 그 경계를 스스로 넘었는지를 눈대중이 아니라
    수치로 확인해야 한다(절대 규칙 6). LLM 에게 "내용이 섞였니"라고 묻는
    대신 겹침을 직접 센다.

    **무엇을 위협하는지 정확히 쓴다.** 도메인 지식이 섞여도 길이·문장·문단
    수는 바뀌지 않으므로 형식 거리 결과는 이것 때문에 흔들리지 않는다.
    위협받는 것은 (가) 산출물을 "문체 프롬프트"라고 부르는 주장과
    (나) 내용 지표(ROUGE-L)의 이득 해석이다.

    0 이면 베낀 4-gram 이 하나도 없고, 1 이면 전부 학습 자료에 있던 것이다.
    """
    prompt_grams = _word_ngrams(prompt, LEAKAGE_NGRAM)
    if not prompt_grams:
        return 0.0

    corpus_grams: set[tuple[str, ...]] = set()
    for example in corpus:
        corpus_grams |= set(_word_ngrams(example.output, LEAKAGE_NGRAM))
        if example.task:
            corpus_grams |= set(_word_ngrams(example.task, LEAKAGE_NGRAM))

    shared = sum(1 for gram in set(prompt_grams) if gram in corpus_grams)
    return round(shared / len(set(prompt_grams)), 4)


def topic_leakage(
    prompt: str,
    own_corpus: list[ExpertExample],
    foreign_corpus: list[ExpertExample],
) -> float:
    """프롬프트에 이 저자의 **주제 어휘**가 얼마나 들어왔는가.

    **왜 `content_leakage` 로는 부족한가.** 축자 겹침(4-gram)을 재보니
    GEPA 프롬프트는 0.000 이었다 - few-shot 은 0.959 로 나오므로 지표는
    작동한다. 즉 GEPA 는 학습 자료를 베낀 게 아니라 **자기 말로 다시
    썼다.** 그런데 프롬프트를 읽으면 suet(신장 주변 지방), 밀가루의 효모
    같은 도메인 내용이 분명히 들어 있다. 축자 지표로는 잡히지 않는
    혼입이다.

    그래서 어휘 수준으로 본다. 다만 "요리 단어 목록"을 손으로 만들면
    도메인마다 다시 만들어야 하고 자의적이다. 대신 **다른 도메인의
    코퍼스를 대조군으로 쓴다** - 이 저자의 자료에는 나오지만 무관한
    도메인 자료에는 안 나오는 단어가 곧 주제 어휘다. 목록이 필요 없고
    도메인을 안 가린다.

    0 이면 주제 어휘가 없는 순수 형식 프롬프트이고, 크면 그 반대다.
    절대값보다 조건 사이의 비교로 읽는다.
    """
    prompt_words = {w.lower() for w in _WORD.findall(prompt) if len(w) >= 4}
    if not prompt_words:
        return 0.0

    own = _vocabulary(own_corpus)
    foreign = _vocabulary(foreign_corpus)
    topic_words = own - foreign
    return round(len(prompt_words & topic_words) / len(prompt_words), 4)


def _vocabulary(corpus: list[ExpertExample]) -> set[str]:
    words: set[str] = set()
    for example in corpus:
        words |= {w.lower() for w in _WORD.findall(example.output) if len(w) >= 4}
        if example.task:
            words |= {w.lower() for w in _WORD.findall(example.task) if len(w) >= 4}
    return words


def _word_ngrams(text: str, n: int) -> list[tuple[str, ...]]:
    """소문자 단어 n-gram. 구두점은 떼고 본다 - 쉼표 하나 차이로 베낀
    문구를 못 잡으면 지표가 쓸모없어진다."""
    words = [w.lower() for w in _WORD.findall(text)]
    if len(words) < n:
        return []
    return [tuple(words[i : i + n]) for i in range(len(words) - n + 1)]


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

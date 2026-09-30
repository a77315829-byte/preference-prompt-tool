"""사용자가 가져온 임의의 프롬프트를 구조화된 피드백으로 다듬는다.

**왜 GEPA를 그대로 못 쓰는가.** GEPA는 프롬프트 텍스트 자체를 채점하지
않는다 - 그 프롬프트로 실제 과제 입력 몇 개를 돌려 나온 *결과물*을
채점한다(`optimize/run_gepa.py`). 사용자가 여기 가져오는 것은 "이 과제에
쓸 프롬프트"뿐이고, 무엇에 쓸지(과제 입력)와 무엇이 좋은 결과인지(채점
기준)가 없다. 그 둘을 사용자에게 요구하면 도메인 온보딩 에이전트를
다시 만드는 것과 같아진다 - 범위가 너무 커진다.

대신 **GEPA가 증명한 원리만 가져온다**: 구조화된 피드백이 막연한
피드백보다 낫다(`experiments/feedback_richness_ablation.py`, 같은 예산에서
0.98 대 0.44). 여기서는 GEPA의 반복 최적화 루프 대신, 프롬프트 자체의
구조를 코드로 점검하고 그 점검표를 근거로 LLM 이 한 번에 고쳐주는
가벼운 구조를 쓴다. 추가 입력 없이 프롬프트 텍스트 하나로 바로 동작한다.

**절대 규칙 6과의 관계.** "역할이 있나", "형식을 지정했나" 같은 구조적
표지는 코드(정규식)로 잰다. "이 문장이 모호한가", "지시가 서로
충돌하나" 같은 의미 판단은 코드로 잴 수 없어 LLM 에 맡긴다 - 이게
바로 규칙 6이 말하는 "최후 수단"에 해당하는 경우다.

**임계값에 대한 정직한 표시.** `domains/*.yaml`의 검사 임계값은 MACSum
실측 분포에 맞춰 보정됐다. 여기 체크리스트의 임계값(예: 12단어 미만이면
과소specification 의심)은 그런 보정을 거치지 않은 상식적 출발점이다.
실사용 데이터가 쌓이면 다시 잴 것 - 지금은 재지 않은 값이라고 표시해둔다.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache" / "polish"

# 서버(api_server.py)는 항상 자기 DEFAULT_MODEL 을 넘긴다. 이 값은 모듈을
# 직접 부를 때의 기본값이라 앱의 후보 생성 모델과 맞춘다.
DEFAULT_MODEL = "openai/gpt-4o-mini"

# engine/generator.py 와 같은 호출 상한.
REQUEST_TIMEOUT_SECONDS = 60
MAX_OUTPUT_TOKENS = 2048

SEPARATOR = "---다듬은 프롬프트---"


def completion(**kwargs):
    """litellm 을 호출 시점에 불러온다. import 에만 11초가 걸려서, 모듈
    최상단에서 부르면 API 서버 시작이 그만큼 늦어진다. 테스트는 이 이름을
    바꿔 끼운다."""
    from litellm import completion as _completion

    return _completion(**kwargs)

# 실측하지 않은 상식적 임계값이다 (위 docstring 참고). 프롬프트가 대체로
# 한두 문장이면 무엇을, 어떤 형식으로, 얼마나 원하는지가 빠졌을 가능성이
# 높다고 보고 12단어를 시작점으로 뒀다.
MIN_WORDS_BEFORE_UNDERSPECIFIED = 12

# 어떤 종류든 짧게 쓰라는 신호만으로도 방향은 맞는다는 게 전문가 경로
# 실험(보너스 5)의 관찰이었다 - 여기서는 반대로, 구체성 없는 낱말이
# 많으면 과제가 아니라 느낌만 적었다는 신호로 쓴다.
VAGUE_WORDS = ("적당히", "알아서", "좋게", "잘", "적절히", "센스있게")

_ROLE_MARKERS = re.compile(r"너는|당신은|역할은|as a\b|you are a\b", re.IGNORECASE)
_FORMAT_MARKERS = re.compile(
    r"형식|포맷|목록으로|표로|json|마크다운|번호를 매겨|글머리", re.IGNORECASE
)
_CONSTRAINT_MARKERS = re.compile(
    r"지\s*마(라|세요)?\b|금지|피하|avoid\b|do not\b|"
    r"\d+\s*(단어|문장|자|글자|줄)\s*(이내|이하|미만|이상|정도)",
    re.IGNORECASE,
)
_EXAMPLE_MARKERS = re.compile(r"예\s*[:：]|예시|example|e\.g\.", re.IGNORECASE)


@dataclass
class CheckResult:
    name: str
    passed: bool
    note: str


@dataclass
class PolishResult:
    checklist: list[CheckResult]
    suggestions: str
    revised_prompt: str


def _word_count(text: str) -> int:
    return len(text.split())


def check_length(prompt: str) -> CheckResult:
    n = _word_count(prompt)
    if n < MIN_WORDS_BEFORE_UNDERSPECIFIED:
        return CheckResult(
            "분량", False,
            f"{n}단어로 짧다 - 과제·형식·분량 중 빠진 게 있을 수 있다.",
        )
    return CheckResult("분량", True, f"{n}단어.")


def check_role(prompt: str) -> CheckResult:
    if _ROLE_MARKERS.search(prompt):
        return CheckResult("역할 지정", True, "역할/청자를 지정하는 표현이 있다.")
    return CheckResult("역할 지정", False, "누구에게 어떤 역할로 답해야 하는지가 없다.")


def check_format(prompt: str) -> CheckResult:
    if _FORMAT_MARKERS.search(prompt):
        return CheckResult("출력 형식", True, "출력 형식을 지정하는 표현이 있다.")
    return CheckResult("출력 형식", False, "결과를 어떤 형태로 받고 싶은지가 없다.")


def check_constraints(prompt: str) -> CheckResult:
    if _CONSTRAINT_MARKERS.search(prompt):
        return CheckResult("제약 조건", True, "분량·금지 사항 등 제약이 있다.")
    return CheckResult("제약 조건", False, "분량이나 하지 말아야 할 것에 대한 제약이 없다.")


def check_examples(prompt: str) -> CheckResult:
    if _EXAMPLE_MARKERS.search(prompt):
        return CheckResult("예시", True, "예시를 보여주는 표현이 있다.")
    return CheckResult("예시", False, "원하는 결과의 예시가 없다 - 있으면 모호함이 크게 줄어든다.")


def check_vague_words(prompt: str) -> CheckResult:
    found = [w for w in VAGUE_WORDS if w in prompt]
    if found:
        return CheckResult(
            "모호한 표현", False,
            f"구체성 없는 표현이 있다: {', '.join(found)}. 무엇을 원하는지 수치나 예시로 바꿀 수 있다.",
        )
    return CheckResult("모호한 표현", True, "모호한 표현이 눈에 띄지 않는다.")


CHECKS = (check_length, check_role, check_format, check_constraints,
          check_examples, check_vague_words)


def checklist(prompt: str) -> list[CheckResult]:
    return [fn(prompt) for fn in CHECKS]


def _feedback_block(results: list[CheckResult]) -> str:
    """metric_builder 가 GEPA 에 주는 것과 같은 모양 - 통과/위반을 항목별로
    나열한다. 통과 항목도 같이 보여줘야 LLM 이 이미 있는 것까지 새로
    지어내지 않는다."""
    lines = []
    for r in results:
        mark = "충족" if r.passed else "미흡"
        lines.append(f"- [{mark}] {r.name}: {r.note}")
    return "\n".join(lines)


_REFLECTION_INSTRUCTIONS = """\
아래는 사용자가 실제로 쓰려는 프롬프트와, 구조를 기계적으로 점검한 결과다.

원래 프롬프트:
---
{prompt}
---

구조 점검 결과:
{feedback}

다음 두 가지를 한다.

1. "미흡"으로 표시된 항목만, 이 프롬프트에서 구체적으로 무엇이 왜 문제인지
   한두 문장씩 설명한다. "충족"인 항목은 언급하지 않는다.
2. 아래 다섯 절 틀로 다시 쓴 프롬프트를 제시한다. 원래 프롬프트의 의도는
   그대로 유지하고, 빠진 절은 사용자가 나중에 채울 수 있게 "[ ]" 로 표시한
   빈 자리를 남긴다. 이미 있는 내용을 지어내서 채우지 않는다.

[역할]
[목표]
[형식]
[제약]
[예시]

"미흡 항목 설명" 다음 "---다듬은 프롬프트---" 구분선 다음 다섯 절 프롬프트,
이 순서로만 답한다. 다른 말은 덧붙이지 않는다.
"""


def _cache_path(message: str, model: str) -> Path:
    # 사용자 프롬프트가 아니라 모델에 실제로 보내는 전체 문장으로 키를 만든다.
    # 지시문(_REFLECTION_INSTRUCTIONS)이나 점검 항목을 고쳐도 옛 응답이
    # 나오지 않게 - generator.py 가 8주차에 같은 이유로 바꾼 것과 같다.
    payload = json.dumps({"message": message, "model": model}, sort_keys=True)
    key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{key}.json"


def polish(prompt: str, model: str = DEFAULT_MODEL) -> PolishResult:
    """체크리스트를 코드로 재고, 그 결과를 근거로 LLM 이 설명과 재작성본을
    낸다. 같은 (프롬프트, 모델)은 다시 호출하지 않는다 (절대 규칙 2)."""
    results = checklist(prompt)
    feedback = _feedback_block(results)

    message = _REFLECTION_INSTRUCTIONS.format(prompt=prompt, feedback=feedback)
    cache_file = _cache_path(message, model)
    if cache_file.exists():
        raw = json.loads(cache_file.read_text(encoding="utf-8"))["response"]
    else:
        response = completion(
            model=model,
            messages=[{"role": "user", "content": message}],
            timeout=REQUEST_TIMEOUT_SECONDS,
            max_tokens=MAX_OUTPUT_TOKENS,
        )
        raw = response.choices[0].message.content
        if not (raw or "").strip():
            raise ValueError("모델이 빈 응답을 반환했다.")
        # 구분선이 없으면 다듬은 프롬프트를 가를 수 없다. 빈 결과를 캐시에
        # 굳히면 같은 입력은 다시 시도해도 계속 빈 결과가 나온다.
        if SEPARATOR not in raw:
            raise ValueError("모델 응답에 다듬은 프롬프트 구분선이 없다. 다시 시도해 주세요.")
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = cache_file.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps({"prompt": prompt, "response": raw}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        tmp.replace(cache_file)

    suggestions, _, revised = raw.partition(SEPARATOR)
    return PolishResult(
        checklist=results,
        suggestions=suggestions.strip(),
        revised_prompt=revised.strip(),
    )

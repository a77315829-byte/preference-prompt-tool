"""직접 고른 개발 환경·선호로 재사용할 지침을 조립한다. 모델·코드는 실행하지 않는다."""
from __future__ import annotations

from coding_examples import SNIPPETS
from coding_framework_examples import framework_example_source
from coding_elicitation import validate_elicitation

PREFERENCES = {
    "explanation": {
        "brief": "코드를 먼저 제시하고 핵심 이유와 사용 방법만 간결하게 설명하라.",
        "steps": "해결 과정을 단계별로 설명하고 주요 선택의 이유와 사용 방법을 덧붙여라.",
    },
    "comments": {
        "essential": "주석은 의도나 주의점을 알아야 하는 곳에만 작성하고 코드 그대로의 설명은 반복하지 마라.",
        "detailed": "핵심 로직과 주의할 부분에 이해를 돕는 주석을 작성하라. 명백한 문법 설명은 반복하지 마라.",
    },
    "structure": {
        "compact": "작은 작업은 불필요한 추상화와 파일 분리를 줄여 간결하게 구성하라. 언어·프레임워크의 필수 구조는 지켜라.",
        "modular": "역할에 따라 함수·모듈·파일을 나누되 요청 규모에 맞게 구성하고 불필요한 계층은 만들지 마라.",
    },
    "output": {
        "complete": "필요한 파일 이름과 전체 코드를 제시하고 실행에 필요한 부분을 생략하지 마라.",
        "changes": "기존 코드가 주어지면 바뀐 부분과 적용 위치를 중심으로 제시하라. 새 구현이라면 필요한 전체 코드를 제시하라.",
    },
}


def _text(value, label: str, limit: int, required: bool = False, single_line: bool = False) -> str:
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f"{label}은(는) {'1' if required else '0'}~{limit}자로 적어 주세요.")
    value = value.strip()
    if single_line and any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f"{label}은(는) 줄바꿈 없이 적어 주세요.")
    return value


def build_coding_instructions(raw: dict) -> dict:
    if not isinstance(raw, dict) or not isinstance(raw.get("preferences"), dict):
        raise ValueError("개발 환경과 작성 선호를 먼저 골라 주세요.")
    language = _text(raw.get("language"), "개발 언어", 60, True, True)
    framework = _text(raw.get("framework", ""), "프레임워크", 100, single_line=True)
    extra = _text(raw.get("extra", ""), "추가 선호", 1000)
    choices = raw["preferences"]
    if set(choices) != set(PREFERENCES) or any(not isinstance(choices[k], str) or choices[k] not in opts for k, opts in PREFERENCES.items()):
        raise ValueError("설명·주석·코드 구성·출력 방식의 선호를 확인해 주세요.")
    profile = {"language": language, "framework": framework, "preferences": dict(choices), "extra": extra}
    comparison = raw.get("comparison")
    if comparison is not None:
        if (not isinstance(comparison, dict) or type(comparison.get("version")) is not int
                or comparison["version"] not in (1, 2, 3) or language not in SNIPPETS
                or not isinstance(comparison.get("choices"), dict)
                or set(comparison["choices"]) != set(PREFERENCES)):
            raise ValueError("예시 비교 기록을 확인한 뒤 지침을 다시 만들어 주세요.")
        for key, options in PREFERENCES.items():
            pick = comparison["choices"][key]
            if pick is not None and (not isinstance(pick, str) or pick not in options or pick != choices[key]):
                raise ValueError("비교에서 고른 방식과 현재 설정이 다릅니다. 다시 비교하거나 직접 설정해 주세요.")
        profile["comparison"] = {"version": comparison["version"], "choices": dict(comparison["choices"])}
        if comparison['version'] == 3:
            profile['comparison'] = validate_elicitation(comparison, profile)
        if comparison["version"] == 2:
            source = framework_example_source(language, framework)
            recorded = comparison.get("example")
            if (source is None or not isinstance(recorded, dict) or recorded.get("id") != source["id"]
                    or recorded.get("kind") != "framework"):
                raise ValueError("비교한 프레임워크와 현재 설정이 다릅니다. 다시 비교해 주세요.")
            profile["comparison"]["example"] = source
    preference_heading = ("## 예시 비교에서 정한 내 작성 선호\n"
                          "네 가지 항목의 예시를 보고 고른 방식이다. 판단을 보류한 항목은 직접 설정한 값을 유지했다.\n"
                          if comparison is not None else
                          "## 직접 고른 내 작성 선호\n아래는 사용자가 직접 정한 선호이며 예시 비교로 추정한 결과가 아니다.\n")
    if comparison is not None and comparison['version'] == 3:
        count = len(profile['comparison']['rounds'])
        preference_heading = (f"## 비교와 직접 확인으로 정한 내 작성 선호\n"
                              f"준비된 예시 {count}회에서 반복 선택을 확인했다. 일관되지 않거나 보류한 항목은 사용자가 직접 정했다. "
                              "이는 제한된 예시의 선호이며 기능 정확도나 다른 과제에서의 만족도가 검증된 것은 아니다.\n")
    if comparison is not None and comparison["version"] in (2, 3):
        preference_heading += f"비교 예시: {profile['comparison']['example']['label']}\n"
    environment = f"개발 언어: {language}\n프레임워크·라이브러리: {framework or '별도 지정 없음 - 임의로 추가하지 말고 필요하면 먼저 확인하라.'}"
    preferences = "\n".join(f"- {opts[choices[key]]}" for key, opts in PREFERENCES.items())
    prompt = (
        "당신은 사용자가 지정한 개발 환경과 작성 선호에 맞춰 개발을 돕는 페어 프로그래머다.\n\n"
        f"## 개발 환경\n{environment}\n\n"
        f"{preference_heading}"
        f"{preferences}\n"
        + (f"\n## 추가 선호\n{extra}\n" if extra else "")
        + "\n## 항상 지킬 것\n"
        "- 새 개발 요청의 기능과 제약을 우선하라. 작성 선호 때문에 필요한 기능을 빼지 마라.\n"
        "- 지정한 언어·프레임워크의 문법과 관례를 따르고 다른 개발 환경의 규칙을 임의로 섞지 마라.\n"
        "- 버전이나 필요한 정보가 없고 구현에 영향을 주면 확인할 질문을 하거나 가정을 명시하라.\n"
        "- 요청하지 않은 라이브러리와 기능을 임의로 추가하지 마라.\n"
        "- 실행·테스트한 사실이 없으면 통과했다고 쓰지 말고 확인할 방법을 제시하라."
    )
    return {"profile": profile, "prompt": prompt}

"""MACSum 속성 조합을 페르소나로 삼아, 두 후보 중 페르소나의 진짜 축값에
더 부합하는 쪽을 고르는 선택 대행. 사람 없이 선택 루프 실험을 돌리기
위한 도구다.

engine/ 과 달리 이 모듈은 MACSum을 알아도 된다 - 실험 도구이지 엔진이 아니다.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from engine.domain_loader import Domain


@dataclass
class Persona:
    """MACSum 속성 조합 하나 = 페르소나 하나. 그 조합의 사람 작성 요약이 답안지."""

    combo: dict[str, str]
    reference_summary: str


def load_personas(macsum_record: dict) -> list[Persona]:
    """MACSum 레코드 하나(원문 1개)에 달린 references를 페르소나 목록으로 변환한다."""
    return [
        Persona(combo=dict(ref["control_attribute"]), reference_summary=ref["summary"])
        for ref in macsum_record["references"]
    ]


def choose(domain: Domain, persona: Persona, candidate_a: str, candidate_b: str, source: str) -> str:
    """페르소나의 실제 축값에 대해 checks/*.py의 검사 함수를 두 후보에 각각
    적용해, 총점이 더 높은 쪽을 고른다.

    9주차 발견: 정답 요약과의 단어 겹침으로 판단했더니, "fully"(원문 그대로
    발췌) 후보가 원문 고유명사를 그대로 가져와 정답 요약과 우연히 어휘가
    더 겹쳐버려 엉뚱한 축으로 수렴하는 문제가 있었다 (내용 겹침과 문체
    겹침을 구분 못 함). checks/summarization.py는 6주차에 실제 MACSum
    데이터로 판별력을 검증해뒀으므로, 정답 요약 텍스트 대신 이걸로
    "페르소나의 축값에 더 부합하는 구조인가"를 직접 재는 쪽이 더 낫다.
    """
    checks_module = importlib.import_module(domain.checks_module)
    score_a = score_b = 0.0

    for axis in domain.axes:
        if axis.type != "enum" or axis.name not in persona.combo:
            continue
        value = persona.combo[axis.name]
        check_spec = axis.check_for(value)
        check_fn = getattr(checks_module, check_spec.fn)
        s_a, _ = check_fn(candidate_a, source, value, check_spec.target)
        s_b, _ = check_fn(candidate_b, source, value, check_spec.target)
        score_a += s_a
        score_b += s_b

    return "a" if score_a >= score_b else "b"

"""MACSum 속성 조합을 페르소나로 삼아, 두 후보 중 정답 요약에 더 가까운
쪽을 고르는 선택 대행. 사람 없이 선택 루프 실험을 돌리기 위한 도구다.

engine/ 과 달리 이 모듈은 MACSum을 알아도 된다 - 실험 도구이지 엔진이 아니다.
"""

from __future__ import annotations

from dataclasses import dataclass


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


def _word_overlap(a: str, b: str) -> float:
    """단어 집합의 F1(Dice 계수: 2*교집합/(|A|+|B|)). LLM 판정 없이 코드로
    재현 가능하게 재는 쪽을 우선한다.

    자카드(교집합/합집합) 대신 이걸 쓰는 이유: 자카드는 두 텍스트 길이가
    다르면 합집합이 커져 점수가 낮아지는 구조적 편향이 있었다 (8주차
    점검에서 발견 - 페르소나가 명백히 더 가까운 후보 대신 우연히 길이가
    비슷한 후보를 고르는 오류). Dice는 두 집합 크기를 합으로 정규화해
    이 편향이 훨씬 덜하다.
    """
    words_a, words_b = set(a.lower().split()), set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    return 2 * len(words_a & words_b) / (len(words_a) + len(words_b))


def choose(persona: Persona, candidate_a: str, candidate_b: str) -> str:
    """정답 요약과의 어휘 겹침이 더 높은 후보를 고른다. "a" 또는 "b"를 반환."""
    score_a = _word_overlap(persona.reference_summary, candidate_a)
    score_b = _word_overlap(persona.reference_summary, candidate_b)
    return "a" if score_a >= score_b else "b"

"""독립 채점자 - 최적화(GEPA)에 쓰인 checks/*.py 와 무관한 지표로
비교군 A/B/D 결과물을 다시 채점한다.

목적: compare_baselines.py의 D는 checks/ 기반 metric으로 최적화된
프롬프트의 결과물을, 같은 checks/ 함수로 채점한다. A/B는 그 최적화를
받지 않았으니 D가 이기는 게 부분적으로 보장돼 있다는 지적(순환 논증)을
피하려면, 최적화에 전혀 관여하지 않은 지표가 최소 하나 있어야 한다.

여기서는 ROUGE-L(최장공통부분수열 기반, checks/의 bigram Dice와는 다른
알고리즘)로 MACSum 사람 작성 정답 요약(persona.reference_summary)과
직접 비교한다. reference_summary는 이 프로젝트 어디의 최적화 루프에도
쓰이지 않는다 (9주차에 persona.choose()가 checks/ 기반으로 바뀐 뒤로는
읽히기만 하고 아무 데도 안 쓰이고 있었다).
"""

from __future__ import annotations

from rouge_score import rouge_scorer

_scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)


def rouge_l_score(output: str, reference_summary: str) -> float:
    return _scorer.score(reference_summary, output)["rougeL"].fmeasure

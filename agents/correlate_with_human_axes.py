"""에이전트가 찾은 축이 "다른 걸 찾은 실패"인지 "같은 걸 다른 이름으로
찾은 성공"인지 구분한다.

이름(conciseness vs length)이 달라도, 실제 측정값이 사람이 만든 축의
측정값과 강하게 상관되면 기능적으로 같은 축이다. agents/
evaluate_domain_onboarding.py 로 만든 macsum_eval_agent 결과물과 사람이
만든 summarization.yaml 축의 원시 측정값을 같은 텍스트 집합에 돌려
피어슨 상관을 잰다.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import checks.macsum_eval_agent as agent_checks
import checks.summarization as human_checks

HUMAN_MEASURES = {
    "length(sentence_count)": lambda text, source: len(human_checks._sentences(text)),
    "extractiveness(bigram_overlap)": lambda text, source: (
        len(human_checks._bigrams(human_checks._words(text)) & human_checks._bigrams(human_checks._words(source)))
        / len(human_checks._bigrams(human_checks._words(text)))
        if human_checks._bigrams(human_checks._words(text))
        else 0.0
    ),
}

AGENT_MEASURES = {
    "conciseness": agent_checks.measure_conciseness,
    "formality": agent_checks.measure_formality,
    "sentence_complexity": agent_checks.measure_sentence_complexity,
    "focus_on_entities": agent_checks.measure_focus_on_entities,
}


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
    sx = statistics.pstdev(xs)
    sy = statistics.pstdev(ys)
    if sx == 0 or sy == 0:
        return 0.0
    return cov / (sx * sy)


def load_texts(path: str, n_docs: int = 6) -> list[tuple[str, str]]:
    """(output, source) 쌍 목록 - evaluate_domain_onboarding.py와 같은 문서 선택 로직."""
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    pairs = []
    used_docs = 0
    for record in records:
        summaries = [ref["summary"] for ref in record["references"]]
        if len(summaries) >= 3:
            source = " ".join(record["source"])
            pairs.extend((summary, source) for summary in summaries)
            used_docs += 1
        if used_docs >= n_docs:
            break
    return pairs


def main() -> None:
    pairs = load_texts("data/macsum/dataset/macdoc/val.json")
    print(f"텍스트 {len(pairs)}개로 상관 계산")

    human_values = {name: [fn(text, source) for text, source in pairs] for name, fn in HUMAN_MEASURES.items()}
    agent_values = {name: [fn(text, source) for text, source in pairs] for name, fn in AGENT_MEASURES.items()}

    print(f"\n{'':30s}" + "".join(f"{a:>22s}" for a in AGENT_MEASURES))
    best_match = {}
    for h_name, h_vals in human_values.items():
        row = []
        for a_name, a_vals in agent_values.items():
            r = pearson(h_vals, a_vals)
            row.append(r)
        best_idx = max(range(len(row)), key=lambda i: abs(row[i]))
        best_match[h_name] = (list(agent_values.keys())[best_idx], row[best_idx])
        print(f"{h_name:30s}" + "".join(f"{r:>22.3f}" for r in row))

    print("\n=== 판정 (|r| >= 0.7 이면 기능적으로 같은 축으로 본다) ===")
    for h_name, (a_name, r) in best_match.items():
        verdict = "같은 축(다른 이름)" if abs(r) >= 0.7 else "다른 축"
        print(f"{h_name} <-> {a_name}: r={r:.3f} [{verdict}]")


if __name__ == "__main__":
    main()

"""4단계 관문: 원문 길이로 계산한 단어 수 지시를 모델이 따르는가.

    python -m experiments.length_v3_compliance

docs/length_v2_preregistration.md 4단계에 실행 전에 적은 기준: 30쌍의 학습 문서 12개 x
길이 값 3개 = 36회 생성으로 출력의 원문 대비 비율 중앙값을 재서, 세 값 모두 사람 중앙값
(5.3 / 10.3 / 15.4%)에서 ±3%p 안이고 순서가 맞아야 30쌍을 돌린다.

비교를 위해 v1(문장 수 지시)과 v2(비율 지시)도 같은 문서로 잰다. 둘 다 캐시에 있다.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import litellm
from dotenv import load_dotenv

from engine.domain_loader import load_domain
from engine.generator import generate
from experiments.heldout_comparison import MODEL, Spend, length_ratio, pick_personas

load_dotenv()

N_DOCS = 12
HUMAN = {"short": 0.053, "normal": 0.103, "long": 0.154}
TOLERANCE = 0.03
DOMAINS = {"v1": "domains/summarization.yaml", "v2": "domains/summarization_v2.yaml",
           "v3": "domains/summarization_v3.yaml"}
OUT = Path("experiments/results/length_v3_compliance.json")


def main() -> int:
    spend = Spend()
    litellm.success_callback = [spend]
    docs = [p["learn_source"] for p in pick_personas(30)[:N_DOCS]]
    result: dict = {"n_docs": N_DOCS, "human_median": HUMAN, "tolerance": TOLERANCE, "median_ratio": {}}
    for name, path in DOMAINS.items():
        domain = load_domain(path)
        ratios = {v: [] for v in HUMAN}
        for source in docs:
            for value in HUMAN:
                out = generate(domain, source, {"length": value, "extractiveness": "normal", "topic": ""}, MODEL)
                ratios[value].append(length_ratio(out, source))
        result["median_ratio"][name] = {v: round(statistics.median(r), 4) for v, r in ratios.items()}

    v3 = result["median_ratio"]["v3"]
    within = all(abs(v3[v] - HUMAN[v]) <= TOLERANCE for v in HUMAN)
    ordered = v3["short"] < v3["normal"] < v3["long"]
    result["gate"] = {"within_tolerance": within, "ordered": ordered, "passed": within and ordered}
    result["spend_dollars"] = round(spend.dollars, 4)
    result["model_calls"] = spend.calls
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

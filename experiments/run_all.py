"""9~10주차: 알고리즘 3종(무작위/순차/불확실도) x 여러 페르소나 x 여러
시드로 선택 루프를 실제로 돌려 수렴 곡선 데이터를 모은다.

문서당 (length, extractiveness) 조합은 최대 9개뿐이라 generator.py의
캐싱 덕분에 시드/알고리즘을 늘려도 문서당 실제 API 호출은 최대 9번으로
제한된다."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from engine.domain_loader import Domain, load_domain
from engine.estimator import Comparison, Estimator
from engine.generator import generate
from engine.selector import RandomSelector, SequentialAxisSelector, UncertaintySelector
from experiments.persona import Persona, choose, load_personas

load_dotenv()

MODEL = "openai/gpt-4.1-mini"
N_DOCS = 5
N_SEEDS = 5
N_ROUNDS = 10

ALGORITHMS = {
    "random": RandomSelector,
    "sequential": SequentialAxisSelector,
    "uncertainty": UncertaintySelector,
}


def pick_documents_with_personas(path: str, n: int) -> list[tuple[str, Persona]]:
    """topic이 빈("") 페르소나가 하나라도 있는 문서를 n개 고른다.
    가능하면 문서마다 다른 (length, extractiveness) 조합을 고른다 - 안 그러면
    데이터셋 삽입 순서상 항상 같은 조합(short, normal)만 뽑히는 문제가 있었다."""
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    picked: list[tuple[str, Persona]] = []
    used_combos: set[tuple[str, str]] = set()

    for rec in records:
        candidates = [p for p in load_personas(rec) if p.combo.get("topic", "") == ""]
        if not candidates:
            continue
        source = " ".join(rec["source"])

        fresh = [p for p in candidates if (p.combo["length"], p.combo["extractiveness"]) not in used_combos]
        persona = fresh[0] if fresh else candidates[0]

        used_combos.add((persona.combo["length"], persona.combo["extractiveness"]))
        picked.append((source, persona))
        if len(picked) >= n:
            break

    return picked


def run_one(domain: Domain, selector_cls, source: str, persona: Persona, seed: int, n_rounds: int) -> list[dict]:
    estimator = Estimator(domain)
    selector = selector_cls(domain, seed=seed)
    hidden = {"length": persona.combo["length"], "extractiveness": persona.combo["extractiveness"]}

    rows = []
    for round_idx in range(1, n_rounds + 1):
        combo_a, combo_b = selector.next_pair(estimator)
        candidate_a = generate(domain, source, combo_a, model=MODEL)
        candidate_b = generate(domain, source, combo_b, model=MODEL)
        winner = choose(domain, persona, candidate_a, candidate_b, source)
        estimator.update(Comparison(combo_a, combo_b, winner))

        restored = sum(
            1 for name in estimator.enum_axis_names() if estimator.preferred_value(name) == hidden[name]
        )
        rows.append({"round": round_idx, "restored": restored})
    return rows


def main() -> None:
    domain = load_domain("domains/summarization.yaml")
    documents = pick_documents_with_personas("data/macsum/dataset/macdoc/val.json", N_DOCS)
    n_axes = len(Estimator(domain).enum_axis_names())

    records = []
    for doc_idx, (source, persona) in enumerate(documents):
        for algo_name, selector_cls in ALGORITHMS.items():
            for seed in range(N_SEEDS):
                rows = run_one(domain, selector_cls, source, persona, seed, N_ROUNDS)
                for row in rows:
                    records.append(
                        {
                            "doc": doc_idx,
                            "algorithm": algo_name,
                            "seed": seed,
                            "round": row["round"],
                            "restored": row["restored"],
                            "n_axes": n_axes,
                        }
                    )
                print(f"doc={doc_idx} algo={algo_name} seed={seed} done")

    df = pd.DataFrame(records)
    out_path = Path("experiments/results/results.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"saved {len(df)} rows to {out_path}")


if __name__ == "__main__":
    main()

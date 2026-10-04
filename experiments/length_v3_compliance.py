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
from experiments.result_files import prepare_run, write_json, finish_run
from experiments.result_statistics import HUMAN, TOLERANCE, N_DOCS, evaluate_gate

load_dotenv()

DOMAINS = {"v1": "domains/summarization.yaml", "v2": "domains/summarization_v2.yaml",
           "v3": "domains/summarization_v3.yaml"}
OUT = Path("experiments/results/length_v3_compliance.json")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=MODEL, help="예: ollama/qwen2.5:7b")
    parser.add_argument("--output-dir", type=Path, help="기본: 실행마다 새 runs/ 폴더")
    parser.add_argument("--overwrite", action="store_true", help="명시한 출력 위치의 기존 실행을 교체")
    args = parser.parse_args()
    model = args.model
    stem = OUT.stem if model == MODEL else f"length_v3_compliance_{model.split('/')[-1].replace(':', '-')}"
    try:
        paths, manifest = prepare_run(stem, (".json",), output_dir=args.output_dir,
                                      overwrite=args.overwrite, metadata={"model": model, "requested_n_docs": N_DOCS})
    except (FileExistsError, ValueError) as exc:
        parser.error(str(exc))
    out = paths[".json"]
    spend = Spend()
    previous_callbacks = litellm.success_callback
    litellm.success_callback = [spend]
    try:
        result = _run(model, spend)
        write_json(out, result)
        finish_run(manifest, "completed", spend_dollars=result["spend_dollars"], model_calls=result["model_calls"])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print(f"결과: {out}")
        return 0
    except BaseException as exc:
        finish_run(manifest, "failed", error_type=type(exc).__name__,
                   spend_dollars=round(spend.dollars, 4), model_calls=spend.calls)
        raise
    finally:
        litellm.success_callback = previous_callbacks


def _run(model, spend) -> dict:
    personas = pick_personas(30)[:N_DOCS]
    docs = [p["learn_source"] for p in personas]
    if len(docs) != N_DOCS:
        raise ValueError(f"관문에는 학습 문서 {N_DOCS}개가 필요하다")
    result: dict = {"model": model, "n_docs": len(docs), "human_median": HUMAN,
                    "tolerance": TOLERANCE, "median_ratio": {}, "ratio_samples": {},
                    "learn_docs": [p["learn_doc"] for p in personas]}
    for name, path in DOMAINS.items():
        domain = load_domain(path)
        ratios = {v: [] for v in HUMAN}
        for source in docs:
            for value in HUMAN:
                text = generate(domain, source, {"length": value, "extractiveness": "normal", "topic": ""}, model)
                ratios[value].append(length_ratio(text, source))
        result["median_ratio"][name] = {v: round(statistics.median(r), 4) for v, r in ratios.items()}
        result["ratio_samples"][name] = ratios

    v3 = result["median_ratio"]["v3"]
    result["gate"] = evaluate_gate(v3, HUMAN, TOLERANCE)
    result["spend_dollars"] = round(spend.dollars, 4)
    result["model_calls"] = spend.calls
    return result


if __name__ == "__main__":
    raise SystemExit(main())

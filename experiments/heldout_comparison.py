"""선호를 배운 문서와 채점하는 문서를 나눈 비교 실험 (계획서 1-3, 1-7).

기존 A/B/D 와 강한 비교군 실험(5문서)의 한계 셋을 한 번에 다룬다.
1. 선호를 배운 문서와 채점한 문서가 같았다 -> 페르소나마다 학습 문서 X 와
   채점 문서 Y 를 다르게 둔다. D 는 X 에서 8회 선택으로 배운 프롬프트를 Y 에
   적용한다.
2. n=5 였다 -> 기본 30 페르소나, 페어드 부호검정.
3. 표본의 조건 범위를 명시한다. topic 없는 MACSum 사례의 추출성 정답은
   모두 normal 이므로 high/fully의 선호 복원까지 검증한 실험은 아니다.

데이터는 MACSum **test** 분할이다. 검사 함수의 임계값은 train+val 분포로
보정했으므로 한 번도 쓰지 않은 분할로 채점한다.

모델은 앱의 후보 생성 모델(gpt-4o-mini)이다. 기존 실험(gpt-4.1-mini)과
수치를 섞지 않는다. 온도는 기존 실험처럼 지정하지 않는다.

비용: 실제 청구 비용(litellm 의 response_cost)을 더하다가 --cap 달러에 닿으면
다음 페르소나로 넘어가지 않고 멈춘다. 결과는 페르소나마다 바로 저장한다.

    python -m experiments.heldout_comparison --n 2      # 새 실행 폴더에 저장
    python -m experiments.heldout_comparison --n 30     # 본 실험 (캐시 재사용)
    python -m experiments.heldout_comparison --domain domains/summarization_v2.yaml

기본 결과는 experiments/results/runs/의 새 실행 폴더에 저장한다. --output-dir로
위치를 지정할 수 있지만 기존 결과는 --overwrite 없이 교체하지 않는다.
동점 처리 기본은 과거 실험의 legacy-a이며 record-tie는 별도 후속 실험이다.
모델 호출 전에 출력 충돌을 확인한다. A/B/B+ 생성 결과는 캐시를 재사용한다.
"""

from __future__ import annotations

import argparse
import json
import hashlib
import math
import random
import threading
from collections import defaultdict
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from checks.summarization import _words
from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator
from engine.generator import generate
from engine.selector import UncertaintySelector
from experiments.compare_baselines import CONDITION_A_PROMPT, CONDITION_B_PROMPT, generate_raw, score_against_combo
from experiments.result_statistics import (sign_test_p, summarize, CONDITIONS, COMPARISONS,
                                          FAIR_BPLUS, FAIR_COMPARISONS)
from experiments.independent_grader import rouge_l_score
from experiments.persona import Persona, choose, comparison_scores
from experiments.result_files import prepare_run, write_csv, write_json, finish_run
from experiments.strong_baseline_comparison import build_strong_direct_prompt
from optimize.run_gepa import build_seed_prompt

load_dotenv()

MODEL = "openai/gpt-4o-mini"
N_ROUNDS = 8
SPLIT = Path("data/macsum/dataset/macdoc/test.json")
SEED = 0
DEFAULT_DOMAIN = "domains/summarization.yaml"
OUT_CSV = Path("experiments/results/heldout_comparison.csv")
OUT_JSON = Path("experiments/results/heldout_comparison.json")
# 5단계 (docs/length_v2_preregistration.md): B+ 에도 D(v3) 와 같은 방식의 단어 수를 준다.
# 비율은 v3 와 같은 topic 없는 사람 요약의 train 중앙값.
FAIR_BPLUS_RATIOS = {"short": 0.053, "normal": 0.103, "long": 0.154}


class Spend:
    """litellm 콜백으로 실제 청구 비용을 더한다. 캐시에 있던 응답은 호출이
    없으므로 0 이다."""

    def __init__(self) -> None:
        self.dollars = 0.0
        self.calls = 0
        self._lock = threading.Lock()

    def __call__(self, kwargs, completion_response, start_time, end_time) -> None:
        with self._lock:
            self.dollars += float(kwargs.get("response_cost") or 0.0)
            self.calls += 1


def pick_personas(n: int) -> list[dict]:
    """(length, extractiveness) 조합을 돌아가며, 조합마다 학습 문서 X 와 채점
    문서 Y 를 서로 다르게 고른다. 한 문서는 한 번만 쓴다 (X 로든 Y 로든)."""
    records = json.loads(SPLIT.read_text(encoding="utf-8"))
    by_combo: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)
    for idx, rec in enumerate(records):
        for ref in rec["references"]:
            attr = ref["control_attribute"]
            if attr.get("topic", "") == "":
                by_combo[(attr["length"], attr["extractiveness"])].append((idx, ref["summary"]))
    rng = random.Random(SEED)
    for docs in by_combo.values():
        rng.shuffle(docs)
    combos = sorted(c for c, docs in by_combo.items() if len(docs) >= 2)

    used: set[int] = set()
    personas: list[dict] = []
    while len(personas) < n:
        progressed = False
        for combo in combos:
            if len(personas) >= n:
                break
            free = [(i, s) for i, s in by_combo[combo] if i not in used]
            if len(free) < 2:
                continue
            (x, x_ref), (y, y_ref) = free[0], free[1]
            used.update((x, y))
            personas.append({
                "combo": {"length": combo[0], "extractiveness": combo[1]},
                "learn_doc": x,
                "learn_source": " ".join(records[x]["source"]),
                "learn_reference": x_ref,
                "eval_doc": y,
                "eval_source": " ".join(records[y]["source"]),
                "eval_reference": y_ref,
            })
            progressed = True
        if not progressed:
            break
    return personas


def build_word_count_prompt(combo: dict, source: str) -> str:
    """B+ 의 공정한 판: 취향을 아는 사람이 채점 문서 길이로 단어 수를 계산해 적은 지침.
    문장 수 대신 "about N words" 를 쓰는 것 말고는 B+ 와 같은 문구다."""
    from experiments.strong_baseline_comparison import EXTRACTIVENESS_PHRASING
    words = round(FAIR_BPLUS_RATIOS[combo["length"]] * len(source.split()))
    return f"Summarize the following article in about {words} words, {EXTRACTIVENESS_PHRASING[combo['extractiveness']]}."


def learn_prompt(domain, persona: dict, model: str = MODEL, *, tie_policy: str = "legacy-a",
                 diagnostics: dict | None = None) -> tuple[str, dict[str, str]]:
    """학습 문서 X 에서 8회 선택으로 선호를 배우고, 그 선호로 조립한 프롬프트."""
    oracle = Persona(combo=persona["combo"], reference_summary=persona["learn_reference"])
    estimator = Estimator(domain)
    selector = UncertaintySelector(domain, seed=SEED)
    for _ in range(N_ROUNDS):
        combo_a, combo_b = selector.next_pair(estimator)
        a = generate(domain, persona["learn_source"], combo_a, model=model)
        b = generate(domain, persona["learn_source"], combo_b, model=model)
        winner = choose(domain, oracle, a, b, persona["learn_source"], tie_policy=tie_policy)
        if diagnostics is not None:
            score_a, score_b = comparison_scores(domain, oracle, a, b, persona["learn_source"])
            diagnostics.setdefault("comparisons", []).append({
                "round": len(diagnostics.get("comparisons", [])) + 1,
                "combo_a": combo_a, "combo_b": combo_b,
                "score_a": score_a, "score_b": score_b, "winner": winner,
            })
        estimator.update(Comparison(combo_a, combo_b, winner))
    learned = {name: estimator.preferred_value(name) for name in estimator.enum_axis_names()}
    # 지시문에 원문 길이 자리표시자가 있는 도메인(v3)이면 채점 문서 Y 의 길이로 채운다.
    # 없는 도메인은 source 와 무관하게 예전과 같은 프롬프트다.
    return build_seed_prompt(domain, estimator, source=persona["eval_source"]), learned


def length_ratio(output: str, source: str) -> float:
    """출력 단어 수 / 원문 단어 수. 모델이 길이 지시를 실제로 따랐는지 본다."""
    return len(_words(output)) / max(len(_words(source)), 1)


def compare_d(df: pd.DataFrame, baseline_csv: Path) -> dict:
    """같은 페르소나에서 기본 도메인의 D 와 이 도메인의 D 를 비교한다."""
    base = pd.read_csv(baseline_csv)
    base_d = base[base["condition"] == "D_our_tool"].set_index("persona")
    new_d = df[df["condition"] == "D_our_tool"].set_index("persona")
    common = new_d.index.intersection(base_d.index)
    assert (base_d.loc[common, "eval_doc"] == new_d.loc[common, "eval_doc"]).all(), "페르소나가 다르다"
    diff = new_d.loc[common, "rouge_l"] - base_d.loc[common, "rouge_l"]
    wins, losses = int((diff > 0).sum()), int((diff < 0).sum())
    return {
        "baseline": str(baseline_csv), "n": len(common),
        "rouge_l_baseline_D": round(float(base_d.loc[common, "rouge_l"].mean()), 4),
        "rouge_l_this_D": round(float(new_d.loc[common, "rouge_l"].mean()), 4),
        "wins": wins, "losses": losses, "ties": int((diff == 0).sum()),
        "mean_diff": round(float(diff.mean()), 4),
        "sign_test_p": round(sign_test_p(wins, wins + losses), 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--cap", type=float, default=2.0, help="실제 청구 비용 상한 (달러)")
    parser.add_argument("--domain", default=DEFAULT_DOMAIN)
    parser.add_argument("--model", default=MODEL, help="예: ollama/qwen2.5:7b (로컬, 비용 0)")
    parser.add_argument("--fair-bplus", action="store_true", help="단어 수를 받는 B+ 조건을 더한다 (5단계)")
    parser.add_argument("--output-dir", type=Path, help="결과 위치 (기본: 실행마다 새 runs/ 폴더)")
    parser.add_argument("--overwrite", action="store_true", help="명시한 출력 위치의 기존 실행을 교체")
    parser.add_argument("--tie-policy", choices=("legacy-a", "record-tie"), default="legacy-a",
                        help="과거 실험 기본은 legacy-a. record-tie는 동점을 별도로 기록하는 새 실험")
    args = parser.parse_args()
    if args.n <= 0 or not math.isfinite(args.cap) or args.cap <= 0:
        parser.error("--n과 --cap은 양수여야 한다")
    conditions = CONDITIONS + ((FAIR_BPLUS,) if args.fair_bplus else ())
    comparisons = COMPARISONS + (FAIR_COMPARISONS if args.fair_bplus else ())

    import litellm

    domain = load_domain(args.domain)
    stem = OUT_CSV.stem
    if args.domain != DEFAULT_DOMAIN or args.model != MODEL:
        # 다른 모델의 결과는 gpt-4o-mini 결과와 섞이지 않게 파일 이름에 모델을 붙인다.
        tag = domain.name + ("" if args.model == MODEL else "_" + args.model.split("/")[-1].replace(":", "-"))
        stem = f"heldout_comparison_{tag}"
    config = {
        "model": args.model, "domain": domain.name, "split": str(SPLIT),
        "requested_n": args.n, "n_rounds": N_ROUNDS, "seed": SEED,
        "fair_bplus": args.fair_bplus, "conditions": list(conditions),
        "comparisons": [list(pair) for pair in comparisons], "tie_policy": args.tie_policy,
        "generation_options": "existing defaults; temperature unspecified; cached responses reused",
        "domain_sha256": hashlib.sha256(Path(args.domain).read_bytes()).hexdigest(),
        "split_sha256": hashlib.sha256(SPLIT.read_bytes()).hexdigest() if SPLIT.exists() else None,
    }
    try:
        paths, manifest = prepare_run(stem, (".csv", ".json"), output_dir=args.output_dir,
                                      overwrite=args.overwrite, metadata=config)
    except (FileExistsError, ValueError) as exc:
        parser.error(str(exc))
    out_csv, out_json = paths[".csv"], paths[".json"]
    spend = Spend()
    previous_callbacks = litellm.success_callback
    litellm.success_callback = [spend]
    try:
        return _run(args, domain, conditions, comparisons, config, spend, out_csv, out_json, manifest)
    except BaseException as exc:
        finish_run(manifest, "failed", error_type=type(exc).__name__,
                   spend_dollars=round(spend.dollars, 4), model_calls=spend.calls)
        raise
    finally:
        litellm.success_callback = previous_callbacks


def _run(args, domain, conditions, comparisons, config, spend, out_csv, out_json, manifest) -> int:
    personas = pick_personas(args.n)
    if not personas:
        raise ValueError("비교할 페르소나가 없다")
    print(f"페르소나 {len(personas)}명 (요청 {args.n}), 조합:",
          sorted({(p['combo']['length'], p['combo']['extractiveness']) for p in personas}))

    rows: list[dict] = []
    stopped = None
    for k, persona in enumerate(personas):
        if spend.dollars >= args.cap:
            stopped = f"비용 상한 ${args.cap} 도달 - {k}번째 페르소나 전에 멈춤"
            break
        diagnostics: dict = {}
        d_prompt, learned = learn_prompt(domain, persona, args.model,
                                        tie_policy=args.tie_policy, diagnostics=diagnostics)
        choices = diagnostics.get("comparisons", [])
        oracle_ties = sum(c["score_a"] == c["score_b"] for c in choices)
        prompts = {
            "A_no_prompt": CONDITION_A_PROMPT,
            "B_custom_instruction": CONDITION_B_PROMPT,
            "B_plus_knows_preference": build_strong_direct_prompt(persona["combo"]),
            "D_our_tool": d_prompt,
            FAIR_BPLUS: build_word_count_prompt(persona["combo"], persona["eval_source"]),
        }
        for condition in conditions:
            output = generate_raw(prompts[condition], persona["eval_source"], args.model)
            rows.append({
                "persona": k,
                "length": persona["combo"]["length"],
                "extractiveness": persona["combo"]["extractiveness"],
                "learn_doc": persona["learn_doc"],
                "eval_doc": persona["eval_doc"],
                "learned_exact": learned == persona["combo"],
                **{f"learned_{axis}": value for axis, value in learned.items()},
                "oracle_ties": oracle_ties, "oracle_comparisons": len(choices),
                "condition": condition,
                "checks_score": score_against_combo(domain, persona["combo"], output, persona["eval_source"]),
                "rouge_l": rouge_l_score(output, persona["eval_reference"]),
                "length_ratio": length_ratio(output, persona["eval_source"]),
            })
        # 페르소나마다 바로 저장한다. 중간에 끊겨도 쓴 비용이 남는다.
        _save_results(pd.DataFrame(rows), args, domain, conditions, comparisons, config,
                      spend, stopped, out_csv, out_json)
        print(f"  {k + 1}/{len(personas)} 완료 · 누적 ${spend.dollars:.4f} ({spend.calls}회 호출)")

    summary = _save_results(pd.DataFrame(rows), args, domain, conditions, comparisons, config,
                            spend, stopped, out_csv, out_json)
    finish_run(manifest, "stopped" if stopped else "completed", n=summary["n"],
               spend_dollars=round(spend.dollars, 4), model_calls=spend.calls)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"결과: {out_csv} / {out_json}")
    return 0


def _save_results(df, args, domain, conditions, comparisons, config, spend, stopped, out_csv, out_json):
    summary = summarize(df, conditions, comparisons) if len(df) else {"n": 0}
    summary.update({
        **config,
        "learned_exact_rate": round(float(df.drop_duplicates("persona")["learned_exact"].mean()), 4) if len(df) else None,
        "spend_dollars": round(spend.dollars, 4), "model_calls": spend.calls, "stopped": stopped,
    })
    summary["domain"] = domain.name
    if len(df):
        cases = df.drop_duplicates("persona")
        summary["axis_learning_accuracy"] = {
            axis.name: {"correct": int((cases[f"learned_{axis.name}"] == cases[axis.name]).sum()),
                        "n": len(cases)}
            for axis in domain.axes if axis.type == "enum" and f"learned_{axis.name}" in cases and axis.name in cases
        }
        summary["oracle_ties"] = int(cases["oracle_ties"].sum())
        summary["oracle_comparisons"] = int(cases["oracle_comparisons"].sum())
    if args.fair_bplus and len(df):
        primary = summary["paired"][f"rouge_l: D_our_tool vs {FAIR_BPLUS}"]
        summary["primary_comparison"] = {
            "metric": "rouge_l", "a": "D_our_tool", "b": FAIR_BPLUS,
            "alpha": 0.05, "test": "two-sided exact sign test, ties omitted",
            "conclusion": "D_superiority_observed" if primary["wins"] > primary["losses"]
                          and primary["sign_test_p"] < 0.05 else "D_superiority_not_established",
            "equivalence_tested": False,
        }
    # 기본 결과(gpt-4o-mini)와의 D 비교는 같은 모델일 때만 뜻이 있다.
    if args.domain != DEFAULT_DOMAIN and args.model == MODEL and OUT_CSV.exists() and len(df):
        summary["D_vs_baseline_D"] = compare_d(df, OUT_CSV)
    if len(df):
        write_csv(out_csv, df)
    write_json(out_json, summary)
    return summary


if __name__ == "__main__":
    raise SystemExit(main())

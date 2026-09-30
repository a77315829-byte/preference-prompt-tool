"""선호를 배운 문서와 채점하는 문서를 나눈 비교 실험 (계획서 1-3, 1-7).

기존 A/B/D 와 강한 비교군 실험(5문서)의 한계 셋을 한 번에 다룬다.
1. 선호를 배운 문서와 채점한 문서가 같았다 -> 페르소나마다 학습 문서 X 와
   채점 문서 Y 를 다르게 둔다. D 는 X 에서 8회 선택으로 배운 프롬프트를 Y 에
   적용한다.
2. n=5 였다 -> 기본 30 페르소나, 페어드 부호검정.
3. 페르소나 5명의 추출성이 전부 normal 이었다 -> (length, extractiveness)
   조합을 돌아가며 고른다.

데이터는 MACSum **test** 분할이다. 검사 함수의 임계값은 train+val 분포로
보정했으므로 한 번도 쓰지 않은 분할로 채점한다.

모델은 앱의 후보 생성 모델(gpt-4o-mini)이다. 기존 실험(gpt-4.1-mini)과
수치를 섞지 않는다. 온도는 기존 실험처럼 지정하지 않는다.

비용: 실제 청구 비용(litellm 의 response_cost)을 더하다가 --cap 달러에 닿으면
다음 페르소나로 넘어가지 않고 멈춘다. 결과는 페르소나마다 바로 저장한다.

    python -m experiments.heldout_comparison --n 2      # 파일럿: 비용 확인
    python -m experiments.heldout_comparison --n 30     # 본 실험 (캐시 재사용)
"""

from __future__ import annotations

import argparse
import json
import random
import threading
from collections import defaultdict
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator
from engine.generator import generate
from engine.selector import UncertaintySelector
from experiments.compare_baselines import CONDITION_A_PROMPT, CONDITION_B_PROMPT, generate_raw, score_against_combo
from experiments.expert_prompt_eval import sign_test_p
from experiments.independent_grader import rouge_l_score
from experiments.persona import Persona, choose
from experiments.strong_baseline_comparison import build_strong_direct_prompt
from optimize.run_gepa import build_seed_prompt

load_dotenv()

MODEL = "openai/gpt-4o-mini"
N_ROUNDS = 8
SPLIT = Path("data/macsum/dataset/macdoc/test.json")
SEED = 0
OUT_CSV = Path("experiments/results/heldout_comparison.csv")
OUT_JSON = Path("experiments/results/heldout_comparison.json")
CONDITIONS = ("A_no_prompt", "B_custom_instruction", "B_plus_knows_preference", "D_our_tool")
COMPARISONS = (
    ("D_our_tool", "B_custom_instruction"),
    ("D_our_tool", "B_plus_knows_preference"),
    ("B_plus_knows_preference", "B_custom_instruction"),
    ("D_our_tool", "A_no_prompt"),
)


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


def learn_prompt(domain, persona: dict) -> tuple[str, dict[str, str]]:
    """학습 문서 X 에서 8회 선택으로 선호를 배우고, 그 선호로 조립한 프롬프트."""
    oracle = Persona(combo=persona["combo"], reference_summary=persona["learn_reference"])
    estimator = Estimator(domain)
    selector = UncertaintySelector(domain, seed=SEED)
    for _ in range(N_ROUNDS):
        combo_a, combo_b = selector.next_pair(estimator)
        a = generate(domain, persona["learn_source"], combo_a, model=MODEL)
        b = generate(domain, persona["learn_source"], combo_b, model=MODEL)
        estimator.update(Comparison(combo_a, combo_b, choose(domain, oracle, a, b, persona["learn_source"])))
    learned = {name: estimator.preferred_value(name) for name in estimator.enum_axis_names()}
    return build_seed_prompt(domain, estimator), learned


def summarize(df: pd.DataFrame) -> dict:
    out = {"n": int(df["persona"].nunique()), "means": {}, "paired": {}}
    for metric in ("checks_score", "rouge_l"):
        pivot = df.pivot(index="persona", columns="condition", values=metric)
        out["means"][metric] = {c: round(float(pivot[c].mean()), 4) for c in CONDITIONS if c in pivot}
        for a, b in COMPARISONS:
            diff = pivot[a] - pivot[b]
            wins, losses = int((diff > 0).sum()), int((diff < 0).sum())
            out["paired"][f"{metric}: {a} vs {b}"] = {
                "wins": wins, "losses": losses, "ties": int((diff == 0).sum()),
                "mean_diff": round(float(diff.mean()), 4),
                "sign_test_p": round(sign_test_p(wins, wins + losses), 4),
            }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--cap", type=float, default=2.0, help="실제 청구 비용 상한 (달러)")
    args = parser.parse_args()

    import litellm

    spend = Spend()
    litellm.success_callback = [spend]

    domain = load_domain("domains/summarization.yaml")
    personas = pick_personas(args.n)
    print(f"페르소나 {len(personas)}명 (요청 {args.n}), 조합:",
          sorted({(p['combo']['length'], p['combo']['extractiveness']) for p in personas}))

    rows: list[dict] = []
    stopped = None
    for k, persona in enumerate(personas):
        if spend.dollars >= args.cap:
            stopped = f"비용 상한 ${args.cap} 도달 - {k}번째 페르소나 전에 멈춤"
            break
        d_prompt, learned = learn_prompt(domain, persona)
        prompts = {
            "A_no_prompt": CONDITION_A_PROMPT,
            "B_custom_instruction": CONDITION_B_PROMPT,
            "B_plus_knows_preference": build_strong_direct_prompt(persona["combo"]),
            "D_our_tool": d_prompt,
        }
        for condition in CONDITIONS:
            output = generate_raw(prompts[condition], persona["eval_source"], MODEL)
            rows.append({
                "persona": k,
                "length": persona["combo"]["length"],
                "extractiveness": persona["combo"]["extractiveness"],
                "learn_doc": persona["learn_doc"],
                "eval_doc": persona["eval_doc"],
                "learned_exact": learned == persona["combo"],
                "condition": condition,
                "checks_score": score_against_combo(domain, persona["combo"], output, persona["eval_source"]),
                "rouge_l": rouge_l_score(output, persona["eval_reference"]),
            })
        # 페르소나마다 바로 저장한다. 중간에 끊겨도 쓴 비용이 남는다.
        df = pd.DataFrame(rows)
        OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(OUT_CSV, index=False)
        print(f"  {k + 1}/{len(personas)} 완료 · 누적 ${spend.dollars:.4f} ({spend.calls}회 호출)")

    df = pd.DataFrame(rows)
    summary = summarize(df) if len(df) else {"n": 0}
    summary.update({
        "model": MODEL, "split": str(SPLIT), "n_rounds": N_ROUNDS, "seed": SEED,
        "learned_exact_rate": round(float(df.drop_duplicates("persona")["learned_exact"].mean()), 4) if len(df) else None,
        "spend_dollars": round(spend.dollars, 4), "model_calls": spend.calls, "stopped": stopped,
    })
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

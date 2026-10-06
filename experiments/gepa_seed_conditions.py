"""GEPA 에 일감을 주면 조립 시드를 이기는가 - 시드 조건 비교.

    python -m experiments.gepa_seed_conditions

왜 필요한가: 제품의 최적화 버튼은 추정 선호로 완전히 조립한 시드를 GEPA 에
넘긴다. 평가 함수가 그 같은 선호를 검사하므로 시드가 처음부터 통과하고
GEPA 는 아무것도 바꾸지 않는다 (로그: "All subsample scores perfect.
Skipping."). 이건 GEPA 의 결함이 아니라 일감을 안 준 것이다. 그렇다고 GEPA
를 뺄지, 다른 시드를 줄지는 재봐야 정해진다.

조건 (문서·페르소나마다 8회 선택 루프를 똑같이 돌려 estimator 를 만든 뒤):

  assembled        추정값 전부를 조립한 시드, GEPA 없음. 비교군 D 와 동일.
  assembled_gepa   같은 시드에 GEPA. 제품의 현재 버튼. 아무것도 안 하는지 확인.
  neutral_gepa     "Summarize the following text." 에 GEPA. 처음부터 찾게 한다.
  partial_gepa     확신도가 평균 이상인 축만 조립하고 나머지는 비운 시드에 GEPA.
                   추정이 약한 축을 GEPA 가 피드백을 읽으며 채우는지 본다.

partial 의 규칙은 상대 확신도다. 8회 뒤 3값 축의 절대 확신도는 0.06 근방에
머물기 때문에(보너스 3) 절대 임계값은 쓸 수 없고, 프로젝트가 확신도를 쓰는
방식대로 축끼리만 비교한다. 정답(페르소나 라벨)은 시드를 만들 때 쓰지 않는다.

채점은 두 지표를 나란히 낸다 (규칙 7). checks 는 GEPA 가 최적화한 지표라
neutral/partial 에 유리하고, ROUGE-L 은 최적화에 쓰이지 않은 독립 지표다.
GEPA 학습·검증 문서는 평가 문서와 겹치지 않도록 val.json 뒤쪽에서 뽑고
원문 텍스트로 겹침을 검사한다.

결과는 문서마다 즉시 저장한다 - 크레딧 소진으로 유료 결과를 잃은 적이 있다.

결정 규칙 (돌리기 전에 적어둔다):
  partial 이 assembled 를 ROUGE-L 페어드에서 이기면 GEPA 는 "추정이 못 미치는
  축을 메우는 장치"로 제품에 남긴다. neutral 만 이기면 선택 루프와 GEPA 가
  대체 관계라는 뜻이다. 둘 다 못 이기면 GEPA 를 제품에서 뺀다.
"""

from __future__ import annotations

import json
import math
import statistics
import time
from pathlib import Path

from dotenv import load_dotenv
from gepa import optimize as gepa_optimize
from gepa.adapters.default_adapter.default_adapter import DefaultAdapter

from engine.domain_loader import Domain, load_domain
from engine.estimator import Comparison, Estimator
from engine.generator import build_prompt, generate
from engine.metric_builder import build_metric
from engine.selector import UncertaintySelector
from experiments.compare_baselines import MODEL, N_ROUNDS, generate_raw, score_against_combo
from experiments.independent_grader import rouge_l_score
from experiments.persona import choose
from experiments.run_all import pick_documents_with_personas
from optimize.run_gepa import MetricEvaluator, build_seed_prompt

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

VAL_PATH = "data/macsum/dataset/macdoc/val.json"
N_DOCS = 5
NEUTRAL_SEED = "Summarize the following text."
MAX_METRIC_CALLS = 40   # 피드백 어블레이션과 같은 예산
GEPA_SEED = 0
REFLECTION_LM = MODEL
OUT = Path("experiments/results/gepa_seed_conditions.json")

CONDITIONS = ("assembled", "assembled_gepa", "neutral_gepa", "partial_gepa")


def learn_preferences(domain: Domain, source: str, persona) -> Estimator:
    """비교군 D 와 같은 8회 루프. seed=0 이라 compare_baselines 의 캐시를 탄다."""
    estimator = Estimator(domain)
    selector = UncertaintySelector(domain, seed=0)
    for _ in range(N_ROUNDS):
        combo_a, combo_b = selector.next_pair(estimator)
        cand_a = generate(domain, source, combo_a, model=MODEL)
        cand_b = generate(domain, source, combo_b, model=MODEL)
        winner = choose(domain, persona, cand_a, cand_b, source)
        estimator.update(Comparison(combo_a, combo_b, winner))
    return estimator


def partial_seed(domain: Domain, estimator: Estimator) -> tuple[str, list[str], dict[str, float]]:
    """확신도가 평균 이상인 축만 조립한다. (프롬프트, 넣은 축, 축별 확신도)."""
    axes = estimator.enum_axis_names()
    conf = {name: estimator.confidence(name) for name in axes}
    mean_conf = sum(conf.values()) / len(conf)
    kept = [name for name in axes if conf[name] >= mean_conf]
    # engine.generator.build_prompt 는 열거형 축을 비울 수 없다 (제품에서는
    # 그게 맞다). 여기서는 뺀 축의 지시문만 생략하고 나머지는 같은 규칙으로
    # 조립한다 - 과제 서술 + 남긴 축의 지시문.
    lines = [domain.task_description]
    for axis in domain.axes:
        if axis.type == "enum" and axis.name in kept:
            lines.append(axis.instruction_for(estimator.preferred_value(axis.name)))
    return "\n".join(lines), kept, conf


def run_gepa(seed_prompt: str, metric, train_sources: list[str], val_sources: list[str]):
    adapter = DefaultAdapter(model=MODEL, evaluator=MetricEvaluator(metric))
    return gepa_optimize(
        seed_candidate={"system_prompt": seed_prompt},
        trainset=[{"input": s} for s in train_sources],
        valset=[{"input": s} for s in val_sources],
        adapter=adapter,
        reflection_lm=REFLECTION_LM,
        max_metric_calls=MAX_METRIC_CALLS,
        seed=GEPA_SEED,
        display_progress_bar=False,
    )


def gepa_sources(eval_sources: list[str]) -> tuple[list[str], list[str]]:
    """val.json 뒤쪽에서 학습 4 / 검증 2. 평가 문서와 원문이 겹치면 건너뛴다."""
    records = json.loads(Path(VAL_PATH).read_text(encoding="utf-8"))
    banned = {" ".join(s.split()) for s in eval_sources}
    pool = []
    for rec in reversed(records):
        source = " ".join(rec["source"])
        if " ".join(source.split()) in banned:
            continue
        pool.append(source)
        if len(pool) == 6:
            break
    return pool[:4], pool[4:6]


def sign_test_p(wins: int, n: int) -> float:
    """양측 부호검정, 동률 제외 후 n."""
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def load_partial() -> dict:
    if OUT.exists():
        return json.loads(OUT.read_text(encoding="utf-8"))
    return {"docs": [], "complete": False}


def save(state: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    domain = load_domain("domains/summarization.yaml")
    documents = pick_documents_with_personas(VAL_PATH, N_DOCS)
    train_sources, val_sources = gepa_sources([s for s, _ in documents])

    state = load_partial()
    done = {d["doc"] for d in state["docs"]}
    state.setdefault("meta", {}).update({
        "model": MODEL, "rounds": N_ROUNDS, "max_metric_calls": MAX_METRIC_CALLS,
        "neutral_seed": NEUTRAL_SEED, "gepa_train_docs": len(train_sources),
        "gepa_val_docs": len(val_sources),
    })

    for doc_idx, (source, persona) in enumerate(documents):
        if doc_idx in done:
            print(f"doc={doc_idx} 이미 있음, 건너뜀")
            continue
        target = {"length": persona.combo["length"], "extractiveness": persona.combo["extractiveness"]}
        estimator = learn_preferences(domain, source, persona)
        metric = build_metric(domain, estimator)
        estimated = {name: estimator.preferred_value(name) for name in estimator.enum_axis_names()}

        seeds = {
            "assembled": build_seed_prompt(domain, estimator),
            "neutral": NEUTRAL_SEED,
        }
        seeds["partial"], kept_axes, conf = partial_seed(domain, estimator)

        # 조건 단위로 저장한다. 문서 단위로 저장했더니 한 문서 안에서 끊긴
        # 유료 GEPA 실행 두 개가 날아갔다.
        partial = state.get("partial_doc")
        if partial and partial["doc"] == doc_idx:
            row = partial
        else:
            row = {
                "doc": doc_idx, "target": target, "estimated": estimated,
                "estimate_correct": {k: estimated[k] == target[k] for k in target},
                "confidence": conf, "partial_kept_axes": kept_axes,
                "conditions": {},
            }
        try:
            for cond in CONDITIONS:
                if cond in row["conditions"]:
                    print(f"doc={doc_idx} {cond:15} 이미 있음, 건너뜀")
                    continue
                t0 = time.time()
                seed_key = cond.split("_")[0]
                seed_prompt = seeds[seed_key]
                gepa_info = None
                if cond.endswith("_gepa"):
                    result = run_gepa(seed_prompt, metric, train_sources, val_sources)
                    final_prompt = result.best_candidate["system_prompt"]
                    gepa_info = {
                        "best_val_score": result.val_aggregate_scores[result.best_idx],
                        "seed_val_score": result.val_aggregate_scores[0],
                        "num_candidates": result.num_candidates,
                        "changed": final_prompt.strip() != seed_prompt.strip(),
                    }
                else:
                    final_prompt = seed_prompt
                output = generate_raw(final_prompt, source, MODEL)
                row["conditions"][cond] = {
                    "seed_prompt": seed_prompt,
                    "final_prompt": final_prompt,
                    "gepa": gepa_info,
                    "checks_score": score_against_combo(domain, target, output, source),
                    "rouge_l": rouge_l_score(output, persona.reference_summary),
                    "seconds": round(time.time() - t0, 1),
                }
                state["partial_doc"] = row
                save(state)
                print(f"doc={doc_idx} {cond:15} checks={row['conditions'][cond]['checks_score']:.3f} "
                      f"rougeL={row['conditions'][cond]['rouge_l']:.3f}"
                      + (f"  gepa: val {gepa_info['seed_val_score']:.2f}->{gepa_info['best_val_score']:.2f}, "
                         f"changed={gepa_info['changed']}" if gepa_info else ""))
        except Exception as exc:  # noqa: BLE001 - 어디서 멈췄는지 남기고 종료
            state["stopped_at"] = {"doc": doc_idx, "reason": f"{type(exc).__name__}: {exc}"[:300]}
            save(state)
            raise
        state["docs"].append(row)
        state.pop("partial_doc", None)
        save(state)

    state["complete"] = len(state["docs"]) == N_DOCS
    state["summary"] = summarize(state["docs"])
    state.pop("stopped_at", None)
    save(state)
    print_summary(state["summary"])
    print(f"저장: {OUT}")


def summarize(docs: list[dict]) -> dict:
    out = {}
    for cond in CONDITIONS:
        checks = [d["conditions"][cond]["checks_score"] for d in docs]
        rouge = [d["conditions"][cond]["rouge_l"] for d in docs]
        entry = {"checks_mean": statistics.mean(checks), "rouge_mean": statistics.mean(rouge)}
        if cond != "assembled":
            base = [d["conditions"]["assembled"]["rouge_l"] for d in docs]
            wins = sum(1 for a, b in zip(rouge, base) if a > b + 1e-9)
            losses = sum(1 for a, b in zip(rouge, base) if a < b - 1e-9)
            entry["rouge_wins_vs_assembled"] = wins
            entry["rouge_losses_vs_assembled"] = losses
            entry["sign_test_p"] = sign_test_p(wins, wins + losses)
            entry["gepa_changed_prompt"] = sum(
                1 for d in docs if d["conditions"][cond]["gepa"]["changed"])
        out[cond] = entry
    out["estimate_correct_axes"] = sum(
        sum(d["estimate_correct"].values()) for d in docs)
    out["estimate_total_axes"] = sum(len(d["estimate_correct"]) for d in docs)
    return out


def print_summary(summary: dict) -> None:
    print(f"\n추정 정확도: {summary['estimate_correct_axes']}/{summary['estimate_total_axes']} 축\n")
    print(f"{'조건':16} {'checks':>7} {'ROUGE-L':>8} {'승/패 vs assembled':>20} {'p':>7} {'GEPA 변경':>10}")
    for cond in CONDITIONS:
        e = summary[cond]
        extra = ""
        if cond != "assembled":
            extra = (f"{e['rouge_wins_vs_assembled']}/{e['rouge_losses_vs_assembled']:<17} "
                     f"{e['sign_test_p']:7.3f} {e['gepa_changed_prompt']:>10}")
        print(f"{cond:16} {e['checks_mean']:7.3f} {e['rouge_mean']:8.3f} {extra}")


if __name__ == "__main__":
    main()

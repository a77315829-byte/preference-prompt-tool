"""앱 선택기와 동점 처리의 선호 추정 정확도 - 사전등록: docs/history/2026-10-06_selector_tie_preregistration.md

    python -m experiments.selector_tie_accuracy --n 30

학습만 한다 (프롬프트 적용·GEPA 없음). default 칸은 heldout_comparison.learn_prompt 를, app 칸은
앱 함수(service.start_session / submit_choice)를 그대로 쓴다. 후보 생성은 캐시를 탄다.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from dotenv import load_dotenv

import service
from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator
from experiments.gepa_app_comparison import DOMAIN_PATH, Spend
from experiments.heldout_comparison import MODEL, learn_prompt, pick_personas
from experiments.persona import Persona, choose, comparison_scores
from experiments.result_statistics import sign_test_p

OUT = Path("experiments/results/selector_tie_accuracy.json")
CELLS = ("default/legacy-a", "default/record-tie", "app/legacy-a", "app/record-tie")


def learn_default(domain, persona: dict, tie_policy: str) -> tuple[Estimator, int]:
    diagnostics: dict = {}
    learn_prompt(domain, persona, tie_policy=tie_policy, diagnostics=diagnostics)
    # learn_prompt 는 추정기를 돌려주지 않으므로 같은 비교를 그대로 다시 넣어 복원한다.
    estimator = Estimator(domain)
    ties = 0
    for c in diagnostics["comparisons"]:
        estimator.update(Comparison(c["combo_a"], c["combo_b"], c["winner"]))
        ties += c["score_a"] == c["score_b"]
    return estimator, ties


def learn_app(domain, persona: dict, tie_policy: str) -> tuple[Estimator, int]:
    oracle = Persona(combo=persona["combo"], reference_summary=persona["learn_reference"])
    source = persona["learn_source"]
    state = service.start_session(source, domain.name, DOMAIN_PATH, model=MODEL, demo_mode=False)
    ties = 0
    while not state.done:
        a, b = state.pair.a.text, state.pair.b.text
        score_a, score_b = comparison_scores(domain, oracle, a, b, source)
        ties += score_a == score_b
        pick = choose(domain, oracle, a, b, source, tie_policy=tie_policy)
        state = service.submit_choice(state, state.pair.pair_id, pick)
    return service.current_estimate(state)[1], ties


def measure(domain, persona: dict, cell: str) -> dict:
    selector, tie_policy = cell.split("/")
    learner = learn_default if selector == "default" else learn_app
    estimator, ties = learner(domain, persona, tie_policy)
    axes = {}
    for name in estimator.enum_axis_names():
        decided = estimator.has_signal(name)
        axes[name] = {
            "learned": estimator.preferred_value(name) if decided else None,
            "correct": decided and estimator.preferred_value(name) == persona["combo"][name],
        }
    return {"axes": axes, "exact": all(a["correct"] for a in axes.values()),
            "undecided": sum(a["learned"] is None for a in axes.values()), "ties": ties}


def paired(rows: list[dict], x: str, y: str) -> dict:
    """y 에서만 맞힌 사람 = y 의 승. 둘 다 맞히거나 둘 다 틀리면 동점."""
    wins = sum(r[y]["exact"] and not r[x]["exact"] for r in rows)
    losses = sum(r[x]["exact"] and not r[y]["exact"] for r in rows)
    return {"only_" + y: wins, "only_" + x: losses, "sign_test_p": round(sign_test_p(wins, wins + losses), 4)}


def summarize(rows: list[dict]) -> dict:
    axis_names = list(rows[0]["app/legacy-a"]["axes"])
    cells = {
        cell: {
            "exact": sum(r[cell]["exact"] for r in rows),
            "per_axis": {a: sum(r[cell]["axes"][a]["correct"] for r in rows) for a in axis_names},
            "undecided_axes": sum(r[cell]["undecided"] for r in rows),
            "tied_comparisons": sum(r[cell]["ties"] for r in rows),
        }
        for cell in CELLS
    }
    return {
        "n": len(rows), "cells": cells,
        "primary_app_record_tie_vs_legacy": paired(rows, "app/legacy-a", "app/record-tie"),
        "app_vs_default_legacy": paired(rows, "default/legacy-a", "app/legacy-a"),
        "app_vs_default_record_tie": paired(rows, "default/record-tie", "app/record-tie"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--cap", type=float, default=0.5, help="실제 청구 비용 상한 (달러)")
    args = parser.parse_args()
    load_dotenv()
    import litellm

    domain = load_domain(DOMAIN_PATH)
    spend = Spend()
    litellm.success_callback = [spend]
    rows, stopped, started = [], None, time.monotonic()
    try:
        for idx, persona in enumerate(pick_personas(args.n)):
            if spend.dollars >= args.cap:
                stopped = f"비용 상한 ${args.cap} 도달 (사람 {idx} 전)"
                break
            row = {"persona": idx, "combo": persona["combo"], "learn_doc": persona["learn_doc"]}
            row.update({cell: measure(domain, persona, cell) for cell in CELLS})
            rows.append(row)
            print(f"[{idx}] {persona['combo']} " + " ".join(
                f"{c}={'O' if row[c]['exact'] else 'x'}(t{row[c]['ties']})" for c in CELLS),
                f"spent=${spend.dollars:.4f}", flush=True)
    except Exception as exc:  # noqa: BLE001 - 중단 사유를 남기고 끝난 결과는 지킨다
        stopped = f"{type(exc).__name__}: {exc}"[:300]
    result = {
        "rows": rows, "summary": summarize(rows) if rows else {},
        "run": {"requested_n": args.n, "spend_dollars": round(spend.dollars, 4), "model_calls": spend.calls,
                "seconds": round(time.monotonic() - started, 1), "stopped": stopped},
        "config": {"domain": DOMAIN_PATH, "model": MODEL, "rounds": "8 (both selectors)",
                   "preregistration": "docs/history/2026-10-06_selector_tie_preregistration.md"},
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print(f"this run: ${spend.dollars:.4f}, {spend.calls} calls, stopped={stopped}")
    return 0 if stopped is None else 1


if __name__ == "__main__":
    raise SystemExit(main())

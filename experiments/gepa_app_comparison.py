"""실제 앱 조건에서 GEPA 의 추가 효과 - 사전등록: docs/history/2026-10-06_gepa_app_preregistration.md

    python -m experiments.gepa_app_comparison --n 2      # 단가 확인
    python -m experiments.gepa_app_comparison --n 30

앱이 실제로 부르는 함수를 그대로 쓴다: 선호 학습은 service.start_session / submit_choice,
결과 화면의 프롬프트는 service.final_prompt, 최적화 버튼은 service.optimize. 실험용으로 다시
짠 경로가 아니다 - 그래서 앱이 바뀌면 이 실험도 같이 바뀐다 (설정은 결과 파일에 남긴다).

페르소나는 heldout_comparison 과 같은 30명이다. 사람마다 결과를 즉시 저장하고, 다시 돌리면
끝난 사람은 건너뛴다 (생성은 캐시, GEPA 후보 평가도 캐시를 탄다).
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

import service
from engine.domain_loader import load_domain
from engine.generator import generate_with_prompt
from experiments.compare_baselines import score_against_combo
from experiments.heldout_comparison import MODEL, length_ratio, pick_personas
from experiments.independent_grader import rouge_l_score
from experiments.persona import Persona, choose
from experiments.result_statistics import sign_test_p

DOMAIN_PATH = "domains/summarization.yaml"
LANGUAGE = "en"  # 앱의 기본 프롬프트 언어 (api_server.DEFAULT_PROMPT_LANGUAGE)
OUT = Path("experiments/results/gepa_app_comparison.json")
CONDITIONS = ("assembled", "app_gepa")


class Spend:
    """litellm 콜백으로 실제 청구 비용을 더한다. 캐시에 있던 응답은 0 이다."""

    def __init__(self) -> None:
        self.dollars, self.calls = 0.0, 0
        self._lock = threading.Lock()

    def __call__(self, kwargs, completion_response, start_time, end_time) -> None:
        with self._lock:
            self.dollars += float(kwargs.get("response_cost") or 0.0)
            self.calls += 1


def learn(domain, persona: dict) -> service.SessionState:
    """앱과 같은 선택 루프. 페르소나가 고른다."""
    oracle = Persona(combo=persona["combo"], reference_summary=persona["learn_reference"])
    state = service.start_session(persona["learn_source"], domain.name, DOMAIN_PATH,
                                  model=MODEL, demo_mode=False)
    while not state.done:
        pick = choose(domain, oracle, state.pair.a.text, state.pair.b.text, persona["learn_source"])
        state = service.submit_choice(state, state.pair.pair_id, pick)
    return state


def evaluate(domain, persona: dict, prompt: str) -> dict:
    output = generate_with_prompt(prompt, persona["eval_source"], MODEL)
    return {
        "rouge_l": round(rouge_l_score(output, persona["eval_reference"]), 4),
        "checks": round(score_against_combo(domain, persona["combo"], output, persona["eval_source"]), 4),
        "length_ratio": round(length_ratio(output, persona["eval_source"]), 4),
        "prompt_words": len(prompt.split()),
    }


def summarize(rows: list[dict]) -> dict:
    out = {"n": len(rows), "means": {}, "app_gepa_vs_assembled": {}}
    for metric in ("rouge_l", "checks", "length_ratio", "prompt_words"):
        out["means"][metric] = {c: round(sum(r[c][metric] for r in rows) / len(rows), 4) for c in CONDITIONS}
    for metric in ("rouge_l", "checks"):
        diffs = [r["app_gepa"][metric] - r["assembled"][metric] for r in rows]
        wins, losses = sum(d > 0 for d in diffs), sum(d < 0 for d in diffs)
        out["app_gepa_vs_assembled"][metric] = {
            "wins": wins, "losses": losses, "ties": len(diffs) - wins - losses,
            "mean_diff": round(sum(diffs) / len(diffs), 4),
            "sign_test_p": round(sign_test_p(wins, wins + losses), 4),
        }
    out["prompt_changed"] = sum(r["prompt_changed"] for r in rows)
    out["estimate_exact"] = sum(r["learned"] == r["combo"] for r in rows)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument("--cap", type=float, default=2.0, help="실제 청구 비용 상한 (달러)")
    args = parser.parse_args()
    load_dotenv()
    import litellm

    domain = load_domain(DOMAIN_PATH)
    state = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"rows": [], "runs": []}
    done = {r["persona"] for r in state["rows"]}
    spend = Spend()
    litellm.success_callback = [spend]
    stopped = None
    started = time.monotonic()
    try:
        for idx, persona in enumerate(pick_personas(args.n)):
            if idx in done:
                continue
            if spend.dollars >= args.cap:
                stopped = f"비용 상한 ${args.cap} 도달 (사람 {idx} 전)"
                break
            t0 = time.monotonic()
            session = learn(domain, persona)
            _, estimator = service.current_estimate(session)
            assembled = service.final_prompt(domain, estimator, language=LANGUAGE)
            report: dict = {}
            optimized = service.optimize(session, report=report, language=LANGUAGE)
            row = {
                "persona": idx, "combo": persona["combo"],
                "learn_doc": persona["learn_doc"], "eval_doc": persona["eval_doc"],
                "learned": {n: estimator.preferred_value(n) for n in estimator.enum_axis_names()},
                "undecided": service.undecided_axes(estimator),
                "questions": session.answered,
                "prompt_changed": optimized.strip() != assembled.strip(),
                "gepa_report": report,
                "assembled": evaluate(domain, persona, assembled),
                "app_gepa": evaluate(domain, persona, optimized),
                "prompts": {"assembled": assembled, "app_gepa": optimized},
                "seconds": round(time.monotonic() - t0, 1),
            }
            state["rows"].append(row)
            OUT.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[{idx}] {persona['combo']} changed={row['prompt_changed']} "
                  f"rouge {row['assembled']['rouge_l']:.3f}->{row['app_gepa']['rouge_l']:.3f} "
                  f"spent=${spend.dollars:.4f}", flush=True)
    except Exception as exc:  # noqa: BLE001 - 중단 사유를 남기고 끝난 결과는 지킨다
        stopped = f"{type(exc).__name__}: {exc}"[:300]
    finally:
        state["runs"].append({
            "requested_n": args.n, "spend_dollars": round(spend.dollars, 4), "model_calls": spend.calls,
            "seconds": round(time.monotonic() - started, 1), "stopped": stopped,
        })
        state["config"] = {
            "domain": DOMAIN_PATH, "language": LANGUAGE, "model": MODEL,
            "reflection_model": service.REFLECTION_MODEL, "metric_calls": service.GEPA_METRIC_CALLS,
            "selector": "app (contrast_first, avoid_repeats)", "tie_policy": "legacy-a",
            "preregistration": "docs/history/2026-10-06_gepa_app_preregistration.md",
        }
        if state["rows"]:
            state["summary"] = summarize(state["rows"])
        OUT.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(state.get("summary", {}), ensure_ascii=False, indent=2))
    print(f"this run: ${spend.dollars:.4f}, {spend.calls} calls, stopped={stopped}")
    return 0 if stopped is None else 1


if __name__ == "__main__":
    raise SystemExit(main())

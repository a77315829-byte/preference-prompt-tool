"""Bounded live selection/transfer PoC, not training or human satisfaction research."""
from __future__ import annotations

import argparse
import json
import os
from unittest.mock import patch

from dotenv import load_dotenv

import service
from api_server import CODING_MODEL, CODING_ESCALATION_MODEL
from benchmarks.coding_ai_quality.run_trial import ROOT, usage_record
from engine import generator

OUTPUT = ROOT / "data/coding_persona_live_2026-10-15.json"
PERSONAS = [
    {"code_structure": "compact", "style_management": "direct", "type_detail": "inferred"},
    {"code_structure": "separated", "style_management": "theme", "type_detail": "explicit"},
]
REQUEST = json.loads((ROOT / "benchmarks/coding_ai_quality/v1.json").read_text())["tasks"][0]["request"]
TRANSFER = "FAQ 질문 3개와 답변을 표시하는 React 컴포넌트. 처음에는 답변이 모두 닫혀 있고, 질문 버튼을 누르면 해당 답변만 열고 다시 누르면 닫습니다. 여러 답변을 동시에 열 수 있습니다."


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Allow bounded paid API calls")
    args = parser.parse_args()
    if not args.execute:
        print("Dry run: 2 scripted personas, at most 36 API attempts; use --execute to run.")
        return
    load_dotenv(ROOT / ".env", override=False)
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("API key unavailable")
    if OUTPUT.exists():
        raise RuntimeError("Existing evidence preserved; do not repeat paid run automatically")
    report = {"kind": "automated_live_persona_poc_not_human_evaluation", "model": CODING_MODEL,
              "escalation_model": CODING_ESCALATION_MODEL, "max_attempts": 36,
              "usage": [], "personas": [], "request": REQUEST, "transfer_request": TRANSFER}

    def save():
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    original = generator._call_and_cache

    def bounded(*args, **kwargs):
        if len(report["usage"]) >= report["max_attempts"]:
            raise RuntimeError("PoC request limit reached")
        import litellm
        completion = litellm.completion

        def measured(*call_args, **call_kwargs):
            call_kwargs["num_retries"] = 0
            record = {"requested_model": call_kwargs.get("model"), "status": "error",
                      "usage_available": False}
            report["usage"].append(record)
            save()
            response = completion(*call_args, **call_kwargs)
            record.update(usage_record(response, call_kwargs.get("model")), status="completed")
            save()
            return response

        with patch.object(litellm, "completion", measured):
            return original(*args, **kwargs)

    save()
    try:
        with patch.object(generator, "_call_and_cache", bounded):
            for target in PERSONAS:
                row = {"target": target, "pairs": [], "status": "running"}
                report["personas"].append(row)
                state = service.start_session(REQUEST, "coding", "domains/coding.yaml",
                                              model=CODING_MODEL, demo_mode=False,
                                              coding_escalation_model=CODING_ESCALATION_MODEL)
                while not state.done:
                    pair = state.pair
                    axes = [axis for axis in target if pair.a.combo[axis] != pair.b.combo[axis]]
                    if len(axes) != 1:
                        raise AssertionError("Expected exactly one differing axis")
                    axis = axes[0]
                    choice = "a" if pair.a.combo[axis] == target[axis] else "b"
                    row["pairs"].append({"axis": axis, "choice": choice,
                                         "combo_a": pair.a.combo, "combo_b": pair.b.combo,
                                         "a": pair.a.text, "b": pair.b.text})
                    save()
                    state = service.submit_choice(state, pair.pair_id, choice)
                domain, estimator = service.current_estimate(state)
                row["actual"] = service.final_combo(domain, estimator)
                row["prompt"] = service.final_prompt(domain, estimator, language="ko")
                if row["actual"] != target:
                    raise AssertionError("Selection preference mismatch")
                row["transfer"] = generator.generate_with_prompt(row["prompt"], TRANSFER, CODING_MODEL)
                row["status"] = "generated_pending_independent_review"
                save()
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {str(exc).replace(os.environ['OPENAI_API_KEY'], '[REDACTED]')[:400]}"
        save()
    print(json.dumps({"output": str(OUTPUT), "attempts": len(report["usage"]),
                      "statuses": [p["status"] for p in report["personas"]],
                      "error": report.get("error")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

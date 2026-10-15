"""One cached, paid repair at most; generated code must be reviewed separately."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from unittest.mock import patch

from dotenv import load_dotenv

from benchmarks.coding_ai_quality.run_trial import ROOT, usage_record
from engine import generator

SOURCE = ROOT / "data/coding_persona_live_2026-10-15.json"
OUTPUT = ROOT / "data/coding_persona_repair_2026-10-15.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=str, default=str(OUTPUT),
                        help="New evidence path; existing files are never overwritten")
    args = parser.parse_args()
    from pathlib import Path
    output = Path(args.output).resolve()
    if output.parent != (ROOT / "data").resolve():
        raise ValueError("Repair evidence must stay in the data directory")
    if not args.execute:
        print("Dry run: repair one saved FAQ, at most one API call; review before execution.")
        return
    if output.exists():
        raise RuntimeError("Existing evidence preserved; inspect it instead of repeating")
    load_dotenv(ROOT / ".env", override=False)
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("API key unavailable")
    source_bytes = SOURCE.read_bytes()
    source = json.loads(source_bytes)
    persona = source["personas"][1]
    prompt = (
        "You are repairing a React/TypeScript answer. Return all original files in "
        "filename-labelled fenced blocks. Only fix the missing explicit return type "
        "of the exported FAQ function (and add its required type-only import). "
        "Keep all behavior, text, styling, filenames, file separation and theme tokens unchanged. "
        "Do not add dependencies, network calls or other features.\n"
        "## A/B 공통 기능 계약\n" + source["transfer_request"] + "\n"
        "Required coding preferences:\n" + persona["prompt"]
    )
    report = {"kind": "single_ai_repair_not_training", "source": str(SOURCE),
              "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
              "persona_index": 1, "model": source["model"], "max_attempts": 1,
              "usage": [], "status": "pending", "review_required": True}

    def save():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    import litellm
    completion = litellm.completion

    def measured(*call_args, **call_kwargs):
        if report["usage"]:
            raise RuntimeError("One-call repair limit reached")
        call_kwargs["num_retries"] = 0
        record = {"requested_model": call_kwargs.get("model"),
                  "status": "started", "usage_available": False}
        report["usage"].append(record)
        save()
        response = completion(*call_args, **call_kwargs)
        record.update(usage_record(response, call_kwargs.get("model")), status="completed")
        save()
        return response

    save()
    try:
        with patch.object(litellm, "completion", measured):
            report["output"] = generator.generate_with_prompt(
                prompt, persona["transfer"], source["model"])
        report["cache_hit"] = not report["usage"]
        report["status"] = "generated_pending_review"
    except Exception as exc:
        report["status"] = "failed"
        report["error_type"] = type(exc).__name__
    save()
    print(json.dumps({key: report[key] for key in ("status", "usage")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

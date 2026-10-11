"""Run a bounded, reproducible pilot through the product's live coding pair path.

Dry-run is the default. Live execution requires --execute and never uses holdout
tasks. Raw outputs stay under the ignored data/ directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

import service
from engine import generator
from engine.domain_loader import load_domain


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = Path(__file__).with_name("v1.json")
OUTPUT = ROOT / "data" / "coding_ai_quality_trial.json"
CANDIDATE_MODEL = "openai/gpt-5.4-mini"


def combinations(task: dict, domain) -> tuple[dict[str, str], dict[str, str]]:
    """Keep the two non-tested axes identical; alternate A/B direction."""
    axis = domain.axis(task["axis"])
    values = [item.value for item in axis.values]
    first = {**task["common_profile"], task["axis"]: values[0]}
    second = {**task["common_profile"], task["axis"]: values[1]}
    return (first, second) if task["id"] in {"counter_reset", "signup_validation"} else (second, first)


def run_trial(*, execute: bool, task_limit: int, max_api_attempts: int,
              output: Path = OUTPUT, task_id: str | None = None) -> dict:
    if task_limit < 1 or task_limit > 4:
        raise ValueError("task_limit must be between 1 and 4 calibration tasks")
    benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    calibration = [task for task in benchmark["tasks"] if task["split"] == "calibration"]
    if task_id is not None and task_id not in {task["id"] for task in calibration}:
        raise ValueError(f"Unknown calibration task: {task_id}")
    tasks = ([task for task in calibration if task["id"] == task_id]
             if task_id is not None else calibration[:task_limit])
    models = [benchmark["baseline_model"], CANDIDATE_MODEL]
    domain_path = ROOT / "domains" / "coding.yaml"
    domain = load_domain(domain_path)
    planned = [
        {"task": task["id"], "model": model, "a": combinations(task, domain)[0],
         "b": combinations(task, domain)[1]}
        for task in tasks for model in models
    ]
    if not execute:
        return {"mode": "dry-run", "planned_pairs": planned, "maximum_api_attempts_with_repairs": len(planned) * 4}
    if max_api_attempts < len(planned) * 4:
        raise ValueError("max_api_attempts must cover the worst case: four calls per pair")
    load_dotenv(ROOT / ".env", override=False)
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is unavailable; no API requests were sent")

    sources = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in (domain_path, ROOT / "service.py", ROOT / "engine" / "generator.py")}
    report = {
        "benchmark_version": benchmark["version"], "generated_at": datetime.now(timezone.utc).isoformat(),
        "models": models, "api_attempt_limit": max_api_attempts, "results": [],
        "source_sha256": sources,
        "note": "Style checks run in the product path; compilation, behavior and equivalence remain unverified. API attempts are not a billing record.",
    }
    if output.exists():
        previous = json.loads(output.read_text(encoding="utf-8"))
        if previous["benchmark_version"] != benchmark["version"] or previous["models"] != models:
            raise ValueError("Existing trial uses different benchmark or models")
        if previous.get("source_sha256") and previous["source_sha256"] != sources:
            raise ValueError("Source changed since the previous trial")
        report["generated_at"] = previous["generated_at"]
        report["results"] = previous["results"]
        for result in report["results"]:
            if result["status"] == "error" and result.get("error", "").startswith(
                "RuntimeError: 코딩 후보가 스타일 검사를 통과하지 못했습니다"
            ):
                result["status"] = "quality_failure"
    api_attempts = sum(item["api_attempts"] for item in report["results"])
    report["total_api_attempts"] = api_attempts
    if api_attempts > max_api_attempts:
        raise ValueError("Existing API attempts exceed the selected limit")
    original_call = generator._call_and_cache

    def bounded_call(*args, **kwargs):
        nonlocal api_attempts
        if api_attempts >= max_api_attempts:
            raise RuntimeError("API-attempt limit reached")
        api_attempts += 1
        return original_call(*args, **kwargs)

    generator._call_and_cache = bounded_call
    try:
        for item in planned:
            if any(r["task"] == item["task"] and r["model"] == item["model"]
                   and r["status"] in {"generated", "quality_failure"}
                   for r in report["results"]):
                continue
            task = next(task for task in tasks if task["id"] == item["task"])
            before = api_attempts
            started = time.monotonic()
            state = service.SessionState(
                session_id="benchmark", domain_key="coding", domain_path=str(domain_path),
                source_text=task["request"], model=item["model"], demo_mode=False,
            )
            result = {"task": item["task"], "model": item["model"], "axis": task["axis"],
                      "combo_a": item["a"], "combo_b": item["b"]}
            try:
                pair = service._generate_pair(state, domain, item["a"], item["b"])
                result.update(status="generated", a=pair.a.text, b=pair.b.text)
            except Exception as exc:
                message = str(exc).replace(os.environ["OPENAI_API_KEY"], "[REDACTED]")
                status = "quality_failure" if isinstance(exc, service.CodingCandidateQualityError) else "error"
                result.update(status=status, error=f"{type(exc).__name__}: {message[:400]}")
                if isinstance(exc, service.CodingCandidateQualityError):
                    result["failed_candidate"] = exc.candidate
                    result["failure_reasons"] = list(exc.issues)
            result["api_attempts"] = api_attempts - before
            result["elapsed_seconds"] = round(time.monotonic() - started, 2)
            report["results"].append(result)
            report["total_api_attempts"] = api_attempts
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            if result["status"] == "error":
                break
    finally:
        generator._call_and_cache = original_call
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Permit bounded, billable API calls")
    parser.add_argument("--tasks", type=int, default=4, choices=range(1, 5))
    parser.add_argument("--task-id", help="Run only one calibration task without repeating earlier tasks")
    parser.add_argument("--max-api-attempts", type=int, default=32)
    parser.add_argument("--output", type=Path, default=OUTPUT,
                        help="Save a new trial separately from earlier prompt versions")
    args = parser.parse_args()
    result = run_trial(execute=args.execute, task_limit=args.tasks,
                       max_api_attempts=args.max_api_attempts, output=args.output,
                       task_id=args.task_id)
    if args.execute:
        print(json.dumps({"output": str(args.output), "api_attempts": result["total_api_attempts"],
                          "statuses": [{"task": r["task"], "model": r["model"], "status": r["status"]}
                                       for r in result["results"]]}, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""Validate cached pilot answers, execute in offline Docker, report paired results."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import statistics
import subprocess

from .evaluate_docker import IMAGE, container_command, summarize_result, verify_official_fix
from .pilot import OUTPUT, charge, committed, save, sha
from .run import ASSETS, CACHE, asset_bytes, audit_dataset, measure_static, reference_code, write_jsonl

CONDITIONS = ("general", "essential:compact", "essential:modular", "detailed:compact", "detailed:modular")
ALLOWED_IMPORTS = {"math", "cmath", "typing", "collections", "itertools", "functools", "heapq", "bisect",
                   "re", "string", "statistics", "decimal", "fractions", "numpy", "operator", "doctest"}


def inspect_answer(text: str, entry_point: str, status: str) -> tuple[str | None, dict]:
    """Parse/compile only; never import or run generated Python on the host."""
    blocks = re.findall(r"^```(?:python|py)?[ \t]*\n(.*?)^```[ \t]*$", text, re.M | re.S)
    if status != "completed" or not blocks:
        return None, {"valid": False, "single_code_block": len(blocks) == 1,
                      "reason": "incomplete response or no Python block"}
    # Keep the originally planned strict one-block score. Separately evaluate a
    # unique implementation block when the model also supplies usage examples.
    # This supplemental extraction was added after observing formatting (before
    # running tests). Never choose between competing implementations by test score.
    selected = []
    for block in blocks:
        try:
            parsed = ast.parse(block.strip())
        except SyntaxError:
            continue
        if any(isinstance(n, ast.FunctionDef) and n.name == entry_point for n in parsed.body):
            selected.append(block)
    if len(selected) != 1:
        return None, {"valid": False, "single_code_block": len(blocks) == 1,
                      "reason": "no unique implementation block"}
    code = selected[0].strip() + "\n"
    try:
        tree = ast.parse(code)
        compile(tree, "<generated-static-validation>", "exec")
        if not any(isinstance(n, ast.FunctionDef) and n.name == entry_point for n in tree.body):
            raise ValueError("Missing required entry point")
        # Security screening in addition to offline-container isolation, not a correctness metric.
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                if any(n.split(".")[0] not in ALLOWED_IMPORTS for n in names):
                    raise ValueError("Import outside pilot allowlist")
            if isinstance(node, ast.Name) and node.id in {"eval", "exec", "compile", "open", "__import__", "breakpoint", "input"}:
                raise ValueError("Unsafe runtime primitive")
            if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                raise ValueError("Dunder traversal")
        measures = measure_static(code)
        functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        measures.update(valid=True, single_code_block=len(blocks) == 1,
                        nonblank_lines=sum(bool(line.strip()) for line in code.splitlines()),
                        docstrings=sum(ast.get_docstring(n) is not None for n in functions),
                        code_sha256=hashlib.sha256(code.encode()).hexdigest())
        return code, measures
    except (SyntaxError, ValueError, TypeError, RecursionError) as error:
        return None, {"valid": False, "single_code_block": len(blocks) == 1,
                      "reason": type(error).__name__ + ": " + str(error)[:160]}


def prepare_evaluation() -> tuple[dict, list[dict], list[dict]]:
    plan = json.loads((OUTPUT / "plan.json").read_text(encoding="utf-8"))
    ledger = json.loads((OUTPUT / "ledger.json").read_text(encoding="utf-8"))
    if ledger["plan_sha256"] != sha(plan) or len(ledger["entries"]) != 100:
        raise ValueError("Pilot is not complete")
    datasets = {name: audit_dataset(asset, asset_bytes(asset, CACHE))[0]
                for name, asset in (("humaneval", "humaneval"), ("mbpp", "mbpp_noextreme"))}
    tasks = {r["task_id"]: r for rows in datasets.values() for r in rows}
    records = []
    for request in plan["requests"]:
        path = OUTPUT / "answers" / (request["id"] + ".json")
        answer = json.loads(path.read_text(encoding="utf-8"))
        if answer["payload_sha256"] != request["id"] or sha(request["payload"]) != request["id"]:
            raise ValueError("Cached request mismatch")
        cost = charge(answer["response"], request)
        if cost != ledger["entries"][request["id"]]["cost_nano_usd"]:
            raise ValueError("Ledger usage mismatch")
        task = tasks[request["task_id"]]
        code, static = inspect_answer(answer["output_text"], task["entry_point"], answer["response"]["status"])
        # Invalid output remains a counted failure and is never executed.
        executable = code or f"def {task['entry_point']}(*args, **kwargs):\n    raise AssertionError('invalid generated answer')\n"
        records.append({"task_id": request["task_id"], "dataset": request["dataset"],
                        "condition": request["condition"], "request_sha256": request["id"],
                        "answer_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "returned_model": answer["response"]["model"],
                        "usage": answer["response"]["usage"], "cost_nano_usd": cost,
                        "elapsed_seconds": answer["elapsed_seconds"], "static": static, "solution": executable})
    work = OUTPUT / "evaluation"
    inputs = work / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    fix = asset_bytes("evalplus_fix", CACHE)
    verify_official_fix(fix)
    (inputs / ASSETS["evalplus_fix"]["file"]).write_bytes(fix)
    driver = Path(__file__).with_name("container_pilot.py")
    compile(ast.parse(driver.read_text(encoding="utf-8")), str(driver), "exec")
    shutil.copyfile(driver, inputs / "controls.py")
    batches = []
    for dataset, rows in datasets.items():
        selected = {r["task_id"] for r in records if r["dataset"] == dataset}
        subset = [r for r in rows if r["task_id"] in selected]
        if len(subset) != 10:
            raise ValueError("Expected 10 paired tasks per dataset")
        archive = gzip.compress(("\n".join(json.dumps(r) for r in subset) + "\n").encode(), mtime=0)
        filename = dataset + ".pilot.jsonl.gz"
        (inputs / filename).write_bytes(archive)
        batch = {"dataset": dataset, "file": filename, "sha256": hashlib.sha256(archive).hexdigest(),
                 "task_ids": sorted(selected), "samples": {}}
        for condition in ("reference", "negative", *CONDITIONS):
            filename = dataset + "." + condition.replace(":", "_") + ".jsonl"
            if condition == "reference":
                samples = [{"task_id": r["task_id"], "solution": reference_code(r)} for r in subset]
            elif condition == "negative":
                samples = [{"task_id": r["task_id"], "solution": f"def {r['entry_point']}(*args, **kwargs):\n    raise AssertionError('negative control')\n"} for r in subset]
            else:
                samples = [{"task_id": r["task_id"], "solution": r["solution"]} for r in records
                           if r["dataset"] == dataset and r["condition"] == condition]
            write_jsonl(work / filename, samples)
            batch["samples"][condition] = filename
        batches.append(batch)
    save(inputs / "batches.json", batches)
    save(OUTPUT / "static.json", [{k: v for k, v in r.items() if k != "solution"} for r in records])
    return plan, records, batches


def summarize(plan: dict, records: list[dict], batches: list[dict]) -> dict:
    work = OUTPUT / "evaluation"
    controls, results, result_hashes = {}, {}, {}
    for batch in batches:
        for condition, sample in batch["samples"].items():
            path = work / sample.replace(".jsonl", "_eval_results.json")
            data = path.read_bytes()
            result = json.loads(data)
            expected_hash = hashlib.md5((work / "inputs" / batch["file"]).read_bytes()).hexdigest()
            if result["hash"] != expected_hash:
                raise ValueError("Wrong dataset evaluated")
            expected_solutions = {r["task_id"]: r["solution"] for r in
                                  (json.loads(line) for line in (work / sample).read_text(encoding="utf-8").splitlines())}
            if any(len(rows) != 1 or rows[0]["solution"] != expected_solutions.get(task_id)
                   for task_id, rows in result["eval"].items()):
                raise ValueError("Evaluation solution differs from cached answer")
            # Same completeness and one-sample check as reference controls.
            checked = summarize_result(result, set(batch["task_ids"]), condition != "negative")
            result_hashes[path.name] = hashlib.sha256(data).hexdigest()
            if condition in ("reference", "negative"):
                controls[batch["dataset"] + ":" + condition] = checked
                if checked["unexpected"]:
                    raise ValueError("Selected-task evaluator control failed; no model accuracy claim")
            else:
                for task_id, rows in result["eval"].items():
                    row = rows[0]
                    results[(task_id, condition)] = {"base": row["base_status"], "plus": row["plus_status"],
                                                   "base_failed_inputs": len(row["base_fail_tests"]),
                                                   "plus_failed_inputs": len(row["plus_fail_tests"])}
    for row in records:
        row.pop("solution", None)
        row["functional"] = results[(row["task_id"], row["condition"])]
        row["base_pass"] = row["static"]["valid"] and row["functional"]["base"] == "pass"
        row["plus_pass"] = row["base_pass"] and row["functional"]["plus"] == "pass"
        row["strict_plus_pass"] = row["plus_pass"] and row["static"]["single_code_block"]
    baseline = {r["task_id"]: r for r in records if r["condition"] == "general"}
    aggregates = {}
    for condition in CONDITIONS:
        rows = [r for r in records if r["condition"] == condition]
        valid = [r for r in rows if r["static"]["valid"]]
        numeric = ("functions", "comment_tokens", "docstrings", "nonblank_lines")
        races = [k for k in valid[0]["static"] if k.startswith("race_")] if valid else []
        pairs = Counter("win" if r["plus_pass"] > baseline[r["task_id"]]["plus_pass"] else
                        "loss" if r["plus_pass"] < baseline[r["task_id"]]["plus_pass"] else "tie" for r in rows)
        aggregates[condition] = {
            "tasks": len(rows), "valid_answers": len(valid),
            "single_code_block_answers": sum(r["static"]["single_code_block"] for r in rows),
            "strict_base_and_plus_passed": sum(r["strict_plus_pass"] for r in rows),
            "base_passed": sum(r["base_pass"] for r in rows), "base_and_plus_passed": sum(r["plus_pass"] for r in rows),
            "by_dataset": {d: {"tasks": 10, "base_passed": sum(r["base_pass"] for r in rows if r["dataset"] == d),
                               "plus_passed": sum(r["plus_pass"] for r in rows if r["dataset"] == d)} for d in ("humaneval", "mbpp")},
            "paired_plus_vs_general": {k: pairs[k] for k in ("win", "tie", "loss")},
            "mean_static_valid_only": {k: statistics.mean(r["static"][k] for r in valid) for k in numeric} if valid else {},
            "race_pass_counts_valid_only": {k: sum(bool(r["static"][k]) for r in valid) for k in races},
            "mean_output_tokens": statistics.mean(r["usage"]["output_tokens"] for r in rows),
            "mean_latency_seconds": statistics.mean(r["elapsed_seconds"] for r in rows),
            "cost_usd": sum(r["cost_nano_usd"] for r in rows) / 1e9}
    report = {"plan_sha256": sha(plan), "model_settings": plan["settings"], "image": IMAGE,
              "dataset_sha256": plan["dataset_sha256"], "official_fix_sha256": ASSETS["evalplus_fix"]["sha256"],
              "scheduling": "one scheduling thread; official per-candidate guarded child processes",
              "calls": len(records), "tasks": len(baseline), "cost_usd": sum(r["cost_nano_usd"] for r in records) / 1e9,
              "budget_usd": plan["budget_nano_usd"] / 1e9, "billing": "usage times Standard rates; invoice not independently verified; tax/FX excluded",
              "total_input_tokens": sum(r["usage"]["input_tokens"] for r in records),
              "total_output_tokens": sum(r["usage"]["output_tokens"] for r in records),
              "controls": controls, "conditions": aggregates, "rows": records, "result_sha256": result_hashes,
              "limitations": plan["limits"],
              "extraction_note": "Strict score requires one Python block as requested. Supplemental functional/style results use the unique block defining the entry point, excluding standalone usage examples. This supplemental rule was added after observing formatting but before executing any generated answer. No code repairs or test-based selection."}
    save(OUTPUT / "summary.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Run cached answers in local offline Docker; no model calls")
    parser.add_argument("--summarize", action="store_true", help="Summarize existing execution results")
    args = parser.parse_args()
    plan, records, batches = prepare_evaluation()
    work = OUTPUT / "evaluation"
    if args.execute:
        if list(work.glob("*_eval_results.json")):
            raise ValueError("Evaluation results already exist; use --summarize, never overwrite them")
        name = "ppt-luna-pilot-v1"
        command = container_command(work / "inputs", work, name)
        save(work / "execution.json", {"command": command, "model_api_calls": 0,
                                      "driver_sha256": hashlib.sha256((work / "inputs/controls.py").read_bytes()).hexdigest()})
        print(f"Evaluation log: {work / 'execution.log'}", flush=True)
        try:
            with (work / "execution.log").open("w", encoding="utf-8") as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=1200)
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "rm", "--force", name], capture_output=True, timeout=30)
            raise
    if args.execute or args.summarize:
        report = summarize(plan, records, batches)
        print(json.dumps({k: report[k] for k in ("calls", "cost_usd", "conditions")}, indent=2))
    else:
        print(json.dumps({"answers": len(records), "valid": sum(r["static"]["valid"] for r in records), "model_api_calls": 0}))


if __name__ == "__main__":
    main()

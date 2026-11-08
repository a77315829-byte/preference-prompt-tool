"""Run free EvalPlus reference/negative controls in a pinned, offline container.

This runner cannot generate model answers. Pull the documented image separately.
Only the public dataset folder and a fresh result directory enter the container.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import uuid

from .run import ASSETS, CACHE, asset_bytes, audit_dataset, reference_code, write_jsonl

IMAGE = "ganler/evalplus@sha256:26b118098bef281fe8dfe999bf05f1d5b45374b4e6c00161ec0f30592aef4740"
PACKAGE_VERSION = "0.4.0.dev2"  # Actual package in the publisher's v0.3.1-tagged image.


def summarize_result(result: dict, task_ids: set[str], expected_pass: bool) -> dict:
    evaluations = result["eval"]
    if not task_ids or set(evaluations) != task_ids or any(len(rows) != 1 for rows in evaluations.values()):
        raise ValueError("Missing, extra or repeated control results")
    base, plus, unexpected = 0, 0, []
    for task_id, rows in evaluations.items():
        row = rows[0]
        base_pass = row["base_status"] == "pass"
        combined_pass = base_pass and row["plus_status"] == "pass"
        base += base_pass
        plus += combined_pass
        if (base_pass != expected_pass or combined_pass != expected_pass
                or (not expected_pass and row["base_status"] != "fail")):
            unexpected.append({"task_id": task_id, "base": row["base_status"], "plus": row["plus_status"]})
    return {"tasks": len(task_ids), "base_passed": base, "base_and_plus_passed": plus,
            "base_pass_at_1": base / len(task_ids), "plus_pass_at_1": plus / len(task_ids),
            "unexpected": unexpected}


def container_command(cache: Path, output: Path, name: str, apply_fix: bool = True,
                      full_mbpp: bool = False) -> list[str]:
    command = [
        "docker", "run", "--rm", "--pull=never", "--name", name,
        "--network=none", "--read-only", "--user", "1000:1000",
        "--cpus=2", "--memory=3g", "--pids-limit=128", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--tmpfs", "/tmp:rw,exec,size=256m,mode=1777",
        "--mount", f"type=bind,source={cache.resolve()},target=/datasets,readonly",
        "--mount", f"type=bind,source={output.resolve()},target=/work",
        "--workdir=/work", "--env", "HOME=/tmp", "--env", "XDG_CACHE_HOME=/work/cache",
        "--env", "PYTHONUNBUFFERED=1", "--env", "PYTHONDONTWRITEBYTECODE=1",
        "--env", "OPENBLAS_NUM_THREADS=1", "--env", "OMP_NUM_THREADS=1",
        "--env", f"HUMANEVAL_OVERRIDE_PATH=/datasets/{ASSETS['humaneval']['file']}",
        "--env", f"MBPP_OVERRIDE_PATH=/datasets/{ASSETS['mbpp' if full_mbpp else 'mbpp_noextreme']['file']}",
    ]
    if apply_fix:
        command += ["--mount", f"type=bind,source={(cache / ASSETS['evalplus_fix']['file']).resolve()},"
                    "target=/usr/local/lib/python3.11/site-packages/evalplus/eval/__init__.py,readonly"]
    return command + [IMAGE, "python", "/datasets/controls.py"]


def verify_official_fix(data: bytes) -> None:
    """Verify the upstream fix differs from the image in exactly two lines."""
    source = data.decode("utf-8").replace("\r\n", "\n")
    old = "                            assert abs(_poly(*inp, out)) <= atol\n                            continue"
    new = old.replace("                            continue", "                            details[i] = True\n"
                      "                            progress.value += 1\n                            continue")
    if source.count(new) != 1:
        raise ValueError("Unexpected official fix")
    before = source.replace(new, old)
    if hashlib.sha256(before.encode()).hexdigest() != "e9d4960c7da3547e2dbd20a1a3aa8bbea77f2caf16215b600a0a9ef5e14bfd80":
        raise ValueError("Official fix changes more than result bookkeeping")
    compile(ast.parse(source), "<official-evalplus-fix>", "exec")


def prepare_batches(datasets: dict, inputs: Path, output: Path) -> list[dict]:
    batches = []
    for dataset, rows in datasets.items():
        size = 50 if dataset == "mbpp" else 164
        for index, start in enumerate(range(0, len(rows), size)):
            subset = rows[start:start + size]
            stem = f"{dataset}.batch{index:02}"
            data = gzip.compress(("\n".join(json.dumps(row) for row in subset) + "\n").encode(), mtime=0)
            filename = stem + ".jsonl.gz"
            (inputs / filename).write_bytes(data)
            batch = {"dataset": dataset, "index": index, "file": filename,
                     "sha256": hashlib.sha256(data).hexdigest(), "task_ids": [row["task_id"] for row in subset]}
            for control in ("reference", "negative"):
                batch[control] = f"{stem}.{control}.jsonl"
                samples = [{"task_id": row["task_id"], "solution": reference_code(row) if control == "reference" else
                            f"def {row['entry_point']}(*args, **kwargs):\n    raise AssertionError('negative control')\n"}
                           for row in subset]
                write_jsonl(output / batch[control], samples)
            batches.append(batch)
    (inputs / "batches.json").write_text(json.dumps(batches, indent=2) + "\n", encoding="utf-8")
    return batches


def run(cache: Path = CACHE, apply_fix: bool = True, full_mbpp: bool = False,
        dataset: str = "humaneval") -> dict:
    # Read and verify inputs before starting any code execution.
    datasets = {}
    selected = {"humaneval": "humaneval", "mbpp": "mbpp" if full_mbpp else "mbpp_noextreme"}
    if dataset != "both":
        selected = {dataset: selected[dataset]}
    for name, asset in selected.items():
        datasets[name], _ = audit_dataset(asset, asset_bytes(asset, cache))
    if apply_fix:
        verify_official_fix(asset_bytes("evalplus_fix", cache))
    subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], check=True,
                   capture_output=True, text=True, timeout=30)
    subprocess.run(["docker", "image", "inspect", IMAGE], check=True,
                   capture_output=True, text=True, timeout=30)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    output = cache / "evalplus-runs" / run_id
    output.mkdir(parents=True, exist_ok=False)
    # Mount only the two public archives, rather than the application's data folder.
    inputs = output / "inputs"
    inputs.mkdir()
    for asset in selected.values():
        shutil.copyfile(cache / ASSETS[asset]["file"], inputs / ASSETS[asset]["file"])
    if apply_fix:
        shutil.copyfile(cache / ASSETS["evalplus_fix"]["file"], inputs / ASSETS["evalplus_fix"]["file"])
    driver = Path(__file__).with_name("container_controls.py")
    compile(ast.parse(driver.read_text(encoding="utf-8")), str(driver), "exec")
    shutil.copyfile(driver, inputs / "controls.py")
    batches = prepare_batches(datasets, inputs, output)
    name = "ppt-evalplus-free-" + run_id.lower()
    command = container_command(inputs, output, name, apply_fix, full_mbpp)
    metadata = {"image": IMAGE, "package_version": PACKAGE_VERSION,
                "publisher_image_tag": "v0.3.1 (tag differs from installed package version)",
                "run_id": run_id, "model_api_calls": 0,
                "model_api_cost_usd": 0, "scope": "evaluation harness controls, not project prompt effectiveness",
                "dataset_variants": selected,
                "dataset_sha256": {name: ASSETS[asset]["sha256"] for name, asset in selected.items()},
                "official_fix": ASSETS["evalplus_fix"] if apply_fix else None,
                "driver_sha256": hashlib.sha256(driver.read_bytes()).hexdigest(),
                "scheduling": "One ThreadPoolExecutor scheduling worker; official per-candidate guarded child processes remain enabled. Avoids copying large oracle outputs through the process-pool queue.",
                "batches": batches,
                "command": command}
    (output / "execution.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"EvalPlus log: {output / 'execution.log'}", flush=True)
    try:
        with (output / "execution.log").open("w", encoding="utf-8") as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=1800)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "rm", "--force", name], capture_output=True, timeout=30)
        raise
    summaries = {}
    for dataset, rows in datasets.items():
        summaries[dataset] = {}
        for control in ("reference", "negative"):
            combined, result_hashes = {}, {}
            for batch in (b for b in batches if b["dataset"] == dataset):
                filename = batch[control].replace(".jsonl", "_eval_results.json")
                raw = (output / filename).read_bytes()
                result = json.loads(raw)
                expected_hash = hashlib.md5((inputs / batch["file"]).read_bytes()).hexdigest()
                if result["hash"] != expected_hash:
                    raise ValueError("EvalPlus evaluated a different dataset")
                summarize_result(result, set(batch["task_ids"]), control == "reference")
                if set(combined) & set(result["eval"]):
                    raise ValueError("Duplicate task across batches")
                combined.update(result["eval"])
                result_hashes[filename] = hashlib.sha256(raw).hexdigest()
            summary = summarize_result({"eval": combined}, {row["task_id"] for row in rows}, control == "reference")
            summary["result_sha256"] = result_hashes
            summaries[dataset][control] = summary
    metadata["results"] = summaries
    metadata["status"] = "passed" if all(not s["unexpected"] for values in summaries.values() for s in values.values()) else "unexpected_results"
    (output / "summary.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": metadata["status"], "results": summaries, "output": str(output)}, indent=2))
    return metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-controls", action="store_true", help="Execute free public controls in Docker; no API calls")
    parser.add_argument("--cache", type=Path, default=CACHE)
    parser.add_argument("--dataset", choices=("humaneval", "mbpp", "both"), default="humaneval",
                        help="HumanEval controls pass on this PC; MBPP/255 remains an unresolved extra-test failure")
    parser.add_argument("--original-evaluator", action="store_true", help="Reproduce the original image's HumanEval/32 bookkeeping bug")
    parser.add_argument("--full-mbpp", action="store_true", help="Include extreme MBPP+ inputs; may exceed laptop memory")
    args = parser.parse_args()
    if not args.execute_controls:
        print(f"Required image: {IMAGE}\nUse --execute-controls to run the local, free harness checks.")
    elif run(args.cache, not args.original_evaluator, args.full_mbpp, args.dataset)["status"] != "passed":
        raise SystemExit(1)

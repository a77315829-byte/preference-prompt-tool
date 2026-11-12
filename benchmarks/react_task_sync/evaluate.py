"""Run locked checks only after the parent has reviewed an agent's actual diff."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "tmp/react-task-sync-20261109"
CHECKS = ROOT / "benchmarks/react_task_sync/acceptance.test.mjs"


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def timestamp(payload):
    if isinstance(payload, str):
        return payload
    for key in ("at", "utc", "timestamp", "started_at", "finished_at", "started_at_utc", "finished_at_utc", "startedAt", "finishedAt"):
        if key in payload:
            return payload[key]
    raise ValueError("Timestamp key must be recorded explicitly")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("arm", choices=("arm_a", "arm_b"))
    parser.add_argument("--reviewed", action="store_true", help="Parent has reviewed candidate production code before execution")
    args = parser.parse_args()
    if not args.reviewed:
        parser.error("Review the candidate code before execution, then pass --reviewed")
    protocol = json.loads((CHECKS.parent / "protocol.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(CHECKS.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    if digest != protocol["acceptance_sha256"]:
        raise SystemExit("Acceptance tests changed after preregistration")
    arm = RUN / args.arm
    dest = RUN / (args.arm + "-evaluation.json")
    if dest.exists():
        raise SystemExit("A cached evaluation exists. Preserve it; do not silently rerun an arm.")
    started = json.loads((arm / "started.json").read_text(encoding="utf-8-sig"))
    finished = json.loads((arm / "finished.json").read_text(encoding="utf-8-sig"))
    start_time, finish_time = (datetime.fromisoformat(timestamp(v).replace("Z", "+00:00")) for v in (started, finished))
    env = dict(os.environ, PPT_REACT_BENCH_TARGET=str(arm / "frontend"))
    before, tick = iso_now(), time.perf_counter()
    process = subprocess.run(["node", "--test", "--test-reporter=tap", str(CHECKS)], cwd=ROOT, env=env,
                             capture_output=True, text=True, encoding="utf-8", timeout=120)
    elapsed = time.perf_counter() - tick
    log = process.stdout + process.stderr
    (RUN / (args.arm + ".tap")).write_text(log, encoding="utf-8")
    cases = [{"name": name, "passed": state == "ok"} for state, name in
             re.findall(r"^(ok|not ok) \d+ - (R\d+[^\r\n]+)", log, flags=re.MULTILINE)]
    result = {"arm": args.arm, "candidate_started": timestamp(started), "candidate_finished": timestamp(finished),
              "agent_work_seconds": round((finish_time - start_time).total_seconds(), 3),
              "evaluation_started": before, "evaluation_seconds": round(elapsed, 3),
              "command_exit_code": process.returncode, "test_sha256": digest, "cases": cases,
              "passed": sum(case["passed"] for case in cases), "total": len(cases),
              "human_edit_seconds": None, "paid_api_requests": 0,
              "candidate_component_sha256": hashlib.sha256((arm / "frontend/src/features/coding-instructions/CodingTrialPanel.jsx").read_bytes()).hexdigest(),
              "agent_record": finished}
    if len(cases) != 9:
        result["evaluation_error"] = "Expected all 9 locked tests; execution/collection failure is not a functional score"
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""Keep prompts, candidate diffs and measured outputs without rerunning agents."""
import difflib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "tmp/react-task-sync-20261109"
DEST = ROOT / "benchmarks/react_task_sync/results/2026-11-09"
COMPONENT = "frontend/src/features/coding-instructions/CodingTrialPanel.jsx"


def log_text(filename):
    raw = filename.read_text(encoding="utf-8").replace(str(ROOT), "$REPO")
    return "\n".join(line.rstrip() for line in raw.splitlines()) + "\n"


def main():
    manifest = json.loads((RUN / "manifest.json").read_text(encoding="utf-8"))
    archive = subprocess.check_output(["git", "archive", "--format=zip", manifest["baseline_commit"], "frontend"], cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        original = {name: bundle.read(name) for name in bundle.namelist() if not name.endswith("/")}
    # Derived artifacts may be regenerated from the immutable cached runs.
    DEST.mkdir(parents=True, exist_ok=True)
    results = []
    for arm, condition in manifest["assignment"].items():
        evaluation = json.loads((RUN / (arm + "-evaluation.json")).read_text(encoding="utf-8"))
        changed = [name for name, data in original.items() if (RUN / arm / name).read_bytes() != data]
        if changed != [COMPONENT]:
            raise ValueError(f"Unexpected tracked changes in {arm}: {changed}")
        candidate = (RUN / arm / COMPONENT).read_text(encoding="utf-8")
        if hashlib.sha256((RUN / arm / COMPONENT).read_bytes()).hexdigest() != evaluation["candidate_component_sha256"]:
            raise ValueError("Candidate was modified after external evaluation")
        baseline = original[COMPONENT].decode("utf-8").replace("\r\n", "\n")
        difference = list(difflib.unified_diff(baseline.splitlines(True), candidate.splitlines(True),
                                              fromfile="a/" + COMPONENT, tofile="b/" + COMPONENT))
        (DEST / (arm + ".patch")).write_text("".join(difference), encoding="utf-8")
        (DEST / (arm + "-prompt.txt")).write_text((RUN / arm / "TASK.txt").read_text(encoding="utf-8"), encoding="utf-8")
        (DEST / (arm + ".tap")).write_text(log_text(RUN / (arm + ".tap")), encoding="utf-8")
        results.append({**evaluation, "condition": condition, "changed_existing_files": changed,
                        "production_added_lines": sum(s.startswith("+") and not s.startswith("+++") for s in difference),
                        "production_removed_lines": sum(s.startswith("-") and not s.startswith("---") for s in difference)})
    (DEST / "baseline.tap").write_text(log_text(RUN / "baseline.tap"), encoding="utf-8")
    (DEST / "summary.json").write_text(json.dumps({"baseline_commit": manifest["baseline_commit"], "profile": manifest["profile"],
        "runs": results, "paid_api_requests": 0, "human_edit_seconds": None,
        "log_normalization": "Repository path replaced with $REPO; line endings and trailing whitespace normalized; test outcomes unchanged.",
        "delta_agent_seconds_personalized_minus_general": round(results[1]["agent_work_seconds"] - results[0]["agent_work_seconds"], 3),
        "protocol_deviation": "arm_b temporarily wrote a compiler output to shared node_modules and removed it; verified absent by parent. No tracked dependency files changed. This is not complete filesystem isolation.",
        "inference": "Single-case description only; no demonstrated preference, speed or general accuracy advantage."}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"directory": str(DEST), "runs": [{k: row[k] for k in ("condition", "agent_work_seconds", "passed", "total", "production_added_lines", "production_removed_lines")} for row in results]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

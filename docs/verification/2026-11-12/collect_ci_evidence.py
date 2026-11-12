"""Package completed CI metadata and the existing offline rerun; no API calls."""
from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "ci"
QA = ROOT / "tmp/weekly_2026_11_13/v0_6"
AUDIT = ROOT / "tmp/ci-skip-audit-20261112"
COMMIT = "c7848083c4c0931fb7c3f649e3f4087685e31a11"


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    OUT.mkdir(exist_ok=True)
    runs = {}
    for name in ["push", "pr", "container"]:
        data = json.loads((QA / f"{name}.json").read_text(encoding="utf-8-sig"))
        assert data["headSha"] == COMMIT
        assert data["status"] == "completed" and data["conclusion"] == "success"
        assert all(job["conclusion"] == "success" for job in data["jobs"])
        runs[name] = data
    save("runs.json", runs)
    counts = {}
    for name, log in [("push", ROOT / "tmp/ci-20261112/push.log"), ("pr", QA / "pr.log")]:
        lines = log.read_text(encoding="utf-8-sig").splitlines()
        relevant = [line for line in lines if "\tRun tests without API\t" in line
                    or ("\tFrontend unit tests\t" in line and re.search(r"# (tests|pass|fail|skipped) ", line))]
        text = "\n".join(relevant) + "\n"
        match = re.search(r"(\d+) passed, (\d+) skipped, (\d+) deselected in ([\d.]+)s", text)
        assert match and tuple(map(int, match.groups()[:3])) == (1353, 3, 16)
        assert re.search(r"# tests 123\b", text) and re.search(r"# fail 0\b", text)
        counts[name] = {"backend_passed": 1353, "backend_skipped": 3,
                        "api_deselected": 16, "frontend_passed": 123,
                        "failed": 0, "backend_seconds": float(match.group(4)),
                        "original_log_sha256": hashlib.sha256(log.read_bytes()).hexdigest()}
        (OUT / f"{name}-test-excerpt.log").write_text(text, encoding="utf-8")
    for name in ["comparison.json", "collected.json", "focused.log", "focused.xml", "focused-guard.json"]:
        (OUT / name).write_bytes((AUDIT / name).read_bytes())
    comparison = json.loads((OUT / "comparison.json").read_text(encoding="utf-8"))
    suite = ET.parse(OUT / "focused.xml").getroot().find("testsuite")
    assert (suite.get("tests"), suite.get("failures"), suite.get("errors"), suite.get("skipped")) == ("3", "0", "0", "0")
    assert all(row["previous_local_outcome"] == "passed" for row in comparison["ci_skips"])
    guard = json.loads((OUT / "focused-guard.json").read_text(encoding="utf-8"))
    assert guard["pytest_exit_code"] == 0 and guard["network_attempts"] == []
    focused_log = (OUT / "focused.log").read_text(encoding="utf-8")
    elapsed = float(re.search(r"3 passed in ([\d.]+)s", focused_log).group(1))
    receipts = json.loads((OUT.parent / "results/source-hashes.json").read_text(encoding="utf-8"))
    assert all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest for path, digest in receipts.items())
    summary = {
        "verified_commit": COMMIT, "evidence_date": "2026-11-12",
        "runs": {name: {"url": run["url"], "conclusion": run["conclusion"]} for name, run in runs.items()},
        "ci": counts,
        "local_full": {"passed": 1355, "skipped": 1, "api_deselected": 16},
        "focused_rerun": {"passed": 3, "failed": 0, "skipped": 0, "seconds": elapsed,
                          "test_names": [row["test"] for row in comparison["ci_skips"]]},
        "ci_skip_reasons": {"MACSum_files_not_committed": 2, "RACE_EvalPlus_cache_not_committed": 1},
        "windows_symlink_check_passed_in_ci": True,
        "verified_source_hashes_unchanged": len(receipts),
        "paid_model_api_calls": 0, "focused_network_attempts": 0,
        "limitations": ["The three reruns overlap with the previous local full run; do not add test counts.",
                        "Container smoke tests are not public deployment or human usability validation.",
                        "The RACE/EvalPlus cached audit checks assets and preparation, not new generated-code execution."]
    }
    summary["artifact_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "results.json"}
    save("results.json", summary)
    print(json.dumps({"runs": 3, "all_success": True, "focused_passed": 3, "seconds": elapsed}))


if __name__ == "__main__":
    main()

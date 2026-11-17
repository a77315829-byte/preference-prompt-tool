"""Preserve successful local readiness evidence without copying accounts or DBs."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "tmp/readiness-20261117"
OUT = Path(__file__).with_name("results")
OUT.mkdir(exist_ok=True)
TARGETS = {
    ("tests.test_checks_vs_labels", "test_recompute_matches_saved"),
    ("tests.test_persona", "test_personas_come_from_real_macsum_attributes"),
    ("tests.test_coding_public", "test_full_cached_audit_is_offline_and_preserves_unknown_outcomes"),
}


def suite(path):
    cases = list(ET.parse(path).iter("testcase"))
    assert cases and not any(c.find("failure") is not None or c.find("error") is not None for c in cases), path
    return cases


before = suite(ROOT / "docs/verification/2026-11-17/results/full.xml")
previous = [c for c in before if (c.get("classname"), c.get("name")) in TARGETS]
assert len(previous) == 3 and all(c.find("skipped") is None for c in previous)
focused = suite(RUN / "skipped-recheck.xml")
assert len(focused) == 3 and all(c.find("skipped") is None for c in focused)
snapshot_tests = suite(RUN / "snapshot.xml")
assert len(snapshot_tests) == 7 and all(c.find("skipped") is None for c in snapshot_tests)
full = suite(RUN / "full.xml")
full_log = (ROOT / "tmp/readiness-full.log").read_text(encoding="utf-8")
counts = re.search(r"(\d+) passed, (\d+) skipped, (\d+) deselected", full_log)
assert counts, full_log[-300:]
frontend_log = (ROOT / "tmp/readiness-frontend.log").read_text(encoding="utf-8")
assert re.search(r"# fail 0\b", frontend_log)
frontend_count = int(re.search(r"# pass (\d+)", frontend_log)[1])
build_log = (ROOT / "tmp/readiness-build.log").read_text(encoding="utf-8")
assert "built in" in build_log
browser = json.loads((RUN / "ui/browser.json").read_text(encoding="utf-8"))
assert len(browser["results"]) == 6 and all(row["pass"] for row in browser["results"])
assert not browser["errors"] and not browser["external"]
storage_path = max(RUN.glob("storage-*/results.json"), key=lambda p: p.stat().st_mtime)
storage = json.loads(storage_path.read_text(encoding="utf-8"))
assert storage["complete"] and len(storage["results"]) == 10 and all(row["pass"] for row in storage["results"])
files = {
    ROOT / "tmp/readiness-skipped-recheck.log": "skipped-recheck.log",
    RUN / "skipped-recheck.xml": "skipped-recheck.xml",
    RUN / "snapshot.xml": "snapshot.xml", RUN / "full.xml": "full.xml",
    ROOT / "tmp/readiness-full.log": "full.log", ROOT / "tmp/readiness-frontend.log": "frontend.log",
    ROOT / "tmp/readiness-build.log": "build.log", RUN / "ui/browser.json": "browser.json",
    storage_path: "storage.json", ROOT / "tmp/readiness-storage.log": "storage.log",
    RUN / "pytest-offline-guard.json": "offline-guard.json",
}
for path in (RUN / "ui").glob("0*.png"):
    files[path] = path.name
for source, filename in files.items():
    shutil.copyfile(source, OUT / filename)
source_files = [
    "scripts/storage_snapshot.py", "tests/test_storage_snapshot.py", "api_server.py", "summary_contracts_v2.py",
    "frontend/src/features/comparison/ComparisonSection.jsx",
    "frontend/src/features/comparison/SummaryContractPanel.jsx",
    "frontend/src/features/comparison/summaryContract.test.js",
    "frontend/src/features/preferences/SavePreferencePanel.jsx",
    ".github/workflows/tests.yml", ".github/workflows/hosting.yml",
    "requirements.txt", "requirements-dev.txt", "frontend/package-lock.json",
]
receipt = {
    "date": "2026-11-17", "baseline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "tested_tree": "baseline plus source files identified below; not an already published commit",
    "previous_local_three_passed": True, "three_current_recheck_passed": True,
    "rechecked_tests": ["::".join(t) for t in sorted(TARGETS)],
    "snapshot_tests_passed": 7,
    "python": dict(zip(("passed", "skipped", "api_excluded"), map(int, counts.groups()))),
    "frontend_passed": frontend_count, "build_passed": True, "browser_passed": 6, "storage_rehearsal_passed": 10,
    "paid_model_api_calls": 0, "real_user_data_used": False,
    "source_lf_sha256": {name: hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest() for name in source_files},
    "artifact_sha256": {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest() for name in files.values()},
    "limitations": ["No human/team rehearsal or usability study", "No paid/live model calls or public deployment",
                    "Existing PDFs and frozen experiments unchanged", "Windows clipboard comparison normalizes CRLF to LF",
                    "Clean-container installation is recorded separately by exact-commit GitHub Actions"],
}
(OUT / "validation.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in receipt.items() if "sha256" not in k}, ensure_ascii=False, indent=2))

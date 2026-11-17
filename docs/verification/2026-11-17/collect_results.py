"""Collect completed offline checks without running or changing any tests."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "tmp/weekly-20261117"
OUT = Path(__file__).resolve().parent / "results"
OUT.mkdir(exist_ok=True)

xml = ET.parse(RUN / "full.xml").getroot()
cases = xml.findall(".//testcase")
assert not xml.findall(".//failure") and not xml.findall(".//error")
skipped = [{"name": case.attrib["name"], "reason": case.find("skipped").attrib.get("message", "")}
           for case in cases if case.find("skipped") is not None]
python_log = (RUN / "full-offline.log").read_text(encoding="utf-8-sig")
summary = re.search(r"(\d+) passed, (\d+) skipped, (\d+) deselected", python_log)
assert summary and int(summary[1]) == len(cases) - len(skipped)
front = (RUN / "frontend-final.log").read_text(encoding="utf-8-sig")
assert re.search(r"# fail 0\b", front)
frontend_passed = int(re.search(r"# pass (\d+)", front)[1])
build = (RUN / "build.log").read_text(encoding="utf-8-sig")
assert "built in" in build
browser = json.loads((RUN / "browser/results.json").read_text())
assert len(browser["results"]) == 6 and all(case["pass"] for case in browser["results"])
assert not browser["errors"] and not browser["external"]
guard = json.loads((RUN / "pytest-offline-guard.json").read_text())
assert guard["dotenv_disabled"] and guard["model_credentials_removed"] and guard["model_live_flags_disabled"]
documents = json.loads((RUN / "document-checks.json").read_text(encoding="utf-8"))
assert not documents["missing_local_links"] and documents["wbs_ids_names_plan_dates_preserved"]

paths = ["api_server.py", "app.py", "preference_comparison.py", "domains/coding.yaml", "domains/coding/v2.yaml", "CLAUDE.md",
         "frontend/src/app/App.jsx", "frontend/src/features/comparison/ComparisonSection.jsx",
         "frontend/src/features/comparison/codingApi.js", "frontend/src/features/comparison/comparisonAccess.test.js",
         "frontend/src/features/preferences/TeamPreferenceComparison.jsx",
         "frontend/test-support/appHarness.js", "tests/conftest.py", "tests/test_comparison_access.py",
         "tests/test_coding_prompt_alignment_v2.py", "tests/test_review_fixes.py",
         "tests/test_summary_grounded_integration.py", "tests/test_server_exposure.py",
         "tests/test_task_preferences.py", "tests/test_team.py", "tests/test_team_invitations.py"]
hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}
normalized_hashes = {path: hashlib.sha256((ROOT / path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                     for path in paths}
old_domain = subprocess.check_output(["git", "show", "4b40d11:domains/coding.yaml"], cwd=ROOT)
assert old_domain.decode().replace("\r\n", "\n") == (ROOT / "domains/coding.yaml").read_text(encoding="utf-8")
for name in ("full-offline.log", "full.xml", "frontend-final.log", "build.log", "pytest-offline-guard.json", "document-checks.json"):
    shutil.copyfile(RUN / name, OUT / name)
for name in ("results.json", "summary-result.png", "revoked-result.png"):
    shutil.copyfile(RUN / "browser" / name, OUT / ("browser.json" if name == "results.json" else name))
result = {
    "date": "2026-11-17", "baseline_commit": "4b40d115141709f8aeb7840a301e02fc206c408a",
    "scope": "comparison ownership/expiry and React prompt language alignment; local synthetic verification",
    "python": {"passed": int(summary[1]), "skipped": int(summary[2]), "api_deselected": int(summary[3]), "skip_details": skipped},
    "frontend": {"passed": frontend_passed, "failed": 0}, "build_passed": True,
    "browser": {"passed": 6, "failed": 0, "page_errors": [], "external_requests": []},
    "paid_model_api_calls": 0, "legacy_domain_preserved": True,
    "source_sha256": hashes,
    "source_lf_normalized_sha256": normalized_hashes,
    "documents": documents,
    "limitations": ["No human preference, usability, time saving, or adoption measurement",
                    "Windows-specific skip is retained; real model API tests excluded",
                    "Existing bundle size warning remains; no production deployment or complete security audit",
                    "Initial network-restricted run and an interrupted diagnostic run are not counted as passed",
                    "Published design/WBS PDFs remain prior snapshots; edited source and dated update are separate"],
}
(OUT / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({key: result[key] for key in ("python", "frontend", "build_passed", "browser", "paid_model_api_calls")}, ensure_ascii=False))

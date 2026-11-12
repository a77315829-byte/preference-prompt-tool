"""Collect local test evidence without rerunning tests or reading user data."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "tmp/summary-policy-20261112"
OUT = Path(__file__).resolve().parent / "results"


def xml_result(name):
    suites = ET.parse(RUN / name).getroot().findall("testsuite")
    result = {key: sum(int(suite.get(key, 0)) for suite in suites)
              for key in ("tests", "failures", "errors", "skipped")}
    result["passed"] = result["tests"] - result["failures"] - result["errors"] - result["skipped"]
    result["seconds"] = sum(float(suite.get("time", 0)) for suite in suites)
    result["skip_details"] = [{"name": case.get("name"), "reason": case.find("skipped").get("message")}
                              for suite in suites for case in suite.findall("testcase") if case.find("skipped") is not None]
    assert result["failures"] == result["errors"] == 0, result
    return result


def main():
    full = xml_result("full.xml")
    focused = xml_result("focused.xml")
    frontend = (RUN / "frontend.log").read_text(encoding="utf-8-sig")
    front = {key: int(re.search(rf"^# {key} (\d+)$", frontend, re.M)[1]) for key in ("tests", "pass", "fail", "skipped")}
    assert front["fail"] == 0
    browser = json.loads((RUN / "browser/results.json").read_text(encoding="utf-8"))
    assert len(browser["results"]) == 8 and all(case["pass"] for case in browser["results"])
    assert not browser["errors"]
    build = (RUN / "build.log").read_text(encoding="utf-8-sig")
    assert "built in" in build
    guard = json.loads((RUN / "pytest-offline-guard.json").read_text(encoding="utf-8"))
    assert guard["dotenv_disabled"] and guard["model_credentials_removed"] and guard["model_live_flags_disabled"]
    baseline = json.loads((ROOT / "docs/verification/2026-11-12/results/source-hashes.json").read_text(encoding="utf-8"))
    changed = [name for name, sha in baseline.items() if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != sha]
    allowed = {"api_server.py", "frontend/src/features/comparison/ComparisonSection.jsx", "frontend/src/features/comparison/SummaryContractPanel.jsx",
               "frontend/src/features/comparison/comparison.css", "frontend/src/features/comparison/summaryContract.test.js"}
    assert set(changed) <= allowed, changed
    sources = sorted(allowed | {"summary_contracts.py", "domains/summary_contract.yaml", "summary_contracts_v2.py", "summary_input_policy.py", "domains/summary_contract/v2.yaml", "frontend/src/features/comparison/summaryInputPolicy.js", "frontend/src/features/comparison/comparison.css"})
    result = {"date": "2026-11-12", "scope": "Summary product input and conflict policy v2; deterministic technical checks, not model-output or human preference evaluation",
              "backend_full": full, "backend_focused": focused, "frontend": front,
              "browser_passed": len(browser["results"]), "build": "passed; existing >500kB chunk warning remains",
              "offline_guard": guard,
              "source_baseline": {"count": len(baseline), "changed": changed, "unchanged": len(baseline) - len(changed)},
              "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources}}
    OUT.mkdir(exist_ok=True)
    (OUT / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copyfile(RUN / "browser/results.json", OUT / "browser.json")
    for name in ("full.log", "frontend.log", "build.log"):
        shutil.copyfile(RUN / name, OUT / name)
    for name in ("source-limit.png", "short-source-conflict.png", "mobile-conflict.png"):
        shutil.copyfile(RUN / "browser" / name, OUT / name)
    print(json.dumps({"backend": full, "frontend": front, "browser_passed": 8, "baseline_changed": changed}, ensure_ascii=False))


if __name__ == "__main__":
    main()

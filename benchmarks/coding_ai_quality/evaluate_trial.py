"""Compile and exercise the frozen local coding-A/B pilot; never call an API."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from checks.coding import inline_pseudo_conflicts


FRONTEND = ROOT / "frontend"
TRIAL = ROOT / "data" / "coding_ai_quality_trial.json"
OUTPUT = ROOT / "data" / "coding_ai_quality_stage4.json"
FENCE = re.compile(r"```(tsx|ts|css)\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
FILENAME = re.compile(r"(?:`|//\s*)([A-Za-z][A-Za-z0-9_.-]*\.(?:tsx|ts|css))(?:`|\s|$)")
HEADING_FILENAME = re.compile(r"(?<![\w./])([A-Za-z][A-Za-z0-9_.-]*\.(?:tsx|ts|css))(?![\w.])")
ENTRY = {
    "counter_reset": "Counter.tsx",
    "product_search": "ProductSearch.tsx",
    "signup_validation": "SignupForm.tsx",
    "todo_toggle": "TodoList.tsx",
    "confirm_dialog": "ConfirmDialog.tsx",
    "text_preview": "TextPreview.tsx",
    "password_visibility": "PasswordVisibility.tsx",
    "faq_toggle": "FaqToggle.tsx",
    "faq_multi": "FAQ.tsx",
    "cart_quantity": "CartQuantity.tsx",
}


def extract_files(answer: str, default_name: str) -> dict[str, str]:
    """Use explicit code-fence labels; never interpret prose as executable code."""
    files: dict[str, str] = {}
    for match in FENCE.finditer(answer):
        language, code = match.groups()
        preceding_lines = answer[:match.start()].rstrip().splitlines()
        heading = preceding_lines[-1] if preceding_lines else ""
        candidates = HEADING_FILENAME.findall(heading)
        name = candidates[-1] if candidates else default_name
        first_line = code.splitlines()[0] if code.splitlines() else ""
        comment = FILENAME.search(first_line)
        if comment:
            name = comment.group(1)
        extension = name.rsplit(".", 1)[-1].lower()
        if extension != language.lower() and not (extension == "ts" and language.lower() == "tsx"):
            raise ValueError(f"Filename/extension mismatch: {name}, {language}")
        if name in files:
            raise ValueError(f"Duplicate file: {name}")
        files[name] = code
    resolve_entry(files, default_name)
    return files


def resolve_entry(files: dict[str, str], default_name: str) -> str:
    """Accept a renamed React entry only when it is unambiguous."""
    if default_name in files:
        return default_name
    candidates = [name for name, source in files.items()
                  if name.endswith(".tsx") and (
                      re.search(r"\bexport\s+default\b", source)
                      or re.search(r"\bexport\s+(?:function|const)\s+[A-Z]\w*", source)
                  )]
    if len(candidates) != 1:
        raise ValueError(f"Missing entry file: {default_name}")
    return candidates[0]


def run(command: list[str], *, cwd: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=30, check=False)
    except subprocess.TimeoutExpired:
        return False, "Timed out after 30 seconds"
    return result.returncode == 0, (result.stdout + result.stderr).strip()[:4000]


def evaluate_candidate(task: str, answer: str, slot: str, folder: Path) -> dict:
    files = extract_files(answer, ENTRY[task])
    entry = resolve_entry(files, ENTRY[task])
    for name, source in files.items():
        (folder / name).write_text(source, encoding="utf-8")
    tsc = FRONTEND / "node_modules/.bin/tsc"
    esbuild = FRONTEND / "node_modules/.bin/esbuild"
    type_command = [str(tsc), "--noEmit", "--strict", "--skipLibCheck", "--esModuleInterop",
                    "--jsx", "react-jsx", "--target", "es2020", "--module", "esnext",
                    "--moduleResolution", "bundler", entry]
    type_ok, type_output = run(type_command, cwd=folder)
    bundle = folder / "bundle.cjs"
    build_ok, build_output = run([str(esbuild), entry, "--bundle", "--platform=node", "--format=cjs",
                                  "--jsx=automatic",
                                  "--external:react", "--external:react/jsx-runtime",
                                  "--loader:.css=empty", f"--outfile={bundle}"], cwd=folder)
    result = {"slot": slot, "entry": entry, "files": sorted(files), "typecheck": type_ok,
              "typecheck_output": type_output, "build": build_ok, "build_output": build_output,
              "behavior": "not_run", "checks": []}
    if type_ok and build_ok:
        ok, output = run(["node", str(Path(__file__).with_name("runtime_check.cjs")), task,
                          str(bundle)], cwd=FRONTEND)
        try:
            result["checks"] = json.loads(output)
            result["behavior"] = "passed" if ok and all(result["checks"]) else "failed"
        except json.JSONDecodeError:
            result["behavior"] = "error"
            result["runtime_output"] = output
    return result


def evaluate(trial: Path = TRIAL) -> dict:
    # Generated JavaScript executes in Node during behavior checks. Review the
    # local trial before running; this is a test harness, not a security sandbox.
    data = json.loads(trial.read_text(encoding="utf-8"))
    report = {"source": str(trial), "note": "No API calls. Behavior checks cover frozen acceptance examples only.",
              "results": []}
    for item in data["results"]:
        if item["status"] != "generated":
            report["results"].append({"task": item["task"], "model": item["model"],
                                      "status": item["status"], "equivalent": "not_tested"})
            continue
        if item["task"] not in ENTRY:
            raise ValueError(f"No stage-4 behavior script for {item['task']}")
        with tempfile.TemporaryDirectory(prefix=".coding-eval-", dir=FRONTEND) as temp:
            folder = Path(temp)
            a_dir, b_dir = folder / "a", folder / "b"
            a_dir.mkdir()
            b_dir.mkdir()
            a = evaluate_candidate(item["task"], item["a"], "A", a_dir)
            b = evaluate_candidate(item["task"], item["b"], "B", b_dir)
        visual_style_issues = {
            "a": inline_pseudo_conflicts(item["a"]),
            "b": inline_pseudo_conflicts(item["b"]),
        }
        equivalent = ("passed_on_covered_scenarios" if a["behavior"] == b["behavior"] == "passed"
                      and a["checks"] == b["checks"]
                      and not any(visual_style_issues.values()) else "not_established")
        report["results"].append({"task": item["task"], "model": item["model"],
                                  "status": "generated", "a": a, "b": b,
                                  "visual_style_issues": visual_style_issues,
                                  "equivalent": equivalent})
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial", type=Path, default=TRIAL)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = evaluate(args.trial)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for item in report["results"]:
        if item["status"] == "generated":
            print(item["task"], item["model"], "A", item["a"]["behavior"],
                  "B", item["b"]["behavior"], item["equivalent"])
        else:
            print(item["task"], item["model"], item["status"])


if __name__ == "__main__":
    main()

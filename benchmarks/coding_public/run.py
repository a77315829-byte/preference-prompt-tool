"""Offline RACE checks and EvalPlus input preparation. No model/API client.

Only --fetch accesses the network, for pinned public source files.
Dataset solutions are parsed, never executed by this module.
"""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import io
import itertools
import json
import math
from pathlib import Path
import tokenize
import urllib.request
import warnings

from coding_elicitation import build_coding_elicitation
from coding_instructions import PREFERENCES, build_coding_instructions
from . import race_static as race

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data/public-code-benchmarks"
RACE_REVISION = "3b8ee591abd5febd8ae8ec17c7b9907949c5e1d5"
ASSETS = {
    "humaneval": {
        "file": "HumanEvalPlus-v0.1.10.jsonl.gz", "count": 164,
        "sha256": "272720b90ac375502c8ed23cd791c2a93dfb22a911641a494da74a426c09f101",
        "url": "https://github.com/evalplus/humanevalplus_release/releases/download/v0.1.10/HumanEvalPlus.jsonl.gz",
    },
    "mbpp": {
        "file": "MbppPlus-v0.2.0.jsonl.gz", "count": 378,
        "sha256": "af43697e8791c4c149bdfd6b489d8b5412507551ac20e28a439f650b8225db63",
        "url": "https://github.com/evalplus/mbppplus_release/releases/download/v0.2.0/MbppPlus.jsonl.gz",
    },
    "mbpp_noextreme": {
        "file": "MbppPlus-NoExtreme-v0.2.0.jsonl.gz", "count": 378,
        "sha256": "72d32acaea73d5606cb97041b30d45bbda9435a675369d3e31965513ee94e564",
        "url": "https://github.com/evalplus/mbppplus_release/releases/download/v0.2.0/MbppPlus-NoExtreme.jsonl.gz",
    },
    "race_source": {
        "file": "race_metrics_utils.py",
        "sha256": "b06af9621bd57c53d94bfb2dbad620637cc9b7bec491bfeceb22ade3d0c2ad30",
        "url": f"https://raw.githubusercontent.com/jszheng21/RACE/{RACE_REVISION}/race/codeeval/metrics_utils.py",
    },
    "evalplus_fix": {
        "file": "evalplus_eval_fixed.py",
        "sha256": "3c833c39b842e33f251c83db4347e0a95191909f23b390c12d73ab29a28a4daf",
        "url": "https://raw.githubusercontent.com/evalplus/evalplus/6eb1e199c2e370518e7bf3e8eee6322c2b23c89c/evalplus/eval/__init__.py",
    },
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def asset_bytes(name: str, cache: Path, fetch: bool = False) -> bytes:
    spec = ASSETS[name]
    path = cache / spec["file"]
    if path.exists():
        data = path.read_bytes()
    elif fetch:
        with urllib.request.urlopen(spec["url"], timeout=60) as response:
            data = response.read(20_000_001)
        if len(data) > 20_000_000:
            raise ValueError("Public asset exceeds the download size limit")
    else:
        raise FileNotFoundError(f"Missing {path}; run with --fetch once")
    if digest(data) != spec["sha256"]:
        raise ValueError(f"SHA-256 mismatch: {path.name}; no automatic replacement")
    if not path.exists():
        cache.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return data


def verify_race_source(data: bytes) -> list[str]:
    """Check extracted function ASTs against the pinned upstream source."""
    upstream = {n.name: n for n in ast.parse(data).body if isinstance(n, ast.FunctionDef)}
    local = ast.parse(Path(race.__file__).read_text(encoding="utf-8"))
    names = []
    for node in local.body:
        if isinstance(node, ast.FunctionDef):
            if ast.dump(node) != ast.dump(upstream[node.name]):
                raise ValueError(f"Changed RACE function: {node.name}")
            names.append(node.name)
    if len(names) != 7:
        raise ValueError("Unexpected extracted RACE function count")
    return names


def reference_code(row: dict) -> str:
    return row["prompt"] + row["canonical_solution"]


def audit_dataset(name: str, data: bytes) -> tuple[list[dict], dict]:
    rows = [json.loads(line) for line in gzip.decompress(data).decode("utf-8").splitlines() if line.strip()]
    ids = [row["task_id"] for row in rows]
    if len(rows) != ASSETS[name]["count"] or len(set(ids)) != len(ids):
        raise ValueError(f"Unexpected or duplicate task IDs in {name}")
    failures, syntax_warnings = [], []
    for row in rows:
        try:
            code = reference_code(row)
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always", SyntaxWarning)
                tree = ast.parse(code)
                compile(tree, row["task_id"], "exec")  # Syntax validation only.
            syntax_warnings.extend({"task_id": row["task_id"], "message": str(item.message)} for item in captured)
            assert any(isinstance(n, ast.FunctionDef) and n.name == row["entry_point"] for n in tree.body)
            assert isinstance(row["base_input"], list) and row["base_input"]
            # The pinned MBPP+ release has an empty object, not a list, here.
            # Preserve and report this upstream exception instead of inventing tests.
            assert isinstance(row["plus_input"], list) or (
                name in ("mbpp", "mbpp_noextreme") and row["task_id"] == "Mbpp/793" and row["plus_input"] == {})
            assert isinstance(row["atol"], (int, float)) and row["atol"] >= 0
        except (SyntaxError, AssertionError, TypeError, KeyError) as error:
            failures.append({"task_id": row["task_id"], "error": type(error).__name__})
    if failures:
        raise ValueError(f"Dataset validation failed: {failures}")
    return rows, {
        "tasks": len(rows), "reference_syntax_valid": len(rows),
        "base_inputs": sum(len(row["base_input"]) for row in rows),
        "plus_inputs": sum(len(row["plus_input"]) for row in rows),
        "tasks_without_plus_inputs": [row["task_id"] for row in rows if not row["plus_input"]],
        "syntax_warnings": syntax_warnings,
        "sha256": digest(data), "functional_pass_rate": None,
        "note": "Input counts are inventories, not executed or passing test counts.",
    }


def measure_static(code: str) -> dict:
    tree = ast.parse(code)
    compile(tree, "<static-only>", "exec")
    functions = race.extract_function_names(code)
    if not functions:
        raise ValueError("A complete function is required; patches need their original context")
    comments = [t for t in tokenize.generate_tokens(io.StringIO(code).readline) if t.type == tokenize.COMMENT]
    return {
        "functions": len(functions), "comment_tokens": len(comments),
        "race_function_snake": race.metrics_for_readability_function_snake(code),
        "race_length_100_40": race.metrics_for_readability_length(code, 100, 40),
        "race_comment_by_function": race.metrics_for_readability_comment_by_function(code),
        "race_comment_by_line_075": race.metrics_for_readability_comment_by_line(code, 0.75),
        "race_module_count_1": race.metrics_for_maintainability_module_count(code, 1),
        "race_module_count_2": race.metrics_for_maintainability_module_count(code, 2),
    }


def complete_example(pair: dict, option: dict) -> str:
    code = option["code"]
    if pair["axis"] != "output" or option["value"] != "changes":
        return code
    before = pair["before"]
    returns = [n for n in ast.walk(ast.parse(before)) if isinstance(n, ast.Return)]
    if len(returns) != 1 or len(code.splitlines()) != 1 or not code.lstrip().startswith("return "):
        raise ValueError("Unsupported patch context; do not score an incomplete snippet")
    lines = before.splitlines()
    node = returns[0]
    if node.lineno != node.end_lineno:
        raise ValueError("Multiline patch requires explicit reconstruction")
    lines[node.lineno - 1] = code
    return "\n".join(lines)


def example_value(code: str, entry: str, *args: int) -> int:
    """Interpret only the small arithmetic subset in our prepared examples.

    Not a Python execution sandbox or an EvalPlus evaluator. Imports, attributes,
    statements other than function/return, and foreign calls are rejected.
    """
    tree = ast.parse(code)
    allowed = (ast.Module, ast.FunctionDef, ast.arguments, ast.arg, ast.Return,
               ast.BinOp, ast.Add, ast.Mult, ast.Name, ast.Load, ast.Constant, ast.Call)
    if any(not isinstance(node, allowed) for node in ast.walk(tree)):
        raise ValueError("Unsupported arithmetic example")
    if any(not isinstance(node, ast.FunctionDef) for node in tree.body):
        raise ValueError("Only function declarations are allowed")
    functions = {node.name: node for node in tree.body}

    def call(name, values, depth=0):
        if depth > 12 or name not in functions:
            raise ValueError("Unknown or recursive function")
        fn = functions[name]
        if (len(fn.body) != 1 or not isinstance(fn.body[0], ast.Return)
                or fn.decorator_list or fn.args.defaults or fn.args.vararg or fn.args.kwarg
                or fn.args.kwonlyargs or fn.args.posonlyargs or len(values) != len(fn.args.args)):
            raise ValueError("Unsupported function signature or body")
        env = dict(zip((arg.arg for arg in fn.args.args), values))

        def value(node):
            if isinstance(node, ast.Constant) and type(node.value) is int:
                return node.value
            if isinstance(node, ast.Name) and node.id in env:
                return env[node.id]
            if isinstance(node, ast.BinOp):
                left, right = value(node.left), value(node.right)
                return left + right if isinstance(node.op, ast.Add) else left * right
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
                return call(node.func.id, [value(arg) for arg in node.args], depth + 1)
            raise ValueError("Unsupported expression")
        return value(fn.body[0].value)
    if any(type(arg) is not int for arg in args):
        raise ValueError("Only integer inputs are allowed")
    return call(entry, args)


def audit_examples() -> dict:
    bank = build_coding_elicitation({"language": "Python", "framework": ""})
    fees = {"order": (3000, 2500), "rental": (1000, 500), "print": (200, 100)}
    rows = []
    for pair in bank["pairs"] + bank["followups"]:
        context = pair["id"].split(":")[0]
        fee = fees[context][int(pair["axis"] == "output")]
        for option in pair["options"]:
            code = complete_example(pair, option)
            checks = [example_value(code, context + "_total", price, count) == price * count + fee
                      for price in (0, 1, 10000, 999999) for count in (0, 1, 2, 7, 100)]
            rows.append({"id": pair["id"], "axis": pair["axis"], "value": option["value"],
                         "code_sha256": digest(code.encode()), **measure_static(code),
                         "arithmetic_checks": len(checks), "arithmetic_passed": sum(checks)})
    return {"scope": "prepared Python language-only examples; not model-generated answers",
            "examples": len(rows), "contexts": 3,
            "arithmetic_checks": sum(row["arithmetic_checks"] for row in rows),
            "arithmetic_passed": sum(row["arithmetic_passed"] for row in rows), "rows": rows}


def profiles() -> dict[str, str]:
    prompts = {}
    for values in itertools.product(*PREFERENCES.values()):
        preferences = dict(zip(PREFERENCES, values))
        result = build_coding_instructions({"language": "Python", "preferences": preferences})
        name = ":".join(values)
        prompts[name] = result["prompt"]
    if len(set(prompts.values())) != 16:
        raise ValueError("Expected 16 distinct assembled preference prompts")
    return prompts


def request_manifest(datasets: dict[str, list[dict]]) -> list[dict]:
    variants = profiles()
    example = next(iter(variants.values()))
    prefix = example.split("## 직접 고른 내 작성 선호")[0]
    rules = "## 항상 지킬 것" + example.split("## 항상 지킬 것")[1]
    conditions = {"general": prefix + rules}
    for comments, structure in itertools.product(PREFERENCES["comments"], PREFERENCES["structure"]):
        conditions[comments + ":" + structure] = variants[f"brief:{comments}:{structure}:complete"]
    requests = []
    for dataset, tasks in datasets.items():
        # Reproducible 10-task pilot per dataset; full set is still held separately.
        ordered = sorted(tasks, key=lambda r: digest(("pilot-v1:" + r["task_id"]).encode()))
        pilot_ids = {row["task_id"] for row in ordered[:10]}
        for task in tasks:
            user = ("다음 과제의 요구사항과 함수 이름·인자를 유지한 전체 Python 구현을 제시하라. "
                    "설명과 실행할 코드는 구분하고, 코드는 하나의 python 코드 블록에 넣어라.\n\n" + task["prompt"])
            for condition, system in conditions.items():
                messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
                serialized = json.dumps(messages, ensure_ascii=False, sort_keys=True).encode("utf-8")
                # Conservative planning allowance, NOT a model-specific tokenizer count.
                budget = math.ceil(len(serialized) * 1.1) + 128
                requests.append({"dataset": dataset, "task_id": task["task_id"], "condition": condition,
                                 "pilot": task["task_id"] in pilot_ids, "messages": messages,
                                 "request_sha256": digest(serialized), "input_token_budget": budget,
                                 "max_output_tokens": 4096})
    return requests


def cost_estimates(requests: list[dict]) -> dict:
    rates = {"gpt-6-luna": (0.10, 0.50), "gpt-6.1-sol": (2.00, 10.00)}
    scenarios = {"pilot_20_tasks": [r for r in requests if r["pilot"]],
                 "humaneval_164_tasks": [r for r in requests if r["dataset"] == "humaneval"],
                 "all_542_tasks": requests}
    result = {}
    for name, rows in scenarios.items():
        budget = sum(row["input_token_budget"] for row in rows)
        result[name] = {"calls": len(rows), "input_token_budget": budget, "models": {}}
        for model, (input_rate, output_rate) in rates.items():
            result[name]["models"][model] = {
                "usd_if_output_1024_each": round((budget * input_rate + len(rows) * 1024 * output_rate) / 1e6, 4),
                "usd_if_output_cap_4096_each": round((budget * input_rate + len(rows) * 4096 * output_rate) / 1e6, 4)}
    return {"rates_checked": "2026-11-09", "currency": "USD", "scenarios": result,
            "assumptions": "Standard API, uncached input, no retries/tools/GEPA; input budget is UTF-8 bytes * 1.1 + 128 per request, not measured tokens. Output includes reasoning. Tax/exchange fees excluded. No calls executed.",
            "sources": [f"https://developers.openai.com/api/docs/models/{model}" for model in rates]}


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def run(cache: Path = CACHE, fetch: bool = False) -> dict:
    functions = verify_race_source(asset_bytes("race_source", cache, fetch))
    asset_bytes("evalplus_fix", cache, fetch)
    datasets, summaries = {}, {}
    for name in ("humaneval", "mbpp"):
        datasets[name], summaries[name] = audit_dataset(name, asset_bytes(name, cache, fetch))
    alternative, alternative_summary = audit_dataset("mbpp_noextreme", asset_bytes("mbpp_noextreme", cache, fetch))
    full = {row["task_id"]: row for row in datasets["mbpp"]}
    changed = {}
    for row in alternative:
        original = full[row["task_id"]]
        if any(row[key] != original[key] for key in original if key != "plus_input"):
            raise ValueError("NoExtreme changes more than additional inputs")
        if row["plus_input"] != original["plus_input"]:
            changed[row["task_id"]] = len(original["plus_input"]) - len(row["plus_input"])
    alternative_summary["excluded_plus_inputs_by_task"] = changed
    examples = audit_examples()
    if examples["arithmetic_passed"] != examples["arithmetic_checks"]:
        raise ValueError("Prepared example arithmetic regression")
    requests = request_manifest(datasets)
    output = cache / "prepared"
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output / "requests.NOT_EXECUTED.jsonl", requests)
    for name, rows in datasets.items():
        write_jsonl(output / f"{name}.reference.jsonl", [
            {"task_id": row["task_id"], "solution": reference_code(row)} for row in rows])
        write_jsonl(output / f"{name}.negative.jsonl", [
            {"task_id": row["task_id"], "solution": f"def {row['entry_point']}(*args, **kwargs):\n    raise AssertionError('negative control')\n"} for row in rows])
    report = {"schema_version": 1, "model_api_calls": 0, "model_api_cost_usd": 0,
              "race_revision": RACE_REVISION, "race_functions_verified": functions,
              "project_source_sha256": {name: digest((ROOT / name).read_bytes()) for name in (
                  "coding_examples.py", "coding_framework_examples.py", "coding_elicitation.py",
                  "coding_instructions.py", "benchmarks/coding_public/run.py", "benchmarks/coding_public/race_static.py",
                  "benchmarks/coding_public/evaluate_docker.py", "benchmarks/coding_public/container_controls.py")},
              "datasets": summaries, "prepared_examples": examples,
              "mbpp_noextreme_audit": alternative_summary,
              "assembled_profiles": len(profiles()), "prepared_requests": len(requests),
              "cost_estimates": cost_estimates(requests),
              "evalplus_execution": "Separate Docker step required; no functional pass rate claimed here.",
              "personalization_effectiveness": "Not measured; requires unseen-task model answers and user evaluation."}
    (output / "offline-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="Download pinned PUBLIC files only; no model calls")
    parser.add_argument("--cache", type=Path, default=CACHE)
    args = parser.parse_args()
    report = run(args.cache, args.fetch)
    print(json.dumps({"datasets": report["datasets"], "examples": report["prepared_examples"]["examples"],
                      "arithmetic_passed": report["prepared_examples"]["arithmetic_passed"],
                      "prepared_requests": report["prepared_requests"], "api_cost_usd": 0}, indent=2))

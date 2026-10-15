"""Offline checks of reviewed, saved persona outputs. Never calls an AI API.

Review every saved code block before using --reviewed: these checks execute code.
"""

import argparse
import json
import re
import tempfile
from pathlib import Path

from benchmarks.coding_ai_quality.evaluate_trial import FRONTEND, evaluate_candidate
from checks.coding import candidate_quality_issues, pair_quality_issues


PROMPT_MARKERS = {
    "compact": "한 파일 안에", "separated": "역할별 파일로 분리",
    "direct": "직접 작성", "theme": "디자인 토큰",
    "inferred": "타입 추론 중심", "explicit": "타입을 꼼꼼하게 명시",
}


def independent_style_issues(code: str, combo: dict) -> list[str]:
    """Check a public boundary separately from the production signal counter."""
    if combo.get("type_detail") != "explicit":
        return []
    names = re.findall(
        r"export\s+(?:default\s+)?function\s+(\w+)\s*\([^)]*\)\s*\{", code
    )
    return [f"Exported function {name} omits an explicit return type" for name in names]


def evaluate_saved(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    results = []
    with tempfile.TemporaryDirectory(prefix="persona-review-", dir=FRONTEND) as temporary:
        root = Path(temporary)

        def check(task, code, combo, request, slot):
            folder = root / slot
            folder.mkdir()
            try:
                result = evaluate_candidate(task, code, slot, folder)
            except ValueError as error:
                result = {"slot": slot, "typecheck": False, "build": False,
                          "behavior": "not_run", "error": str(error)}
            result["style_issues"] = candidate_quality_issues(code, combo, request)
            result["independent_style_issues"] = independent_style_issues(code, combo)
            result["passed"] = (result["typecheck"] and result["build"]
                                and result["behavior"] == "passed"
                                and not result["style_issues"]
                                and not result["independent_style_issues"])
            return result

        for index, persona in enumerate(data["personas"]):
            pairs = []
            for number, pair in enumerate(persona["pairs"]):
                candidates = {
                    side: check("counter_reset", pair[side], pair[f"combo_{side}"],
                                data["request"], f"p{index}-{number}-{side}")
                    for side in ("a", "b")
                }
                issues = pair_quality_issues(pair["a"], pair["b"],
                                             pair["combo_a"], pair["combo_b"])
                candidates.update(axis=pair["axis"], pair_issues=issues)
                candidates["passed"] = all(candidates[s]["passed"] for s in ("a", "b")) and not issues
                pairs.append(candidates)
            prompt_checks = {
                axis: PROMPT_MARKERS[value] in persona["prompt"]
                for axis, value in persona["target"].items()
            }
            transfer = check("faq_multi", persona["transfer"], persona["target"],
                             data["transfer_request"], f"p{index}-transfer")
            matched = persona["target"] == persona["actual"]
            results.append({"target": persona["target"], "preference_matches": matched,
                            "prompt_checks": prompt_checks, "pairs": pairs, "transfer": transfer,
                            "passed": matched and all(prompt_checks.values())
                            and all(p["passed"] for p in pairs) and transfer["passed"]})
    return {"source": str(path), "additional_api_calls": 0,
            "kind": "scripted_persona_offline_verification_not_human_evaluation",
            "limitations": ["Behavior equivalence is limited to covered scenarios.",
                            "CSS is not rendered; visual equivalence is not established.",
                            "Style checks are heuristics, not proof of every annotation."],
            "personas": results, "passed": all(p["passed"] for p in results) and bool(results)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--reviewed", action="store_true", required=True)
    args = parser.parse_args()
    result = evaluate_saved(args.input)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "personas": len(result["personas"]),
                      "additional_api_calls": 0}))


if __name__ == "__main__":
    main()

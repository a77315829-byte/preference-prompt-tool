"""Offline contract audit. Writes only beside this file; no user DB or API imports."""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from app_db import Database
from coding_elicitation import build_adaptive_coding_elicitation
from coding_instructions import build_coding_instructions
from coding_work_exports import export_preview
from personal_prompts import PersonalPromptStore

AXES = ("explanation", "comments", "structure", "output")
VALUES = (("brief", "steps"), ("essential", "detailed"), ("compact", "modular"), ("complete", "changes"))
ENVIRONMENTS = (("Python", "FastAPI", "framework"), ("JavaScript", "React", "language"),
                ("TypeScript", "React", "language"), ("Python", "Flask", "language"),
                ("Java", "Spring Boot", "framework"))
TASK = "AUDIT_ONLY_TRANSIENT_TASK_20261110: change the invoice endpoint"
TARGETS = ("agents_md", "claude_code", "copilot", "cursor", "markdown")
SOURCES = ("coding_instructions.py", "coding_elicitation.py", "coding_examples.py", "coding_framework_examples.py",
           "personal_prompts.py", "coding_work_exports.py", "exporters.py")


def check(condition, explanation):
    if not condition:
        raise AssertionError(explanation)


def rejected(fn):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError("Expected ValueError rejection")


def profile_for(language, framework, values):
    return {"language": language, "framework": framework, "preferences": dict(zip(AXES, values)),
            "extra": "설명은 한국어로, 기존 함수 이름 유지"}


def comparison_profile(profile, count):
    bank = build_adaptive_coding_elicitation(profile)
    result = copy.deepcopy(profile)
    result["comparison"] = {"version": 4, "choices": dict(profile["preferences"]), "example": bank["source"],
                            "rounds": [{"id": pair["id"], "value": profile["preferences"][pair["axis"]]}
                                       for pair in bank["pairs"][:count]]}
    return result


def preference_rules(prompt):
    # Read the emitted rule block; provenance headings intentionally differ across routes.
    return tuple(line for line in prompt.split("## 항상 지킬 것")[0].splitlines() if line.startswith("- "))


def create_body(draft, title):
    return {"title": title, "domainKey": "coding", "prompt": draft["prompt"], "codingProfile": draft["profile"]}


def execute():
    run = HERE / ("run-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    run.mkdir()
    database = Database(run / "audit.db")
    store = PersonalPromptStore(database)
    report = {"scope": "Deterministic software contracts only; not human preference accuracy, convenience, satisfaction, or live AI output.",
              "expected_head": "def4d7cf3bb32d40770e70e91205a6ee7a708eb2",
              "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES},
              "counts": {}, "failures": [], "environments": ENVIRONMENTS, "db": str(database.path)}
    samples = []

    def case(group, identity, fn):
        count = report["counts"].setdefault(group, {"passed": 0, "failed": 0})
        try:
            fn()
            count["passed"] += 1
        except Exception as exc:
            count["failed"] += 1
            report["failures"].append({"group": group, "case": identity, "type": type(exc).__name__, "error": str(exc)})

    for env_index, (language, framework, kind) in enumerate(ENVIRONMENTS):
        source_id = None
        for combo_index, values in enumerate(itertools.product(*VALUES)):
            profile = profile_for(language, framework, values)
            direct = build_coding_instructions(profile)
            owner = 1 + env_index * 16 + combo_index
            with database.connect() as connection:
                connection.execute("INSERT INTO users VALUES (?, ?, 'audit-not-a-password', 'audit')", (owner, f"audit{owner}"))
            identity = f"{language}/{framework}/{''.join(str(VALUES[i].index(v)) for i, v in enumerate(values))}"

            for count in (0, 4, 8):
                raw = profile if count == 0 else comparison_profile(profile, count)
                original_raw = copy.deepcopy(raw)
                draft = build_coding_instructions(raw)
                route_id = f"{identity}/{count or 'direct'}"

                def route_contract():
                    check(raw == original_raw, "Builder changed input profile")
                    check(draft["profile"]["preferences"] == profile["preferences"], "Final preferences differ")
                    check(preference_rules(draft["prompt"]) == preference_rules(direct["prompt"]), "Rule block differs across routes")
                    check(len(preference_rules(draft["prompt"])) == 4, "Expected exactly four preference rules")
                    check(f"개발 언어: {language}\n프레임워크·라이브러리: {framework}" in draft["prompt"], "Environment missing")
                    if count:
                        comparison = draft["profile"]["comparison"]
                        check(comparison["example"]["kind"] == kind, "Framework evidence overstated or lost")
                        check(comparison["stop_reason"] == ("user" if count == 4 else "consistent"), "Wrong stop reason")
                        for axis in AXES:
                            signal = comparison["summary"][axis]
                            check(signal["status"] == ("single" if count == 4 else "consistent"), "Wrong signal strength")
                            check(signal["answered"] == count // 4, "Wrong response count")
                        check("기능 정확도나 다른 과제에서의 만족도가 검증된 것은 아니다" in draft["prompt"], "Missing scope limitation")
                        if kind == "language":
                            check(framework not in comparison["example"]["label"], "Unobserved framework in example label")
                        else:
                            check(framework in comparison["example"]["label"], "Framework label missing")

                case("route_equivalence", route_id, route_contract)
                if combo_index == 0:
                    samples.append({"case": route_id, "profile": draft["profile"], "prompt": draft["prompt"]})
                if count:
                    next_id = draft["profile"]["comparison"]["example"]["id"]
                    if source_id is None:
                        source_id = next_id
                    case("source_stability", route_id, lambda: check(next_id == source_id, "Source ID depends on preference choices/count"))

                body = {**create_body(draft, route_id), "task": TASK, "sourceText": TASK, "output": TASK}
                saved = store.create(owner, body)

                def storage_contract():
                    reread = PersonalPromptStore(Database(database.path)).get(owner, saved["id"])
                    check(reread == saved, "Reopen changed persisted values")
                    check(saved["coding_profile"] == draft["profile"], "Stored snapshot differs")
                    check(saved["coding_profile_matches"] is True, "New snapshot does not match")
                    check(TASK not in json.dumps(reread), "Task leaked into stored entry")
                    check(TASK not in json.dumps(store.list_for(owner)), "Task leaked into library metadata")
                    rejected(lambda: store.create(owner, {**body, "prompt": draft["prompt"] + "\n\n## 이번 작업 요청\n" + TASK}))
                    check(store.get(owner, saved["id"]) == saved, "Rejected mixed prompt mutated original")

                case("save_reopen_task_separation", route_id, storage_contract)

                for axis, options in zip(AXES, VALUES):
                    def change_contract(axis=axis, options=options):
                        reused = store.get(owner, saved["id"])["coding_profile"]
                        reused["preferences"][axis] = next(v for v in options if v != profile["preferences"][axis])
                        if count:
                            reused["comparison"]["choices"][axis] = None
                        changed = build_coding_instructions(reused)
                        rules_before, rules_after = preference_rules(draft["prompt"]), preference_rules(changed["prompt"])
                        check(sum(a != b for a, b in zip(rules_before, rules_after)) == 1, "Changing one axis changed other rules")
                        if count:
                            before_cmp, after_cmp = draft["profile"]["comparison"], changed["profile"]["comparison"]
                            check(after_cmp["rounds"] == before_cmp["rounds"], "Historical answers changed")
                            check(after_cmp["example"] == before_cmp["example"], "Source changed on manual override")
                            for other in AXES:
                                check(after_cmp["choices"][other] == (None if other == axis else before_cmp["choices"][other]), "Wrong axis attribution")
                        child = store.create(owner, create_body(changed, route_id + "/change-" + axis))
                        check(child["id"] != saved["id"] and child["revision"] == 1, "Derived entry overwrote original")
                        check(store.get(owner, saved["id"]) == saved, "Original changed after independent new save")
                        check(build_coding_instructions(child["coding_profile"])["prompt"] == child["prompt"], "Derived entry cannot be reused")
                    case("one_axis_change_new_save", route_id + "/" + axis, change_contract)

                for target in TARGETS:
                    def export_contract(target=target):
                        existing = "AUDIT_EXISTING_PREFIX\n" if target != "cursor" else ""
                        exported = export_preview({"prompt": saved["prompt"], "target": target, "existing": existing, "task": TASK})
                        check(saved["prompt"] in exported["content"], "Export lost saved instruction content")
                        check(TASK not in exported["content"], "Export leaked task field")
                        if target != "cursor":
                            existing_again = exported["content"] + "\nAUDIT_EXISTING_SUFFIX\n"
                            refreshed = export_preview({"prompt": saved["prompt"], "target": target, "existing": existing_again})
                            check(refreshed["content"] == existing_again, "Export refresh changed unrelated existing content")
                        check(store.get(owner, saved["id"]) == saved, "Export changed stored entry")
                    case("exports_preserve_original", route_id + "/" + target, export_contract)

        base = comparison_profile(profile_for(language, framework, tuple(v[0] for v in VALUES)), 4)
        for other_language, other_framework, _ in ENVIRONMENTS:
            if (language, framework) == (other_language, other_framework):
                continue
            altered = copy.deepcopy(base)
            altered.update(language=other_language, framework=other_framework)
            case("cross_environment_source_rejected", f"{language}/{framework}->{other_language}/{other_framework}",
                 lambda altered=altered: rejected(lambda: build_coding_instructions(altered)))

    report["source_sha256_after"] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}
    check(report["source_sha256"] == report["source_sha256_after"], "Audited production sources changed during run")
    (run / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (run / "sample-prompts.json").write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")
    (HERE / "latest-run.txt").write_text(str(run), encoding="utf-8")
    print(json.dumps({"run": str(run), "counts": report["counts"], "failures": report["failures"]}, ensure_ascii=False, indent=2))
    return bool(report["failures"])


if __name__ == "__main__":
    raise SystemExit(execute())

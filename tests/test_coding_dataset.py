"""The synthetic corpus has no invented users, outcomes, or preference labels."""

from collections import Counter
import json
from pathlib import Path

from checks import coding
from experiments.coding_dataset import AXES, TASKS, build_dataset
from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator
from optimize.run_gepa import build_seed_prompt


def test_export_is_reproducible_and_current():
    exported = Path("benchmarks/coding_style/v1.json").read_text(encoding="utf-8")
    assert exported == json.dumps(build_dataset(), ensure_ascii=False, indent=2) + "\n"
    assert build_dataset() == build_dataset()


def test_counts_and_unique_ids():
    dataset = build_dataset()
    for name, count in (("tasks", 6), ("variants", 48), ("pairs", 72)):
        assert len(dataset[name]) == count
        assert len({row["id"] for row in dataset[name]}) == count
    assert Counter(p["axis"] for p in dataset["pairs"]) == dict.fromkeys(AXES, 24)
    assert all(pair["winner"] is None for pair in dataset["pairs"])
    assert dataset["human_review_status"] == "pending"


def test_pairs_change_exactly_one_axis_with_balanced_order():
    dataset = build_dataset()
    variants = {v["id"]: v for v in dataset["variants"]}
    for pair in dataset["pairs"]:
        a, b = variants[pair["a"]], variants[pair["b"]]
        assert a["task_id"] == b["task_id"] == pair["task_id"]
        assert a["split"] == b["split"] == pair["split"]
        changed = [axis for axis in AXES if a["profile"][axis] != b["profile"][axis]]
        assert changed == [pair["axis"]]
        assert a["files"] != b["files"]
    for task in TASKS:
        for axis, values in AXES.items():
            subset = [p for p in dataset["pairs"] if p["task_id"] == task["id"] and p["axis"] == axis]
            assert Counter(variants[p["a"]]["profile"][axis] for p in subset) == dict.fromkeys(values, 2)


def test_splits_do_not_share_tasks_or_code_variants():
    dataset = build_dataset()
    groups = {split: {t["id"] for t in dataset["tasks"] if t["split"] == split} for split in ("elicitation", "holdout")}
    assert len(groups["elicitation"]) == 4
    assert len(groups["holdout"]) == 2
    assert groups["elicitation"].isdisjoint(groups["holdout"])
    for kind in ("variants", "pairs"):
        for row in dataset[kind]:
            assert row["task_id"] in groups[row["split"]]


def test_structure_and_non_target_code_remain_controlled():
    dataset = build_dataset()
    variants = {v["id"]: v for v in dataset["variants"]}
    for variant in variants.values():
        assert len(variant["files"]) == (1 if variant["profile"]["code_structure"] == "compact" else 3)
        code = "\n".join(variant["files"].values())
        assert ("theme.colors" in code) == (variant["profile"]["style_management"] == "theme")
        assert ("interface Model" in code) == (variant["profile"]["type_detail"] == "explicit")
    for pair in dataset["pairs"]:
        a, b = variants[pair["a"]], variants[pair["b"]]
        if a["profile"]["code_structure"] == b["profile"]["code_structure"] == "separated":
            if pair["axis"] == "style_management":
                assert a["files"]["useModel.ts"] == b["files"]["useModel.ts"]
            if pair["axis"] == "type_detail":
                assert a["files"]["styles.ts"] == b["files"]["styles.ts"]


def test_simulated_choices_feed_existing_estimator_and_prompt():
    """Wiring regression only: this is NOT a human-user effectiveness result."""
    dataset = build_dataset()
    variants = {v["id"]: v for v in dataset["variants"]}
    domain = load_domain("domains/coding.yaml")
    targets = {tuple(v["profile"].items()) for v in dataset["variants"]}
    for target_items in targets:
        target = dict(target_items)
        estimator = Estimator(domain)
        for pair in dataset["pairs"]:
            if pair["split"] != "elicitation":
                continue
            a, b = variants[pair["a"]]["profile"], variants[pair["b"]]["profile"]
            winner = "a" if a[pair["axis"]] == target[pair["axis"]] else "b"
            estimator.update(Comparison(a, b, winner))
        assert {axis: estimator.preferred_value(axis) for axis in AXES} == target
        prompt = build_seed_prompt(domain, estimator)
        for axis in domain.axes:
            assert axis.instruction_for(target[axis.name]) in prompt


def test_all_variants_match_existing_domain_style_checks():
    domain = load_domain("domains/coding.yaml")
    for variant in build_dataset()["variants"]:
        output = "\n\n".join(
            f"`{name}`\n```{'tsx' if name.endswith('.tsx') else 'ts'}\n{code}```"
            for name, code in variant["files"].items()
        )
        for axis in domain.axes:
            value = variant["profile"][axis.name]
            spec = axis.check_for(value)
            score, feedback = getattr(coding, spec.fn)(output, "", value, spec.target)
            assert score == 1.0, (variant["id"], axis.name, feedback)

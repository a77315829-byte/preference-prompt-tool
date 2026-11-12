"""Offline measurements and blind packets; never generates model responses."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from pathlib import Path

from checks.summarization import _bigrams, _sentences, _words
from benchmarks.summary_agent_pilot.prepare import RUN, SEED, write_json

ARMS = ("general", "manual", "assembled")


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normalize(text: str) -> str:
    return " ".join(text.split())


def verbatim_units(output: str, units: list[str]) -> bool:
    """Strict diagnostic: output must concatenate complete, unmodified dataset units."""
    target = normalize(output)
    if not target:
        return False
    units = [normalize(unit) for unit in units if normalize(unit)]
    reached = {0}
    for pos in range(len(target) + 1):
        if pos not in reached:
            continue
        for unit in units:
            start = pos + (1 if pos and target[pos:pos + 1] == " " else 0)
            if target.startswith(unit, start):
                reached.add(start + len(unit))
    return len(target) in reached


def length_pass(count: int, value: str) -> bool:
    if count < 1:
        return False
    return {"short": count <= 2, "normal": 3 <= count <= 4, "long": count >= 5}[value]


def measurements(summary: str, case: dict) -> dict:
    ob = _bigrams(_words(summary))
    sb = _bigrams(_words(case["source"]))
    overlap = len(ob & sb) / len(ob) if ob else 0.0
    value = case["profile"]["extractiveness"]
    proxy_pass = bool(ob) and {
        "normal": overlap <= .5, "high": .5 <= overlap <= .75, "fully": overlap >= .75,
    }[value]
    count = len(_sentences(summary))
    return {
        "app_sentence_count": count,
        "app_length_pass": bool(summary.strip()) and length_pass(count, case["profile"]["length"]),
        "bigram_overlap": overlap, "app_overlap_proxy_pass": proxy_pass,
        "strict_source_unit_extraction": verbatim_units(summary, case["source_units"]),
        "words": len(summary.split()), "word_ratio": len(summary.split()) / case["source_words"],
        "novel_digit_tokens_flags_only": sorted(set(re.findall(r"\d+(?:[.,]\d+)*", summary)) - set(re.findall(r"\d+(?:[.,]\d+)*", case["source"]))),
    }


def validate_facts(cases: list[dict], facts: list[dict]) -> None:
    by_id = {c["id"]: c for c in cases}
    assert len(facts) == len(by_id) and {f["id"] for f in facts} == set(by_id)
    for row in facts:
        assert len(row["facts"]) == 3
        assert {f["id"] for f in row["facts"]} == {"F1", "F2", "F3"}
        for fact in row["facts"]:
            assert fact["proposition"] and fact["evidence"]
            assert all(q and q in by_id[row["id"]]["source"] for q in fact["evidence"]), (row["id"], fact["id"])


def freeze() -> None:
    cases, facts = read(RUN / "cases.json"), read(RUN / "facts.json")
    validate_facts(cases, facts)
    paths = [RUN / "protocol.json", RUN / "cases.json", RUN / "facts.json", Path(__file__), Path(__file__).with_name("rubric.json")]
    paths += [RUN / "inputs" / f"{arm}.json" for arm in ARMS]
    write_json(RUN / "frozen.json", {str(p.relative_to(RUN.parent.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})


def verify_frozen() -> None:
    for path, expected in read(RUN / "frozen.json").items():
        assert hashlib.sha256((RUN.parent.parent / path).read_bytes()).hexdigest() == expected, path


def blind() -> None:
    verify_frozen()
    cases = read(RUN / "cases.json")
    facts = {r["id"]: r["facts"] for r in read(RUN / "facts.json")}
    ids = {c["id"] for c in cases}
    entries = []
    for arm in ARMS:
        outputs = read(RUN / "outputs" / f"{arm}.json")
        assert len(outputs) == len(ids) and {r["id"] for r in outputs} == ids
        assert all(isinstance(r["summary"], str) and r["summary"].strip() for r in outputs)
        by_id = {r["id"]: r["summary"] for r in outputs}
        for case in cases:
            entries.append((arm, case, by_id[case["id"]]))
    random.Random(SEED + 2).shuffle(entries)
    packet, mapping, automatic = [], {}, []
    for i, (arm, case, summary) in enumerate(entries, 1):
        oid = f"O{i:02d}"
        packet.append({"output_id": oid, "case_id": case["id"], "source": case["source"],
                       "target": case["profile"], "key_facts": facts[case["id"]], "summary": summary})
        mapping[oid] = {"arm": arm, "case_id": case["id"]}
        automatic.append({"output_id": oid, **mapping[oid], **measurements(summary, case)})
    write_json(RUN / "blind_packet.json", packet)
    write_json(RUN / "blind_mapping.json", mapping)
    write_json(RUN / "automatic.json", automatic)


def validate_review(rows: list[dict], packet: list[dict]) -> None:
    by_id = {r["output_id"]: r for r in packet}
    assert len(rows) == len(by_id) and {r["output_id"] for r in rows} == set(by_id)
    for row in rows:
        item = by_id[row["output_id"]]
        assert isinstance(row["sentence_count"], int) and row["sentence_count"] >= 1
        assert isinstance(row["wording_pass"], bool) and row["wording_reason"]
        assert len(row["facts"]) == 3 and {f["id"] for f in row["facts"]} == {"F1", "F2", "F3"}
        for fact in row["facts"]:
            assert isinstance(fact["preserved"], bool) and fact["reason"]
            assert all(q in item["summary"] for q in fact["summary_evidence"])
            if fact["preserved"]:
                assert fact["summary_evidence"]
        for issue in row["issues"]:
            assert issue["summary_quote"] in item["summary"] and issue["reason"]
            assert all(q in item["source"] for q in issue["source_evidence"])


def score() -> None:
    verify_frozen()
    packet = read(RUN / "blind_packet.json")
    mapping = read(RUN / "blind_mapping.json")
    reviews = [read(RUN / f"review_{key}.json") for key in ("a", "b")]
    for review in reviews:
        validate_review(review, packet)
    a, b = [{r["output_id"]: r for r in review} for review in reviews]
    agreement = {"sentence_count": 0, "wording": 0, "facts": 0, "any_issue": 0}
    disagreements = []
    for oid in a:
        agreement["sentence_count"] += a[oid]["sentence_count"] == b[oid]["sentence_count"]
        agreement["wording"] += a[oid]["wording_pass"] == b[oid]["wording_pass"]
        agreement["any_issue"] += bool(a[oid]["issues"]) == bool(b[oid]["issues"])
        fa, fb = [{f["id"]: f["preserved"] for f in r[oid]["facts"]} for r in (a, b)]
        agreement["facts"] += sum(fa[k] == fb[k] for k in fa)
        if fa != fb or a[oid]["wording_pass"] != b[oid]["wording_pass"] or a[oid]["sentence_count"] != b[oid]["sentence_count"] or bool(a[oid]["issues"]) != bool(b[oid]["issues"]):
            disagreements.append(oid)
    report = {"outputs": 27, "reviewer_agreement": agreement, "disagreement_ids": disagreements, "by_reviewer": {}}
    for reviewer, rows in zip(("a", "b"), reviews):
        counts = {arm: {"outputs": 0, "length_pass": 0, "wording_pass": 0, "both_conditions_pass": 0, "facts_preserved": 0, "facts_total": 0, "outputs_with_factual_issue": 0} for arm in ARMS}
        targets = {r["output_id"]: r["target"] for r in packet}
        for row in rows:
            oid = row["output_id"]
            c = counts[mapping[oid]["arm"]]
            lp = length_pass(row["sentence_count"], targets[oid]["length"])
            c["outputs"] += 1
            c["length_pass"] += lp
            c["wording_pass"] += row["wording_pass"]
            c["both_conditions_pass"] += lp and row["wording_pass"]
            c["facts_preserved"] += sum(f["preserved"] for f in row["facts"])
            c["facts_total"] += 3
            c["outputs_with_factual_issue"] += bool(row["issues"])
        report["by_reviewer"][reviewer] = counts
    write_json(RUN / "scores.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["freeze", "blind", "score"])
    args = parser.parse_args()
    {"freeze": freeze, "blind": blind, "score": score}[args.command]()

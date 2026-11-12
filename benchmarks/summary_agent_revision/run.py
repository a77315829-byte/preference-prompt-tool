"""No-API, previously unused-source comparison: manual, old export, revised export."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from engine.domain_loader import load_domain
from engine.generator import build_final_prompt
from benchmarks.summary_agent_pilot.evaluate import validate_facts, validate_review, length_pass

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
RUN = BASE / "results" / "2026-11-10"
PREVIOUS = ROOT / "benchmarks/summary_agent_pilot/results/2026-11-10"
ARMS = ("manual", "previous", "revised")
SEED = 20261112


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def sample():
    if RUN.exists():
        raise SystemExit("Refusing to overwrite an existing run")
    previous = read(PREVIOUS / "cases.json")
    excluded = {c["source_sha256"] for c in previous}
    records = read(ROOT / "data/macsum/dataset/macdoc/test.json")
    pool = []
    for index, record in enumerate(records):
        source = "\n".join(record["source"])
        digest = hashlib.sha256(source.encode()).hexdigest()
        refs = [r for r in record["references"] if not r["control_attribute"].get("topic")]
        if digest not in excluded and 250 <= len(source.split()) <= 800 and len(record["source"]) >= 8 and refs:
            pool.append((index, record, source, digest, refs))
    random.Random(SEED).shuffle(pool)
    profiles = [c["profile"] for c in previous]
    random.Random(SEED + 1).shuffle(profiles)
    cases = []
    for i, ((index, record, source, digest, refs), profile) in enumerate(zip(pool[:9], profiles), 1):
        cases.append({"id": f"N{i:02d}", "record_index": index, "metadata": record["metadata"],
                      "source": source, "source_units": record["source"], "source_sha256": digest,
                      "source_words": len(source.split()), "profile": profile, "references": refs})
    assert len(cases) == 9 and len({c["source_sha256"] for c in cases}) == 9
    write(RUN / "cases.json", cases)
    write(RUN / "sampling.json", {"seed": SEED, "eligible_remaining": len(pool), "excluded_source_sha256": sorted(excluded),
          "new_source_sha256": [c["source_sha256"] for c in cases], "overlap_with_previous": 0,
          "previous_cases_sha256": sha(PREVIOUS / "cases.json"),
          "dataset_sha256": sha(ROOT / "data/macsum/dataset/macdoc/test.json")})
    print("Selected 9 distinct sources with zero overlap with the previous 9; no output generated.")


def freeze():
    cases = read(RUN / "cases.json")
    validate_facts(cases, read(RUN / "facts.json"))
    previous = read(PREVIOUS / "cases.json")
    old_by_profile = {tuple(sorted(c["profile"].items())): c for c in previous}
    domain = load_domain(ROOT / "domains/summarization_grounded.yaml")
    inputs = {arm: [] for arm in ARMS}
    for case in cases:
        old = old_by_profile[tuple(sorted(case["profile"].items()))]
        prompts = {"manual": old["prompts"]["manual"], "previous": old["prompts"]["assembled"],
                   "revised": build_final_prompt(domain, case["profile"], language="en")}
        for arm in ARMS:
            inputs[arm].append({"id": case["id"], "prompt": prompts[arm], "source": case["source"]})
    for arm in ARMS:
        write(RUN / "inputs" / f"{arm}.json", inputs[arm])
    protocol = {
        "version": 2, "frozen_utc": datetime.now(timezone.utc).isoformat(), "arms": list(ARMS),
        "sources": 9, "outputs": 27, "external_paid_api_calls": 0,
        "sampling": "Same MACSum news eligibility as pilot; exclude all 9 previous source hashes before seeded shuffle. One document per length/wording combination.",
        "baselines": "Manual and previous-export prompt strings copied unchanged by profile from archived pilot. Revised arm uses actual new domain/export builder. Whole-prompt comparison, not identical-policy formatting comparison.",
        "leakage_control": "Prompt/check developer instructed not to access these sources. Fact annotator sees sources/references but no generated outputs. Freeze prompts/anchors/rubric before generation; no retries or prompt tuning after heldout responses.",
        "primary": ["sentence-length compliance", "blinded wording instruction compliance", "coverage of three pre-frozen atomic central propositions", "source-supported factuality audit over entire summary"],
        "secondary": ["legacy overlap proxy", "revised overlap proxy", "revised literal extraction check", "automatic versus reviewed sentence count"],
        "evaluation_changes": "Publisher prefix removal and whitespace normalization allowed explicitly in revised instructions/rubric. Existing overlap score is diagnostic, not a factuality/semantic preference score. Atomic anchors avoid making incidental detail mandatory. Compare all 3 arms under the SAME revised rubric, never compare absolute coverage directly against previous corpus.",
        "generation": "Three fresh independent subagents, inherited same runtime model/settings, one arm with 9 tasks per context, no parent conversation. Read only assigned input and operational rules. First submissions cached; no paid API.",
        "review": "Two fresh blinded same-runtime reviewers, no condition names/prompts/automatic metrics. Exact evidence validated; report disagreements and all factual-issue flags, retain ranges where ambiguous.",
        "no_claims": ["human preference recovery", "optimal selection count", "time saving", "adoption", "statistical superiority or equivalence", "unseen in model training", "Korean semantic accuracy"],
        "gepa": "Not run. Fixing criteria precedes optimization. These new test sources must not be used for subsequent tuning and then reported as an independent test again."
    }
    write(RUN / "protocol.json", protocol)
    paths = [RUN / n for n in ("cases.json", "facts.json", "sampling.json", "protocol.json")]
    paths += [RUN / "inputs" / f"{arm}.json" for arm in ARMS]
    paths += [BASE / "rubric.json", Path(__file__), ROOT / "domains/summarization_grounded.yaml",
              ROOT / "checks/summarization_grounded.py", ROOT / "engine/generator.py",
              ROOT / "benchmarks/summary_agent_pilot/evaluate.py"]
    write(RUN / "frozen.json", {str(p.relative_to(ROOT)): sha(p) for p in paths})
    print("Frozen prompts, anchors, rubric and implementation before generation.")


def verify():
    for path, digest in read(RUN / "frozen.json").items():
        assert sha(ROOT / path) == digest, path
    cases = read(RUN / "cases.json")
    sampling = read(RUN / "sampling.json")
    assert not ({c["source_sha256"] for c in cases} & set(sampling["excluded_source_sha256"]))
    for c in cases:
        assert hashlib.sha256(c["source"].encode()).hexdigest() == c["source_sha256"]
    if (RUN / "generation_seal.json").exists():
        for path, digest in read(RUN / "generation_seal.json").items():
            assert sha(ROOT / path) == digest, path


def blind():
    verify()
    from checks import summarization_grounded as revised
    from checks.summarization import _bigrams, _words, _sentences
    cases = {c["id"]: c for c in read(RUN / "cases.json")}
    facts = {r["id"]: r["facts"] for r in read(RUN / "facts.json")}
    entries = []
    for arm in ARMS:
        rows = read(RUN / "outputs" / f"{arm}.json")
        assert len(rows) == len(cases) and {r["id"] for r in rows} == set(cases)
        for row in rows:
            assert isinstance(row["summary"], str) and row["summary"].strip()
            entries.append((arm, cases[row["id"]], row["summary"]))
    random.Random(SEED + 2).shuffle(entries)
    packet, mapping, automatic = [], {}, []
    domain = load_domain(ROOT / "domains/summarization_grounded.yaml")
    for i, (arm, case, summary) in enumerate(entries, 1):
        oid = f"R{i:02d}"
        packet.append({"output_id": oid, "case_id": case["id"], "source": case["source"],
                       "target": case["profile"], "key_facts": facts[case["id"]], "summary": summary})
        mapping[oid] = {"arm": arm, "case_id": case["id"]}
        ob, sb = _bigrams(_words(summary)), _bigrams(_words(case["source"]))
        overlap = len(ob & sb) / len(ob) if ob else 0.0
        value = case["profile"]["extractiveness"]
        check = domain.axis("extractiveness").check_for(value)
        score, feedback = getattr(revised, check.fn)(summary, case["source"], value, check.target)
        lc = domain.axis("length").check_for(case["profile"]["length"])
        ls, lf = getattr(revised, lc.fn)(summary, case["source"], case["profile"]["length"], lc.target)
        automatic.append({"output_id": oid, **mapping[oid], "legacy_sentence_count": len(_sentences(summary)),
                          "revised_length_score": ls, "revised_length_feedback": lf, "bigram_overlap": overlap,
                          "legacy_overlap_pass": {"normal": overlap <= .5, "high": .5 <= overlap <= .75, "fully": overlap >= .75}[value],
                          "revised_wording_score": score, "revised_wording_feedback": feedback,
                          "words": len(summary.split())})
    write(RUN / "blind_packet.json", packet)
    write(RUN / "blind_mapping.json", mapping)
    write(RUN / "automatic.json", automatic)
    paths = [RUN / "outputs" / f"{arm}.json" for arm in ARMS]
    paths += [RUN / n for n in ("blind_packet.json", "blind_mapping.json", "automatic.json")]
    write(RUN / "generation_seal.json", {str(p.relative_to(ROOT)): sha(p) for p in paths})
    print("Prepared and sealed 27 anonymous outputs.")


def score():
    verify()
    packet = read(RUN / "blind_packet.json")
    by_id = {r["output_id"]: r for r in packet}
    mapping = read(RUN / "blind_mapping.json")
    reviews = {key: read(RUN / f"review_{key}.json") for key in ("a", "b")}
    report = {"outputs": len(packet), "by_reviewer": {}, "disagreements": [], "all_factual_flag_ids": []}
    for key, rows in reviews.items():
        validate_review(rows, packet)
        counts = {}
        for arm in ARMS:
            rr = [r for r in rows if mapping[r["output_id"]]["arm"] == arm]
            lengths = [length_pass(r["sentence_count"], by_id[r["output_id"]]["target"]["length"]) for r in rr]
            counts[arm] = {"outputs": len(rr), "length_pass": sum(lengths), "wording_pass": sum(r["wording_pass"] for r in rr),
                           "both_conditions_pass": sum(l and r["wording_pass"] for l, r in zip(lengths, rr)),
                           "facts_preserved": sum(f["preserved"] for r in rr for f in r["facts"]), "facts_total": len(rr)*3,
                           "outputs_with_factual_issue": sum(bool(r["issues"]) for r in rr)}
        report["by_reviewer"][key] = counts
    a, b = [{r["output_id"]: r for r in reviews[key]} for key in ("a", "b")]
    report["agreement"] = {"sentences": 0, "wording": 0, "facts": 0}
    for oid in by_id:
        fa, fb = [{f["id"]: f["preserved"] for f in row[oid]["facts"]} for row in (a,b)]
        report["agreement"]["sentences"] += a[oid]["sentence_count"] == b[oid]["sentence_count"]
        report["agreement"]["wording"] += a[oid]["wording_pass"] == b[oid]["wording_pass"]
        report["agreement"]["facts"] += sum(fa[k] == fb[k] for k in fa)
        if fa != fb or a[oid]["sentence_count"] != b[oid]["sentence_count"] or a[oid]["wording_pass"] != b[oid]["wording_pass"]:
            report["disagreements"].append(oid)
        if a[oid]["issues"] or b[oid]["issues"]:
            report["all_factual_flag_ids"].append(oid)
    write(RUN / "scores.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["sample", "freeze", "blind", "score", "verify"])
    args = parser.parse_args()
    globals()[args.command]()

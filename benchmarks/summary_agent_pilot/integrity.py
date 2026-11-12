"""Additional post-generation integrity guard; does not change frozen scoring rules."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from benchmarks.summary_agent_pilot.evaluate import ARMS, measurements, read, verify_frozen
from benchmarks.summary_agent_pilot.prepare import ROOT, RUN, write_json
from engine.domain_loader import load_domain
from engine.generator import build_final_prompt


def check_links() -> None:
    verify_frozen()
    for name, expected in read(RUN / "protocol.json")["code_hashes"].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    cases = {c["id"]: c for c in read(RUN / "cases.json")}
    facts = {r["id"]: r["facts"] for r in read(RUN / "facts.json")}
    domain = load_domain(ROOT / "domains/summarization.yaml")
    outputs = {}
    for arm in ARMS:
        inputs = read(RUN / "inputs" / f"{arm}.json")
        rows = read(RUN / "outputs" / f"{arm}.json")
        assert len(inputs) == len(rows) == len(cases)
        assert {r["id"] for r in inputs} == {r["id"] for r in rows} == set(cases)
        outputs[arm] = {r["id"]: r["summary"] for r in rows}
        for item in inputs:
            case = cases[item["id"]]
            assert item["source"] == case["source"]
            assert item["prompt"] == case["prompts"][arm]
    for case in cases.values():
        assert case["source_sha256"] == hashlib.sha256(case["source"].encode()).hexdigest()
        assert case["prompts"]["assembled"] == build_final_prompt(domain, case["profile"], language="en")
    packet = read(RUN / "blind_packet.json")
    mapping = read(RUN / "blind_mapping.json")
    automatic = read(RUN / "automatic.json")
    assert len(packet) == len(mapping) == len(automatic) == 27
    assert len({r["output_id"] for r in packet}) == 27
    assert len({(v["arm"], v["case_id"]) for v in mapping.values()}) == 27
    by_id = {r["output_id"]: r for r in automatic}
    assert set(by_id) == set(mapping) == {r["output_id"] for r in packet}
    for item in packet:
        oid = item["output_id"]
        link = mapping[oid]
        case = cases[link["case_id"]]
        summary = outputs[link["arm"]][link["case_id"]]
        assert item["case_id"] == case["id"]
        assert item["source"] == case["source"] and item["target"] == case["profile"]
        assert item["key_facts"] == facts[case["id"]] and item["summary"] == summary
        assert by_id[oid] == {"output_id": oid, **link, **measurements(summary, case)}


def seal() -> None:
    check_links()
    paths = [RUN / "outputs" / f"{arm}.json" for arm in ARMS]
    paths += [RUN / name for name in ("blind_packet.json", "blind_mapping.json", "automatic.json")]
    paths += [Path(__file__)]
    write_json(RUN / "generation_seal.json", {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
    })
    print("Sealed 27 outputs, blind mapping, and automatic measurements after consistency checks.")


def verify() -> None:
    check_links()
    for name, expected in read(RUN / "generation_seal.json").items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    print("Frozen protocol, current builder, 27 outputs, mapping and automatic measurements verified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["seal", "verify"])
    args = parser.parse_args()
    {"seal": seal, "verify": verify}[args.command]()

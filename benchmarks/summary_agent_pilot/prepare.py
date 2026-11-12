"""Freeze a no-API, three-arm summary pilot using the current exported prompt."""
from __future__ import annotations

import hashlib
import itertools
import json
import random
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from engine.domain_loader import load_domain
from engine.generator import build_final_prompt

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
RUN = BASE / "results" / "2026-11-10"
SEED = 20261110


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def prepare() -> None:
    if RUN.exists():
        raise SystemExit(f"Refusing to overwrite frozen run: {RUN}")
    dataset = ROOT / "data/macsum/dataset/macdoc/test.json"
    raw = dataset.read_bytes()
    records = json.loads(raw)
    eligible = []
    for index, record in enumerate(records):
        source = "\n".join(record["source"])
        refs = [r for r in record["references"] if not r["control_attribute"].get("topic")]
        if 250 <= len(source.split()) <= 800 and len(record["source"]) >= 8 and refs:
            eligible.append((index, record, source, refs))
    random.Random(SEED).shuffle(eligible)
    profiles = list(itertools.product(["short", "normal", "long"], ["normal", "high", "fully"]))
    random.Random(SEED + 1).shuffle(profiles)
    domain = load_domain(ROOT / "domains/summarization.yaml")
    length = {
        "short": "Use no more than two sentences.",
        "normal": "Use three to four sentences.",
        "long": "Use at least five sentences and include detail.",
    }
    wording = {
        "normal": "Mostly paraphrase in your own words, retaining original wording only where helpful.",
        "high": "Reuse the original words and phrases as much as possible.",
        "fully": "Use only complete sentences copied verbatim from the source; do not write new sentences.",
    }
    cases = []
    arms: dict[str, list[dict]] = {k: [] for k in ("general", "manual", "assembled")}
    for n, ((index, record, source, refs), (size, extract)) in enumerate(zip(eligible[:9], profiles), 1):
        case_id = f"S{n:02d}"
        combo = {"length": size, "extractiveness": extract, "topic": ""}
        prompts = {
            "general": "Summarize the following source in English. Output only the summary.",
            "manual": " ".join([
                "Summarize the following source in English.", length[size], wording[extract],
                "Do not invent facts, guesses, or opinions. Preserve numbers, dates, names, and attribution accurately.",
                "Distinguish confirmed information from allegations, plans, and uncertainty.",
                "Output only the summary, without a title, preamble, explanation, or closing.",
            ]),
            "assembled": build_final_prompt(domain, combo, language="en"),
        }
        cases.append({
            "id": case_id, "record_index": index, "metadata": record["metadata"],
            "source": source, "source_units": record["source"], "source_sha256": digest(source.encode()),
            "source_words": len(source.split()), "profile": combo, "references": refs,
            "prompts": prompts,
        })
        for arm in arms:
            arms[arm].append({"id": case_id, "prompt": prompts[arm], "source": source})
    protocol = {
        "version": 1, "prepared_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "dataset": "MACSum macdoc/test.json", "dataset_sha256": digest(raw),
        "sampling": "Seeded shuffle; 250-800 whitespace words, >=8 source units, at least one no-topic reference; first 9 distinct records",
        "seed": SEED, "eligible_records": len(eligible), "cases": 9, "outputs": 27,
        "profiles": "All 3 length x 3 extractiveness combinations, one document per combination; no topic",
        "generator": "Three independent Codex subagents with no parent conversation, same inherited model/settings, one arm each; each arm receives all 9 tasks",
        "external_model_api_calls": 0, "selection_rounds": None,
        "selection_scope": "Confirmed target profiles injected into the actual export builder. No user selection, inference, GEPA, or prompt optimization in this pilot.",
        "manual_baseline": "Investigator-authored strong instructions, not written by recruited users; same target constraints and fidelity rules",
        "primary": ["requested sentence-length compliance", "blind wording-instruction review", "coverage of 3 pre-frozen source-grounded key facts", "blind audit of unsupported or distorted summary claims"],
        "secondary": ["current app bigram-overlap proxy with frozen YAML thresholds", "strict verbatim source-unit extraction", "summary/source word ratio", "novel digit tokens as flags only"],
        "reporting": "Separate length, wording, key-fact coverage, and factual problems; no combined score, significance claim, or human usability inference",
        "blind_review": "Two fresh independent reviewers see randomized output IDs, sources, frozen facts and target conditions; no arm names or generation prompts. Different wording may still reveal strategy. Root adjudicates disagreements with evidence.",
        "stop_rule": "One first submission per arm, no regeneration or prompt tuning after outputs. Keep failures. Reviewer amendments only for missing schema/evidence, never desired scores.",
        "limitations": ["9 news documents, one output per condition, profile and document confounded", "Within-arm shared context; instruction isolation not OS isolation", "Public corpus may be in model training and was examined in prior project work", "MACSum labels do not validate app sentence-count thresholds", "Content anchors and semantic judgments are AI-assisted, not human gold", "No Korean, dialogue, personal preference, time saving, or adoption claim"],
        "code_hashes": {name: digest((ROOT / name).read_bytes()) for name in [
            "domains/summarization.yaml", "engine/generator.py", "checks/summarization.py",
            "benchmarks/summary_agent_pilot/prepare.py",
        ]},
    }
    write_json(RUN / "protocol.json", protocol)
    write_json(RUN / "cases.json", cases)
    for arm, tasks in arms.items():
        write_json(RUN / "inputs" / f"{arm}.json", tasks)
    print(json.dumps({"run": str(RUN), "eligible": len(eligible), "cases": 9, "outputs": 27}))


if __name__ == "__main__":
    prepare()

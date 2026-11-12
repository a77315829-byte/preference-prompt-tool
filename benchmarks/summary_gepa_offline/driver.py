"""Run the installed GEPA engine using a local, externally serviced file queue.

No model client, model name, subprocess, credential lookup or network executor is
used. A coordinator supplies each first response through a fresh Codex agent.
This is an experimental adapter, not the production service.optimize pathway.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import socket
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmarks.summary_agent_pilot.evaluate import length_pass, validate_facts
from benchmarks.summary_reflection.audit import strict_review
from checks import summarization_grounded_v2 as checks
from engine.domain_loader import load_domain

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = Path(__file__).resolve().parent / "results" / "2026-11-10"
SEED = 20261114
MAX_REFLECTIONS = 2
MAX_UNIQUE_EVALUATIONS = 30
MAX_SUPPLEMENT_WORDS = 220

REFLECTION_TEMPLATE = """Improve a reusable supplementary instruction for source-grounded summarization.
The fixed base instruction and requested conditions in each example remain unchanged;
your text is appended to that base. You may not override its length, wording,
source-fidelity, language or summary-only requirements.

Current supplementary instruction (empty means no supplement):
```
<curr_param>
```

Training examples, first generated outputs, and source-grounded evaluation feedback:
<side_info>

Propose one generic supplement of at most 220 whitespace-separated words. Learn a
general selection or verification strategy from failures. Do NOT copy article
facts, names, numbers, quoted source passages or case-specific instructions into
the supplement. Do not include expected answers, evaluator identifiers, scoring
instructions, hidden-reasoning requests or claims of exhaustive coverage. Respect
the existing sentence budget and exact-copy restrictions; a short extractive
summary may not fit every central fact. Improve content preservation without
inventing links or turning uncertainty into certainty. If there is no supported
improvement, retaining the current supplement is allowed. Return only the new
supplement inside one fenced code block, with no language label.
"""


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    """Publish once; refuse to replace any previously published artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    temporary = path.with_suffix(path.suffix + ".pending")
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    # Windows rename fails if a destination appeared in the meantime.
    temporary.rename(path)


def verify_manifest(run_dir: Path) -> None:
    manifest = read(run_dir / "frozen.json")
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError("A nonempty frozen.json hash manifest is required")
    for name, expected in manifest.items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT.resolve()) or file_sha(path) != expected:
            raise ValueError(f"Frozen artifact changed: {name}")


@contextmanager
def network_disabled():
    """Fail closed if any imported library unexpectedly tries a socket call."""
    originals = (socket.create_connection, socket.socket.connect, socket.socket.connect_ex)

    def blocked(*args, **kwargs):
        raise RuntimeError("Network connections are disabled for this offline GEPA run")

    socket.create_connection = blocked
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    try:
        yield
    finally:
        socket.create_connection, socket.socket.connect, socket.socket.connect_ex = originals


class FileQueue:
    def __init__(self, run_dir: Path, timeout: float = 1800, poll: float = .25,
                 verify=None, responder=None):
        if timeout <= 0 or not 0 < poll <= 1:
            raise ValueError("Positive timeout and polling interval <= 1 second required")
        self.run_dir = Path(run_dir)
        self.timeout, self.poll = timeout, poll
        self.verify = verify or (lambda: None)
        self.responder = responder  # Synchronous local test hook; never a model client.
        self.requests = 0
        self.cache_hits = 0
        self.counts = {"generate": 0, "review": 0, "reflection": 0}
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def event(self, event_name: str, **payload) -> None:
        with (self.run_dir / "events.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps({"utc": utc(), "event": event_name, **payload}, ensure_ascii=False) + "\n")

    def exchange(self, kind: str, payload: dict) -> dict:
        if kind not in self.counts:
            raise ValueError("Unknown queue request kind")
        self.verify()
        cache_key = digest({"kind": kind, "payload": payload})
        cache_path = self.run_dir / "transport_cache" / f"{cache_key}.json"
        if cache_path.exists():
            cached = read(cache_path)
            request_path = self.run_dir / cached["request_path"]
            response_path = self.run_dir / cached["response_path"]
            if file_sha(request_path) != cached["request_sha256"] or file_sha(response_path) != cached["response_sha256"]:
                raise ValueError("Cached transport evidence changed")
            response = read(response_path)
            if response.get("request_sha256") != cached["request_sha256"]:
                raise ValueError("Cached response does not match its request")
            self.cache_hits += 1
            self.event("transport_cache_hit", kind=kind, cache_key=cache_key)
            return response
        self.requests += 1
        self.counts[kind] += 1
        request_id = f"{self.requests:04d}_{kind}"
        folder = self.run_dir / "queue" / request_id
        request_path, response_path = folder / "request.json", folder / "response.json"
        request = {"request_id": request_id, "kind": kind, "payload": payload, "created_utc": utc()}
        atomic_json(request_path, request)
        request_hash = file_sha(request_path)
        self.event("request_published", request_id=request_id, kind=kind, request_sha256=request_hash)
        print(f"PENDING {request_path}", flush=True)
        if self.responder is not None:
            reply = self.responder(request, request_hash)
            atomic_json(response_path, {"request_sha256": request_hash, **reply})
        start = time.monotonic()
        while True:
            if (self.run_dir / "STOP").exists():
                raise RuntimeError("Coordinator requested stop")
            if time.monotonic() - start >= self.timeout:
                raise TimeoutError(f"No complete response for {request_id}")
            if response_path.exists():
                try:
                    response = read(response_path)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    time.sleep(self.poll)
                    continue
                if not isinstance(response, dict) or response.get("request_sha256") != request_hash:
                    raise ValueError(f"Response hash mismatch: {request_id}")
                break
            time.sleep(self.poll)
        self.verify()
        atomic_json(cache_path, {"request_path": str(request_path.relative_to(self.run_dir)),
                    "response_path": str(response_path.relative_to(self.run_dir)),
                    "request_sha256": request_hash, "response_sha256": file_sha(response_path)})
        self.event("response_received", request_id=request_id, response_sha256=file_sha(response_path),
                   orchestration_wait_seconds=round(time.monotonic() - start, 3))
        return response


def fivegrams(text: str) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.casefold())
    return {tuple(words[i:i+5]) for i in range(max(0, len(words)-4))}


class OfflineAdapter:
    propose_new_texts = None  # Let GEPA's real reflection machinery own proposal generation.

    def __init__(self, queue: FileQueue, cases: list[dict], facts: list[dict], max_unique=30):
        validate_facts(cases, facts)
        if len({c["id"] for c in cases}) != len(cases):
            raise ValueError("Case IDs must be unique across train and validation")
        for case in cases:
            if hashlib.sha256(case["source"].encode("utf-8")).hexdigest() != case["source_sha256"]:
                raise ValueError("Case source hash mismatch")
            if not isinstance(case["base_prompt"], str) or not case["base_prompt"].strip():
                raise ValueError("Fixed base instruction must be nonempty text")
        self.queue = queue
        self.cases = {c["id"]: c for c in cases}
        self.facts = {f["id"]: f["facts"] for f in facts}
        self.domain = load_domain(ROOT / "domains/summarization_grounded_v2.yaml")
        self.source_grams = set().union(*(fivegrams(c["source"]) for c in cases))
        self.allowed_grams = set().union(*(fivegrams(c["base_prompt"]) for c in cases))
        self.max_unique = max_unique
        self.unique_evaluations = 0
        self.cache_hits = 0
        self.generated_summaries = 0
        self.semantic_reviews = 0
        self.invalid_candidates = []

    def candidate_error(self, candidate: dict) -> str | None:
        if not isinstance(candidate, dict) or set(candidate) != {"supplement"} or not isinstance(candidate["supplement"], str):
            return "Candidate must contain only a string supplement"
        supplement = candidate["supplement"]
        if len(supplement.split()) > MAX_SUPPLEMENT_WORDS:
            return f"Supplement exceeds {MAX_SUPPLEMENT_WORDS} words"
        leaked = sorted((fivegrams(supplement) & self.source_grams) - self.allowed_grams)
        if leaked:
            return "Possible source-specific five-word leakage: " + "; ".join(" ".join(g) for g in leaked[:5])
        return None

    @staticmethod
    def prompt(case: dict, supplement: str) -> str:
        return case["base_prompt"] + ("\n\n" + supplement if supplement else "")

    def key(self, case: dict, supplement: str) -> str:
        return digest({"source": case["source"], "profile": case["profile"],
                       "prompt": self.prompt(case, supplement)})

    def evaluate(self, batch, candidate, capture_traces=False):
        from gepa.core.adapter import EvaluationBatch
        if not batch or any(c["id"] not in self.cases or c != self.cases[c["id"]] for c in batch):
            raise ValueError("Only the fixed training/validation cases may be evaluated")
        error = self.candidate_error(candidate)
        if error:
            self.invalid_candidates.append({"candidate": candidate, "reason": error})
            self.queue.event("invalid_candidate", candidate=candidate, reason=error)
            # A rejected instruction must lose even against a valid zero-score
            # parent when GEPA's improvement-or-equal exploration is enabled.
            records = [{"case": c, "summary": "", "score": -1.0, "feedback": error,
                        "objective_scores": {"coverage": 0.0, "conditions": 0.0, "no_factual_flags": 0.0}}
                       for c in batch]
            return EvaluationBatch(outputs=[{"summary": ""} for _ in batch], scores=[-1.0]*len(batch),
                                   trajectories=records if capture_traces else None,
                                   objective_scores=[r["objective_scores"] for r in records], num_metric_calls=0)
        supplement = candidate["supplement"]
        paths = {c["id"]: self.queue.run_dir / "evaluation_cache" / f"{self.key(c, supplement)}.json" for c in batch}
        missing = [c for c in batch if not paths[c["id"]].exists()]
        if self.unique_evaluations + len(missing) > self.max_unique:
            raise RuntimeError("Hard unique-evaluation budget would be exceeded")
        self.cache_hits += len(batch)-len(missing)
        if missing:
            request_rows = [{"id": c["id"], "prompt": self.prompt(c, supplement), "source": c["source"]} for c in missing]
            response = self.queue.exchange("generate", {"rows": request_rows})
            rows = response.get("rows")
            expected_ids = {c["id"] for c in missing}
            if not isinstance(rows, list) or len(rows) != len(expected_ids) or {r.get("id") for r in rows} != expected_ids:
                raise ValueError("Generation IDs/count do not match request")
            if any(not isinstance(r.get("summary"), str) or not r["summary"].strip() for r in rows):
                raise ValueError("A generated summary is empty or not text")
            summaries = {r["id"]: r["summary"] for r in rows}
            self.generated_summaries += len(rows)
            packet = [{"output_id": "Q" + self.key(c, supplement)[:16], "case_id": c["id"],
                       "source": c["source"], "target": c["profile"], "key_facts": self.facts[c["id"]],
                       "summary": summaries[c["id"]]} for c in missing]
            review_response = self.queue.exchange("review", {"packet": packet})
            reviews = review_response.get("rows")
            if not isinstance(reviews, list):
                raise ValueError("Review response rows must be a list")
            strict_review(reviews, packet)
            by_output = {r["output_id"]: r for r in reviews}
            self.semantic_reviews += len(reviews)
            for c, item in zip(missing, packet, strict=True):
                review = by_output[item["output_id"]]
                summary = summaries[c["id"]]
                automatic = {}
                for axis in ("length", "extractiveness"):
                    value = c["profile"][axis]
                    spec = self.domain.axis(axis).check_for(value)
                    score, feedback = getattr(checks, spec.fn)(summary, c["source"], value, spec.target)
                    automatic[axis] = {"score": score, "feedback": feedback}
                coverage = sum(f["preserved"] for f in review["facts"]) / 3
                conditions = (length_pass(review["sentence_count"], c["profile"]["length"])
                              and review["wording_pass"] and all(x["score"] == 1.0 for x in automatic.values()))
                supported = not review["issues"]
                scalar = coverage if conditions and supported else 0.0
                feedback = json.dumps({"preserved_facts": review["facts"], "factual_issues": review["issues"],
                                       "reviewed_wording": review["wording_reason"], "automatic": automatic,
                                       "score_rule": "coverage only when all condition checks pass and no factual issue is flagged"}, ensure_ascii=False)
                record = {"cache_key": self.key(c, supplement), "case": c, "supplement": supplement,
                          "summary": summary, "score": scalar, "feedback": feedback, "review": review,
                          "automatic": automatic, "objective_scores": {"coverage": coverage,
                          "conditions": float(conditions), "no_factual_flags": float(supported)}}
                atomic_json(paths[c["id"]], record)
                self.unique_evaluations += 1
                self.queue.event("evaluation_saved", case_id=c["id"], cache_key=record["cache_key"],
                                 score=scalar, objective_scores=record["objective_scores"])
        records = [read(paths[c["id"]]) for c in batch]
        for c, record in zip(batch, records, strict=True):
            if record["cache_key"] != self.key(c, supplement) or record["case"] != c or record["supplement"] != supplement:
                raise ValueError("Evaluation cache identity mismatch")
        return EvaluationBatch(outputs=[{"summary": r["summary"]} for r in records],
                               scores=[r["score"] for r in records],
                               trajectories=records if capture_traces else None,
                               objective_scores=[r["objective_scores"] for r in records],
                               num_metric_calls=len(missing))

    def make_reflective_dataset(self, candidate, eval_batch, components_to_update):
        if components_to_update != ["supplement"] or eval_batch.trajectories is None:
            raise ValueError("Only supplement reflection with captured traces is supported")
        return {"supplement": [{"Inputs": {"fixed_base_instruction": r["case"]["base_prompt"],
                  "source": r["case"]["source"]}, "Generated Outputs": r["summary"],
                  "Feedback": r["feedback"]} for r in eval_batch.trajectories]}


class QueueReflection:
    def __init__(self, queue: FileQueue, max_calls=MAX_REFLECTIONS):
        self.queue, self.max_calls = queue, max_calls
        self.calls = 0
        self.responses = []
        self.failure = None

    def __call__(self, prompt):
        if self.failure is not None:
            raise RuntimeError("Reflection transport previously failed; refusing retry")
        if self.calls >= self.max_calls:
            raise RuntimeError("Reflection proposal budget exhausted")
        self.calls += 1
        try:
            response = self.queue.exchange("reflection", {"prompt": prompt})
            if not isinstance(response.get("text"), str) or not response["text"].strip():
                raise ValueError("Reflection must return nonempty text")
        except Exception as exc:
            # GEPA may retry its reflection callable. Preserve a fatal transport
            # error rather than issuing another model request or hiding failure.
            self.failure = f"{type(exc).__name__}: {exc}"
            raise
        self.responses.append({"ordinal": self.calls, "prompt_sha256": digest(prompt), "text": response["text"]})
        return response["text"]


class StopAfterReflections:
    def __init__(self, reflection):
        self.reflection = reflection

    def __call__(self, state):
        # GEPA checks this at the next iteration boundary, after current validation.
        return self.reflection.failure is not None or self.reflection.calls >= self.reflection.max_calls


def optimize(adapter: OfflineAdapter, reflection: QueueReflection, engine_dir: Path):
    from gepa import optimize as gepa_optimize
    train = [c for c in adapter.cases.values() if c["id"].startswith("G")]
    validation = [c for c in adapter.cases.values() if c["id"].startswith("V")]
    if not train or not validation:
        raise ValueError("Expected G-prefixed training and V-prefixed validation IDs")
    return gepa_optimize(seed_candidate={"supplement": ""}, trainset=train, valset=validation,
                         adapter=adapter, reflection_lm=reflection,
                         reflection_prompt_template=REFLECTION_TEMPLATE,
                         candidate_selection_strategy="pareto", frontier_type="instance",
                         reflection_minibatch_size=3, acceptance_criterion="improvement_or_equal",
                         skip_perfect_score=False, use_merge=False,
                         max_metric_calls=30, stop_callbacks=StopAfterReflections(reflection),
                         run_dir=str(engine_dir), use_wandb=False, use_mlflow=False,
                         track_best_outputs=True, display_progress_bar=False,
                         # List-backed train/validation loaders both use 0..N IDs.
                         # Keep GEPA's shared ID cache off; our cache keys include
                         # source, profile and full prompt and are split-safe.
                         cache_evaluation=False, seed=SEED, raise_on_exception=True)


def run(run_dir: Path = DEFAULT_RUN):
    run_dir = Path(run_dir).resolve()
    if not run_dir.is_relative_to(ROOT.resolve()):
        raise ValueError("Run directory must remain in this repository")
    verify_manifest(run_dir)
    cases, facts = [], []
    for split in ("train", "validation"):
        cases.extend(read(run_dir / split / "cases.json"))
        facts.extend(read(run_dir / split / "facts.json"))
    atomic_json(run_dir / "driver_started.json", {"utc": utc(), "gepa_version": importlib.metadata.version("gepa"),
                "final_data_loaded": False, "network_connections_disabled": True,
                "max_reflections": MAX_REFLECTIONS, "max_unique_evaluations": MAX_UNIQUE_EVALUATIONS,
                "framework": "installed gepa.optimize, custom offline adapter and callable reflection"})
    queue = FileQueue(run_dir, verify=lambda: verify_manifest(run_dir))
    adapter = OfflineAdapter(queue, cases, facts, MAX_UNIQUE_EVALUATIONS)
    reflection = QueueReflection(queue)
    try:
        with network_disabled():
            result = optimize(adapter, reflection, run_dir / "engine")
        if reflection.failure is not None:
            raise RuntimeError(reflection.failure)
        verify_manifest(run_dir)
        candidates = result.candidates
        nonseed = [i for i, c in enumerate(candidates) if c["supplement"]]
        exploratory = max(nonseed, key=lambda i: result.val_aggregate_scores[i]) if nonseed else None
        report = {"completed_utc": utc(), "gepa_version": importlib.metadata.version("gepa"),
                  "candidates": candidates, "val_scores": result.val_aggregate_scores,
                  "best_index": result.best_idx, "best_supplement": candidates[result.best_idx]["supplement"],
                  "best_nonseed_index": exploratory, "parents": result.parents, "raw_gepa_result": result.to_dict(),
                  "reflections": reflection.responses, "invalid_candidates": adapter.invalid_candidates,
                  "counts": {"reflection_calls": reflection.calls, "unique_evaluations": adapter.unique_evaluations,
                  "generated_summaries": adapter.generated_summaries, "semantic_reviews": adapter.semantic_reviews,
                  "evaluation_cache_hits": adapter.cache_hits, "queue_requests": queue.requests,
                  "queue_by_kind": queue.counts, "transport_cache_hits": queue.cache_hits,
                  "gepa_total_metric_calls": result.total_metric_calls},
                  "external_paid_model_api_calls": 0, "actual_gepa_engine": True,
                  "runtime_model_identifier": None, "codex_usage_metered": False,
                  "limitations": ["Same runtime AI feedback is not human gold truth.",
                  "Two reflective proposals are a bounded pilot, not an exhaustive GEPA search.",
                  "Network is blocked in this process; coordinator-supplied replies are outside this process.",
                  "Socket blocking is defensive instrumentation, not a complete OS sandbox.",
                  "Five-word leakage filtering is conservative and can reject generic overlaps.",
                  "This content metric/custom adapter differs from production format-only optimization.",
                  "Ties retain GEPA's first maximum (the seed when tied); exploratory candidate is not an adopted winner.",
                  "Queue wait timestamps include coordination and cannot measure model inference latency."]}
        atomic_json(run_dir / "gepa_result.json", report)
        queue.event("completed", best_index=result.best_idx, unique_evaluations=adapter.unique_evaluations)
        print(f"COMPLETE GEPA best={result.best_idx}; candidates={len(candidates)}; reflections={reflection.calls}", flush=True)
        return report
    except Exception as exc:
        queue.event("failed", error_type=type(exc).__name__, message=str(exc))
        atomic_json(run_dir / "driver_failure.json", {"utc": utc(), "error_type": type(exc).__name__, "message": str(exc)})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN)
    run(parser.parse_args().run_dir)

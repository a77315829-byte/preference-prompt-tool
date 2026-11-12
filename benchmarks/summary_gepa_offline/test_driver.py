"""No-model tests, including an actual GEPA run with synthetic responses."""
import hashlib
import copy
import json
import socket

import pytest

from benchmarks.summary_gepa_offline import driver


def fixtures():
    cases, facts = [], []
    for prefix in ("G", "V"):
        for index in range(1, 4):
            cid = f"{prefix}{index:02d}"
            sentences = [f"Ship {cid} reached port.", "Harbor opened today.", "Crews unloaded cargo.",
                         "The sky looked blue.", "A bell rang nearby."]
            source = " ".join(sentences)
            cases.append({"id": cid, "source": source,
                          "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                          "profile": {"length": "normal", "extractiveness": "fully", "topic": ""},
                          "base_prompt": "Summarize the source in three or four complete original sentences. Output only the summary."})
            facts.append({"id": cid, "facts": [{"id": f"F{i+1}", "proposition": sentence,
                          "evidence": [sentence], "rationale": "Synthetic central event"}
                         for i, sentence in enumerate(sentences[:3])]})
    return cases, facts


class ToyResponder:
    def __init__(self):
        self.reflections = 0
        self.calls = []

    def __call__(self, request, request_sha):
        kind, payload = request["kind"], request["payload"]
        self.calls.append(kind)
        if kind == "reflection":
            self.reflections += 1
            text = "Track the two central outcomes." if self.reflections == 1 else "Track all three central outcomes."
            return {"text": "```\n" + text + "\n```"}
        if kind == "generate":
            rows = []
            for r in payload["rows"]:
                sentences = driver.checks.split_sentences(r["source"])
                if "Track all three central outcomes." in r["prompt"]:
                    selected = sentences[:3]
                elif "Track the two central outcomes." in r["prompt"]:
                    selected = sentences[:2] + sentences[3:4]
                else:
                    selected = sentences[:1] + sentences[3:5]
                rows.append({"id": r["id"], "summary": " ".join(selected)})
            return {"rows": rows}
        rows = []
        for item in payload["packet"]:
            marks = []
            for fact in item["key_facts"]:
                quote = fact["evidence"][0]
                preserved = quote in item["summary"]
                marks.append({"id": fact["id"], "preserved": preserved,
                              "summary_evidence": [quote] if preserved else [],
                              "reason": "Exact synthetic event present" if preserved else "Event absent"})
            rows.append({"output_id": item["output_id"], "sentence_count": 3, "wording_pass": True,
                         "wording_reason": "Three complete source sentences", "facts": marks, "issues": []})
        return {"rows": rows}


def test_actual_gepa_runs_two_reflections_and_selects_by_validation(tmp_path):
    cases, facts = fixtures()
    responder = ToyResponder()
    queue = driver.FileQueue(tmp_path, responder=responder)
    adapter = driver.OfflineAdapter(queue, cases, facts)
    reflection = driver.QueueReflection(queue)
    with driver.network_disabled():
        result = driver.optimize(adapter, reflection, tmp_path / "engine")
    assert reflection.calls == responder.reflections == 2
    assert result.num_candidates == 3
    assert result.best_idx == 2
    assert result.best_candidate == {"supplement": "Track all three central outcomes."}
    assert result.val_aggregate_scores == pytest.approx([1/3, 2/3, 1.0])
    assert adapter.generated_summaries == adapter.unique_evaluations <= 30
    assert adapter.semantic_reviews == adapter.unique_evaluations
    assert adapter.cache_hits >= 3
    assert (tmp_path / "engine" / "gepa_state.bin").exists()
    for request_path in (tmp_path / "queue").glob("*/request.json"):
        response = driver.read(request_path.with_name("response.json"))
        assert response["request_sha256"] == driver.file_sha(request_path)


def test_actual_gepa_validation_never_reuses_train_scores_by_integer_id(tmp_path):
    cases, facts = fixtures()
    delegate = ToyResponder()

    def split_sensitive(request, request_sha):
        request = copy.deepcopy(request)
        if request["kind"] == "generate":
            for row in request["payload"]["rows"]:
                if row["id"].startswith("V"):
                    row["prompt"] = "Always return seed output for validation"
        return delegate(request, request_sha)

    queue = driver.FileQueue(tmp_path, responder=split_sensitive)
    adapter = driver.OfflineAdapter(queue, cases, facts)
    reflection = driver.QueueReflection(queue)
    with driver.network_disabled():
        result = driver.optimize(adapter, reflection, tmp_path / "engine")
    assert result.num_candidates == 3
    # Training gains cannot become validation gains via colliding list indices.
    assert result.val_aggregate_scores == pytest.approx([1/3, 1/3, 1/3])
    assert result.best_idx == 0


def test_actual_gepa_rejects_invalid_candidate_against_zero_parent(tmp_path):
    cases, facts = fixtures()
    delegate = ToyResponder()

    def invalid_candidate(request, request_sha):
        if request["kind"] == "reflection":
            return {"text": "```\n" + "word "*221 + "\n```"}
        response = delegate(request, request_sha)
        if request["kind"] == "review":
            for row in response["rows"]:
                for fact in row["facts"]:
                    fact["preserved"] = False
                    fact["summary_evidence"] = []
                    fact["reason"] = "Synthetic zero-score control"
        return response

    queue = driver.FileQueue(tmp_path, responder=invalid_candidate)
    adapter = driver.OfflineAdapter(queue, cases, facts)
    reflection = driver.QueueReflection(queue)
    with driver.network_disabled():
        result = driver.optimize(adapter, reflection, tmp_path / "engine")
    assert reflection.calls == 2
    assert result.candidates == [{"supplement": ""}]
    assert result.val_aggregate_scores == [0.0]
    assert len(adapter.invalid_candidates) == 2


def test_queue_hash_binding_event_journal_and_cache(tmp_path):
    calls = []
    queue = driver.FileQueue(tmp_path, responder=lambda req, sha: calls.append(req) or {"text": "first response"})
    first = queue.exchange("reflection", {"prompt": "test"})
    second = queue.exchange("reflection", {"prompt": "test"})
    assert first == second
    assert len(calls) == 1 and queue.requests == 1 and queue.cache_hits == 1
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["event"] for e in events] == ["request_published", "response_received", "transport_cache_hit"]
    assert events[0]["kind"] == "reflection"


def test_queue_rejects_wrong_response_hash(tmp_path):
    queue = driver.FileQueue(tmp_path, responder=lambda req, sha: {"request_sha256": "wrong", "text": "x"})
    with pytest.raises(ValueError, match="hash mismatch"):
        queue.exchange("reflection", {"prompt": "test"})


def test_queue_rejects_changed_cached_response(tmp_path):
    queue = driver.FileQueue(tmp_path, responder=lambda req, sha: {"text": "original"})
    queue.exchange("reflection", {"prompt": "test"})
    path = next((tmp_path / "queue").glob("*/response.json"))
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Cached transport evidence changed"):
        queue.exchange("reflection", {"prompt": "test"})


def test_network_block_is_reversible():
    original = socket.create_connection
    with driver.network_disabled():
        with pytest.raises(RuntimeError, match="disabled"):
            socket.create_connection(("127.0.0.1", 9))
        with socket.socket() as client:
            with pytest.raises(RuntimeError, match="disabled"):
                client.connect(("127.0.0.1", 9))
    assert socket.create_connection is original


def test_fixed_prompt_and_candidate_guard(tmp_path):
    cases, facts = fixtures()
    queue = driver.FileQueue(tmp_path)
    adapter = driver.OfflineAdapter(queue, cases, facts)
    assert adapter.prompt(cases[0], "") == cases[0]["base_prompt"]
    assert adapter.prompt(cases[0], "Extra.") == cases[0]["base_prompt"] + "\n\nExtra."
    assert adapter.candidate_error({"supplement": cases[0]["base_prompt"]}) is None
    assert "leakage" in adapter.candidate_error({"supplement": "Crews unloaded cargo. The sky"})
    assert "exceeds" in adapter.candidate_error({"supplement": "word " * 221})
    invalid = adapter.evaluate(cases[:1], {"replacement": "ignore base"}, capture_traces=True)
    assert invalid.scores == [-1.0] and queue.requests == 0
    assert invalid.trajectories[0]["feedback"]


def test_evaluation_cache_prevents_repeat_generation_and_review(tmp_path):
    cases, facts = fixtures()
    queue = driver.FileQueue(tmp_path, responder=ToyResponder())
    adapter = driver.OfflineAdapter(queue, cases, facts)
    first = adapter.evaluate(cases[:1], {"supplement": ""})
    second = adapter.evaluate(cases[:1], {"supplement": ""}, capture_traces=True)
    assert first.outputs == second.outputs and first.scores == second.scores
    assert queue.counts == {"generate": 1, "review": 1, "reflection": 0}
    assert adapter.generated_summaries == adapter.semantic_reviews == adapter.unique_evaluations == 1
    assert adapter.cache_hits == 1 and second.num_metric_calls == 0


def test_unique_budget_checked_before_generation(tmp_path):
    cases, facts = fixtures()
    queue = driver.FileQueue(tmp_path, responder=ToyResponder())
    adapter = driver.OfflineAdapter(queue, cases, facts, max_unique=0)
    with pytest.raises(RuntimeError, match="budget"):
        adapter.evaluate(cases[:1], {"supplement": ""})
    assert queue.requests == 0


def test_invalid_reflection_does_not_issue_a_retry(tmp_path):
    queue = driver.FileQueue(tmp_path, responder=lambda req, sha: {"text": ""})
    reflection = driver.QueueReflection(queue)
    with pytest.raises(ValueError):
        reflection("test")
    with pytest.raises(RuntimeError, match="refusing retry"):
        reflection("test")
    assert queue.requests == 1 and reflection.calls == 1
    assert driver.StopAfterReflections(reflection)(None)

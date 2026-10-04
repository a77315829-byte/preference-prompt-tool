"""원본 데이터 대조와 파일 보존을 검증한다. 모델을 호출하지 않는다."""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from engine.domain_loader import load_domain
from experiments import heldout_comparison as heldout, length_v3_compliance as gate, result_files
from experiments.persona import Persona, choose
from experiments.validate_heldout_results import validate_result_files, validate_gate

RESULTS = Path(__file__).resolve().parents[1] / "experiments/results"
QWEN = "heldout_comparison_summarization_v3_qwen2.5-7b"


@pytest.mark.parametrize("stem", ["heldout_comparison", "heldout_comparison_summarization_v2",
                                  "heldout_comparison_summarization_ratio_check",
                                  "heldout_comparison_summarization_v3", QWEN])
def test_archived_summaries_are_recomputed_from_csv(stem):
    assert validate_result_files(RESULTS / f"{stem}.csv", RESULTS / f"{stem}.json")["n"] == 30


@pytest.mark.parametrize("kind", ["duplicate", "missing_condition", "nan", "wrong_learning", "overlap", "different_target"])
def test_tampered_csv_is_rejected(tmp_path, kind):
    df = pd.read_csv(RESULTS / f"{QWEN}.csv")
    if kind == "duplicate":
        df = pd.concat([df, df.iloc[:1]])
    elif kind == "missing_condition":
        df = df.iloc[1:]
    elif kind == "nan":
        df.loc[0, "rouge_l"] = float("nan")
    elif kind == "wrong_learning":
        df.loc[df.persona == 0, "learned_exact"] = not bool(df.loc[0, "learned_exact"])
    elif kind == "overlap":
        df.loc[df.persona == 0, "eval_doc"] = df.loc[0, "learn_doc"]
    else:
        df.loc[0, "length"] = "short"
    path = tmp_path / "broken.csv"
    df.to_csv(path, index=False)
    with pytest.raises(ValueError):
        validate_result_files(path, RESULTS / f"{QWEN}.json")


@pytest.mark.parametrize("kind", ["p", "mean", "gate", "gate_type"])
def test_tampered_json_is_rejected(tmp_path, kind):
    source = RESULTS / ("length_v3_compliance_qwen2.5-7b.json" if kind.startswith("gate") else f"{QWEN}.json")
    data = json.loads(source.read_text(encoding="utf-8"))
    if kind == "p":
        data["paired"]["rouge_l: D_our_tool vs B_plus_word_count"]["sign_test_p"] = 0.01
    elif kind == "mean":
        data["means"]["rouge_l"]["D_our_tool"] = 0.9
    else:
        data["gate"]["passed"] = 1 if kind == "gate_type" else False
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        if kind.startswith("gate"):
            validate_gate(path)
        else:
            validate_result_files(RESULTS / f"{QWEN}.csv", path)


def test_default_runs_are_distinct_and_explicit_collisions_preserve_results(tmp_path, monkeypatch):
    monkeypatch.setattr(result_files, "RUNS", tmp_path / "runs")
    first, manifest = result_files.prepare_run("heldout", (".csv", ".json"))
    second, _ = result_files.prepare_run("heldout", (".csv", ".json"))
    assert first[".csv"].parent != second[".csv"].parent
    first[".csv"].write_text("archived", encoding="utf-8")
    manifest_before = manifest.read_bytes()
    with pytest.raises(FileExistsError):
        result_files.prepare_run("heldout", (".csv", ".json"), output_dir=first[".csv"].parent)
    assert first[".csv"].read_text(encoding="utf-8") == "archived"
    assert manifest.read_bytes() == manifest_before
    with pytest.raises(ValueError):
        result_files.prepare_run("heldout", (".csv",), overwrite=True)


def test_failed_atomic_write_preserves_previous_file(tmp_path):
    target = tmp_path / "result.json"
    target.write_text("archived", encoding="utf-8")
    with pytest.raises(ValueError):
        result_files.write_json(target, {"score": float("nan")})
    assert target.read_text(encoding="utf-8") == "archived"
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("module,stem", [(heldout, "heldout_comparison"), (gate, "length_v3_compliance")])
def test_cli_collision_stops_before_any_model_calls(module, stem, tmp_path, monkeypatch):
    archived = tmp_path / f"{stem}.json"
    archived.write_text("archived", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["experiment", "--output-dir", str(tmp_path)])
    def forbidden(*args, **kwargs):
        pytest.fail("출력 충돌 뒤에는 모델/데이터를 호출할 수 없다")
    monkeypatch.setattr(module, "pick_personas", forbidden)
    with pytest.raises(SystemExit) as exc:
        module.main()
    assert exc.value.code == 2
    assert archived.read_text(encoding="utf-8") == "archived"


def test_tie_policy_preserves_history_and_allows_explicit_new_experiment():
    domain = load_domain("domains/summarization_v3.yaml")
    persona = Persona(combo={"length": "short", "extractiveness": "normal"}, reference_summary="")
    assert choose(domain, persona, "same output", "same output", "source") == "a"
    assert choose(domain, persona, "same output", "same output", "source", tie_policy="record-tie") == "tie"


def test_short_run_records_axes_and_ties_without_changing_archives(tmp_path, monkeypatch):
    import litellm
    before = {p: p.read_bytes() for p in RESULTS.glob("heldout_comparison*")}
    monkeypatch.setattr(result_files, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(sys, "argv", ["experiment", "--n", "2", "--fair-bplus"])
    personas = [{"combo": {"length": "short", "extractiveness": "normal"},
                 "learn_doc": n * 2, "eval_doc": n * 2 + 1, "eval_source": "source " * 100,
                 "eval_reference": "reference"} for n in range(2)]
    monkeypatch.setattr(heldout, "pick_personas", lambda n: personas[:n])
    def learn(domain, persona, model, *, tie_policy, diagnostics):
        diagnostics["comparisons"] = [{"score_a": 1, "score_b": 1}] * 8
        return "prompt", persona["combo"]
    monkeypatch.setattr(heldout, "learn_prompt", learn)
    monkeypatch.setattr(heldout, "generate_raw", lambda *a: "output")
    callbacks = litellm.success_callback
    assert heldout.main() == 0
    assert litellm.success_callback is callbacks
    summary = next((tmp_path / "runs").glob("*/*.json"))
    summary = summary.parent / "heldout_comparison.json"
    result = validate_result_files(summary.with_suffix(".csv"), summary)
    assert result["n"] == 2 and result["axis_diagnostics_available"]
    data = json.loads(summary.read_text(encoding="utf-8"))
    assert data["oracle_ties"] == data["oracle_comparisons"] == 16
    assert data["primary_comparison"]["equivalence_tested"] is False
    assert all(p.read_bytes() == contents for p, contents in before.items())


def test_gate_records_raw_samples_and_restores_callbacks_on_failure(tmp_path, monkeypatch):
    import litellm
    monkeypatch.setattr(result_files, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(sys, "argv", ["gate"])
    monkeypatch.setattr(gate, "pick_personas", lambda n: [{"learn_doc": k, "learn_source": "word " * 100}
                                                        for k in range(12)])
    counts = {"short": 5, "normal": 10, "long": 15}
    monkeypatch.setattr(gate, "generate", lambda domain, source, combo, model: "word " * counts[combo["length"]])
    callbacks = litellm.success_callback
    assert gate.main() == 0
    path = next((tmp_path / "runs").glob("*/length_v3_compliance.json"))
    assert validate_gate(path) == {"passed": True, "raw_samples_available": True}
    def failure(*args):
        raise RuntimeError("mock failure")
    monkeypatch.setattr(gate, "generate", failure)
    with pytest.raises(RuntimeError, match="mock failure"):
        gate.main()
    assert litellm.success_callback is callbacks
    states = [json.loads(p.read_text(encoding="utf-8"))["status"]
              for p in (tmp_path / "runs").glob("*/*.run.json")]
    assert sorted(states) == ["completed", "failed"]

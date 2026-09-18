"""Blind pilot integrity and UI regressions. Every generator is a test double."""
import copy
import json

import pytest

from experiments import korean_pilot as pilot


@pytest.fixture
def protocol():
    return {
        "schema_version": 1, "participant_id": "P001", "is_test": True,
        "model": "test-model", "temperature": 0,
        "prompts": {"direct": "한국어로 간결하게 요약하세요.", "selected": "한국어로 두 문장으로 요약하세요."},
        "selection_rounds": 8, "collection_order": "direct_first",
        "effort_seconds": {"direct": 42.0, "selected": None},
        "calibration_sources": ["선호 수집에 사용한 원문입니다."],
        "documents": [{"id": f"doc-{i}", "source": f"새 평가 원문 {i}입니다.", "must_keep": [f"사실 {i}"]} for i in range(3)],
    }


def ready(protocol, tmp_path):
    packet_path = pilot.prepare(protocol, tmp_path, generate=lambda *a, **k: "한국어 요약 결과입니다.")
    return pilot.read_json(packet_path.parent / "private.json"), pilot.read_json(packet_path)


def answers(packet, preference="A"):
    return [{"case_id": case["case_id"], "preference": preference, "reason": "",
             "quality": {side: {"factuality": "not_assessed", "missing_points": None} for side in ("A", "B")}}
            for case in packet["cases"]]


def test_plan_does_not_create_files_or_generate(protocol):
    assert pilot.plan(protocol)["max_generation_requests"] == 6


@pytest.mark.parametrize("kind", ["calibration", "duplicate_source", "duplicate_id"])
def test_rejects_leakage_and_duplicate_documents(protocol, kind):
    if kind == "calibration":
        protocol["documents"][0]["source"] = "  선호   수집에 사용한 원문입니다.  "
    elif kind == "duplicate_source":
        protocol["documents"][1]["source"] = protocol["documents"][0]["source"]
    else:
        protocol["documents"][1]["id"] = protocol["documents"][0]["id"]
    with pytest.raises(ValueError):
        pilot.validate_protocol(protocol)


@pytest.mark.parametrize("value", [-1, float("inf"), True])
def test_effort_must_be_real_measurement_or_null(protocol, value):
    protocol["effort_seconds"]["direct"] = value
    with pytest.raises(ValueError):
        pilot.validate_protocol(protocol)


def test_blind_packet_does_not_expose_prompts_mapping_or_participant(protocol, tmp_path):
    private, packet = ready(protocol, tmp_path)
    pilot.validate_packet(packet)
    serialized = json.dumps(packet, ensure_ascii=False)
    assert "mapping" not in serialized and "protocol" not in serialized and "P001" not in serialized
    for prompt in protocol["prompts"].values():
        assert prompt not in serialized
    placements = [c["mapping"]["A"] for c in private["cases"]]
    assert abs(placements.count("direct") - placements.count("selected")) <= 1


def test_failure_resumes_without_repeating_finished_requests(protocol, tmp_path):
    calls = []
    def failing(prompt, source, **kwargs):
        calls.append((prompt, source, kwargs))
        if len(calls) == 2:
            raise RuntimeError("sensitive simulated SDK detail")
        return "완료한 결과"
    with pytest.raises(RuntimeError, match="재개") as exc:
        pilot.prepare(protocol, tmp_path, generate=failing)
    assert "sensitive" not in str(exc.value)
    saved = pilot.read_json(tmp_path / "P001" / "private.json")
    resumed = []
    def succeeding(prompt, source, **kwargs):
        resumed.append((prompt, source, kwargs))
        return "재개 결과"
    path = pilot.prepare(protocol, tmp_path, generate=succeeding)
    assert len(resumed) == 5
    assert all(c[2]["model"] == "test-model" and c[2]["temperature"] == 0 for c in calls + resumed)
    after = pilot.read_json(path.parent / "private.json")
    assert after["study_id"] == saved["study_id"]
    assert [c["mapping"] for c in after["cases"]] == [c["mapping"] for c in saved["cases"]]
    def forbidden(*args, **kwargs):
        pytest.fail("complete study generated again")
    pilot.prepare(protocol, tmp_path, generate=forbidden)


def test_frozen_protocol_cannot_be_changed(protocol, tmp_path):
    ready(protocol, tmp_path)
    protocol["prompts"]["direct"] += " 수정"
    with pytest.raises(ValueError, match="동결"):
        pilot.prepare(protocol, tmp_path, generate=lambda *a, **k: pytest.fail("must not call"))


def test_private_or_modified_packet_rejected(protocol, tmp_path):
    private, packet = ready(protocol, tmp_path)
    with pytest.raises(ValueError):
        pilot.validate_packet(private)
    packet["cases"][0]["source"] = "수정된 원문"
    with pytest.raises(ValueError, match="변경"):
        pilot.validate_packet(packet)


@pytest.mark.parametrize("mode", ["missing", "duplicate", "unknown", "no_preference", "bad_omission"])
def test_invalid_responses_not_silently_counted(protocol, tmp_path, mode):
    _, packet = ready(protocol, tmp_path)
    data = answers(packet)
    if mode == "missing":
        data.pop()
    elif mode == "duplicate":
        data.append(data[0])
    elif mode == "unknown":
        data[0]["case_id"] = "wrong"
    elif mode == "no_preference":
        data[0]["preference"] = None
    else:
        data[0]["quality"]["A"]["missing_points"] = 99
    with pytest.raises(ValueError):
        pilot.response_record(packet, data)


def test_condition_mapping_and_unassessed_quality_preserved(protocol, tmp_path):
    private, packet = ready(protocol, tmp_path)
    data = answers(packet)
    data[0]["preference"] = next(s for s,c in private["cases"][0]["mapping"].items() if c == "selected")
    data[1]["preference"] = "tie"
    data[2]["preference"] = "neither"
    result = pilot.analyze(private, packet, pilot.response_record(packet, data))
    assert result["preference_counts"] == {"direct": 0, "selected": 1, "tie": 1, "neither": 1}
    assert result["quality"]["selected"]["factuality"]["not_assessed"] == 3
    assert result["quality"]["direct"]["missing_points"] == []
    assert result["effort_seconds"]["selected"] is None


def test_wrong_study_or_forged_test_flag_rejected(protocol, tmp_path):
    private, packet = ready(protocol, tmp_path)
    record = pilot.response_record(packet, answers(packet))
    for key, value in (("study_id", "wrong"), ("is_test", False), ("packet_hash", "wrong")):
        changed = {**record, key: value}
        with pytest.raises(ValueError, match="일치"):
            pilot.analyze(private, packet, changed)


def test_synthetic_results_excluded_and_no_empty_success_rate(protocol, tmp_path):
    private, packet = ready(protocol, tmp_path)
    result = pilot.analyze(private, packet, pilot.response_record(packet, answers(packet)))
    summary = pilot.summarize([result])
    assert summary["participants"] == 0
    assert summary["excluded_test_records"] == 1
    assert summary["mean_selected_share"] is None


def test_group_statistics_count_participants_not_documents(protocol, tmp_path):
    protocol["is_test"] = False
    private, packet = ready(protocol, tmp_path)
    r1 = pilot.analyze(private, packet, pilot.response_record(packet, answers(packet)))
    r1["documents"] = 1
    r1["preference_counts"] = {"direct": 0, "selected": 1, "tie": 0, "neither": 0}
    r2 = copy.deepcopy(r1)
    r2.update(participant_id="P002", documents=3)
    r2["preference_counts"] = {"direct": 3, "selected": 0, "tie": 0, "neither": 0}
    summary = pilot.summarize([r1, r2])
    assert summary["participants"] == 2
    assert summary["mean_selected_share"] == 0.5
    with pytest.raises(ValueError, match="두 번"):
        pilot.summarize([r1, r1])
    r2["model"] = "other-model"
    with pytest.raises(ValueError, match="모델"):
        pilot.summarize([r1, r2])


def test_review_ui_requires_answers_and_exports_only_submitted_ratings(protocol, tmp_path):
    from streamlit.testing.v1 import AppTest
    _, packet = ready(protocol, tmp_path)
    script = "import json\nfrom pilot_review import render_packet\nrender_packet(json.loads(" + repr(json.dumps(packet)) + "))"
    app = AppTest.from_string(script, default_timeout=30).run()
    assert not app.exception
    assert len(app.radio) == 3
    assert all(r.value is None for r in app.radio)
    app.checkbox[0].check()
    app.button[0].click().run()
    assert app.error
    assert "pilot_response" not in app.session_state
    for radio in app.radio:
        radio.set_value("tie")
    app.button[0].click().run()
    assert not app.exception
    assert app.success
    record = app.session_state["pilot_response"]
    assert all(a["preference"] == "tie" for a in record["answers"])
    assert all(a["quality"]["A"]["factuality"] == "not_assessed" for a in record["answers"])
    assert record["is_test"] is True

def test_demo_never_uses_model_api_and_stays_test_only(tmp_path, monkeypatch):
    from engine import generator
    def forbidden(*args, **kwargs):
        pytest.fail("demo must never call the model")
    monkeypatch.setattr(generator, "generate_with_prompt", forbidden)
    path = pilot.prepare_demo(tmp_path)
    packet = pilot.read_json(path)
    private = pilot.read_json(path.parent / "private.json")
    assert packet["is_test"] is True
    assert private["protocol"]["model"] == "no-api-demo"
    assert len(packet["cases"]) == 3
    pilot.validate_packet(packet)
    result = pilot.analyze(private, packet, pilot.response_record(packet, answers(packet, "tie")))
    assert pilot.summarize([result])["participants"] == 0

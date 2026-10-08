"""개선 방향 추천 (prompt_workspace/suggest.py). 실제 API 는 부르지 않는다.

고정하는 것: 찾을 문장이 지금 지침에 없으면 적용 불가로 표시한다(모델 말을 믿지
않는다), 필수 규칙을 바꾸는 제안은 코드가 찾아 따로 확인을 받는다, 적용은 프로젝트를
바꾸지 않고 후보만 낸다, 실패한 검사를 모델에게 알려 준다."""

from __future__ import annotations

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import pytest

import api_server
from budget import DailyBudget
from prompt_workspace import builder, llm, suggest
from prompt_workspace.examples import synthetic_cost
from prompt_workspace.models import ProjectError, new_project


def _built() -> dict:
    project = new_project("샘플", synthetic_cost.SAMPLE_DESCRIPTION)
    project["requirements"] = synthetic_cost.sample_requirements()
    project["requirements"]["open_questions"] = []
    project["check_set"] = synthetic_cost.NAME
    return builder.build(builder.confirm(project))


PREF = "조회 기간과 총액을 먼저 말하고 세부는 뒤에 둔다."
RULE = "입력에 없는 금액, 리소스 ID, 절감액을 만들지 않는다."


def _reply(*suggestions) -> str:
    return json.dumps({"suggestions": list(suggestions)}, ensure_ascii=False)


@pytest.fixture
def fake(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path / "cache")
    calls = []

    def install(text):
        def completion(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))], usage=None)
        monkeypatch.setattr(llm, "completion", completion)
        return calls

    return install


def test_applicable_edit_is_checked_against_the_real_prompt(fake) -> None:
    fake(_reply(
        {"category": "clarify", "title": "순서를 분명히", "reason": "첫 문장을 정한다",
         "edits": [{"find": PREF, "replace": "summary 의 첫 문장에 조회 기간과 총액을 쓴다."}]},
        {"category": "examples", "title": "예시", "reason": "모델이 옮기다 바꾼 문장",
         "edits": [{"find": "조회 기간과 총액을 먼저 말한다.", "replace": "x"}]},
    ))
    result = suggest.suggest(_built(), model="m")
    first, second = result["suggestions"]
    assert first["applicable"] and first["touches_rules"] == [] and first["category_label"] == "명확화"
    assert not second["applicable"] and "찾지 못함" in second["problem"]


def test_rule_changes_are_detected_by_code_not_by_the_model(fake) -> None:
    fake(_reply({"category": "dedupe", "title": "합치기", "reason": "",
                 "edits": [{"find": f"- {RULE}\n", "replace": ""}]}))
    item = suggest.suggest(_built(), model="m")["suggestions"][0]
    assert item["applicable"] and item["touches_rules"] == ["R1"]


def test_unknown_category_and_empty_opinion(fake) -> None:
    fake(_reply({"category": "magic", "title": "?", "edits": []},
                {"category": "grounding", "title": "의견만", "reason": "근거를 더 묶자", "edits": []}))
    result = suggest.suggest(_built(), model="m")
    assert len(result["suggestions"]) == 1 and not result["suggestions"][0]["applicable"]
    assert "범주" in result["notes"][0]


def test_failed_checks_are_sent_to_the_model(fake) -> None:
    calls = fake(_reply())
    project = _built()
    project["runs"] = [{"status": "ran", "artifact_revision": 1, "output": "{...}",
                        "checks": [{"name": "총액 보존", "status": "fail", "detail": "입력 37.50, 출력 37.5", "group": "meaning"}]}]
    suggest.suggest(project, model="m")
    user = calls[0]["messages"][1]["content"]
    assert "총액 보존: 입력 37.50" in user and RULE in user


def test_suggest_needs_a_current_prompt(fake) -> None:
    project = _built()
    project["requirements_revision"] += 1
    with pytest.raises(ProjectError):
        suggest.suggest(project, model="m")


def test_apply_returns_a_candidate_without_touching_the_project() -> None:
    project = _built()
    picked = [{"edits": [{"find": PREF, "replace": "총액을 첫 문장에 쓴다."}]},
              {"edits": [{"find": "", "replace": "- 숫자는 입력의 표기를 그대로 쓴다."}]}]
    result = suggest.apply(project, picked)
    assert "총액을 첫 문장에 쓴다." in result["system_prompt"]
    assert result["system_prompt"].endswith("- 숫자는 입력의 표기를 그대로 쓴다.")
    assert PREF in project["artifact"]["system_prompt"]  # 원본은 그대로


def test_apply_refuses_rule_changes_unless_confirmed() -> None:
    project = _built()
    picked = [{"edits": [{"find": RULE, "replace": "금액을 지어내지 않는다."}]}]
    with pytest.raises(ProjectError, match="R1"):
        suggest.apply(project, picked)
    assert suggest.apply(project, picked, allow_rule_changes=True)["touches_rules"] == ["R1"]


def test_apply_reports_conflicting_suggestions() -> None:
    project = _built()
    picked = [{"edits": [{"find": PREF, "replace": "A"}]}, {"edits": [{"find": PREF, "replace": "B"}]}]
    with pytest.raises(ProjectError, match="함께 적용"):
        suggest.apply(project, picked)


def test_suggest_over_http_follows_live_switch_and_budget(monkeypatch, fake, tmp_path) -> None:
    calls = fake(_reply())
    srv = ThreadingHTTPServer(("127.0.0.1", 0), api_server.ApiHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/api"

    def post(path, body):
        req = urllib.request.Request(base + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    try:
        project = _built()
        monkeypatch.setattr(api_server, "LIVE", False)
        status, body = post("/workspace/suggest", {"project": project})
        assert status == 200 and calls == [] and "실제 생성 모드" in body["notes"][0]  # 코드 점검만
        monkeypatch.setattr(api_server, "LIVE", True)
        monkeypatch.setattr(api_server, "DAILY_WORKSPACE_CALLS", DailyBudget(1))
        assert post("/workspace/suggest", {"project": project})[0] == 200
        status, body = post("/workspace/suggest", {"project": project})
        assert status == 400 and "모두 썼" in body["error"]
        status, body = post("/workspace/apply-suggestions",
                            {"project": project, "suggestions": [{"edits": [{"find": PREF, "replace": "A"}]}]})
        assert status == 200 and "A" in body["system_prompt"]
    finally:
        srv.shutdown()


def test_builder_safety_lines_are_protected_like_rules(fake) -> None:
    """실제 gpt-4o-mini 가 '입력에 없는 값은 지어내지 않는다'를 중복이라며 지우자고 했다.
    필수 규칙이 아니라 빌더의 안전 문장이어도 코드가 잡아 따로 확인받는다."""
    fake(_reply({"category": "dedupe", "title": "중복", "reason": "",
                 "edits": [{"find": "입력에 없는 값은 지어내지 않는다.", "replace": ""}]}))
    item = suggest.suggest(_built(), model="m")["suggestions"][0]
    assert item["touches_rules"] == ["안전 문장 2"]
    with pytest.raises(ProjectError, match="안전 문장 2"):
        suggest.apply(_built(), [item])


def test_model_is_told_to_fix_failures_first_and_what_to_keep(fake) -> None:
    calls = fake(_reply())
    suggest.suggest(_built(), model="m")
    system, user = calls[0]["messages"]
    assert "첫 제안은 반드시 그 실패를 직접 고치는 것" in system["content"]
    assert "안전 문장 1:" in user["content"] and "R1:" in user["content"]



def test_code_suggestions_restore_a_missing_output_format_without_ai(fake) -> None:
    """실제 모델은 출력 형식이 빠진 지침의 JSON 파싱 실패를 고치지 못했다(v1: 다루지 않음,
    v2: 시험 출력의 문장을 고치려 함). 출력 계약이 있으니 코드가 그 절을 되살린다."""
    calls = fake(_reply())
    project = _built()
    prompt = project["artifact"]["system_prompt"]
    start, end = prompt.index("# 출력 형식"), prompt.index("# 입력 처리")
    project["artifact"]["system_prompt"] = prompt[:start] + prompt[end:]
    project["runs"] = [{"status": "ran", "artifact_revision": 1, "checks": [
        {"name": "JSON 파싱", "status": "fail", "detail": "", "group": "contract"}]}]
    result = suggest.suggest(project, model="m", use_ai=False)
    assert calls == []
    item = result["suggestions"][0]
    assert item["source"] == "code" and item["applicable"] and "JSON 파싱" in item["reason"]
    restored = suggest.apply(project, [item])["system_prompt"]
    assert "# 출력 형식" in restored and "- currency (문자열, 필수)" in restored


def test_code_suggestions_restore_missing_rules(fake) -> None:
    fake(_reply())
    project = _built()
    project["artifact"]["system_prompt"] = project["artifact"]["system_prompt"].replace(f"- {RULE}\n", "")
    item = suggest.suggest(project, model="m", use_ai=False)["suggestions"][0]
    assert "R1" in item["reason"]
    assert RULE in suggest.apply(project, [item])["system_prompt"]


def test_healthy_prompt_gets_no_code_suggestions(fake) -> None:
    fake(_reply())
    assert suggest.suggest(_built(), model="m", use_ai=False)["suggestions"] == []


def test_ai_suggestions_follow_code_ones_and_ids_are_sequential(fake) -> None:
    fake(_reply({"category": "clarify", "title": "t", "reason": "r", "edits": [{"find": PREF, "replace": "A"}]}))
    project = _built()
    project["artifact"]["system_prompt"] = project["artifact"]["system_prompt"].replace(f"- {RULE}\n", "")
    result = suggest.suggest(project, model="m")
    assert [(s["id"], s["source"]) for s in result["suggestions"]] == [("S1", "code"), ("S2", "ai")]


# --- 강한 모델 호출 설정과 제안별 시험 ----------------------------------------------


def test_ai_suggestions_are_called_like_a_reasoning_model(fake) -> None:
    """추론형 모델은 temperature=0 을 거부하고 생각에도 출력 토큰을 쓴다."""
    calls = fake(_reply())
    suggest.suggest(_built(), model="openai/gpt-5.6-luna")
    assert "temperature" not in calls[0]
    assert calls[0]["max_tokens"] == suggest.AI_MAX_TOKENS and calls[0]["model"] == "openai/gpt-5.6-luna"


def _checks(**statuses):
    return [{"name": n, "status": st, "detail": "", "group": "contract"} for n, st in statuses.items()]


def test_trial_counts_fixed_and_broken_checks_per_suggestion() -> None:
    project = _built()
    good = {"id": "S1", "applicable": True, "touches_rules": [],
            "edits": [{"find": "", "replace": "- FIXES_PARSE"}]}
    bad = {"id": "S2", "applicable": True, "touches_rules": [],
           "edits": [{"find": "", "replace": "- BREAKS_TOTAL"}]}
    advice = {"id": "S3", "applicable": False, "touches_rules": [], "edits": []}
    # 보호 문장을 지우는 제안 - 브라우저가 touches_rules 를 비워 보내도 코드가 다시 잰다.
    guarded = {"id": "S4", "applicable": True, "touches_rules": [], "edits": [{"find": RULE, "replace": ""}]}
    seen = []

    def run(p):
        prompt = p["artifact"]["system_prompt"]
        seen.append(prompt)
        if "FIXES_PARSE" in prompt:
            checks = _checks(**{"JSON 파싱": "pass", "총액 보존": "pass", "규칙 R1": "not_evaluated"})
        elif "BREAKS_TOTAL" in prompt:
            checks = _checks(**{"JSON 파싱": "fail", "총액 보존": "fail", "규칙 R1": "not_evaluated"})
        else:
            checks = _checks(**{"JSON 파싱": "fail", "총액 보존": "pass", "규칙 R1": "not_evaluated"})
        return {"status": "ran", "checks": checks, "output": "x"}

    result = suggest.trial(project, [good, bad, advice, guarded], run)
    by_id = {r["id"]: r for r in result["results"]}
    assert by_id["S1"]["fixed"] == ["JSON 파싱"] and by_id["S1"]["broke"] == []
    assert by_id["S2"]["fixed"] == [] and by_id["S2"]["broke"] == ["총액 보존"]
    assert by_id["S1"]["fail_before"] == 1 and by_id["S1"]["fail_after"] == 0
    assert by_id["S3"]["tested"] is False and by_id["S4"]["tested"] is False
    assert len(seen) == 3  # 지금 지침 1 + 시험 가능한 제안 2. 보호 문장 제안은 부르지 않는다.
    assert all("FIXES_PARSE" not in prompt for prompt in seen[:1])


def test_trial_needs_a_real_baseline_run() -> None:
    with pytest.raises(ProjectError, match="시험 입력"):
        suggest.trial(_built(), [{"id": "S1", "applicable": True, "touches_rules": [], "edits": []}],
                      lambda p: {"status": "input_error", "checks": []})


def test_trial_route_checks_live_mode_and_remaining_calls(monkeypatch, fake) -> None:
    fake(json.dumps({"currency": "USD", "total": "37.50", "summary": "37.50 USD",
                     "items": [{"service": "Compute", "amount": "25.00"}, {"service": "Storage", "amount": "12.50"}]}))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), api_server.ApiHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/api"

    def post(path, body):
        req = urllib.request.Request(base + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    picked = [{"id": "S1", "applicable": True, "touches_rules": [], "edits": [{"find": "", "replace": "- 짧게"}]},
              {"id": "S2", "applicable": True, "touches_rules": [], "edits": [{"find": "", "replace": "- 길게"}]}]
    body = {"project": _built(), "input": synthetic_cost.SAMPLE_INPUT, "suggestions": picked}
    try:
        monkeypatch.setattr(api_server, "LIVE", False)
        assert post("/workspace/trial-suggestions", body)[0] == 400
        monkeypatch.setattr(api_server, "LIVE", True)
        monkeypatch.setattr(api_server, "DAILY_WORKSPACE_CALLS", DailyBudget(2))
        status, data = post("/workspace/trial-suggestions", body)
        assert status == 400 and "3회가 필요" in data["error"]
        assert api_server.DAILY_WORKSPACE_CALLS.left() == 2  # 거절하면 아무것도 쓰지 않았다
        monkeypatch.setattr(api_server, "DAILY_WORKSPACE_CALLS", DailyBudget(3))
        status, data = post("/workspace/trial-suggestions", body)
        assert status == 200 and [r["id"] for r in data["results"]] == ["S1", "S2"]
        assert api_server.DAILY_WORKSPACE_CALLS.left() == 0
    finally:
        srv.shutdown()


def test_trial_recomputes_flags_instead_of_trusting_the_browser() -> None:
    """applicable·touches_rules 는 화면이 들고 다니는 값이라 바뀌어 올 수 있다.
    시험 여부는 서버가 지금 지침에 대고 다시 정한다."""
    project = _built()
    sneaky = {"id": "S1", "applicable": True, "touches_rules": [], "edits": [{"find": RULE, "replace": "- 무엇이든"}]}
    shy = {"id": "S2", "applicable": False, "touches_rules": ["R1"], "edits": [{"find": "", "replace": "- 짧게"}]}
    seen = []
    result = suggest.trial(project, [sneaky, shy],
                           lambda p: seen.append(p) or {"status": "ran", "checks": [], "output": ""})
    by_id = {r["id"]: r for r in result["results"]}
    assert by_id["S1"]["tested"] is False and "보호 문장" in by_id["S1"]["reason"]
    assert by_id["S2"]["tested"] is True
    assert len(seen) == 2
    assert suggest.testable_count(project, [sneaky, shy]) == 1


@pytest.mark.parametrize("picked", [["not a dict"], [{"edits": "x"}], [{"edits": ["x"]}],
                                    [{"edits": [{"find": 1, "replace": "a"}]}]])
def test_malformed_suggestions_are_a_400_not_a_500(picked) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), api_server.ApiHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/api"
    try:
        for path in ("/workspace/apply-suggestions", "/workspace/trial-suggestions"):
            req = urllib.request.Request(base + path, json.dumps({"project": _built(), "suggestions": picked}).encode(),
                                         {"Content-Type": "application/json"})
            try:
                urllib.request.urlopen(req)
                status = 200
            except urllib.error.HTTPError as err:
                status = err.code
            assert status == 400, (path, picked)
    finally:
        srv.shutdown()

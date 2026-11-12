import copy

import pytest

import api_server
import service
import team
from budget import DailyBudget
from engine.domain_loader import load_domain
from engine.generator import build_final_prompt
from preference_comparison import compare_preferences, compose_task_prompt, recognize_standard_prompt
from tests.test_personal_prompts import request, signup
from tests.test_preference_comparison import COMBO, prepare
from tests.test_team import _history, server


@pytest.mark.parametrize("domain_key,personal,other", [
    ("coding", COMBO, {**COMBO, "code_structure": "separated", "type_detail": "inferred"}),
    ("summarization_ko", None, None),
    ("summarization", None, None),
])
def test_composition_uses_exact_selected_values_and_keeps_originals(domain_key, personal, other):
    domain = load_domain(f"domains/{domain_key}.yaml")
    personal = personal or {a.name: a.values[0].value if a.type == "enum" else "" for a in domain.axes}
    other = other or {a.name: a.values[-1].value if a.type == "enum" else "" for a in domain.axes}
    item = {"id": "mine", "revision": 1, "prompt": build_final_prompt(domain, personal)}
    members = [team.Member("팀원", _history(domain_key, other))]
    before = copy.deepcopy(item)
    comparison = compare_preferences(item, domain, "devteam", "팀", members, "ko")
    differing = [a for a in comparison["axes"] if a["personal_value"] != a["team_value"]]
    choices = {a["axis"]: "personal" if i % 2 else "team" for i, a in enumerate(differing)}
    draft = compose_task_prompt(item, domain, comparison, choices)
    combo = {a["axis"]: a[f"{choices.get(a['axis'], 'personal')}_value"] for a in comparison["axes"]}
    expected = build_final_prompt(domain, combo)
    note = domain.final_prompt.preference_note
    if note:
        expected = expected.replace(note, "이번 작업에서 선택한 방식입니다.")
    assert draft["prompt"] == expected
    assert draft["choices"] == choices
    assert item == before
    assert comparison == compare_preferences(item, domain, "devteam", "팀", members, "ko")
    for invalid in (None, [], {}, {**choices, "fake_axis": "team"}, {k: "unknown" for k in choices}):
        with pytest.raises(ValueError):
            compose_task_prompt(item, domain, comparison, invalid)


def test_undecided_choice_omits_axis_and_custom_text_is_not_guessed():
    domain = load_domain("domains/coding.yaml")
    item = {"id": "p", "revision": 1, "prompt": build_final_prompt(domain, {**COMBO, "code_structure": ""}, language="en")}
    members = [team.Member("팀원", _history("coding", COMBO))]
    comparison = compare_preferences(item, domain, "devteam", "팀", members)
    draft = compose_task_prompt(item, domain, comparison, {"code_structure": "personal"})
    assert "Code structure:" not in draft["prompt"]
    assert draft["snapshot"] != compose_task_prompt(item, domain, comparison, {"code_structure": "team"})["snapshot"]
    edited = {**item, "prompt": item["prompt"] + "\n추가 요청"}
    comparison = compare_preferences(edited, domain, "devteam", "팀", members)
    with pytest.raises(ValueError, match="수정한 지침"):
        compose_task_prompt(edited, domain, comparison, {})


def test_compose_and_run_validate_choices_and_snapshots_without_writes(server, monkeypatch):
    cookie, item, path = prepare(server)
    # 기존 팀원의 표와 충돌하지 않도록 같은 이름으로 갱신한다.
    api_server.TEAMS.add("devteam", "coding", "민수", _history("coding", {**COMBO, "code_structure": "separated"}))
    before_team = copy.deepcopy(api_server.TEAMS.get("devteam"))
    _, data, _ = request(server, path + "/compare-team", {"revision": 1, "teamCode": "devteam"}, cookie)
    comparison = data["comparison"]
    body = {"revision": 1, "teamCode": "devteam", "teamSnapshot": comparison["team_snapshot"],
            "language": comparison["team_language"], "choices": {"code_structure": "team"}}
    status, data, _ = request(server, path + "/compose-task", body, cookie)
    assert status == 200
    draft = data["draft"]
    assert request(server, path + "/compose-task", body)[0] == 401
    assert request(server, path + "/compose-task", body, signup(server, "bob"))[0] == 404
    for changes, status in (({"choices": {}}, 400), ({"teamSnapshot": "old"}, 409), ({"revision": 2}, 409)):
        assert request(server, path + "/compose-task", {**body, **changes}, cookie)[0] == status
    seen = []
    monkeypatch.setattr(api_server, "LIVE", True)
    monkeypatch.setattr(api_server, "_live_key_available", lambda _: True)
    monkeypatch.setattr(api_server, "DAILY_PREFERENCE_RUNS", DailyBudget(3))
    monkeypatch.setattr(service.generator, "generate_with_prompt", lambda prompt, source, model: seen.append(prompt) or "결과")
    run = {**body, "basis": "custom", "teamLanguage": comparison["team_language"], "taskSnapshot": draft["snapshot"], "task": "새 작업", "prompt": "무시할 클라이언트 지침"}
    status, result, _ = request(server, path + "/run", run, cookie)
    assert status == 200 and result["task_snapshot"] == draft["snapshot"]
    assert seen == [draft["prompt"]]
    monkeypatch.setattr(api_server, "_take", lambda *_: pytest.fail("검증 실패는 사용량을 차감하지 않는다"))
    for changes, status in (({"choices": {}}, 400), ({"taskSnapshot": "stale"}, 409), ({"choices": {"code_structure": "personal"}}, 409)):
        assert request(server, path + "/run", {**run, **changes}, cookie)[0] == status
    assert api_server.PERSONAL_PROMPTS.get(1, item["id"]) == item
    assert api_server.TEAMS.get("devteam") == before_team
    api_server.TEAMS.add("devteam", "coding", "지은", _history("coding", COMBO))
    assert request(server, path + "/run", run, cookie)[0] == 409
    assert seen == [draft["prompt"]]


def test_save_task_creates_independent_named_item_for_reuse(server, monkeypatch):
    cookie, original, path = prepare(server)
    api_server.TEAMS.add("devteam", "coding", "민수", _history("coding", {**COMBO, "code_structure": "separated"}))
    before_team = copy.deepcopy(api_server.TEAMS.get("devteam"))
    _, data, _ = request(server, path + "/compare-team", {"revision": 1, "teamCode": "devteam"}, cookie)
    comparison = data["comparison"]
    body = {"revision": 1, "teamCode": "devteam", "teamSnapshot": comparison["team_snapshot"],
            "language": comparison["team_language"], "choices": {"code_structure": "team"}}
    _, data, _ = request(server, path + "/compose-task", body, cookie)
    draft = data["draft"]
    save = {**body, "taskSnapshot": draft["snapshot"], "title": "팀 구성 + 내 타입", "note": "React 작업에 재사용",
            "prompt": "클라이언트 본문은 무시", "domainKey": "summarization_ko", "task": "저장하면 안 되는 새 작업", "output": "저장하면 안 되는 결과"}
    status, data, _ = request(server, path + "/save-task", save, cookie)
    assert status == 201
    saved = data["preference"]
    assert saved["id"] != original["id"] and saved["revision"] == 1
    assert saved["title"] == save["title"] and saved["note"] == save["note"]
    assert saved["domain_key"] == "coding" and saved["prompt"] == draft["prompt"]
    assert "task" not in saved and "output" not in saved
    assert api_server.PERSONAL_PROMPTS.get(1, original["id"]) == original
    assert api_server.TEAMS.get("devteam") == before_team
    assert len(api_server.PERSONAL_PROMPTS.list_for(1)) == 2
    assert request(server, path + "/save-task", save)[0] == 401
    bob = signup(server, "bob")
    assert request(server, path + "/save-task", save, bob)[0] == 404
    for changes, status in (({"title": " "}, 400), ({"title": "x" * 101}, 400), ({"note": "x" * 1001}, 400),
                            ({"choices": {}}, 400), ({"taskSnapshot": "old"}, 409), ({"revision": 2}, 409), ({"teamSnapshot": "old"}, 409)):
        assert request(server, path + "/save-task", {**save, **changes}, cookie)[0] == status
    assert len(api_server.PERSONAL_PROMPTS.list_for(1)) == 2
    # 저장한 지침은 이후 팀 기준이 바뀌어도 독립적으로 열고 사용할 수 있다.
    api_server.TEAMS.add("devteam", "coding", "지은", _history("coding", COMBO))
    assert request(server, path + "/save-task", save, cookie)[0] == 409
    status, data, _ = request(server, f"/preferences/{saved['id']}", cookie=cookie)
    assert status == 200 and data["preference"] == saved
    assert recognize_standard_prompt(load_domain("domains/coding.yaml"), saved["prompt"])["combo"]["code_structure"] == "separated"
    seen = []
    monkeypatch.setattr(api_server, "LIVE", True)
    monkeypatch.setattr(api_server, "_live_key_available", lambda _: True)
    monkeypatch.setattr(api_server, "DAILY_PREFERENCE_RUNS", DailyBudget(3))
    monkeypatch.setattr(service.generator, "generate_with_prompt", lambda prompt, source, model: seen.append((prompt, source)) or "결과")
    status, _, _ = request(server, f"/preferences/{saved['id']}/run", {"revision": 1, "task": "다음 작업", "basis": "personal"}, cookie)
    assert status == 200 and seen == [(draft["prompt"], "다음 작업")]

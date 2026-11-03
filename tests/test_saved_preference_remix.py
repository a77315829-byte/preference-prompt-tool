import copy

import pytest

import api_server
from auth import AuthService
from engine.domain_loader import load_domain
from engine.generator import build_final_prompt
from personal_prompts import PersonalPromptStore
from preference_comparison import compare_preferences, compose_task_prompt
from saved_preference_remix import remix_saved_prompt
import team
from tests.test_personal_prompts import request, signup
from tests.test_preference_comparison import COMBO, prepare
from tests.test_team import _history, db, server


@pytest.mark.parametrize("domain_key", ["coding", "summarization", "summarization_ko"])
@pytest.mark.parametrize("language", ["ko", "en"])
def test_remix_uses_recorded_values_preserves_language_and_keeps_original(db, domain_key, language):
    domain = load_domain(f"domains/{domain_key}.yaml")
    mine = {a.name: a.values[0].value if a.type == "enum" else "" for a in domain.axes}
    theirs = {a.name: a.values[-1].value if a.type == "enum" else "" for a in domain.axes}
    user, _ = AuthService(db).signup("alice", "alice-password-123")
    store = PersonalPromptStore(db)
    item = store.create(user.id, {"title": "개인 원본", "domainKey": domain_key,
        "prompt": build_final_prompt(domain, mine, language=None if language == "ko" else language)})
    comparison = compare_preferences(item, domain, "devteam", "팀 원본", [team.Member("팀원", _history(domain_key, theirs))], language)
    choices = {a["axis"]: "team" for a in comparison["axes"] if a["personal_value"] != a["team_value"]}
    draft = compose_task_prompt(item, domain, comparison, choices)
    saved = store.create(user.id, {"title": "작업용", "domainKey": domain_key, "prompt": draft["prompt"]}, provenance=draft["provenance"])
    before = copy.deepcopy(saved)
    changed = {axis: "personal" for axis in choices}
    remixed = remix_saved_prompt(saved, domain, changed)
    assert remixed["prompt"] == compose_task_prompt(item, domain, comparison, changed)["prompt"]
    assert remixed["provenance"]["personal"] == saved["provenance"]["personal"]
    assert remixed["provenance"]["team"] == saved["provenance"]["team"]
    parent = remixed["provenance"]["remixed_from"]
    assert parent["title"] == "작업용" and parent["revision"] == 1
    assert parent["axes"] == [{k: a[k] for k in ("axis", "label", "value", "source")} for a in saved["provenance"]["axes"]]
    assert remixed["provenance"]["language"] == language
    assert all(a["source"] == ("personal" if a["axis"] in choices else "shared") for a in remixed["provenance"]["axes"])
    assert store.get(user.id, saved["id"]) == before
    legacy = copy.deepcopy(saved); legacy["provenance"].pop("language")
    assert remix_saved_prompt(legacy, domain, changed)["prompt"] == remixed["prompt"]
    for invalid in (None, [], {}, {**changed, "made_up_axis": "team"}, {a: "fake" for a in changed}):
        with pytest.raises(ValueError):
            remix_saved_prompt(saved, domain, invalid)
    for altered in ({**saved, "provenance": None}, {**saved, "provenance_matches": False}, {**saved, "prompt": "직접 수정"}):
        with pytest.raises(ValueError):
            remix_saved_prompt(altered, domain, changed)


def test_saved_remix_creates_new_item_without_accessing_or_changing_source_team(server, monkeypatch):
    cookie, original, path = prepare(server)
    api_server.TEAMS.add("devteam", "coding", "민수", _history("coding", {**COMBO, "code_structure": "separated"}))
    _, data, _ = request(server, path + "/compare-team", {"revision": 1, "teamCode": "devteam"}, cookie)
    comparison = data["comparison"]
    selection = {"revision": 1, "teamCode": "devteam", "teamSnapshot": comparison["team_snapshot"],
        "language": comparison["team_language"], "choices": {"code_structure": "team"}}
    _, data, _ = request(server, path + "/compose-task", selection, cookie)
    _, data, _ = request(server, path + "/save-task", {**selection, "title": "작업용 원본", "taskSnapshot": data["draft"]["snapshot"]}, cookie)
    saved = data["preference"]
    api_server.PERSONAL_PROMPTS.delete(1, original["id"], 1)
    monkeypatch.setattr(api_server.TEAMS, "get", lambda *_: pytest.fail("재조합은 현재 팀을 조회하지 않는다"))
    remix_path = f"/preferences/{saved['id']}"
    body = {"revision": 1, "choices": {"code_structure": "personal"}}
    status, data, _ = request(server, remix_path + "/remix-preview", body, cookie)
    assert status == 200
    draft = data["draft"]
    save = {**body, "draftSnapshot": draft["snapshot"], "title": "새 개인 구성", "note": "다른 작업용",
        "prompt": "위조 프롬프트", "provenance": {"fake": True}, "domainKey": "summarization_ko"}
    bob = signup(server, "bob")
    for action in ("remix-preview", "remix-save"):
        assert request(server, remix_path + "/" + action, save)[0] == 401
        assert request(server, remix_path + "/" + action, save, bob)[0] == 404
    for changes, status in (({"title": saved["title"]}, 400), ({"title": " "}, 400), ({"revision": 2}, 409),
                            ({"draftSnapshot": "stale"}, 409), ({"choices": {"code_structure": "team"}}, 409)):
        assert request(server, remix_path + "/remix-save", {**save, **changes}, cookie)[0] == status
    assert len(api_server.PERSONAL_PROMPTS.list_for(1)) == 1
    status, data, _ = request(server, remix_path + "/remix-save", save, cookie)
    new = data["preference"]
    assert status == 201 and new["id"] != saved["id"] and new["revision"] == 1
    assert new["title"] == save["title"] and new["domain_key"] == "coding" and new["prompt"] == draft["prompt"]
    assert new["provenance_matches"] is True
    assert next(a for a in new["provenance"]["axes"] if a["axis"] == "code_structure")["source"] == "personal"
    assert api_server.PERSONAL_PROMPTS.get(1, saved["id"]) == saved
    assert len(api_server.PERSONAL_PROMPTS.list_for(1)) == 2
    # 새 항목에서도 같은 두 출처 값으로 다시 조합할 수 있다.
    assert request(server, f"/preferences/{new['id']}/remix-preview", {"revision": 1, "choices": {"code_structure": "team"}}, cookie)[0] == 200
    # 비교 기준은 직전 작업용의 당시 값이며 원본 삭제 후에도 남는다.
    baseline = new["provenance"]["remixed_from"]
    assert baseline["axes"] == [{k: a[k] for k in ("axis", "label", "value", "source")} for a in saved["provenance"]["axes"]]
    api_server.PERSONAL_PROMPTS.delete(1, saved["id"], 1)
    assert api_server.PERSONAL_PROMPTS.get(1, new["id"])["provenance"]["remixed_from"] == baseline
    _, data, _ = request(server, f"/preferences/{new['id']}/remix-preview", {"revision": 1, "choices": {"code_structure": "team"}}, cookie)
    assert data["draft"]["provenance"]["remixed_from"]["title"] == new["title"]
    assert data["draft"]["provenance"]["remixed_from"]["axes"] == [{k: a[k] for k in ("axis", "label", "value", "source")} for a in new["provenance"]["axes"]]

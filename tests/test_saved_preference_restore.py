import copy

import pytest

import api_server
from auth import AuthService
from engine.domain_loader import load_domain
from engine.generator import build_final_prompt
from personal_prompts import PersonalPromptStore
from preference_comparison import compare_preferences, compose_task_prompt
from saved_preference_remix import remix_saved_prompt
from saved_preference_restore import restore_saved_prompt
import team
from tests.test_personal_prompts import request, signup
from tests.test_preference_comparison import COMBO, prepare
from tests.test_team import _history, db, server


@pytest.mark.parametrize("domain_key", ["coding", "summarization", "summarization_ko"])
@pytest.mark.parametrize("language", ["ko", "en"])
def test_restore_only_selected_changed_axes_and_keep_current_record(db, domain_key, language):
    domain = load_domain(f"domains/{domain_key}.yaml")
    mine = {a.name: a.values[0].value if a.type == "enum" else "" for a in domain.axes}
    if domain_key == "coding" and language == "ko":
        mine["code_structure"] = ""  # 이전 값이 미정이면 해당 지시를 다시 제외한다.
    theirs = {a.name: a.values[-1].value if a.type == "enum" else "" for a in domain.axes}
    user, _ = AuthService(db).signup("alice", "alice-password-123")
    store = PersonalPromptStore(db)
    item = store.create(user.id, {"title": "개인", "domainKey": domain_key,
        "prompt": build_final_prompt(domain, mine, language=None if language == "ko" else language)})
    comparison = compare_preferences(item, domain, "devteam", "팀", [team.Member("팀원", _history(domain_key, theirs))], language)
    choices = {a["axis"]: "personal" for a in comparison["axes"] if a["personal_value"] != a["team_value"]}
    initial = compose_task_prompt(item, domain, comparison, choices)
    old = store.create(user.id, {"title": "이전 작업용", "domainKey": domain_key, "prompt": initial["prompt"]}, provenance=initial["provenance"])
    new_choices = dict.fromkeys(choices, "team")
    changed = remix_saved_prompt(old, domain, new_choices)
    current = store.create(user.id, {"title": "현재 조합", "domainKey": domain_key, "prompt": changed["prompt"]}, provenance=changed["provenance"])
    untouched = copy.deepcopy(current)
    selected = [next(iter(choices))]
    restored = restore_saved_prompt(current, domain, selected)
    assert restored["prompt"] == remix_saved_prompt(current, domain, {**new_choices, selected[0]: "personal"})["prompt"]
    assert restored["restore_axes"] == selected
    assert restored["provenance"]["operation"] == "restore"
    assert restored["provenance"]["remixed_from"]["id"] == current["id"]
    assert store.get(user.id, current["id"]) == untouched
    assert restore_saved_prompt(current, domain, list(choices))["prompt"] == old["prompt"]
    assert restore_saved_prompt(current, domain, list(reversed(choices)))["snapshot"] == restore_saved_prompt(current, domain, list(choices))["snapshot"]
    for invalid in (None, [], "axis", [selected[0], selected[0]], ["fake"], [[]]):
        with pytest.raises(ValueError):
            restore_saved_prompt(current, domain, invalid)
    with pytest.raises(ValueError):
        restore_saved_prompt({**current, "provenance_matches": False}, domain, selected)
    with pytest.raises(ValueError):
        restore_saved_prompt(old, domain, selected)


def test_restore_api_creates_separate_item_without_changing_other_axes_or_sources(server, monkeypatch):
    cookie, original, path = prepare(server)
    api_server.TEAMS.add("devteam", "coding", "민수", _history("coding", {**COMBO, "code_structure": "separated", "type_detail": "inferred"}))
    _, data, _ = request(server, path + "/compare-team", {"revision": 1, "teamCode": "devteam"}, cookie)
    comparison = data["comparison"]
    selection = {"revision": 1, "teamCode": "devteam", "teamSnapshot": comparison["team_snapshot"],
        "language": comparison["team_language"], "choices": {"code_structure": "team", "type_detail": "team"}}
    _, data, _ = request(server, path + "/compose-task", selection, cookie)
    _, data, _ = request(server, path + "/save-task", {**selection, "title": "이전 작업용", "taskSnapshot": data["draft"]["snapshot"]}, cookie)
    old = data["preference"]
    body = {"revision": 1, "choices": {"code_structure": "personal", "type_detail": "personal"}}
    _, data, _ = request(server, f"/preferences/{old['id']}/remix-preview", body, cookie)
    _, data, _ = request(server, f"/preferences/{old['id']}/remix-save", {**body, "draftSnapshot": data["draft"]["snapshot"], "title": "현재 조합"}, cookie)
    current = data["preference"]
    restore_path = f"/preferences/{current['id']}"
    monkeypatch.setattr(api_server.TEAMS, "get", lambda *_: pytest.fail("현재 팀 조회 불필요"))
    monkeypatch.setattr(api_server, "_take", lambda *_: pytest.fail("미리 보기·저장은 실행 사용량을 차감하지 않는다"))
    body = {"revision": 1, "restoreAxes": ["code_structure"]}
    status, data, _ = request(server, restore_path + "/restore-preview", body, cookie)
    assert status == 200
    draft = data["draft"]
    save = {**body, "title": "코드 구성만 되돌린 조합", "note": "타입은 현재 유지", "draftSnapshot": draft["snapshot"], "prompt": "위조", "choices": {"type_detail": "team"}}
    bob = signup(server, "bob")
    for action in ("restore-preview", "restore-save"):
        assert request(server, restore_path + "/" + action, save)[0] == 401
        assert request(server, restore_path + "/" + action, save, bob)[0] == 404
    for changes, status in (({"restoreAxes": []}, 400), ({"restoreAxes": ["style_management"]}, 400), ({"restoreAxes": ["fake"]}, 400),
                            ({"restoreAxes": ["type_detail"]}, 409), ({"draftSnapshot": "old"}, 409), ({"revision": 2}, 409),
                            ({"title": current["title"]}, 400), ({"title": " "}, 400)):
        assert request(server, restore_path + "/restore-save", {**save, **changes}, cookie)[0] == status
    assert len(api_server.PERSONAL_PROMPTS.list_for(1)) == 3
    status, data, _ = request(server, restore_path + "/restore-save", save, cookie)
    restored = data["preference"]
    assert status == 201 and restored["id"] != current["id"] and restored["prompt"] == draft["prompt"]
    rows = {a["axis"]: a for a in restored["provenance"]["axes"]}
    assert rows["code_structure"]["value"] == "separated" and rows["code_structure"]["source"] == "team"
    assert rows["type_detail"]["value"] == "explicit" and rows["type_detail"]["source"] == "personal"
    assert rows["style_management"]["value"] == "theme"
    for saved in (original, old, current):
        assert api_server.PERSONAL_PROMPTS.get(1, saved["id"]) == saved
    # 비교 대상이 삭제되어도 저장된 변경 전 기록으로 복원한다.
    api_server.PERSONAL_PROMPTS.delete(1, old["id"], 1)
    assert request(server, restore_path + "/restore-preview", body, cookie)[0] == 200

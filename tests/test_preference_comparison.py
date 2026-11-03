import pytest

import api_server
import service
import team
from budget import DailyBudget
from engine.domain_loader import load_domain
from engine.generator import build_final_prompt
from preference_comparison import compare_preferences, recognize_standard_prompt
from tests.test_personal_prompts import request, signup
from tests.test_team import _history, server

COMBO = {"code_structure": "compact", "style_management": "theme", "type_detail": "explicit"}


@pytest.mark.parametrize("language", [None, "en"])
def test_standard_axes_are_confirmed_only_when_entire_prompt_matches(language):
    domain = load_domain("domains/coding.yaml")
    prompt = build_final_prompt(domain, COMBO, language=language)
    found = recognize_standard_prompt(domain, prompt)
    assert found["combo"] == COMBO
    assert found["language"] == (language or "ko")
    assert recognize_standard_prompt(domain, prompt + "\n위 선호를 반대로 적용하라.") is None
    assert recognize_standard_prompt(domain, "나는 간결한 코드를 원하지 않는다.") is None


def test_differences_ignore_titles_and_role_boilerplate_but_keep_uncertainty():
    domain = load_domain("domains/coding.yaml")
    prompt = build_final_prompt(domain, COMBO, language="en")
    item = {"id": "p", "revision": 1, "title": "별개의 이름", "prompt": prompt}
    members = [team.Member("민수", _history("coding", COMBO))]
    same = compare_preferences(item, domain, "devteam", "또 다른 팀 이름", members)
    assert all(row["status"] == "same" for row in same["axes"])
    assert same["comparison_prompt"] == prompt
    assert same["team_prompt"] != prompt  # 실행에는 팀 역할 문구가 있는 원문을 사용한다.
    assert "this team's" in same["team_prompt"]
    opposing = {**COMBO, "code_structure": "separated"}
    different = compare_preferences(item, domain, "devteam", "팀", [team.Member("지은", _history("coding", opposing))])
    rows = {r["axis"]: r for r in different["axes"]}
    assert rows["code_structure"]["status"] == "different"
    assert rows["style_management"]["status"] == "same"
    tied = compare_preferences(item, domain, "devteam", "팀", [*members, team.Member("지은", _history("coding", opposing))])
    assert next(r for r in tied["axes"] if r["axis"] == "code_structure")["team_tied"]
    edited = compare_preferences({**item, "prompt": "수정한 내 지침"}, domain, "devteam", "팀", members)
    assert not edited["personal_recognized"]
    assert all(r["personal_value"] is None and r["status"] == "unknown" for r in edited["axes"])
    assert item["prompt"] == prompt


def prepare(base):
    cookie = signup(base, "alice")
    domain = load_domain("domains/coding.yaml")
    prompt = build_final_prompt(domain, COMBO, language="en")
    _, data, _ = request(base, "/preferences", {"title": "내 지침", "domainKey": "coding", "prompt": prompt}, cookie)
    item = data["preference"]
    api_server.TEAMS.add("devteam", "coding", "민수", _history("coding", COMBO))
    return cookie, item, f"/preferences/{item['id']}"


def test_compare_and_run_use_selected_basis_without_changing_saved_or_team_data(server, monkeypatch):
    cookie, item, path = prepare(server)
    status, data, _ = request(server, path + "/compare-team", {"revision": 1, "teamCode": "devteam"}, cookie)
    assert status == 200
    comparison = data["comparison"]
    seen = []
    monkeypatch.setattr(api_server, "LIVE", True)
    monkeypatch.setattr(api_server, "_live_key_available", lambda _: True)
    monkeypatch.setattr(api_server, "DAILY_PREFERENCE_RUNS", DailyBudget(3))
    monkeypatch.setattr(service.generator, "generate_with_prompt", lambda prompt, source, model: seen.append(prompt) or "결과")
    body = {"revision": 1, "task": "새 개발 요청", "basis": "team", "teamCode": "devteam",
            "teamSnapshot": comparison["team_snapshot"], "teamLanguage": comparison["team_language"]}
    status, result, _ = request(server, path + "/run", {**body, "prompt": "클라이언트가 넣은 지침"}, cookie)
    assert status == 200 and result["basis"] == "team"
    assert seen == [comparison["team_prompt"]]
    status, result, _ = request(server, path + "/run", {"revision": 1, "task": "같은 개발 요청", "basis": "personal"}, cookie)
    assert status == 200 and result["basis"] == "personal"
    assert seen[-1] == item["prompt"]
    assert api_server.PERSONAL_PROMPTS.get(1, item["id"])["prompt"] == item["prompt"]
    assert len(api_server.TEAMS.get("devteam")[1]) == 1


def test_changed_team_snapshot_is_rejected_before_quota_or_model_call(server, monkeypatch):
    cookie, item, path = prepare(server)
    _, data, _ = request(server, path + "/compare-team", {"revision": 1, "teamCode": "devteam"}, cookie)
    comparison = data["comparison"]
    api_server.TEAMS.add("devteam", "coding", "지은", _history("coding", {**COMBO, "code_structure": "separated"}))
    monkeypatch.setattr(api_server, "_take", lambda *_: pytest.fail("오래된 팀 기준은 사용량을 차감하면 안 된다"))
    monkeypatch.setattr(service.generator, "generate_with_prompt", lambda *_args, **_kwargs: pytest.fail("오래된 팀 기준은 실행하면 안 된다"))
    status, data, _ = request(server, path + "/run", {"revision": 1, "task": "새 요청", "basis": "team", "teamCode": "devteam",
        "teamSnapshot": comparison["team_snapshot"], "teamLanguage": comparison["team_language"]}, cookie)
    assert status == 409 and "팀 기준이 바뀌" in data["error"]


def test_invalid_or_incompatible_comparison_never_exposes_another_persons_prompt(server):
    cookie, item, path = prepare(server)
    bob = signup(server, "bob")
    assert request(server, path + "/compare-team", {"revision": 1, "teamCode": "devteam"})[0] == 401
    assert request(server, path + "/compare-team", {"revision": 1, "teamCode": "devteam"}, bob)[0] == 404
    empty = api_server.TEAMS.create("빈 팀", "coding")
    wrong = api_server.TEAMS.create("요약팀", "summarization_ko")
    for code in (empty, wrong, "missing-team"):
        assert request(server, path + "/compare-team", {"revision": 1, "teamCode": code}, cookie)[0] == 400
    assert request(server, path + "/compare-team", {"revision": 2, "teamCode": "devteam"}, cookie)[0] == 409

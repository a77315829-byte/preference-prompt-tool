"""언어별 준비 예시와 비교 기록의 저장/격리 검증. 유료 API를 쓰지 않는다."""
import ast
import copy

import pytest

import api_server
from app_db import Database
from coding_examples import SNIPPETS, build_coding_examples
from coding_instructions import PREFERENCES, build_coding_instructions
from personal_prompts import PersonalPromptStore
from tests.test_coding_instructions import PROFILE
from tests.test_personal_prompts import request, signup
from tests.test_team import db, server


@pytest.mark.parametrize("language", SNIPPETS)
def test_each_language_has_four_distinct_comparisons_with_one_target_axis(language):
    profile = {**PROFILE, "language": language}
    before = copy.deepcopy(profile)
    examples = build_coding_examples(profile)
    assert profile == before
    assert examples["language"] == language and examples["framework"] == "FastAPI"
    assert examples == build_coding_examples(profile)
    assert [p["axis"] for p in examples["pairs"]] == list(PREFERENCES)
    for pair in examples["pairs"]:
        assert [o["value"] for o in pair["options"]] == list(PREFERENCES[pair["axis"]])
        a, b = pair["options"]
        assert (a["code"], a["explanation"]) != (b["code"], b["explanation"])
        assert "React" not in a["code"] + b["code"]
    output = examples["pairs"][-1]
    assert "3000" in output["before"] and all("2500" in o["code"] for o in output["options"])
    assert "3000" not in output["options"][0]["code"]


def test_python_variants_preserve_behavior_and_the_change_example_has_context():
    examples = build_coding_examples({**PROFILE, "framework": ""})
    for pair in examples["pairs"][:3]:
        for option in pair["options"]:
            ast.parse(option["code"])
            namespace = {}
            exec(compile(option["code"], '<reviewed-comparison-fixture>', 'exec'), namespace)
            assert namespace["order_total"](10000, 2) == 23000
    output = examples["pairs"][-1]
    namespace = {}
    exec(compile(output["options"][0]["code"], '<reviewed-change-fixture>', 'exec'), namespace)
    assert namespace["order_total"](10000, 2) == 22500


@pytest.mark.parametrize("comparison", [
    {}, [], {"version": True, "choices": PROFILE["preferences"]},
    {"version": 2, "choices": PROFILE["preferences"]},
    {"version": 1, "choices": {"output": "changes"}},
    {"version": 1, "choices": {**PROFILE["preferences"], "comments": []}},
    {"version": 1, "choices": {**PROFILE["preferences"], "output": "complete"}},
])
def test_invalid_or_mismatching_comparison_cannot_be_saved_as_evidence(comparison):
    with pytest.raises(ValueError):
        build_coding_instructions({**PROFILE, "comparison": comparison})


def test_unknown_languages_keep_direct_settings_but_cannot_claim_prepared_comparison():
    profile = {**PROFILE, "language": "Elixir"}
    assert "Elixir" in build_coding_instructions(profile)["prompt"]
    with pytest.raises(ValueError, match="준비 중"):
        build_coding_examples(profile)
    with pytest.raises(ValueError):
        build_coding_instructions({**profile, "comparison": {"version": 1, "choices": PROFILE["preferences"]}})


def test_api_compare_save_reopen_reuse_and_manual_edit_preserve_original(server, monkeypatch):
    monkeypatch.setattr(api_server, "_take", lambda *_: pytest.fail("준비 예시·조립·저장은 유료 호출을 차감하지 않는다"))
    status, data, _ = request(server, '/coding-instructions/examples', {"profile": PROFILE})
    assert status == 200 and data["examples"]["language"] == "Python"
    assert request(server, '/coding-instructions/examples', {"profile": {}})[0] == 400
    assert request(server, '/coding-instructions/examples', {"profile": {**PROFILE, "language": "SQL"}})[0] == 400
    profile = {**PROFILE, "comparison": {"version": 1, "choices": {**PROFILE["preferences"], "comments": None}}}
    draft = request(server, '/coding-instructions/preview', {"profile": profile})[1]["draft"]
    assert draft["profile"] == profile and "예시 비교에서 정한" in draft["prompt"]
    cookie = signup(server, 'compare-user')
    body = {"title": "Python 비교 취향", "domainKey": "coding", "prompt": draft["prompt"], "codingProfile": draft["profile"]}
    status, data, _ = request(server, '/preferences', body, cookie)
    assert status == 201
    item = data["preference"]
    path = f'/preferences/{item["id"]}'
    assert request(server, path, cookie=cookie)[1]["preference"] == item
    assert request(server, path, cookie=signup(server, 'another-user'))[0] == 404
    # 다시 설정을 사용해 새 지침을 만들어도 저장 원본은 갱신하지 않는다.
    assert request(server, '/coding-instructions/preview', {"profile": item["coding_profile"]})[1]["draft"] == draft
    assert request(server, path, cookie=cookie)[1]["preference"] == item
    assert request(server, path + '/compare-team', {"revision": 1, "teamCode": "react-team"}, cookie)[0] == 400
    edited = request(server, path + '/update', {**body, "prompt": "직접 수정", "revision": 1}, cookie)[1]["preference"]
    assert edited["coding_profile"] == profile and edited["coding_profile_matches"] is False
    assert PersonalPromptStore(Database(api_server.DB.path)).get(1, item["id"])["coding_profile"] == profile

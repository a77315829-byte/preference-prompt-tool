"""프레임워크 예시의 경로 계약·계산, 출처 저장과 기존 저장본 호환성 검증."""
import ast
import copy

import pytest

import api_server
from coding_examples import build_coding_examples
from coding_framework_examples import framework_example_source
from coding_instructions import build_coding_instructions, PREFERENCES
from tests.test_coding_instructions import PROFILE
from tests.test_personal_prompts import request, signup
from tests.test_team import db, server


@pytest.mark.parametrize("language,framework,marker", [
    ("Python", "FastAPI", "@app.get"), ("Java", "Spring Boot", "@RestController"),
])
def test_framework_examples_have_files_same_api_contract_and_comparison_source(language, framework, marker):
    profile = {**PROFILE, "language": language, "framework": framework}
    before = copy.deepcopy(profile)
    examples = build_coding_examples(profile)
    assert profile == before
    assert examples["version"] == 2
    assert examples["source"] == framework_example_source(language, framework)
    assert examples["source"]["kind"] == "framework"
    assert marker in examples["pairs"][0]["options"][0]["code"]
    assert [pair["axis"] for pair in examples["pairs"]] == list(PREFERENCES)
    for pair in examples["pairs"]:
        assert [option["value"] for option in pair["options"]] == list(PREFERENCES[pair["axis"]])
        for option in pair["options"]:
            assert option["files"] and all(file["name"] and file["code"] for file in option["files"])
    structure = examples["pairs"][2]
    assert len(structure["options"][0]["files"]) == 1
    assert len(structure["options"][1]["files"]) == 2
    assert "/orders/total" in structure["options"][0]["code"]
    output = examples["pairs"][3]
    assert "3000" in output["before"]
    assert "3000" not in output["options"][0]["code"]
    assert "2500" in output["options"][0]["code"]
    assert output["options"][1]["files"][0]["name"] == output["options"][0]["files"][0]["name"]
    before_code = examples["pairs"][0]["options"][0]["files"][0]["code"]
    old_line = next(line for line in before_code.splitlines() if "3000" in line)
    partial = output["options"][1]["files"][0]["code"]
    assert before_code.replace(old_line, partial) == output["options"][0]["files"][0]["code"]


def test_fastapi_variants_have_equivalent_calculation_and_explicit_route_wiring():
    """정적 경로 검사와 함수 계산 검사이며 FastAPI HTTP 실행 검사와 구분한다."""
    examples = build_coding_examples(PROFILE)
    for pair in examples["pairs"][:3] + [examples["pairs"][3]]:
        for option in pair["options"]:
            if option["value"] == "changes":
                continue
            trees = [ast.parse(file["code"], filename=file["name"]) for file in option["files"]]
            endpoint = next(node for tree in trees for node in tree.body
                            if isinstance(node, ast.FunctionDef) and node.name == "order_total")
            assert [arg.arg for arg in endpoint.args.args] == ["price", "quantity"]
            assert all(default.func.id == "Query" and any(k.arg == "ge" and k.value.value == 0 for k in default.keywords)
                       for default in endpoint.args.defaults)
            decorator = endpoint.decorator_list[0]
            if len(trees) == 1:
                assert decorator.func.value.id == "app" and decorator.args[0].value == "/orders/total"
            else:
                assert decorator.func.value.id == "router" and decorator.args[0].value == "/total"
                joined = "\n".join(file["code"] for file in option["files"])
                assert 'APIRouter(prefix="/orders")' in joined and 'app.include_router(router)' in joined
            endpoint = copy.deepcopy(endpoint)
            endpoint.decorator_list = []
            endpoint.args.defaults = []
            module = ast.fix_missing_locations(ast.Module(body=[endpoint], type_ignores=[]))
            scope = {}
            exec(compile(module, '<reviewed-route-calculation>', 'exec'), scope)
            delivery = 2500 if pair["axis"] == "output" else 3000
            assert scope["order_total"](10000, 2) == {"total": 20000 + delivery}
            assert scope["order_total"](0, 0) == {"total": delivery}


@pytest.mark.parametrize("language,framework", [("Python", "Django"), ("Java", "FastAPI"), ("Python", "FastAPI 9.x"), ("Go", "Gin")])
def test_unprepared_or_mismatched_framework_is_clearly_language_only(language, framework):
    examples = build_coding_examples({**PROFILE, "language": language, "framework": framework})
    assert examples["version"] == 1 and examples["source"]["kind"] == "language"
    assert framework + " 전용 예시는 아직 없어" in examples["notice"]


def test_old_language_comparison_with_fastapi_setting_keeps_original_prompt_and_source():
    old_profile = {**PROFILE, "comparison": {"version": 1, "choices": dict(PROFILE["preferences"])}}
    draft = build_coding_instructions(old_profile)
    assert draft["profile"] == old_profile
    assert "비교 예시:" not in draft["prompt"]
    assert draft == build_coding_instructions(draft["profile"])
    source = framework_example_source("Python", "FastAPI")
    framework_draft = build_coding_instructions({**old_profile, "comparison": {**old_profile["comparison"], "version": 2, "example": source}})
    assert source["label"] in framework_draft["prompt"]
    assert framework_draft["prompt"] != draft["prompt"]


@pytest.mark.parametrize("changes", [
    {"language": "Java"}, {"framework": "Django"},
    {"comparison": {"version": 2, "choices": dict(PROFILE["preferences"])}},
    {"comparison": {"version": 2, "choices": dict(PROFILE["preferences"]), "example": {"id": "spring-boot-orders-v1", "kind": "framework"}}},
])
def test_framework_comparison_cannot_silently_change_environment_or_source(changes):
    profile = {**PROFILE, "comparison": {"version": 2, "choices": dict(PROFILE["preferences"]),
                                       "example": framework_example_source("Python", "FastAPI")}}
    with pytest.raises(ValueError):
        build_coding_instructions({**profile, **changes})


@pytest.mark.parametrize("language,framework", [("Python", "FastAPI"), ("Java", "Spring Boot")])
def test_framework_comparison_api_save_reopen_and_reuse_never_overwrite_original(server, monkeypatch, language, framework):
    monkeypatch.setattr(api_server, "_take", lambda *_: pytest.fail("준비 예시와 저장은 모델 사용량을 차감하지 않는다"))
    profile = {**PROFILE, "language": language, "framework": framework}
    status, data, _ = request(server, '/coding-instructions/examples', {"profile": profile})
    assert status == 200
    examples = data["examples"]
    profile["comparison"] = {"version": examples["version"], "choices": {**profile["preferences"], "comments": None}, "example": examples["source"]}
    draft = request(server, '/coding-instructions/preview', {"profile": profile})[1]["draft"]
    cookie = signup(server, 'framework-user')
    status, data, _ = request(server, '/preferences', {"title": "프레임워크 비교", "domainKey": "coding", "codingProfile": draft["profile"], "prompt": draft["prompt"]}, cookie)
    assert status == 201
    original = data["preference"]
    path = f'/preferences/{original["id"]}'
    assert original["coding_profile"]["comparison"]["example"] == examples["source"]
    assert request(server, path, cookie=cookie)[1]["preference"] == original
    assert request(server, '/coding-instructions/preview', {"profile": original["coding_profile"]})[1]["draft"] == draft
    assert request(server, path, cookie=cookie)[1]["preference"] == original
    assert request(server, path, cookie=signup(server, 'framework-other'))[0] == 404

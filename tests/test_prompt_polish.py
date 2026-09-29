"""agents/prompt_polish.py 회귀 테스트. API 없이 전부 돈다 - 체크리스트는
순수 코드이고, polish()의 모델 호출은 monkeypatch로 막는다.
"""

from __future__ import annotations

import json

import pytest

from agents import prompt_polish as pp

THIN_PROMPT = "요약해줘"
RICH_PROMPT = (
    "너는 5년차 백엔드 개발자다. 아래 PR 설명을 팀 리뷰어가 읽을 수 있게 "
    "다듬어라. 불릿 목록 형식으로 쓰고, 5줄 이내로 제한한다. 과장된 표현은 "
    "쓰지 마라. 예: '- 캐시 미스 시 재시도 로직을 추가했습니다.'"
)


# ── 체크리스트: 순수 함수, API 불필요 ──────────────────────────────────

def test_thin_prompt_fails_most_checks() -> None:
    results = pp.checklist(THIN_PROMPT)
    failed = {r.name for r in results if not r.passed}
    assert {"분량", "역할 지정", "출력 형식", "제약 조건", "예시"} <= failed


def test_rich_prompt_passes_structural_checks() -> None:
    results = pp.checklist(RICH_PROMPT)
    by_name = {r.name: r.passed for r in results}
    assert by_name["역할 지정"] is True
    assert by_name["출력 형식"] is True
    assert by_name["제약 조건"] is True
    assert by_name["예시"] is True


def test_vague_words_detected() -> None:
    result = pp.check_vague_words("적당히 알아서 잘 써줘")
    assert result.passed is False
    assert "적당히" in result.note


def test_vague_words_absent_when_specific() -> None:
    result = pp.check_vague_words("300단어 이내로, 존댓말로 써줘")
    assert result.passed is True


def test_length_threshold_is_word_count_not_character_count() -> None:
    # "분량" 체크가 글자 수가 아니라 단어 수를 쓴다는 걸 고정한다 - 한국어는
    # 띄어쓰기가 부실하면 짧은 문장도 char 기준으로는 길게 잡힐 수 있다.
    short = pp.check_length("한 두 세 네 다섯 여섯 일곱 여덟 아홉 열")  # 10단어
    assert short.passed is False
    long_ = pp.check_length(" ".join(["단어"] * 15))
    assert long_.passed is True


# ── polish(): 모델 호출을 막고 캐시·파싱만 검증 ────────────────────────

class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = type("M", (), {"content": content})()


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


FAKE_REPLY = (
    "역할이 빠져 있다.\n형식도 없다.\n"
    "---다듬은 프롬프트---\n"
    "[역할]\n[ ]\n[목표]\n요약\n[형식]\n[ ]\n[제약]\n[ ]\n[예시]\n[ ]"
)


def test_polish_parses_suggestions_and_revised_prompt(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(pp, "CACHE_DIR", tmp_path)
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return _FakeResponse(FAKE_REPLY)

    monkeypatch.setattr(pp, "completion", fake_completion)

    result = pp.polish(THIN_PROMPT, model="fake/model")

    assert len(calls) == 1
    assert "역할이 빠져 있다" in result.suggestions
    assert result.revised_prompt.startswith("[역할]")
    assert len(result.checklist) == len(pp.CHECKS)


def test_polish_caches_and_does_not_call_twice(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(pp, "CACHE_DIR", tmp_path)
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return _FakeResponse(FAKE_REPLY)

    monkeypatch.setattr(pp, "completion", fake_completion)

    pp.polish(THIN_PROMPT, model="fake/model")
    pp.polish(THIN_PROMPT, model="fake/model")

    assert len(calls) == 1  # 두 번째 호출은 캐시를 탄다


def test_polish_cache_is_keyed_by_model_too(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(pp, "CACHE_DIR", tmp_path)
    calls = []
    monkeypatch.setattr(pp, "completion", lambda **kw: calls.append(kw) or _FakeResponse(FAKE_REPLY))

    pp.polish(THIN_PROMPT, model="fake/model-a")
    pp.polish(THIN_PROMPT, model="fake/model-b")

    assert len(calls) == 2


def test_polish_raises_on_empty_model_response(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(pp, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(pp, "completion", lambda **kw: _FakeResponse(""))

    with pytest.raises(ValueError):
        pp.polish(THIN_PROMPT, model="fake/model")


def test_cache_file_is_valid_json_with_prompt_and_response(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(pp, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(pp, "completion", lambda **kw: _FakeResponse(FAKE_REPLY))

    pp.polish(THIN_PROMPT, model="fake/model")

    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["prompt"] == THIN_PROMPT
    assert payload["response"] == FAKE_REPLY

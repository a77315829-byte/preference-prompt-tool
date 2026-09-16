"""generate_all()이 동시에 호출하면서 순서를 지키는지 검증."""

import threading
import time

import pytest

from engine.domain_loader import load_domain
from engine.generator import generate_all
import engine.generator as generator_module


COMBOS = (
    {"length": "short", "extractiveness": "fully", "topic": ""},
    {"length": "long", "extractiveness": "normal", "topic": ""},
    {"length": "normal", "extractiveness": "high", "topic": ""},
)


@pytest.fixture
def domain():
    return load_domain("domains/summarization_ko.yaml")


def test_results_follow_input_order(domain, monkeypatch) -> None:
    """A/B가 뒤바뀌면 사용자가 고른 것과 다른 축을 학습한다.

    빨리 끝나는 호출이 먼저 반환되는 순서로 결과를 모으면(as_completed)
    순서가 섞인다. 일부러 뒤쪽 조합을 더 빠르게 만들어 확인한다.
    """
    delays = {"short": 0.20, "long": 0.05, "normal": 0.01}

    def fake_generate(_domain, _source, combo, model, cache_dir=None):
        time.sleep(delays[combo["length"]])
        return combo["length"]

    monkeypatch.setattr(generator_module, "generate", fake_generate)

    got = generate_all(domain, "원문", COMBOS, model="x")
    assert got == ["short", "long", "normal"]


def test_calls_run_concurrently(domain, monkeypatch) -> None:
    """순차 실행이면 총 시간이 합계가 된다. 동시라면 최댓값 근처다."""
    sleep_each = 0.25

    def fake_generate(_domain, _source, combo, model, cache_dir=None):
        time.sleep(sleep_each)
        return combo["length"]

    monkeypatch.setattr(generator_module, "generate", fake_generate)

    start = time.monotonic()
    generate_all(domain, "원문", COMBOS, model="x")
    elapsed = time.monotonic() - start

    sequential = sleep_each * len(COMBOS)
    assert elapsed < sequential * 0.7, (
        f"{elapsed:.2f}s 걸렸다. 순차({sequential:.2f}s)와 차이가 없으면 동시 실행이 아니다."
    )


def test_uses_distinct_threads(domain, monkeypatch) -> None:
    seen: set[int] = set()
    lock = threading.Lock()

    def fake_generate(_domain, _source, combo, model, cache_dir=None):
        time.sleep(0.15)
        with lock:
            seen.add(threading.get_ident())
        return combo["length"]

    monkeypatch.setattr(generator_module, "generate", fake_generate)
    generate_all(domain, "원문", COMBOS, model="x")
    assert len(seen) > 1


def test_exception_propagates(domain, monkeypatch) -> None:
    """한 후보가 실패하면 호출자에게 그대로 올라와야 한다.

    app.py 는 이 예외를 잡아 데모 모드로 내려간다. 스레드 안에서 조용히
    삼켜지면 그 경로가 죽는다.
    """
    def fake_generate(_domain, _source, combo, model, cache_dir=None):
        if combo["length"] == "long":
            raise RuntimeError("AuthenticationError: invalid api key")
        return combo["length"]

    monkeypatch.setattr(generator_module, "generate", fake_generate)

    with pytest.raises(RuntimeError, match="invalid api key"):
        generate_all(domain, "원문", COMBOS, model="x")


def test_empty_and_single(domain, monkeypatch) -> None:
    calls = []

    def fake_generate(_domain, _source, combo, model, cache_dir=None):
        calls.append(combo["length"])
        return combo["length"]

    monkeypatch.setattr(generator_module, "generate", fake_generate)

    assert generate_all(domain, "원문", (), model="x") == []
    assert calls == []
    # 하나뿐이면 스레드를 띄우지 않고 바로 부른다.
    assert generate_all(domain, "원문", COMBOS[:1], model="x") == ["short"]
    assert calls == ["short"]


def test_optional_arguments_are_passed_by_keyword(domain, monkeypatch) -> None:
    """선택 인자는 키워드로 넘어와야 한다.

    위치로 넘기면 인자를 하나 더할 때 호출부와 테스트 대역이 조용히 깨진다.
    실제로 temperature 를 더한 직후 앱의 프롬프트 비교가 죽었고, app.py 의
    try/except 가 그 TypeError 를 삼켜서 화면에는 "API 호출 실패"로만
    보였다. 필수 인자만 위치로 받는 대역으로 그 계약을 고정한다.
    """
    calls = []

    def strict_fake(prompt, source_text, model, *, cache_dir=None, temperature=None):
        calls.append({"temperature": temperature, "cache_dir": cache_dir})
        return "ok"

    monkeypatch.setattr(generator_module, "generate_with_prompt", strict_fake)

    from engine.generator import generate_all_with_prompts

    # 하나일 때와 여럿일 때 경로가 다르므로 둘 다 본다.
    assert generate_all_with_prompts(["p1"], "원문", model="x", temperature=0.0) == ["ok"]
    assert generate_all_with_prompts(["p1", "p2"], "원문", model="x", temperature=0.0) == [
        "ok",
        "ok",
    ]
    assert len(calls) == 3
    assert all(call["temperature"] == 0.0 for call in calls)


def test_temperature_is_part_of_the_cache_key(domain, tmp_path) -> None:
    """온도가 다르면 캐시가 갈려야 한다. 안 그러면 결정적 실험이 예전
    무작위 응답을 그대로 집어온다.

    지정하지 않은 호출의 키는 예전과 같아야 한다 - 그래야 기존 cache/ 가
    한꺼번에 무효화되지 않는다.
    """
    from engine.generator import _cache_key

    plain = _cache_key("prompt", "source", "model")
    none_explicit = _cache_key("prompt", "source", "model", None)
    zero = _cache_key("prompt", "source", "model", 0.0)
    one = _cache_key("prompt", "source", "model", 1.0)

    assert plain == none_explicit
    assert zero != plain
    assert zero != one

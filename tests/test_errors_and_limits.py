"""모델 호출의 오류 표시와 호출 제한 검증. 네트워크는 쓰지 않는다.

- 화면에 띄우는 오류 문구에 공급자 오류 원문이 들어가면 안 된다. OpenAI
  인증 오류 원문에는 키 일부가 들어 있고, 공개 링크에서는 아무나 본다.
- 생성 호출에는 시간 제한과 출력 상한이 걸려야 하고, 같은 요청이 동시에
  오면 한 번만 호출해야 한다.
"""

import sys
import threading
import time
import types

import pytest

import engine.generator as generator
import service

LEAK = "Incorrect API key provided: sk-abc*****wxyz"


def _exc(*mro_names: str) -> Exception:
    """litellm 을 import 하지 않고 같은 이름의 예외 계층을 만든다."""
    base = Exception
    for name in reversed(mro_names):
        base = type(name, (base,), {})
    return base(LEAK)


@pytest.mark.parametrize(
    "mro, expected",
    [
        (("AuthenticationError", "APIStatusError"), "인증 실패"),
        (("RateLimitError", "APIStatusError"), "호출 한도 초과"),
        (("Timeout", "APITimeoutError", "APIConnectionError"), "응답 시간 초과"),
        (("APIConnectionError",), "연결 실패"),
        (("ContextWindowExceededError", "BadRequestError"), "입력이 너무 김"),
        (("UnsupportedParamsError", "BadRequestError"), "설정 오류"),
        (("NotFoundError",), "모델 없음"),
        (("SomethingNew",), "알 수 없는 오류"),
    ],
)
def test_api_errors_are_classified_without_the_raw_message(mro, expected) -> None:
    message = service.describe_api_error(_exc(*mro))
    assert message.startswith(expected)
    assert "sk-" not in message and LEAK not in message


@pytest.fixture
def fake_litellm(monkeypatch):
    calls = []

    def completion(**kwargs):
        calls.append(kwargs)
        time.sleep(0.2)  # 두 번째 호출이 첫 호출과 겹치게
        message = types.SimpleNamespace(content="output")
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message, finish_reason="stop")])

    monkeypatch.setitem(sys.modules, "litellm", types.SimpleNamespace(completion=completion))
    return calls


def test_generation_has_timeout_and_output_cap(fake_litellm, tmp_path) -> None:
    generator.generate_with_prompt("p", "s", "m", cache_dir=tmp_path)
    (call,) = fake_litellm
    assert call["timeout"] == generator.REQUEST_TIMEOUT_SECONDS
    assert call["max_tokens"] == generator.MAX_OUTPUT_TOKENS


def test_concurrent_identical_requests_call_once(fake_litellm, tmp_path) -> None:
    results = []
    threads = [
        threading.Thread(
            target=lambda: results.append(generator.generate_with_prompt("p", "s", "m", cache_dir=tmp_path))
        )
        for _ in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == ["output"] * 4
    assert len(fake_litellm) == 1


def test_different_requests_still_run_in_parallel(fake_litellm, tmp_path) -> None:
    """키마다 잠그므로 서로 다른 요청(A/B 후보)은 막히지 않는다."""
    start = time.monotonic()
    generator.generate_all_with_prompts(["p1", "p2", "p3"], "s", "m", cache_dir=tmp_path)
    assert time.monotonic() - start < 0.5
    assert len(fake_litellm) == 3

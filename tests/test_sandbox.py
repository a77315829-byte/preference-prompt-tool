"""agents/sandbox.py + code_validator.py 회귀 테스트 (절대 규칙 9).

에이전트가 만든 measure() 코드는 LLM 출력이다. 여기 있는 탈출 경로는
전부 실제로 검증을 통과해 부모 프로세스의 환경변수(= .env 의 API 키)를
읽어냈던 것들이다. 읽은 값은 int() 에러 메시지에 실려 나오고, 그 메시지는
재시도 프롬프트로 외부 LLM 에 전송된다. API 호출은 하지 않는다.
"""

import pytest

from agents.code_validator import ValidationError, validate_measure_code
from agents.sandbox import MeasureExecutionError, run_measure

SECRET = "sk-test-must-not-leak"


@pytest.fixture(autouse=True)
def fake_secret(monkeypatch):
    monkeypatch.setenv("FAKE_API_KEY", SECRET)


def test_plain_measure_still_runs() -> None:
    code = (
        "def measure(text, source):\n"
        "    words = re.findall(r'\\w+', text)\n"
        "    return statistics.mean([len(w) for w in words]) + math.log(1)\n"
    )
    assert run_measure(code, "ab abcd", "") == pytest.approx(3.0)


def test_collections_counter_still_usable() -> None:
    code = (
        "def measure(text, source):\n"
        "    return float(max(collections.Counter(text.split()).values()))\n"
    )
    assert run_measure(code, "a a b", "") == 2.0


ESCAPES = {
    "private module attribute": (
        "def measure(text, source):\n"
        "    return int(collections._sys.modules['os'].environ['FAKE_API_KEY'])\n"
    ),
    "public submodule attribute": (
        "def measure(text, source):\n"
        "    return int(statistics.sys.modules['os'].environ['FAKE_API_KEY'])\n"
    ),
    "str.format attribute traversal": (
        "def measure(text, source):\n"
        "    return int('{0.mean.__globals__[sys].modules[os].environ[FAKE_API_KEY]}'"
        ".format(statistics))\n"
    ),
    # submission 원본에서 실제로 os 함수 호출까지 성공했던 코드다.
    "generator frame walk": (
        "def measure(text, source):\n"
        "    def gen():\n"
        "        yield g.gi_frame.f_back.f_back.f_globals['sys'].modules['os']"
        ".environ['FAKE_API_KEY']\n"
        "    g = gen()\n"
        "    for v in g:\n"
        "        return int(v)\n"
    ),
}


# statistics.sys 는 이름만 보면 평범한 공개 속성이라 정적 검사로 거를 수
# 없다. 러너 이름공간에서 모듈을 빼는 쪽(2차 방어)이 막는다.
STATICALLY_REJECTED = [name for name in ESCAPES if name != "public submodule attribute"]


@pytest.mark.parametrize("name", STATICALLY_REJECTED)
def test_escape_is_rejected_statically(name) -> None:
    with pytest.raises(ValidationError):
        validate_measure_code(ESCAPES[name])


@pytest.mark.parametrize("name", list(ESCAPES))
def test_escape_does_not_leak_secret(name) -> None:
    with pytest.raises(MeasureExecutionError) as info:
        run_measure(ESCAPES[name], "a", "b")
    assert SECRET not in str(info.value)


def test_runner_namespace_has_no_modules() -> None:
    """정적 검증이 뚫린 경우의 2차 방어: 러너에 넘기는 멤버 중 모듈이 없어야
    한다. statistics.sys 같은 공개 속성은 이름만으로는 못 거른다."""
    import collections
    import math
    import re
    import statistics
    import types

    from agents.code_validator import MODULE_MEMBERS

    modules = {"re": re, "math": math, "statistics": statistics, "collections": collections}
    for name, members in MODULE_MEMBERS.items():
        for member in members:
            assert not isinstance(getattr(modules[name], member), types.ModuleType), f"{name}.{member}"


def test_child_process_gets_no_secrets() -> None:
    """3차 방어: 전부 뚫려도 자식 프로세스 환경에는 키가 없다."""
    from agents.sandbox import _child_env

    env = _child_env()
    assert "FAKE_API_KEY" not in env
    assert SECRET not in env.values()

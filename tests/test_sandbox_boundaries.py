"""Research runner regressions; no secrets, network or generated model calls."""
import pytest

from agents.code_validator import ValidationError, validate_measure_code
from agents.sandbox import MeasureExecutionError, run_measure


@pytest.mark.parametrize("expression", [
    "statistics.sys.version_info.major",
    "collections._sys.version_info.major",
    "re._compiler",
    '"{0.__class__}".format(text)',
    '"{x.__class__}".format_map({"x": text})',
])
def test_rejects_module_traversal_and_format_attribute_access(expression):
    with pytest.raises(ValidationError):
        validate_measure_code(f"def measure(text, source):\n    return {expression}")


def test_module_alias_does_not_expose_host_module():
    code = "def measure(text, source):\n    alias = statistics\n    return float(alias.sys.version_info.major)"
    with pytest.raises(MeasureExecutionError, match="AttributeError"):
        run_measure(code, "", "")


def test_supported_measurements_still_work():
    code = "def measure(text, source):\n    return statistics.mean([len(re.findall(r'\\w+', text)), math.sqrt(4)])"
    assert run_measure(code, "one two three four", "") == 3.0


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_rejects_nonfinite_measurement(value):
    with pytest.raises(MeasureExecutionError, match="finite"):
        run_measure(f"def measure(text, source):\n    return float('{value}')", "", "")


def test_timeout_remains_effective():
    with pytest.raises(MeasureExecutionError, match="타임아웃"):
        run_measure("def measure(text, source):\n    while True: pass", "", "", timeout=0.5)


def test_child_does_not_inherit_application_secrets(monkeypatch):
    from types import SimpleNamespace
    from agents import sandbox
    monkeypatch.setenv("REVIEW_TEST_SECRET", "synthetic-only")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-key-not-a-real-key")
    def run(command, **kwargs):
        assert "-I" in command
        assert "REVIEW_TEST_SECRET" not in kwargs["env"]
        assert "OPENAI_API_KEY" not in kwargs["env"]
        return SimpleNamespace(returncode=0, stdout='{"value": 1.0}', stderr="")
    monkeypatch.setattr(sandbox.subprocess, "run", run)
    assert run_measure("def measure(text, source):\n    return 1.0", "", "") == 1.0

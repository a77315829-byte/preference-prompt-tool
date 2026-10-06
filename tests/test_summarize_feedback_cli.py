"""scripts/summarize_feedback.py 의 --json 옵션 검증 (API 불필요)."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from feedback import FeedbackLog, summarize
from scripts import summarize_feedback as cli

ROOT = Path(__file__).resolve().parent.parent


def _lines_for(*calls):
    lines = []
    log = FeedbackLog(sink=lines.append, clock=lambda: "t")
    for kwargs in calls:
        log.record(**kwargs)
    return lines


def _make_lines():
    return _lines_for(
        dict(domain="summarization", fits=True),
        dict(domain="summarization", fits=False),
        dict(domain="coding", fits=True, comment="좋아요"),
        dict(domain="summarization", demo_mode=True, fits=True),
        dict(domain="x", fits=True, mode="expert", extra=dict(answers=12)),
        dict(domain="x", fits=False, mode="expert", extra=dict(answers=12)),
        dict(domain="x", fits=True, mode="expert", extra=dict(answers=30)),
        dict(domain="x", fits=True, mode="expert"),
    )


def _run(args, text, env=None):
    # 내용 비교가 목적이라 UTF-8 모드로 띄운다. 사람용 표 출력은 한국어 윈도우에서 예전처럼
    # cp949 로 나오므로(test_default_output_unchanged), 그대로 UTF-8 로 읽으면 깨진다.
    # --json 이 환경과 상관없이 UTF-8 인지는 test_json_is_utf8_without_utf8_mode 가 따로 본다.
    return subprocess.run(
        [sys.executable, "-m", "scripts.summarize_feedback", *args],
        input=text, capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
        env=env if env is not None else {**os.environ, "PYTHONUTF8": "1"},
    )


@pytest.fixture
def log_text():
    return "\n".join(_make_lines()) + "\n"


@pytest.fixture
def log_file(tmp_path, log_text):
    path = tmp_path / "sample.log"
    path.write_text(log_text, encoding="utf-8")
    return path


def test_json_is_single_document_and_stdin_matches_file(log_file, log_text):
    from_file = _run(["--json", str(log_file)], "")
    from_stdin = _run(["--json"], log_text)
    assert from_file.returncode == 0
    data = json.loads(from_file.stdout)  # AC-1: 전체가 JSON 하나
    assert data == json.loads(from_stdin.stdout)  # AC-9


def test_json_modes_match_summarize_and_table(log_file, log_text):
    data = json.loads(_run(["--json", str(log_file)], "").stdout)
    records = cli.parse_lines(log_text.splitlines())
    assert data["responses"] == 8
    assert data["modes"]["api"] == dict(total=3, yes=2, no=1, yes_rate=0.667)
    for mode, bucket in summarize(records).items():
        assert data["modes"][mode] == {k: bucket[k] for k in ("total", "yes", "no", "yes_rate")}
    # AC-2: 표의 같은 행과 일치
    table = _run([str(log_file)], "").stdout
    for mode, bucket in data["modes"].items():
        row = next(line for line in table.splitlines() if line.startswith(f"{mode:6} "))
        assert row.split() == [
            mode, str(bucket["total"]), str(bucket["yes"]), str(bucket["no"]),
            f"{bucket['yes_rate']:.0%}",
        ]


def test_json_api_by_domain_excludes_other_modes(log_file):
    data = json.loads(_run(["--json", str(log_file)], "").stdout)
    assert data["api_by_domain"] == dict(
        coding=dict(yes=1, no=0), summarization=dict(yes=1, no=1)
    )
    assert sum(b["yes"] + b["no"] for b in data["api_by_domain"].values()) == data["modes"]["api"]["total"]


def test_json_expert_buckets_missing_answers_count_as_under_30(log_file):
    data = json.loads(_run(["--json", str(log_file)], "").stdout)
    assert data["expert"] == {
        "under_30": dict(total=3, yes=2, yes_rate=0.667),
        "30_or_more": dict(total=1, yes=1, yes_rate=1.0),
    }
    table = _run([str(log_file)], "").stdout
    assert "30개 미만: 3건 중 맞다 2건 (67%)" in table
    assert "30개 이상: 1건 중 맞다 1건 (100%)" in table


def test_json_expert_empty_bucket_and_no_expert():
    lines = _lines_for(dict(domain="x", fits=True, mode="expert", extra=dict(answers=5)))
    data = json.loads(_run(["--json"], "\n".join(lines)).stdout)
    assert data["expert"]["30_or_more"] == dict(total=0, yes=0, yes_rate=None)
    lines = _lines_for(dict(domain="x", fits=True))
    data = json.loads(_run(["--json"], "\n".join(lines)).stdout)
    assert data["expert"] == {}


def test_json_has_no_merged_rate(log_file):
    data = json.loads(_run(["--json", str(log_file)], "").stdout)
    assert set(data) == {"responses", "modes", "api_by_domain", "expert"}


@pytest.mark.parametrize("text", ["", "아무 줄\n다른 줄\n"])
def test_json_empty_log(text):
    result = _run(["--json"], text)
    assert result.returncode == 0
    assert json.loads(result.stdout) == dict(
        responses=0, modes={}, api_by_domain={}, expert={}
    )


def test_json_truncated_line_goes_to_stderr_only(log_text):
    broken = log_text + 'USER_FEEDBACK {"at": "t", "mode": "ap\n'
    result = _run(["--json"], broken)
    assert "건너뜀" in result.stderr
    assert json.loads(result.stdout)["responses"] == 8


def test_default_output_unchanged(log_file, tmp_path):
    """AC-5: 변경 전 코드(HEAD)의 출력과 바이트까지 같다."""
    old = subprocess.run(
        ["git", "show", "HEAD:scripts/summarize_feedback.py"],
        capture_output=True, cwd=ROOT,
    )
    if old.returncode != 0:
        pytest.skip("git HEAD 에서 원본을 읽을 수 없다")
    # 원본은 부모 디렉터리를 sys.path 에 넣어 feedback 을 찾으므로 복사본 옆에 둔다.
    old_dir = tmp_path / "old" / "scripts"
    old_dir.mkdir(parents=True)
    (old_dir / "old_summarize.py").write_bytes(old.stdout)
    (tmp_path / "old" / "feedback.py").write_bytes((ROOT / "feedback.py").read_bytes())
    before = subprocess.run(
        [sys.executable, str(old_dir / "old_summarize.py"), str(log_file)],
        capture_output=True, cwd=tmp_path,
    )
    after = subprocess.run(
        [sys.executable, "-m", "scripts.summarize_feedback", str(log_file)],
        capture_output=True, cwd=ROOT,
    )
    assert before.returncode == 0
    assert after.stdout == before.stdout


def test_json_is_utf8_without_utf8_mode(log_text):
    """PYTHONUTF8 를 끈 한국어 윈도우에서도 --json 은 UTF-8 이다. 이것을 파이프로 받는 쪽은
    프로그램이고 UTF-8 JSON 을 기대한다. 고치기 전에는 cp949 로 나와 테스트 3개가 실패했다."""
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    result = _run(["--json"], log_text + 'USER_FEEDBACK {"at": "t", "mode": "ap\n', env=env)
    assert json.loads(result.stdout)["responses"] == 8
    assert "건너뜀" in result.stderr

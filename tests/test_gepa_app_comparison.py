"""experiments/gepa_app_comparison.py - 집계가 맞는지, 저장된 결과가 스스로 일관적인지.
API 는 부르지 않는다. 결과 파일이 없으면 결과 대조는 건너뛴다."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.gepa_app_comparison import OUT, summarize
from experiments.result_statistics import sign_test_p

ROOT = Path(__file__).resolve().parents[1]


def _row(persona, a_rouge, g_rouge, changed=True, learned=None):
    combo = {"length": "short", "extractiveness": "normal"}
    metrics = lambda r: {"rouge_l": r, "checks": 1.0, "length_ratio": 0.1, "prompt_words": 100}  # noqa: E731
    return {"persona": persona, "combo": combo, "learned": learned or combo,
            "prompt_changed": changed, "assembled": metrics(a_rouge), "app_gepa": metrics(g_rouge)}


def test_summary_counts_paired_wins_losses_and_ties() -> None:
    rows = [_row(0, 0.1, 0.2), _row(1, 0.3, 0.2), _row(2, 0.2, 0.2, changed=False),
            _row(3, 0.1, 0.3, learned={"length": "long", "extractiveness": "normal"})]
    s = summarize(rows)
    rouge = s["app_gepa_vs_assembled"]["rouge_l"]
    assert (rouge["wins"], rouge["losses"], rouge["ties"]) == (2, 1, 1)
    assert rouge["sign_test_p"] == round(sign_test_p(2, 3), 4)
    assert s["prompt_changed"] == 3 and s["estimate_exact"] == 3
    assert s["means"]["rouge_l"]["app_gepa"] == round((0.2 + 0.2 + 0.2 + 0.3) / 4, 4)


def test_recorded_results_match_their_own_summary() -> None:
    path = ROOT / OUT
    if not path.exists():
        pytest.skip("결과 파일이 없다")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["summary"] == summarize(data["rows"])
    # 같은 사람을 두 번 세지 않았다.
    assert len({r["persona"] for r in data["rows"]}) == len(data["rows"])
    # GEPA 가 바꾸지 않은 사람은 두 조건의 프롬프트가 같다.
    for r in data["rows"]:
        same = r["prompts"]["assembled"].strip() == r["prompts"]["app_gepa"].strip()
        assert same == (not r["prompt_changed"])

"""AWS 비용 보고가 실제로 정확한지 - 실제 모델 호출로 확인.

    python -m experiments.idle_tracker_accuracy

왜 필요한가: api_server.py 의 sourceText 가 "찾았으니 확인하세요" 한 줄
이었을 때는(2026-09-30 이전) 생성기가 실제 금액·리소스ID를 하나도 못
받았다 - 화면 카드에는 진짜 데이터가 있는데, 그걸 요약하는 모델만
못 보고 있었다. sourceText를 고친 뒤, 실제 API 호출로 4개 축조합을
돌려 checks/idle_tracker.py 의 total_cost_accuracy·no_fabrication 및
축 채점표(format·scope)가 실제 모델 출력에서도 통과하는지 확인한다.
offline 테스트(tests/test_idle_tracker_accuracy.py)는 결정적 데모 생성기만
검증했으므로 실제 모델의 행동은 따로 재야 한다.
"""

from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

from api_server import _demo_aws_cost_report
from checks.idle_tracker import format as check_format
from checks.idle_tracker import no_fabrication, scope, total_cost_accuracy
from engine.domain_loader import load_domain
from engine.generator import generate

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MODEL = "openai/gpt-4.1-mini"
OUT = Path("experiments/results/idle_tracker_accuracy.json")

COMBOS = [
    {"format": "bullet_list", "scope": "summary_brief"},
    {"format": "bullet_list", "scope": "deep_dive"},
    {"format": "markdown_table", "scope": "summary_brief"},
    {"format": "markdown_table", "scope": "deep_dive"},
]


def main() -> None:
    domain = load_domain("domains/idle_tracker.yaml")
    report = _demo_aws_cost_report()
    source_text = report["sourceText"]

    print("[생성기에 실제로 들어가는 sourceText]")
    print(source_text)
    print()

    rows = []
    for combo in COMBOS:
        output = generate(domain, source_text, combo, model=MODEL)
        cost_score, cost_note = total_cost_accuracy(output, report)
        fab_score, fab_note = no_fabrication(output, report)
        fmt_score, fmt_note = check_format(
            output, source_text, combo["format"], {"style": combo["format"]}
        )
        scp_score, scp_note = scope(
            output, source_text, combo["scope"], {"level": combo["scope"]}
        )
        rows.append({
            "combo": combo,
            "output": output,
            "total_cost_accuracy": cost_score,
            "total_cost_note": cost_note,
            "no_fabrication": fab_score,
            "fabrication_note": fab_note,
            "format_score": fmt_score,
            "format_note": fmt_note,
            "scope_score": scp_score,
            "scope_note": scp_note,
        })
        print(f"combo={combo}")
        print(f"  total_cost_accuracy={cost_score} ({cost_note})")
        print(f"  no_fabrication={fab_score} ({fab_note})")
        print(f"  format={fmt_score} ({fmt_note}) | scope={scp_score} ({scp_note})")
        print(f"  output: {output[:200]}")
        print()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    n = len(rows)
    cost_pass = sum(1 for r in rows if r["total_cost_accuracy"] == 1.0)
    fab_pass = sum(1 for r in rows if r["no_fabrication"] == 1.0)
    fmt_pass = sum(1 for r in rows if r["format_score"] == 1.0)
    scp_pass = sum(1 for r in rows if r["scope_score"] == 1.0)
    print(f"total_cost_accuracy 통과: {cost_pass}/{n}")
    print(f"no_fabrication 통과: {fab_pass}/{n}")
    print(f"format 채점 통과: {fmt_pass}/{n}")
    print(f"scope 채점 통과: {scp_pass}/{n}")
    print(f"저장: {OUT}")


if __name__ == "__main__":
    main()
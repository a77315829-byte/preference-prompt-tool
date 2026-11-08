"""저장된 실행 검증 결과를 현재 검사 코드로 다시 채점해 결과 필드가 같은지 대조한다. API 를 부르지 않는다.

    python -m benchmarks.coding_ai_quality.rescore_saved --reviewed

검사 코드(진입 파일 고르기, 실행 시나리오)를 고친 뒤 예전에 보고한 수치가 바뀌는지 확인하는 용도다.
비교하는 것은 typecheck / build / behavior / checks / equivalent(페르소나는 passed) 이다. 나중에 추가된
필드(entry 등)는 보지 않는다. 생성 코드를 로컬 Node 에서 다시 실행하므로 이미 검토한 원문에만 쓴다 (절대 규칙 9).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmarks.coding_ai_quality.evaluate_persona_poc import evaluate_saved
from benchmarks.coding_ai_quality.evaluate_trial import ROOT, evaluate

DATA = ROOT / "data"
FIELDS = ("typecheck", "build", "behavior", "checks")
# 이름 규칙(<x>_trial.json → <x>_evaluation.json / <x>_eval.json)을 따르지 않는 짝.
EXTRA_PAIRS = [("coding_ai_quality_trial.json", "coding_ai_quality_stage4.json"),
               ("coding_ai_cost_fixed_2026-10-15.json", "coding_ai_cost_fixed_2026-10-15_evaluation.json"),
               ("coding_ai_quality_holdout_v4_final_trial.json", "coding_stage3_2026-10-15_evaluation.json")]
PERSONA_PAIRS = [("coding_persona_live_2026-10-15.json", "coding_persona_evaluation_2026-10-15.json"),
                 ("coding_persona_repaired_2026-10-15.json", "coding_persona_repaired_evaluation_2026-10-15.json")]


def trial_pairs(data: Path = DATA) -> list[tuple[Path, Path]]:
    pairs = []
    for trial in sorted(data.glob("coding_ai_quality*_trial.json")):
        stem = trial.name[:-len("_trial.json")]
        pairs += [(trial, ev) for ev in (data / f"{stem}_evaluation.json", data / f"{stem}_eval.json") if ev.exists()]
    pairs += [(data / t, data / e) for t, e in EXTRA_PAIRS if (data / t).exists() and (data / e).exists()]
    return list(dict.fromkeys(pairs))


def trial_differences(old: list[dict], new: list[dict]) -> list[str]:
    if len(old) != len(new):
        return [f"result count {len(old)} -> {len(new)}"]
    diff = [f"{o['task']} {side}.{f}" for o, n in zip(old, new) for side in ("a", "b") for f in FIELDS
            if (o.get(side) or {}).get(f) != (n.get(side) or {}).get(f)]
    return diff + [f"{o['task']} equivalent" for o, n in zip(old, new) if o.get("equivalent") != n.get("equivalent")]


def persona_differences(old: dict, new: dict) -> list[str]:
    def key(report):
        return [(p["passed"], [(q["a"]["passed"], q["b"]["passed"]) for q in p["pairs"]], p["transfer"]["passed"])
                for p in report["personas"]]
    return [] if key(old) == key(new) and old["passed"] == new["passed"] else ["persona passed fields"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reviewed", action="store_true", required=True,
                        help="저장된 원문은 예전에 검토하고 실행한 것이다")
    parser.parse_args()
    report = []
    for trial, ev in trial_pairs():
        diff = trial_differences(json.loads(ev.read_text(encoding="utf-8"))["results"], evaluate(trial)["results"])
        report.append({"evaluation": ev.name, "same": not diff, "differences": diff})
    for src, ev in PERSONA_PAIRS:
        if (DATA / src).exists() and (DATA / ev).exists():
            diff = persona_differences(json.loads((DATA / ev).read_text(encoding="utf-8")), evaluate_saved(DATA / src))
            report.append({"evaluation": ev, "same": not diff, "differences": diff})
    for row in report:
        print("same" if row["same"] else f"DIFFERENT {row['differences'][:5]}", row["evaluation"])
    print(json.dumps({"checked": len(report), "different": sum(not r["same"] for r in report)}))


if __name__ == "__main__":
    main()

"""기본 조립본의 기능 저하가 선호 절에서 오는가, 나머지 틀에서 오는가 (4차 사전등록).

    # 1. 과제 고르기: 후보 v7 에서 (a)(b) 만 생성하고, 검토 뒤 실행 검사로 사전등록 규칙대로 5과제를 고른다
    python -m experiments.function_cost_comparison --phase select --execute --max-api-calls 40 --output-name fc_select
    python -m experiments.function_cost_comparison --phase select --cached-only --behavior --reviewed-outputs \\
        --output-name fc_select_behavior
    # 2. 확증: 고른 과제에서 (a)(b)(s), 고르기에 쓰지 않은 반복 3회
    python -m experiments.function_cost_comparison --phase confirm --tasks-from fc_select_behavior --execute \\
        --max-api-calls 90 --output-name fc_confirm
    python -m experiments.function_cost_comparison --phase confirm --tasks-from fc_select_behavior --cached-only \\
        --behavior --reviewed-outputs --output-name fc_confirm_behavior

조건
  (a) none           시스템 프롬프트 없음.
  (b) rule_based     서비스가 주는 기본 조립본.
  (s) scaffold_only  (b) 에서 선호 절(머리말부터 다음 머리말 전까지)만 뺀 것. 프로필과 무관하게 같다.

판정은 docs/function_cost_preregistration.md 의 기준을 그대로 계산한다. 가상 사용자·축 검사·실행 검사는
experiments/personalized_prompt_comparison.py 의 것을 쓴다. 이전 비교 스크립트와 결과는 바꾸지 않는다 (절대 규칙 10).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv

import service
from engine import generator
from experiments import personalized_prompt_comparison as base

ROOT = base.ROOT
POOL = ROOT / "benchmarks" / "coding_ai_quality" / "v7.json"
OUTPUT_DIR = ROOT / "data" / "function_cost_outputs"  # 검토용 원문. 커밋하지 않는다.
RESULTS = ROOT / "experiments" / "results"
PHASE_CONDITIONS = {"select": ("none", "rule_based"), "confirm": ("none", "rule_based", "scaffold_only")}
# 사전등록한 과제 고르기 규칙. 결과를 본 뒤 바꾸지 않는다.
SELECT_RANGE = (0.4, 0.85)    # (a)(b) 를 합친 기능 통과율이 이 범위(양끝 포함)인 과제만
SELECT_TARGET = 0.6           # 그중 이 값에 가까운 순서(같으면 v7 순서)로
SELECT_COUNT = 5              # 최대 이만큼
SELECT_MINIMUM = 3            # 이보다 적으면 확증을 돌리지 않는다
CONFIRM_REPEATS = 3
CONFIRM_REPEAT_OFFSET = 1     # 확증은 반복 1~3 을 쓴다 - 고르기에 쓴 반복 0 출력은 다시 쓰지 않는다
FROZEN_SOURCES = ["experiments/function_cost_comparison.py", "experiments/personalized_prompt_comparison.py",
                  "benchmarks/coding_ai_quality/evaluate_trial.py", "benchmarks/coding_ai_quality/runtime_check.cjs",
                  "benchmarks/coding_ai_quality/v7.json", "domains/coding.yaml", "checks/coding.py"]


def pool_tasks() -> list[dict]:
    return [t for t in json.loads(POOL.read_text(encoding="utf-8"))["tasks"] if t["split"] == "pool_v4"]


def scaffold_only(prompt: str, preference_heading: str) -> str:
    """선호 절을 통째로 뺀다. 머리말이 정확히 한 번 없으면 실험을 멈춘다."""
    marker = f"## {preference_heading}\n"
    if prompt.count(marker) != 1:
        raise ValueError("preference heading must appear exactly once")
    start = prompt.index(marker)
    end = prompt.find("\n## ", start + len(marker))
    if end == -1:
        raise ValueError("preference section must be followed by another heading")
    return prompt[:start] + prompt[end + 1:]


def build_prompts(profile: dict[str, str], source: str, rounds: int) -> tuple[dict[str, str], list]:
    state = base.simulate_history(profile, source, rounds)
    domain, estimator = service.current_estimate(state)
    rule_based = service.final_prompt(domain, estimator, language=None)
    return ({"none": "", "rule_based": rule_based,
             "scaffold_only": scaffold_only(rule_based, domain.final_prompt.preference_heading)}, state.history)


def worst_case(n_tasks: int, n_profiles: int, repeats: int, conditions: tuple[str, ...]) -> int:
    # (a)(s) 는 프로필과 무관하게 같은 입력이라 과제×반복만큼이다.
    shared = sum(c in ("none", "scaffold_only") for c in conditions)
    return n_tasks * repeats * (shared + n_profiles * ("rule_based" in conditions))


def _func(row: dict) -> float:
    return 1.0 if (row.get("behavior") or {}).get("functional_pass") is True else 0.0


def _axis(row: dict) -> float:
    axes = row["evaluation"]["axes"]
    return sum(a["passed"] for a in axes.values()) / len(axes)


def select(rows: list[dict], tasks: list[dict]) -> dict:
    """사전등록 규칙으로 확증 과제를 고른다."""
    rates = {}
    for task in tasks:
        # (a) 는 프로필마다 같은 출력이 한 줄씩 있다 - 한 번만 센다 (과제당 (a) 1 + (b) 프로필 수).
        outputs = [r for r in rows if r["task"] == task["id"] and r.get("behavior")
                   and (r["condition"] != "none" or r["profile"] == rows[0]["profile"])]
        rates[task["id"]] = round(sum(map(_func, outputs)) / len(outputs), 4) if outputs else None
    order = {t["id"]: i for i, t in enumerate(tasks)}
    eligible = [t for t, rate in rates.items() if rate is not None and SELECT_RANGE[0] <= rate <= SELECT_RANGE[1]]
    chosen = sorted(eligible, key=lambda t: (abs(rates[t] - SELECT_TARGET), order[t]))[:SELECT_COUNT]
    return {"pooled_functional_pass": rates, "eligible": eligible, "chosen": chosen,
            "enough": len(chosen) >= SELECT_MINIMUM}


def summarize(rows: list[dict]) -> dict:
    per_unit: dict[str, dict[str, dict]] = {}
    conditions = {}
    for condition in PHASE_CONDITIONS["confirm"]:
        outputs = [r for r in rows if r["condition"] == condition and r.get("evaluation")]
        functional = [(r.get("behavior") or {}).get("functional_pass") for r in outputs]
        evaluated = any(r.get("behavior") for r in outputs)
        conditions[condition] = {
            "outputs": len(outputs),
            "missing": sum(1 for r in rows if r["condition"] == condition and not r.get("evaluation")),
            "axis_pass_rate": round(sum(map(_axis, outputs)) / len(outputs), 4) if outputs else None,
            "functional_pass_rate": (round(sum(f is True for f in functional) / len(outputs), 4)
                                     if outputs and evaluated else None),
            "functional_unknown": sum(f is None for f in functional) if evaluated else None,
        }
        for r in outputs:
            per_unit.setdefault(f"{r['task']}#{r['profile']}#r{r['repeat']}", {})[condition] = r
    paired = {}
    for left, right in (("none", "rule_based"), ("scaffold_only", "rule_based"), ("none", "scaffold_only")):
        units = [u for u in per_unit.values() if left in u and right in u]
        functional = ([_func(u[right]) - _func(u[left]) for u in units]
                      if units and all(u[left].get("behavior") and u[right].get("behavior") for u in units) else [])
        style = [_axis(u[right]) - _axis(u[left]) for u in units]
        paired[f"{right}-{left}"] = {
            "units": len(units),
            "functional_diff": round(sum(functional) / len(functional), 4) if functional else None,
            "functional_diff_ci95": base._bootstrap_ci(functional),
            "axis_pass_diff": round(sum(style) / len(style), 4) if style else None,
            "axis_pass_diff_ci95": base._bootstrap_ci(style),
        }

    def below_zero(key):
        ci = paired[key]["functional_diff_ci95"]
        return None if ci is None else ci[1] < 0
    return {"conditions": conditions, "paired": paired,
            "findings": {"rule_based_costs_function": below_zero("rule_based-none"),
                         "preference_section_costs_function": below_zero("rule_based-scaffold_only"),
                         "scaffold_costs_function": below_zero("scaffold_only-none")}}


def run(*, phase: str, execute: bool, cached_only: bool, behavior: bool, reviewed_outputs: bool,
        max_api_calls: int, model: str, temperature: float | None, rounds: int,
        tasks_from: str | None = None) -> dict:
    if execute and cached_only:
        raise ValueError("--execute and --cached-only are exclusive")
    if behavior and not reviewed_outputs:
        raise ValueError("--behavior runs generated code; review data/function_cost_outputs first "
                         "and pass --reviewed-outputs")
    conditions = PHASE_CONDITIONS[phase]
    tasks = pool_tasks()
    selection = None
    if phase == "confirm":
        if not tasks_from:
            raise ValueError("--phase confirm needs --tasks-from <select result name>")
        selection = json.loads((RESULTS / f"{tasks_from}.json").read_text(encoding="utf-8"))["selection"]
        if not selection["enough"]:
            raise ValueError("selection found too few tasks; the preregistration says not to run the confirmation")
        tasks = [t for t in tasks if t["id"] in selection["chosen"]]
    repeats, offset = (1, 0) if phase == "select" else (CONFIRM_REPEATS, CONFIRM_REPEAT_OFFSET)
    profiles = base.PREREGISTERED_PROFILES
    plan = {"phase": phase, "tasks": [t["id"] for t in tasks], "conditions": list(conditions), "model": model,
            "repeats": list(range(offset, offset + repeats)), "temperature": temperature,
            "max_api_requests_worst_case": worst_case(len(tasks), len(profiles), repeats, conditions)}
    if cached_only:
        max_api_calls = 0
    elif execute and max_api_calls < plan["max_api_requests_worst_case"]:
        raise ValueError(f"--max-api-calls must be at least {plan['max_api_requests_worst_case']}")
    if not execute and not cached_only:
        return {"mode": "dry-run", "plan": plan}
    load_dotenv()
    usage = {"generation_requests": 0, "input_tokens": 0, "output_tokens": 0, "unknown_usage_requests": 0}
    original_call = generator._call_and_cache

    def bounded_call(*args, **kwargs):
        if usage["generation_requests"] >= max_api_calls:
            raise RuntimeError("API request limit reached")
        usage["generation_requests"] += 1
        import litellm
        completion = litellm.completion

        def measured(*call_args, **call_kwargs):
            call_kwargs["num_retries"] = 0
            response = completion(*call_args, **call_kwargs)
            tokens = getattr(response, "usage", None)
            if tokens is None:
                usage["unknown_usage_requests"] += 1
            else:
                usage["input_tokens"] += getattr(tokens, "prompt_tokens", 0) or 0
                usage["output_tokens"] += getattr(tokens, "completion_tokens", 0) or 0
            return response

        with patch.object(litellm, "completion", measured):
            return original_call(*args, **kwargs)

    rows, built = [], []
    generator._call_and_cache = bounded_call
    try:
        for profile in profiles:
            prompts, history = build_prompts(profile, tasks[0]["request"], rounds)
            label = base.profile_label(profile)
            built.append({"label": label, "profile": profile, "history": history, "prompts": prompts})
            for task in tasks:
                for repeat in range(offset, offset + repeats):
                    cache_dir = (generator.CACHE_DIR if repeat == 0
                                 else generator.CACHE_DIR / "ppc-repeats" / f"r{repeat}")
                    for condition in conditions:
                        row = {"task": task["id"], "condition": condition, "profile": label, "repeat": repeat}
                        before = usage["generation_requests"]
                        try:
                            output = generator.generate_with_prompt(prompts[condition], task["request"], model,
                                                                    cache_dir=cache_dir, temperature=temperature)
                        except Exception as exc:  # noqa: BLE001 - 공급자 문구·키는 남기지 않는다
                            rows.append({**row, "status": "not_cached" if cached_only
                                         else f"error ({type(exc).__name__})"})
                            continue
                        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                        (OUTPUT_DIR / f"{task['id']}__{condition}__{label}__r{repeat}.md").write_text(
                            output, encoding="utf-8")
                        row.update(status="generated", new_request=usage["generation_requests"] > before,
                                   evaluation=base.evaluate(output, task["request"], profile))
                        if behavior:
                            row["behavior"] = base.behavior_check(task["id"], output)
                        rows.append(row)
    finally:
        generator._call_and_cache = original_call
    report = {"mode": "cached-only" if cached_only else "execute", "phase": phase, "model": model,
              "temperature": temperature, "plan": plan, "profiles": built, "rows": rows, "usage": usage,
              "generated_at": datetime.now(timezone.utc).isoformat(),
              "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()[:16]
                                for name in FROZEN_SOURCES}}
    if phase == "select":
        report["selection"] = select(rows, pool_tasks()) if behavior else None
    else:
        report["selection_source"] = tasks_from
        report["summary"] = summarize(rows)
    return report


def markdown(report: dict) -> str:
    lines = [f"# 기능 저하 원인 비교 — {report['phase']} ({report['mode']})", "",
             f"- 생성: {report['generated_at']} · 모델 `{report['model']}` · 반복 {report['plan']['repeats']} · "
             f"temperature {report['temperature']}",
             f"- 사용량(공급자 보고, 청구서 아님): {json.dumps(report['usage'])}", ""]
    if report["phase"] == "select":
        sel = report.get("selection")
        if sel:
            lines += ["| 과제 | (a)(b) 합친 기능 통과율 | 고름 |", "|---|---|---|"]
            lines += [f"| {t} | {r} | {'예' if t in sel['chosen'] else ''} |"
                      for t, r in sel["pooled_functional_pass"].items()]
            lines += ["", f"- 규칙: 범위 {list(SELECT_RANGE)}, {SELECT_TARGET} 에 가까운 순, 최대 {SELECT_COUNT}개, "
                          f"{SELECT_MINIMUM}개 미만이면 확증 안 함 → 고른 과제 {sel['chosen']} (충분: `{sel['enough']}`)"]
        return "\n".join(lines) + "\n"
    s = report["summary"]
    lines += ["| 조건 | 출력 | 축 검사 통과율 | 기능 통과율 | 기능 미확인 |", "|---|---|---|---|---|"]
    lines += [f"| {c} | {v['outputs']} | {v['axis_pass_rate']} | {v['functional_pass_rate']} | {v['functional_unknown']} |"
              for c, v in s["conditions"].items()]
    lines += ["", "| 짝 | 단위 | 기능 차이 [95%] | 축 검사 차이 [95%] |", "|---|---|---|---|"]
    lines += [f"| {k} | {v['units']} | {v['functional_diff']} {v['functional_diff_ci95']} | "
              f"{v['axis_pass_diff']} {v['axis_pass_diff_ci95']} |" for k, v in s["paired"].items()]
    lines += ["", f"- 사전등록 판정: {json.dumps(s['findings'])}",
              "- (a)·(s) 는 프로필끼리 같은 출력을 공유해 단위가 독립이 아니다 - 구간은 실제보다 좁을 수 있다.",
              "- 정적 축 검사와 고정 시나리오는 기능 동일성이나 사용자 만족을 입증하지 않는다 (절대 규칙 11)."]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--phase", required=True, choices=list(PHASE_CONDITIONS))
    parser.add_argument("--tasks-from", default=None, help="고르기 실행 검사 결과 이름 (confirm 에 필요)")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--cached-only", action="store_true")
    parser.add_argument("--behavior", action="store_true")
    parser.add_argument("--reviewed-outputs", action="store_true")
    parser.add_argument("--max-api-calls", type=int, default=0)
    parser.add_argument("--model", default=base.DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--rounds", type=int, default=service.TOTAL_ROUNDS)
    parser.add_argument("--output-name", default=None, help="experiments/results/<이름>.{json,md}")
    args = parser.parse_args()
    if (args.execute or args.cached_only) and not args.output_name:
        parser.error("--output-name is required when results are written")
    started = time.monotonic()
    report = run(phase=args.phase, execute=args.execute, cached_only=args.cached_only, behavior=args.behavior,
                 reviewed_outputs=args.reviewed_outputs, max_api_calls=args.max_api_calls, model=args.model,
                 temperature=args.temperature, rounds=args.rounds, tasks_from=args.tasks_from)
    if report["mode"] == "dry-run":
        print(json.dumps(report["plan"], ensure_ascii=False, indent=2))
        print("dry-run: no API requests sent.")
        return
    report["usage"]["elapsed_seconds"] = round(time.monotonic() - started, 2)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / f"{args.output_name}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                                      encoding="utf-8")
    (RESULTS / f"{args.output_name}.md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))


if __name__ == "__main__":
    main()

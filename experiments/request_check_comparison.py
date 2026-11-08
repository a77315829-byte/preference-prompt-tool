"""기본 조립본이 요청 동작을 덜 지키는가, 요청 대조 규칙 한 줄이 그것을 되돌리는가 (3차 사전등록).

    python -m experiments.request_check_comparison                    # 사전 확인 (호출 0회)
    python -m experiments.request_check_comparison --execute --max-api-calls N
    python -m experiments.request_check_comparison --cached-only --behavior --reviewed-outputs

조건
  (a) none           시스템 프롬프트 없이 개발 요청만.
  (b) rule_based     선택 이력으로 조립한 최종 프롬프트 (서비스가 주는 것).
  (d) request_check  (b) 의 "항상 지킬 것" 맨 앞에 REQUEST_CHECK_RULE 한 줄을 더한 것. 나머지 글자는 같다.

판정은 docs/rule_based_function_preregistration.md 의 기준을 그대로 계산한다. 가상 사용자, 축 검사,
실행 검사(독립 지표)는 experiments/personalized_prompt_comparison.py 의 것을 그대로 쓴다. 생성된 코드를
로컬 Node 에서 실행하므로 원문을 먼저 검토하고 --reviewed-outputs 를 줘야 한다 (절대 규칙 9).
기존 비교 스크립트와 결과 파일은 바꾸지 않는다 (절대 규칙 10).
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
OUTPUT_DIR = ROOT / "data" / "request_check_outputs"  # 검토용 원문. 커밋하지 않는다.
RESULTS = ROOT / "experiments" / "results"
SPLITS = {"calibration": (ROOT / "benchmarks" / "coding_ai_quality" / "v1.json", "calibration"),
          "holdout_v3": (ROOT / "benchmarks" / "coding_ai_quality" / "v6.json", "holdout_v3")}
CONDITIONS = ("none", "rule_based", "request_check")
# 사전등록한 규칙 문구. 결과를 본 뒤 바꾸지 않는다.
REQUEST_CHECK_RULE = ("코드를 내기 전에 개발 요청에 따옴표로 적힌 화면 문구, 버튼 글자, 표시 형식을 하나씩 대조하라. "
                      "글자를 바꾸거나 덧붙이지 말고, 요청에 없는 라이브러리(예: styled-components)를 쓰지 마라.")
# 판정 기준 (사전등록 문서와 같은 값).
MIN_FUNCTIONAL_GAIN = 0.10   # (d)-(b) 기능 통과율 평균 차이의 하한, 95% 구간 하한 > 0 도 필요
MAX_STYLE_DROP = 0.05        # (d)-(b) 축 검사 통과율 차이의 하한 (비열등 한계)
FROZEN_SOURCES = ["experiments/request_check_comparison.py", "experiments/personalized_prompt_comparison.py",
                  "benchmarks/coding_ai_quality/evaluate_trial.py", "benchmarks/coding_ai_quality/runtime_check.cjs",
                  "benchmarks/coding_ai_quality/v6.json", "domains/coding.yaml", "checks/coding.py"]


def select_tasks(split: str) -> list[dict]:
    path, name = SPLITS[split]
    tasks = [t for t in json.loads(path.read_text(encoding="utf-8"))["tasks"] if t["split"] == name]
    if not tasks:
        raise ValueError(f"no {split} tasks")
    return tasks


def with_request_check(prompt: str, rules_heading: str) -> str:
    """규칙 머리말 바로 아래 첫 줄로 끼운다. 머리말이 정확히 한 번 없으면 실험을 멈춘다."""
    marker = f"## {rules_heading}\n"
    if prompt.count(marker) != 1:
        raise ValueError("rules heading must appear exactly once")
    return prompt.replace(marker, f"{marker}- {REQUEST_CHECK_RULE}\n")


def build_prompts(profile: dict[str, str], source: str, rounds: int) -> tuple[dict[str, str], list]:
    state = base.simulate_history(profile, source, rounds)
    domain, estimator = service.current_estimate(state)
    rule_based = service.final_prompt(domain, estimator, language=None)
    return ({"none": "", "rule_based": rule_based,
             "request_check": with_request_check(rule_based, domain.final_prompt.rules_heading)}, state.history)


def worst_case(n_tasks: int, n_profiles: int, repeats: int) -> int:
    # (a) 는 프로필과 무관하게 같은 입력이라 과제×반복만큼이다.
    return n_tasks * repeats * (1 + 2 * n_profiles)


def summarize(rows: list[dict]) -> dict:
    per_unit: dict[str, dict[str, dict]] = {}
    conditions = {}
    for condition in CONDITIONS:
        outputs = [r for r in rows if r["condition"] == condition and r.get("evaluation")]
        functional = [(r.get("behavior") or {}).get("functional_pass") for r in outputs]
        evaluated = any(r.get("behavior") for r in outputs)
        conditions[condition] = {
            "outputs": len(outputs),
            "missing": sum(1 for r in rows if r["condition"] == condition and not r.get("evaluation")),
            "axis_pass_rate": round(sum(_axis(r) for r in outputs) / len(outputs), 4) if outputs else None,
            "functional_pass_rate": (round(sum(f is True for f in functional) / len(outputs), 4)
                                     if outputs and evaluated else None),
            "functional_unknown": sum(f is None for f in functional) if evaluated else None,
        }
        for r in outputs:
            per_unit.setdefault(f"{r['task']}#{r['profile']}#r{r['repeat']}", {})[condition] = r
    paired = {}
    for left, right in (("rule_based", "request_check"), ("none", "rule_based")):
        units = [u for u in per_unit.values() if left in u and right in u]
        style = [_axis(u[right]) - _axis(u[left]) for u in units]
        functional = ([_func(u[right]) - _func(u[left]) for u in units]
                      if units and all(u[left].get("behavior") and u[right].get("behavior") for u in units) else [])
        paired[f"{right}-{left}"] = {
            "units": len(units),
            "axis_pass_diff": round(sum(style) / len(style), 4) if style else None,
            "axis_pass_diff_ci95": base._bootstrap_ci(style),
            "functional_diff": round(sum(functional) / len(functional), 4) if functional else None,
            "functional_diff_ci95": base._bootstrap_ci(functional),
        }
    gain, drop = paired["request_check-rule_based"], paired["rule_based-none"]
    criteria = {
        "functional_gain": (None if gain["functional_diff"] is None else
                            gain["functional_diff"] >= MIN_FUNCTIONAL_GAIN and gain["functional_diff_ci95"][0] > 0),
        "style_non_inferior": None if gain["axis_pass_diff"] is None else gain["axis_pass_diff"] >= -MAX_STYLE_DROP,
    }
    return {"conditions": conditions, "paired": paired, "criteria": criteria,
            "all_criteria_met": None if None in criteria.values() else all(criteria.values()),
            # 보고용 (판정 아님): 기본 조립본의 기능 저하가 새 과제에서도 나타나는가.
            "rule_based_functional_drop_replicated": (None if drop["functional_diff"] is None
                                                      else drop["functional_diff_ci95"][1] < 0),
            "thresholds": {"min_functional_gain": MIN_FUNCTIONAL_GAIN, "max_style_drop": MAX_STYLE_DROP}}


def _axis(row: dict) -> float:
    axes = row["evaluation"]["axes"]
    return sum(a["passed"] for a in axes.values()) / len(axes)


def _func(row: dict) -> float:
    return 1.0 if (row.get("behavior") or {}).get("functional_pass") is True else 0.0


def markdown(report: dict) -> str:
    s = report["summary"]
    role = ("확증(판정에 쓴다)" if report["split"] == "holdout_v3" and report["mode"] != "dry-run"
            else "판정에 쓰지 않는다 (pilot)")
    lines = [f"# 요청 대조 규칙 비교 ({report['split']}) — {role}", "",
             f"- 생성: {report['generated_at']} · 모드 `{report['mode']}` · 모델 `{report['model']}` · "
             f"반복 {report['repeats']} · temperature {report['temperature']}",
             f"- 추가 규칙: {REQUEST_CHECK_RULE}", "",
             "| 조건 | 출력 | 축 검사 통과율 | 기능 통과율 | 기능 미확인 |", "|---|---|---|---|---|"]
    for c, v in s["conditions"].items():
        lines.append(f"| {c} | {v['outputs']} | {v['axis_pass_rate']} | {v['functional_pass_rate']} | "
                     f"{v['functional_unknown']} |")
    lines += ["", "| 짝 | 단위 | 축 검사 차이 [95%] | 기능 차이 [95%] |", "|---|---|---|---|"]
    for k, v in s["paired"].items():
        lines.append(f"| {k} | {v['units']} | {v['axis_pass_diff']} {v['axis_pass_diff_ci95']} | "
                     f"{v['functional_diff']} {v['functional_diff_ci95']} |")
    lines += ["", f"- 사전등록 기준: {json.dumps(s['criteria'])} → 전부 충족: `{s['all_criteria_met']}`",
              f"- (보고용) 기본 조립본 기능 저하 재현: `{s['rule_based_functional_drop_replicated']}`",
              f"- 사용량(공급자 보고, 청구서 아님): {json.dumps(report['usage'])}",
              "- 정적 축 검사와 과제별 고정 시나리오는 기능 동일성이나 사용자 만족을 입증하지 않는다. "
              "과제·프로필 단위의 작은 차이는 결론으로 쓰지 않는다 (절대 규칙 11)."]
    return "\n".join(lines) + "\n"


def run(*, split: str, execute: bool, cached_only: bool, behavior: bool, reviewed_outputs: bool,
        max_api_calls: int, model: str, repeats: int, temperature: float | None, rounds: int) -> dict:
    if execute and cached_only:
        raise ValueError("--execute and --cached-only are exclusive")
    if behavior and not reviewed_outputs:
        raise ValueError("--behavior runs generated code; review data/request_check_outputs first "
                         "and pass --reviewed-outputs")
    tasks = select_tasks(split)
    profiles = base.PREREGISTERED_PROFILES
    plan = {"split": split, "tasks": [t["id"] for t in tasks], "conditions": list(CONDITIONS), "model": model,
            "profiles": profiles, "repeats": repeats, "temperature": temperature,
            "max_api_requests_worst_case": worst_case(len(tasks), len(profiles), repeats)}
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
                for repeat in range(repeats):
                    # 1·2차 비교와 같은 캐시 배치: 반복마다 폴더를 나눈다 (0 번은 기본 캐시).
                    cache_dir = (generator.CACHE_DIR if repeat == 0
                                 else generator.CACHE_DIR / "ppc-repeats" / f"r{repeat}")
                    for condition in CONDITIONS:
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
    return {"mode": "cached-only" if cached_only else "execute", "split": split, "model": model,
            "repeats": repeats, "temperature": temperature, "plan": plan, "profiles": built, "rows": rows,
            "summary": summarize(rows), "usage": usage,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()[:16]
                              for name in FROZEN_SOURCES}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", default="calibration", choices=list(SPLITS))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--cached-only", action="store_true")
    parser.add_argument("--behavior", action="store_true")
    parser.add_argument("--reviewed-outputs", action="store_true")
    parser.add_argument("--max-api-calls", type=int, default=0)
    parser.add_argument("--model", default=base.DEFAULT_MODEL)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--rounds", type=int, default=service.TOTAL_ROUNDS)
    parser.add_argument("--output-name", default=None, help="experiments/results/<이름>.{json,md}")
    args = parser.parse_args()
    if (args.execute or args.cached_only) and not args.output_name:
        parser.error("--output-name is required when results are written")
    started = time.monotonic()
    report = run(split=args.split, execute=args.execute, cached_only=args.cached_only, behavior=args.behavior,
                 reviewed_outputs=args.reviewed_outputs, max_api_calls=args.max_api_calls, model=args.model,
                 repeats=args.repeats, temperature=args.temperature, rounds=args.rounds)
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

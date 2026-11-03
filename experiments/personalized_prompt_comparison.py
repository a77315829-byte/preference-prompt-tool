"""개인화 프롬프트 없음 / 기본 조립 / AI 개선 - 세 조건을 같은 기능·모델·검사로 비교한다.

    python -m experiments.personalized_prompt_comparison              # 사전 확인 (호출 0회)
    python -m experiments.personalized_prompt_comparison --execute    # 실제 호출 (상한 안에서)
    python -m experiments.personalized_prompt_comparison --cached-only --behavior --reviewed-outputs
                                                                      # 호출 0회, 캐시된 출력만 실행 검사

조건
  (a) none        시스템 프롬프트 없이 개발 요청만 보낸다.
  (b) rule_based  선택 이력에서 추정한 선호를 정해진 문구로 조립한 최종 프롬프트.
  (c) ai_improved 같은 이력·추정으로 service.complete_personalized_prompt 가 만든 개선본.
                  개선이 실패하면(fallback) 기본은 (c) 를 측정하지 않고 그렇다고 기록한다.
                  --fallback-as-base 면 서비스와 똑같이 기본 조립본을 (c) 로 쓴다 (사전등록 설계).

선택 이력은 사람 대신 목표 선호(--profile)를 가진 가상 사용자가 데모 후보로 만든다 - 후보
생성에 API 를 쓰지 않는다. 검사는 도메인 YAML 이 각 축 값에 지정한 함수(checks.coding)와
그 원 신호 수(파일 수, 테마 신호, 타입 신호)다.

독립 지표(절대 규칙 7): --behavior 를 주면 benchmarks/coding_ai_quality/evaluate_trial 의 기존 실행
검사(tsc 타입 검사 → esbuild 번들 → jsdom 에서 과제의 고정 인수 시나리오)를 같은 출력에 돌린다.
스타일 검사·GEPA 와는 다른 기준이다. **생성된 코드를 로컬 Node 에서 실행한다** - 보안 샌드박스가
아니다. 그래서 출력 원문을 data/ 에 먼저 남기고, 검토했다는 --reviewed-outputs 없이는 실행하지
않는다 (절대 규칙 9).

이 비교가 말하지 않는 것: 정적 검사 통과는 기능이 같다거나 사용자가 만족한다는 증거가 아니다.
과제 수가 적으면 차이는 사례일 뿐이다 (CLAUDE.md 절대 규칙 11). 결과 파일에 그대로 적는다.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv

import service
from engine import generator
from engine.domain_loader import load_domain

ROOT = Path(__file__).resolve().parents[1]
DOMAIN_PATH = ROOT / "domains" / "coding.yaml"
BENCHMARK = ROOT / "benchmarks" / "coding_ai_quality" / "v1.json"
OUTPUT_JSON = ROOT / "experiments" / "results" / "personalized_prompt_comparison.json"
OUTPUT_MD = ROOT / "experiments" / "results" / "personalized_prompt_comparison.md"
# 캐시 재생(--cached-only) 결과. 실제 호출 결과 파일을 덮어쓰지 않는다.
CACHED_JSON = ROOT / "experiments" / "results" / "personalized_prompt_comparison_cached.json"
CACHED_MD = ROOT / "experiments" / "results" / "personalized_prompt_comparison_cached.md"
RECORD_DIR = ROOT / "data" / "personalized_prompt_comparison_records"
OUTPUT_DIR = ROOT / "data" / "personalized_prompt_comparison_outputs"  # 검토용 원문. 커밋하지 않는다.
DEFAULT_MODEL = "openai/gpt-4o-mini"  # api_server.DEFAULT_MODEL 의 기본값과 같다.
DEFAULT_PROFILE = {"code_structure": "separated", "style_management": "theme", "type_detail": "explicit"}
# docs/personalized_prompt_preregistration.md 의 고정 설계. 각 축의 두 값이 모두 두 번씩 목표가 된다.
PREREGISTERED_PROFILES = [
    DEFAULT_PROFILE,
    {"code_structure": "compact", "style_management": "direct", "type_detail": "inferred"},
    {"code_structure": "compact", "style_management": "theme", "type_detail": "inferred"},
    {"code_structure": "separated", "style_management": "direct", "type_detail": "explicit"},
]
BENCHMARKS = [ROOT / "benchmarks" / "coding_ai_quality" / f"v{n}.json" for n in (1, 2, 3, 4)]
# 판정 기준 (사전등록 문서와 같은 값). 결과를 본 뒤 바꾸지 않는다.
MIN_STYLE_GAIN = 0.10          # (c)-(b) 축 검사 통과율 평균 차이의 하한
MAX_FUNCTIONAL_DROP = 0.05     # (b)-(c) 기능 통과율 차이의 상한 (비열등 한계)
MAX_FALLBACK_RATE = 0.25       # 프로필 중 개선이 적용되지 않은 비율의 상한
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 0
CONDITIONS = ("none", "rule_based", "ai_improved")
NOTE = ("Style checks are static. The independent behavior check covers only the task's frozen "
        "acceptance scenario; neither shows functional equivalence on all inputs or user satisfaction. "
        "With few tasks, differences are anecdotes.")


def profile_label(profile: dict[str, str]) -> str:
    return "-".join(profile[k] for k in sorted(profile))


def select_tasks(split: str, limit: int | None = None) -> list[dict]:
    """calibration 은 v1 의 네 과제, holdout 은 v1~v4 의 보류 과제 전부(실행 시나리오가 있는 것)."""
    if split not in ("calibration", "holdout"):
        raise ValueError("split must be calibration or holdout")
    paths = BENCHMARKS[:1] if split == "calibration" else BENCHMARKS
    tasks, seen = [], set()
    for path in paths:
        for task in json.loads(path.read_text(encoding="utf-8"))["tasks"]:
            if task["split"] == split and task["id"] not in seen:
                seen.add(task["id"])
                tasks.append(task)
    if limit is not None:
        tasks = tasks[:limit]
    if not tasks:
        raise ValueError(f"no {split} tasks selected")
    return tasks


def simulate_history(profile: dict[str, str], source: str, rounds: int) -> service.SessionState:
    """목표 선호와 맞는 축이 더 많은 쪽을 고르는 가상 사용자. 같으면 '비슷해요'."""
    state = service.start_session(source, "coding", str(DOMAIN_PATH), model="demo", demo_mode=True,
                                  total_rounds=rounds)
    while not state.done:
        a, b = state.pair.a.combo, state.pair.b.combo
        score_a = sum(a.get(k) == v for k, v in profile.items())
        score_b = sum(b.get(k) == v for k, v in profile.items())
        chosen = "a" if score_a > score_b else "b" if score_b > score_a else "tie"
        state = service.submit_choice(state, state.pair.pair_id, chosen)
    return state


def build_prompts(history_state: service.SessionState, model: str, language: str, *,
                  execute: bool, reserve) -> tuple[dict[str, str | None], dict]:
    """(a)(b)(c) 의 시스템 프롬프트와 개선 단계 메타데이터. 사전 확인에서는 (c) 를 만들지 않는다."""
    domain, estimator = service.current_estimate(history_state)
    base = service.final_prompt(domain, estimator, language=None if language == "ko" else language)
    prompts: dict[str, str | None] = {"none": "", "rule_based": base, "ai_improved": None}
    if not execute:
        return prompts, {"method": "not_run", "reason": "dry_run"}
    live = replace(history_state, demo_mode=False, model=model)
    # 서비스 기본값(PPT_PROMPT_IMPROVEMENT)과 무관하게 (c) 를 만든다 - 이 비교가 그 기본값을 정할 근거다.
    done = service.complete_personalized_prompt(live, [language], before_call=reserve, record_dir=RECORD_DIR,
                                                enabled=True)
    meta = {k: v for k, v in done.prompt_improvement.items() if k != "base_prompts"}
    if meta["method"] == "ai_improved":
        prompts["ai_improved"] = done.personalized_prompts[language]
    return prompts, meta


def evaluate(output: str, source: str, profile: dict[str, str]) -> dict:
    """도메인이 지정한 축별 검사 + 그 원 신호 수."""
    domain = load_domain(DOMAIN_PATH)
    checks = importlib.import_module(domain.checks_module)
    axes = {}
    for axis, value in profile.items():
        spec = domain.axis(axis).check_for(value)
        score, feedback = getattr(checks, spec.fn)(output, source, value, spec.target)
        axes[axis] = {"value": value, "check": spec.fn, "score": round(float(score), 3),
                      "passed": score >= 1.0, "feedback": feedback}
    return {
        "axes": axes,
        "all_passed": all(item["passed"] for item in axes.values()),
        "signals": {"files": checks.count_files(output),
                    "theme_signals": checks.count_theme_signals(output),
                    "type_signals": checks.count_type_signals(output)},
        "quality_issues": checks.candidate_quality_issues(output, profile, source),
    }


def behavior_check(task_id: str, output: str) -> dict:
    """기존 실행 검사를 그대로 쓴다. 시나리오가 없는 과제나 파일을 못 뽑은 출력은 통과로 세지 않는다."""
    import tempfile
    from benchmarks.coding_ai_quality.evaluate_trial import ENTRY, FRONTEND, evaluate_candidate
    if task_id not in ENTRY:
        return {"functional_pass": None, "behavior": "unknown", "reason": "no_scenario"}
    # 기존 추출기는 tsx/ts/css 코드 블록만 읽는다. ```typescript 표기만 tsx 로 맞추고 그 사실을 남긴다.
    normalized = re.sub(r"```typescript\b", "```tsx", output)
    with tempfile.TemporaryDirectory(prefix=".ppc-eval-", dir=FRONTEND) as temp:
        try:
            result = evaluate_candidate(task_id, normalized, "-", Path(temp))
        except ValueError as exc:
            # 파일 이름·확장자를 확정하지 못했다. 실행하지 못한 것이므로 실패가 아니라 미확인이다.
            return {"functional_pass": None, "behavior": "not_run", "fence_normalized": normalized != output,
                    "reason": f"extract_failed: {exc}"[:200]}
    return {"fence_normalized": normalized != output,
            "functional_pass": result["typecheck"] and result["build"] and result["behavior"] == "passed",
            "typecheck": result["typecheck"], "build": result["build"], "behavior": result["behavior"],
            "checks": result["checks"], "files": result["files"],
            "typecheck_output": result["typecheck_output"][:600], "build_output": result["build_output"][:300]}


def _unit(row: dict) -> str:
    return f"{row['task']}#{row.get('profile', '-')}#r{row.get('repeat', 0)}"


def differences(rows: list[dict]) -> list[str]:
    """조건 사이에 달라진 항목. 없으면 '차이 없음'을 그대로 적는다."""
    notes = []
    by_unit: dict[str, dict[str, dict]] = {}
    for row in rows:
        if row.get("evaluation"):
            by_unit.setdefault(_unit(row), {})[row["condition"]] = {
                **row["evaluation"], "functional": (row.get("behavior") or {}).get("functional_pass", "not_run")}
    for unit, evals in by_unit.items():
        for left, right in (("none", "rule_based"), ("rule_based", "ai_improved"), ("none", "ai_improved")):
            if left not in evals or right not in evals:
                continue
            changed = [f"{axis}: {evals[left]['axes'][axis]['passed']}→{evals[right]['axes'][axis]['passed']}"
                       for axis in evals[left]["axes"]
                       if evals[left]["axes"][axis]["passed"] != evals[right]["axes"][axis]["passed"]]
            signals = [f"{k}: {evals[left]['signals'][k]}→{evals[right]['signals'][k]}"
                       for k in evals[left]["signals"] if evals[left]["signals"][k] != evals[right]["signals"][k]]
            fl, fr = evals[left]["functional"], evals[right]["functional"]
            label = unit.split("#")[0] if unit.endswith("#-#r0") else unit
            notes.append(f"{label} {left} vs {right}: "
                         + ("검사 통과 차이 없음" if not changed else "검사 통과 변화 " + ", ".join(changed))
                         + "; " + ("신호 수 차이 없음" if not signals else "신호 " + ", ".join(signals))
                         + "; " + (f"실행 검사 차이 없음 ({fl})" if fl == fr else f"실행 검사 {fl}→{fr}"))
    return notes


def _bootstrap_ci(values: list[float]) -> tuple[float, float] | None:
    """단위(프로필×과제×반복)를 복원추출한 평균의 95% 구간. 고정 시드라 다시 계산해도 같다."""
    import random
    if not values:
        return None
    rng = random.Random(BOOTSTRAP_SEED)
    means = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(BOOTSTRAP_RESAMPLES))
    return round(means[int(0.025 * len(means))], 4), round(means[int(0.975 * len(means)) - 1], 4)


def summarize(rows: list[dict], profiles: list[dict]) -> dict:
    """조건별 통과율, 짝지은 차이와 구간, 사전등록 기준의 기계적 판정."""
    per_unit: dict[str, dict[str, dict]] = {}
    conditions = {}
    for condition in CONDITIONS:
        outputs = [r for r in rows if r["condition"] == condition and r.get("evaluation")]
        functional = [(r.get("behavior") or {}).get("functional_pass") for r in outputs]
        evaluated = any(r.get("behavior") for r in outputs)
        conditions[condition] = {
            "outputs": len(outputs),
            "missing": sum(1 for r in rows if r["condition"] == condition and not r.get("evaluation")),
            "axis_pass_rate": round(sum(sum(a["passed"] for a in r["evaluation"]["axes"].values())
                                        / len(r["evaluation"]["axes"]) for r in outputs) / len(outputs), 4)
                              if outputs else None,
            "all_axes_pass_rate": round(sum(r["evaluation"]["all_passed"] for r in outputs) / len(outputs), 4)
                                  if outputs else None,
            # 미확인(None)은 분모에 남기고 통과로 세지 않는다.
            "functional_pass_rate": round(sum(f is True for f in functional) / len(outputs), 4)
                                    if outputs and evaluated else None,
            "functional_unknown": sum(f is None for f in functional) if evaluated else None,
        }
        for r in outputs:
            per_unit.setdefault(_unit(r), {})[condition] = r

    def axis_rate(r):
        return sum(a["passed"] for a in r["evaluation"]["axes"].values()) / len(r["evaluation"]["axes"])

    def func(r):
        return 1.0 if (r.get("behavior") or {}).get("functional_pass") is True else 0.0

    paired = {}
    for left, right in (("rule_based", "ai_improved"), ("none", "rule_based")):
        units = [u for u in per_unit.values() if left in u and right in u]
        style = [axis_rate(u[right]) - axis_rate(u[left]) for u in units]
        functional = ([func(u[right]) - func(u[left]) for u in units]
                      if all(u[left].get("behavior") and u[right].get("behavior") for u in units) else [])
        paired[f"{right}-{left}"] = {
            "units": len(units),
            "axis_pass_diff": round(sum(style) / len(style), 4) if style else None,
            "axis_pass_diff_ci95": _bootstrap_ci(style),
            "functional_diff": round(sum(functional) / len(functional), 4) if functional else None,
            "functional_diff_ci95": _bootstrap_ci(functional),
        }
    applied = sum(1 for p in profiles if (p.get("improvement") or {}).get("method") in ("ai_improved", "replayed"))
    fallback_rate = round(1 - applied / len(profiles), 4) if profiles else None
    gain = paired["ai_improved-rule_based"]
    criteria = {
        "style_gain": (gain["axis_pass_diff"] is not None and gain["axis_pass_diff"] >= MIN_STYLE_GAIN
                       and gain["axis_pass_diff_ci95"][0] > 0),
        "functional_non_inferior": (None if gain["functional_diff"] is None
                                    else gain["functional_diff"] >= -MAX_FUNCTIONAL_DROP),
        "fallback_rate": fallback_rate is not None and fallback_rate <= MAX_FALLBACK_RATE,
    }
    met = None if None in criteria.values() else all(criteria.values())
    return {"conditions": conditions, "paired": paired, "fallback_rate": fallback_rate,
            "criteria": criteria, "all_criteria_met": met,
            "thresholds": {"min_style_gain": MIN_STYLE_GAIN, "max_functional_drop": MAX_FUNCTIONAL_DROP,
                           "max_fallback_rate": MAX_FALLBACK_RATE}}


def behavior_cells(b: dict | None) -> str:
    if not b:
        return "미실행 | 미실행 | 미실행 | 미실행 |"
    mark = lambda v: "✅" if v is True else "❌" if v is False else "미확인"
    checks = b.get("checks") or []
    scenario = f"{b['behavior']} ({sum(map(bool, checks))}/{len(checks)})" if checks else b["behavior"]
    return (f"{mark(b.get('typecheck'))} | {mark(b.get('build'))} | {scenario} | "
            f"{mark(b.get('functional_pass'))} |")


def markdown(report: dict) -> str:
    profiles = report.get("profiles") or [{
        "label": "-", "profile": report["profile"], "improvement": report["improvement"],
        "ai_prompt_identical_to_base": report.get("ai_prompt_identical_to_base")}]
    lines = [
        "# 개인화 프롬프트 3조건 비교", "",
        f"- 생성: {report['generated_at']} · 모드: `{report['mode']}` · 모델: `{report['model']}`"
        f" · 언어: `{report['language']}`"
        + (f" · split `{report['split']}` · 반복 {report['repeats']} · temperature {report['temperature']}"
           if report.get("split") else ""),
    ]
    for item in profiles:
        imp = item["improvement"]
        lines.append(
            f"- 목표 선호 `{json.dumps(item['profile'], ensure_ascii=False)}` → 개선 단계 `{imp['method']}`"
            + (f" (reason `{imp.get('reason')}`)" if imp.get("reason") else "")
            + (" · (b) 와 문구 같음" if item.get("ai_prompt_identical_to_base") else "")
            + (f" · (c) 출처 `{item['ai_prompt_source']}`" if item.get("ai_prompt_source") else ""))
    lines += [
        f"- 새 API 요청: 생성 {report['usage']['generation_requests']}회, 개선 {report['usage']['improvement_requests']}회"
        f" · 토큰(공급자 보고, 청구서 아님) 입력 {report['usage']['input_tokens']} / 출력 {report['usage']['output_tokens']}"
        f" · 경과 {report['usage']['elapsed_seconds']}초",
        f"- 주의: {report['note']}", "",
        "| 과제 | 조건 | 파일 구성 | 스타일 관리 | 타입 작성 | 스타일 전부 | 파일 수 | 테마 신호 | 타입 신호 | 품질 문제 "
        "| 타입 검사 | 빌드 | 동작 시나리오 | 기능 통과(독립) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in report["rows"]:
        name = row["task"] if "profile" not in row else f"{row['task']} · {row['profile']} · r{row['repeat']}"
        e = row.get("evaluation")
        if not e:
            lines.append(f"| {name} | {row['condition']} | - | - | - | - | - | - | - | {row['status']} "
                         "| - | - | - | - |")
            continue
        cell = lambda axis: f"{'✅' if e['axes'][axis]['passed'] else '❌'} {e['axes'][axis]['score']}"
        lines.append(
            f"| {name} | {row['condition']} | {cell('code_structure')} | {cell('style_management')} | "
            f"{cell('type_detail')} | {'예' if e['all_passed'] else '아니오'} | {e['signals']['files']} | "
            f"{e['signals']['theme_signals']} | {e['signals']['type_signals']} | {len(e['quality_issues'])} | "
            + behavior_cells(row.get("behavior")))
    summary = report.get("summary")
    if summary:
        lines += ["", "## 집계", "", "| 조건 | 출력 | 누락 | 축 통과율 | 세 축 전부 | 기능 통과율 | 기능 미확인 |",
                  "|---|---|---|---|---|---|---|"]
        for name, c in summary["conditions"].items():
            lines.append(f"| {name} | {c['outputs']} | {c['missing']} | {c['axis_pass_rate']} | "
                         f"{c['all_axes_pass_rate']} | {c['functional_pass_rate']} | {c['functional_unknown']} |")
        lines += ["", "| 짝 비교 | 단위 수 | 축 통과율 차이 [95% 구간] | 기능 통과율 차이 [95% 구간] |", "|---|---|---|---|"]
        for name, d in summary["paired"].items():
            lines.append(f"| {name} | {d['units']} | {d['axis_pass_diff']} {d['axis_pass_diff_ci95']} | "
                         f"{d['functional_diff']} {d['functional_diff_ci95']} |")
        # 실행 검사는 설계상 캐시 재생(--cached-only)으로 잰다. holdout 이면서 이전 프롬프트 재생이 아닐 때만 확증이다.
        replayed = any((item.get("improvement") or {}).get("method") == "replayed" for item in profiles)
        role = ("확증(판정에 쓴다)" if report.get("split") == "holdout" and not replayed
                else "판정에 쓰지 않는다 (pilot·재생·calibration)")
        lines += ["", f"- 사전등록 기준 ({role}): {json.dumps(summary['criteria'], ensure_ascii=False)}"
                  f" → 전부 충족: `{summary['all_criteria_met']}` · 미적용 비율 {summary['fallback_rate']}"]
    lines += ["", "## 조건 간 차이", ""] + [f"- {n}" for n in report["differences"] or ["비교할 결과 없음"]]
    return "\n".join(lines) + "\n"


FROZEN_SOURCES = ("service.py", "agents/personalized_prompt.py", "domains/coding.yaml", "engine/generator.py",
                  "checks/coding.py", "benchmarks/coding_ai_quality/evaluate_trial.py",
                  "benchmarks/coding_ai_quality/runtime_check.cjs", "experiments/personalized_prompt_comparison.py")


def source_hashes() -> dict[str, str]:
    """확증 실행이 사전등록 때와 같은 코드로 돌았는지 대조할 수 있게 남긴다."""
    import hashlib
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()[:16] for name in FROZEN_SOURCES}


def run(*, execute: bool, task_limit: int | None, max_api_calls: int, model: str, language: str,
        profile: dict[str, str] | None = None, rounds: int, temperature: float | None,
        cached_only: bool = False, behavior: bool = False, reviewed_outputs: bool = False,
        ai_prompt_from: Path | None = None, profiles: list[dict[str, str]] | None = None,
        split: str = "calibration", repeats: int = 1, fallback_as_base: bool = False) -> dict:
    """execute: 상한 안에서 실제 호출. cached_only: 호출 0회, 캐시에 있는 출력만 다시 꺼낸다."""
    if execute and cached_only:
        raise ValueError("--execute and --cached-only are exclusive")
    if behavior and not reviewed_outputs:
        raise ValueError("--behavior runs generated code in Node; review the outputs in "
                         f"{OUTPUT_DIR.relative_to(ROOT)} first and pass --reviewed-outputs")
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    profiles = profiles or [profile or DEFAULT_PROFILE]
    if ai_prompt_from is not None and len(profiles) != 1:
        raise ValueError("--ai-prompt-from replays one profile's prompt")
    if cached_only:
        max_api_calls = 0
    tasks = select_tasks(split, task_limit)
    worst_case = len(profiles) * (1 + len(tasks) * len(CONDITIONS) * repeats)
    plan = {"tasks": [t["id"] for t in tasks], "split": split, "conditions": list(CONDITIONS), "model": model,
            "language": language, "profiles": profiles, "rounds": rounds, "repeats": repeats,
            "temperature": temperature, "fallback_as_base": fallback_as_base,
            "max_api_requests_worst_case": worst_case,
            "note": "Cache hits send no request; condition (a) is shared across profiles, so the real count is lower."}
    if execute:
        if max_api_calls < worst_case:
            raise ValueError(f"--max-api-calls must cover the worst case ({worst_case})")
        load_dotenv(ROOT / ".env", override=False)
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is unavailable; no API requests were sent")

    usage = {"generation_requests": 0, "improvement_requests": 0, "input_tokens": 0, "output_tokens": 0,
             "unknown_usage_requests": 0}
    started = time.monotonic()

    def reserve():
        if usage["generation_requests"] + usage["improvement_requests"] >= max_api_calls:
            raise RuntimeError("API request limit reached")
        usage["improvement_requests"] += 1

    built = []
    for target in profiles:
        # 과제와 무관하게 같은 가상 사용자·같은 선택 이력 (이력은 축 조합만 담는다).
        history_state = simulate_history(target, tasks[0]["request"], rounds)
        prompts, improvement = build_prompts(history_state, model, language, execute=execute or cached_only,
                                             reserve=reserve)
        if ai_prompt_from is not None:
            if not cached_only:
                raise ValueError("--ai-prompt-from only replays a recorded prompt with --cached-only")
            recorded = json.loads(Path(ai_prompt_from).read_text(encoding="utf-8"))
            if (recorded.get("prompts", {}).get("rule_based") != prompts["rule_based"]
                    or not recorded["prompts"].get("ai_improved")):
                raise ValueError("recorded run has a different base prompt or no ai_improved prompt")
            prompts["ai_improved"] = recorded["prompts"]["ai_improved"]
            improvement = {"method": "replayed",
                           "source": str(Path(ai_prompt_from).resolve().relative_to(ROOT)),
                           "recorded_improvement": recorded.get("improvement"),
                           "note": "Prompt replayed from an earlier run; current validation may reject it."}
        if improvement.get("calls"):  # 캐시를 타면 0 - 예전 요청의 사용량은 original_usage 에 따로 있다
            usage["input_tokens"] += improvement.get("input_tokens") or 0
            usage["output_tokens"] += improvement.get("output_tokens") or 0
            if improvement.get("input_tokens") is None:
                usage["unknown_usage_requests"] += 1
        source = "ai_improved" if prompts["ai_improved"] is not None else None
        if source is None and fallback_as_base and (execute or cached_only):
            # 서비스와 같다: 개선이 안 되면 사용자는 기본 조립본을 받는다.
            prompts["ai_improved"], source = prompts["rule_based"], "fallback_base"
        built.append({"label": profile_label(target), "profile": target, "history": history_state.history,
                      "prompts": prompts, "improvement": improvement, "ai_prompt_source": source,
                      "ai_prompt_identical_to_base": prompts["ai_improved"] == prompts["rule_based"]})

    if not execute and not cached_only:
        return {"mode": "dry-run", "plan": plan,
                "prompts": {k: v for k, v in built[0]["prompts"].items() if k != "ai_improved"},
                "history": built[0]["history"]}

    rows = []
    single = len(profiles) == 1 and repeats == 1
    original_call = generator._call_and_cache

    def bounded_call(*args, **kwargs):
        if usage["generation_requests"] + usage["improvement_requests"] >= max_api_calls:
            raise RuntimeError("API request limit reached")
        usage["generation_requests"] += 1
        import litellm
        completion = litellm.completion

        def measured(*call_args, **call_kwargs):
            call_kwargs["num_retries"] = 0  # 보이지 않는 재시도 비용을 막는다
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

    generator._call_and_cache = bounded_call
    try:
        for item in built:
            for task in tasks:
                for repeat in range(repeats):
                    # 반복마다 캐시 폴더를 나눠 같은 입력도 새로 생성한다. 0 번은 기존 캐시와 같은 곳이다.
                    cache_dir = generator.CACHE_DIR if repeat == 0 else generator.CACHE_DIR / "ppc-repeats" / f"r{repeat}"
                    for condition in CONDITIONS:
                        prompt = item["prompts"][condition]
                        row = {"task": task["id"], "condition": condition}
                        if not single:
                            row.update(profile=item["label"], repeat=repeat)
                        if prompt is None:
                            rows.append({**row, "status": f"skipped ({item['improvement'].get('method')})"})
                            continue
                        before = usage["generation_requests"]
                        t0 = time.monotonic()
                        try:
                            output = generator.generate_with_prompt(prompt, task["request"], model,
                                                                    cache_dir=cache_dir, temperature=temperature)
                        except Exception as exc:  # noqa: BLE001 - 키·공급자 문구는 남기지 않는다
                            status = "not_cached" if cached_only else f"error ({type(exc).__name__})"
                            rows.append({**row, "status": status})
                            continue
                        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                        stem = (f"{task['id']}__{condition}" if single
                                else f"{task['id']}__{condition}__{item['label']}__r{repeat}")
                        (OUTPUT_DIR / f"{stem}.md").write_text(output, encoding="utf-8")
                        rows.append({**row, "status": "generated",
                                     "new_request": usage["generation_requests"] > before,
                                     "elapsed_seconds": round(time.monotonic() - t0, 2),
                                     "evaluation": evaluate(output, task["request"], item["profile"]),
                                     "behavior": behavior_check(task["id"], output) if behavior else None,
                                     "output_chars": len(output)})
    finally:
        generator._call_and_cache = original_call

    usage["elapsed_seconds"] = round(time.monotonic() - started, 2)
    first = built[0]
    return {
        "mode": "cached-only" if cached_only else "execute", "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model, "language": language, "split": split, "repeats": repeats, "temperature": temperature,
        "plan": plan, "profiles": built,
        # 한 프로필 실행과 같은 모양의 요약 필드 (예전 결과 파일과 호환).
        "profile": first["profile"], "history": first["history"], "prompts": first["prompts"],
        "improvement": first["improvement"], "ai_prompt_identical_to_base": first["ai_prompt_identical_to_base"],
        "rows": rows, "differences": differences(rows), "summary": summarize(rows, built),
        "usage": usage, "note": NOTE, "source_sha256": source_hashes(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true", help="실제 API 를 부른다 (기본은 사전 확인)")
    parser.add_argument("--task-limit", type=int, default=None, help="기본: split 의 과제 전부")
    parser.add_argument("--split", default="calibration", choices=["calibration", "holdout"])
    parser.add_argument("--max-api-calls", type=int, default=4)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--language", default="ko", choices=["ko", "en"])
    parser.add_argument("--rounds", type=int, default=service.TOTAL_ROUNDS)
    parser.add_argument("--profile", default=",".join(f"{k}={v}" for k, v in DEFAULT_PROFILE.items()))
    parser.add_argument("--preregistered-profiles", action="store_true",
                        help="사전등록한 네 프로필을 쓴다 (--profile 무시)")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--fallback-as-base", action="store_true",
                        help="개선이 적용되지 않으면 (c) 에 기본 조립본을 쓴다 (서비스 동작과 같다)")
    parser.add_argument("--cached-only", action="store_true", help="API 를 부르지 않고 캐시된 출력만 쓴다")
    parser.add_argument("--behavior", action="store_true", help="독립 지표: 타입 검사·빌드·동작 시나리오 실행")
    parser.add_argument("--reviewed-outputs", action="store_true",
                        help="data/personalized_prompt_comparison_outputs 의 원문을 검토했다 (--behavior 에 필요)")
    parser.add_argument("--ai-prompt-from", type=Path, default=None,
                        help="--cached-only 에서 (c) 를 이전 실행 결과 JSON 의 ai_improved 프롬프트로 재생한다")
    parser.add_argument("--output-name", default=None,
                        help="결과 파일 이름 (experiments/results/<이름>.{json,md}). 기본은 모드별 고정 이름")
    args = parser.parse_args()
    profiles = (PREREGISTERED_PROFILES if args.preregistered_profiles
                else [dict(item.split("=", 1) for item in args.profile.split(","))])
    temperature = None if args.model.startswith(("openai/gpt-5", "openai/gpt-6", "openai/o")) else args.temperature
    report = run(execute=args.execute, task_limit=args.task_limit, max_api_calls=args.max_api_calls,
                 model=args.model, language=args.language, profiles=profiles, rounds=args.rounds,
                 temperature=temperature, cached_only=args.cached_only, behavior=args.behavior,
                 reviewed_outputs=args.reviewed_outputs, ai_prompt_from=args.ai_prompt_from,
                 split=args.split, repeats=args.repeats, fallback_as_base=args.fallback_as_base)
    if report["mode"] == "dry-run":
        print(json.dumps(report["plan"], ensure_ascii=False, indent=2))
        print("dry-run: no API requests sent. Use --execute to run.")
        return
    if args.output_name:
        out_json = ROOT / "experiments" / "results" / f"{args.output_name}.json"
        out_md = out_json.with_suffix(".md")
    else:
        out_json, out_md = (CACHED_JSON, CACHED_MD) if args.cached_only else (OUTPUT_JSON, OUTPUT_MD)
    if out_json == OUTPUT_JSON and out_json.exists() and len(profiles) > 1:
        raise ValueError("refusing to overwrite the single-run result; pass --output-name")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(markdown(report), encoding="utf-8")
    print(markdown(report))


if __name__ == "__main__":
    main()

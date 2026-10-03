"""앱의 "선호 기준으로 최적화 (GEPA)" 한 번이 실제로 얼마인지 잰다.

    python -m experiments.gepa_cost

지금까지 화면은 "1~2분"이라고만 적었고 비용은 잰 적이 없었다. 앱과 같은 경로
(`service.start_session` -> 선택 -> `service.optimize`)를 앱과 같은 모델 설정으로 돌리고,
litellm 이 보고하는 실제 청구 비용(response_cost)을 모델별로 더한다.

선택은 늘 A 를 고른다 - 비용을 재는 것이 목적이라 선호의 내용은 상관없다. 후보 생성은
캐시를 탈 수 있으므로 세션 비용과 최적화 비용을 나눠 적는다. 최적화 쪽의 평가 호출은
후보 프롬프트가 매번 달라 대부분 캐시를 타지 않는다.
"""

from __future__ import annotations

import json
import threading
import time
from collections import defaultdict
from pathlib import Path

import litellm
from dotenv import load_dotenv

import service
from engine.domain_loader import load_domain

load_dotenv()

MODEL = "openai/gpt-4o-mini"  # 앱의 후보 생성 모델과 같다
DOMAINS = ("summarization", "coding")
OUT = Path("experiments/results/gepa_cost.json")


class ByModel:
    def __init__(self) -> None:
        self.cost: dict[str, float] = defaultdict(float)
        self.calls: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def __call__(self, kwargs, completion_response, start_time, end_time) -> None:
        model = str(kwargs.get("model") or "?")
        with self._lock:
            self.cost[model] += float(kwargs.get("response_cost") or 0.0)
            self.calls[model] += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {m: {"dollars": round(self.cost[m], 5), "calls": self.calls[m]} for m in self.cost}


def run(domain_key: str) -> dict:
    path = f"domains/{domain_key}.yaml"
    source = load_domain(path).example_sources[0]
    session_meter = ByModel()
    litellm.success_callback = [session_meter]
    state = service.start_session(source, domain_key, path, model=MODEL, demo_mode=False)
    while not state.done:
        state = service.submit_choice(state, state.pair.pair_id, "a")
    if state.demo_mode:
        raise RuntimeError("실제 생성이 실패해 데모로 내려갔다 - API 키를 확인할 것")

    meter = ByModel()
    litellm.success_callback = [meter]
    report: dict = {}
    started = time.monotonic()
    prompt = service.optimize(state, report=report)
    elapsed = time.monotonic() - started
    by_model = meter.snapshot()
    return {
        "domain": domain_key,
        "rounds": len(state.history),
        "session": session_meter.snapshot(),
        "optimize": by_model,
        "optimize_dollars": round(sum(v["dollars"] for v in by_model.values()), 4),
        "optimize_seconds": round(elapsed, 1),
        "metric_calls_budget": service.GEPA_METRIC_CALLS,
        "reflection_model": service.REFLECTION_MODEL,
        "prompt_changed": prompt != service.final_prompt(*service._rebuild(state)[:2], template_id=state.template_id),
        "report": {k: v for k, v in report.items() if isinstance(v, (int, float, str, bool))},
    }


def main() -> int:
    results = []
    for domain_key in DOMAINS:
        results.append(run(domain_key))
        OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(results[-1], ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

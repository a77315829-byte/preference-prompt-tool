"""학습률과 선택 잡음에 따른 선호 복원 - 모델을 부르지 않는 가상 사용자 실험.

    python -m experiments.estimator_ablation

외부 코드 검토에서 나온 두 질문에 답한다.
1. "Estimator 의 학습률 0.5 는 어디서 나온 값인가?" - 0.1~1.0 을 같은 조건에서 비교한다.
2. "왜 정해진 횟수만큼 묻는가?" - 앱의 선택기(같은 질문 금지, 물을 게 없으면 종료)가
   실제로 몇 번에 끝나는지 센다.

가상 사용자: 숨긴 축값이 있고, 두 후보 중 숨긴 값에 더 가까운(YAML 값 순서로 거리가
작은) 쪽을 고른다. noise 확률로 반대쪽을 고른다 - 실수로 누른 클릭을 흉내 낸다.
후보 글은 만들지 않는다. 그래서 이 실험은 **선택·추정 기계만** 시험하고, 모델이 축값대로
글을 쓰는지는 시험하지 않는다 (그건 heldout_comparison 등의 몫이다). API 호출 0회.
"""

from __future__ import annotations

import json
import random
import statistics
from itertools import product
from pathlib import Path

from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator
from engine.selector import UncertaintySelector

DOMAINS = ("summarization", "coding", "idle_tracker", "review", "email")
LEARNING_RATES = (0.1, 0.25, 0.5, 0.75, 1.0)
NOISES = (0.0, 0.1, 0.2)
SEEDS = range(5)
CHECKPOINTS = (4, 6, 8)
OUT = Path("experiments/results/estimator_ablation.json")


def _distance(domain, combo: dict, hidden: dict) -> int:
    total = 0
    for axis in domain.axes:
        if axis.type != "enum" or axis.name not in combo:
            continue
        values = [v.value for v in axis.values]
        total += abs(values.index(combo[axis.name]) - values.index(hidden[axis.name]))
    return total


def choose(domain, a: dict, b: dict, hidden: dict, noise: float, rng: random.Random) -> str:
    da, db = _distance(domain, a, hidden), _distance(domain, b, hidden)
    pick = "a" if da < db else "b" if db < da else rng.choice("ab")
    if rng.random() < noise:
        pick = "b" if pick == "a" else "a"
    return pick


def run_one(domain, hidden: dict, lr: float, noise: float, seed: int, app: bool) -> dict:
    """한 가상 사용자. 체크포인트마다 정확 복원 여부와, 앱 모드면 멈춘 회차."""
    rng = random.Random(1000 + seed)
    estimator = Estimator(domain, learning_rate=lr)
    selector = UncertaintySelector(domain, seed=seed, contrast_first=app, avoid_repeats=app)
    exact_at, stopped = {}, None
    for round_no in range(1, max(CHECKPOINTS) + 1):
        pair = selector.next_pair(estimator)
        if pair is None:  # 앱 모드: 물을 게 없으면 끝낸다
            stopped = round_no - 1
            break
        a, b = pair
        estimator.update(Comparison(a, b, choose(domain, a, b, hidden, noise, rng)))
        if round_no in CHECKPOINTS:
            exact_at[round_no] = all(estimator.preferred_value(k) == v for k, v in hidden.items())
    final = all(estimator.preferred_value(k) == v for k, v in hidden.items())
    for c in CHECKPOINTS:  # 일찍 끝났으면 그 뒤 체크포인트는 끝난 시점의 결과다
        exact_at.setdefault(c, final)
    return {"exact_at": exact_at, "final": final, "rounds": stopped or max(CHECKPOINTS)}


def run() -> dict:
    rows = []
    for name in DOMAINS:
        domain = load_domain(f"domains/{name}.yaml")
        enum_axes = [a for a in domain.axes if a.type == "enum"]
        for values in product(*[[v.value for v in a.values] for a in enum_axes]):
            hidden = dict(zip([a.name for a in enum_axes], values))
            for lr, noise, seed, app in product(LEARNING_RATES, NOISES, SEEDS, (False, True)):
                r = run_one(domain, hidden, lr, noise, seed, app)
                rows.append({"domain": name, "lr": lr, "noise": noise, "app": app, **r})

    def summary(app: bool) -> dict:
        out = {}
        for lr, noise in product(LEARNING_RATES, NOISES):
            sel = [r for r in rows if r["app"] == app and r["lr"] == lr and r["noise"] == noise]
            out[f"lr={lr} noise={noise}"] = {
                **{f"exact@{c}": round(sum(r["exact_at"][c] for r in sel) / len(sel), 3) for c in CHECKPOINTS},
                "mean_rounds": round(statistics.mean(r["rounds"] for r in sel), 2),
                "n": len(sel),
            }
        return out

    rounds_by_domain = {
        name: round(statistics.mean(r["rounds"] for r in rows
                                    if r["app"] and r["domain"] == name and r["lr"] == 0.5 and r["noise"] == 0), 2)
        for name in DOMAINS
    }
    return {"experiment_selector": summary(False), "app_selector": summary(True),
            "app_rounds_by_domain_lr0.5_noise0": rounds_by_domain,
            "note": "가상 사용자, API 0회. 선택·추정 기계만 시험한다."}


def main() -> int:
    result = run()
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    for mode in ("experiment_selector", "app_selector"):
        print(f"[{mode}]  exact@4 / exact@6 / exact@8 / 평균 회차")
        for key, v in result[mode].items():
            print(f"  {key:22} {v['exact@4']:.3f} / {v['exact@6']:.3f} / {v['exact@8']:.3f} / {v['mean_rounds']}")
    print("앱 선택기 도메인별 평균 회차 (lr 0.5, 잡음 0):", result["app_rounds_by_domain_lr0.5_noise0"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

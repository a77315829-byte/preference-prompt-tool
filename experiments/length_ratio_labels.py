"""길이 측정 v1(문장 수) 대 v2(원문 대비 단어 비율) - 사람 라벨 일치도.

    python -m experiments.length_ratio_labels

판단 기준은 실행 전에 docs/length_v2_preregistration.md 로 커밋했다.
임계값은 train 에서만 정하고 test 에서 잰다. API 호출은 없다.

checks_vs_labels.py 가 모든 분할을 합쳐 현행 YAML 의 일치도를 잰 진단이라면,
이 파일은 임계값을 고르는 데이터와 재는 데이터를 나눈 비교다.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import pandas as pd

from checks import summarization as checks
from experiments.checks_vs_labels import load_summaries

LABELS = ("short", "normal", "long")
HELDOUT_CSV = Path("experiments/results/heldout_comparison.csv")
TEST_JSON = Path("data/macsum/dataset/macdoc/test.json")
OUT = Path("experiments/results/length_ratio_labels.json")

# 현행 domains/summarization.yaml: short <= 2문장, normal 3~4, long >= 5.
V1_YAML_CUTS = (2, 4)


def features(summary: str, source: str) -> dict[str, float]:
    words = len(checks._words(summary))
    return {
        "sentences": len(checks._sentences(summary)),
        "ratio": words / max(len(checks._words(source)), 1),
    }


def classify(x: float, cuts: tuple[float, float]) -> str:
    low, high = cuts
    return "short" if x <= low else ("normal" if x <= high else "long")


def balanced_accuracy(labels: list[str], preds: list[str], classes=LABELS) -> float:
    recalls = []
    for c in classes:
        idx = [i for i, y in enumerate(labels) if y == c]
        if idx:
            recalls.append(sum(preds[i] == c for i in idx) / len(idx))
    return sum(recalls) / len(recalls)


def fit_cuts(xs: list[float], labels: list[str]) -> tuple[float, float]:
    """train 값의 1~99 백분위수 격자에서 균형정확도가 최대인 두 절단점."""
    s = sorted(xs)
    grid = sorted({s[min(len(s) - 1, len(s) * q // 100)] for q in range(1, 100)})
    best, best_cuts = -1.0, (grid[0], grid[-1])
    for cuts in combinations(grid, 2):
        score = balanced_accuracy(labels, [classify(x, cuts) for x in xs])
        if score > best:
            best, best_cuts = score, cuts
    return best_cuts


def short_vs_normal(labels: list[str], xs: list[float], cuts: tuple[float, float]) -> float:
    """short·normal 라벨만 떼어, 첫 절단점 하나로 가른 2클래스 균형정확도."""
    pairs = [(y, x) for y, x in zip(labels, xs) if y in ("short", "normal")]
    ys = [y for y, _ in pairs]
    preds = ["short" if x <= cuts[0] else "normal" for _, x in pairs]
    return balanced_accuracy(ys, preds, ("short", "normal"))


def report(rows: list[dict], key: str, cuts: tuple[float, float]) -> dict:
    labels = [r["label"] for r in rows]
    xs = [r[key] for r in rows]
    preds = [classify(x, cuts) for x in xs]
    confusion = defaultdict(Counter)
    for y, p in zip(labels, preds):
        confusion[y][p] += 1
    return {
        "n": len(rows),
        "cuts": list(cuts),
        "balanced_accuracy": round(balanced_accuracy(labels, preds), 4),
        "short_vs_normal": round(short_vs_normal(labels, xs, cuts), 4),
        "confusion": {y: {p: confusion[y][p] for p in LABELS} for y in LABELS},
    }


def check_no_leak(rows: list[dict]) -> dict:
    train_sources = {r["source"] for r in rows if r["split"] == "train"}
    test_sources = {r["source"] for r in rows if r["split"] == "test"}
    heldout_docs: set[int] = set()
    if HELDOUT_CSV.exists():
        df = pd.read_csv(HELDOUT_CSV)
        heldout_docs = set(df["learn_doc"]) | set(df["eval_doc"])
    test_records = json.loads(TEST_JSON.read_text(encoding="utf-8"))
    heldout_sources = {" ".join(test_records[i]["source"]) for i in heldout_docs}
    return {
        "train_test_overlap": len(train_sources & test_sources),
        "heldout_docs": len(heldout_docs),
        "heldout_in_train": len(heldout_sources & train_sources),
    }


def main() -> None:
    rows = []
    for r in load_summaries():
        label = r["labels"].get("length")
        if r["split"] == "val" and label in LABELS:
            continue  # 판단 기준대로 train 으로 정하고 test 로 잰다
        if label in LABELS:
            rows.append({"split": r["split"], "label": label, "source": r["source"],
                         "topic": bool(r["labels"].get("topic")), **features(r["summary"], r["source"])})

    leak = check_no_leak(rows)
    assert leak["train_test_overlap"] == 0 and leak["heldout_in_train"] == 0, leak

    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    v1_cuts = fit_cuts([r["sentences"] for r in train], [r["label"] for r in train])
    v2_cuts = fit_cuts([r["ratio"] for r in train], [r["label"] for r in train])
    methods = {"v1_yaml": ("sentences", V1_YAML_CUTS), "v1_refit": ("sentences", v1_cuts),
               "v2_ratio": ("ratio", v2_cuts)}

    result = {
        "leak_check": leak,
        "n_train": len(train),
        "test": {name: report(test, key, cuts) for name, (key, cuts) in methods.items()},
        "test_by_topic": {
            subset: {name: report([r for r in test if r["topic"] == flag], key, cuts)
                     for name, (key, cuts) in methods.items()}
            for subset, flag in (("no_topic", False), ("with_topic", True))
        },
    }
    gain = result["test"]["v2_ratio"]["balanced_accuracy"] - result["test"]["v1_refit"]["balanced_accuracy"]
    result["primary_criterion"] = {"gain_over_v1_refit": round(gain, 4), "threshold": 0.10, "met": gain >= 0.10}

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"누수 검사: {leak}")
    print(f"train {len(train)}개로 임계값 결정, test {len(test)}개로 평가\n")
    for scope, block in [("test 전체", result["test"])] + [
            (f"test {k}", v) for k, v in result["test_by_topic"].items()]:
        print(f"[{scope}]")
        for name, r in block.items():
            print(f"  {name:9} n={r['n']:4d} 절단점={r['cuts']}  균형정확도 {r['balanced_accuracy']:.3f}"
                  f"  short-normal {r['short_vs_normal']:.3f}")
            for y in LABELS:
                print(f"      {y:6} -> {r['confusion'][y]}")
    print(f"\n주 기준 (v2 >= v1-refit + 0.10): {result['primary_criterion']}")
    print(f"저장: {OUT}")


if __name__ == "__main__":
    main()

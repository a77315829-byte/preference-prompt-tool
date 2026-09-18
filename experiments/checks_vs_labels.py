"""검사 함수가 사람이 붙인 라벨과 얼마나 일치하는가.

    python -m experiments.checks_vs_labels

왜 필요한가: 비교군 D 는 `checks/` 로 조립한 평가 함수에 맞춰 프롬프트를
만들고 같은 `checks/` 로 채점한다. "검사 함수가 검증됐다"는 말이 문서에
있지만 근거 표가 없었다 - 6주차에 임계값을 MACSum 분포에 맞췄다는 기록뿐이다.
검사 함수가 사람 라벨과 대조된 수치가 없으면 순환 논증 의심을 끊을 수 없다.

무엇을 재는가: MACSum macdoc 의 사람 작성 요약 전체에 대해, 축마다

  1. 통과율   - 라벨된 값의 검사 함수가 그 요약에 만점(1.0)을 주는 비율
  2. 분류 정확도 - 세 값의 검사 점수 중 최고를 예측으로 삼았을 때
                  라벨과 맞는 비율 (클래스별 재현율과 균형정확도)

이 실험은 최적화 루프와 무관하다. 검사 함수가 만들어질 때 본 것은 분포의
요약 통계이고, 여기서는 라벨 하나하나에 대고 판정을 센다. API 호출은 없다.

specificity 는 검사 함수가 없으므로 같은 표에 넣을 수 없다. 대신
experiments/hybrid_routing_eval.py 가 같은 라벨(5,379건)에 대해 잰
균형정확도(분류기 0.500 / 소형 0.525 / 대형 0.464)를 나란히 읽으면 된다 -
"검사 함수가 라벨을 구분한다"는 것이 무슨 뜻인지 그 대조로 보인다.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from checks import summarization as checks
from engine.domain_loader import load_domain

DOMAIN_PATH = Path("domains/summarization.yaml")
MACDOC_DIR = Path("data/macsum/dataset/macdoc")
OUT = Path("experiments/results/checks_vs_labels.json")

AXES = ("length", "extractiveness")


def load_summaries(macdoc_dir: Path = MACDOC_DIR) -> list[dict]:
    rows = []
    for split in ("train", "val", "test"):
        data = json.loads((macdoc_dir / f"{split}.json").read_text(encoding="utf-8"))
        for record in data:
            source = " ".join(record["source"])
            for ref in record["references"]:
                rows.append({
                    "split": split,
                    "source": source,
                    "summary": ref["summary"],
                    "labels": ref["control_attribute"],
                })
    return rows


def _check_fn(name: str):
    return getattr(checks, name)


def score_all_values(domain, axis_name: str, summary: str, source: str) -> dict[str, float]:
    """축의 모든 값에 대해 검사 점수를 낸다."""
    axis = next(a for a in domain.axes if a.name == axis_name)
    out = {}
    for v in axis.values:
        fn = _check_fn(v.check.fn)
        score, _ = fn(summary, source, v.value, v.check.target)
        out[v.value] = score
    return out


def evaluate(domain, rows: list[dict]) -> dict:
    result = {}
    for axis_name in AXES:
        values = [v.value for v in next(a for a in domain.axes if a.name == axis_name).values]
        n = Counter()
        passed = Counter()
        correct = Counter()
        confusion = defaultdict(Counter)
        raw = defaultdict(list)

        for row in rows:
            label = row["labels"].get(axis_name, "")
            if label not in values:
                continue
            scores = score_all_values(domain, axis_name, row["summary"], row["source"])
            n[label] += 1
            if scores[label] >= 1.0:
                passed[label] += 1
            # 동점이면 라벨 순서상 앞을 고른다 - 사람 편을 들지 않기 위해
            # 정답이 뒤에 있을 때 불리하게 작동한다.
            pred = max(values, key=lambda v: scores[v])
            confusion[label][pred] += 1
            if pred == label:
                correct[label] += 1
            if axis_name == "length":
                raw[label].append(len(checks._sentences(row["summary"])))
            else:
                ob = checks._bigrams(checks._words(row["summary"]))
                sb = checks._bigrams(checks._words(row["source"]))
                raw[label].append(len(ob & sb) / len(ob) if ob else 0.0)

        recall = {v: correct[v] / n[v] for v in values if n[v]}
        result[axis_name] = {
            "n": dict(n),
            "pass_rate": {v: passed[v] / n[v] for v in values if n[v]},
            "recall": recall,
            "balanced_accuracy": sum(recall.values()) / len(recall),
            "accuracy": sum(correct.values()) / sum(n.values()),
            "confusion": {k: dict(v) for k, v in confusion.items()},
            "raw_mean": {v: sum(raw[v]) / len(raw[v]) for v in values if raw[v]},
        }
    return result


def main() -> None:
    domain = load_domain(DOMAIN_PATH)
    rows = load_summaries()
    result = evaluate(domain, rows)
    result["_meta"] = {
        "summaries": len(rows),
        "source": "MACSum macdoc train+val+test, 사람 작성 요약",
        "note": "검사 함수의 만점 통과율과 argmax 분류 정확도. API 호출 없음.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"사람 작성 요약 {len(rows)}개\n")
    for axis_name in AXES:
        r = result[axis_name]
        print(f"[{axis_name}]  균형정확도 {r['balanced_accuracy']:.3f}  "
              f"단순정확도 {r['accuracy']:.3f}")
        print(f"  {'값':8} {'N':>5} {'통과율':>7} {'재현율':>7} {'원시값 평균':>10}")
        for v in r["n"]:
            print(f"  {v:8} {r['n'][v]:5d} {r['pass_rate'][v]:7.1%} "
                  f"{r['recall'][v]:7.1%} {r['raw_mean'][v]:10.3f}")
        print("  혼동 (행=라벨, 열=예측):")
        for label, preds in r["confusion"].items():
            print(f"    {label:8} {dict(preds)}")
        print()
    print(f"저장: {OUT}")


if __name__ == "__main__":
    main()

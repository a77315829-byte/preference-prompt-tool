"""하이브리드 라우팅 곡선 검증용 대조 실험. specificity(판별력 미확인 축)에서
잰 라우팅 곡선이 신뢰할 만한지 확인하기 위해, 판별력이 이미 확인된 축인
length(짧다/길다, sentence_count로 검증됨)에 같은 라우팅 스윕을 그대로
돌려본다. 여기서 나오는 곡선은 축 자체의 노이즈가 아니라 라우팅 방식
자체의 성질을 반영한다고 볼 수 있다.

specificity 실험(experiments/hybrid_routing_eval.py)과 구조는 같지만
독립적으로 작성했다 - specificity 전용 코드(checks/summarization_hybrid.py)에
기대지 않아야 "같은 코드라서 같은 패턴이 나온 것 아니냐"는 지적을 피한다.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
from dotenv import load_dotenv
from litellm import completion
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

load_dotenv()

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

SMALL_MODEL = "openai/gpt-4.1-mini"
LARGE_MODEL = "openai/gpt-4.1"
MODEL_PATH = Path("models/length_classifier.joblib")
CACHE_DIR = Path("cache/hybrid_judge_length")
TIER_COST = {"classifier": 0.0, "small_llm": 1.0, "large_llm": 5.0}

JUDGE_PROMPT = (
    'Classify the given summary as either "short" or "long". Answer with exactly one '
    "word: short or long."
)


def load_examples(macdoc_dir: str = "data/macsum/dataset/macdoc") -> list[tuple[str, str]]:
    """(text, label) - label은 short/long만 (normal은 제외해 이진 분류로 단순화,
    specificity 실험과 동일한 이진 구조를 유지해 곡선을 비교 가능하게 함)."""
    examples = []
    for split in ("train", "val", "test"):
        data = json.loads(Path(macdoc_dir, f"{split}.json").read_text(encoding="utf-8"))
        for record in data:
            for ref in record["references"]:
                label = ref["control_attribute"].get("length", "")
                if label in ("short", "long"):
                    examples.append((ref["summary"], label))
    return examples


def train_test_split(examples: list, test_ratio: float = 0.2, seed: int = 0):
    rng = random.Random(seed)
    shuffled = examples.copy()
    rng.shuffle(shuffled)
    n_test = int(len(shuffled) * test_ratio)
    return shuffled[n_test:], shuffled[:n_test]


def train_classifier(train: list[tuple[str, str]]) -> Pipeline:
    pipeline = Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )
    pipeline.fit([t for t, _ in train], [label for _, label in train])
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    return pipeline


def classifier_tier(clf: Pipeline, text: str) -> tuple[str, float]:
    proba = clf.predict_proba([text])[0]
    idx = proba.argmax()
    return clf.classes_[idx], float(proba[idx])


def llm_tier(text: str, model: str) -> tuple[str, float]:
    response = completion(
        model=model,
        messages=[{"role": "system", "content": JUDGE_PROMPT}, {"role": "user", "content": text}],
        max_tokens=1,
        temperature=0,
        logprobs=True,
        top_logprobs=5,
    )
    top = response.choices[0].logprobs.content[0].top_logprobs
    logprobs = {t.token.strip().lower(): t.logprob for t in top}
    lp_short = logprobs.get("short", -50.0)
    lp_long = logprobs.get("long", -50.0)
    p_short = math.exp(lp_short) / (math.exp(lp_short) + math.exp(lp_long))
    label = "short" if p_short >= 0.5 else "long"
    confidence = p_short if label == "short" else 1.0 - p_short
    return label, confidence


def cached_llm_tier(text: str, model: str, tier_name: str) -> tuple[str, float]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    import hashlib

    key = hashlib.sha256(f"{tier_name}:{text}".encode("utf-8")).hexdigest()
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        return cached["label"], cached["confidence"]
    label, confidence = llm_tier(text, model)
    cache_file.write_text(json.dumps({"label": label, "confidence": confidence}), encoding="utf-8")
    return label, confidence


def route(row, classifier_threshold: float, small_threshold: float) -> tuple[str, str]:
    if row["classifier_conf"] >= classifier_threshold:
        return row["classifier_label"], "classifier"
    if row["small_conf"] >= small_threshold:
        return row["small_label"], "small_llm"
    return row["large_label"], "large_llm"


def main() -> None:
    examples = load_examples()
    train, test = train_test_split(examples)
    clf = train_classifier(train)

    rng = random.Random(0)
    short_examples = [e for e in test if e[1] == "short"]
    long_examples = [e for e in test if e[1] == "long"]
    n = min(len(short_examples), len(long_examples), 138)  # specificity 실험과 표본 크기 맞춤
    eval_set = rng.sample(short_examples, n) + rng.sample(long_examples, n)
    print(f"평가셋: {len(eval_set)} (short={n}, long={n})")

    rows = []
    for i, (text, true_label) in enumerate(eval_set):
        c_label, c_conf = classifier_tier(clf, text)
        s_label, s_conf = cached_llm_tier(text, SMALL_MODEL, "small_llm")
        l_label, l_conf = cached_llm_tier(text, LARGE_MODEL, "large_llm")
        rows.append(
            {
                "true_label": true_label,
                "classifier_label": c_label, "classifier_conf": c_conf,
                "small_label": s_label, "small_conf": s_conf,
                "large_label": l_label, "large_conf": l_conf,
            }
        )
        if (i + 1) % 40 == 0:
            print(f"{i + 1}/{len(eval_set)}")

    df = pd.DataFrame(rows)
    out_dir = Path("experiments/results")
    df.to_csv(out_dir / "hybrid_judge_raw_length.csv", index=False)

    for tier, label_col in [("classifier", "classifier_label"), ("small_llm", "small_label"), ("large_llm", "large_label")]:
        acc = (df[label_col] == df["true_label"]).mean()
        print(f"[{tier} 단독] accuracy={acc:.3f}")

    thresholds = [round(0.5 + 0.05 * i, 2) for i in range(11)]
    sweep_rows = []
    for t in thresholds:
        predicted, tier = zip(*df.apply(lambda r: route(r, t, t), axis=1))
        correct = [p == truth for p, truth in zip(predicted, df["true_label"])]
        acc = sum(correct) / len(correct)
        avg_cost = sum(TIER_COST[x] for x in tier) / len(tier)
        sweep_rows.append({"threshold": t, "accuracy": acc, "avg_cost": avg_cost})

    sweep_df = pd.DataFrame(sweep_rows)
    sweep_df.to_csv(out_dir / "hybrid_routing_sweep_length.csv", index=False)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(sweep_df["avg_cost"], sweep_df["accuracy"], marker="o")
    for _, r in sweep_df.iterrows():
        ax.annotate(f"{r['threshold']:.2f}", (r["avg_cost"], r["accuracy"]), fontsize=8)
    ax.set_xlabel("평균 상대 비용 (분류기=0, 소형=1, 대형=5)")
    ax.set_ylabel("정확도")
    ax.set_title("length(short/long) 판정: 비용 대비 정확도 (판별력 확인된 축, 대조군)")
    ax.grid(alpha=0.3)
    fig.savefig(out_dir / "hybrid_routing_curve_length.png", dpi=150, bbox_inches="tight")
    print(f"saved plot to {out_dir / 'hybrid_routing_curve_length.png'}")


if __name__ == "__main__":
    main()

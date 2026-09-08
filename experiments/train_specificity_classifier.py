"""specificity 축 판정용 초소형 분류기 학습 (CLAUDE.md v2, 우선순위 3, 계층 2).

정규식(6주차)도 spaCy NER(6주차)도 판별력이 없었던 specificity 축을,
TF-IDF + 로지스틱 회귀로 다시 시도한다. 라벨 불균형(normal 87% / high 13%)이
있어 class_weight="balanced"를 쓰고, 정확도 대신 균형정확도·F1로 채점한다.

결과가 좋으면: "초소형 분류기가 LLM 판정을 훨씬 싼 비용으로 대체" - 강한 성과.
결과가 나쁘면: "규칙도 학습도 실패 -> 이 축엔 LLM 판정이 실제로 필요하다"는
주장이 훨씬 단단해진다. 어느 쪽이든 하이브리드 판정 계층의 근거가 된다.
"""

from __future__ import annotations

from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, classification_report, f1_score
from sklearn.pipeline import Pipeline

from experiments.specificity_dataset import load_examples, train_test_split

MODEL_PATH = Path("models/specificity_classifier.joblib")


def main() -> None:
    examples = load_examples()
    train, test = train_test_split(examples)

    pipeline = Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )

    x_train, y_train = [e.text for e in train], [e.label for e in train]
    x_test, y_test = [e.text for e in test], [e.label for e in test]

    pipeline.fit(x_train, y_train)
    y_pred = pipeline.predict(x_test)

    print(classification_report(y_test, y_pred))
    print("balanced_accuracy:", round(balanced_accuracy_score(y_test, y_pred), 3))
    print("f1(high):", round(f1_score(y_test, y_pred, pos_label="high"), 3))

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    print(f"saved to {MODEL_PATH}")


if __name__ == "__main__":
    main()

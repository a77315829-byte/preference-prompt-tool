"""specificity 축 - 하이브리드 판정 계층 (CLAUDE.md v2, 우선순위 3).

4단 계층: 코드(정규식/spaCy, 6주차에 판별력 없어 이미 탈락) -> 학습형
초소형 분류기(TF-IDF+로지스틱회귀, train_specificity_classifier.py -
균형정확도 0.498로 사실상 실패) -> 소형 LLM -> 대형 LLM.

확신도는 모델의 자기 보고(verbalized confidence)를 쓰지 않는다 - 보정이
안 되는 것으로 알려져 있다. 대신 단일 토큰(high/normal) 출력을 강제하고
그 토큰의 로그확률을 소프트맥스해 확신도로 쓴다.

캐싱: GEPA는 같은 후보 프롬프트를 여러 예시에 반복 평가하므로, 같은
(텍스트, 축, 목표값) 조합은 재호출하지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import joblib
from litellm import completion

# domains/summarization_hybrid.yaml 은 summarization.yaml에서 axes를 상속하므로
# (engine/domain_loader.py의 extends 병합), length/extractiveness/topic 축이
# 쓰는 check.fn(sentence_count 등)도 이 모듈의 이름공간에 있어야 metric_builder가
# getattr(checks_module, fn)으로 찾을 수 있다.
from checks.summarization import keyword_presence, lexical_overlap, sentence_count  # noqa: F401

CLASSIFIER_PATH = Path("models/specificity_classifier.joblib")
CACHE_DIR = Path("cache/hybrid_judge")

SMALL_MODEL = "openai/gpt-4.1-mini"
LARGE_MODEL = "openai/gpt-4.1"

# 라우팅 임계값 - experiments/hybrid_routing_eval.py 스윕 결과(0.85가 균형
# 정확도 최고점, 0.558)로 정했다. 분류기는 균형정확도 0.500(우연)이라 사실상
# 항상 우회되고, 대부분 소형 LLM에서 끝난다 - 대형 모델로 전부 에스컬레이션
# (임계값 1.0)하면 오히려 0.514로 떨어지고 비용만 5배가 된다. "더 비싼 모델이
# 항상 낫지는 않다"는 것 자체가 이 실험의 결과다.
CLASSIFIER_CONFIDENCE_THRESHOLD = 0.85
SMALL_MODEL_CONFIDENCE_THRESHOLD = 0.85

_JUDGE_PROMPT = (
    "You are given a source article and a summary of it. Classify the summary's "
    'specificity as either "high" or "normal" - whether it pulls in precise, '
    "concrete detail available in the source (numbers, dates, named entities) "
    "versus staying at a general level, relative to how much specific detail the "
    "source actually offers. Answer with exactly one word: high or normal."
)

_classifier = None


def _load_classifier():
    global _classifier
    if _classifier is None:
        _classifier = joblib.load(CLASSIFIER_PATH)
    return _classifier


def classifier_tier(text: str) -> tuple[str, float]:
    """계층 2: 학습형 초소형 분류기. API 호출 없음, 사실상 무료."""
    clf = _load_classifier()
    proba = clf.predict_proba([text])[0]
    idx = proba.argmax()
    return clf.classes_[idx], float(proba[idx])


def llm_tier(text: str, source: str, model: str) -> tuple[str, float]:
    """계층 3/4 공용: 단일 토큰 출력 + logprob 기반 확신도. 원문도 같이 준다 -
    구체성은 원문 대비 상대적 개념일 가능성이 높다 (요약문만 봐서는 소형/대형
    LLM 모두 우연 수준 정확도였다)."""
    response = completion(
        model=model,
        messages=[
            {"role": "system", "content": _JUDGE_PROMPT},
            {"role": "user", "content": f"[SOURCE]\n{source}\n\n[SUMMARY]\n{text}"},
        ],
        max_tokens=1,
        temperature=0,
        logprobs=True,
        top_logprobs=5,
    )
    top = response.choices[0].logprobs.content[0].top_logprobs
    logprobs = {t.token.strip().lower(): t.logprob for t in top}
    lp_high = logprobs.get("high", -50.0)
    lp_normal = logprobs.get("normal", -50.0)
    p_high = math.exp(lp_high) / (math.exp(lp_high) + math.exp(lp_normal))
    label = "high" if p_high >= 0.5 else "normal"
    confidence = p_high if label == "high" else 1.0 - p_high
    return label, confidence


def _cache_path(text: str, source: str, tier: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{tier}:{source}:{text}".encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{key}.json"


def cached_llm_tier(text: str, source: str, model: str, tier_name: str) -> tuple[str, float]:
    cache_file = _cache_path(text, source, tier_name)
    if cache_file.exists():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        return cached["label"], cached["confidence"]

    label, confidence = llm_tier(text, source, model)
    cache_file.write_text(json.dumps({"label": label, "confidence": confidence}), encoding="utf-8")
    return label, confidence


def predict_label(
    text: str,
    source: str,
    classifier_threshold: float = CLASSIFIER_CONFIDENCE_THRESHOLD,
    small_model_threshold: float = SMALL_MODEL_CONFIDENCE_THRESHOLD,
) -> tuple[str, float, str]:
    """계층을 순서대로 타며 확신도가 임계값을 넘으면 그 자리에서 멈춘다.
    반환: (예측 라벨, 확신도, 사용된 계층 이름)"""
    label, confidence = classifier_tier(text)
    if confidence >= classifier_threshold:
        return label, confidence, "classifier"

    label, confidence = cached_llm_tier(text, source, SMALL_MODEL, "small_llm_src")
    if confidence >= small_model_threshold:
        return label, confidence, "small_llm"

    label, confidence = cached_llm_tier(text, source, LARGE_MODEL, "large_llm_src")
    return label, confidence, "large_llm"


def specificity_judge(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    """checks/*.py 표준 시그니처. specificity 축 하나만 이 하이브리드 계층을 쓴다."""
    predicted_label, confidence, tier = predict_label(output, source)

    if predicted_label == value:
        return 1.0, f"구체성 충족: {tier} 판정 결과 '{value}'와 일치 (확신도 {confidence:.2f})."
    return 0.0, (
        f"구체성 위반: {tier} 판정 결과 '{predicted_label}'로 보임 "
        f"(목표 '{value}', 확신도 {confidence:.2f})."
    )

"""비교군 A(프롬프트 없음) · B(사용자 커스텀 지침) · D(본 도구) 결과 비교.

CLAUDE.md 평가계획의 "최소 달성(반드시)" 항목 - 각 조건의 산출물을 페르소나의
실제 축값(length, extractiveness)에 대해 checks/summarization.py로 채점해
비교한다. 정답 축값을 알고 있는 상태로 재는 것이므로 estimator의 확신도
가중치는 쓰지 않고 단순 평균을 쓴다 (metric_builder.py는 "추정된" 선호를
다루지만, 여기서는 "진짜" 선호를 알고 채점하는 평가 스크립트라 다르다).
"""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from litellm import completion

from engine.domain_loader import Domain, load_domain
from engine.estimator import Comparison, Estimator
from engine.generator import generate
from engine.selector import UncertaintySelector
from experiments.persona import choose
from experiments.run_all import pick_documents_with_personas
from optimize.run_gepa import build_seed_prompt

load_dotenv()

MODEL = "openai/gpt-4.1-mini"
N_DOCS = 5
N_ROUNDS = 8
CACHE_DIR = Path("cache")

CONDITION_A_PROMPT = ""  # A: 프롬프트 없이 기본 호출
CONDITION_B_PROMPT = (  # B: 사용자가 직접 쓸 법한, 개인화되지 않은 일반적인 지침
    "Summarize the following article in a clear and concise way that captures the key points."
)


def generate_raw(prompt: str, source: str, model: str) -> str:
    """축조합 없이 고정 프롬프트로 생성 (조건 A/B용). engine/generator.py와
    같은 규칙(같은 프롬프트+원문+모델은 재호출 안 함)으로 캐싱한다."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"prompt": prompt, "source": source, "model": model}, sort_keys=True)
    key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    cache_file = CACHE_DIR / f"{key}.json"

    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))["output"]

    messages = [{"role": "user", "content": source}]
    if prompt:
        messages.insert(0, {"role": "system", "content": prompt})

    response = completion(model=model, messages=messages)
    output = response.choices[0].message.content

    cache_file.write_text(
        json.dumps({"prompt": prompt, "output": output}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output


def score_against_combo(domain: Domain, combo: dict, output: str, source: str) -> float:
    checks_module = importlib.import_module(domain.checks_module)
    scores = []
    for axis in domain.axes:
        if axis.type != "enum" or axis.name not in combo:
            continue
        value = combo[axis.name]
        check_spec = axis.check_for(value)
        check_fn = getattr(checks_module, check_spec.fn)
        score, _ = check_fn(output, source, value, check_spec.target)
        scores.append(score)
    return sum(scores) / len(scores) if scores else 0.0


def run_condition_d(domain: Domain, source: str, persona) -> str:
    """D: 8회 선택 루프(불확실도 기반)를 실제로 돌려 선호를 학습하고, 그
    선호로 조립한 프롬프트로 최종 결과물을 생성한다."""
    estimator = Estimator(domain)
    selector = UncertaintySelector(domain, seed=0)

    for _ in range(N_ROUNDS):
        combo_a, combo_b = selector.next_pair(estimator)
        candidate_a = generate(domain, source, combo_a, model=MODEL)
        candidate_b = generate(domain, source, combo_b, model=MODEL)
        winner = choose(domain, persona, candidate_a, candidate_b, source)
        estimator.update(Comparison(combo_a, combo_b, winner))

    seed_prompt = build_seed_prompt(domain, estimator)
    return generate_raw(seed_prompt, source, MODEL)


def main() -> None:
    domain = load_domain("domains/summarization.yaml")
    documents = pick_documents_with_personas("data/macsum/dataset/macdoc/val.json", N_DOCS)

    rows = []
    for doc_idx, (source, persona) in enumerate(documents):
        target_combo = {"length": persona.combo["length"], "extractiveness": persona.combo["extractiveness"]}

        outputs = {
            "A_no_prompt": generate_raw(CONDITION_A_PROMPT, source, MODEL),
            "B_custom_instruction": generate_raw(CONDITION_B_PROMPT, source, MODEL),
            "D_our_tool": run_condition_d(domain, source, persona),
        }

        for condition, output in outputs.items():
            score = score_against_combo(domain, target_combo, output, source)
            rows.append({"doc": doc_idx, "condition": condition, "score": score})
            print(f"doc={doc_idx} condition={condition} target={target_combo} score={score:.3f}")

    df = pd.DataFrame(rows)
    out_path = Path("experiments/results/baseline_comparison.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

    print()
    print(df.groupby("condition")["score"].agg(["mean", "std"]).round(3))
    print(f"saved to {out_path}")


if __name__ == "__main__":
    main()

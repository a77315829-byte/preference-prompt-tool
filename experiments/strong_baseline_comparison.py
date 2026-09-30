"""강한 비교군 - B가 '자기 취향을 모르는 사람이 쓴 지침'이라는 지적에 대한 답.

    python -m experiments.strong_baseline_comparison

수행계획서 3-3 페이지의 잔여 항목 #1: "비교군 B가 실험자가 쓴 일반 지침
1줄"이라 D가 이기는 것이 당연해 보인다는 지적. B는 그대로 두고, 두 조건을
더한다 - compare_baselines.py 와 같은 5문서·페르소나로 비교해야 뜻이 있다.

  B      기존 조건. 취향을 모르는 사람의 지침 1줄 (그대로 유지)
  B+     취향을 아는 사람이 썼을 법한 지침. 페르소나의 실제 축값을
         자연어로 옮겨 쓰되, YAML의 지시문과는 다른 표현을 쓴다 - 같은
         문구를 쓰면 D를 손으로 베낀 것과 다르지 않다.
  B-LLM  '취향을 말로 설명하면 모델이 지침으로 바꿔준다'는, 이 프로젝트가
         대체하려는 바로 그 기존 방식. 페르소나의 축값 설명을 모델에
         주고 지침 문장을 만들게 한다. 이 지침을 만드는 호출도 캐싱한다.
  D      기존 조건. 8회 비교 → 조립 (GEPA 없음)

B+ 가 D 에 근접하면 "D 가 이기는 건 B 가 약해서"라는 반박이 성립한다.
반대로 D 가 B+ 도 이기면, 그 반박이 사실이 아니라는 뜻이다. B-LLM 은
그 사이 어딘가에 있을 것으로 예상한다 - 말로 설명하는 것 자체의 정보
손실은 있지만 완전히 취향을 모르는 것보다는 낫다.

채점은 규칙 7대로 둘 다 낸다 - checks_score(D의 최적화 목표와 동일 계열,
B/B+/B-LLM에는 유리하지 않음)와 ROUGE-L(독립). 판정은 ROUGE-L로 한다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from litellm import completion

from engine.domain_loader import load_domain
from experiments.compare_baselines import (
    CACHE_DIR,
    MODEL,
    N_DOCS,
    CONDITION_B_PROMPT,
    generate_raw,
    run_condition_d,
    score_against_combo,
)
from experiments.independent_grader import rouge_l_score
from experiments.run_all import pick_documents_with_personas

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

OUT_CSV = Path("experiments/results/strong_baseline_comparison.csv")
OUT_PROMPTS = Path("experiments/results/strong_baseline_prompts.json")

# 페르소나 축값을 YAML 지시문과는 다른 표현으로 옮긴다 - 문구가 같으면
# "취향을 아는 사람이 직접 썼다"가 아니라 그냥 D를 베낀 것이 된다.
LENGTH_PHRASING = {
    "short": "in 2 sentences or less - keep it as short as possible",
    "normal": "in about 3 to 4 sentences, a normal-length summary",
    "long": "in at least 5 sentences, with plenty of detail",
}
EXTRACTIVENESS_PHRASING = {
    "normal": "using your own words for the most part",
    "high": "keeping close to the original wording where you can",
    "fully": "by directly excerpting sentences from the original text rather than rewriting them",
}


def build_strong_direct_prompt(combo: dict) -> str:
    """B+: 취향을 아는 사람이 직접 쓴 지침. YAML 지시문과 다른 문구를 쓴다."""
    length = LENGTH_PHRASING[combo["length"]]
    extractiveness = EXTRACTIVENESS_PHRASING[combo["extractiveness"]]
    return f"Summarize the following article {length}, {extractiveness}."


def _cached_completion(prompt: str, cache_name: str, model: str) -> str:
    """지침 문장 자체를 만드는 호출도 캐싱한다 (규칙 2) - generate_raw와
    같은 방식이지만 system/user 구성이 달라 별도 함수로 둔다."""
    import hashlib

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{cache_name}:{prompt}:{model}".encode("utf-8")).hexdigest()
    cache_file = CACHE_DIR / f"instr_{key}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))["output"]

    response = completion(model=model, messages=[{"role": "user", "content": prompt}])
    output = response.choices[0].message.content
    if not (output or "").strip():
        raise ValueError("모델이 빈 지침을 반환했다.")
    cache_file.write_text(json.dumps({"prompt": prompt, "output": output}, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    return output


def build_llm_generated_prompt(combo: dict, model: str) -> str:
    """B-LLM: 사용자가 취향을 '말로' 설명하면 모델이 지침으로 바꿔준다는,
    이 프로젝트가 대체하려는 기존 방식 그 자체를 재현한다."""
    length_desc = {
        "short": "as short as possible, just the essentials",
        "normal": "a normal, moderate length",
        "long": "detailed and thorough",
    }[combo["length"]]
    style_desc = {
        "normal": "mostly in their own words",
        "high": "sticking fairly close to the original wording",
        "fully": "by directly quoting the original text rather than paraphrasing",
    }[combo["extractiveness"]]

    meta_prompt = (
        "A user wants a summarization assistant that fits their preferences. "
        f"They want summaries that are {length_desc}, and written {style_desc}. "
        "Write ONE short system instruction (a single sentence) that a summarization "
        "assistant could follow to match these preferences, phrased naturally as a "
        "user might write it. Return only the instruction sentence, nothing else."
    )
    return _cached_completion(meta_prompt, "b_llm_instruction", model).strip()


def main() -> None:
    domain = load_domain("domains/summarization.yaml")
    documents = pick_documents_with_personas("data/macsum/dataset/macdoc/val.json", N_DOCS)

    rows = []
    prompts_used = []
    for doc_idx, (source, persona) in enumerate(documents):
        target_combo = {"length": persona.combo["length"], "extractiveness": persona.combo["extractiveness"]}

        b_plus_prompt = build_strong_direct_prompt(target_combo)
        b_llm_prompt = build_llm_generated_prompt(target_combo, MODEL)
        prompts_used.append({"doc": doc_idx, "target": target_combo,
                             "b_plus": b_plus_prompt, "b_llm": b_llm_prompt})

        outputs = {
            "B_custom_instruction": generate_raw(CONDITION_B_PROMPT, source, MODEL),
            "B_plus_knows_preference": generate_raw(b_plus_prompt, source, MODEL),
            "B_llm_generated": generate_raw(b_llm_prompt, source, MODEL),
            "D_our_tool": run_condition_d(domain, source, persona),
        }

        for condition, output in outputs.items():
            checks_score = score_against_combo(domain, target_combo, output, source)
            independent_score = rouge_l_score(output, persona.reference_summary)
            rows.append({"doc": doc_idx, "condition": condition,
                         "checks_score": checks_score, "independent_score": independent_score})
            print(f"doc={doc_idx} condition={condition:24} checks={checks_score:.3f} "
                  f"rougeL={independent_score:.3f}")

    df = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    OUT_PROMPTS.write_text(json.dumps(prompts_used, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    summary = df.groupby("condition")[["checks_score", "independent_score"]].agg(["mean", "std"]).round(3)
    print(summary)

    # D vs B+ 페어드 비교 - 이게 이번 실험의 핵심 질문에 대한 답이다.
    pivot = df.pivot(index="doc", columns="condition", values="independent_score")
    d_vs_bplus = (pivot["D_our_tool"] - pivot["B_plus_knows_preference"])
    wins = int((d_vs_bplus > 0).sum())
    print(f"\nD vs B+ (ROUGE-L): D가 이긴 문서 {wins}/{len(pivot)}, 평균 차이 {d_vs_bplus.mean():+.3f}")
    d_vs_bllm = (pivot["D_our_tool"] - pivot["B_llm_generated"])
    wins_llm = int((d_vs_bllm > 0).sum())
    print(f"D vs B-LLM (ROUGE-L): D가 이긴 문서 {wins_llm}/{len(pivot)}, 평균 차이 {d_vs_bllm.mean():+.3f}")

    print(f"\nsaved to {OUT_CSV}")
    print(f"instructions saved to {OUT_PROMPTS}")


if __name__ == "__main__":
    main()

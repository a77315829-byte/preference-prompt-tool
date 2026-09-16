"""추출한 전문가 프롬프트가 정말 그 사람처럼 쓰게 만드는지 홀드아웃으로 잰다.

이 실험이 없으면 `agents/expert_onboarding.py` 는 "그럴듯한데 효과를
증명할 수 없는 기능"이 된다. 이 프로젝트가 지켜온 기준과 반대다.

**설계.** MACSum 은 같은 원문에 대해 사람이 서로 다른 속성으로 쓴 요약을
갖고 있다. 속성 조합 하나를 고정하면 그 조합으로 94개 문서를 요약한
"한 사람"이 생긴다. 그 사람의 요약 몇 개만 보여주고(라벨은 감춘다) 축을
추출해 프롬프트를 만든 뒤, **한 번도 보여주지 않은 문서**에 그 프롬프트를
적용해서 그 사람의 실제 요약과 얼마나 가까운지 잰다.

**지표.** ROUGE-L (`experiments/independent_grader.py`). 추출 루프에
쓰이지 않으므로 순환 논증이 아니다. checks/ 와도 다른 알고리즘이다.

**비교군.**
  base   : task_description 만. 축 지시문이 전부 빠진 상태.
  expert : task_description + 추출한 축을 이 사람의 값으로 설정.
  anti   : 같은 축을 일부러 반대값으로 설정. 축이 방향을 갖는지 본다.

anti 를 넣는 이유: expert 가 base 보다 높다고 해서 "축을 맞게 추정했다"는
뜻은 아니다. 지시문을 더 붙이면 그냥 좋아지는 것일 수도 있다. anti 가
base 보다 낮아야 축이 실제로 방향을 가진 것이다.

실행:
    python -m experiments.expert_prompt_eval
    python -m experiments.expert_prompt_eval --persona long --train 5 --test 8
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from dotenv import load_dotenv

from agents.expert_onboarding import (
    ExpertExample,
    corpus_stats,
    extract_axes,
    to_domain,
)
from engine.generator import build_prompt, generate_all_with_prompts
from experiments.independent_grader import rouge_l_score

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
MACSUM_VAL = ROOT / "data" / "macsum" / "dataset" / "macdoc" / "val.json"
RESULTS = ROOT / "experiments" / "results"

MODEL = "openai/gpt-4.1-mini"

# val.json 에 topic 없이 존재하는 조합은 extractiveness=normal 뿐이고
# length 로만 갈린다. 그래서 페르소나는 길이로 고른다.
PERSONAS = {
    "short": {"length": "short", "extractiveness": "normal"},
    "normal": {"length": "normal", "extractiveness": "normal"},
    "long": {"length": "long", "extractiveness": "normal"},
}


def load_persona_examples(persona: dict[str, str], limit: int) -> list[ExpertExample]:
    """이 속성 조합으로 쓰인 (원문, 사람 요약) 쌍을 모은다."""
    records = json.loads(MACSUM_VAL.read_text(encoding="utf-8"))
    examples: list[ExpertExample] = []
    for record in records:
        source = " ".join(record["source"])
        for reference in record["references"]:
            attribute = reference["control_attribute"]
            if attribute.get("topic"):
                continue
            if all(attribute.get(k) == v for k, v in persona.items()):
                examples.append(ExpertExample(output=reference["summary"], task=source))
                break
        if len(examples) >= limit:
            break
    return examples


def _anti_combo(report) -> dict[str, str]:
    """각 축에서 이 사람의 값이 아닌 값을 고른다."""
    combo = {}
    for axis in report.axes:
        others = [v.value for v in axis.values if v.value != axis.author_value]
        combo[axis.name] = others[0] if others else axis.author_value
    return combo


def run(persona_name: str, n_train: int, n_test: int) -> dict:
    persona = PERSONAS[persona_name]
    examples = load_persona_examples(persona, n_train + n_test)
    if len(examples) < n_train + n_test:
        raise SystemExit(
            f"예시가 부족하다: {len(examples)}개 (필요 {n_train + n_test}개)"
        )

    train, test = examples[:n_train], examples[n_train : n_train + n_test]
    print(f"페르소나 {persona_name} {persona}")
    print(f"학습 예시 {len(train)}개 / 홀드아웃 {len(test)}개 (라벨은 알려주지 않는다)\n")

    report = extract_axes(train)
    domain = to_domain(report)
    print("추정한 과제 서술:", report.task_description)
    print(f"뽑은 축 {len(report.axes)}개:")
    for axis in report.axes:
        print(f"  [{axis.name}] 이 사람={axis.author_value} / 값={axis.value_names()}")
    print()

    prompts = {
        "base": domain.task_description,
        "expert": build_prompt(domain, report.author_combo()),
        "anti": build_prompt(domain, _anti_combo(report)),
    }
    print("조립된 전문가 프롬프트:")
    print(prompts["expert"])
    print()

    scores: dict[str, list[float]] = {name: [] for name in prompts}
    generated: dict[str, list[ExpertExample]] = {name: [] for name in prompts}
    order = list(prompts)
    for index, example in enumerate(test, start=1):
        outputs = generate_all_with_prompts(
            [prompts[name] for name in order], example.task, model=MODEL
        )
        line = []
        for name, output in zip(order, outputs):
            score = rouge_l_score(output, example.output)
            scores[name].append(score)
            generated[name].append(ExpertExample(output=output, task=example.task))
            line.append(f"{name} {score:.3f}")
        print(f"  홀드아웃 {index}/{len(test)}: " + " | ".join(line))

    print()
    print(f"{'조건':8} {'ROUGE-L 평균':>12} {'표준편차':>9}")
    means = {}
    for name in order:
        values = scores[name]
        means[name] = statistics.fmean(values)
        sd = statistics.stdev(values) if len(values) > 1 else 0.0
        print(f"{name:8} {means[name]:12.3f} {sd:9.3f}")

    # 진단: 생성된 글이 목표 길이에 다가가는지 본다. expert 가 base 를 못
    # 넘길 때 원인이 두 가지로 갈린다 - (a) 축이 형식을 못 바꿨다,
    # (b) 형식은 맞췄는데 ROUGE-L 이 보상하는 내용 겹침이 안 올랐다.
    # 이걸 구분하지 않고 고치려 들면 엉뚱한 곳을 손댄다.
    target_stats = corpus_stats(test)
    print()
    print("길이 진단 (목표에 다가갔는가)")
    print(f"{'조건':8} {'단어/답변':>10} {'문장/답변':>10} {'목표와 차이':>12}")
    print(f"{'목표':8} {target_stats['words_per_answer']:10.1f} "
          f"{target_stats['sentences_per_answer']:10.1f} {'-':>12}")
    length_gap = {}
    for name in order:
        stats = corpus_stats(generated[name])
        gap = stats["words_per_answer"] - target_stats["words_per_answer"]
        length_gap[name] = round(gap, 1)
        print(f"{name:8} {stats['words_per_answer']:10.1f} "
              f"{stats['sentences_per_answer']:10.1f} {gap:+12.1f}")

    wins = sum(1 for e, b in zip(scores["expert"], scores["base"]) if e > b)
    print()
    print(f"문서별 비교: expert 가 base 보다 높은 문서 {wins}/{len(test)}개")
    print(f"expert - base = {means['expert'] - means['base']:+.3f}")
    print(f"anti  - base = {means['anti'] - means['base']:+.3f}")
    print()
    if means["expert"] > means["base"] and means["anti"] < means["base"]:
        print("판정: 축이 방향을 갖는다 (expert > base > anti).")
    elif means["expert"] > means["base"]:
        print("판정: expert 가 base 보다 높지만 anti 도 base 보다 높다.")
        print("      지시문을 더 붙인 효과일 수 있어 축 추정이 맞았다고 단정할 수 없다.")
    else:
        print("판정: expert 가 base 를 못 넘었다. 추출이 실패했다고 보고한다.")

    return {
        "persona": persona_name,
        "n_train": n_train,
        "n_test": n_test,
        "task_description": report.task_description,
        "axes": [
            {
                "name": a.name,
                "description": a.description,
                "author_value": a.author_value,
                "values": [
                    {"value": v.value, "instruction": v.instruction} for v in a.values
                ],
            }
            for a in report.axes
        ],
        "prompts": prompts,
        "target_stats": target_stats,
        "length_gap": length_gap,
        "means": means,
        "per_document": scores,
        "expert_beats_base_docs": wins,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--persona", default="short", choices=sorted(PERSONAS))
    parser.add_argument("--train", type=int, default=5, help="축 추출에 쓸 예시 수")
    parser.add_argument("--test", type=int, default=6, help="홀드아웃 문서 수")
    parser.add_argument("--out", default=None, help="결과 JSON 경로")
    args = parser.parse_args()

    if not MACSUM_VAL.exists():
        raise SystemExit(f"MACSum 데이터가 없다: {MACSUM_VAL}")

    result = run(args.persona, args.train, args.test)

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else RESULTS / f"expert_prompt_{args.persona}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

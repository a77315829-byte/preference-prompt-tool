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
    form_anchor,
    form_distance,
    LENGTH_ANCHOR_KEYS,
    selective_form_anchor,
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

    expert_prompt = build_prompt(domain, report.author_combo())
    anchor = form_anchor(train)

    # 모델 기본 출력의 형식을 직접 잰다. 한 사람의 글만 보면 "무엇에 비해
    # 긴가"를 알 수 없으니, 과제 서술만 준 프롬프트로 학습 과제를 풀게 해
    # 기준점을 만든다. 홀드아웃이 아니라 학습 쪽 과제를 쓰므로 누출이 없다.
    print("모델 기본 출력 측정 중...")
    default_outputs = [
        ExpertExample(
            output=generate_all_with_prompts(
                [domain.task_description], example.task, model=MODEL, temperature=0.0
            )[0],
            task=example.task,
        )
        for example in train
    ]
    selective, selected_keys = selective_form_anchor(train, default_outputs)
    # 길이 계열만 쓴 앵커. 넓힌 항목(불릿·문단·유보·숫자·1인칭)이 실제로
    # 보탬이 되는지 두 조건의 차이로 잰다. 저자끼리는 이 항목들이 갈리지
    # 않지만 모델 기본값과는 갈리므로, 이 말뭉치에서도 비교가 성립한다.
    selective_len, selected_len_keys = selective_form_anchor(
        train, default_outputs, keys=LENGTH_ANCHOR_KEYS
    )
    print("길이 전용 앵커  :", selective_len or "(없음)")
    print("모델 기본 형식:", corpus_stats(default_outputs))
    print("저자 형식      :", corpus_stats(train))
    print("고른 항목      :", selected_keys or "(없음 - 기본값과 차이가 작다)")
    print("선별 앵커      :", selective or "(없음)")
    prompts = {
        "base": domain.task_description,
        # 어블레이션의 핵심 조건. 과제 서술 + 코드로 잰 수치만 주고 축
        # 지시문은 전부 뺀다. 이게 anchored 와 비슷하면 축은 아무것도
        # 기여하지 않는다는 뜻이고, 그러면 이 기능의 주장은 "저자의 글
        # 길이를 재서 맞춘다"로 줄어든다.
        "anchor_only": (
            (domain.task_description + "\n" + anchor)
            if anchor
            else domain.task_description
        ),
        # 선별 앵커. 저자가 모델 기본값과 실제로 다른 항목만 지시한다.
        "selective_len": (
            (domain.task_description + "\n" + selective_len)
            if selective_len
            else domain.task_description
        ),
        "selective": (
            (domain.task_description + "\n" + selective)
            if selective
            else domain.task_description
        ),
        "expert": expert_prompt,
        # 축 + 측정한 형식 수치. 축 지시문은 LLM 이 수치를 형용사로 번역한
        # 결과이고 그 번역이 양방향으로 틀렸다. 수치를 직접 주면 그 왕복이
        # 사라지는지 본다. 길이가 맞는 것은 당연하므로 축의 기여와 반드시
        # 구분해서 읽어야 한다.
        "anchored": (expert_prompt + "\n" + anchor) if anchor else expert_prompt,
        "anti": build_prompt(domain, _anti_combo(report)),
    }
    print("형식 수치 앵커:", anchor or "(없음)")
    print("조립된 전문가 프롬프트:")
    print(prompts["expert"])
    print()

    scores: dict[str, list[float]] = {name: [] for name in prompts}
    generated: dict[str, list[ExpertExample]] = {name: [] for name in prompts}
    order = list(prompts)
    for index, example in enumerate(test, start=1):
        outputs = generate_all_with_prompts(
            [prompts[name] for name in order],
            example.task,
            model=MODEL,
            temperature=0.0,
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
    length_gap, form_dist = {}, {}
    for name in order:
        stats = corpus_stats(generated[name])
        gap = stats["words_per_answer"] - target_stats["words_per_answer"]
        length_gap[name] = round(gap, 1)
        form_dist[name] = form_distance(generated[name], test)
        print(f"{name:8} {stats['words_per_answer']:10.1f} "
              f"{stats['sentences_per_answer']:10.1f} {gap:+12.1f}")

    # 형식 거리. 이 방법이 주장하는 것이 형식 복제이므로 여기서 이겨야 한다.
    print()
    print("형식 거리 (0에 가까울수록 이 저자의 형식에 가깝다)")
    for name in order:
        print(f"  {name:8} {form_dist[name]:.3f}")
    if form_dist["expert"] < form_dist["base"]:
        print(f"  -> expert 가 형식을 더 잘 맞췄다 "
              f"({form_dist['base']:.3f} -> {form_dist['expert']:.3f})")
    else:
        print("  -> expert 가 형식조차 못 맞췄다. 축 지시문이 약하다는 뜻이다.")

    wins = sum(1 for e, b in zip(scores["expert"], scores["base"]) if e > b)
    print()
    print(f"문서별 비교: expert 가 base 보다 높은 문서 {wins}/{len(test)}개")
    print(f"expert - base = {means['expert'] - means['base']:+.3f}")
    print(f"anti  - base = {means['anti'] - means['base']:+.3f}")
    print()
    print()
    print("어블레이션: 축이 수치 앵커 이상을 하는가")
    print(f"{'조건':12} {'형식 거리':>10} {'ROUGE-L':>9}")
    for name in ("base", "anchor_only", "selective_len", "selective", "anchored", "expert"):
        print(f"{name:12} {form_dist[name]:10.3f} {means[name]:9.3f}")
    form_gain = form_dist["anchor_only"] - form_dist["anchored"]
    rouge_gain = means["anchored"] - means["anchor_only"]
    print(f"  축의 기여: 형식 거리 {form_gain:+.3f} / ROUGE-L {rouge_gain:+.3f}")
    print("  (형식 거리는 낮을수록 좋으므로 양수가 축의 이득)")
    # 3분기로 읽는다. 처음엔 "기여 없음"과 "해를 끼침"을 한 덩어리로 봐서
    # 축이 형식을 망친 경우까지 "기여한다"고 찍었다.
    if form_gain < -0.02:
        print("  -> 축이 형식을 오히려 망친다. 수치 앵커만 쓰는 쪽이 낫다.")
        if rouge_gain > 0.01:
            print("     (다만 ROUGE-L 은 올랐다. 형식을 버리고 내용을 얻은 셈이다.)")
    elif form_gain <= 0.02 and abs(rouge_gain) <= 0.01:
        print("  -> 축은 수치 앵커 위에 기여하지 않는다. 주장을 길이 맞추기로 줄여야 한다.")
    else:
        print("  -> 축이 수치 앵커 위에 추가로 기여한다.")
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
        "form_distance": form_dist,
        "selected_anchor_keys": selected_keys,
        "selected_length_only_keys": selected_len_keys,
        "selective_anchor": selective,
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

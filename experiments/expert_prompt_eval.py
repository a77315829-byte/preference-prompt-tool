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
import math
import random
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
    anchor_text,
    calibrate_targets,
    ratio_anchor,
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


# 분할 전에 섞을 때 쓰는 시드. 고정해야 재현된다.
SPLIT_SEED = 0


def load_persona_examples(
    persona: dict[str, str], limit: int, shuffle: bool = True
) -> list[ExpertExample]:
    """이 속성 조합으로 쓰인 (원문, 사람 요약) 쌍을 모은다.

    **섞어서 돌려준다.** 섞지 않고 앞에서 잘라 쓰다가 낭패를 봤다.
    MACSum 요약 길이는 원문 길이를 따라가고 레코드가 정렬돼 있어서,
    앞 8개(학습)와 다음 14개(홀드아웃)의 평균 길이가 체계적으로 달랐다
    (long 에서 98.5 대 128.4 단어). 그 결과 "모델이 큰 길이 목표에
    미달한다"는 엉뚱한 결론을 냈다 - 실제로는 학습에서 잰 98단어를
    요청해 97.9단어를 받은, 거의 완벽한 준수였다.
    """
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
        if not shuffle and len(examples) >= limit:
            break
    if shuffle:
        random.Random(SPLIT_SEED).shuffle(examples)
    return examples[:limit]


def sign_test_p(wins: int, total: int) -> float:
    """문서별 페어드 비교의 양측 부호검정 p 값.

    왜 필요한가: 표본이 작고 표준편차가 평균 차이보다 큰 경우가 많아
    평균만으로는 우위를 주장할 수 없다. 이 프로젝트는 비교군 A/B/D 에서
    이미 "5개 중 4개" 같은 페어드 수치를 보고하는데, 그 수치가 우연으로
    나올 확률까지 적어두면 읽는 사람이 판단할 수 있다.

    새 의존성 없이 이항분포로 정확히 계산한다(귀무가설 p=0.5).
    """
    if total == 0:
        return 1.0
    # 관측값만큼 또는 그보다 극단적인 경우의 확률을 양쪽으로 더한다.
    extreme = min(wins, total - wins)
    tail = sum(math.comb(total, k) for k in range(extreme + 1)) / (2 ** total)
    return min(1.0, 2 * tail)


def _anti_combo(report) -> dict[str, str]:
    """각 축에서 이 사람의 값이 아닌 값을 고른다."""
    combo = {}
    for axis in report.axes:
        others = [v.value for v in axis.values if v.value != axis.author_value]
        combo[axis.name] = others[0] if others else axis.author_value
    return combo


# 조건을 골라 돌릴 수 있게 한다. 표본을 키울 때 전 조건을 다 돌리면
# 호출 수가 조건 수만큼 곱해진다.
ALL_CONDITIONS = (
    "base", "anchor_only", "selective_len", "selective", "calibrated",
    "ratio", "anchored", "expert",
)
CORE_CONDITIONS = ("base", "anchor_only", "ratio")


def run(
    persona_name: str,
    n_train: int,
    n_test: int,
    conditions: tuple[str, ...] = ALL_CONDITIONS,
) -> dict:
    persona = PERSONAS[persona_name]
    # 섞어서 뽑으므로 후보 전체를 모은 뒤 잘라낸다.
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

    # 보정 루프. 학습 과제로 선별 앵커를 한 번 써보고, 요청값 대비 실제
    # 산출값의 비율로 요청값을 역보정한다. 모델이 큰 목표에 미달하는
    # 성질을 측정으로 상쇄한다. 학습 과제만 쓰므로 누출이 없다.
    print("보정 탐침 생성 중...")
    probe_prompt = (
        (domain.task_description + "\n" + selective) if selective else domain.task_description
    )
    probe_outputs = [
        ExpertExample(
            output=generate_all_with_prompts(
                [probe_prompt], example.task, model=MODEL, temperature=0.0
            )[0],
            task=example.task,
        )
        for example in train
    ]
    author_stats = corpus_stats(train)
    probe_stats = corpus_stats(probe_outputs)
    corrected, factors = calibrate_targets(
        author_stats, probe_stats, tuple(selected_keys) or LENGTH_ANCHOR_KEYS
    )
    calibrated = anchor_text(corrected)
    print(f"  요청 -> 실제: 단어 {author_stats['words_per_answer']:.1f} -> "
          f"{probe_stats['words_per_answer']:.1f}, 문장 "
          f"{author_stats['sentences_per_answer']:.1f} -> "
          f"{probe_stats['sentences_per_answer']:.1f}")
    print("  보정 배율:", factors)
    print("  보정 앵커:", calibrated or "(없음)")
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
        # 보정된 앵커. 목표를 맞추려면 얼마를 요청해야 하는지 역산한 값.
        "calibrated": (
            (domain.task_description + "\n" + calibrated)
            if calibrated
            else domain.task_description
        ),
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
    prompts = {name: text for name, text in prompts.items() if name in conditions}
    print("돌리는 조건:", list(prompts) + (["ratio"] if "ratio" in conditions else []))
    print("형식 수치 앵커:", anchor or "(없음)")
    # --core 로 조건을 걸러내면 expert 가 없을 수 있다. 조건 필터를 넣고
    # 이 출력을 안 고쳐서 KeyError 로 죽었다.
    for shown in ("expert", "ratio", "anchor_only", "base"):
        if shown in prompts:
            print(f"조립된 프롬프트 ({shown}):")
            print(prompts[shown])
            break
    print()

    scores: dict[str, list[float]] = {name: [] for name in prompts}
    generated: dict[str, list[ExpertExample]] = {name: [] for name in prompts}
    print("압축률 기반 앵커 예시:", ratio_anchor(train, test[0].task) or "(없음)")
    order = list(prompts) + (["ratio"] if "ratio" in conditions else [])
    if "ratio" in conditions:
        scores["ratio"] = []
        generated["ratio"] = []
    for index, example in enumerate(test, start=1):
        # ratio 조건만 과제별로 프롬프트가 달라진다. 목표를 원문 길이에
        # 곱해서 구하기 때문이다.
        per_task = dict(prompts)
        ratio_line = ratio_anchor(train, example.task)
        per_task["ratio"] = (
            (domain.task_description + "\n" + ratio_line)
            if ratio_line
            else domain.task_description
        )
        outputs = generate_all_with_prompts(
            [per_task[name] for name in order],
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
    # 조건 필터(--core)로 걸러진 이름을 참조하면 KeyError 로 죽는다.
    # 실제로 두 군데에서 그랬고, 표가 다 찍힌 뒤 결과 저장 직전에 죽어서
    # 눈으로는 성공처럼 보였다.
    best = min(order, key=lambda name: form_dist[name])
    print(f"  -> 형식을 가장 잘 맞춘 조건: {best} ({form_dist[best]:.3f})")
    if best == "base":
        print("     기준선이 가장 가깝다. 이 저자에게서는 얻을 것이 없다는 뜻이다.")

    # 표본이 작고 표준편차가 평균 차이보다 큰 경우가 많아, 평균만으로는
    # 우위를 주장할 수 없다. 이 프로젝트가 비교군 A/B/D 에서 쓴 것과 같은
    # 문서별 페어드 비교를 모든 조건에 대해 낸다.
    print()
    print(f"문서별 페어드 비교 (base 보다 높은 문서 / {len(test)})")
    paired = {}
    for name in order:
        if name == "base":
            continue
        count = sum(1 for x, b in zip(scores[name], scores["base"]) if x > b)
        paired[name] = count
        p_value = sign_test_p(count, len(test))
        mark = "유의" if p_value < 0.05 else "판정보류"
        print(
            f"  {name:14} {count:2d}/{len(test)}  평균차 {means[name]-means['base']:+.3f}"
            f"  p={p_value:.4f} {mark}"
        )
    wins = paired.get("expert", 0)
    if "expert" in order:
        print(f"expert - base = {means['expert'] - means['base']:+.3f}")
    if "anti" in order:
        print(f"anti  - base = {means['anti'] - means['base']:+.3f}")
    print()
    print()
    print("어블레이션: 축이 수치 앵커 이상을 하는가")
    print(f"{'조건':12} {'형식 거리':>10} {'ROUGE-L':>9}")
    for name in order:
        print(f"{name:12} {form_dist[name]:10.3f} {means[name]:9.3f}")
    if "anchored" not in order or "anchor_only" not in order:
        print("  (어블레이션 판정 생략 - 해당 조건을 돌리지 않았다)")
        form_gain = rouge_gain = 0.0
    else:
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
    if "expert" not in order or "anti" not in order:
        pass
    elif means["expert"] > means["base"] and means["anti"] < means["base"]:
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
        "calibration_factors": factors,
        "calibrated_targets": corrected,
        "selective_anchor": selective,
        "means": means,
        "per_document": scores,
        "expert_beats_base_docs": wins,
        "paired_wins_vs_base": paired,
        "sign_test_p": {k: round(sign_test_p(v, len(test)), 5) for k, v in paired.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--persona", default="short", choices=sorted(PERSONAS))
    parser.add_argument("--train", type=int, default=5, help="축 추출에 쓸 예시 수")
    parser.add_argument("--test", type=int, default=6, help="홀드아웃 문서 수")
    parser.add_argument("--out", default=None, help="결과 JSON 경로")
    parser.add_argument(
        "--core", action="store_true",
        help="핵심 조건만 (base / 절대 앵커 / 압축률 앵커). 표본을 키울 때 쓴다.",
    )
    args = parser.parse_args()

    if not MACSUM_VAL.exists():
        raise SystemExit(f"MACSum 데이터가 없다: {MACSUM_VAL}")

    result = run(
        args.persona, args.train, args.test,
        conditions=CORE_CONDITIONS if args.core else ALL_CONDITIONS,
    )

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else RESULTS / f"expert_prompt_{args.persona}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    # --out 으로 상대 경로를 받으면 relative_to 가 터진다. 파일은 이미
    # 써진 뒤라서 저장은 됐는데 마지막 출력만 죽어 실패처럼 보였다.
    try:
        shown = out.resolve().relative_to(ROOT)
    except ValueError:
        shown = out
    print(f"\n결과 저장: {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

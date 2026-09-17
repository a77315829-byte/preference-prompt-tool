"""넓힌 형식 지표가 MACSum 페르소나 사이에서 실제로 갈리는지 잰다.

**왜 필요한가.** 형식 어휘를 넓혔는데(글머리 기호 비율, 유보 표현 밀도,
숫자 밀도, 1인칭 밀도, 문단 수) 앵커가 나아지지 않았다. 원인이 두 가지로
갈린다.

  (가) 지표가 저자를 구분하지 못한다 - 지표를 갈아야 한다.
  (나) MACSum 페르소나가 길이 말고는 문체가 균질하다 - 지표는 멀쩡한데
       걸릴 신호가 데이터에 없다. 그러면 필요한 건 다른 지표가 아니라
       문체가 갈리는 코퍼스다.

두 경우의 다음 행동이 정반대라서 그냥 두면 안 된다. 그런데 API 없이
가를 수 있다 - **저자들 사이의 차이가 저자 안의 흔들림보다 큰지**만
보면 된다. 크면 (가), 작으면 (나)다.

**분모를 무엇으로 두느냐가 중요하다.** 처음엔 답변 하나하나의 분산으로
나눴는데 그러면 대조군인 words_per_answer(34/65/97 단어로 뚜렷이 갈린다)
조차 0.48 로 탈락했다. 저자 안의 흔들림이 크기 때문인데 - 같은 사람도
짧은 기사엔 40단어, 긴 기사엔 258단어를 쓴다 - **앵커는 답변 하나가 아니라
학습 예시의 평균을 쓴다.** 그러니 분모는 개별 분산이 아니라 n개로 추정한
평균의 분산(표준오차의 제곱 = 개별분산/n)이어야 한다. 둘 다 출력하되
판정은 평균 기준으로 한다.

MACSum 이 아닌 코퍼스도 같은 잣대로 볼 수 있게 해뒀다. MACSum 에서
"신호가 없다"는 판정을 내렸으면 신호가 있는 곳에서 같은 지표가 살아나는지
확인해야 판정이 완성된다.

실행:
    python -m experiments.form_feature_spread
    python -m experiments.form_feature_spread --macsum-part macdial
    python -m experiments.form_feature_spread --site cooking
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
from pathlib import Path

from agents.expert_onboarding import ExpertExample, corpus_stats
from experiments.expert_prompt_eval import PERSONAS, load_persona_examples

ROOT = Path(__file__).resolve().parent.parent

# 저자마다 쓰는 예시 수. 학습 12개보다 넉넉히 잡아야 저자 안 분산이
# 표본 부족으로 과대평가되지 않는다.
PER_PERSONA = 40

# 이 값을 넘으면 그 특징으로 저자가 갈린다고 본다. 추정한 평균들이
# 그 평균의 오차보다 2배는 넓게 퍼져야 앵커에 적을 값을 신뢰할 수 있다.
DISCRIMINATIVE_MIN = 2.0

# 앵커를 만들 때 실제로 쓰는 학습 예시 수. 판정은 이 표본 크기에서의
# 평균 추정 정밀도를 기준으로 한다.
TRAIN_N = 12

# 길이 계열은 이미 효과가 확인됐다. 대조군으로 같이 출력해서 이 지표
# 자체가 갈리는 특징을 잡아내긴 하는지 확인한다.
# 압축률 키 이름은 corpus_stats 가 쓰는 것을 그대로 따른다.
LENGTH_KEYS = (
    "words_per_answer",
    "sentences_per_answer",
    "answer_to_task_word_ratio",
    "words_per_sentence",
)
WIDENED_KEYS = (
    "bullet_line_ratio",
    "paragraphs_per_answer",
    "hedges_per_100w",
    "numerals_per_100w",
    "first_person_per_100w",
)


def per_example_values(examples: list[ExpertExample], key: str) -> list[float]:
    """예시 하나씩 따로 재서 저자 안의 흔들림을 본다."""
    return [float(corpus_stats([example]).get(key, 0.0)) for example in examples]


def spread_ratios(groups: list[list[float]]) -> tuple[float, float]:
    """(답변 하나 기준, 학습 평균 기준) 두 판별력비를 돌려준다.

    평균 기준은 분모를 개별분산/TRAIN_N 으로 둔다 - 앵커가 신뢰해야 하는
    것은 개별 답변이 아니라 학습 예시로 추정한 평균이기 때문이다.
    """
    means = [statistics.fmean(values) for values in groups if values]
    if len(means) < 2:
        return 0.0, 0.0
    between = statistics.pvariance(means)
    within = statistics.fmean(
        [statistics.pvariance(values) for values in groups if len(values) > 1]
    )
    if within == 0:
        # 저자 안이 완전히 고정된 경우. 저자 간에도 같으면 신호 자체가 없다.
        return (0.0, 0.0) if between == 0 else (float("inf"), float("inf"))
    return between / within, between / (within / TRAIN_N)


def macsum_corpora(part: str) -> dict[str, list[ExpertExample]]:
    """MACSum 페르소나별 코퍼스.

    macdoc 은 검증에 쓴 그 분할을 그대로 쓴다(누출 없음 - 여기서는
    생성을 하지 않고 사람 요약만 재므로 학습·홀드아웃 구분이 의미 없다).
    macdial 은 topic·speaker 가 항상 붙어 있어 조합을 고정할 수 없으므로
    length 로만 묶는다 - 그 안의 주제 변동은 노이즈로 들어간다.
    """
    if part == "macdoc":
        return {
            name: load_persona_examples(persona, PER_PERSONA)
            for name, persona in PERSONAS.items()
        }

    groups: dict[str, list[ExpertExample]] = collections.defaultdict(list)
    for split in ("train", "val", "test"):
        path = ROOT / "data" / "macsum" / "dataset" / part / f"{split}.json"
        if not path.exists():
            continue
        for record in json.loads(path.read_text(encoding="utf-8")):
            source = " ".join(record["source"])
            for reference in record["references"]:
                length = reference["control_attribute"].get("length")
                if length:
                    groups[length].append(
                        ExpertExample(output=reference["summary"], task=source)
                    )
    return {name: groups[name] for name in ("short", "normal", "long") if name in groups}


def stackexchange_corpora(site: str) -> dict[str, list[ExpertExample]]:
    """Stack Exchange 저자별 코퍼스. `expert_corpus_se.py` 가 받아둔 캐시."""
    matches = sorted((ROOT / "data" / "stackexchange").glob(f"{site}_a*_n*.json"))
    if not matches:
        raise SystemExit(
            f"{site} 코퍼스가 없다. 먼저 받을 것: "
            f"python -m experiments.expert_corpus_se --site {site}"
        )
    corpus = json.loads(matches[-1].read_text(encoding="utf-8"))
    print(f"코퍼스: {matches[-1].relative_to(ROOT)}")
    return {
        f"u{author['user_id']}": [
            ExpertExample(output=pair["answer"], task=pair["task"])
            for pair in author["pairs"]
        ]
        for author in corpus["authors"]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--macsum-part", default="macdoc", choices=("macdoc", "macdial"),
        help="MACSum 의 어느 쪽을 볼지",
    )
    parser.add_argument(
        "--site", default=None,
        help="주면 MACSum 대신 이 Stack Exchange 코퍼스를 본다",
    )
    args = parser.parse_args()

    if args.site:
        corpora = stackexchange_corpora(args.site)
        label = f"Stack Exchange {args.site} (저자별)"
    else:
        corpora = macsum_corpora(args.macsum_part)
        label = f"MACSum {args.macsum_part} (페르소나별)"

    print(f"{label}")
    for name, examples in corpora.items():
        print(f"  {name}: 예시 {len(examples)}개")
    print()

    names = list(corpora)
    header = (
        f"{'특징':26} "
        + " ".join(f"{name:>10}" for name in names)
        + f"{'답변기준':>10}{'평균기준':>10}"
    )
    verdicts: dict[str, float] = {}
    flat: list[str] = []

    for group_label, keys in (("길이 계열 (대조군)", LENGTH_KEYS), ("넓힌 지표", WIDENED_KEYS)):
        print(f"[{group_label}]")
        print(header)
        for key in keys:
            groups = [per_example_values(corpora[name], key) for name in names]
            raw, pooled = spread_ratios(groups)
            verdicts[key] = pooled
            values_seen = [v for group in groups for v in group]
            if values_seen and max(values_seen) == min(values_seen):
                flat.append(key)
            means = " ".join(
                f"{statistics.fmean(values):10.3f}" if values else f"{'-':>10}"
                for values in groups
            )
            print(f"{key:26} {means} {raw:10.2f}{pooled:10.2f}")
        print()

    if flat:
        print(f"코퍼스 전체에서 값이 한 번도 변하지 않은 특징: {', '.join(flat)}")
        print("이 특징들은 어떤 앵커에 넣어도 저자를 구분할 수 없다.")
        print()

    passing = [k for k in WIDENED_KEYS if verdicts[k] >= DISCRIMINATIVE_MIN]
    control = [k for k in LENGTH_KEYS if verdicts[k] >= DISCRIMINATIVE_MIN]

    print(f"판별력비 {DISCRIMINATIVE_MIN} 이상:")
    print(f"  길이 계열 {len(control)}/{len(LENGTH_KEYS)}: {', '.join(control) or '없음'}")
    print(f"  넓힌 지표 {len(passing)}/{len(WIDENED_KEYS)}: {', '.join(passing) or '없음'}")
    print()

    if not control:
        print("판정 불가. 대조군인 길이 계열조차 안 갈린다 - 측정 코드나")
        print("코퍼스 구성을 먼저 의심해야 한다.")
    elif passing:
        print("가설 (가). 넓힌 지표 중 일부가 이 코퍼스에서 저자를 가른다.")
        print(f"앵커에 넣어 시험할 값이 있다: {', '.join(passing)}")
    else:
        print("가설 (나). 길이 계열은 갈리는데 넓힌 지표는 하나도 안 갈린다.")
        print("지표가 나쁘다는 증거가 아니라, 이 코퍼스에 걸릴 문체 신호가")
        print("없다는 뜻이다. 다음 단계는 지표 교체가 아니라 문체가 실제로")
        print("갈리는 코퍼스 확보다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

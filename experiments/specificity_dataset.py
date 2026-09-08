"""specificity 축의 실제 정답 라벨 데이터셋 (CLAUDE.md v2, 우선순위 3).

6주차에 "specificity는 코드로 판별 불가"라고 결론 내릴 때 썼던 것과 같은
MACSum control_attribute.specificity 라벨을 재사용한다. 이번엔 통계만
뽑는 게 아니라 (텍스트, 라벨) 쌍 자체를 학습/평가용으로 뽑아둔다 - 학습형
분류기와 LLM 판정기 둘 다 여기서 나온 동일한 train/test 분할로 채점해야
공정하게 비교된다.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

LABELS = ("normal", "high")  # MACSum specificity는 이 두 값만 씀 (macdoc 기준)


@dataclass
class Example:
    text: str
    label: str
    source: str  # 원문 - "구체성"이 원문 대비 상대적 개념일 수 있어 판정기에 같이 준다


def load_examples(macdoc_dir: str = "data/macsum/dataset/macdoc") -> list[Example]:
    examples: list[Example] = []
    for split in ("train", "val", "test"):
        data = json.loads(Path(macdoc_dir, f"{split}.json").read_text(encoding="utf-8"))
        for record in data:
            source = " ".join(record["source"])
            for ref in record["references"]:
                label = ref["control_attribute"].get("specificity", "")
                if label in LABELS:
                    examples.append(Example(text=ref["summary"], label=label, source=source))
    return examples


def train_test_split(examples: list[Example], test_ratio: float = 0.2, seed: int = 0) -> tuple[list[Example], list[Example]]:
    rng = random.Random(seed)
    shuffled = examples.copy()
    rng.shuffle(shuffled)
    n_test = int(len(shuffled) * test_ratio)
    return shuffled[n_test:], shuffled[:n_test]


if __name__ == "__main__":
    examples = load_examples()
    train, test = train_test_split(examples)
    counts = {label: sum(1 for e in examples if e.label == label) for label in LABELS}
    print(f"total={len(examples)} counts={counts} train={len(train)} test={len(test)}")

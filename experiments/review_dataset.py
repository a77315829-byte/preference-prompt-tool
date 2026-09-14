"""고객 리뷰 작성 도메인의 sentiment 축 정답 라벨 데이터셋.

Yelp Review Full (Yelp/yelp_review_full, HuggingFace) - 실제 사람이 쓴 리뷰
65만 건 + 1~5점 별점. 게이팅 없이 바로 받을 수 있고, datasets 라이브러리
없이 HF datasets-server의 rows API(순수 HTTP+JSON)로만 받는다 - 새 의존성
추가 없음.

별점 -> sentiment 라벨: 1~2점=negative, 3점=neutral, 4~5점=positive.
"""

from __future__ import annotations

import json
import random
import urllib.request
from dataclasses import dataclass
from pathlib import Path

CACHE_PATH = Path("data/yelp_review_sample.json")
LABELS = ("negative", "neutral", "positive")


@dataclass
class Example:
    text: str
    stars: int  # 1~5
    label: str  # negative/neutral/positive


def _star_to_label(stars: int) -> str:
    if stars <= 2:
        return "negative"
    if stars == 3:
        return "neutral"
    return "positive"


def _fetch_page(offset: int, length: int = 100) -> list[dict]:
    url = (
        "https://datasets-server.huggingface.co/rows?dataset=Yelp%2Fyelp_review_full"
        f"&config=yelp_review_full&split=train&offset={offset}&length={length}"
    )
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)["rows"]


def load_examples(n: int = 3000, seed: int = 0) -> list[Example]:
    """캐시가 있으면 그걸 쓰고, 없으면 HF에서 받아 캐시한다."""
    if CACHE_PATH.exists():
        raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return [Example(**e) for e in raw]

    rows = []
    offset = 0
    while len(rows) < n:
        rows.extend(_fetch_page(offset))
        offset += 100

    examples = [
        Example(text=r["row"]["text"], stars=r["row"]["label"] + 1, label=_star_to_label(r["row"]["label"] + 1))
        for r in rows[:n]
    ]

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(
        json.dumps([e.__dict__ for e in examples], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return examples


def train_test_split(examples: list[Example], test_ratio: float = 0.2, seed: int = 0):
    rng = random.Random(seed)
    shuffled = examples.copy()
    rng.shuffle(shuffled)
    n_test = int(len(shuffled) * test_ratio)
    return shuffled[n_test:], shuffled[:n_test]


if __name__ == "__main__":
    examples = load_examples()
    counts = {label: sum(1 for e in examples if e.label == label) for label in LABELS}
    print(f"total={len(examples)} counts={counts}")

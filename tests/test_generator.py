"""3주차 검증용: generator.py가 실제 MACSum 원문에 대해 캐싱까지 포함해
정상 동작하는지 확인."""

import json
import time
from pathlib import Path

from dotenv import load_dotenv

from engine.domain_loader import load_domain
from engine.generator import generate

load_dotenv()


def main() -> None:
    domain = load_domain("domains/summarization.yaml")
    record = json.loads(
        Path("data/macsum/dataset/macdoc/val.json").read_text(encoding="utf-8")
    )[0]
    source_text = " ".join(record["source"])
    combo = {"length": "short", "extractiveness": "normal", "specificity": "normal", "topic": ""}

    t0 = time.time()
    out1 = generate(domain, source_text, combo, model="openai/gpt-4.1-mini")
    t1 = time.time()
    out2 = generate(domain, source_text, combo, model="openai/gpt-4.1-mini")
    t2 = time.time()

    print("first call (API):", f"{t1 - t0:.2f}s")
    print(out1)
    print()
    print("second call (cache):", f"{t2 - t1:.2f}s")
    assert out1 == out2, "cache mismatch"
    print("cache hit OK, identical output")


if __name__ == "__main__":
    main()

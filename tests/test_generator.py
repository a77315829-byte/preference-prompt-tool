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
    combo = {"length": "short", "extractiveness": "normal", "topic": ""}

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


# --- 자동 회귀 테스트 ------------------------------------------------------

import pytest

COMBO = {"length": "short", "extractiveness": "normal", "topic": ""}


@pytest.mark.api
@pytest.mark.macsum
def test_second_call_hits_cache(model, macsum_source, tmp_path) -> None:
    """절대 규칙 2: 같은 입력은 두 번 호출하지 않는다.

    실험을 수백 회 돌리므로 캐시가 깨지면 비용이 폭발한다. 캐시 디렉토리를
    격리해서 첫 호출이 반드시 API를 타게 만든 뒤, 두 번째가 같은 결과를
    즉시 돌려주는지 본다.
    """
    domain = load_domain("domains/summarization.yaml")

    t0 = time.time()
    first = generate(domain, macsum_source, COMBO, model=model, cache_dir=tmp_path)
    api_seconds = time.time() - t0

    t1 = time.time()
    second = generate(domain, macsum_source, COMBO, model=model, cache_dir=tmp_path)
    cache_seconds = time.time() - t1

    assert first == second
    assert first.strip()
    assert len(list(tmp_path.glob("*.json"))) == 1
    assert cache_seconds < api_seconds, f"API {api_seconds:.2f}s / 캐시 {cache_seconds:.2f}s"


@pytest.mark.api
@pytest.mark.macsum
def test_cache_key_follows_the_assembled_prompt(model, macsum_source, tmp_path) -> None:
    """캐시 키는 축조합이 아니라 조립된 프롬프트여야 한다.

    8주차에 고친 것이다. 축조합을 키로 쓰면 domains/*.yaml 문구를 고쳐도
    캐시가 무효화되지 않아, 실제로 보내는 내용과 저장된 응답이 어긋난다.
    """
    domain = load_domain("domains/summarization.yaml")
    generate(domain, macsum_source, COMBO, model=model, cache_dir=tmp_path)

    other = dict(COMBO, length="long")
    generate(domain, macsum_source, other, model=model, cache_dir=tmp_path)

    # 축 값이 다르면 조립된 프롬프트가 다르므로 캐시 파일도 따로 생긴다.
    assert len(list(tmp_path.glob("*.json"))) == 2

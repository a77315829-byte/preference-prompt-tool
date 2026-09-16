"""3주차 검증용: generator.py + persona.py 엔드투엔드.
같은 원문을 서로 다른 두 축조합으로 생성하고, 각 조합에 대응하는
페르소나가 (당연히) 자기 조합에 더 가까운 후보를 고르는지 확인한다."""

import json
from pathlib import Path

from dotenv import load_dotenv

from engine.domain_loader import load_domain
from engine.generator import generate
from experiments.persona import choose, load_personas

load_dotenv()


def _find_persona(personas, *, length: str):
    """원하는 축값을 가진 페르소나를 찾는다.

    MACSum 의 control_attribute 에는 6주차에 우리가 제외한 specificity 축이
    그대로 들어 있다. 딕셔너리 정확 비교로 찾으면 데이터 쪽 축 구성에
    묶이므로, 필요한 축만 보고 고른다.
    """
    return next(
        p for p in personas
        if p.combo.get("length") == length
        and p.combo.get("extractiveness") == "normal"
        and p.combo.get("topic", "") == ""
    )


def main() -> None:
    domain = load_domain("domains/summarization.yaml")
    record = json.loads(
        Path("data/macsum/dataset/macdoc/val.json").read_text(encoding="utf-8")
    )[0]
    source_text = " ".join(record["source"])
    personas = load_personas(record)

    short_persona = _find_persona(personas, length="short")
    long_persona = _find_persona(personas, length="long")

    short_candidate = generate(domain, source_text, short_persona.combo, model="openai/gpt-4.1-mini")
    long_candidate = generate(domain, source_text, long_persona.combo, model="openai/gpt-4.1-mini")

    print("[short candidate]", short_candidate)
    print()
    print("[long candidate]", long_candidate)
    print()

    pick_for_short_persona = choose(domain, short_persona, short_candidate, long_candidate, source_text)
    pick_for_long_persona = choose(domain, long_persona, short_candidate, long_candidate, source_text)

    print("short persona picks:", pick_for_short_persona, "(expect a)")
    print("long persona picks:", pick_for_long_persona, "(expect b)")


if __name__ == "__main__":
    main()


# --- 자동 회귀 테스트 ------------------------------------------------------

import pytest


@pytest.mark.macsum
def test_personas_come_from_real_macsum_attributes(macsum_record) -> None:
    """페르소나 하나 = MACSum 속성 조합 하나. API 없이 돈다.

    MACSum 의 control_attribute 에는 6주차에 우리가 제외한 specificity 축이
    그대로 들어 있다. 그 사실을 여기 고정해둔다 - 딕셔너리 정확 비교로
    페르소나를 찾는 코드가 조용히 깨지는 것을 막는다.
    """
    personas = load_personas(macsum_record)
    assert personas
    for persona in personas:
        assert persona.reference_summary.strip()
        assert {"length", "extractiveness"} <= set(persona.combo)
    assert any("specificity" in p.combo for p in personas)


@pytest.mark.api
@pytest.mark.macsum
def test_each_persona_picks_the_candidate_matching_its_own_axes(
    macsum_record, macsum_source, model
) -> None:
    """9주차 재설계의 핵심 검사.

    원래는 정답 요약과의 단어 겹침으로 페르소나의 선택을 대행했는데,
    원문을 그대로 발췌한 후보가 고유명사 덮침으로 우연히 이겨버려 엉뚱한
    축으로 수렴했다. checks 기반으로 바꾼 뒤에는 각 페르소나가 자기 축값에
    맞는 후보를 고른다. 그게 무너지면 모든 복원율 수치의 근거가 사라진다.
    """
    domain = load_domain("domains/summarization.yaml")
    personas = load_personas(macsum_record)
    short_persona = _find_persona(personas, length="short")
    long_persona = _find_persona(personas, length="long")

    short_candidate = generate(domain, macsum_source, short_persona.combo, model=model)
    long_candidate = generate(domain, macsum_source, long_persona.combo, model=model)

    assert choose(domain, short_persona, short_candidate, long_candidate, macsum_source) == "a"
    assert choose(domain, long_persona, short_candidate, long_candidate, macsum_source) == "b"

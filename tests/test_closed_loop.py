"""8주차 리스크 점검용: 선택 루프 전체(selector -> 실제 API 생성 ->
persona.choose 오라클 -> estimator.update)를 실제로 돌려서 숨겨진
페르소나 선호를 복원하는지 확인한다.

기존 테스트는 부품별 단위 테스트(3주차)이거나 합성 오라클(4~5주차)이었다.
이게 실제 생성 결과 + 실제 MACSum 답안지 기반 오라클로 도는 첫 엔드투엔드
폐루프 테스트다."""

import json
from pathlib import Path

from dotenv import load_dotenv

from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator
from engine.generator import generate
from engine.selector import UncertaintySelector
from experiments.persona import choose, load_personas

load_dotenv()

MODEL = "openai/gpt-4.1-mini"


def main() -> None:
    domain = load_domain("domains/summarization.yaml")
    record = json.loads(Path("data/macsum/dataset/macdoc/val.json").read_text(encoding="utf-8"))[0]
    source = " ".join(record["source"])

    personas = load_personas(record)
    persona = next(
        p
        for p in personas
        if p.combo.get("topic", "") == "" and p.combo["length"] == "long" and p.combo["extractiveness"] == "normal"
    )
    hidden = {"length": persona.combo["length"], "extractiveness": persona.combo["extractiveness"]}
    print("hidden persona combo:", hidden)
    print("reference summary:", persona.reference_summary)
    print()

    estimator = Estimator(domain)
    selector = UncertaintySelector(domain, seed=0)

    for i in range(8):
        combo_a, combo_b = selector.next_pair(estimator)
        cand_a = generate(domain, source, combo_a, model=MODEL)
        cand_b = generate(domain, source, combo_b, model=MODEL)
        winner = choose(domain, persona, cand_a, cand_b, source)
        estimator.update(Comparison(combo_a, combo_b, winner))

        so_far = {n: estimator.preferred_value(n) for n in estimator.enum_axis_names()}
        print(f"round {i + 1}: A={combo_a} B={combo_b} -> winner={winner} | so far: {so_far}")

    final = {n: estimator.preferred_value(n) for n in estimator.enum_axis_names()}
    print()
    print("hidden   :", hidden)
    print("recovered:", final)
    print("MATCH" if final == hidden else "MISMATCH")


if __name__ == "__main__":
    main()


# --- 자동 회귀 테스트 ------------------------------------------------------
# 실측 결과를 그대로 적어둔다. 문서 3개 x 페르소나 3개(자유 키워드 축
# 제외) = 9케이스를 8라운드씩 돌렸을 때:
#
#   완전복원 5/9 (56%), 축 단위 12/18 (67%)
#
# 축별로 갈린다. length=short 선호는 문서 3개에서 3번 다 정확히 복원되고,
# length=long 선호는 3번 중 2번 normal 로 수렴한다. 8라운드 안에서는
# 인접한 값(normal/long)을 가르기 어렵다는 뜻이다.
#
# 그래서 "모든 페르소나를 정확히 복원한다"를 테스트로 박지 않는다. 그건
# 사실이 아니다. 아래는 (1) 폐루프가 끝까지 도는지, (2) 안정적으로
# 복원되는 케이스가 계속 복원되는지를 잡는다. 보고되는 집계 수치
# (완전복원 80%)는 별도 실험이고 tests/test_reported_results.py 가 지킨다.

import pytest


def _run_loop(domain, source, persona, rounds: int, model: str) -> dict:
    estimator = Estimator(domain)
    selector = UncertaintySelector(domain, seed=0)
    for _ in range(rounds):
        combo_a, combo_b = selector.next_pair(estimator)
        cand_a = generate(domain, source, combo_a, model=model)
        cand_b = generate(domain, source, combo_b, model=model)
        estimator.update(
            Comparison(combo_a, combo_b, choose(domain, persona, cand_a, cand_b, source))
        )
    return {name: estimator.preferred_value(name) for name in estimator.enum_axis_names()}


def _persona_with(personas, length: str):
    return next(
        p for p in personas
        if p.combo.get("length") == length
        and p.combo.get("extractiveness") == "normal"
        and p.combo.get("topic", "") == ""
    )


@pytest.mark.api
@pytest.mark.macsum
def test_loop_recovers_the_short_persona(macsum_record, macsum_source, model) -> None:
    """selector -> 실제 생성 -> checks 기반 오라클 -> estimator 가 한 바퀴
    돌아 숨긴 선호를 복원하는지. short 선호는 실측에서 문서 3개 모두
    정확히 복원됐다."""
    domain = load_domain("domains/summarization.yaml")
    persona = _persona_with(load_personas(macsum_record), "short")
    hidden = {"length": "short", "extractiveness": "normal"}

    assert _run_loop(domain, macsum_source, persona, 8, model) == hidden


@pytest.mark.api
@pytest.mark.macsum
def test_loop_completes_for_a_hard_persona(macsum_record, macsum_source, model) -> None:
    """복원이 안 되는 케이스에서도 루프 자체는 끝까지 돌아야 한다.

    length=long 선호는 8라운드에서 normal 로 수렴하는 경우가 있다(실측
    3번 중 2번). 여기서는 그 결과를 단정하지 않고, 예외 없이 완주해서
    형식이 맞는 선호를 내놓는지만 본다.
    """
    domain = load_domain("domains/summarization.yaml")
    persona = _persona_with(load_personas(macsum_record), "long")

    learned = _run_loop(domain, macsum_source, persona, 8, model)
    assert set(learned) == {"length", "extractiveness"}
    assert learned["length"] in {"short", "normal", "long"}
    assert learned["extractiveness"] in {"normal", "high", "fully"}

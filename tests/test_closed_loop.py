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

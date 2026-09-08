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


def main() -> None:
    domain = load_domain("domains/summarization.yaml")
    record = json.loads(
        Path("data/macsum/dataset/macdoc/val.json").read_text(encoding="utf-8")
    )[0]
    source_text = " ".join(record["source"])
    personas = load_personas(record)

    short_persona = next(p for p in personas if p.combo == {
        "length": "short", "extractiveness": "normal", "specificity": "normal", "topic": ""
    })
    long_persona = next(p for p in personas if p.combo == {
        "length": "long", "extractiveness": "normal", "specificity": "normal", "topic": ""
    })

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

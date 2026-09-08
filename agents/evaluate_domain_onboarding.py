"""도메인 온보딩 에이전트 평가 (CLAUDE.md v2, 우선순위 4).

MACSum 문서 여러 개를, 라벨(control_attribute) 없이 "같은 원문에 대한
서로 다른 결과물 여러 개"로만 에이전트에게 준다. 사람이 이미 확정한
summarization.yaml 축 구성(length, extractiveness, topic - specificity는
6주차에 판별력 없어 제외)이 정답이다. 확인할 것:

- length·extractiveness처럼 실제로 판별력 있는 축을 스스로 찾아내는가
- specificity처럼 판별력 없는 축을 제안하더라도 스스로 걸러내는가
  (또는 애초에 제안조차 안 하는가)

에이전트는 이 정답을 모른 채로 동작한다 - 정답은 평가(이 파일)에서만 쓴다.
"""

from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv
from litellm import completion

from agents.domain_onboarding import MODEL, DocExample, discover_domain, emit_domain

load_dotenv()

KNOWN_GOOD_AXES = {"length", "extractiveness"}  # topic은 freeform이라 이 에이전트 설계(enum 전용) 범위 밖
KNOWN_BAD_AXES = {"specificity"}  # 6주차에 사람이 이미 "판별력 없음"으로 결론낸 축


def semantic_match(agent_axis_name: str, agent_axis_description: str, known_axis: str) -> bool:
    """이름이 문자 그대로 같은지가 아니라 같은 개념인지를 LLM으로 판정한다
    (예: "conciseness"와 "length"는 이름은 다르지만 같은 축) - 정확 일치
    비교는 이 에이전트가 다른 이름을 붙였다는 이유만으로 실제 성공을
    실패로 잘못 셀 수 있다."""
    prompt = (
        f'Axis A: name="{agent_axis_name}", description="{agent_axis_description}"\n'
        f'Axis B: "{known_axis}" (a summarization control axis - length means output '
        "length/conciseness; extractiveness means how verbatim vs paraphrased the output "
        "is relative to the source)\n\n"
        "Do Axis A and Axis B measure essentially the same underlying property, even if "
        'worded differently? Answer with exactly one word: yes or no.'
    )
    response = completion(model=MODEL, messages=[{"role": "user", "content": prompt}], max_tokens=1, temperature=0)
    return response.choices[0].message.content.strip().lower().startswith("y")


def load_macsum_examples(path: str, n_docs: int = 6) -> list[DocExample]:
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    examples = []
    for record in records:
        summaries = [ref["summary"] for ref in record["references"]]
        if len(summaries) >= 3:
            examples.append(DocExample(source=" ".join(record["source"]), outputs=summaries))
        if len(examples) >= n_docs:
            break
    return examples


def main() -> None:
    examples = load_macsum_examples("data/macsum/dataset/macdoc/val.json")
    print(f"평가용 문서 {len(examples)}개 (문서당 결과물 {[len(e.outputs) for e in examples]}개)")

    report = discover_domain("macsum_eval", examples)

    print("\n=== 제안된 축 ===")
    for c in report.proposed:
        print(f"- {c.name}: {c.description} ({c.low_end} <-> {c.high_end}) values={c.value_names}")

    print("\n=== 결과 ===")
    for result in report.results:
        status = "SURVIVED" if result.survived else "DROPPED"
        powers = [a.discriminative_power for a in result.attempts]
        print(f"- {result.candidate.name}: {status} (판별력: {powers})")

    survived_names = {r.candidate.name for r in report.survived}
    print("\n=== 사람이 정한 정답과 비교 (문자열 완전일치) ===")
    print(f"살아남은 축: {survived_names}")
    print(f"알려진 좋은 축(length/extractiveness) 중 발견: {survived_names & KNOWN_GOOD_AXES}")
    print(f"알려진 나쁜 축(specificity) 중 살아남음(오탐): {survived_names & KNOWN_BAD_AXES}")

    print("\n=== 사람이 정한 정답과 비교 (의미 매칭, LLM 판정) ===")
    for result in report.survived:
        matches = [
            known for known in (KNOWN_GOOD_AXES | KNOWN_BAD_AXES)
            if semantic_match(result.candidate.name, result.candidate.description, known)
        ]
        tag = "GOOD" if any(m in KNOWN_GOOD_AXES for m in matches) else (
            "BAD(오탐)" if any(m in KNOWN_BAD_AXES for m in matches) else "NEW(정답에 없음)"
        )
        print(f"- {result.candidate.name} -> {matches or '없음'} [{tag}]")

    found_good_semantic = any(
        any(semantic_match(r.candidate.name, r.candidate.description, g) for g in KNOWN_GOOD_AXES)
        for r in report.survived
    )
    if not found_good_semantic:
        print("\n주의: length/extractiveness에 의미적으로 대응하는 축을 하나도 못 찾음")

    if report.survived:
        # _agent 접미사가 항상 붙으므로(emit_domain 참고) 기존 summarization.yaml과
        # 이름이 겹치지 않는다 - 절대 규칙 10(기존 파이프라인과 분리)은 이 이름
        # 충돌 회피로 지킨다. checks_module이 "checks.<name>_agent" 형태로 참조되므로
        # domains/, checks/ 표준 위치에 그대로 써야 engine/domain_loader.py가 정상
        # 로드한다.
        yaml_path, checks_path = emit_domain(report)
        print(f"\n방출됨: {yaml_path}, {checks_path}")


if __name__ == "__main__":
    main()

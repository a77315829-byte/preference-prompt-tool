"""service.optimize 의 과적합 방어 검증. API 호출은 없다.

원문 하나로 학습하고 같은 원문으로 평가했을 때 GEPA 성찰 모델이 실제로
그 기사 내용을 프롬프트에 박아 넣었다. 아래 LEAKY 는 그때 나온 후보를
줄인 것이다. 그런 프롬프트는 다른 글에 쓸 수 없다.
"""

from types import SimpleNamespace

import pytest

import service
from engine.domain_loader import load_domain
from engine.estimator import Estimator
from optimize.run_gepa import build_seed_prompt

SOURCE = ("SK hynix is building a more than $4 billion Indiana plant to package memory chips. "
          "It is exploring options to move part of chipmaking to the US, including a possible listing. "
          "Responding to the Reuters report, the company said it was exploring various options to strengthen "
          "its global competitiveness, but that no specific plans or arrangements have been finalized.")
LEAKY = {
 "제안2 (한국어, 기사 내용)": "아래에 제공되는 영어 원문을 영어(English)로 3~4문장 분량으로 요약하라. 원문의 핵심 사실, 인물·기업명, 수치를 정확히 유지하라. 기업·산업 관련 원문에서는 확정된 사업과 검토 중인 선택지를 구분해 서술하라. 예를 들어 SK hynix 관련 내용이라면, 40억 달러가 넘는 인디애나 메모리 칩 패키징 공장 건설은 진행 중인 사실로 요약해야 한다.",
 "제안3 (영어, 기사 예시)": "Read the English source passage and write a concise summary in English only. For example, if the source states that SK hynix is constructing a more-than-$4-billion Indiana facility for memory-chip packaging, considering moving some chipmaking to the United States and possibly listing there, retain all of those facts.",
 "제안4 (영어, 기사 예시)": "The input will be a short English news passage. Summarize it in English in 3–4 concise sentences. For example, if the passage says that SK hynix is constructing a more-than-$4-billion Indiana facility, convey those facts in different wording.",
 "원문 문장 복사": "Summarize. Keep phrases like the company said it was exploring various options to strengthen its position.",
}
CLEAN = {
 "제안1 (일반 지침)": "Summarize the provided English source text in exactly 3–4 sentences, and write the summary only in English. Preserve the source's key facts, entities, figures, chronology, uncertainty, and attribution; do not add information, opinions, or conclusions that are not supported by the source. Use concise paraphrasing rather than copying the original sentence structure or wording. Retain necessary proper nouns, technical terms, and important numbers, but substantially rephrase surrounding expressions so that the wording overlap with the source is no higher than approximately 75%. Output only the finished 3–4 sentence English summary, with no preface, explanation, headings, or commentary.",
 "일반 한국어 지침": "아래 원문을 영어로 3~4문장으로 요약하라. 원문의 핵심 사실과 수치, 인용의 출처를 유지하고, 원문에 없는 내용은 덧붙이지 마라. 요약문만 출력하라.",
 "일반 영어 지침 2": "You summarize news articles for a busy reader. Lead with the main development, then the key numbers and who said what. Keep it to three or four plain sentences and do not speculate.",
}


@pytest.fixture(scope="module")
def domain():
    return load_domain("domains/summarization.yaml")


@pytest.fixture(scope="module")
def reference(domain):
    return " ".join([build_seed_prompt(domain, Estimator(domain)), domain.task_description, *domain.example_sources])


@pytest.mark.parametrize("name", list(LEAKY))
def test_leaky_candidates_are_caught(name, reference) -> None:
    assert service.source_leak(LEAKY[name], SOURCE, reference)


@pytest.mark.parametrize("name", list(CLEAN))
def test_generic_prompts_pass(name, reference) -> None:
    """한 자리 숫자("3~4문장")나 문장 첫 단어 때문에 일반 지침이 걸리면 안 된다."""
    assert service.source_leak(CLEAN[name], SOURCE, reference) == []


def test_korean_source_leak() -> None:
    ko = load_domain("domains/summarization_ko.yaml")
    ref = " ".join([build_seed_prompt(ko, Estimator(ko)), ko.task_description, *ko.example_sources])
    src = "한빛전자는 청주에 3조 원 규모의 배터리 공장을 짓는다고 밝혔다. 회사는 미국 상장도 검토하고 있지만 구체적인 계획은 정해지지 않았다고 말했다."
    assert service.source_leak("예를 들어 한빛전자가 청주에 배터리 공장을 짓는다면 투자 규모를 먼저 적어라.", src, ref)
    assert not service.source_leak("원문을 한국어로 2문장 이내로 요약하라. 핵심 사실과 수치를 유지하라.", src, ref)


def _finished_state(domain_path: str, source: str):
    state = service.start_session(source, "summarization", domain_path, model="m", demo_mode=True, total_rounds=2)
    for _ in range(2):
        state = service.submit_choice(state, state.pair.pair_id, "a")
    return state


def test_validation_uses_examples_not_user_source(monkeypatch) -> None:
    """후보를 고르는 평가 세트에 사용자 원문이 들어가면 그 원문에 맞춘 후보가 이긴다."""
    import gepa

    seen = {}

    def fake_optimize(**kwargs):
        seen.update(kwargs)
        seed = kwargs["seed_candidate"]
        return SimpleNamespace(candidates=[seed], val_aggregate_scores=[1.0])

    monkeypatch.setattr(gepa, "optimize", fake_optimize)
    state = _finished_state("domains/summarization.yaml", SOURCE)
    service.optimize(state)

    domain = load_domain("domains/summarization.yaml")
    val_inputs = [row["input"] for row in seen["valset"]]
    train_inputs = [row["input"] for row in seen["trainset"]]
    assert SOURCE not in val_inputs
    assert val_inputs == domain.example_sources
    assert train_inputs[0] == SOURCE


def test_best_leaky_candidate_is_skipped(monkeypatch) -> None:
    """점수가 가장 높아도 원문 내용이 든 후보는 고르지 않는다."""
    import gepa

    clean = CLEAN["제안1 (일반 지침)"]

    def fake_optimize(**kwargs):
        seed = kwargs["seed_candidate"]
        return SimpleNamespace(
            candidates=[seed, {"system_prompt": LEAKY["제안3 (영어, 기사 예시)"]}, {"system_prompt": clean}],
            val_aggregate_scores=[0.5, 0.9, 0.7],
        )

    monkeypatch.setattr(gepa, "optimize", fake_optimize)
    state = _finished_state("domains/summarization.yaml", SOURCE)
    assert service.optimize(state) == clean


def test_all_leaky_falls_back_to_seed(monkeypatch) -> None:
    import gepa

    def fake_optimize(**kwargs):
        seed = kwargs["seed_candidate"]
        return SimpleNamespace(
            candidates=[seed, {"system_prompt": LEAKY["제안2 (한국어, 기사 내용)"]}],
            val_aggregate_scores=[0.5, 0.9],
        )

    monkeypatch.setattr(gepa, "optimize", fake_optimize)
    state = _finished_state("domains/summarization.yaml", SOURCE)
    assert service.optimize(state) == service.optimize.__globals__["build_seed_prompt"](
        *service._rebuild(state)[:2]
    )

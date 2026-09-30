"""exporters.py 와 service.exports_for 검증. API 호출은 없다."""

from pathlib import Path

import pytest

import exporters
import service
from engine.domain_loader import load_domain

DOMAINS = sorted(Path("domains").glob("*.yaml"))
PROMPT = "당신은 요약 도우미다.\n\n## 이 사용자의 선호\n- 분량: 2문장 이내로 요약하라."


@pytest.mark.parametrize("path", DOMAINS, ids=lambda p: p.stem)
def test_every_domain_names_only_known_targets(path) -> None:
    """YAML 의 오타는 로드 시점이 아니라 여기서 잡는다 (엔진은 이름을 모른다)."""
    assert exporters.unknown_targets(load_domain(path).export_targets) == []


def test_default_targets_are_chat_services_and_a_markdown_file() -> None:
    exports = exporters.build_exports(PROMPT, slug="summarization", title="t")
    assert [e.key for e in exports] == list(exporters.DEFAULT_TARGETS)
    md = next(e for e in exports if e.key == "markdown")
    assert md.kind == "file" and md.filename == "summarization-prompt.md"
    assert PROMPT in md.content
    for e in exports:
        if e.kind == "copy":
            assert e.content == PROMPT  # 붙여 넣을 글에는 아무것도 덧붙이지 않는다


def test_repository_files_use_the_paths_the_tools_read() -> None:
    exports = {e.key: e for e in exporters.build_exports(
        PROMPT, slug="coding", title="선호", targets=["copilot", "cursor", "agents_md"])}
    assert exports["copilot"].path == ".github/copilot-instructions.md"
    assert exports["agents_md"].path == "AGENTS.md"
    cursor = exports["cursor"]
    assert cursor.path == ".cursor/rules/coding-preferences.mdc"
    assert cursor.filename == "coding-preferences.mdc"
    # 머리말이 맨 앞에 와야 Cursor 가 규칙으로 읽는다.
    assert cursor.content.startswith("---\ndescription: ")
    assert "alwaysApply: true\n---\n" in cursor.content
    assert PROMPT in cursor.content


def test_over_the_chatgpt_limit_offers_a_compact_version_instead_of_cutting() -> None:
    long_prompt = PROMPT + "\n" + "- 규칙.\n" * 400
    (chatgpt,) = exporters.build_exports(
        long_prompt, slug="s", title="t", targets=["chatgpt"], compact_prompt="짧은 판")
    assert chatgpt.over_limit and chatgpt.char_count > exporters.CHATGPT_FREE_LIMIT
    assert chatgpt.content == long_prompt.strip()  # 자르지 않는다
    assert chatgpt.compact == "짧은 판"

    (short,) = exporters.build_exports(PROMPT, slug="s", title="t", targets=["chatgpt"], compact_prompt="x")
    assert not short.over_limit and short.compact is None


def _finished(domain_file: str):
    state = service.start_session("The council approved a plan. It adds homes. Critics worry.",
                                  domain_file, f"domains/{domain_file}.yaml", model="m", demo_mode=True)
    while not state.done:
        state = service.submit_choice(state, state.pair.pair_id, "a")
    return state


def test_service_uses_the_domain_targets() -> None:
    coding = [e.key for e in service.exports_for(_finished("coding"), "P")]
    assert coding[:3] == ["copilot", "cursor", "agents_md"]
    summary = [e.key for e in service.exports_for(_finished("summarization"), "P")]
    assert summary == list(exporters.DEFAULT_TARGETS)


def test_compact_version_is_the_short_assembly() -> None:
    state = _finished("summarization")
    domain, _ = service.current_estimate(state)
    (chatgpt,) = [e for e in service.exports_for(state, "x" * 2000) if e.key == "chatgpt"]
    assert chatgpt.over_limit
    assert chatgpt.compact.startswith(domain.task_description)
    assert len(chatgpt.compact) < exporters.CHATGPT_FREE_LIMIT

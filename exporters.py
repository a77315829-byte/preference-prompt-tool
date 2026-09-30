"""만든 프롬프트를 실제 도구가 받는 형식으로 바꾼다.

Streamlit 을 import 하지 않는다 (`service.py`, `budget.py` 와 같은 층).

도구가 지침을 받는 방식은 두 가지다.
- **붙여 넣기**: ChatGPT 맞춤 지침, Claude 프로젝트 지침, Gemini Gem 은 설정
  칸에 글을 붙여 넣는다. 복사 버튼이 맞다.
- **파일**: GitHub Copilot, Cursor, AGENTS.md 를 읽는 코딩 도구는 저장소
  안의 정해진 파일을 자동으로 읽는다. 파일을 저장소에 넣으면 팀원 모두에게
  적용된다.

형식 근거 (2026-09-30 확인):
- Copilot: `.github/copilot-instructions.md`, 일반 마크다운. AGENTS.md 도 읽는다.
  https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions
- Cursor: `.cursor/rules/*.mdc`, 머리말 `description`/`globs`/`alwaysApply`.
  AGENTS.md 도 지원한다. https://cursor.com/docs/context/rules
- ChatGPT 맞춤 지침: 무료·Go 1,500자, 유료 5,000자 (OpenAI 도움말 검색 요약.
  도움말 페이지 자체는 403 이라 직접 읽지 못했다). 무료 기준으로 경고만 하고
  자르지 않는다 - 자르면 선호나 규칙이 조용히 빠진다.
- Claude 프로젝트·Gemini Gem: 짧은 글자 수 제한을 문서로 확인하지 못해
  한도를 두지 않는다.

어떤 도메인에 어떤 내보내기를 줄지는 `domains/*.yaml` 의 `export_targets`
에서 읽는다. 이 모듈은 도메인 이름을 모른다.
"""

from __future__ import annotations

from dataclasses import dataclass

# 도메인 YAML 에 export_targets 가 없을 때. 채팅 서비스 셋과 파일 하나.
DEFAULT_TARGETS = ("chatgpt", "claude", "gemini", "markdown")

CHATGPT_FREE_LIMIT = 1500


@dataclass(frozen=True)
class Target:
    key: str
    label: str
    kind: str  # "copy" | "file"
    how_to: str
    char_limit: int | None = None
    path: str | None = None  # kind == "file" 일 때 저장소 기준 경로


TARGETS: dict[str, Target] = {
    "chatgpt": Target(
        "chatgpt", "ChatGPT 맞춤 지침", "copy",
        "ChatGPT 설정의 맞춤 지침(개인 맞춤 설정) 칸에 붙여 넣으세요.",
        char_limit=CHATGPT_FREE_LIMIT,
    ),
    "claude": Target(
        "claude", "Claude 프로젝트 지침", "copy",
        "Claude 에서 프로젝트를 만들고 프로젝트 지침 칸에 붙여 넣으세요.",
    ),
    "gemini": Target(
        "gemini", "Gemini Gem 지침", "copy",
        "Gemini 에서 새 Gem 을 만들고 지침 칸에 붙여 넣으세요.",
    ),
    "markdown": Target(
        "markdown", "마크다운 파일", "file",
        "보관하거나 다른 도구에 붙여 넣을 때 쓰세요.",
        path="{slug}-prompt.md",
    ),
    "copilot": Target(
        "copilot", "GitHub Copilot", "file",
        "저장소의 .github/ 폴더에 넣으면 Copilot 이 자동으로 읽습니다.",
        path=".github/copilot-instructions.md",
    ),
    "cursor": Target(
        "cursor", "Cursor 규칙", "file",
        "저장소의 .cursor/rules/ 폴더에 넣으면 Cursor 가 항상 적용합니다.",
        path=".cursor/rules/{slug}-preferences.mdc",
    ),
    "agents_md": Target(
        "agents_md", "AGENTS.md", "file",
        "저장소 루트에 두면 Cursor·Copilot 등 AGENTS.md 를 읽는 도구가 씁니다.",
        path="AGENTS.md",
    ),
}


@dataclass(frozen=True)
class Export:
    key: str
    label: str
    kind: str
    how_to: str
    content: str
    filename: str | None = None  # 내려받을 파일 이름 (경로의 마지막 부분)
    path: str | None = None  # 저장소 안에 둘 위치
    char_count: int = 0
    char_limit: int | None = None
    over_limit: bool = False
    compact: str | None = None  # 한도를 넘을 때 대신 쓸 짧은 판


def unknown_targets(keys) -> list[str]:
    """도메인 YAML 에 적힌 이름 중 모르는 것. 로드 시점 검증에 쓴다."""
    return [k for k in keys if k not in TARGETS]


def _render(target: Target, prompt: str, title: str) -> str:
    body = prompt.strip()
    if target.key == "cursor":
        # alwaysApply: 파일 종류와 상관없이 매 요청에 적용한다. 선호는
        # 특정 파일에 묶인 규칙이 아니다.
        description = title.replace('"', "'")
        return f'---\ndescription: "{description}"\nalwaysApply: true\n---\n\n{body}\n'
    if target.kind == "file":
        return f"# {title}\n\n{body}\n"
    return body


def build_exports(
    prompt: str,
    *,
    slug: str,
    title: str,
    targets=None,
    compact_prompt: str | None = None,
) -> list[Export]:
    """prompt 를 targets 각각의 형식으로 바꾼다.

    slug: 파일 이름에 쓸 짧은 이름 (도메인 이름). title: 파일 머리에 붙일 제목.
    compact_prompt: 글자 수 한도가 있는 곳에서 넘칠 때 대신 줄 짧은 판.
    """
    exports = []
    for key in targets or DEFAULT_TARGETS:
        target = TARGETS[key]
        content = _render(target, prompt, title)
        path = target.path.format(slug=slug) if target.path else None
        over = target.char_limit is not None and len(content) > target.char_limit
        compact = None
        if over and compact_prompt:
            compact = _render(target, compact_prompt, title)
        exports.append(Export(
            key=target.key,
            label=target.label,
            kind=target.kind,
            how_to=target.how_to,
            content=content,
            filename=path.rsplit("/", 1)[-1] if path else None,
            path=path,
            char_count=len(content),
            char_limit=target.char_limit,
            over_limit=over,
            compact=compact,
        ))
    return exports

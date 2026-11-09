"""Existing format adapters plus an explicit, non-destructive merge preview."""
from dataclasses import asdict
import difflib

from exporters import build_exports
from coding_work_trials import text

BEGIN = "<!-- preference-prompt-tool:coding:begin -->"
END = "<!-- preference-prompt-tool:coding:end -->"


def export_preview(body):
    prompt = text(body.get("prompt"), "내보낼 지침", 20000)
    title = text(body.get("title", "코딩 작업 지침"), "이름", 100)
    targets = [asdict(e) for e in build_exports(prompt, slug="coding-guide", title=title,
                                               targets=("agents_md", "copilot", "cursor", "markdown"))]
    targets.insert(1, {**targets[0], "key": "claude_code", "label": "Claude Code", "path": "CLAUDE.md",
                       "filename": "CLAUDE.md", "how_to": "프로젝트 지침 파일의 기존 규칙과 함께 검토해 적용하세요."})
    target = next((e for e in targets if e["key"] == body.get("target", "agents_md")), None)
    if target is None:
        raise ValueError("지원하는 내보내기 도구를 선택해 주세요.")
    existing = body.get("existing", "")
    text(existing, "기존 지침", 40000, False)
    if existing and target["key"] == "cursor":
        raise ValueError("Cursor의 기존 적용 범위는 자동으로 합치지 않습니다. 별도 규칙 파일로 내려받아 범위를 확인해 주세요.")
    generated = target["content"]
    if target["key"] != "cursor":
        block = f"{BEGIN}\n{generated.rstrip()}\n{END}\n"
        if BEGIN in existing or END in existing:
            if existing.count(BEGIN) != 1 or existing.count(END) != 1 or existing.index(BEGIN) > existing.index(END):
                raise ValueError("기존 지침의 자동 생성 영역 표시가 맞지 않습니다. 직접 확인해 주세요.")
            before, rest = existing.split(BEGIN, 1)
            _, after = rest.split(END, 1)
            generated = before + block.rstrip() + after
        else:
            generated = (existing + "\n\n" if existing else "") + block
    difference = "\n".join(difflib.unified_diff(existing.splitlines(), generated.splitlines(),
                                                fromfile="기존 지침", tofile=target["path"], lineterm=""))
    return {"target": target["key"], "filename": target["filename"], "path": target["path"],
            "content": generated, "diff": difference,
            "targets": [{k: e[k] for k in ("key", "label", "path")} for e in targets],
            "scope": "저장소의 지침으로 적용됩니다. 개인 취향을 팀 전체에 적용할지는 먼저 검토하세요.",
            "verification": "파일을 둔 뒤 사용 도구에서 적용된 지침을 확인하세요. 내려받기만으로 자동 설치되지는 않습니다."}

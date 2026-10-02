"""개발용 묶음 ZIP (계획서 9절).

- 파일 이름은 아래 FILES 로 고정한다. 사용자 입력(작업 이름 등)으로 경로를
  만들지 않으므로 `../` 가 들어갈 여지가 없다.
- render_example.py 는 고정 문자열이다. 모델이 만든 코드를 넣지 않는다.
  표준 라이브러리만 쓰고 네트워크 없이 메시지를 구성한다.
- include_data=False 면 업무 설명·결과 예시·시험 입력·실행 결과를 빼고,
  input.example.json 은 변수 정의로 만든 빈 틀이 된다. 비밀 키는 어느
  쪽이든 들어가지 않는다 - 프로젝트에 키를 담는 칸 자체가 없다.
- 마지막 시험이 지금 프롬프트·입력과 맞지 않으면 README 에 그 결과를 현재
  버전의 검증으로 적지 않는다.
"""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

from prompt_workspace.models import input_hash, status, validate_project
from prompt_workspace.runner import summarize_checks

ROOT = "prompt-package"
FILES = (
    "prompt.md",
    "input_template.txt",
    "variables.json",
    "output_contract.json",
    "input.example.json",
    "render_example.py",
    "project.json",
    "README.md",
)

RENDER_EXAMPLE = '''"""네트워크 없이 시험 입력으로 모델에 보낼 메시지를 구성한다.

    python render_example.py                 # input.example.json 사용
    python render_example.py my_input.json

표준 라이브러리만 쓴다. 모델을 부르지 않는다. 실제 호출 예시는 README 참고.
치환 규칙: {{변수}} 를 한 번만 바꾼다. 값 안의 {{...}} 는 다시 평가하지 않는다.
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLACEHOLDER = re.compile(r"\\{\\{\\s*([a-z_][a-z0-9_]*)\\s*\\}\\}")
TYPES = {"string": (str,), "number": (int, float), "integer": (int,), "boolean": (bool,),
         "array": (list,), "object": (dict,)}


def as_text(value):
    if value is None:
        return ""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def problems(variables, values):
    if not isinstance(values, dict):
        return ["시험 입력은 JSON 객체여야 합니다."]
    found = []
    for var in variables:
        value = values.get(var["name"])
        if value is None or (isinstance(value, str) and not value.strip()):
            if var["required"]:
                found.append(f"필수 변수 '{var['name']}' 의 값이 없습니다.")
            continue
        bad_bool = var["type"] in ("number", "integer") and isinstance(value, bool)
        if bad_bool or not isinstance(value, TYPES[var["type"]]):
            found.append(f"'{var['name']}' 은 {var['type']} 이어야 합니다.")
    return found


def main():
    # 한국어 윈도우는 표준 출력을 cp949 로 쓴다. 파이프로 받는 쪽이 UTF-8 JSON 을
    # 기대하므로 고정한다.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "input.example.json"
    variables = json.loads((HERE / "variables.json").read_text(encoding="utf-8"))
    values = json.loads(input_path.read_text(encoding="utf-8"))
    errors = problems(variables, values)
    if errors:
        print("\\n".join(errors), file=sys.stderr)
        sys.exit(1)
    # 파일 끝 줄바꿈은 내보낼 때 붙인 것이라 뗀다.
    template = (HERE / "input_template.txt").read_text(encoding="utf-8").removesuffix("\\n")
    messages = [
        {"role": "system", "content": (HERE / "prompt.md").read_text(encoding="utf-8").removesuffix("\\n")},
        {"role": "user", "content": PLACEHOLDER.sub(lambda m: as_text(values.get(m.group(1))), template)},
    ]
    print(json.dumps(messages, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
'''

_BLANK = {"string": "", "number": 0, "integer": 0, "boolean": False, "array": [], "object": {}}


def _blank_input(variables: list[dict[str, Any]]) -> dict[str, Any]:
    return {v["name"]: _BLANK[v["type"]] for v in variables}


def _last_run_note(project: dict[str, Any], values: Any) -> list[str]:
    runs = project.get("runs") or []
    if not runs:
        return ["- 시험 실행 기록이 없습니다. 이 묶음의 프롬프트는 실행 확인 전입니다."]
    last = runs[-1]
    current = (
        last.get("artifact_revision") == project["artifact"]["revision"]
        and last.get("requirements_revision") == project["requirements_revision"]
        and (values is None or last.get("input_hash") == input_hash(values))
    )
    if last.get("status") != "ran":
        return [f"- 마지막 시험은 모델을 실행하지 않았습니다 (상태: {last.get('status')})."]
    counts = summarize_checks(last.get("checks", []))
    head = (
        f"- 마지막 시험: 모델 `{last.get('model')}`, 캐시 사용 {'예' if last.get('cached') else '아니오'}, "
        f"통과 {counts['pass']} / 실패 {counts['fail']} / 미평가 {counts['not_evaluated']}"
    )
    if not current:
        return [head, "- **이 결과는 이전 버전의 프롬프트나 다른 입력으로 실행한 것입니다.** 현재 버전의 검증이 아닙니다."]
    lines = [head, "- 검사 항목:"]
    for c in last.get("checks", []):
        label = {"pass": "통과", "fail": "실패", "not_evaluated": "미평가"}[c["status"]]
        lines.append(f"  - [{label}] {c['name']}" + (f" - {c['detail']}" if c.get("detail") else ""))
    return lines


def _readme(project: dict[str, Any], values: Any, include_data: bool) -> str:
    st = status(project)
    lines = [
        f"# {project.get('title') or '프롬프트 묶음'}",
        "",
        "선호 기반 프롬프트 도구의 개발자용 작업 공간에서 내보낸 묶음입니다.",
        "",
        "## 파일",
        "- `prompt.md` - 시스템 지침 (system 메시지)",
        "- `input_template.txt` - 입력 템플릿. `{{변수}}` 를 요청마다 코드가 채웁니다",
        "- `variables.json` - 변수 정의 (이름·타입·필수)",
        "- `output_contract.json` - 출력 계약. **이 도구의 제한된 형식이며 JSON Schema 표준이 아닙니다**",
        "- `input.example.json` - 시험 입력" + ("" if include_data else " (값을 비운 틀)"),
        "- `render_example.py` - 네트워크 없이 메시지를 구성하는 예제",
        "- `project.json` - 작업 공간으로 다시 가져올 수 있는 프로젝트",
        "",
        "## 사용",
        "```",
        "python render_example.py            # 메시지 구성만, 모델 호출 없음",
        "```",
        "실제 모델 호출은 사용하는 라이브러리에 맞춰 직접 붙입니다. 출력된 messages 를",
        "그대로 chat completion 요청에 넣으면 됩니다. **호출하면 비용이 발생합니다.**",
        "API 키는 파일에 넣지 말고 환경 변수에서 읽으세요.",
        "",
        "## 상태",
        f"- 요구사항: {'확인됨' if st['requirements_confirmed'] else '확인 전 (초안)'}"
        f", revision {project['requirements_revision']}",
        f"- 프롬프트 revision {project['artifact']['revision']}"
        + (" - **요구사항이 바뀐 뒤 다시 생성하지 않았습니다**" if st["stage"] == "stale_artifact" else ""),
        *_last_run_note(project, values),
        "",
        "## 확인하지 않은 것",
        "- 설명 문장의 의미 정확성 (근거 없는 판단 등)은 코드로 검사하지 않았습니다.",
        "- 필수 규칙은 프롬프트에 적혀 있을 뿐, 모델이 늘 지킨다는 보장은 없습니다.",
        "- 같은 설정(temperature 0)이라도 결과가 완전히 같다는 보장은 없습니다.",
        "- 몇 개 예제의 통과는 일반적인 정확성을 뜻하지 않습니다.",
    ]
    return "\n".join(lines) + "\n"


def build_zip(project: dict[str, Any], values: Any = None, *, include_data: bool = False) -> bytes:
    validate_project(project)
    if project.get("artifact") is None:
        raise ValueError("먼저 프롬프트를 생성해 주세요.")
    req = project["requirements"]
    exported = dict(project)
    if not include_data:
        exported.update(raw_description="", example_output="", runs=[])
        example = _blank_input(req["variables"])
    else:
        example = values if isinstance(values, dict) else _blank_input(req["variables"])

    contents = {
        "prompt.md": project["artifact"]["system_prompt"] + "\n",
        "input_template.txt": project["artifact"]["input_template"] + "\n",
        "variables.json": json.dumps(
            [{k: v[k] for k in ("name", "description", "type", "required")} for v in req["variables"]],
            ensure_ascii=False, indent=2),
        "output_contract.json": json.dumps(
            {"format": "preference-prompt-tool/output-contract-v1", **req["output_contract"]},
            ensure_ascii=False, indent=2),
        "input.example.json": json.dumps(example, ensure_ascii=False, indent=2),
        "render_example.py": RENDER_EXAMPLE,
        "project.json": json.dumps(exported, ensure_ascii=False, indent=2),
        "README.md": _readme(project, values, include_data),
    }
    assert tuple(contents) == FILES
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in FILES:
            zf.writestr(f"{ROOT}/{name}", contents[name])
    return buffer.getvalue()

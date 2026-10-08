"""Reproducible, AI-authored React style stimuli; not human preference labels.

Run ``python -m experiments.coding_dataset`` to export the complete JSON dataset.
No network, API key, random generator, or third-party package is used.
"""

from __future__ import annotations

import itertools
import json


AXES = {
    "code_structure": ("compact", "separated"),
    "style_management": ("direct", "theme"),
    "type_detail": ("inferred", "explicit"),
}

# Families, rather than individual variants, are assigned to splits. All eight
# styles of a task stay together. Holdout tasks must not be shown in onboarding.
TASKS = (
    {
        "id": "counter", "split": "elicitation", "component": "Counter",
        "request": "클릭 횟수를 보여주세요. 처음에는 0이며, 증가 버튼으로 1씩 늘리고 초기화 버튼으로 0으로 되돌립니다.",
        "initial": "0", "type": "number",
        "actions": (("increment", "setValue((current) => current + 1)"), ("reset", "setValue(0)")),
        "body": '<output>{value}</output><button onClick={increment}>증가</button><button onClick={reset}>초기화</button>',
        "trace": [("increment", 1), ("increment", 2), ("reset", 0)],
        "expected_initial": ["0", "증가", "초기화"],
    },
    {
        "id": "disclosure", "split": "elicitation", "component": "Disclosure",
        "request": "설명 접기/펼치기를 만드세요. 처음에는 닫혀 있고 펼치기 버튼으로 설명을 표시하며 닫기 버튼으로 숨깁니다. 펼침 상태를 aria-expanded로 알려주세요.",
        "initial": "false", "type": "boolean",
        "actions": (("open", "setValue(true)"), ("close", "setValue(false)")),
        "body": '<button aria-expanded={value} onClick={open}>펼치기</button><button onClick={close}>닫기</button>{value && <p>추가 설명입니다.</p>}',
        "trace": [("open", True), ("open", True), ("close", False)],
        "expected_initial": ["펼치기", "닫기"],
    },
    {
        "id": "filter", "split": "elicitation", "component": "ItemFilter",
        "request": "전체/완료 필터를 만드세요. 처음에는 '계획 세우기'와 '발표하기' 모두 표시합니다. 완료 필터에서는 완료된 '계획 세우기'만 표시하고 전체 버튼으로 복원합니다.",
        "initial": "false", "type": "boolean",
        "actions": (("showCompleted", "setValue(true)"), ("showAll", "setValue(false)")),
        "body": '<button aria-pressed={!value} onClick={showAll}>전체</button><button aria-pressed={value} onClick={showCompleted}>완료</button><ul><li>계획 세우기</li>{!value && <li>발표하기</li>}</ul>',
        "trace": [("showCompleted", True), ("showAll", False)],
        "expected_initial": ["전체", "완료", "계획 세우기", "발표하기"],
    },
    {
        "id": "checklist", "split": "elicitation", "component": "Checklist",
        "request": "읽기와 검토 두 항목의 체크리스트를 만드세요. 처음에는 둘 다 미완료이며 각 버튼을 누르면 해당 항목만 완료/미완료로 전환됩니다. 완료 상태는 aria-pressed로 알려주세요.",
        "initial": "[false, false]", "type": "boolean[]",
        "actions": (("toggleRead", "setValue((current) => current.map((done, index) => index === 0 ? !done : done))"), ("toggleReview", "setValue((current) => current.map((done, index) => index === 1 ? !done : done))")),
        "body": '<button aria-pressed={value[0]} onClick={toggleRead}>읽기 {value[0] ? "완료" : "미완료"}</button><button aria-pressed={value[1]} onClick={toggleReview}>검토 {value[1] ? "완료" : "미완료"}</button>',
        "trace": [("toggleRead", [True, False]), ("toggleReview", [True, True]), ("toggleRead", [False, True])],
        "expected_initial": ["읽기 ", "미완료", "검토 ", "미완료"],
    },
    {
        "id": "view_switcher", "split": "holdout", "component": "ViewSwitcher",
        "request": "소개/사용법 화면 선택기를 만드세요. 처음에는 '프로젝트 소개'를 표시합니다. 사용법 버튼은 '버튼을 눌러 선택하세요.'를 표시하고 소개 버튼으로 돌아올 수 있습니다. 선택한 버튼은 aria-pressed로 구분합니다.",
        "initial": '"intro"', "type": "string",
        "actions": (("showIntro", 'setValue("intro")'), ("showGuide", 'setValue("guide")')),
        "body": '<button aria-pressed={value === "intro"} onClick={showIntro}>소개</button><button aria-pressed={value === "guide"} onClick={showGuide}>사용법</button><p>{value === "intro" ? "프로젝트 소개" : "버튼을 눌러 선택하세요."}</p>',
        "trace": [("showGuide", "guide"), ("showIntro", "intro")],
        "expected_initial": ["소개", "사용법", "프로젝트 소개"],
    },
    {
        "id": "text_preview", "split": "holdout", "component": "TextPreview",
        "request": "텍스트 미리보기를 만드세요. 입력창은 '내용' 레이블과 연결하고 입력한 내용을 즉시 output에 표시합니다. 처음에는 빈 문자열이고, 비우기 버튼으로 입력창과 미리보기를 함께 초기화합니다.",
        "initial": '""', "type": "string",
        "actions": (("update", "setValue(next)", 'next = ""', 'next: string = ""'), ("clear", 'setValue("")')),
        "body": '<label>내용<input value={value} onChange={(event) => update(event.currentTarget.value)} /></label><output>{value}</output><button onClick={clear}>비우기</button>',
        "trace": [("update", "안녕하세요", ["안녕하세요"]), ("clear", "")],
        "expected_initial": ["내용", "", "비우기"],
    },
)


def render_files(task: dict, profile: dict[str, str]) -> dict[str, str]:
    """Apply three orthogonal transformations to the same task implementation."""
    explicit = profile["type_detail"] == "explicit"
    separated = profile["code_structure"] == "separated"
    themed = profile["style_management"] == "theme"
    component = task["component"]
    actions = task["actions"]
    names = ", ".join(["value", *(action[0] for action in actions)])

    model = ""
    if explicit:
        fields = "\n".join(
            f"  {action[0]}: ({'next?: string' if len(action) == 4 else ''}) => void;"
            for action in actions
        )
        model = f"interface Model {{\n  value: {task['type']};\n{fields}\n}}\n\n"
    declarations = []
    for action in actions:
        params = action[3 if explicit else 2] if len(action) == 4 else ""
        declarations.append(f"  const {action[0]} = ({params}){': void' if explicit else ''} => {action[1]};")
    hook = (
        model
        + f"{'export ' if separated else ''}function useModel(){': Model' if explicit else ''} {{\n"
        + f"  const [value, setValue] = useState{'<' + task['type'] + '>' if explicit else ''}({task['initial']});\n"
        + "\n".join(declarations)
        + f"\n  return {{ {names} }};\n}}\n"
    )
    theme = (
        'const theme = {\n  colors: { background: "#eef2ff", text: "#172554" },\n'
        '  spacing: { panel: 16 },\n};\n\n'
        if themed else ""
    )
    style = (
        theme + f"{'export ' if separated else ''}const panelStyle: CSSProperties = {{\n"
        + f"  backgroundColor: {'theme.colors.background' if themed else chr(34) + '#eef2ff' + chr(34)},\n"
        + f"  color: {'theme.colors.text' if themed else chr(34) + '#172554' + chr(34)},\n"
        + f"  padding: {'theme.spacing.panel' if themed else '16'},\n"
        + "};\n"
    )
    view = (
        f"export function {component}(){': ReactElement' if explicit else ''} {{\n"
        + f"  const {{ {names} }} = useModel();\n"
        + f'  return <section style={{panelStyle}} aria-label="{component}">{task["body"]}</section>;\n'
        + "}\n"
    )
    if separated:
        return {
            f"{component}.tsx": (
                ('import type { ReactElement } from "react";\n' if explicit else "")
                + 'import { useModel } from "./useModel";\n'
                + 'import { panelStyle } from "./styles";\n\n' + view
            ),
            "useModel.ts": 'import { useState } from "react";\n\n' + hook,
            "styles.ts": 'import type { CSSProperties } from "react";\n\n' + style,
        }
    types = "CSSProperties, type ReactElement" if explicit else "CSSProperties"
    return {f"{component}.tsx": f'import {{ useState, type {types} }} from "react";\n\n' + style + "\n" + hook + "\n" + view}


def build_dataset() -> dict:
    profiles = [dict(zip(AXES, values)) for values in itertools.product(*AXES.values())]
    variants, pairs = [], []
    for task in TASKS:
        task_variants = []
        for index, profile in enumerate(profiles):
            variant = {
                "id": f"{task['id']}-v{index}", "task_id": task["id"],
                "split": task["split"], "profile": profile,
                "files": render_files(task, profile),
            }
            task_variants.append(variant)
            variants.append(variant)
        for axis in AXES:
            for left in task_variants:
                if left["profile"][axis] != AXES[axis][0]:
                    continue
                target = {**left["profile"], axis: AXES[axis][1]}
                right = next(v for v in task_variants if v["profile"] == target)
                # Balanced presentation order, not a preference/winner label.
                a, b = (left, right) if len(pairs) % 2 == 0 else (right, left)
                pairs.append({
                    "id": f"{task['id']}-{axis}-{left['id'].split('-')[-1]}",
                    "task_id": task["id"], "split": task["split"], "axis": axis,
                    "a": a["id"], "b": b["id"], "winner": None,
                })
    return {
        "schema_version": 1, "dataset_id": "coding-style-pairs-v1",
        "provenance": "AI-authored synthetic stimuli, not collected human preferences",
        "human_review_status": "pending", "axes": AXES,
        "tasks": [{k: v for k, v in task.items() if k not in ("body", "actions")} for task in TASKS],
        "variants": variants, "pairs": pairs,
    }


if __name__ == "__main__":
    print(json.dumps(build_dataset(), ensure_ascii=False, indent=2))

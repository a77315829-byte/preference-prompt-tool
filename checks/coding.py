"""TypeScript/React 코딩 스타일을 검사하는 함수."""

from __future__ import annotations

import re


FILE_PATTERN = re.compile(
    r"\b[A-Za-z][\w.-]*\.(?:tsx?|css|scss)\b",
    re.IGNORECASE,
)

CODE_BLOCK_PATTERN = re.compile(
    r"```(?:tsx?|typescript|javascript|jsx|css|scss)?\s*\n(.*?)```",
    re.IGNORECASE | re.DOTALL,
)


def count_files(output: str) -> int:
    file_names = {
        match.group(0).lower()
        for match in FILE_PATTERN.finditer(output)
    }

    if file_names:
        return len(file_names)

    if not output.strip():
        return 0

    code_fence_count = len(CODE_BLOCK_PATTERN.findall(output))
    return max(1, code_fence_count)


def file_structure(
    output: str,
    source: str,
    value: str,
    target: dict,
) -> tuple[float, str]:
    del source, value

    file_count = count_files(output)
    min_files = target.get("min_files")
    max_files = target.get("max_files")

    if min_files is not None and file_count < min_files:
        score = file_count / min_files
        feedback = (
            f"파일 구성 위반: {file_count}개 파일 "
            f"(목표 {min_files}개 이상)."
        )
        return score, feedback

    if max_files is not None and file_count > max_files:
        score = max_files / file_count
        feedback = (
            f"파일 구성 위반: {file_count}개 파일 "
            f"(목표 {max_files}개 이하)."
        )
        return score, feedback

    return 1.0, f"파일 구성 충족: {file_count}개 파일로 제시됨."

def count_theme_signals(output: str) -> int:
    patterns = [
        r"\btheme\s*\.",
        r"\btokens?\s*\.",
        r"\bcolors\s*\.",
        r"\bspacing\s*\.",
        r"var\(\s*--",
        r"\bThemeProvider\b",
        r"\bcreateTheme\b",
        r"\bconst\s+theme\s*=",
    ]

    return sum(
        len(re.findall(pattern, output, re.IGNORECASE))
        for pattern in patterns
    )


def theme_usage(
    output: str,
    source: str,
    value: str,
    target: dict,
) -> tuple[float, str]:
    del source, value

    signal_count = count_theme_signals(output)
    min_signals = target.get("min_theme_signals")
    max_signals = target.get("max_theme_signals")

    if min_signals is not None and signal_count < min_signals:
        score = signal_count / min_signals
        feedback = (
            f"스타일 관리 위반: 테마 사용 신호 {signal_count}개 "
            f"(목표 {min_signals}개 이상)."
        )
        return score, feedback

    if max_signals is not None and signal_count > max_signals:
        return (
            0.0,
            f"스타일 관리 위반: 테마 사용 신호 {signal_count}개 "
            f"(목표 {max_signals}개 이하).",
        )

    return (
        1.0,
        f"스타일 관리 충족: 테마 사용 신호 {signal_count}개.",
    )

def count_type_signals(output: str) -> int:
    patterns = [
        r"\binterface\s+[A-Za-z_]\w*",
        r"\btype\s+[A-Za-z_]\w*\s*=",
        r"\b(?:const|let)\s+\w+\s*:",
        r"\b\w+\??\s*:\s*(?:string|number|boolean|[A-Z]\w*)",
        r"\)\s*:\s*[A-Za-z_]\w*",
        r"\b(?:useState|useRef|useReducer)<",
        r"\bReact\.(?:FC|ComponentType)<",
    ]

    return sum(
        len(re.findall(pattern, output))
        for pattern in patterns
    )


def type_explicitness(
    output: str,
    source: str,
    value: str,
    target: dict,
) -> tuple[float, str]:
    del source, value

    signal_count = count_type_signals(output)
    min_signals = target.get("min_signals")
    max_signals = target.get("max_signals")

    if min_signals is not None and signal_count < min_signals:
        score = signal_count / min_signals
        feedback = (
            f"타입 작성 위반: 명시적 타입 신호 {signal_count}개 "
            f"(목표 {min_signals}개 이상)."
        )
        return score, feedback

    if max_signals is not None and signal_count > max_signals:
        score = max_signals / signal_count
        feedback = (
            f"타입 작성 위반: 명시적 타입 신호 {signal_count}개 "
            f"(목표 {max_signals}개 이하)."
        )
        return score, feedback

    return (
        1.0,
        f"타입 작성 충족: 명시적 타입 신호 {signal_count}개.",
    )


def candidate_quality_issues(
    output: str, combo: dict[str, str], source_text: str = ""
) -> list[str]:
    """실제 코딩 후보가 요청한 스타일에 맞는지 보수적으로 확인한다.

    기능의 의미적 동일성은 정규식으로 증명할 수 없으므로 이 검사는 코드
    누락, 흔한 타입 오류, 세 가지 스타일 축만 검증한다.
    """
    issues = []
    blocks = CODE_BLOCK_PATTERN.findall(output)
    if not blocks or not any(block.strip() for block in blocks):
        issues.append("닫힌 코드 블록에 구현 코드가 없다")
    elif output.count("```") != 2 * len(blocks):
        issues.append("코드 블록이 닫히지 않았다")

    code = "\n".join(blocks)
    if not re.search(r"\b(?:function|const|export)\b", code):
        issues.append("TypeScript/React 구현이 확인되지 않는다")
    if re.search(r"\buseState\s*\(\s*\[\s*\]\s*\)", code):
        issues.append("빈 배열 상태에 요소 타입이 없어 TypeScript에서 never[]가 될 수 있다")
    if combo.get("type_detail") == "inferred" and re.search(
        r"\bReact\.FC\b|\b(?:const|let)\s+\w+\s*:"
        r"|\buseState\s*<\s*(?:number|string|boolean)\s*>\s*\(",
        code,
    ):
        issues.append("타입 추론 조건 위반: 추론 가능한 타입을 명시했다")
    if source_text and not re.search(r"\b(?:index|main)\.tsx?\b", source_text, re.IGNORECASE):
        if re.search(r"\b(?:index|main)\.tsx?\b", output, re.IGNORECASE):
            issues.append("요청에 없는 실행 진입점 파일을 추가했다")
    if source_text and not re.search(r"\bApp(?:\.tsx?)?\b", source_text, re.IGNORECASE):
        if re.search(r"\bApp\.tsx?\b", output, re.IGNORECASE):
            issues.append("요청에 없는 App 래퍼 파일을 추가했다")

    # 사용자가 버튼 안의 초기 문구를 정확히 지정한 경우, 같은 문구를
    # 별도 문단에 놓고 버튼 자체에는 다른 말을 쓰는 응답을 거부한다.
    requested_button_text = re.search(
        r"버튼에 보이는 문구는 처음에 정확히\s*[\"'“]?(.+?)[\"'”]?\s*이고",
        source_text,
    )
    if requested_button_text:
        initial_text = requested_button_text.group(1).strip().strip("\"'“”")
        label_prefix = re.sub(r"\d+\s*$", "", initial_text).strip()
        button_bodies = re.findall(r"<button\b[^>]*>(.*?)</button>", code, re.DOTALL | re.IGNORECASE)
        if label_prefix and not any(label_prefix in body for body in button_bodies):
            issues.append(f"버튼 문구 위반: '{initial_text}'를 버튼 안에 표시하지 않았다")

    checks = (
        ("code_structure", file_structure),
        ("style_management", theme_usage),
        ("type_detail", type_explicitness),
    )
    for axis, check in checks:
        value = combo.get(axis)
        if axis == "code_structure":
            target = {"max_files": 1} if value == "compact" else {"min_files": 2}
        elif axis == "style_management":
            target = {"max_theme_signals": 0} if value == "direct" else {"min_theme_signals": 2}
        else:
            target = {"max_signals": 3} if value == "inferred" else {"min_signals": 5}
            # Props와 빈 배열 상태처럼 필수 타입도 신호 수에 포함된다.
            # 추론형을 숫자만으로 거부하면 정상적인 React 코드까지 탈락한다.
            # 불필요한 명시는 위의 구체적인 패턴 검사로 판별한다.
            if value == "inferred":
                continue
        checked_text = output if axis == "code_structure" else code
        score, feedback = check(checked_text, "", value or "", target)
        if score < 1:
            issues.append(feedback)
    return issues

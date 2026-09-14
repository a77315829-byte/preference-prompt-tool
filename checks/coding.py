"""TypeScript/React 코딩 스타일을 검사하는 함수."""

from __future__ import annotations

import re


FILE_PATTERN = re.compile(
    r"\b[A-Za-z][\w.-]*\.(?:tsx?|css|scss)\b",
    re.IGNORECASE,
)

CODE_FENCE_PATTERN = re.compile(
    r"```(?:tsx?|css|scss)?\s*\n",
    re.IGNORECASE,
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

    code_fence_count = len(CODE_FENCE_PATTERN.findall(output))
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

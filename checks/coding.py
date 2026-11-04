"""TypeScript/React 코딩 스타일을 검사하는 함수."""

from __future__ import annotations

import re
from collections import Counter


FILE_PATTERN = re.compile(
    r"\b[A-Za-z][\w.-]*\.(?:tsx?|css|scss)\b",
    re.IGNORECASE,
)

CODE_BLOCK_PATTERN = re.compile(
    r"```(?:tsx?|typescript|javascript|jsx|css|scss)?\s*\n(.*?)```",
    re.IGNORECASE | re.DOTALL,
)

NAMED_CODE_BLOCK_PATTERN = re.compile(
    r"```(tsx?|typescript|javascript|jsx|css|scss)?\s*\n(.*?)```",
    re.IGNORECASE | re.DOTALL,
)
FILE_COMMENT_PATTERN = re.compile(
    r"^\s*(?://|/\*|\*)\s*(?:file:\s*)?([\w./-]+\.(?:tsx?|jsx?|css|scss))\b",
    re.IGNORECASE,
)


def code_module_counts(output: str) -> tuple[int, int]:
    """Count React and TypeScript modules, ignoring extra theme/style sheets."""
    tsx = ts = 0
    for match in NAMED_CODE_BLOCK_PATTERN.finditer(output):
        language, code = match.groups()
        preceding = output[:match.start()].rstrip().splitlines()
        heading = preceding[-1] if preceding else ""
        first_line = code.splitlines()[0] if code.splitlines() else ""
        comment_name = FILE_COMMENT_PATTERN.match(first_line)
        heading_name = FILE_PATTERN.search(heading)
        name = comment_name.group(1) if comment_name else (
            heading_name.group(0) if heading_name else ""
        )
        extension = name.rsplit(".", 1)[-1].lower() if name else (language or "").lower()
        if extension in {"tsx", "jsx"}:
            tsx += 1
        elif extension in {"ts", "typescript", "javascript"} and not re.search(
            r"(?:theme|token)", name, re.IGNORECASE
        ):
            ts += 1
    return tsx, ts


def pair_quality_issues(
    first: str, second: str, combo_a: dict[str, str], combo_b: dict[str, str]
) -> list[str]:
    """Catch measurable A/B drift; runtime tests still prove functional equivalence."""
    issues = []
    if combo_a.get("code_structure") == combo_b.get("code_structure"):
        first_modules = code_module_counts(first)
        second_modules = code_module_counts(second)
        if first_modules != second_modules:
            issues.append(
                "A/B 공통 코드 구조 위반: 비교하지 않는 TSX 컴포넌트/TS 로직 파일 수가 "
                f"A={first_modules}, B={second_modules}로 다르다. "
                "테마용 CSS/토큰 파일은 추가할 수 있지만 로직 파일 역할과 개수는 맞춰라"
            )

    first_interactions = interaction_signals(first)
    second_interactions = interaction_signals(second)
    if first_interactions != second_interactions:
        different = sorted(set(first_interactions) | set(second_interactions))
        details = ", ".join(
            f"{name}: A={first_interactions[name]}, B={second_interactions[name]}"
            for name in different
            if first_interactions[name] != second_interactions[name]
        )
        issues.append(
            "A/B 공통 상호작용 위반: 상태·효과·이벤트 처리 또는 호버/포커스 표현이 "
            f"서로 다르다 ({details}). 비교 축에 필요한 파일 배치·스타일 값 관리·타입만 "
            "바꾸고 동작을 위한 상태와 이벤트는 동일하게 유지하라"
        )
    return issues


def interaction_signals(output: str) -> Counter[str]:
    """Track observable interaction machinery across all supplied code files."""
    code = "\n".join(CODE_BLOCK_PATTERN.findall(output))
    signals: Counter[str] = Counter()
    for hook in ("useState", "useReducer", "useEffect", "useLayoutEffect"):
        signals[f"hook:{hook}"] = len(
            re.findall(rf"\b{hook}\s*(?:<|\()", code)
        )
    for handler in re.findall(r"\b(on[A-Z][A-Za-z]+)\s*=", code):
        signals[f"handler:{handler}"] += 1
    for method, event in re.findall(
        r"\b(addEventListener|removeEventListener)\s*\(\s*['\"]([^'\"]+)['\"]", code
    ):
        signals[f"listener:{method}:{event}"] += 1
    for pseudo in re.findall(r":(hover|focus-visible|focus|active)\b", code):
        signals[f"css:{pseudo}"] += 1
    return +signals


def inline_pseudo_conflicts(output: str) -> list[str]:
    """Find CSS hover/focus declarations hidden by inline styles on the same JSX element."""
    code = "\n".join(CODE_BLOCK_PATTERN.findall(output))
    conflicts = set()
    for css_class, pseudo, declarations in re.findall(
        r"\.([\w-]+):(hover|focus-visible|focus|active)\s*\{([^{}]*)\}", code
    ):
        css_properties = {
            re.sub(r"-([a-z])", lambda match: match.group(1).upper(), prop)
            for prop in re.findall(r"(?:^|[;\n])\s*([\w-]+)\s*:", declarations)
        }
        if not css_properties:
            continue
        for tag_start in re.finditer(r"<[A-Za-z][\w.]*\b", code):
            # JSX event handlers may contain `=>`; only a top-level `>` ends the tag.
            depth = 0
            quote = None
            escaped = False
            end = None
            for pos in range(tag_start.end(), len(code)):
                char = code[pos]
                if quote:
                    if escaped:
                        escaped = False
                    elif char == "\\":
                        escaped = True
                    elif char == quote:
                        quote = None
                elif char in "\"'`":
                    quote = char
                elif char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                elif char == ">" and depth == 0:
                    end = pos
                    break
            if end is None:
                continue
            tag = code[tag_start.start():end + 1]
            classes = re.search(r"\bclassName\s*=\s*['\"]([^'\"]+)['\"]", tag)
            if not classes or css_class not in classes.group(1).split():
                continue
            style = re.search(r"\bstyle\s*=\s*\{\s*\{(.*?)\}\s*\}", tag, re.DOTALL)
            if not style:
                continue
            inline_properties = set(re.findall(r"\b([A-Za-z]\w*)\s*:", style.group(1)))
            for prop in css_properties & inline_properties:
                conflicts.add(f".{css_class}:{pseudo}의 {prop}")
    return sorted(conflicts)


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
    # JSX는 React에서 명시적으로 가져오면 유효하다. 파일별로 검사해서
    # 한 파일의 import가 다른 파일의 전역 JSX 사용을 숨기지 않게 한다.
    if any(
        re.search(r"(?<![\w.])JSX\.[A-Za-z_]\w*", block)
        and not re.search(
            r"import\s+(?:type\s+)?\{[^}]*\bJSX\b(?!\s+as\b)[^}]*\}"
            r"\s+from\s+['\"]react['\"]",
            block,
        )
        for block in blocks
    ):
        issues.append("React 19 타입 오류: 전역 JSX 네임스페이스 대신 React.JSX를 사용하거나 타입을 추론해야 한다")
    conflicts = inline_pseudo_conflicts(output)
    if conflicts:
        issues.append(
            "호버/포커스 스타일 위반: 같은 요소의 인라인 스타일이 CSS 상태 스타일을 "
            f"덮어쓴다 ({', '.join(conflicts)}). 상태별 값은 인라인에서 제거하거나 "
            "동일하게 동작하는 방식으로 작성하라"
        )
    if combo.get("type_detail") == "inferred" and re.search(
        r"\bReact\.FC\b|\b(?:const|let)\s+\w+\s*:"
        r"|\buseState\s*<\s*(?:number|string|boolean)\s*>\s*\(",
        code,
    ):
        issues.append("타입 추론 조건 위반: 추론 가능한 타입을 명시했다")
    if combo.get("type_detail") == "explicit":
        # 타입 신호의 총개수가 많아도 공개 함수의 반환 타입은 빠질 수 있다.
        # 보수적으로 단순한 named function 선언만 검사한다. 중첩 매개변수,
        # 화살표 함수 등 모든 TypeScript 구문을 판별하는 파서는 아니다.
        for name in re.findall(
            r"^\s*export\s+(?:default\s+)?(?:async\s+)?function\s+"
            r"([A-Za-z_$][\w$]*)\s*\([^()]*\)\s*\{",
            code, re.MULTILINE,
        ):
            issues.append(
                f"타입 명시 조건 위반: 공개 함수 {name}의 반환 타입이 없다. "
                "함수 선언에 반환 타입을 명시하라"
            )
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

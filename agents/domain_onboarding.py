"""도메인 온보딩 에이전트 (CLAUDE.md v2, 우선순위 4).

사람이 domains/*.yaml + checks/*.py 를 손으로 쓰는 대신, 라벨 없는
원문·결과물 예시만 보고 에이전트가:

1. 갈릴 만한 축 후보를 제안한다 (LLM)
2. 각 축에 대해 measure(text, source) -> float 코드를 쓴다 (LLM, 샌드박스 검증)
3. 실제 예시 corpus에 그 코드를 돌려 판별력(측정값의 분산)을 잰다 (코드, 결정론적)
4. 판별력이 없으면 실패 사유를 알려주고 재시도시키거나, 재시도 상한
   도달 시 그 축을 버린다
5. 살아남은 축으로 domains/*.yaml + checks/*.py 를 새로 만든다

이게 사전에 그릴 수 있는 워크플로우가 아니라 에이전트인 이유: 3번의
실측 결과에 따라 4번에서 재시도할지 버릴지가 갈리고, 몇 번 반복될지
미리 정할 수 없다. 또한 코드를 실제로 작성하고 실행한다(도구 사용).

절대 규칙 9: 생성된 코드는 agents/sandbox.py의 검증+격리를 거친 뒤에만
실행한다. 절대 규칙 10: 이 모듈은 기존 domains/checks/engine 파일을
읽거나 고치지 않는다 - 완전히 새 파일만 만든다. 최종적으로 방출되는
domains/checks 파일은 (탐색 중 샌드박스로 검증된 코드로 조립되지만) 그
자체로 평범한 저장소 파일이 되므로, 사람이 커밋 전에 리뷰하는 걸 권장한다
(에이전트가 "안전한 코드"를 짤 수 있다는 것과 "올바른 축"을 찾았다는 것은
별개 문제다).
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from litellm import completion

from agents.sandbox import MeasureExecutionError, run_measure

MODEL = "openai/gpt-4.1-mini"
MAX_AXIS_CANDIDATES = 4
MAX_RETRIES_PER_AXIS = 2
MIN_DISCRIMINATIVE_POWER = 0.15  # (p90-p10)/(|mean|+eps) - 6주차 specificity 실측(0.217 vs
# 0.228, 거의 무변화)과 length 실측(문장수 0~16, 큰 변화)의 중간 어딘가로 잡은 임계값


@dataclass
class DocExample:
    source: str
    outputs: list[str]  # 같은 source에 대한, 라벨 없는 결과물 여러 개


@dataclass
class AxisCandidate:
    name: str
    description: str
    low_end: str
    high_end: str
    value_names: list[str]  # 예: ["short", "normal", "long"]


@dataclass
class AxisAttempt:
    code: str | None
    discriminative_power: float | None
    error: str | None


@dataclass
class AxisResult:
    candidate: AxisCandidate
    survived: bool
    attempts: list[AxisAttempt] = field(default_factory=list)
    final_code: str | None = None
    value_boundaries: list[tuple[float, float]] | None = None  # value_names와 같은 순서
    measured_range: tuple[float, float] | None = None  # 점수 정규화에 씀 (span)


def _call_llm_json(system_prompt: str, user_prompt: str) -> dict:
    response = completion(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )
    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def propose_axes(examples: list[DocExample], max_candidates: int = MAX_AXIS_CANDIDATES) -> list[AxisCandidate]:
    """예시(원문 + 같은 원문의 서로 다른 결과물 여러 개, 라벨 없음)를 보고
    갈릴 만한 축 후보를 제안시킨다."""
    sample_block = []
    for i, ex in enumerate(examples[:5]):
        outputs_block = "\n".join(f"  ({j + 1}) {o}" for j, o in enumerate(ex.outputs))
        sample_block.append(f"[Example {i + 1}] Source (truncated): {ex.source[:300]}\nOutputs:\n{outputs_block}")

    prompt = (
        "Below are several documents, each with multiple different outputs for the same "
        "source (e.g. summaries written in different styles). No labels are given. "
        "Propose up to "
        f"{max_candidates} candidate axes along which these outputs seem to vary "
        "stylistically (not content-wise). For each axis, give: name (short snake_case "
        "identifier), description, low_end (short phrase), high_end (short phrase), and "
        "value_names (an ordered list of 2-3 short value labels from low to high, e.g. "
        '["short","normal","long"]). Only propose axes you can plausibly imagine measuring '
        "from the text itself (not axes that require external knowledge). "
        'Respond as JSON: {"axes": [{"name":..., "description":..., "low_end":..., '
        '"high_end":..., "value_names": [...]}]}'
    )
    user_prompt = "\n\n".join(sample_block)

    result = _call_llm_json(prompt, user_prompt)
    return [
        AxisCandidate(
            name=a["name"],
            description=a["description"],
            low_end=a["low_end"],
            high_end=a["high_end"],
            value_names=a["value_names"],
        )
        for a in result.get("axes", [])[:max_candidates]
    ]


def write_measure_code(candidate: AxisCandidate, previous_error: str | None = None) -> str:
    """measure(text, source) -> float 코드를 작성시킨다. 높을수록 candidate.high_end에
    가깝다는 방향성만 지키면 되고, 스케일은 자유다 (판별력만 재므로)."""
    system_prompt = (
        "Write a single Python function named `measure` with signature "
        "`measure(text: str, source: str) -> float`. It should return a continuous score "
        "where higher values mean the text is more '"
        + candidate.high_end
        + "' and lower values mean more '"
        + candidate.low_end
        + "'. You may use `re`, `math`, `statistics`, `collections` WITHOUT importing them "
        "(they are already available). Do NOT write import statements. Do NOT define any "
        "other functions or use any I/O. Return ONLY the function code, no explanation, no "
        "markdown fences."
    )
    user_prompt = f"Axis: {candidate.name}\nDescription: {candidate.description}"
    if previous_error:
        user_prompt += f"\n\nYour previous attempt failed: {previous_error}\nTry a different approach."

    response = completion(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.5,
    )
    code = response.choices[0].message.content.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    return code


def measure_discriminative_power(code: str, examples: list[DocExample]) -> tuple[float, list[float]]:
    """corpus 전체(라벨 무시하고 전부 pooling)에 measure()를 돌려, 측정값이
    실제로 흩어져 있는지(=쓸모 있는 신호일 가능성)를 잰다. (p90-p10)/(|mean|+eps)
    를 쓴다 - 스케일에 안 흔들리고, 값이 사실상 상수인 경우(6주차 specificity처럼)
    0에 가까운 값을 낸다."""
    values = []
    for ex in examples:
        for output in ex.outputs:
            values.append(run_measure(code, output, ex.source))

    if len(values) < 2:
        return 0.0, values

    sorted_v = sorted(values)
    p10 = sorted_v[max(0, int(len(sorted_v) * 0.1))]
    p90 = sorted_v[min(len(sorted_v) - 1, int(len(sorted_v) * 0.9))]
    mean = statistics.fmean(values)
    power = (p90 - p10) / (abs(mean) + 1e-6)
    return power, values


def discover_axis(candidate: AxisCandidate, examples: list[DocExample]) -> AxisResult:
    result = AxisResult(candidate=candidate, survived=False)
    previous_error: str | None = None

    for attempt_num in range(1, MAX_RETRIES_PER_AXIS + 2):  # 최초 시도 + 재시도
        code = write_measure_code(candidate, previous_error)
        try:
            power, values = measure_discriminative_power(code, examples)
        except MeasureExecutionError as e:
            result.attempts.append(AxisAttempt(code=code, discriminative_power=None, error=str(e)))
            previous_error = str(e)
            continue

        result.attempts.append(AxisAttempt(code=code, discriminative_power=power, error=None))

        if power >= MIN_DISCRIMINATIVE_POWER:
            result.survived = True
            result.final_code = code
            result.value_boundaries = _compute_value_boundaries(values, len(candidate.value_names))
            result.measured_range = (min(values), max(values))
            return result

        previous_error = (
            f"측정값이 corpus 전체에서 거의 안 흩어짐 (판별력 {power:.3f} < "
            f"{MIN_DISCRIMINATIVE_POWER}). 표본 측정값: {sorted(values)[:5]}...{sorted(values)[-5:]}"
        )

    return result  # survived=False로 반환 (재시도 상한 도달)


def _py_float_literal(x: float) -> str:
    """repr(float('-inf'))는 '-inf'인데 그걸 그대로 소스코드에 박으면 파싱 시
    NameError가 난다 (inf가 파이썬 기본 이름이 아님) - float('-inf') 형태로 써야 한다."""
    if x == float("inf"):
        return "float('inf')"
    if x == float("-inf"):
        return "float('-inf')"
    return repr(x)


def _compute_value_boundaries(values: list[float], n_buckets: int) -> list[tuple[float, float]]:
    """실측 분포의 등빈도(quantile) 분할로 값별 경계를 정한다 - 임의 임계값이
    아니라 실제 데이터 기준으로 잡는다 (이 프로젝트가 여러 번 배운 교훈)."""
    sorted_v = sorted(values)
    n = len(sorted_v)
    cut_points = [sorted_v[int(n * i / n_buckets)] for i in range(1, n_buckets)]
    bounds = [-float("inf"), *cut_points, float("inf")]
    return [(bounds[i], bounds[i + 1]) for i in range(n_buckets)]


@dataclass
class DiscoveryReport:
    domain_name: str
    proposed: list[AxisCandidate]
    results: list[AxisResult]

    @property
    def survived(self) -> list[AxisResult]:
        return [r for r in self.results if r.survived]

    @property
    def dropped(self) -> list[AxisResult]:
        return [r for r in self.results if not r.survived]


def discover_domain(domain_name: str, examples: list[DocExample]) -> DiscoveryReport:
    candidates = propose_axes(examples)
    results = [discover_axis(c, examples) for c in candidates]
    return DiscoveryReport(domain_name=domain_name, proposed=candidates, results=results)


def emit_domain(report: DiscoveryReport, out_dir: str = ".") -> tuple[Path, Path]:
    """살아남은 축으로 domains/<name>.yaml + checks/<name>.py 를 새로 쓴다.
    기존 파일과 이름이 겹치지 않게 항상 <name>_agent 접미사를 붙인다 -
    사람이 만든 도메인을 덮어쓰지 않는다 (절대 규칙 10)."""
    domain_file_name = f"{report.domain_name}_agent"
    yaml_path = Path(out_dir, "domains", f"{domain_file_name}.yaml")
    checks_path = Path(out_dir, "checks", f"{domain_file_name}.py")

    yaml_lines = [
        f"# {domain_file_name} 도메인 - agents/domain_onboarding.py 가 자동 생성함.",
        "# 사람이 검토 후 커밋하는 걸 권장한다 - 안전하게 실행됐다는 것과 축이",
        "# 올바르다는 것은 별개 문제다.",
        "",
        f"domain: {domain_file_name}",
        "task_description: >-",
        "  아래 원문을 지침에 따라 처리하라.",
        "",
        f"checks_module: checks.{domain_file_name}",
        "",
        "axes:",
    ]
    checks_lines = [
        f'"""{domain_file_name} 도메인의 축별 검사 함수. agents/domain_onboarding.py 가',
        "자동 생성함 - measure_* 함수는 샌드박스에서 판별력을 검증받은 뒤 채택된",
        '코드다."""',
        "",
        "from __future__ import annotations",
        "",
        "import re",
        "import math",
        "import statistics",
        "import collections",
        "",
    ]

    for result in report.survived:
        axis = result.candidate
        fn_name = f"measure_{axis.name}"
        measure_body = result.final_code.replace("def measure(", f"def {fn_name}(", 1)
        checks_lines.append(measure_body)
        checks_lines.append("")

        yaml_lines.append(f"  - name: {axis.name}")
        yaml_lines.append("    type: enum")
        yaml_lines.append(f"    description: {axis.description}")
        yaml_lines.append("    values:")
        for value_name, (lo, hi) in zip(axis.value_names, result.value_boundaries):
            yaml_lines.append(f"      - value: {value_name}")
            yaml_lines.append(f"        prompt: 이 결과물을 '{value_name}' 수준의 {axis.name}(으)로 만들어라.")
            yaml_lines.append("        check:")
            yaml_lines.append(f"          fn: check_{axis.name}")
            yaml_lines.append("          target: {}  # 경계값은 check 함수 안에 이미 고정돼 있음")

        boundaries_src = ", ".join(
            f'"{name}": ({_py_float_literal(lo)}, {_py_float_literal(hi)})'
            for name, (lo, hi) in zip(axis.value_names, result.value_boundaries)
        )
        range_lo, range_hi = result.measured_range
        span = max(range_hi - range_lo, 1e-6)  # 탐색 시점 corpus 실측 범위로 정규화

        check_fn = f'''
def check_{axis.name}(output: str, source: str, value: str, target: dict) -> tuple[float, str]:
    m = {fn_name}(output, source)
    boundaries = {{{boundaries_src}}}
    lo, hi = boundaries[value]
    if lo <= m <= hi:
        return 1.0, f"{axis.name} 충족: 측정값 {{m:.3f}} (목표 '{{value}}')."
    if m < lo:
        distance = (lo - m) if math.isfinite(lo) else 0.0
    else:
        distance = (m - hi) if math.isfinite(hi) else 0.0
    score = max(0.0, 1.0 - distance / {span!r})
    return score, f"{axis.name} 위반: 측정값 {{m:.3f}} (목표 '{{value}}' 범위 [{{lo}}, {{hi}}])."
'''
        checks_lines.append(check_fn)

    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    checks_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text("\n".join(yaml_lines) + "\n", encoding="utf-8")
    checks_path.write_text("\n".join(checks_lines) + "\n", encoding="utf-8")
    return yaml_path, checks_path

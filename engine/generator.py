"""축조합 -> 프롬프트 조립 -> API 호출 -> 캐싱.

이 모듈은 축이 N개 있고 각 축에 값이 M개 있다는 것만 알 뿐, 어떤
도메인인지는 모른다. 같은 (조립된 프롬프트, 원문, 모델)은 캐시에 있으면
API를 다시 호출하지 않는다. 캐시 키에 축조합이 아니라 조립된 프롬프트
텍스트 자체를 쓰는 이유: domains/*.yaml의 문구가 바뀌면(축조합은 그대로여도)
실제 API에 보내는 내용이 달라지므로 캐시도 무효화돼야 한다.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Sequence
from pathlib import Path

from engine.domain_loader import Domain

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"

# 한 번의 생성 호출이 기다릴 최대 시간(초)과 출력 토큰 상한. 상한은
# 요약·리뷰·코드 한 벌에는 넉넉하고, 모델이 폭주하면 거기서 끊는다.
# 캐시 키에는 넣지 않는다 - 넣으면 기존 cache/ 가 통째로 무효화된다.
REQUEST_TIMEOUT_SECONDS = 60
MAX_OUTPUT_TOKENS = 2048

# 같은 캐시 키를 동시에 부르면 한 번만 호출하고 나머지는 기다렸다 캐시를
# 읽는다. 새로고침·분기 미리 만들기가 같은 요청을 겹쳐 보낸다.
_KEY_LOCKS: dict[str, threading.Lock] = {}
_KEY_LOCKS_GUARD = threading.Lock()


def _lock_for(key: str) -> threading.Lock:
    with _KEY_LOCKS_GUARD:
        return _KEY_LOCKS.setdefault(key, threading.Lock())


# 지시문 안의 `{source_words*R}` 는 이 원문의 단어 수 x R 로 채운다. 모델은 "원문의
# 5%" 같은 비율 지시를 스스로 환산하지 못하지만 단어 수 지시는 따른다
# (docs/length_v2_preregistration.md). 단어 수는 공백으로 나눈 개수 - 언어나 과제를
# 가정하지 않는다.
_SOURCE_WORDS = re.compile(r"\{source_words\*([0-9]*\.?[0-9]+)\}")


def fill_source_placeholders(text: str, source: str | None) -> str:
    """자리표시자가 없으면 text 를 그대로 돌려준다. 있는데 원문이 없으면 ValueError -
    조용히 비율 문구로 바꾸면 모델이 따르지 못하는 지시가 된다."""
    if not _SOURCE_WORDS.search(text):
        return text
    if source is None:
        raise ValueError("이 지시문은 원문 길이로 채워야 하는데 원문이 주어지지 않았다.")
    words = len(source.split())
    return _SOURCE_WORDS.sub(lambda m: str(round(float(m.group(1)) * words)), text)


def build_prompt(domain: Domain, combo: dict[str, str], source: str | None = None) -> str:
    """후보 생성용 프롬프트. 자리표시자가 없는 도메인은 source 와 무관하게 예전과
    글자 하나까지 같다 - 캐시 키가 이 텍스트라서다."""
    lines = [domain.task_description]
    for axis in domain.axes:
        instruction = axis.instruction_for(combo.get(axis.name, ""))
        if instruction:
            lines.append(instruction)
    return fill_source_placeholders("\n".join(lines), source)


def build_final_prompt(domain: Domain, combo: dict[str, str], team: bool = False) -> str:
    """사용자에게 건네는 최종 프롬프트. 역할 -> 과제 -> 선호 -> 규칙 ->
    출력 형식 순으로 domain.final_prompt 의 문구를 이어 붙인다.

    build_prompt 와 따로 둔다. build_prompt 는 후보를 만들 때 모델에 보내는
    문장이라 바꾸면 캐시 키와 실험 재현성이 같이 바뀐다. 이 함수는 화면에
    내보내는 결과물에만 쓴다. final_prompt 가 없는 도메인은 build_prompt
    와 같은 결과를 돌려준다.
    """
    spec = domain.final_prompt
    if spec is None:
        return build_prompt(domain, combo)

    # team: 여러 사람의 선택을 합친 프롬프트. YAML 에 팀용 문구가 있으면 그것을 쓴다.
    role = (spec.team_role if team else None) or spec.role
    sections = [role, domain.task_description]
    preferences = build_preference_section(domain, combo, team=team)
    if preferences:
        sections.append(preferences)
    sections.append("\n".join([f"## {spec.rules_heading}", *(f"- {r}" for r in spec.rules)]))
    sections.append(f"## {spec.output_heading}\n{spec.output}")
    return "\n\n".join(sections)


def build_preference_section(domain: Domain, combo: dict[str, str], team: bool = False) -> str:
    """추정한 선호만 담은 절. "## 머리말" 아래 "- 라벨: 지시" 줄들이다.
    선호가 하나도 없으면 빈 문자열. 머리말과 라벨은 domain.final_prompt 에서
    읽고, 없으면 축 설명과 기본 머리말을 쓴다."""
    spec = domain.final_prompt
    lines = []
    for axis in domain.axes:
        instruction = axis.instruction_for(combo.get(axis.name, ""))
        if instruction:
            label = (spec.axis_labels.get(axis.name) if spec else None) or axis.description
            lines.append(f"- {label}: {instruction}")
    if not lines:
        return ""
    heading = ((spec.team_preference_heading if team else None) or spec.preference_heading) if spec else "선호"
    return "\n".join([f"## {heading}", *lines])


def build_template_prompt(domain: Domain, combo: dict[str, str], template: str) -> str:
    """사용자가 고른 템플릿 본문 뒤에 추정한 선호 절을 붙인다. 템플릿의
    과제·규칙은 그대로 두고, 표현 방식만 이 사람에게 맞춘다."""
    preferences = build_preference_section(domain, combo)
    return template.strip() + (f"\n\n{preferences}" if preferences else "")


def _cache_key(
    prompt: str, source_text: str, model: str, temperature: float | None = None
) -> str:
    key: dict[str, object] = {"prompt": prompt, "source": source_text, "model": model}
    # temperature 를 지정하지 않은 호출의 캐시 키는 예전과 같아야 한다.
    # 안 그러면 기존 cache/ 전체가 한 번에 무효화된다.
    if temperature is not None:
        key["temperature"] = temperature
    payload = json.dumps(key, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_all(
    domain: Domain,
    source_text: str,
    combos: Sequence[dict[str, str]],
    model: str,
    cache_dir: Path = CACHE_DIR,
) -> list[str]:
    """여러 축조합의 결과물을 동시에 생성해 입력 순서대로 돌려준다.

    한 축조합당 API 호출 한 번이고 서로 의존이 없는데 순차로 부르면
    호출 수만큼 대기 시간이 쌓인다. UI에서 8회 x 후보 2개를 순차로
    돌리면 한 번 완주에 2분 넘게 걸렸다. API 호출은 CPU가 아니라
    네트워크 대기라서 스레드로 충분하다(GIL이 문제되지 않는다).

    캐시에 이미 있으면 generate()가 즉시 반환하므로 그 경우엔 스레드를
    띄우는 비용만 든다. 예외는 그대로 올려보낸다 - 호출하는 쪽에서
    한 번에 처리하게 한다.
    """
    if not combos:
        return []
    if len(combos) == 1:
        return [generate(domain, source_text, combos[0], model, cache_dir=cache_dir)]

    with ThreadPoolExecutor(max_workers=len(combos)) as pool:
        futures = [
            pool.submit(generate, domain, source_text, combo, model, cache_dir=cache_dir)
            for combo in combos
        ]
        # 순서를 보존해야 한다. as_completed를 쓰면 A/B가 뒤바뀐다.
        return [future.result() for future in futures]


def generate(
    domain: Domain,
    source_text: str,
    combo: dict[str, str],
    model: str,
    cache_dir: Path = CACHE_DIR,
) -> str:
    """축조합으로 프롬프트를 조립해 결과물을 만든다."""
    return generate_with_prompt(
        build_prompt(domain, combo, source=source_text), source_text, model, cache_dir=cache_dir
    )


def generate_all_with_prompts(
    prompts: Sequence[str],
    source_text: str,
    model: str,
    cache_dir: Path = CACHE_DIR,
    temperature: float | None = None,
) -> list[str]:
    """여러 시스템 프롬프트를 같은 원문에 동시에 적용해 순서대로 돌려준다.

    같은 원문에 서로 다른 프롬프트를 적용해 나란히 보여줄 때 쓴다
    (예: 개인화 전 기본 프롬프트 vs 사용자 프롬프트). generate_all 과 같은
    이유로 동시에 호출하고, 같은 이유로 순서를 보존한다.
    """
    if not prompts:
        return []
    # 선택 인자는 키워드로 넘긴다. 위치로 넘기면 인자를 하나 더할 때
    # 호출부와 테스트 대역이 조용히 깨진다 - temperature 를 더한 직후
    # 앱의 프롬프트 비교가 죽었는데, try/except 가 삼켜서 화면에는
    # "API 호출 실패"로만 보였다.
    if len(prompts) == 1:
        return [
            generate_with_prompt(
                prompts[0], source_text, model,
                cache_dir=cache_dir, temperature=temperature,
            )
        ]

    with ThreadPoolExecutor(max_workers=len(prompts)) as pool:
        futures = [
            pool.submit(
                generate_with_prompt, prompt, source_text, model,
                cache_dir=cache_dir, temperature=temperature,
            )
            for prompt in prompts
        ]
        return [future.result() for future in futures]


def generate_with_prompt(
    prompt: str,
    source_text: str,
    model: str,
    cache_dir: Path = CACHE_DIR,
    temperature: float | None = None,
) -> str:
    """조립이 끝난 시스템 프롬프트로 결과물을 만든다.

    축조합을 거치지 않고 프롬프트 문자열을 직접 받는다. 최종 산출물인
    프롬프트를 새 원문에 적용해 보여주려면 이 경로가 필요하다 - 그때는
    축조합이 아니라 프롬프트 텍스트가 입력이다.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = _cache_key(prompt, source_text, model, temperature)
    cache_file = cache_dir / f"{key}.json"

    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))["output"]

    with _lock_for(key):
        # 기다리는 동안 다른 스레드가 채웠을 수 있다.
        if cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))["output"]
        return _call_and_cache(prompt, source_text, model, temperature, cache_file)


def _call_and_cache(
    prompt: str, source_text: str, model: str, temperature: float | None, cache_file: Path
) -> str:
    # litellm은 import에만 11초가 걸린다. 첫 화면 렌더에는 필요 없으므로
    # 실제 API 호출 시점까지 미룬다 (배포 콜드스타트 12.6초 -> 약 2초).
    from litellm import completion

    extra = {} if temperature is None else {"temperature": temperature}
    response = completion(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": source_text},
        ],
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_tokens=MAX_OUTPUT_TOKENS,
        **extra,
    )
    output = response.choices[0].message.content
    # 거절·콘텐츠 필터면 content 가 None 이나 빈 문자열로 온다. 그대로
    # 캐시하면 같은 입력은 다시 호출되지 않으므로 실패가 영구히 굳는다.
    if not output or not output.strip():
        finish = getattr(response.choices[0], "finish_reason", None)
        raise RuntimeError(f"모델이 빈 응답을 돌려줬다 (finish_reason={finish})")

    # 임시 파일에 쓰고 rename 한다. 같은 키를 두 스레드가 동시에 쓰면
    # 반쯤 쓰인 JSON이 남아 다음 실행에서 깨질 수 있다. rename 은 같은
    # 디렉토리 안에서 원자적이다.
    payload = json.dumps({"prompt": prompt, "output": output}, ensure_ascii=False, indent=2)
    tmp_file = cache_file.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    tmp_file.write_text(payload, encoding="utf-8")
    os.replace(tmp_file, cache_file)
    return output

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
import threading
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Sequence
from pathlib import Path

from engine.domain_loader import Domain

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"


def build_prompt(domain: Domain, combo: dict[str, str]) -> str:
    lines = [domain.task_description]
    for axis in domain.axes:
        instruction = axis.instruction_for(combo.get(axis.name, ""))
        if instruction:
            lines.append(instruction)
    return "\n".join(lines)


def _cache_key(prompt: str, source_text: str, model: str) -> str:
    payload = json.dumps(
        {"prompt": prompt, "source": source_text, "model": model},
        ensure_ascii=False,
        sort_keys=True,
    )
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
        return [generate(domain, source_text, combos[0], model, cache_dir)]

    with ThreadPoolExecutor(max_workers=len(combos)) as pool:
        futures = [
            pool.submit(generate, domain, source_text, combo, model, cache_dir)
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
    cache_dir.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(domain, combo)
    cache_file = cache_dir / f"{_cache_key(prompt, source_text, model)}.json"

    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))["output"]

    # litellm은 import에만 11초가 걸린다. 첫 화면 렌더에는 필요 없으므로
    # 실제 API 호출 시점까지 미룬다 (배포 콜드스타트 12.6초 -> 약 2초).
    from litellm import completion

    response = completion(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": source_text},
        ],
    )
    output = response.choices[0].message.content

    # 임시 파일에 쓰고 rename 한다. 같은 키를 두 스레드가 동시에 쓰면
    # 반쯤 쓰인 JSON이 남아 다음 실행에서 깨질 수 있다. rename 은 같은
    # 디렉토리 안에서 원자적이다.
    payload = json.dumps({"prompt": prompt, "output": output}, ensure_ascii=False, indent=2)
    tmp_file = cache_file.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    tmp_file.write_text(payload, encoding="utf-8")
    os.replace(tmp_file, cache_file)
    return output

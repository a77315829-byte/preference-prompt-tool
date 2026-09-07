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
from pathlib import Path

from litellm import completion

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

    response = completion(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": source_text},
        ],
    )
    output = response.choices[0].message.content

    cache_file.write_text(
        json.dumps({"prompt": prompt, "output": output}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output

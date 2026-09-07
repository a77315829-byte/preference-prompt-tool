"""축조합 -> 프롬프트 조립 -> API 호출 -> 캐싱.

이 모듈은 축이 N개 있고 각 축에 값이 M개 있다는 것만 알 뿐, 어떤
도메인인지는 모른다. 같은 (도메인, 원문, 축조합, 모델) 조합은 캐시에
있으면 API를 다시 호출하지 않는다.
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


def _cache_key(domain_name: str, source_text: str, combo: dict[str, str], model: str) -> str:
    payload = json.dumps(
        {"domain": domain_name, "source": source_text, "combo": combo, "model": model},
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
    cache_file = cache_dir / f"{_cache_key(domain.name, source_text, combo, model)}.json"

    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))["output"]

    prompt = build_prompt(domain, combo)
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

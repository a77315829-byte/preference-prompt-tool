"""실험 실행별 저장 경로와 원자적 결과 저장. 기존 대표 결과는 기본으로 덮지 않는다."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

RUNS = Path("experiments/results/runs")


def prepare_run(stem: str, suffixes: tuple[str, ...], *, output_dir: str | Path | None = None,
                overwrite: bool = False, metadata: dict | None = None) -> tuple[dict[str, Path], Path]:
    """모델 호출 전에 충돌을 검사하고 실행 설정 파일을 예약한다.

    기본은 실행마다 새 디렉터리다. 명시한 디렉터리도 --overwrite 없이 같은
    결과를 교체할 수 없다. .run.json을 배타적으로 생성해 동시 실행 충돌도 막는다.
    """
    if Path(stem).name != stem or not stem:
        raise ValueError("결과 이름에는 경로를 넣을 수 없다")
    if overwrite and output_dir is None:
        raise ValueError("덮어쓰려면 --output-dir도 명시해야 한다")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    directory = Path(output_dir) if output_dir is not None else RUNS / f"{stamp}-{uuid.uuid4().hex[:8]}"
    paths = {suffix: directory / f"{stem}{suffix}" for suffix in suffixes}
    manifest = directory / f"{stem}.run.json"
    existing = [p for p in (*paths.values(), manifest) if p.exists()]
    if existing and not overwrite:
        raise FileExistsError(f"결과가 이미 있다: {existing[0]}. 새 --output-dir를 사용하라")
    directory.mkdir(parents=True, exist_ok=True)
    payload = {**(metadata or {}), "started_at": datetime.now(timezone.utc).isoformat(),
               "status": "running", "files": {key: str(value) for key, value in paths.items()}}
    with manifest.open("w" if overwrite else "x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
    return paths, manifest


def _atomic_write(path: Path, write) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            write(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_json(path: Path, payload: dict) -> None:
    _atomic_write(path, lambda stream: json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False))


def write_csv(path: Path, frame) -> None:
    _atomic_write(path, lambda stream: frame.to_csv(stream, index=False))


def finish_run(manifest: Path, status: str, **details) -> None:
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload.update(status=status, finished_at=datetime.now(timezone.utc).isoformat(), **details)
    write_json(manifest, payload)

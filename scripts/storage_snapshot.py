"""Back up SQLite (including attachments) and optional cache to a new directory.

Restore always creates a NEW storage directory. Stop the application and point
PPT_DB_PATH at the restored data/app.db; existing storage is never overwritten.
No application imports, .env reads, network requests, or model calls.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_db(path: Path) -> dict:
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        checks = db.execute("PRAGMA quick_check").fetchall()
        if checks != [("ok",)]:
            raise ValueError("SQLite integrity check failed")
        tables = [row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        counts = {name: db.execute('SELECT count(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0]
                  for name in tables}
        return {"quick_check": "ok", "table_rows": counts}


def new_destination(destination: Path, forbidden: list[Path]) -> Path:
    resolved = destination.resolve()
    if destination.is_symlink() or destination.exists():
        raise ValueError("Destination already exists; choose a new directory")
    for parent in [ROOT / "frontend", *forbidden]:
        if resolved == parent.resolve() or resolved.is_relative_to(parent.resolve()):
            raise ValueError("Destination must be outside the source and public frontend directories")
    return resolved


def inventory(folder: Path) -> dict:
    result = {}
    for path in sorted(folder.rglob("*")):
        if path.is_symlink():
            raise ValueError("Snapshot/cache symbolic links are not supported")
        if path.is_file() and path != folder / "manifest.json":
            name = path.relative_to(folder).as_posix()
            result[name] = {"bytes": path.stat().st_size, "sha256": digest(path)}
        elif not path.is_dir() and not path.is_file():
            raise ValueError("Only regular files and directories are supported")
    return result


def backup(source: Path, destination: Path, cache: Path | None = None) -> dict:
    source = Path(source)
    if not source.is_file() or source.is_symlink():
        raise ValueError("Source must be an existing regular SQLite file")
    if cache is not None and (not cache.is_dir() or cache.is_symlink()):
        raise ValueError("Cache must be an existing regular directory")
    target = new_destination(destination, [source.parent, *([cache] if cache else [])])
    if cache:
        inventory(cache)  # Reject links before creating output.
    target.mkdir(parents=True, mode=0o700)
    (target / "data").mkdir()
    snapshot = target / "data/app.db"
    # backup(), unlike a file copy, includes committed WAL records.
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as src:
        with closing(sqlite3.connect(snapshot)) as dst:
            src.backup(dst)
            dst.execute("PRAGMA journal_mode=DELETE")
    database = check_db(snapshot)
    if cache:
        shutil.copytree(cache, target / "cache", symlinks=True)
    manifest = {"format_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                "database": database, "cache_included": cache is not None, "files": inventory(target)}
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def validate(snapshot: Path) -> dict:
    if snapshot.is_symlink() or not snapshot.is_dir():
        raise ValueError("Snapshot must be an existing directory")
    manifest_path = snapshot / "manifest.json"
    if manifest_path.is_symlink():
        raise ValueError("Snapshot manifest must be a regular file")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format_version") != 1:
        raise ValueError("Unsupported snapshot version")
    files = inventory(snapshot)
    if manifest.get("files") != files or "data/app.db" not in files:
        raise ValueError("Snapshot inventory or SHA-256 does not match")
    if any(name != "data/app.db" and not name.startswith("cache/") for name in files):
        raise ValueError("Unexpected snapshot file")
    if check_db(snapshot / "data/app.db") != manifest.get("database"):
        raise ValueError("Snapshot database does not match its manifest")
    return manifest


def restore(snapshot: Path, destination: Path) -> dict:
    manifest = validate(snapshot)
    target = new_destination(destination, [snapshot])
    target.mkdir(parents=True, mode=0o700)
    for name in manifest["files"]:
        source = snapshot / name  # Names originate from the verified local inventory.
        output = target / name
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, output)
    if inventory(target) != manifest["files"] or check_db(target / "data/app.db") != manifest["database"]:
        raise ValueError("Restored files failed verification; do not use this directory")
    return {"status": "restored", "database": str(target / "data/app.db"),
            "files_verified": len(manifest["files"]), "cache_included": manifest["cache_included"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    save = commands.add_parser("backup")
    save.add_argument("--database", type=Path, required=True)
    save.add_argument("--destination", type=Path, required=True)
    save.add_argument("--cache", type=Path)
    read = commands.add_parser("verify")
    read.add_argument("--snapshot", type=Path, required=True)
    load = commands.add_parser("restore")
    load.add_argument("--snapshot", type=Path, required=True)
    load.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "backup":
        result = backup(args.database, args.destination, args.cache)
    elif args.command == "restore":
        result = restore(args.snapshot, args.destination)
    else:
        result = validate(args.snapshot)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

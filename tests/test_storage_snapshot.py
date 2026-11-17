"""Snapshot safety and a live SQLite WAL round trip; no user data or network."""
import json
from pathlib import Path
import sqlite3

import pytest

from scripts.storage_snapshot import backup, restore, validate


def database(tmp_path):
    path = tmp_path / "original" / "app.db"
    path.parent.mkdir()
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("CREATE TABLE attachments (id INTEGER PRIMARY KEY, body BLOB)")
    db.execute("INSERT INTO attachments VALUES (1, ?)", (b"synthetic attachment\x00\xff",))
    db.commit()
    return path, db


def test_snapshot_keeps_committed_wal_and_binary_attachment_and_cache(tmp_path):
    source, db = database(tmp_path)
    cache = tmp_path / "cache"
    (cache / "nested").mkdir(parents=True)
    (cache / "nested/manifest.json").write_text('{"synthetic": true}', encoding="utf-8")
    try:
        assert Path(str(source) + "-wal").stat().st_size > 0
        backup(source, tmp_path / "backup", cache)
        # A subsequent committed change must not leak into the saved snapshot.
        db.execute("DELETE FROM attachments")
        db.commit()
        receipt = restore(tmp_path / "backup", tmp_path / "restored")
        with sqlite3.connect(receipt["database"]) as recovered:
            assert recovered.execute("SELECT body FROM attachments").fetchone()[0] == b"synthetic attachment\x00\xff"
        assert db.execute("SELECT count(*) FROM attachments").fetchone()[0] == 0
        assert (tmp_path / "restored/cache/nested/manifest.json").read_bytes() == (cache / "nested/manifest.json").read_bytes()
        assert receipt["files_verified"] == 2
    finally:
        db.close()


@pytest.mark.parametrize("change", ["corrupt", "missing", "extra", "manifest"])
def test_invalid_snapshot_never_creates_restore_destination(tmp_path, change):
    source, db = database(tmp_path)
    db.close()
    snap = tmp_path / "backup"
    backup(source, snap)
    if change == "corrupt":
        (snap / "data/app.db").write_bytes(b"broken")
    elif change == "missing":
        (snap / "data/app.db").unlink()
    elif change == "extra":
        (snap / "extra.txt").write_text("unexpected")
    else:
        data = json.loads((snap / "manifest.json").read_text())
        data["files"]["../../escape.db"] = data["files"]["data/app.db"]
        (snap / "manifest.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="inventory|SHA-256"):
        restore(snap, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


def test_existing_destination_and_source_storage_are_never_overwritten(tmp_path):
    source, db = database(tmp_path)
    db.close()
    backup(source, tmp_path / "backup")
    original = source.read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        restore(tmp_path / "backup", source.parent)
    with pytest.raises(ValueError, match="already exists"):
        backup(source, tmp_path / "backup")
    with pytest.raises(ValueError, match="outside"):
        backup(source, source.parent / "inside-source")
    assert source.read_bytes() == original
    assert not (source.parent / "inside-source").exists()


def test_non_database_is_rejected_and_incomplete_backup_cannot_restore(tmp_path):
    source = tmp_path / "original/not-a-database"
    source.parent.mkdir()
    source.write_bytes(b"not SQLite")
    with pytest.raises(sqlite3.DatabaseError):
        backup(source, tmp_path / "backup")
    with pytest.raises(FileNotFoundError):
        validate(tmp_path / "backup")

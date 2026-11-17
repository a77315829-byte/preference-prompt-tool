"""Synthetic HTTP -> online backup -> restart -> restored HTTP rehearsal."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.smoke_hosting import run as smoke
from scripts.storage_snapshot import backup, restore, validate

RUN = ROOT / "tmp/readiness-20261117" / ("storage-" + uuid.uuid4().hex[:8])
RUN.mkdir(parents=True)
PORT = 18770
BASE = f"http://127.0.0.1:{PORT}"
results = []
process = None
log = None


def request(path, cookie="", body=None, expected=200):
    headers = {"Cookie": cookie, "Content-Type": "application/json"}
    req = urllib.request.Request(BASE + path, None if body is None else json.dumps(body).encode(), headers)
    try:
        response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        assert response.status == expected, (path, response.status, expected)
        return json.loads(response.read()), response.headers


def stop():
    global process, log
    if process is not None:
        process.terminate()
        process.wait(timeout=15)
        process = None
    if log:
        log.close()
        log = None


def start(db, name):
    global process, log
    env = dict(os.environ, VERIFY_RUN_DIR=str(RUN), VERIFY_DB_PATH=str(db), VERIFY_PORT=str(PORT))
    log = (RUN / f"{name}.log").open("w", encoding="utf-8")
    process = subprocess.Popen([sys.executable, "-X", "utf8", str(Path(__file__).with_name("offline.py")), "server"],
        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    for _ in range(45):
        if process.poll() is not None:
            raise RuntimeError(f"Server exited; inspect {name}.log")
        try:
            health, _ = request("/api/health")
            assert health["live"] is False
            return
        except OSError:
            time.sleep(0.5)
    raise TimeoutError("Disposable server did not start")


def check(name, fn):
    fn()
    results.append({"name": name, "pass": True})
    print("PASS", name, flush=True)


def main():
    original = RUN / "original/data/app.db"
    original.parent.mkdir(parents=True)
    cache = RUN / "original/cache"
    cache.mkdir()
    (cache / "synthetic.json").write_text('{"answer":"cached synthetic response"}', encoding="utf-8")
    state_file = RUN / "private-state.json"
    start(original, "original-server")
    check("empty storage creates account, preference, handoff and attachment", lambda: smoke(BASE, state_file, "create"))
    state = json.loads(state_file.read_text())
    owner = state["cookie"]
    _, headers = request("/api/auth/signup", body={"username": "other_" + uuid.uuid4().hex[:10], "password": uuid.uuid4().hex})
    other = headers["Set-Cookie"].split(";", 1)[0]
    session, _ = request("/api/sessions", owner, {"domainKey": "summarization", "sourceText": "Synthetic source. It remains private."}, 201)
    session_id = session["session"]["session_id"]
    check("another account cannot read the saved preference", lambda: request(f"/api/preferences/{state['preference']}", other, expected=404))
    check("another account cannot read the comparison", lambda: request(f"/api/sessions/{session_id}", other, expected=404))
    snapshot = RUN / "snapshot"
    check("online SQLite backup and optional cache pass integrity checks", lambda: backup(original, snapshot, cache))
    validate(snapshot)
    after, _ = request("/api/preferences", owner, {"title": "After snapshot", "domainKey": "coding", "prompt": "Post-snapshot data"}, 201)
    stop()
    start(original, "restart-server")
    check("restart keeps login, saved preference, handoff and binary file", lambda: smoke(BASE, state_file, "verify"))
    check("restart discards the unsaved comparison", lambda: request(f"/api/sessions/{session_id}", owner, expected=404))
    stop()
    target = RUN / "restored"
    restored = restore(snapshot, target)
    start(Path(restored["database"]), "restored-server")
    check("restored storage preserves login, saved preference, handoff and file", lambda: smoke(BASE, state_file, "verify"))
    check("restored owner can read only the snapshot state", lambda: request(f"/api/preferences/{after['preference']['id']}", owner, expected=404))
    check("restored account boundary still denies another account", lambda: request(f"/api/preferences/{state['preference']}", other, expected=404))
    assert (target / "cache/synthetic.json").read_bytes() == (cache / "synthetic.json").read_bytes()
    results.append({"name": "cache restored byte for byte without regeneration", "pass": True})
    stop()


if __name__ == "__main__":
    try:
        main()
    finally:
        stop()
        receipt = {"results": results, "complete": len(results) == 10,
                   "paid_model_api_calls": 0, "real_user_data_used": False}
        (RUN / "results.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print("Evidence:", RUN / "results.json")

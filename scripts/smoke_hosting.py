"""Exercise a disposable hosted deployment before/after restart, without AI.

Uses only synthetic accounts/data. Keep the temporary state file out of git.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid


def run(base: str, state_file: Path, phase: str) -> None:
    cookie = ""

    def request(path, body=None, expected=200, raw=False):
        headers = {"Cookie": cookie} if cookie else {}
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(base + path,
            json.dumps(body).encode("utf-8") if body is not None else None, headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            assert response.status == expected, (path, response.status)
            data = response.read()
            return (data if raw else json.loads(data)), response.headers

    for attempt in range(60):
        try:
            health, _ = request("/api/health")
            assert health["ok"] and not health["live"], "Use a disposable server with PPT_LIVE=0"
            break
        except (OSError, urllib.error.URLError):
            if attempt == 59:
                raise
            time.sleep(1)

    if phase == "create":
        page, _ = request("/?handoff=smoke", raw=True)
        assert b'id="root"' in page
        _, headers = request("/api/auth/signup", {
            "username": "smoke_" + uuid.uuid4().hex[:12], "password": uuid.uuid4().hex})
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        preference, _ = request("/api/preferences", {
            "title": "Hosting smoke preference", "domainKey": "coding",
            "prompt": "Explain in concise steps.", "note": "Synthetic deployment verification"}, 201)
        handoff, _ = request("/api/handoffs", {
            "title": "Hosting smoke handoff", "purpose": "Check durable storage",
            "progress": "Created via disposable HTTP smoke test", "remaining": "Verify after restart",
            "references": ["https://example.test/reference"], "prompt": "Explain in concise steps."}, 201)
        item = handoff["handoff"]
        attached, _ = request(f"/api/handoffs/{item['id']}/attach", {
            "revision": item["revision"], "name": "smoke.txt",
            "data": base64.b64encode(b"persistent synthetic attachment\n").decode("ascii")})
        item = attached["handoff"]
        state_file.write_text(json.dumps({"cookie": cookie,
            "preference": preference["preference"]["id"], "handoff": item["id"],
            "revision": item["revision"], "file": item["body"]["attachments"][0]["id"]}), encoding="utf-8")
        templates, _ = request("/api/templates")
        assert len(templates["templates"]) == 24
        for domain in ("coding", "summarization"):
            data, _ = request("/api/sessions", {"domainKey": domain,
                "sourceText": "A team released a small update. Testing finished. The next release is planned.",
                "demoMode": True}, 201)
            assert data["session"]["demo_mode"]
        print("Hosted page, login, preference, handoff, attachment, templates and both demo domains: passed")
    else:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        cookie = state["cookie"]
        preference, _ = request(f"/api/preferences/{state['preference']}")
        assert preference["preference"]["prompt"] == "Explain in concise steps."
        handoff, _ = request(f"/api/handoffs/{state['handoff']}")
        assert handoff["handoff"]["body"]["remaining"] == "Verify after restart"
        data, _ = request(f"/api/handoffs/{state['handoff']}/files/{state['file']}?revision={state['revision']}", raw=True)
        assert data == b"persistent synthetic attachment\n"
        print("After restart: session, saved preference, handoff and attachment persisted")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--phase", choices=("create", "verify"), required=True)
    args = parser.parse_args()
    run(args.base_url.rstrip("/"), args.state_file, args.phase)

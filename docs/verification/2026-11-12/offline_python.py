"""Run local regression or a disposable HTTP server with model access disabled.

No secrets or user database are read. Only loopback Python socket connections
are allowed in this process. Test subprocesses inherit the scrubbed environment.
"""
from pathlib import Path
import atexit
import ipaddress
import json
import os
import runpy
import socket
import sys

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "tmp" / "integration-20261112"
RUN.mkdir(parents=True, exist_ok=True)
mode = sys.argv[1]
assert mode in {"pytest", "server"}
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
for key in list(os.environ):
    if key.endswith(("_API_KEY", "_API_TOKEN")) or key.startswith("OPENAI_"):
        os.environ.pop(key, None)
    if key.startswith("PPT_"):
        os.environ.pop(key, None)
os.environ.update({
    "PYTHON_DOTENV_DISABLED": "1", "PYTHONUTF8": "1",
    "PPT_LIVE": "0", "PPT_FASTAPI_GEPA_LIVE": "0",
    "PPT_SPRING_BOOT_GEPA_LIVE": "0", "PPT_WEB_GEPA_LIVE": "0",
    "PPT_PYTHON_WEB_GEPA_LIVE": "0", "PPT_COOKIE_SECURE": "0",
    "PPT_DB_PATH": str(RUN / ("browser.db" if mode == "server" else "regression-import.db")),
    "PPT_API_HOST": "127.0.0.1", "PPT_API_PORT": "18762", "PORT": "18762",
    "LITELLM_LOCAL_MODEL_COST_MAP": "True", "HF_HUB_OFFLINE": "1",
})
blocked = []
connect = socket.socket.connect
connect_ex = socket.socket.connect_ex


def allowed(address):
    if not isinstance(address, tuple):
        return True  # Local IPC, not a TCP destination.
    host = address[0]
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def guarded(original):
    def call(self, address):
        if not allowed(address):
            blocked.append({"host": str(address[0]), "port": address[1]})
            (RUN / f"{mode}-network-denials.json").write_text(json.dumps(blocked, indent=2), encoding="utf-8")
            raise OSError("Offline verification blocks non-loopback connections")
        return original(self, address)
    return call


socket.socket.connect = guarded(connect)
socket.socket.connect_ex = guarded(connect_ex)


@atexit.register
def receipt():
    (RUN / f"{mode}-offline-guard.json").write_text(json.dumps({
        "dotenv_disabled": True, "model_credentials_removed": True,
        "model_live_flags_disabled": True, "database": os.environ["PPT_DB_PATH"],
        "non_loopback_denials": blocked,
    }, indent=2), encoding="utf-8")


if mode == "pytest":
    import pytest
    raise SystemExit(pytest.main(["-m", "not api", *sys.argv[2:]]))
else:
    runpy.run_module("hosting_server", run_name="__main__")

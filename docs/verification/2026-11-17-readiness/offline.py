"""Run tests or a disposable server without loading secrets or model access."""
from pathlib import Path
import atexit
import ipaddress
import json
import os
import runpy
import socket
import sys

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(os.environ.get("VERIFY_RUN_DIR", ROOT / "tmp/readiness-20261117")).resolve()
if not RUN.is_relative_to(ROOT / "tmp"):
    raise ValueError("Verification output must be inside the repository tmp directory")
RUN.mkdir(parents=True, exist_ok=True)
mode = sys.argv[1]
assert mode in {"pytest", "server"}
db = Path(os.environ.get("VERIFY_DB_PATH", RUN / "demo.db")).resolve()
if not db.is_relative_to(RUN):
    raise ValueError("Use a disposable database inside the verification directory")
port = os.environ.get("VERIFY_PORT", "18769")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
for key in list(os.environ):
    if key.endswith(("_API_KEY", "_API_TOKEN")) or key.startswith(("OPENAI_", "PPT_")):
        os.environ.pop(key, None)
os.environ.update({
    "PYTHON_DOTENV_DISABLED": "1", "PYTHONUTF8": "1",
    "PPT_LIVE": "0", "PPT_FASTAPI_GEPA_LIVE": "0",
    "PPT_SPRING_BOOT_GEPA_LIVE": "0", "PPT_WEB_GEPA_LIVE": "0",
    "PPT_PYTHON_WEB_GEPA_LIVE": "0", "PPT_COOKIE_SECURE": "0",
    "PPT_DB_PATH": str(db), "PPT_API_HOST": "127.0.0.1",
    "PPT_API_PORT": port, "PORT": port,
    "PPT_SESSION_TTL_HOURS": os.environ.get("VERIFY_SESSION_TTL_HOURS", "12"),
    "LITELLM_LOCAL_MODEL_COST_MAP": "True", "HF_HUB_OFFLINE": "1",
})
blocked = []


def guarded(original):
    def call(self, address):
        if isinstance(address, tuple):
            host = address[0]
            try:
                local = host == "localhost" or ipaddress.ip_address(host).is_loopback
            except ValueError:
                local = False
            if not local:
                blocked.append({"host": str(host), "port": address[1]})
                raise OSError("Offline verification blocks non-loopback connections")
        return original(self, address)
    return call


socket.socket.connect = guarded(socket.socket.connect)
socket.socket.connect_ex = guarded(socket.socket.connect_ex)


@atexit.register
def receipt():
    (RUN / f"{mode}-offline-guard.json").write_text(json.dumps({
        "dotenv_disabled": True, "model_credentials_removed": True,
        "model_live_flags_disabled": True, "database": str(db),
        "non_loopback_denials": blocked,
    }, indent=2), encoding="utf-8")


if mode == "pytest":
    import pytest
    raise SystemExit(pytest.main(["-m", "not api", *sys.argv[2:]]))
else:
    runpy.run_module("hosting_server", run_name="__main__")

"""Record local verification source hashes; never read user state or credentials."""
from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[3]
RUN=ROOT/"tmp/integration-20261112"
files=list(ROOT.glob("*.py"))
for directory in ["engine","domains","checks","demos","optimize","agents","prompt_workspace","scripts","tests","frontend/src","frontend/test-support"]:
    files.extend(p for p in (ROOT/directory).rglob("*") if p.is_file() and p.suffix in {".py",".js",".jsx",".mjs",".ts",".tsx",".css",".yaml"})
for name in ["frontend/package.json","frontend/package-lock.json","pytest.ini","Dockerfile"]:
    files.append(ROOT/name)
hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(files))}
target=RUN/"final-source-hashes.json"
if sys.argv[1]=="record":
    assert not target.exists(), "Do not replace a final source snapshot"
    target.write_text(json.dumps(hashes,indent=2),encoding="utf-8")
else:
    assert hashes==json.loads(target.read_text(encoding="utf-8")), "Sources changed after final regression started"
frozen=json.loads((ROOT/"benchmarks/summary_contract_revision/results/2026-11-10/frozen.json").read_text(encoding="utf-8"))
contract_key="domains\\summary_contract.yaml"
assert hashes["domains/summary_contract.yaml"]==frozen[contract_key]
print(f"{sys.argv[1]}: {len(hashes)} source files; frozen summary contract bytes unchanged")

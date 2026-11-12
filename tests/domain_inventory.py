"""Distinguish engine definitions from explicitly declared support resources.

summary_contract.yaml contains localized constraint-handling copy, not engine
axes. Its original path/bytes are retained for frozen experiment provenance.
Every other top-level YAML, including any newly added file, remains subject to
the complete engine-domain validation (no skipping on missing schema fields).
"""
from pathlib import Path

DOMAIN_DIR = Path(__file__).resolve().parents[1] / "domains"
SUPPORT_CONFIGS = frozenset({"summary_contract.yaml"})
ENGINE_DOMAINS = sorted(path for path in DOMAIN_DIR.glob("*.yaml") if path.name not in SUPPORT_CONFIGS)

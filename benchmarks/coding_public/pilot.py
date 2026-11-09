"""Explicitly authorized, cached Luna pilot: 20 paired tasks, 100 attempts maximum.

No code is executed here. Generation requires --execute; analysis is separate.
All money is integer nano-USD. Ambiguous failures retain their full reservation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from .run import ASSETS, CACHE, ROOT, asset_bytes, audit_dataset, request_manifest

OUTPUT = CACHE / "luna-pilot-v1"
CAP = 230_000_000  # $0.23, excluding tax and exchange fees.
MODEL = "gpt-6-luna"
SETTINGS = {
    "model": MODEL, "reasoning": {"effort": "none"},
    "max_output_tokens": 4096, "service_tier": "default", "store": False,
    # No explicit breakpoints: disable provider prompt caching and write charges.
    # Application-level answer caching below remains mandatory.
    "prompt_cache_options": {"mode": "explicit"},
}


def sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def save(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    # Windows antivirus/indexers can briefly hold the destination open. Retry only
    # the local atomic rename, never the API call; exhaustion still fails closed.
    for attempt in range(6):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.05 * 2 ** attempt)


def prepare() -> dict:
    datasets = {name: audit_dataset(name, asset_bytes(name, CACHE))[0] for name in ("humaneval", "mbpp")}
    rows = [r for r in request_manifest(datasets) if r["pilot"]]
    prepared = [json.loads(line) for line in
                (CACHE / "prepared/requests.NOT_EXECUTED.jsonl").read_text(encoding="utf-8").splitlines()]
    if rows != [r for r in prepared if r["pilot"]]:
        raise ValueError("Frozen request manifest changed; do not silently rerun a new experiment")
    for row in rows:
        row["payload"] = {**SETTINGS, "input": row["messages"]}
        row["id"] = sha(row["payload"])
        row["reservation_nano_usd"] = row["input_token_budget"] * 100 + 4096 * 500
    # Deterministic shuffled execution order prevents all baseline calls running first.
    rows.sort(key=lambda r: sha("luna-order-v1:" + r["id"]))
    if len(rows) != 100 or len({r["id"] for r in rows}) != 100 or len({r["task_id"] for r in rows}) != 20:
        raise ValueError("Expected exactly 20 tasks and 100 unique requests")
    plan = {"version": 1, "budget_nano_usd": CAP, "settings": SETTINGS,
            "rates_nano_usd_per_token": {"input": 100, "output": 500},
            "pricing_checked": "2026-11-09", "requests": rows,
            "dataset_sha256": {k: ASSETS[k]["sha256"] for k in ("humaneval", "mbpp", "mbpp_noextreme")},
            "reserved_total_nano_usd": sum(r["reservation_nano_usd"] for r in rows),
            "scope": "Direct-setting prompt assembly; not human preference recovery or GEPA",
            "metrics": ["EvalPlus base and base+plus pass@1", "paired task wins/ties/losses",
                        "RACE static indicators", "comment count", "function count", "code lines", "tokens and latency"],
            "analysis": "All 20 tasks per condition; invalid/truncated outputs count as failures. No retries or repairs.",
            "input_budget": "UTF-8 serialized message bytes * 1.1 + 128; conservative allowance, not tokenizer measurement",
            "limits": "100 single samples; Python algorithm tasks; no human preference, edit time, or 8-10-choice validation"}
    if plan["reserved_total_nano_usd"] > CAP:
        raise ValueError("Projected maximum exceeds approved $0.23; approval required before generation")
    return plan


def charge(response: dict, request: dict) -> int:
    """Fail closed if a response no longer matches the approved pricing assumptions."""
    model = response.get("model", "")
    if model != MODEL and not model.startswith(MODEL + "-"):
        raise ValueError("Unexpected returned model")
    if response.get("service_tier") != "default":
        raise ValueError("Unexpected service tier")
    usage = response["usage"]
    input_count, output_count = usage["input_tokens"], usage["output_tokens"]
    if any(type(n) is not int or n < 0 for n in (input_count, output_count)):
        raise ValueError("Invalid usage")
    details = usage.get("input_tokens_details") or {}
    if details.get("cached_tokens", 0) or details.get("cache_write_tokens", 0):
        raise ValueError("Unexpected provider cache use; retain reservation and stop")
    if input_count > request["input_token_budget"] or output_count > SETTINGS["max_output_tokens"]:
        raise ValueError("Usage exceeded request allowance; stop before next call")
    return input_count * 100 + output_count * 500


def committed(ledger: dict) -> int:
    return sum(e.get("cost_nano_usd", e["reservation_nano_usd"]) for e in ledger["entries"].values())


def execute(plan: dict, output: Path, client) -> dict:
    """Client injection allows offline tests; caller owns process lock."""
    ledger_path = output / "ledger.json"
    plan_hash = sha(plan)
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {"plan_sha256": plan_hash, "entries": {}}
    if ledger["plan_sha256"] != plan_hash:
        raise ValueError("Plan changed; refusing additional paid requests")
    if not set(ledger["entries"]).issubset({r["id"] for r in plan["requests"]}):
        raise ValueError("Unrecognized ledger request")
    for request in plan["requests"]:
        key = request["id"]
        answer = output / "answers" / (key + ".json")
        entry = ledger["entries"].get(key)
        if entry is not None:
            # Even an interrupted save cannot trigger a duplicate model request.
            if not answer.exists():
                raise RuntimeError("Previous attempt has no cached response; uncertain charge, automatic retry forbidden")
            result = json.loads(answer.read_text(encoding="utf-8"))
            if result["payload_sha256"] != key:
                raise ValueError("Cached payload mismatch")
            cost = charge(result["response"], request)
            entry.update(status="cached", cost_nano_usd=cost)
            save(ledger_path, ledger)
            continue
        if answer.exists():
            raise ValueError("Answer without ledger; reconcile before proceeding")
        if len(ledger["entries"]) >= 100 or committed(ledger) + request["reservation_nano_usd"] > CAP:
            raise RuntimeError("Budget/attempt limit reached; no further API call")
        entry = {"task_id": request["task_id"], "condition": request["condition"],
                 "reservation_nano_usd": request["reservation_nano_usd"], "status": "reserved"}
        ledger["entries"][key] = entry
        save(ledger_path, ledger)  # Durable reservation BEFORE network activity.
        started = time.monotonic()
        try:
            response = client.responses.create(**request["payload"])
            result = {"payload_sha256": key, "response": response.model_dump(mode="json"),
                      "output_text": response.output_text, "elapsed_seconds": round(time.monotonic() - started, 3)}
            save(answer, result)  # Cache even incomplete or refused answers; never regenerate.
            cost = charge(result["response"], request)
            entry.update(status="received", cost_nano_usd=cost,
                         response_status=result["response"].get("status"))
            save(ledger_path, ledger)
        except Exception as error:
            entry.update(status="stopped", error_type=type(error).__name__,
                         http_status=getattr(error, "status_code", None))
            save(ledger_path, ledger)
            # No exception message/headers or client settings are printed.
            raise RuntimeError(f"Stopped after attempt {len(ledger['entries'])}: {type(error).__name__}; no retry") from None
        print(json.dumps({"completed": len(ledger["entries"]), "of": 100,
                          "cost_usd": committed(ledger) / 1e9, "task": request["task_id"],
                          "condition": request["condition"]}), flush=True)
    return ledger


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Permit the explicitly approved 100 Luna calls, capped at $0.23")
    args = parser.parse_args()
    plan = prepare()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "answers").mkdir(exist_ok=True)
    plan_path = OUTPUT / "plan.json"
    if plan_path.exists() and json.loads(plan_path.read_text(encoding="utf-8")) != plan:
        raise ValueError("Existing plan differs; experiment is immutable")
    save(plan_path, plan)
    print(json.dumps({"planned_calls": 100, "max_estimated_usd": plan["reserved_total_nano_usd"] / 1e9,
                      "cap_usd": CAP / 1e9, "execute": args.execute}), flush=True)
    if not args.execute:
        return
    from dotenv import load_dotenv
    from openai import OpenAI

    # Existing project credential convention; never display or edit .env values.
    load_dotenv(ROOT / ".env", override=False)
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY unavailable; no paid requests made")
    client = OpenAI(api_key=key, base_url="https://api.openai.com/v1", max_retries=0, timeout=120)
    lock = OUTPUT / "execution.lock"
    with lock.open("x", encoding="utf-8") as handle:
        handle.write(str(os.getpid()))
    try:
        ledger = execute(plan, OUTPUT, client)
        print(json.dumps({"complete": True, "attempts": len(ledger["entries"]),
                          "usage_estimated_usd": committed(ledger) / 1e9}), flush=True)
    finally:
        lock.unlink()
        client.close()


if __name__ == "__main__":
    main()

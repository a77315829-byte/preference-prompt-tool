"""One offline request over stdin/stdout; actual functions, isolated SQLite only."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from app_db import Database
from coding_instructions import build_coding_instructions
from coding_elicitation import build_adaptive_coding_elicitation
from coding_work_exports import export_preview
from personal_prompts import PersonalPromptStore


def main():
    request = json.load(sys.stdin)
    database_path = Path(request["database"]).resolve()
    if not database_path.is_relative_to(HERE) or database_path.suffix != ".db":
        raise ValueError("Only audit-owned SQLite paths are allowed")
    database = Database(database_path)
    with database.connect() as connection:
        connection.execute("INSERT OR IGNORE INTO users VALUES (1, 'audit', 'audit-not-a-password', 'audit')")
    store = PersonalPromptStore(database)
    operation = request["operation"]
    body = request.get("body", {})
    if operation == "preview":
        result = {"draft": build_coding_instructions(body["profile"])}
    elif operation == "examples":
        result = {"examples": build_adaptive_coding_elicitation(body["profile"])}
    elif operation == "create":
        result = {"preference": store.create(1, body)}
    elif operation == "list":
        result = {"preferences": store.list_for(1)}
    elif operation == "get":
        result = {"preference": store.get(1, request["id"])}
    elif operation == "export":
        result = export_preview(body)
    else:
        raise ValueError("Unrecognized operation")
    result["auditRuntime"] = {"executable": sys.executable, "version": sys.version}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

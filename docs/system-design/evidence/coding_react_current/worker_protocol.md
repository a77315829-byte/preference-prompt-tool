# Candidate generation worker protocol

Each worker starts with `fork_turns=none`, inherits the same parent runtime, and receives one arm input path. It reads repository `CLAUDE.md` and only its assigned `inputs/<arm>.json`. It must not inspect task-control files, evaluator code, other inputs/outputs, scores, prior experiments, or network services.

Process the eight requests in the supplied order. Treat every request as a separate task with only its supplied starter. Write the natural answer that request calls for; do not add an alternative full-files artifact that would override a changes-focused answer. Capture the first completed answer for each ID in a plain JSON array of `{ "id": "...", "answer": "..." }`.

No shell/compiler/test execution of candidate code, model APIs, external browsing, new dependencies, or paid services. Reasoning while composing the first answer is allowed. Do not obtain evaluation feedback, retry for a better score, inspect hidden tests, or repair answers after they have been saved. Only JSON structure, exact eight IDs and nonempty answer strings may be checked before saving.

Save UTF-8 to `outputs/<arm>.json.pending`, then rename atomically to `outputs/<arm>.json`, refusing overwrite. Give a concise completion message. The root retains the raw first response and separately applies only literal, unambiguous code edits before execution.

Task order offsets are predeclared in `run.py`. Worker isolation is by context/instructions on a shared workspace, not by an operating-system boundary. Within-worker answers may be correlated. This pilot measures returned artifacts, not independent user preference or human editing time.

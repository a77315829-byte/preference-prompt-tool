# First-response generation protocol

Use a fresh Codex context (`fork_turns=none`, inherited runtime without model override) per arm. Read `CLAUDE.md` and only the assigned `inputs/<arm>.json`. Do not inspect other arms, hidden task controls, evaluator, rubric, raw outputs, reviews, prior studies or network sources.

Process the eight requests in listed order. Each is a separate feature task, with only its supplied contract and requirements. Write the natural answer requested by the prompt, including named full source files; do not add a parallel hidden artifact. Capture the first completed answer as `{id, answer}` in a JSON array. Do not execute code, typecheck, run tests, browse, invoke model APIs, install packages or read secrets/user databases.

Only JSON shape, exact eight IDs/order and nonempty answer strings may be checked. Do not regenerate for quality or obtain score feedback. Save UTF-8 `outputs/<arm>.json.pending` and rename atomically without overwriting to `outputs/<arm>.json`. Each condition's eight answers share a worker context, so they may correlate. This protocol does not measure human preferences or editing time.

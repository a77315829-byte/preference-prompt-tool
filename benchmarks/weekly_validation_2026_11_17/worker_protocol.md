# First-response generation

Read CLAUDE.md and your assigned input JSON only. Do not inspect other arms, old experiments, evaluation scripts, controls, source annotations, rubrics or generated outputs. Work only in the assigned `outputs/<arm>/` directory.

Process all 14 input rows in their fixed order. Produce one first answer to each row's `request`. For summary rows, the answer contains only the requested summary. For React rows, give complete filenames and fenced file contents followed by the requested short explanation. Do not execute, compile, test, browse, install packages or call any model API. Do not claim execution occurred. Do not ask for missing information unless the request is genuinely impossible; if so preserve that clarification as the first response.

Save each answer once as UTF-8 JSON at `outputs/<arm>/<id>.json`:

```json
{"id":"the input id","kind":"summary or react","answer":"the first response verbatim"}
```

Use exclusive writes. Shell/Python may be used only to read the assigned inputs or serialize authored answer text, never to run generated React code. Work on one output file at a time. Do not reopen and improve a saved answer. Do not compare outputs, measure scores, revise in response to imagined checks, or change an input. Report completion and paths to the coordinator. Exact model identity/decoding/usage are unavailable; elapsed agent time is not human work time. Paid API calls must remain zero.

# Independent anonymous review

Read only CLAUDE.md, this file, `reviewer_rubric.json`, `blind_summary.json`, and `blind_react.json`. Do not inspect inputs, arm mapping, old experiments, automatic metrics, generated-code files, execution results, another review or tests. Do not run generated code or model APIs. You did not generate any answer in this run.

Judge every anonymous answer independently from its source/task and fixed target. Save one first judgment per output ID in your assigned `reviews/<reviewer>/Bxxx.json`, using exclusive writes. Read packets in small batches if necessary. Do not revise a judgment after saving, do not infer the arm, and do not choose scores to obtain a desired comparison. Missing evidence or genuine ambiguity must be visible. Record only exact answer excerpts as evidence; do not paraphrase inside evidence fields. An absent obligation can have an empty evidence list with a reason.

For a summary, save:

```json
{
  "output_id": "B001", "kind": "summary",
  "response_kind": "summary", "sentence_count": 3,
  "length_pass": true, "wording_pass": true,
  "wording_reason": "Reason tied to the requested wording level",
  "facts": [{"id":"F1","preserved":true,"evidence":["exact answer excerpt"],"reason":"why"}],
  "priorities": [{"id":"P1","preserved":true,"evidence":["exact answer excerpt"],"reason":"why"}],
  "issues": [{"evidence":"exact answer excerpt","reason":"unsupported/distorted claim and source comparison"}],
  "ambiguities": []
}
```

Include all three F1–F3 facts and all three P1–P3 passages, each exactly once. Empty `issues` is valid. `response_kind` is summary, clarification or other. Sentence count is grammatical, not the number of lines or semicolons; record uncertainty. Check the entire answer for unsupported facts, changed quantities, claims asserted as fact, misplaced attribution and unclear pronouns. Missing information is separate from hallucination. In `prioritize_with_omission`, an omitted selected point remains false but is allowed and must not automatically become a policy violation. Required-passage preservation concerns the semantic information in the passage under the frozen rubric; explain material omissions. Do not treat supplied source stories, opinions or allegations as your own endorsement.

For React, save:

```json
{
  "output_id": "B002", "kind": "react",
  "dimensions": {
    "code_structure": {"match":true,"evidence":["exact excerpt"],"reason":"why"},
    "style_management": {"match":true,"evidence":["exact excerpt"],"reason":"why"},
    "type_detail": {"match":true,"evidence":["exact excerpt"],"reason":"why"}
  },
  "other_observations": [], "unsupported_execution_claims": [], "ambiguities": []
}
```

Read the supplied code semantically; file counts, token names and annotation counts alone are insufficient. A meaningful style-only separation satisfies `separated`; no additional state hook/file is required. Necessary empty-array/null/union/public/CSS/event annotations satisfy `inferred`; redundant scalar-state generics/simple local-return annotations do not. For `explicit`, concise inline callbacks can use contextual typing when the principal functions/state are explicitly typed. Record nuanced boundaries in ambiguities and retain your own verdict. Do not claim type compilation or functional tests passed. Code correctness is measured separately. Flag omitted supplied files or incorrect panel design values as supporting observations rather than silently changing the three-axis rubric.

Completion means 28 JSON files. Report only completion counts/path and any genuine inability to judge. These are AI-assisted reviews, not human judgments or evidence of human productivity.

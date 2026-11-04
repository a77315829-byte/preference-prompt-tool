"""Regression tests for offline persona verification; no API calls."""

import json

import pytest

from benchmarks.coding_ai_quality.evaluate_persona_poc import independent_style_issues
from benchmarks.coding_ai_quality.evaluate_trial import evaluate


def test_explicit_public_return_type_is_checked_independently():
    combo = {"type_detail": "explicit"}
    assert independent_style_issues("export default function FAQ() {}", combo)
    assert not independent_style_issues("export default function FAQ(): ReactElement {}", combo)
    assert not independent_style_issues("export default function FAQ() {}", {"type_detail": "inferred"})


@pytest.mark.parametrize("exclusive", [False, True])
def test_multi_faq_requires_independent_answers(tmp_path, exclusive):
    # Reviewed local fixture: React state and DOM only, no external side effects.
    update = "new Set([index])" if exclusive else "new Set(current).add(index)"
    source = """import { useState } from 'react';
export default function FAQ() {
  const [open, setOpen] = useState<Set<number>>(new Set());
  return <section>{[0, 1, 2].map(index => <div key={index}>
    <button aria-expanded={open.has(index)} aria-controls={'a' + index}
      onClick={() => setOpen(current => {
        if (current.has(index)) {
          const next = new Set(current); next.delete(index); return next;
        }
        return UPDATE;
      })}>Question {index}</button>
    <p id={'a' + index} hidden={!open.has(index)}>Answer {index}</p>
  </div>)}</section>;
}""".replace("UPDATE", update)
    answer = f"```tsx\n{source}\n```"
    trial = tmp_path / "trial.json"
    trial.write_text(json.dumps({"results": [{"task": "faq_multi", "model": "fixture",
                                              "status": "generated", "a": answer, "b": answer}]}))
    result = evaluate(trial)["results"][0]
    assert result["a"]["typecheck"]
    assert result["a"]["behavior"] == ("failed" if exclusive else "passed")

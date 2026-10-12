"""The evaluator must extract files safely and exercise held-out behavior."""

import json

import pytest

from benchmarks.coding_ai_quality.evaluate_trial import evaluate, extract_files


def test_extracts_an_unlabeled_single_file() -> None:
    answer = "Example:\n```tsx\nexport default function Counter() { return <div>0</div>; }\n```"
    assert list(extract_files(answer, "Counter.tsx")) == ["Counter.tsx"]


def test_extracts_named_files_without_using_structure_prose() -> None:
    answer = """### 파일 구조
- `CounterStyles.ts`: 설명
### `Counter.tsx` 코드
```tsx
import './CounterStyles.css';
export default function Counter() { return <div />; }
```
### `CounterStyles.css` 코드
```css
div { color: red; }
```"""
    assert set(extract_files(answer, "Counter.tsx")) == {"Counter.tsx", "CounterStyles.css"}


def test_ignores_filename_in_file_structure_list_before_heading() -> None:
    answer = """### 파일 구조
1. `Counter.tsx` - 컴포넌트
2. `styles.css` - 스타일

### Counter.tsx
```tsx
export default function Counter() { return <div />; }
```

### styles.css
```css
div { color: red; }
```"""
    assert set(extract_files(answer, "Counter.tsx")) == {"Counter.tsx", "styles.css"}


def test_extracts_dotted_style_module_filename() -> None:
    answer = """### `Counter.tsx`
```tsx
export default function Counter() { return <div />; }
```
### `Counter.styles.ts`
```ts
export const color = 'red';
```"""
    assert set(extract_files(answer, "Counter.tsx")) == {"Counter.tsx", "Counter.styles.ts"}


def test_rejects_missing_entry_and_duplicate_file() -> None:
    with pytest.raises(ValueError, match="Missing entry"):
        extract_files("### `Counter.css`\n```css\nbody {}\n```", "Counter.tsx")
    with pytest.raises(ValueError, match="Duplicate file"):
        extract_files("```tsx\nexport default 1;\n```\n```tsx\nexport default 2;\n```", "Counter.tsx")


def test_rejects_filename_language_mismatch() -> None:
    with pytest.raises(ValueError, match="Filename/extension mismatch"):
        extract_files("### `Counter.css`\n```tsx\nexport default 1;\n```", "Counter.tsx")


def test_accepts_an_unambiguous_renamed_component_entry() -> None:
    answer = "### `DeleteConfirmation.tsx`\n```tsx\nexport default function DeleteConfirmation() { return <div />; }\n```"
    assert set(extract_files(answer, "ConfirmDialog.tsx")) == {"DeleteConfirmation.tsx"}


def test_accepts_an_unambiguous_named_component_entry() -> None:
    answer = "### `PasswordInput.tsx`\n```tsx\nexport function PasswordInput() { return <input />; }\n```"
    assert set(extract_files(answer, "PasswordVisibility.tsx")) == {"PasswordInput.tsx"}


def test_accepts_ts_file_in_tsx_fence_when_model_uses_generic_label() -> None:
    answer = ("### `DeleteConfirmation.tsx`\n```tsx\n"
              "export default function DeleteConfirmation() { return <div />; }\n```\n"
              "### `useDeleteConfirmation.ts`\n```tsx\nexport const enabled = true;\n```")
    assert set(extract_files(answer, "ConfirmDialog.tsx")) == {
        "DeleteConfirmation.tsx", "useDeleteConfirmation.ts"
    }


def test_rejects_ambiguous_renamed_component_entries() -> None:
    answer = ("### `First.tsx`\n```tsx\nexport default function First() { return <div />; }\n```\n"
              "### `Second.tsx`\n```tsx\nexport default function Second() { return <div />; }\n```")
    with pytest.raises(ValueError, match="Missing entry"):
        extract_files(answer, "ConfirmDialog.tsx")


@pytest.mark.parametrize("task,source", [
    ("confirm_dialog", """import { useState } from 'react';
export default function ConfirmDialog() {
  const [open, setOpen] = useState(false);
  const [deleted, setDeleted] = useState(false);
  return <div>
    <button onClick={() => setOpen(true)}>삭제하기</button>
    {open && <section><p>정말 삭제할까요?</p>
      <button onClick={() => setOpen(false)}>취소</button>
      <button onClick={() => { setOpen(false); setDeleted(true); }}>삭제 확인</button>
    </section>}
    {deleted && <p>삭제되었습니다</p>}
  </div>;
}"""),
    ("text_preview", """import { useState } from 'react';
export default function TextPreview() {
  const [value, setValue] = useState('');
  return <div>
    <textarea value={value} onChange={(event) => setValue(event.target.value)} />
    <p>{value ? value.slice(0, 20) + (value.length > 20 ? '…' : '') : '미리보기 없음'}</p>
  </div>;
}"""),
    ("password_visibility", """import { useState } from 'react';
export default function PasswordVisibility() {
  const [value, setValue] = useState('');
  const [visible, setVisible] = useState(false);
  return <div>
    <input type={visible ? 'text' : 'password'} value={value}
      onChange={(event) => setValue(event.target.value)} />
    <button onClick={() => setVisible(!visible)}>
      {visible ? '비밀번호 숨기기' : '비밀번호 보기'}
    </button>
  </div>;
}"""),
    ("faq_toggle", """import { useState } from 'react';
export default function FaqToggle() {
  const [open, setOpen] = useState(false);
  return <section>
    <p>배송은 얼마나 걸리나요?</p>
    <button aria-expanded={open} onClick={() => setOpen(!open)}>
      {open ? '답변 닫기' : '답변 보기'}
    </button>
    {open && <p>배송은 2~3일 걸립니다.</p>}
  </section>;
}"""),
])
def test_holdout_runtime_checks_accept_known_correct_examples(tmp_path, task, source) -> None:
    answer = f"```tsx\n{source}\n```"
    trial = tmp_path / "trial.json"
    trial.write_text(json.dumps({"results": [{"task": task, "model": "test-fixture",
                                              "status": "generated", "a": answer, "b": answer}]}),
                     encoding="utf-8")

    result = evaluate(trial)["results"][0]

    assert result["a"]["typecheck"] and result["b"]["typecheck"]
    assert result["a"]["behavior"] == result["b"]["behavior"] == "passed", (
        result["a"]["checks"], result["a"].get("runtime_output"), result["b"]["checks"]
    )
    assert result["equivalent"] == "passed_on_covered_scenarios"


def test_faq_runtime_checks_reject_an_answer_visible_before_click(tmp_path) -> None:
    answer = """```tsx
export default function FaqToggle() {
  return <section>
    <p>배송은 얼마나 걸리나요?</p>
    <button aria-expanded={false}>답변 보기</button>
    <p>배송은 2~3일 걸립니다.</p>
  </section>;
}
```"""
    trial = tmp_path / "trial.json"
    trial.write_text(json.dumps({"results": [{"task": "faq_toggle", "model": "test-fixture",
                                              "status": "generated", "a": answer, "b": answer}]}),
                     encoding="utf-8")

    result = evaluate(trial)["results"][0]

    assert result["a"]["typecheck"] and result["b"]["typecheck"]
    assert result["a"]["behavior"] == result["b"]["behavior"] == "error"
    assert "Missing button: 답변 닫기" in result["a"]["runtime_output"]
    assert result["equivalent"] != "passed_on_covered_scenarios"

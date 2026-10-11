"""The stage-4 evaluator must not mistake prose for compilable files."""

import pytest

from benchmarks.coding_ai_quality.evaluate_trial import extract_files


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


def test_rejects_missing_entry_and_duplicate_file() -> None:
    with pytest.raises(ValueError, match="Missing entry"):
        extract_files("### `Counter.css`\n```css\nbody {}\n```", "Counter.tsx")
    with pytest.raises(ValueError, match="Duplicate file"):
        extract_files("```tsx\nexport default 1;\n```\n```tsx\nexport default 2;\n```", "Counter.tsx")


def test_rejects_filename_language_mismatch() -> None:
    with pytest.raises(ValueError, match="Filename/extension mismatch"):
        extract_files("### `Counter.css`\n```tsx\nexport default 1;\n```", "Counter.tsx")

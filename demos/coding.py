"""TypeScript/React 코딩 도메인의 결정적 A/B 예시 생성기."""

from __future__ import annotations

import re


def _request_note(source_text: str) -> str:
    note = re.sub(r"\s+", " ", source_text.strip()).replace("*/", "")
    return note[:100] or "선호 횟수를 보여주는 버튼을 만들어 주세요."


def _style_block(themed: bool) -> str:
    if themed:
        return """
const theme = {
  colors: { primary: "#2563eb", text: "#ffffff" },
  spacing: { medium: "12px", large: "16px" },
};

const buttonStyle = {
  backgroundColor: theme.colors.primary,
  color: theme.colors.text,
  padding: `${theme.spacing.medium} ${theme.spacing.large}`,
  border: "none",
};
"""
    return """
const buttonStyle = {
  backgroundColor: "#2563eb",
  color: "#ffffff",
  padding: "12px 16px",
  border: "none",
};
"""


def _type_block(explicit: bool) -> str:
    if not explicit:
        return ""
    return """
type ButtonStatus = "idle" | "selected";

interface PreferenceButtonProps {
  label: string;
}

interface ButtonState {
  count: number;
  status: ButtonStatus;
}
"""


def _compact_example(source_text: str, themed: bool, explicit: bool) -> str:
    if explicit:
        component = """
const initialState: ButtonState = { count: 0, status: "idle" };

export function PreferenceButton(props: PreferenceButtonProps): JSX.Element {
  const [state, setState] = useState<ButtonState>(initialState);

  const handleClick = (): void => {
    setState((previous: ButtonState): ButtonState => ({
      count: previous.count + 1,
      status: "selected",
    }));
  };

  return (
    <button style={buttonStyle} onClick={handleClick}>
      {props.label}: {state.count}번 선택
    </button>
  );
}
"""
    else:
        component = """
export function PreferenceButton() {
  const [count, setCount] = useState(0);

  return (
    <button style={buttonStyle} onClick={() => setCount(count + 1)}>
      {count === 0 ? "선호 선택" : `${count}번 선택`}
    </button>
  );
}
"""

    return f"""요청 예시: {_request_note(source_text)}

`PreferenceButton.tsx`
```tsx
import {{ useState }} from "react";
{_type_block(explicit)}{_style_block(themed)}{component}```
"""


def _separated_example(source_text: str, themed: bool, explicit: bool) -> str:
    if themed:
        style_file = """`designTokens.ts`
```ts
export const theme = {
  colors: { primary: "#2563eb", text: "#ffffff" },
  spacing: { medium: "12px", large: "16px" },
};
```
"""
        style_import = 'import { theme } from "./designTokens";'
        style_code = """
const buttonStyle = {
  backgroundColor: theme.colors.primary,
  color: theme.colors.text,
  padding: `${theme.spacing.medium} ${theme.spacing.large}`,
  border: "none",
};
"""
        style_attribute = " style={buttonStyle}"
    else:
        style_file = """`PreferenceButton.module.css`
```css
.button {
  padding: 12px 16px;
  color: #ffffff;
  background: #2563eb;
  border: 0;
}
```
"""
        style_import = 'import styles from "./PreferenceButton.module.css";'
        style_code = ""
        style_attribute = " className={styles.button}"

    if explicit:
        hook_file = """`usePreferenceCount.ts`
```ts
import { useState } from "react";

export interface PreferenceCount {
  count: number;
  increment: () => void;
}

export function usePreferenceCount(initialCount: number): PreferenceCount {
  const [count, setCount] = useState<number>(initialCount);
  const increment = (): void => setCount((current: number): number => current + 1);
  return { count, increment };
}
```
"""
        component_file = f"""`PreferenceButton.tsx`
```tsx
import {{ usePreferenceCount, type PreferenceCount }} from "./usePreferenceCount";
{style_import}

interface PreferenceButtonProps {{
  label: string;
  initialCount: number;
}}
{style_code}
export function PreferenceButton(props: PreferenceButtonProps): JSX.Element {{
  const preference: PreferenceCount = usePreferenceCount(props.initialCount);
  return <button{style_attribute} onClick={{preference.increment}}>{{props.label}}: {{preference.count}}</button>;
}}
```
"""
    else:
        hook_file = """`usePreferenceCount.ts`
```ts
import { useState } from "react";

export function usePreferenceCount(initialCount = 0) {
  const [count, setCount] = useState(initialCount);
  const increment = () => setCount((current) => current + 1);
  return { count, increment };
}
```
"""
        component_file = f"""`PreferenceButton.tsx`
```tsx
import {{ usePreferenceCount }} from "./usePreferenceCount";
{style_import}
{style_code}
export function PreferenceButton() {{
  const preference = usePreferenceCount();
  return <button{style_attribute} onClick={{preference.increment}}>{{preference.count}}번 선택</button>;
}}
```
"""

    return f"요청 예시: {_request_note(source_text)}\n\n{style_file}\n{hook_file}\n{component_file}"


def generate_demo(source_text: str, combo: dict[str, str]) -> str:
    themed = combo.get("style_management", "direct") == "theme"
    explicit = combo.get("type_detail", "inferred") == "explicit"
    if combo.get("code_structure", "compact") == "separated":
        return _separated_example(source_text, themed, explicit)
    return _compact_example(source_text, themed, explicit)

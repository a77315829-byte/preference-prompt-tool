"""TypeScript/React 코딩 도메인의 결정적 A/B 예시 생성기."""

from __future__ import annotations

import re


def _request_note(source_text: str) -> str:
    note = re.sub(r"\s+", " ", source_text.strip()).replace("*/", "")
    return note[:100] or "선호 횟수를 보여주는 버튼을 만들어 주세요."


def _scenario(source_text: str) -> str:
    request = source_text.lower()
    if re.search(r"상품|제품|product", request) and re.search(r"검색|필터|search|filter", request):
        return "filter"
    if re.search(r"확인|confirm", request) and re.search(r"모달|대화상자|dialog|modal", request):
        return "modal"
    if re.search(r"프로필|profile", request) and re.search(r"api|가져오|불러오|조회|fetch", request):
        return "profile"
    if re.search(r"클릭 횟수|카운터|counter|click count", request):
        return "counter"
    return "unsupported"


def demo_scenario(source_text: str) -> str | None:
    """데모가 실제 기능으로 구현할 수 있는 요청만 공개한다."""
    scenario = _scenario(source_text)
    return None if scenario == "unsupported" else scenario


def _task_example(source_text: str, themed: bool, explicit: bool, separated: bool) -> str:
    """대표 기능 요청은 실제로 동작하는 예시로, 동일한 스타일 축을 비교한다."""
    scenario = _scenario(source_text)
    if scenario == "unsupported":
        return ""

    if scenario == "filter":
        name = "ProductSearch"
        hook_name = "useProductSearch"
        state = """  const [query, setQuery] = useState("");
  const products = ["노트북", "키보드", "마우스"];
  const filtered = products.filter((product) => product.toLowerCase().includes(query.toLowerCase()));
"""
        view = """    <section style={panelStyle}>
      <input aria-label="상품 검색" value={query} onChange={(event) => setQuery(event.target.value)} />
      <ul>{filtered.map((product) => <li key={product}>{product}</li>)}</ul>
    </section>"""
        hook_return = "{ query, setQuery, filtered }"
    elif scenario == "modal":
        name = "ConfirmDialog"
        hook_name = "useConfirmDialog"
        state = """  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
"""
        view = """    <section style={panelStyle}>
      <button onClick={() => setOpen(true)}>확인 창 열기</button>
      {open && <div role="dialog" aria-modal="true" aria-label="확인 창">
        <h2>진행하시겠어요?</h2><p>선택한 작업을 계속합니다.</p>
        <button onClick={close}>취소</button><button onClick={close}>확인</button>
      </div>}
    </section>"""
        hook_return = "{ open, setOpen, close }"
    elif scenario == "profile":
        name = "ProfileCard"
        hook_name = "useProfile"
        state = """  const [profile, setProfile] = useState<{ name: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/profile", { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error("프로필을 불러오지 못했습니다."); return response.json(); })
      .then((data) => setProfile(data))
      .catch((reason) => { if (!controller.signal.aborted) setError(String(reason)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);
"""
        view = """    <section style={panelStyle}>
      {loading ? <p>불러오는 중...</p> : error ? <p role="alert">{error}</p> : <p>{profile?.name}</p>}
    </section>"""
        hook_return = "{ profile, loading, error }"
    else:
        name = "PreferenceButton"
        hook_name = "usePreferenceCount"
        state = """  const [count, setCount] = useState(0);
  const increment = () => setCount((current) => current + 1);
"""
        view = """    <button style={panelStyle} onClick={increment}>
      {count}번 선택
    </button>"""
        hook_return = "{ count, increment }"

    if explicit and scenario == "filter":
        state = state.replace('useState("")', 'useState<string>("")')
        state = state.replace('const products =', 'const products: string[] =')
        state = state.replace('const filtered =', 'const filtered: string[] =')
    if explicit and scenario == "modal":
        state = state.replace('useState(false)', 'useState<boolean>(false)')
        state = state.replace('const close = () =>', 'const close = (): void =>')
        state += '  const show = (): void => setOpen(true);\n'
        view = view.replace('onClick={() => setOpen(true)}', 'onClick={show}')
        hook_return = "{ open, close, show }"
    if explicit and scenario == "counter":
        state = state.replace("useState(0)", "useState<number>(0)")
        state = state.replace("const increment = () =>", "const increment = (): void =>")
        state = state.replace('const [count, setCount]', 'const initialCount: number = 0;\n  const [count, setCount]')
        state = state.replace('useState<number>(0)', 'useState<number>(initialCount)')
    if explicit and scenario == "profile":
        state = state.replace('useState(true)', 'useState<boolean>(true)')
        state = state.replace('useState("")', 'useState<string>("")')

    style = (
        'const theme = { colors: { surface: "#eef3ff" }, spacing: { medium: "16px" } };\n'
        'const panelStyle = { backgroundColor: theme.colors.surface, padding: theme.spacing.medium };'
        if themed else
        'const panelStyle = { backgroundColor: "#eef3ff", padding: "16px" };'
    )
    if explicit and not separated:
        style = style.replace('const panelStyle =', 'const panelStyle: CSSProperties =')
    annotation = ""
    props = ""
    return_type = ": ReactElement" if explicit else ""
    if scenario == "profile":
        imports = 'import { useEffect, useState' + (', type ReactElement, type CSSProperties' if explicit and not separated else '') + ' } from "react";'
    else:
        imports = 'import { useState' + (', type ReactElement, type CSSProperties' if explicit and not separated else '') + ' } from "react";'

    if not separated:
        return f"""요청 예시: {_request_note(source_text)}

`{name}.tsx`
```tsx
{imports}
{annotation}{style}
export function {name}({props}){return_type} {{
{state}  return (
{view}
  );
}}
```
"""

    if themed:
        style_file = f"""`designTokens.ts`
```ts
export const theme = {{ colors: {{ surface: "#eef3ff" }}, spacing: {{ medium: "16px" }} }};
```
"""
        style_import = 'import { theme } from "./designTokens";'
        panel = 'const panelStyle = { backgroundColor: theme.colors.surface, padding: theme.spacing.medium };'
    else:
        style_file = f"""`{name}.module.css`
```css
.panel {{ background: #eef3ff; padding: 16px; }}
```
"""
        style_import = f'import styles from "./{name}.module.css";'
        panel = ''
        view = view.replace('style={panelStyle}', 'className={styles.panel}')

    if scenario == "profile":
        hook_annotation = (
            "interface Profile { name: string; }\n"
            "interface ProfileState { profile: Profile | null; loading: boolean; error: string; }\n"
            if explicit else ""
        )
        state = state.replace("useState<{ name: string } | null>(null)", "useState<Profile | null>(null)" if explicit else "useState<{ name: string } | null>(null)")
        hook_result = ": ProfileState" if explicit else ""
    elif scenario == "modal":
        hook_annotation = (
            f"interface {name}State {{ open: boolean; close: () => void; show: () => void; }}\n"
            if explicit else ""
        )
        hook_result = f": {name}State" if explicit else ""
    elif scenario == "filter":
        hook_annotation = (
            f"interface {name}State {{ query: string; setQuery: (value: string) => void; filtered: string[]; }}\n"
            if explicit else ""
        )
        hook_result = f": {name}State" if explicit else ""
    else:
        hook_annotation = (
            "interface PreferenceCountState { count: number; increment: () => void; }\n"
            if explicit else ""
        )
        hook_result = ": PreferenceCountState" if explicit else ""
    hook_file = f"""`{hook_name}.ts`
```ts
{imports}
{hook_annotation}export function {hook_name}(){hook_result} {{
{state}  return {hook_return};
}}
```
"""
    state_names = hook_return.strip("{} ")
    component = f"""`{name}.tsx`
```tsx
import {{ {hook_name} }} from "./{hook_name}";
{'import type { ReactElement } from "react";' if explicit else ''}
{style_import}
{annotation}{panel if themed else ''}
export function {name}({props}){return_type} {{
  const {{ {state_names} }} = {hook_name}();
  return (
{view}
  );
}}
```
"""
    return f"요청 예시: {_request_note(source_text)}\n\n{style_file}\n{hook_file}\n{component}"


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

export function PreferenceButton(props: PreferenceButtonProps): ReactElement {
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
import {{ useState{', type ReactElement' if explicit else ''} }} from "react";
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
import type {{ ReactElement }} from "react";
{style_import}

interface PreferenceButtonProps {{
  label: string;
  initialCount: number;
}}
{style_code}
export function PreferenceButton(props: PreferenceButtonProps): ReactElement {{
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
    separated = combo.get("code_structure", "compact") == "separated"
    task_example = _task_example(source_text, themed, explicit, separated)
    if task_example:
        return task_example
    note = (
        "데모 안내: 이 요청은 준비된 기능 예시에 없어 버튼 예시로 코딩 스타일만 비교합니다. "
        "요청 기능에 맞춘 새 코드는 실제 API 모드에서 생성할 수 있습니다.\n\n"
    )
    return note + _task_example("클릭 횟수를 보여주는 버튼 컴포넌트", themed, explicit, separated)

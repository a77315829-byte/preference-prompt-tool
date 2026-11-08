"""v6(3차 사전등록 holdout) 실행 시나리오의 타당성: 요청대로 쓴 정답은 통과하고, 한 군데만 틀린 변형은
실패해야 한다. 역할별로 나눈 답(App.tsx 껍데기 포함)도 정답이면 통과해야 한다.
프론트 의존성(tsc, esbuild, jsdom)이 없으면 건너뛴다."""

import tempfile
from pathlib import Path

import pytest

from benchmarks.coding_ai_quality.evaluate_trial import FRONTEND, evaluate_candidate

pytestmark = pytest.mark.skipif(not (Path(FRONTEND) / "node_modules" / ".bin" / "tsc").exists(),
                                reason="frontend node_modules not installed")

REF = {
    "notify_switch": ("NotifySwitch.tsx", """import { useState } from 'react';
export default function NotifySwitch() {
  const [on, setOn] = useState(false);
  return (<div><button type="button" role="switch" aria-checked={on} onClick={() => setOn(!on)}>알림</button>
  <p>{on ? '알림 켜짐' : '알림 꺼짐'}</p></div>);
}"""),
    "step_counter": ("StepCounter.tsx", """import { useState } from 'react';
export default function StepCounter() {
  const [value, setValue] = useState(0);
  return (<div><p>값 {value}</p><button type="button" onClick={() => setValue(value + 5)}>5 더하기</button>
  <button type="button" onClick={() => setValue(0)}>초기화</button></div>);
}"""),
    "todo_add": ("TodoAdd.tsx", """import { useState } from 'react';
export default function TodoAdd() {
  const [text, setText] = useState('');
  const [items, setItems] = useState<string[]>([]);
  const add = () => { const v = text.trim(); if (!v) return; setItems([...items, v]); setText(''); };
  return (<div><label htmlFor="todo">할 일</label><input id="todo" value={text} onChange={(e) => setText(e.target.value)} />
  <button type="button" onClick={add}>추가</button><ul>{items.map((item, i) => <li key={i}>{item}</li>)}</ul>
  <p>할 일 {items.length}개</p></div>);
}"""),
    "color_choice": ("ColorChoice.tsx", """import { useState } from 'react';
const COLORS = ['빨강', '초록', '파랑'];
export default function ColorChoice() {
  const [picked, setPicked] = useState<string | null>(null);
  return (<div>{COLORS.map((c) => (<button key={c} type="button" aria-pressed={picked === c} onClick={() => setPicked(c)}>{c}</button>))}
  <p>선택한 색: {picked ?? '없음'}</p></div>);
}"""),
    "word_count": ("WordCount.tsx", """import { useState } from 'react';
export default function WordCount() {
  const [text, setText] = useState('');
  const count = text.split(/\\s+/).filter(Boolean).length;
  return (<div><label htmlFor="t">내용</label><textarea id="t" value={text} onChange={(e) => setText(e.target.value)} />
  <p>단어 {count}개</p></div>);
}"""),
}
MUT = {
    "notify_switch": ("aria-checked={on}", "aria-checked={false}"),
    "step_counter": ("setValue(value + 5)", "setValue(value + 1)"),
    "todo_add": ("const v = text.trim(); if (!v) return;", "const v = text;"),
    "color_choice": ("aria-pressed={picked === c}", "aria-pressed={picked !== null}"),
    "word_count": ("text.split(/\\s+/).filter(Boolean).length", "text.split(' ').length"),
}


def _behavior(task, files):
    answer = "".join(f"### `{name}`\n```tsx\n{code}\n```\n" for name, code in files)
    with tempfile.TemporaryDirectory(prefix=".v6-scenario-", dir=FRONTEND) as folder:
        return evaluate_candidate(task, answer, "test", Path(folder))


@pytest.mark.parametrize("task", list(REF))
def test_reference_passes_and_single_mutation_fails(task) -> None:
    name, code = REF[task]
    assert _behavior(task, [(name, code)])["behavior"] == "passed"
    mutant = code.replace(*MUT[task])
    assert mutant != code
    assert _behavior(task, [(name, mutant)])["behavior"] != "passed"


@pytest.mark.parametrize("task", list(REF))
def test_split_answer_with_a_host_app_file_is_measured(task) -> None:
    name, code = REF[task]
    component = Path(name).stem
    renamed = f"{component}View.tsx"
    app = (f"import {component} from './{component}View';\n"
           f"export default function App() {{ return <{component} />; }}")
    assert _behavior(task, [(renamed, code), ("App.tsx", app)])["behavior"] == "passed"

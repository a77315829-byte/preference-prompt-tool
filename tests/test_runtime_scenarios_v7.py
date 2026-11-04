"""v7(4차 사전등록 후보 과제) 실행 시나리오의 타당성: 정답은 통과, 한 군데만 틀린 변형은 실패,
역할별로 나눈 답(App.tsx 껍데기 포함)도 정답이면 통과. 프론트 의존성이 없으면 건너뛴다."""

import tempfile
from pathlib import Path

import pytest

from benchmarks.coding_ai_quality.evaluate_trial import FRONTEND, evaluate_candidate

pytestmark = pytest.mark.skipif(not (Path(FRONTEND) / "node_modules" / ".bin" / "tsc").exists(),
                                reason="frontend node_modules not installed")

REF = {
    "page_list": ("PageList.tsx", """import { useState } from 'react';
const ITEMS = Array.from({ length: 7 }, (_, i) => `항목 ${i + 1}`);
export default function PageList() {
  const [page, setPage] = useState(1);
  const last = Math.ceil(ITEMS.length / 3);
  return (<div><ul>{ITEMS.slice((page - 1) * 3, page * 3).map((item) => <li key={item}>{item}</li>)}</ul>
  <p>{page} / {last}쪽</p>
  <button type="button" disabled={page === 1} onClick={() => setPage(page - 1)}>이전</button>
  <button type="button" disabled={page === last} onClick={() => setPage(page + 1)}>다음</button></div>);
}"""),
    "tip_calc": ("TipCalc.tsx", """import { useState } from 'react';
const RATES = [10, 15, 20];
export default function TipCalc() {
  const [amount, setAmount] = useState('10000');
  const [rate, setRate] = useState(10);
  const value = amount.trim() === '' ? NaN : Number(amount);
  const tip = Math.round(value * rate / 100);
  return (<div><label htmlFor="amount">금액</label>
  <input id="amount" type="number" value={amount} onChange={(e) => setAmount(e.target.value)} />
  {RATES.map((r) => <button key={r} type="button" aria-pressed={rate === r} onClick={() => setRate(r)}>{r}%</button>)}
  {Number.isFinite(value) ? (<><p>팁 {tip.toLocaleString('ko-KR')}원</p><p>합계 {(value + tip).toLocaleString('ko-KR')}원</p></>)
    : <p>금액을 입력하세요</p>}</div>);
}"""),
    "tag_input": ("TagInput.tsx", """import { useState } from 'react';
export default function TagInput() {
  const [text, setText] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  const full = tags.length >= 3;
  const add = () => { const v = text.trim(); if (v && !tags.includes(v) && !full) setTags([...tags, v]); setText(''); };
  return (<div><label htmlFor="tag">태그</label><input id="tag" value={text} onChange={(e) => setText(e.target.value)} />
  <button type="button" disabled={full} onClick={add}>추가</button>
  <ul>{tags.map((t) => <li key={t}>{t}<button type="button" aria-label={`${t} 삭제`} onClick={() => setTags(tags.filter((x) => x !== t))}>×</button></li>)}</ul>
  {full && <p>태그는 3개까지입니다</p>}</div>);
}"""),
    "step_wizard": ("StepWizard.tsx", """import { useState } from 'react';
const STEPS = ['1단계: 약관', '2단계: 정보 입력', '3단계: 확인'];
export default function StepWizard() {
  const [step, setStep] = useState(0);
  const [done, setDone] = useState(false);
  if (done) return <p>가입 완료</p>;
  return (<div><h2>{STEPS[step]}</h2>
  <button type="button" disabled={step === 0} onClick={() => setStep(step - 1)}>이전</button>
  {step < 2 ? <button type="button" onClick={() => setStep(step + 1)}>다음</button>
    : <button type="button" onClick={() => setDone(true)}>가입하기</button>}</div>);
}"""),
    "category_filter": ("CategoryFilter.tsx", """import { useState } from 'react';
const ITEMS = [{ name: '사과', kind: '과일' }, { name: '바나나', kind: '과일' }, { name: '당근', kind: '채소' }, { name: '오이', kind: '채소' }];
export default function CategoryFilter() {
  const [on, setOn] = useState<Record<string, boolean>>({ 과일: true, 채소: true });
  const shown = ITEMS.filter((i) => on[i.kind]);
  return (<div>{['과일', '채소'].map((k) => (<label key={k}><input type="checkbox" checked={on[k]} onChange={() => setOn({ ...on, [k]: !on[k] })} />{k}</label>))}
  {shown.length ? <ul>{shown.map((i) => <li key={i.name}>{i.name}</li>)}</ul> : <p>표시할 항목이 없습니다</p>}
  <p>{shown.length}개 표시</p></div>);
}"""),
    "price_sort": ("PriceSort.tsx", """import { useState } from 'react';
const ITEMS = [{ name: '연필', price: 500 }, { name: '공책', price: 2000 }, { name: '지우개', price: 300 }];
const LABEL = ['정렬 없음', '낮은 가격순', '높은 가격순'];
export default function PriceSort() {
  const [mode, setMode] = useState(0);
  const list = mode === 0 ? ITEMS : [...ITEMS].sort((a, b) => mode === 1 ? a.price - b.price : b.price - a.price);
  return (<div><button type="button" onClick={() => setMode(mode === 1 ? 2 : 1)}>가격순 정렬</button><p>{LABEL[mode]}</p>
  <ul>{list.map((i) => <li key={i.name}>{i.name} {i.price.toLocaleString('ko-KR')}원</li>)}</ul></div>);
}"""),
    "single_accordion": ("SingleAccordion.tsx", """import { useState } from 'react';
const QA = [['배송', '2~3일 걸립니다.'], ['교환', '7일 안에 가능합니다.'], ['환불', '결제 수단으로 돌려드립니다.']];
export default function SingleAccordion() {
  const [open, setOpen] = useState<number | null>(null);
  return (<div>{QA.map(([q, a], i) => (<div key={q}><button type="button" aria-expanded={open === i} aria-controls={`a${i}`} onClick={() => setOpen(open === i ? null : i)}>{q}</button>
  <p id={`a${i}`} hidden={open !== i}>{a}</p></div>))}</div>);
}"""),
    "bounded_counter": ("BoundedCounter.tsx", """import { useState } from 'react';
export default function BoundedCounter() {
  const [n, setN] = useState(0);
  return (<div><button type="button" disabled={n === 0} onClick={() => setN(n - 1)}>빼기</button>
  <button type="button" disabled={n === 5} onClick={() => setN(n + 1)}>더하기</button>
  <p>수량 {n}</p>{n === 5 && <p>최대 수량입니다</p>}</div>);
}"""),
}
MUT = {
    "page_list": ("disabled={page === last}", "disabled={false}"),
    "tip_calc": ("Math.round(value * rate / 100)", "Math.round(value * 10 / 100)"),
    "tag_input": ("v && !tags.includes(v) && !full", "v && !full"),
    "step_wizard": ("disabled={step === 0}", "disabled={false}"),
    "category_filter": ("<p>표시할 항목이 없습니다</p>", "<p>없음</p>"),
    "price_sort": ("setMode(mode === 1 ? 2 : 1)", "setMode(1)"),
    "single_accordion": ("setOpen(open === i ? null : i)", "setOpen(i)"),
    "bounded_counter": ("disabled={n === 5}", "disabled={n === 6}"),
}


def _behavior(task, files):
    answer = "".join(f"### `{name}`\n```tsx\n{code}\n```\n" for name, code in files)
    with tempfile.TemporaryDirectory(prefix=".v7-scenario-", dir=FRONTEND) as folder:
        return evaluate_candidate(task, answer, "test", Path(folder))


@pytest.mark.parametrize("task", list(REF))
def test_reference_passes_and_single_mutation_fails(task) -> None:
    name, code = REF[task]
    result = _behavior(task, [(name, code)])
    assert result["behavior"] == "passed", (result["checks"], result.get("runtime_output"), result["typecheck_output"])
    mutant = code.replace(*MUT[task])
    assert mutant != code
    assert _behavior(task, [(name, mutant)])["behavior"] != "passed"


@pytest.mark.parametrize("task", list(REF))
def test_split_answer_with_a_host_app_file_is_measured(task) -> None:
    name, code = REF[task]
    component = Path(name).stem
    app = (f"import {component} from './{component}View';\n"
           f"export default function App() {{ return <{component} />; }}")
    assert _behavior(task, [(f"{component}View.tsx", code), ("App.tsx", app)])["behavior"] == "passed"

"""v5(2차 사전등록 holdout) 실행 시나리오의 타당성: 요청대로 쓴 정답은 통과하고, 한 군데만 틀린 변형은
실패해야 한다. 시나리오가 너무 느슨하거나 엄하면 기능 통과율이 아무것도 재지 않는다.
프론트 의존성(tsc, esbuild, jsdom)이 없으면 건너뛴다."""

import tempfile
from pathlib import Path

import pytest

from benchmarks.coding_ai_quality.evaluate_trial import FRONTEND, evaluate_candidate

pytestmark = pytest.mark.skipif(not (Path(FRONTEND) / "node_modules" / ".bin" / "tsc").exists(),
                                reason="frontend node_modules not installed")


def _wrap(name, code):
    return f"`{name}`\n```tsx\n{code}\n```\n"


REF = {
"tab_switch": ("TabSwitch.tsx", """import { useState } from 'react';
const TABS = [{ id: 'notice', label: '공지', body: '이번 주 점검은 없습니다.' }, { id: 'event', label: '이벤트', body: '신규 가입 시 쿠폰을 드립니다.' }];
export default function TabSwitch() {
  const [active, setActive] = useState('notice');
  return (<div><div role="tablist">{TABS.map((t) => (<button key={t.id} role="tab" id={`tab-${t.id}`} aria-controls={`panel-${t.id}`} aria-selected={active === t.id} onClick={() => setActive(t.id)}>{t.label}</button>))}</div>
  {TABS.map((t) => (<div key={t.id} role="tabpanel" id={`panel-${t.id}`} aria-labelledby={`tab-${t.id}`} hidden={active !== t.id}><p>{t.body}</p></div>))}</div>);
}"""),
"char_counter": ("CharCounter.tsx", """import { useState } from 'react';
export default function CharCounter() {
  const [text, setText] = useState('');
  const over = text.length > 20;
  return (<form onSubmit={(e) => e.preventDefault()}><label htmlFor="memo">메모</label><textarea id="memo" value={text} onChange={(e) => setText(e.target.value)} />
  <p>{text.length}/20자</p>{over && <p role="alert">20자를 넘었습니다</p>}<button type="submit" disabled={over}>제출</button></form>);
}"""),
"star_rating": ("StarRating.tsx", """import { useState } from 'react';
export default function StarRating() {
  const [rating, setRating] = useState(0);
  return (<div><div>{[1, 2, 3, 4, 5].map((n) => (<button key={n} type="button" aria-label={`별 ${n}개`} aria-pressed={n <= rating} onClick={() => setRating(n)}>{n <= rating ? '★' : '☆'}</button>))}</div><p>평점 {rating}점</p></div>);
}"""),
"like_toggle": ("LikeToggle.tsx", """import { useState } from 'react';
export default function LikeToggle() {
  const [liked, setLiked] = useState(false);
  return (<div><p>좋아요 {liked ? 11 : 10}</p><button type="button" aria-pressed={liked} onClick={() => setLiked(!liked)}>{liked ? '좋아요 취소' : '좋아요'}</button></div>);
}"""),
"temperature_convert": ("TemperatureConvert.tsx", """import { useState } from 'react';
export default function TemperatureConvert() {
  const [value, setValue] = useState('0');
  const c = value.trim() === '' ? NaN : Number(value);
  const f = Math.round((c * 9 / 5 + 32) * 10) / 10;
  return (<div><label htmlFor="c">섭씨</label><input id="c" value={value} onChange={(e) => setValue(e.target.value)} />
  <p>{Number.isFinite(c) ? `화씨 ${f}°F` : '숫자를 입력하세요'}</p></div>);
}"""),
}
# 하나씩 틀리게 만든 변형: 시나리오가 그 차이를 잡아야 한다.
MUT = {
"tab_switch": ("hidden={active !== t.id}", "hidden={false}"),
"char_counter": ("disabled={over}", "disabled={false}"),
"star_rating": ("aria-pressed={n <= rating}", "aria-pressed={n === rating}"),
"like_toggle": ("{liked ? '좋아요 취소' : '좋아요'}", "{'좋아요'}"),
"temperature_convert": ("Math.round((c * 9 / 5 + 32) * 10) / 10", "Math.round(c * 9 / 5 + 32)"),
}


def _behavior(task, code):
    name = REF[task][0]
    with tempfile.TemporaryDirectory(prefix=".v5-scenario-", dir=FRONTEND) as folder:
        return evaluate_candidate(task, _wrap(name, code), "test", Path(folder))


@pytest.mark.parametrize("task", list(REF))
def test_reference_passes_and_single_mutation_fails(task) -> None:
    code = REF[task][1]
    assert _behavior(task, code)["behavior"] == "passed"
    mutant = code.replace(*MUT[task])
    assert mutant != code
    assert _behavior(task, mutant)["behavior"] != "passed"

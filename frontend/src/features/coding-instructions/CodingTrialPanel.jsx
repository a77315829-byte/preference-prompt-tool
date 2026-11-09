import { useEffect, useRef, useState } from 'react';
import { ARM_LABELS, codingWork, downloadText, formatSeconds, observedSeconds } from './workflowApi';

const OUTCOMES = { unverified: '미확인', pass: '기능 통과 확인', fail: '기능 실패 확인', blocked: '진행 불가' };

function TrialArm({ arm, trial, tick, busy, act }) {
  const saved = trial.arms[arm];
  const [result, setResult] = useState(saved);
  const [copied, setCopied] = useState('');
  const signature = JSON.stringify([saved.outcome, saved.evidence, saved.answer, saved.passed_tests, saved.total_tests]);
  useEffect(() => { setResult(saved); }, [signature]);
  const change = (key, value) => setResult(current => ({ ...current, [key]: value }));
  const timer = phase => act('timer', { operation: 'start', arm, phase });
  const fullPrompt = `${trial.prompts[arm]}\n\n## 이번 작업\n${trial.task}\n\n## 작업 맥락과 완료 조건\n${trial.context}`;
  const copy = async () => {
    try { await navigator.clipboard.writeText(fullPrompt); setCopied('복사했어요. 같은 도구·모델·설정의 새 대화에서 실행해 주세요.'); }
    catch { setCopied('복사하지 못했어요. 지침 전문을 펼쳐 직접 복사해 주세요.'); }
  };
  return <section className="coding-work-arm">
    <h4>{ARM_LABELS[arm]}</h4>
    <p>{trial.tool} · {trial.model}</p>
    <button type="button" className="coding-secondary-button" onClick={copy}>지침·작업 함께 복사</button>
    {copied && <p role="status">{copied}</p>}
    <details><summary>이번 비교에 고정한 지침 전문</summary><textarea readOnly rows={7} value={fullPrompt} /></details>
    <dl className="coding-work-times">
      {['setup', 'edit'].map(phase => <div key={phase}><dt>{phase === 'setup' ? '준비·요청·응답 대기' : '답변 수정·검사'}</dt>
        <dd>{saved.timed[phase] || (trial.active?.arm === arm && trial.active.phase === phase)
          ? formatSeconds(observedSeconds(trial, arm, phase, tick)) : '미측정'}</dd>
        <button type="button" className="coding-secondary-button" disabled={busy || Boolean(trial.active)} onClick={() => timer(phase)}>
          {phase === 'setup' ? '준비 시간 재기' : '수정·검사 시간 재기'}</button></div>)}
    </dl>
    <label>실제로 확인한 기능 결과<select value={result.outcome} onChange={e => change('outcome', e.target.value)}>
      {Object.entries(OUTCOMES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
    </select></label>
    <label>실행한 검사·결과 근거<textarea rows={3} maxLength={4000} value={result.evidence} onChange={e => change('evidence', e.target.value)}
      placeholder="예: 실행한 테스트 명령, 통과·실패 항목, 수동으로 확인한 완료 조건" /></label>
    <div className="coding-work-counts">
      <label>통과 테스트 수 (선택)<input type="number" min="0" max="100000" value={result.passed_tests ?? ''} onChange={e => change('passed_tests', e.target.value === '' ? null : Number(e.target.value))} /></label>
      <label>전체 테스트 수 (선택)<input type="number" min="1" max="100000" value={result.total_tests ?? ''} onChange={e => change('total_tests', e.target.value === '' ? null : Number(e.target.value))} /></label>
    </div>
    <details><summary>답변도 함께 보관하기 (선택)</summary><label>받은 답변<textarea rows={5} maxLength={20000} value={result.answer} onChange={e => change('answer', e.target.value)} /></label></details>
    <button type="button" className="coding-primary-button" disabled={busy || Boolean(trial.active)} onClick={() => act('result', {
      arm, outcome: result.outcome, evidence: result.evidence, answer: result.answer,
      passed_tests: result.passed_tests, total_tests: result.total_tests,
    })}>이 조건의 확인 결과 저장</button>
  </section>;
}

export default function CodingTrialPanel({ source, selected, user, task = '', onActiveChange }) {
  const [trials, setTrials] = useState([]);
  const [trial, setTrial] = useState(null);
  const [form, setForm] = useState({ title: '', task, model: '', tool: '', context: '' });
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);
  const [received, setReceived] = useState(0);
  const request = useRef(0);
  const adopt = next => { setTrial(next); setTick(0); setReceived(performance.now()); };
  const refresh = () => codingWork('trials').then(data => setTrials(data.trials));
  useEffect(() => { if (user) refresh().catch(e => setError(e.message)); }, [user?.id]);
  useEffect(() => () => { request.current += 1; }, []);
  useEffect(() => { onActiveChange?.(Boolean(trial?.active)); return () => onActiveChange?.(false); }, [trial?.active, onActiveChange]);
  useEffect(() => {
    if (!trial?.active) return undefined;
    const id = window.setInterval(() => setTick((performance.now() - received) / 1000), 1000);
    return () => window.clearInterval(id);
  }, [trial?.active, received]);
  useEffect(() => {
    if (!trial?.active) return undefined;
    const warn = event => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [trial?.active]);
  const perform = async work => {
    const token = ++request.current; setBusy(true); setError('');
    try { const next = await work(); if (token === request.current) { adopt(next); await refresh(); } }
    catch (e) { if (token === request.current) setError(e.message); }
    finally { if (token === request.current) setBusy(false); }
  };
  const create = e => { e.preventDefault(); perform(async () => {
    const next = (await codingWork('trials', { ...source, ...form, snapshot: selected.snapshot })).trial;
    setReason(''); return next;
  }); };
  const act = (action, values) => perform(async () => (await codingWork(`trials/${trial.id}/${action}`, { revision: trial.revision, ...values })).trial);
  const open = id => {
    if (trial && !window.confirm('화면에서 입력 중인 미저장 결과는 사라집니다. 다른 기록을 열까요?')) return;
    perform(async () => { const next = (await codingWork(`trials/${id}`)).trial; setReason(next.preference_reason); return next; });
  };
  if (!user) return <p>로그인하면 작업 비교를 내 계정에 보관하고 다시 이어갈 수 있어요.</p>;
  return <div className="coding-work-card">
    <h4>실제 작업에서 비교하기</h4>
    <p>같은 작업·도구·모델 설정으로 일반 지침과 선택한 지침을 사용하고, 시간·기능 결과·선호를 따로 기록합니다. 여기서는 AI를 호출하거나 코드를 실행하지 않습니다.</p>
    <p className="ws-help">일반 지침에는 개발 환경·공통 원칙·동일 팀 필수 규칙을 넣습니다. 비교 대상은 추가 선호나 개선 안내를 포함한 현재 지침 전체이므로, 차이가 나더라도 네 선호만의 효과로 해석하지 않습니다.</p>
    <p className="ws-help">팀 필수 규칙은 두 조건에 동일하게 포함됩니다. 타이머 시작 이후의 시간만 측정하며, 최초 선호 선택·팀 설정 시간은 포함하지 않습니다. 같은 작업 반복에는 학습 효과가 있으므로 권장 순서를 따르고 여러 작업에서 순서를 교차하세요.</p>
    <details><summary>TypeScript/React 버그 수정·기능 추가 비교 방법</summary>
      <ol><li>실제 이슈의 재현 절차·대상 파일·기준 커밋과 완료 조건을 적습니다.</li>
        <li>두 조건을 같은 커밋에서 각각 시작하고 도구·모델·설정·제공 파일을 맞춥니다. 별도 대화에서 실행하고 기존 개인/팀 지침 적용 여부도 동일하게 기록합니다.</li>
        <li>준비·응답 대기 후 타이머를 멈추고, 답변을 적용할 때 수정·검사 타이머를 켭니다.</li>
        <li>프로젝트의 타입 검사·관련 테스트·빌드와 화면 재현 결과를 기록합니다. 빌드 성공만으로 기능 전체 통과를 판단하지 않습니다.</li>
        <li>두 조건의 검사 결과를 저장한 뒤 사용하기 편했던 쪽을 별도로 고릅니다.</li></ol>
    </details>
    {!trial && <form onSubmit={create}>
      {[["title", "작업 이름", 100], ["tool", "사용할 도구", 100], ["model", "모델·추론 설정", 200]].map(([key, label, maximum]) => <label key={key}>{label}
        <input required maxLength={maximum} value={form[key]} onChange={e => setForm(current => ({ ...current, [key]: e.target.value }))} /></label>)}
      <label>두 조건에 사용할 실제 작업<textarea required rows={3} maxLength={10000} value={form.task} onChange={e => setForm(current => ({ ...current, task: e.target.value }))} placeholder="예: 이슈 번호와 재현 방법을 적고, 기존 화면의 오류를 수정하도록 요청하세요." /></label>
      <label>저장소·기준 커밋·완료 조건<textarea required rows={3} maxLength={3000} value={form.context} onChange={e => setForm(current => ({ ...current, context: e.target.value }))} placeholder="저장소/기준 커밋, 제공 파일, 기존 AI 지침 적용 여부, React·TypeScript 버전, 타입/테스트/빌드 명령, 화면 완료 조건을 적어 주세요." /></label>
      <p className="ws-help">시작하면 작업 요청·지침·맥락을 이 계정에 저장합니다. 팀원에게 자동 공유하지 않으며 API 키·비밀값은 입력하지 마세요.</p>
      <button type="submit" className="coding-primary-button" disabled={busy || !selected?.snapshot}>두 조건을 고정하고 비교 시작</button>
    </form>}
    {trial && <>
      <h4>{trial.title}</h4><p>권장 순서: {trial.order.map(arm => ARM_LABELS[arm]).join(' → ')} · 지침은 시작 당시 버전으로 고정</p>
      <details><summary>작업과 완료 조건</summary><pre>{trial.task}{'\n\n'}{trial.context}</pre></details>
      <p className="ws-help">타이머는 창을 닫아도 계속됩니다. 자리 비움·다른 작업으로 전환할 때 멈춰 주세요. 준비와 수정·검사를 모두 시작·멈춰야 총시간을 비교합니다.</p>
      {trial.active && <div className="coding-work-running" role="status">{ARM_LABELS[trial.active.arm]} · {trial.active.phase === 'setup' ? '준비' : '수정·검사'} 시간 측정 중
        <button type="button" className="coding-primary-button" disabled={busy} onClick={() => act('timer', { operation: 'pause' })}>멈추고 시간 저장</button></div>}
      <div className="coding-work-columns">{trial.order.map(arm => <TrialArm key={`${trial.id}-${arm}`} {...{ arm, trial, tick, busy, act }} />)}</div>
      <div className="coding-work-preview">
        <h4>각 지표를 따로 확인</h4>
        <p>일반 지침: {OUTCOMES[trial.arms.general.outcome]} / 선택한 지침: {OUTCOMES[trial.arms.selected.outcome]}</p>
        <p>기록된 총시간: 일반 {formatSeconds(trial.comparison.seconds.general)} / 선택한 지침 {formatSeconds(trial.comparison.seconds.selected)}</p>
        <p>수정·검사 시간: 일반 {formatSeconds(trial.comparison.edit_seconds?.general)} / 선택한 지침 {formatSeconds(trial.comparison.edit_seconds?.selected)}</p>
        {trial.comparison.timing_complete && <p>시간 차이: {formatSeconds(Math.abs(trial.comparison.seconds_saved))} {trial.comparison.seconds_saved > 0 ? '선택한 지침이 짧음' : trial.comparison.seconds_saved < 0 ? '일반 지침이 짧음' : '동일'}</p>}
        <p className="ws-help">{trial.comparison.accuracy_basis} 미확인·진행 불가를 실패나 통과로 바꾸어 집계하지 않습니다.</p>
        {!trial.comparison.both_passed && <p>두 조건의 기능 통과가 확인되기 전에는 시간이 짧다는 이유만으로 개선됐다고 판단하지 마세요.</p>}
        <label>선호 이유 (기능 결과와 별도)<textarea rows={2} maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} /></label>
        <div className="prompt-actions">{[['general', '일반이 더 편함'], ['selected', '선택한 지침이 더 편함'], ['tie', '비슷함'], ['unselected', '판단 보류']].map(([value, label]) =>
          <button type="button" key={value} className="coding-secondary-button" aria-pressed={trial.preference === value} disabled={busy} onClick={() => act('preference', { preference: value, reason })}>{label}</button>)}</div>
        <p>현재 선호: {trial.preference === 'unselected' ? '미확정' : trial.preference === 'tie' ? '비슷함' : ARM_LABELS[trial.preference]}</p>
      </div>
      <div className="prompt-actions">
        <button type="button" className="coding-secondary-button" disabled={busy} onClick={() => open(trial.id)}>서버 기록 새로 읽기</button>
        <button type="button" className="coding-secondary-button" onClick={() => downloadText(`coding-trial-${trial.id}.json`, JSON.stringify(trial, null, 2), 'application/json')}>현재 저장 기록 내려받기</button>
        <button type="button" className="coding-secondary-button" disabled={busy || Boolean(trial.active)} onClick={() => { if (window.confirm('미저장 입력을 닫고 새 비교를 준비할까요?')) adopt(null); }}>새 작업 비교</button>
        <button type="button" className="coding-text-button" disabled={busy || Boolean(trial.active)} onClick={() => { if (window.confirm('이 작업 비교 기록을 삭제할까요?')) act('delete', {}); }}>기록 삭제</button>
      </div>
    </>}
    {error && <p role="alert" className="ws-error">{error}</p>}
    <details open={!trial}><summary>내 작업 비교 기록 {trials.length}개</summary>
      <ul className="coding-work-history">{trials.map(row => <li key={row.id}><span>{row.title} · {row.active ? '타이머 진행 중' : row.comparison.both_checked ? '양쪽 기능 확인 기록 있음' : '확인 미완료'}</span>
        <button type="button" className="coding-secondary-button" disabled={busy || Boolean(trial?.active)} onClick={() => open(row.id)}>열기</button></li>)}</ul>
      <p className="ws-help">기록은 준비·수정 시간과 확인 근거를 수집하는 용도입니다. 한두 사례로 팀 생산성이나 개인화 효과를 확정하지 않습니다.</p>
    </details>
  </div>;
}

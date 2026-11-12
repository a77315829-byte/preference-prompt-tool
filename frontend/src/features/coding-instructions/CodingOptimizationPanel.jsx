import { useEffect, useRef, useState } from 'react';
import AuthSection from '../../shared/auth/AuthSection';
import CodingEvaluationBreakdown from './CodingEvaluationBreakdown';
import { HumanAnswerReview } from './CodingAnswerReview';
import { codingOptimizationKind } from './codingOptions';
import './fastApiOptimization.css';

const ROOT = '/api/coding-instructions/optimizations';
async function call(path = '', body) {
  const response = await fetch(`${ROOT}${path}`, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || '개선 작업을 확인하지 못했어요. 잠시 후 다시 시도해 주세요.');
  return data;
}

export default function CodingOptimizationPanel({ draft, user, signupOpen, onLogin, onOpenLibrary, onBusy, disabled }) {
  const kind = codingOptimizationKind(draft.profile);
  const frameworkLabel = kind === 'fastapi' ? 'FastAPI' : kind === 'spring_boot' ? 'Spring Boot' : `${draft.profile.language} · ${draft.profile.framework}`;
  const [availability, setAvailability] = useState(null);
  const [job, setJob] = useState(null);
  const [recent, setRecent] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [loginOpen, setLoginOpen] = useState(false);
  const [verdict, setVerdict] = useState('');
  const [title, setTitle] = useState(`${frameworkLabel} 내 작성 방식 · GEPA 후보`);
  const [saved, setSaved] = useState(null);
  const [example, setExample] = useState(0);
  const [copied, setCopied] = useState(false);
  const [humanReview, setHumanReview] = useState({});
  const active = useRef(true);
  const ownsBusy = useRef(false);
  const polling = useRef(null);
  const startedHere = useRef(false);
  const result = job?.result;
  const supported = Boolean(kind);

  const updateBusy = value => { ownsBusy.current = value; setBusy(value); onBusy?.(value); };
  useEffect(() => {
    active.current = true;
    if (supported) call().then(data => { if (active.current) setAvailability({ ...data, ...(data.environments?.[kind]
      || (kind === 'fastapi' ? data : { enabled: false, reason: `${frameworkLabel} GEPA를 지원하는 서버 설정을 확인해 주세요.` })) }); })
      .catch(() => { if (active.current) setAvailability({ enabled: false, reason: '서버의 GEPA 설정을 확인하지 못했어요. 프롬프트 복사와 저장은 계속 사용할 수 있어요.' }); });
    if (user) call('/recent').then(data => {
      if (!active.current) return;
      const jobs = (data.jobs || []).filter(item => JSON.stringify(item.profile) === JSON.stringify(draft.profile)
        || item.result?.original_prompt === draft.prompt);
      setRecent(jobs);
      if (jobs[0] && !startedHere.current) { updateBusy(jobs[0].status === 'running'); receive(jobs[0]); }
    }).catch(() => { /* A server without recovery support can still start jobs. */ });
    return () => { active.current = false; clearTimeout(polling.current); if (ownsBusy.current) onBusy?.(false); };
  }, [user?.id]);

  const receive = next => {
    if (!active.current) return;
    setJob(next);
    if (next.status === 'running') {
      polling.current = setTimeout(async () => {
        try { receive((await call(`/${next.id}`)).job); }
        catch (e) { if (active.current) { setError(e.message); updateBusy(false); } }
      }, 1200);
    } else {
      updateBusy(false);
      if (next.status === 'error') setError(next.error || '개선을 마치지 못했어요. 원본은 그대로 있어요.');
    }
  };
  const start = async () => {
    if (!user) { setLoginOpen(true); return; }
    if (!availability?.enabled || busy || disabled) return;
    startedHere.current = true;
    updateBusy(true); setError(''); setJob(null); setVerdict(''); setSaved(null); setCopied(false); setExample(0); setHumanReview({});
    try { receive((await call('', { profile: draft.profile, originalPrompt: draft.prompt })).job); }
    catch (e) { if (active.current) { setError(e.message); updateBusy(false); } }
  };
  const save = async event => {
    event.preventDefault();
    if (busy || disabled || saved || !result?.changed || verdict !== 'candidate' || !title.trim()) return;
    updateBusy(true); setError('');
    try {
      const item = (await call(`/${job.id}/save`, { title: title.trim(), ...(Object.keys(humanReview).length ? { humanReview } : {}) })).preference;
      if (active.current) setSaved(item);
    } catch (e) { if (active.current) setError(e.message); }
    finally { if (active.current) updateBusy(false); }
  };
  if (!supported) return null;

  return <section className="fastapi-optimization" aria-labelledby="fastapi-gepa-title">
    {recent.length > 0 && <details><summary>이 지침의 최근 개선 작업 · 7일 보관</summary>
      {recent.map(entry => <button key={entry.id} type="button" className="coding-secondary-button" disabled={busy}
        onClick={() => { setError(''); setVerdict(''); setSaved(null); setHumanReview({}); updateBusy(entry.status === 'running');
          call(`/${entry.id}`).then(data => receive(data.job)).catch(e => { setError(e.message); updateBusy(false); }); }}>
        {entry.created_at ? new Date(entry.created_at * 1000).toLocaleString('ko-KR') : '최근 작업'} · {entry.status === 'running' ? '진행 중' : entry.status === 'done' ? '결과 확인' : '중단·오류'}</button>)}
    </details>}
    <div className="coding-screen-heading"><span className="coding-kicker">선택 사항 · {frameworkLabel} + GEPA</span>
      <h3 id="fastapi-gepa-title">실제 답변으로 확인하며 지침을 다듬어 볼까요?</h3>
      <p>GEPA가 준비된 개발 과제의 답변을 평가해 보충 안내를 제안해요. 지금 고른 개발 환경과 답변 방식은 그대로 둡니다.</p></div>
    {!result && <>
      <ol className="fastapi-gepa-steps"><li>준비 과제로 평가</li><li>GEPA가 보충 안내 제안</li><li>전후 비교 후 새로 저장</li></ol>
      <p className="ws-help">준비 과제만 AI에 보내요. ‘이번 작업’ 입력 내용은 보내지 않습니다. 실제 AI 호출 비용이 발생하며 최대 {availability?.call_limit || 32}회(평가·보충 안내 생성 합계)까지 요청할 수 있어요. 몇 분 걸릴 수 있습니다.</p>
      {availability?.evaluation_scope && <p className="coding-review-support">{availability.evaluation_scope} 개선용 2개·후보 선택용 2개·별도 확인용 2개를 사용해요. 주석·역할 구성은 직접 확인합니다.</p>}
      <button className="coding-primary-button" type="button" disabled={busy || disabled || user === undefined || (Boolean(user) && !availability?.enabled)} onClick={start}>
        {busy ? 'GEPA로 다듬는 중…' : user ? '실제 AI로 GEPA 개선 시작' : '로그인하고 개선하기'}</button>
      {!availability ? <p className="ws-help" role="status">서버 설정을 확인하는 중…</p> : !availability.enabled && <p className="ws-help">{availability.reason}</p>}
    </>}
    {job?.status === 'running' && <div className="fastapi-gepa-progress" role="status"><strong>{job.stage}</strong><p>AI 요청 {job.model_calls}회 / 최대 {availability?.call_limit || 32}회 · 원본은 유지하고 있어요.</p></div>}
    {job?.id && error && job.status === 'running' && !busy && <button className="coding-secondary-button" type="button" onClick={() => {
      setError(''); updateBusy(true); call(`/${job.id}`).then(data => receive(data.job)).catch(e => { if (active.current) { setError(e.message); updateBusy(false); } });
    }}>진행 상태 다시 확인</button>}
    {result && <>
      <CodingEvaluationBreakdown result={result} />
      {result.changed && <details className="fastapi-gepa-guidance"><summary>GEPA가 덧붙인 안내 보기</summary><p>{result.guidance}</p><small>원본 문구는 유지하고 이 안내만 뒤에 덧붙였어요.</small></details>}
      <div className="fastapi-gepa-comparison">
        <div><label htmlFor="fastapi-gepa-original">개선 전 · 기존 프롬프트</label><textarea id="fastapi-gepa-original" readOnly className="task-input" rows={12} value={result.original_prompt} /></div>
        <div><label htmlFor="fastapi-gepa-candidate">{result.changed ? '개선 후 · 비교할 후보' : '검토 후 · 그대로 유지한 원본'}</label><textarea id="fastapi-gepa-candidate" readOnly className="task-input" rows={12} value={result.improved_prompt} /></div>
      </div>
      <details className="fastapi-gepa-examples"><summary>별도 과제의 실제 AI 답변도 비교하기</summary>
        <div className="prompt-actions" role="group" aria-label="비교할 별도 평가 과제">{result.report.holdout_before.tasks.map((task, index) => <button key={task.id} type="button" className="coding-secondary-button" aria-pressed={example === index} onClick={() => setExample(index)}>{task.label}</button>)}</div>
        <p className="ws-help">{result.report.holdout_before.tasks[example].request}</p>
        <div className="fastapi-gepa-comparison"><div><label htmlFor="fastapi-gepa-answer-before">기존 지침으로 받은 답변</label><textarea id="fastapi-gepa-answer-before" readOnly className="task-input" rows={12} value={result.report.holdout_before.tasks[example].response} /></div>
          <div><label htmlFor="fastapi-gepa-answer-after">{result.changed ? '후보 지침으로 받은 답변' : '원본 유지 · 동일한 답변'}</label><textarea id="fastapi-gepa-answer-after" readOnly className="task-input" rows={12} value={result.report.holdout_after.tasks[example].response} /></div></div>
        <h4>실제 답변을 보고 내가 직접 확인</h4>
        <p className="ws-help">자동 검사와 별개인 내 판단입니다. 기본 선택은 없으며 과제를 바꿔도 고른 값은 유지해요. 개선 후보를 새로 저장하면 이 확인도 함께 보관하고 원본과 자동 점수는 그대로 둡니다. 새 항목으로 저장하지 않으면 현재 화면에서만 유지됩니다.</p>
        <div className="fastapi-gepa-comparison">{(result.changed ? ['original', 'candidate'] : ['original']).map(side => {
          const task = result.report[side === 'original' ? 'holdout_before' : 'holdout_after'].tasks[example];
          return <div key={side}><h5>{side === 'original' ? '기존 답변' : '후보 답변'}</h5><HumanAnswerReview profile={result.profile}
            prefix={side === 'original' ? '기존 답변' : '후보 답변'} observation={task.observations} value={humanReview[task.id]?.[side]}
            disabled={busy || disabled || Boolean(saved)} onChange={value => setHumanReview(current => ({ ...current, [task.id]: { ...current[task.id], [side]: value } }))} /></div>;
        })}</div>
      </details>
      {result.changed && <>
        <h4>이번에는 어느 지침이 더 마음에 드나요?</h4><div className="prompt-actions" role="group" aria-label="GEPA 후보 채택">
          <button className="coding-secondary-button" type="button" aria-pressed={verdict === 'original'} disabled={busy || disabled || Boolean(saved)} onClick={() => setVerdict('original')}>기존 프롬프트 유지</button>
          <button className="coding-secondary-button" type="button" aria-pressed={verdict === 'candidate'} disabled={busy || disabled || Boolean(saved)} onClick={() => setVerdict('candidate')}>개선 후보를 새로 보관할게요</button></div>
        {verdict === 'original' && <p className="ws-help" role="status">기존 지침을 그대로 사용하세요. 보관함의 어느 항목도 변경하지 않았어요.</p>}
        {verdict === 'candidate' && <form className="fastapi-gepa-save" onSubmit={save}>
          <label className="task-input-label" htmlFor="fastapi-gepa-save-title">개선 후보를 기억할 새 이름</label><input id="fastapi-gepa-save-title" className="ws-input" value={title} required maxLength={100} disabled={busy || disabled || Boolean(saved)} onChange={event => setTitle(event.target.value)} />
          <p className="ws-help">기존 프롬프트는 그대로 두고 개선 후보·원래 지침·설정·평가 기록을 새 항목에 보관해요.</p>
          <button className="coding-primary-button" type="submit" disabled={busy || disabled || !title.trim() || Boolean(saved)}>{saved ? '개선 후보를 새 항목에 저장했어요' : '개선 후보를 새 항목으로 저장'}</button>
          {saved && <button className="coding-secondary-button" type="button" onClick={() => onOpenLibrary(saved.id)}>저장한 개선 후보 열기</button>}
        </form>}
        <button className="coding-text-button" type="button" onClick={async () => { try { await navigator.clipboard.writeText(result.improved_prompt); setCopied(true); } catch { setError('복사하지 못했어요. 후보 본문을 직접 선택해 복사해 주세요.'); } }}>{copied ? '개선 후보를 복사했어요' : '개선 후보 프롬프트 복사'}</button>
      </>}
      <p className="ws-help">이번 AI 요청 {result.report.model_calls}회 · 결과는 이 계정에 7일간 임시 보관돼요. 화면을 다시 열면 이어서 확인할 수 있어요. 계속 재사용하려면 보관함에 저장하세요.</p>
    </>}
    {error && <p className="ws-error" role="alert">{error}</p>}
    {loginOpen && !user && <AuthSection embedded signupOpen={signupOpen} onDone={onLogin} reason="선택과 원본 프롬프트는 유지됩니다. 로그인 후 개선 시작 버튼을 눌러 주세요." />}
  </section>;
}

import { useEffect, useRef, useState } from 'react';
import AuthSection from '../../shared/auth/AuthSection';
import CodingTeamPanel from './CodingTeamPanel';
import CodingExportPanel from './CodingExportPanel';
import CodingTrialPanel from './CodingTrialPanel';
import { codingWork } from './workflowApi';
import './codingWorkflow.css';

export default function CodingWorkflowPanel({ draft, preference, user, signupOpen, onLogin, onOpenLibrary, initialTeamCode = '', task = '' }) {
  const [tab, setTab] = useState('team');
  const [selected, setSelected] = useState(user ? null : draft);
  const [selection, setSelection] = useState(null);
  const [login, setLogin] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [name, setName] = useState('팀 기준을 반영한 내 작업 지침');
  const [saved, setSaved] = useState(null);
  const [timerActive, setTimerActive] = useState(false);
  const request = useRef(0);
  const identity = preference ? { preferenceId: preference.id, preferenceRevision: preference.revision } : { profile: draft.profile };
  const source = { ...identity, ...(selection ? { teamSelection: selection } : {}) };
  const identityKey = JSON.stringify(identity);
  const resolve = async teamSelection => {
    const token = ++request.current;
    setSelected(null); setSelection(null); setSaved(null); setBusy(true); setError('');
    try {
      if (!user) { if (token === request.current) setSelected(draft); return; }
      const data = await codingWork('resolve', { ...identity, ...(teamSelection ? { teamSelection } : {}) });
      if (token === request.current) { setSelected(data.draft); setSelection(teamSelection); }
    } catch (e) { if (token === request.current) setError(e.message); throw e; }
    finally { if (token === request.current) setBusy(false); }
  };
  useEffect(() => { resolve(null).catch(() => {}); return () => { request.current += 1; }; }, [identityKey, user?.id]);
  const save = async () => {
    setBusy(true); setError('');
    try { const data = await codingWork('save', { ...source, title: name, snapshot: selected.snapshot }); setSaved(data.preference); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };
  return <section className="coding-workflow" aria-label="코딩 지침 적용과 실제 작업 비교">
    <h3>만든 지침을 실제 작업에 연결하세요</h3>
    <p>팀 기준 확인 → 사용할 지침 확인 → 도구 적용 → 작업 결과 기록의 순서로 이어집니다.</p>
    <div className="coding-work-tabs" role="group" aria-label="지침 적용 단계">
      {[['team', '1. 팀 기준과 연결'], ['export', '2. 도구에 적용'], ['trial', '3. 작업 시간·기능 비교']].map(([key, label]) =>
        <button type="button" key={key} className="coding-secondary-button" aria-pressed={tab === key} disabled={busy || (timerActive && key !== 'trial')} onClick={() => setTab(key)}>{label}</button>)}
    </div>
    {selected && <div className="coding-work-selected" role="status">
      <strong>현재 사용할 지침: {selected.team_context ? `${selected.team_context.name} ${selected.team_context.revision}판을 반영한 작업용` : '개인용'}</strong>
      <details><summary>실제 전달할 지침 확인</summary><textarea readOnly rows={6} value={selected.prompt} /></details>
      {selected.team_context && <>
        <p className="ws-help">선택 출처와 당시 팀 규칙을 함께 보관합니다. 기존 개인 지침·팀 기준은 바꾸지 않습니다.</p>
        <label>새 보관 이름<input value={name} maxLength={100} onChange={e => setName(e.target.value)} /></label>
        <button type="button" className="coding-secondary-button" disabled={busy || !name.trim() || Boolean(saved)} onClick={save}>{saved ? '새 항목으로 저장했어요' : '이 작업용 지침을 새 항목으로 보관'}</button>
        {saved && <button type="button" className="coding-text-button" onClick={() => onOpenLibrary?.(saved.id)}>보관함에서 열기</button>}
      </>}
    </div>}
    {busy && <p role="status">지침과 저장 버전을 확인하고 있어요…</p>}
    {error && <div><p role="alert" className="ws-error">{error}</p>
      <button type="button" className="coding-secondary-button" disabled={busy} onClick={() => resolve(null).catch(() => {})}>원래 지침 다시 불러오기</button></div>}
    {!user && tab !== 'export' && <div className="coding-work-card">
      <p>팀과 작업 비교는 로그인 후 보관할 수 있어요. 파일 내보내기는 로그인 없이 가능합니다.</p>
      <button type="button" className="coding-secondary-button" onClick={() => setLogin(true)}>로그인</button>
      {login && <AuthSection signupOpen={signupOpen} reason="팀 기준과 실제 작업 비교를 내 계정에 보관합니다."
        onDone={next => { setLogin(false); onLogin(next); }} onBack={() => setLogin(false)} />}
    </div>}
    <div hidden={tab !== 'team'}>
      {user && <CodingTeamPanel key={`${identityKey}-${user.id}`} profile={draft.profile} user={user} initialCode={initialTeamCode}
        onApply={resolve} onReset={() => resolve(null).catch(() => {})} />}
    </div>
    <div hidden={tab !== 'export'}><CodingExportPanel prompt={selected?.prompt || ''} /></div>
    <div hidden={tab !== 'trial'}>
      {user && <CodingTrialPanel key={user.id} source={source} selected={selected} user={user} task={task} onActiveChange={setTimerActive} />}
    </div>
  </section>;
}

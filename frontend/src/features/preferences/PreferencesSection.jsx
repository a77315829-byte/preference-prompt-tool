import { useCallback, useEffect, useRef, useState } from 'react';
import AuthSection from '../../shared/auth/AuthSection';
import { fetchHealth } from '../comparison/codingApi';
import { createPreference, deletePreference, getPreference, listPreferences, runPreference, updatePreference } from './preferencesApi';
import { composePreferenceRequest, PREFERENCE_CATEGORIES, WORK_EXAMPLES } from './preferenceText';
import TeamPreferenceComparison from './TeamPreferenceComparison';
import TaskPreferenceMixer from './TaskPreferenceMixer';
import SaveTaskPreferencePanel from './SaveTaskPreferencePanel';
import SavedPreferenceSources from './SavedPreferenceSources';
import RemixSavedPreferencePanel from './RemixSavedPreferencePanel';
import SavedRemixComparison from './SavedRemixComparison';
import { selectionMatches } from './comparisonText';

const formOf = (item) => ({ title: item.title, domainKey: item.domain_key, prompt: item.prompt, note: item.note || '' });

function PreferencesSection({ user, signupOpen, onLogin, onBack, onStartComparison, initialId = '' }) {
  const [items, setItems] = useState(null);
  const [item, setItem] = useState(null);
  const [form, setForm] = useState(null);
  const [view, setView] = useState('use');
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [task, setTask] = useState('');
  const [output, setOutput] = useState(null);
  const [basis, setBasis] = useState('personal');
  const [teamComparison, setTeamComparison] = useState(null);
  const [taskDraft, setTaskDraft] = useState(null);
  const [health, setHealth] = useState(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [copied, setCopied] = useState('');
  const requestId = useRef(0);
  const editorRef = useRef(null);
  const dirty = form && (!item?.id || JSON.stringify(form) !== JSON.stringify(formOf(item)));
  const leaveOk = () => !(dirty || task.trim()) || window.confirm('저장하지 않은 수정 내용과 새 작업 입력이 사라집니다. 계속할까요?');
  const teamChanged = useCallback((next) => {
    setTeamComparison(next); setTaskDraft(null); setBasis('personal'); setCopied(''); setError('');
  }, []);
  const draftChanged = useCallback((next) => {
    setTaskDraft(next); setBasis((current) => next ? 'custom' : current === 'custom' ? 'personal' : current);
    setCopied(''); setError('');
  }, []);

  const adopt = (next, mode = 'use') => {
    setItem(next); setForm(formOf(next)); setView(mode); setTask(''); setOutput(null); setCopied(''); setNotice('');
    setBasis('personal'); setTeamComparison(null); setTaskDraft(null);
    window.setTimeout(() => editorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 30);
  };

  const open = async (id, mode = 'use', reload = false) => {
    if (!reload && id === item?.id) {
      if (mode === 'use' && dirty) { setError('수정 내용을 먼저 저장한 뒤 새 작업에 사용해 주세요.'); return; }
      setView(mode); setError(''); return;
    }
    if (!leaveOk()) return;
    const token = ++requestId.current;
    setBusy('open'); setError('');
    try {
      const next = await getPreference(id);
      if (token === requestId.current) adopt(next, mode);
    } catch (e) { if (token === requestId.current) setError(e.message); }
    finally { if (token === requestId.current) setBusy(''); }
  };

  useEffect(() => {
    if (!user) return undefined;
    const token = ++requestId.current;
    let cancelled = false;
    listPreferences().then(async (list) => {
      if (cancelled) return;
      setItems(list);
      if (initialId) {
        try {
          const next = await getPreference(initialId);
          if (!cancelled && token === requestId.current) adopt(next);
        } catch (e) { if (!cancelled && token === requestId.current) setError(e.message); }
      }
    }).catch((e) => { if (!cancelled) { setItems([]); setError(e.message); } });
    fetchHealth().then((next) => { if (!cancelled) setHealth(next); }).catch(() => { if (!cancelled) setHealth({ liveConfigured: false }); });
    return () => { cancelled = true; requestId.current += 1; };
  }, [user?.id, initialId]);

  const edit = (key, value) => { setForm((current) => ({ ...current, [key]: value })); setNotice(''); setCopied(''); };
  const save = async (event) => {
    event.preventDefault(); setBusy('save'); setError(''); setNotice('');
    try {
      const saved = item.id ? await updatePreference(item.id, { ...form, revision: item.revision }) : await createPreference(form);
      setItem(saved); setForm(formOf(saved));
      setBasis('personal'); setTeamComparison(null); setTaskDraft(null);
      setItems((current) => [saved, ...(current || []).filter((p) => p.id !== saved.id)]);
      setNotice('저장했어요. 새 작업에 사용할 수 있습니다.');
    } catch (e) { setError(e.message); }
    finally { setBusy(''); }
  };

  const add = () => {
    if (!leaveOk()) return;
    adopt({ id: null, title: '', domain_key: 'summarization_ko', prompt: '', note: '' }, 'edit');
    setError('');
  };
  const remove = async () => {
    if (!window.confirm(`‘${item.title}’을 보관함에서 삭제할까요? 삭제하면 되돌릴 수 없습니다.`)) return;
    setBusy('delete'); setError('');
    try {
      await deletePreference(item.id, item.revision);
      setItems((current) => current.filter((p) => p.id !== item.id));
      setItem(null); setForm(null); setTask(''); setOutput(null); setNotice('보관함에서 삭제했어요.');
    } catch (e) { setError(e.message); }
    finally { setBusy(''); }
  };

  const chosenPrompt = basis === 'custom' ? taskDraft?.prompt || '' : basis === 'team' ? teamComparison?.team_prompt || '' : item?.prompt || '';
  const requestText = item?.id ? composePreferenceRequest(chosenPrompt, task, item.domain_key) : '';
  const copy = async (kind, text) => {
    try { await navigator.clipboard.writeText(text); setCopied(kind); setError(''); }
    catch { setCopied(''); setError('복사하지 못했어요. 아래 내용 칸을 직접 선택해 복사해 주세요.'); }
  };
  const run = async () => {
    setBusy('run'); setError(''); setCopied('');
    const snapshot = { task, revision: item.revision, id: item.id };
    const selection = basis !== 'personal' ? { basis, teamCode: teamComparison.team_code,
      teamSnapshot: teamComparison.team_snapshot, teamLanguage: teamComparison.team_language,
      ...(basis === 'custom' ? { choices: taskDraft.choices, taskSnapshot: taskDraft.snapshot } : {}) } : { basis: 'personal' };
    try {
      const result = await runPreference(snapshot.id, snapshot.revision, snapshot.task, selection);
      setOutput({ ...result, task: snapshot.task });
    } catch (e) { setError(e.message); }
    finally { setBusy(''); }
  };
  const shown = (items || []).filter((p) => (filter === 'all' || (filter === 'coding' ? p.domain_key === 'coding' : p.domain_key.startsWith('summarization')))
    && `${p.title} ${p.note}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  const startComparison = (domain) => { if (leaveOk()) onStartComparison(domain); };

  return (
    <section className="comparison-section preferences-section" id="preferences-section">
      <div className="comparison-inner">
        <button className="back-button" type="button" onClick={() => { if (leaveOk()) onBack(); }}>← 시작 화면으로</button>
        <div className="comparison-heading">
          <p className="eyebrow">MY PREFERENCES</p><h2>내 선호 보관함</h2>
          <p>마음에 들었던 요약·코딩 방식을 모아 두세요. 저장한 지침을 고치고, 새 작업에도 같은 방식으로 요청할 수 있어요.</p>
        </div>
        <ol className="workflow-guide">
          <li><strong>1. 내 방식을 저장해요</strong><span>예시 비교를 마친 뒤 결과 화면에서 보관함에 담습니다.</span></li>
          <li><strong>2. 필요할 때 고쳐요</strong><span>이름·설명·지침을 수정하고 저장합니다.</span></li>
          <li><strong>3. 새 작업에 사용해요</strong><span>새 원문이나 개발 요청을 넣고 복사하거나 AI로 실행합니다.</span></li>
        </ol>
        {user === undefined ? <p role="status">계정을 확인하는 중…</p> : !user ? (
          <AuthSection embedded signupOpen={signupOpen} onDone={onLogin}
            reason="로그인하면 내 계정의 지침만 볼 수 있고, 다음 방문에도 다시 사용할 수 있어요. 아직 지침이 없다면 아래에서 내 취향부터 찾아보세요." />
        ) : <>
          <div className="preference-toolbar ws-step">
            <label className="task-input-label" htmlFor="preference-search">이름·설명으로 찾기</label>
            <input id="preference-search" className="ws-input" placeholder="예: 회의록, React" value={search} onChange={(e) => setSearch(e.target.value)} />
            <div className="prompt-actions" role="group" aria-label="보관함 분류">
              {[['all', '전체'], ['summary', '요약용'], ['coding', '코딩용']].map(([value, label]) => (
                <button className={filter === value ? 'prompt-copy-button' : 'prompt-reset-button'} type="button" key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>
              ))}
              <button className="prompt-reset-button" type="button" disabled={Boolean(busy)} onClick={add}>가진 프롬프트 직접 추가</button>
            </div>
            {items === null ? <p role="status">보관함을 불러오는 중…</p> : items.length === 0 ? <p>아직 저장한 지침이 없어요. 아래에서 요약·코딩 취향을 찾거나 가진 프롬프트를 직접 추가하세요.</p>
              : shown.length === 0 ? <p>이 조건에 맞는 항목이 없어요. 검색어나 분류를 바꿔 보세요.</p>
              : <ul className="preference-list">{shown.map((p) => (
                <li key={p.id} className={p.id === item?.id ? 'is-selected' : ''}>
                  <div><span className="ws-help">{PREFERENCE_CATEGORIES[p.domain_key]}</span><h3>{p.title}</h3>{p.note && <p>{p.note}</p>}
                    <span className="ws-help">수정: {new Date(p.updated_at).toLocaleString('ko-KR')}</span></div>
                  <div className="prompt-actions">
                    <button className="prompt-copy-button" type="button" disabled={Boolean(busy)} onClick={() => open(p.id)}>새 작업에 사용</button>
                    <button className="prompt-reset-button" type="button" disabled={Boolean(busy)} onClick={() => open(p.id, 'edit')}>수정</button>
                  </div>
                </li>
              ))}</ul>}
          </div>
          {form && <div className="ws-step preference-editor" ref={editorRef}>
            <div className="prompt-actions">
              <button className="prompt-reset-button" type="button" disabled={Boolean(busy)} aria-pressed={view === 'edit'} onClick={() => setView('edit')}>지침 수정</button>
              {item.id && <button className="prompt-reset-button" type="button" disabled={Boolean(busy) || dirty} aria-pressed={view === 'use'} onClick={() => setView('use')}>새 작업에 쓰기</button>}
            </div>
            {item.id && item.provenance?.remixed_from && <SavedRemixComparison key={`comparison-${item.id}-${item.revision}`}
              before={item.provenance.remixed_from} afterAxes={item.provenance.axes} afterTitle={item.title}
              matches={item.provenance_matches && form.prompt === item.prompt && form.domainKey === item.domain_key}
              restoreContext={view === 'use' ? { item, disabled: Boolean(busy), onBusy: setBusy, onOpen: open,
                onSaved: (saved) => setItems((current) => [saved, ...(current || []).filter((p) => p.id !== saved.id)]) } : null} />}
            {item.id && <SavedPreferenceSources item={item} editingPrompt={form.prompt !== item.prompt || form.domainKey !== item.domain_key} />}
            {item.id && view === 'use' && item.provenance && <RemixSavedPreferencePanel key={`${item.id}-${item.revision}`}
              item={item} disabled={Boolean(busy)} onBusy={setBusy} onOpen={open}
              onSaved={(saved) => setItems((current) => [saved, ...(current || []).filter((p) => p.id !== saved.id)])} />}
            {view === 'edit' ? <form onSubmit={save}>
              <h3>{item.id ? '내 방식에 맞게 수정하기' : '가진 프롬프트 보관하기'}</h3>
              <label className="task-input-label" htmlFor="preference-title">기억하기 쉬운 이름</label>
              <input id="preference-title" className="ws-input" disabled={Boolean(busy)} required maxLength={100} value={form.title} onChange={(e) => edit('title', e.target.value)} placeholder="예: 짧은 회의록 요약" />
              <label className="task-input-label" htmlFor="preference-domain">언제 쓸 지침인가요?</label>
              <select id="preference-domain" className="ws-input" disabled={Boolean(busy)} value={form.domainKey} onChange={(e) => edit('domainKey', e.target.value)}>
                {Object.entries(PREFERENCE_CATEGORIES).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
              </select>
              <label className="task-input-label" htmlFor="preference-note">나중에 알아볼 설명 <span>(선택)</span></label>
              <input id="preference-note" className="ws-input" disabled={Boolean(busy)} maxLength={1000} value={form.note} onChange={(e) => edit('note', e.target.value)} placeholder="예: 결정 사항·담당자·기한을 먼저 보고 싶을 때" />
              <label className="task-input-label" htmlFor="preference-prompt">AI에게 줄 지침</label>
              <textarea id="preference-prompt" className="task-input" disabled={Boolean(busy)} rows={12} required maxLength={20000} value={form.prompt} onChange={(e) => edit('prompt', e.target.value)} />
              <p className="ws-help" role="status">{dirty ? '수정 중 · 아직 저장하지 않았어요.' : '저장된 내용과 같아요.'} 새 작업 원문은 아래 ‘새 작업에 쓰기’에서 입력하세요.</p>
              <div className="prompt-actions">
                <button className="prompt-copy-button" type="submit" disabled={Boolean(busy) || !dirty || !form.title.trim() || !form.prompt.trim()}>{busy === 'save' ? '저장하는 중…' : '변경 내용 저장'}</button>
                {item.id && <button className="prompt-reset-button" type="button" disabled={Boolean(busy)} onClick={() => open(item.id, 'edit', true)}>저장된 내용 다시 불러오기</button>}
                {item.id && <button className="prompt-reset-button" type="button" disabled={Boolean(busy)} onClick={remove}>보관함에서 삭제</button>}
              </div>
            </form> : <>
              <h3>{item.title} · 새 작업에 사용하기</h3>
              <TeamPreferenceComparison key={item.id} item={item} disabled={Boolean(busy)} onChange={teamChanged} />
              {teamComparison && <TaskPreferenceMixer key={`${item.id}-${item.revision}-${teamComparison.team_snapshot}`}
                item={item} comparison={teamComparison} disabled={Boolean(busy)} onChange={draftChanged} />}
              <h4>이번 작업에는 어떤 지침을 쓸까요?</h4>
              <div className="prompt-actions" role="group" aria-label="이번 작업에 사용할 지침">
                <button className={basis === 'personal' ? 'prompt-copy-button' : 'prompt-reset-button'} type="button" aria-pressed={basis === 'personal'} disabled={Boolean(busy)}
                  onClick={() => { setBasis('personal'); setCopied(''); setError(''); }}>개인용으로 사용</button>
                <button className={basis === 'team' ? 'prompt-copy-button' : 'prompt-reset-button'} type="button" aria-pressed={basis === 'team'} disabled={Boolean(busy) || !teamComparison}
                  onClick={() => { setBasis('team'); setCopied(''); setError(''); }}>팀용으로 사용</button>
                <button className={basis === 'custom' ? 'prompt-copy-button' : 'prompt-reset-button'} type="button" aria-pressed={basis === 'custom'} disabled={Boolean(busy) || !taskDraft}
                  onClick={() => { setBasis('custom'); setCopied(''); setError(''); }}>이번 작업용으로 사용</button>
              </div>
              <p className="ws-help" role="status">{basis === 'custom' ? '이번 작업: 항목별로 고른 작업용 지침 · 원본은 그대로 유지' : basis === 'team' ? `이번 작업: ${teamComparison?.team_name}의 팀 기준` : '이번 작업: 보관한 내 개인 지침'}
                {!teamComparison && ' · 팀용을 쓰려면 먼저 위에서 팀 기준을 확인하세요.'}</p>
              <details className="ws-raw"><summary>이번에 사용할 지침 보기</summary><pre className="prompt-box"><code>{chosenPrompt}</code></pre></details>
              {basis === 'custom' && taskDraft && <SaveTaskPreferencePanel key={`${item.id}-${taskDraft.snapshot}`}
                item={item} comparison={teamComparison} draft={taskDraft} disabled={Boolean(busy)} onBusy={setBusy}
                onSaved={(saved) => setItems((current) => [saved, ...(current || []).filter((p) => p.id !== saved.id)])} onOpen={open} />}
              <label className="task-input-label" htmlFor="preference-task">{item.domain_key === 'coding' ? '이번에 만들 기능이나 개발 요청' : '이번에 요약할 원문'}</label>
              <textarea id="preference-task" className="task-input" rows={6} maxLength={12000} value={task} onChange={(e) => { setTask(e.target.value); setCopied(''); }} placeholder="새 작업 내용을 여기에 넣으세요." />
              <button className="ws-small-button" type="button" disabled={Boolean(busy)} onClick={() => {
                if (!task.trim() || window.confirm('입력한 작업을 예시로 바꿀까요?')) { setTask(WORK_EXAMPLES[item.domain_key]); setCopied(''); }
              }}>예시 자료 넣어보기</button>
              <p className="ws-help">새 작업 내용은 보관함에 저장하지 않습니다. 아래 요청문을 복사해 평소 사용하는 AI에 붙여 넣으세요.</p>
              {requestText && <>
                <label className="task-input-label" htmlFor="preference-request">AI에 보낼 요청문</label>
                <textarea id="preference-request" className="task-input" readOnly rows={8} value={requestText} onFocus={(e) => e.target.select()} />
                <div className="prompt-actions">
                  <button className="prompt-copy-button" type="button" onClick={() => copy('request', requestText)}>{copied === 'request' ? '요청문을 복사했어요' : '지침 + 새 작업 복사'}</button>
                  <button className="prompt-reset-button" type="button" disabled={Boolean(busy) || !health?.liveConfigured} onClick={run}>{busy === 'run' ? 'AI가 작업하는 중…' : '이 지침으로 AI 실행'}</button>
                </div>
              </>}
              <p className="ws-help">{health?.liveConfigured ? 'AI 실행을 누르면 입력 자료가 모델에 전송되며 모델 사용 비용이 발생할 수 있습니다. 실행 결과는 자동 저장하지 않습니다.' : '현재는 복사해서 사용할 수 있어요. 실제 생성 모드에서는 이 화면에서 AI를 실행할 수도 있습니다.'}</p>
              {output && <div className="preference-output">
                <h4>{selectionMatches(output, task, item, basis, teamComparison, taskDraft) ? 'AI 실행 결과' : '이전 입력·지침으로 실행한 결과'}</h4>
                <p className="ws-help">{output.basis === 'custom' ? '이번 작업용 지침' : output.basis === 'team' ? '팀용 지침' : '개인용 지침'} · {output.model} · 저장 버전 {output.revision} · 생성한 코드는 자동 실행하지 않습니다.</p>
                <textarea className="task-input" aria-label="AI 실행 결과 내용" readOnly rows={10} value={output.output} onFocus={(e) => e.target.select()} />
                <button className="prompt-reset-button" type="button" onClick={() => copy('output', output.output)}>{copied === 'output' ? '결과를 복사했어요' : '결과 복사'}</button>
              </div>}
            </>}
          </div>}
        </>}
        {error && <p className="ws-error" role="alert">{error}</p>}
        {notice && <p className="ws-help" role="status">{notice}</p>}
        <div className="ws-step">
          <h3>새로운 내 방식 찾기</h3><p className="ws-help">원하는 표현을 설명하기 어렵다면, 두 예시 중 마음에 드는 쪽을 골라 보세요.</p>
          <div className="prompt-actions">
            <button className="prompt-reset-button" type="button" onClick={() => startComparison('summarization_ko')}>요약 취향 찾기</button>
            <button className="prompt-reset-button" type="button" onClick={() => startComparison('coding')}>코딩 취향 찾기</button>
          </div>
        </div>
      </div>
    </section>
  );
}

export default PreferencesSection;

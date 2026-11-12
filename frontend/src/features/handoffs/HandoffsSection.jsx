import { useEffect, useRef, useState } from 'react';
import AuthSection from '../../shared/auth/AuthSection';
import HandoffFields from './HandoffFields';
import HandoffAttachments from './HandoffAttachments';
import { readDraft, useDraftCache } from '../../shared/draftCache';
import './handoffFlow.css';
import { HANDOFF_EVENTS, HANDOFF_STATUS, changeHandoff, continuationRequest, createHandoff, getHandoff,
  getHandoffHistory, getHandoffVersion, handoffBody, handoffForm, handoffLink, listHandoffs, parseHandoffLink, readHandoffFile } from './handoffApi';

function HandoffsSection({ user, signupOpen, onLogin, onBack, onNavigationRisk, onConsumeInitial, initialId = '', initialDraft = null }) {
  const [restored] = useState(() => initialDraft ? null : readDraft('handoff', user));
  const [items, setItems] = useState(null);
  const [item, setItem] = useState(restored?.item || null);
  const [form, setForm] = useState(() => initialDraft ? handoffForm({ title: initialDraft.title, body: initialDraft }) : restored?.form || null);
  const [filter, setFilter] = useState('all');
  const [linkInput, setLinkInput] = useState('');
  const [recipient, setRecipient] = useState(restored?.recipient || '');
  const [history, setHistory] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [copied, setCopied] = useState('');
  const [file, setFile] = useState(null);
  const request = useRef(0);
  const account = useRef(user?.id);
  const editor = useRef(null);
  const contentDirty = Boolean(form && (item ? JSON.stringify(form) !== JSON.stringify(handoffForm(item)) : Object.values(form).some((v) => v.trim())));
  const dirty = contentDirty || Boolean(file);
  useDraftCache('handoff', user, { item, form, recipient });
  useEffect(() => { if (initialDraft) onConsumeInitial?.(); }, [initialDraft, onConsumeInitial]);
  useEffect(() => {
    const message = file ? '아직 첨부하지 않은 파일은 다시 선택해야 합니다. 작성 내용은 임시 보관됩니다. 이동할까요?'
      : busy ? '요청을 처리 중입니다. 화면을 옮긴 뒤 저장 결과를 다시 확인해야 합니다. 이동할까요?' : '';
    onNavigationRisk?.(message);
    const warn = event => { event.preventDefault(); event.returnValue = ''; };
    if (file || busy) window.addEventListener('beforeunload', warn);
    return () => { onNavigationRisk?.(''); window.removeEventListener('beforeunload', warn); };
  }, [file, busy, onNavigationRisk]);
  const leaveOk = () => !dirty || window.confirm('아직 저장하지 않은 작업 내용이 사라집니다. 이동할까요?');
  const adopt = (next, preserveFile = false) => {
    setItem(next); setForm(handoffForm(next)); setRecipient(next.recipient || ''); setHistory(null); setSnapshot(null); setCopied(''); if (!preserveFile) setFile(null);
    window.setTimeout(() => editor.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 30);
  };
  const upsert = (next) => setItems((current) => [next, ...(current || []).filter((r) => r.id !== next.id)]);
  const handleRequestError = async (failure, token, id, directRead = false) => {
    if (token !== request.current) return;
    setError(failure.message);
    if (![401, 403, 404].includes(failure.status)) return;
    // An absent historical version or a denied edit need not revoke read access.
    // Confirm the current resource before discarding its cached draft; a 409
    // conflict or transient server failure must preserve the user's input.
    let unavailable = directRead || failure.status === 401;
    if (!unavailable && id) {
      try { await getHandoff(id); }
      catch (check) { unavailable = [401, 403, 404].includes(check.status); }
    }
    if (!unavailable || token !== request.current) return;
    if (failure.status === 401 || item?.id === id) {
      setItem(null); setForm(null); setRecipient(''); setHistory(null); setSnapshot(null);
      setNotice(''); setCopied(''); setFile(null);
    }
    setItems((current) => failure.status === 401 ? [] : (current || []).filter((entry) => entry.id !== id));
  };

  useEffect(() => {
    const token = ++request.current;
    setItems(null); setError(''); setBusy('');
    if (account.current && account.current !== user?.id) {
      setItem(null); setForm(null); setHistory(null); setSnapshot(null); setRecipient(''); setNotice(''); setCopied(''); setFile(null);
    }
    account.current = user?.id;
    if (!user) return undefined;
    listHandoffs().then(async (next) => {
      if (token !== request.current) return;
      setItems(next);
      const target = initialId || restored?.item?.id;
      if (target) {
        try {
          const selected = await getHandoff(target);
          if (token === request.current) {
            if (restored?.item?.id === target && restored.form) {
              if (!selected.can_edit) { adopt(selected); setNotice('현재 권한에 맞춰 저장된 내용을 다시 불러왔어요.'); }
              else setNotice(selected.revision !== restored.item.revision
                ? '임시 초안을 복구했지만 서버에 더 최신 버전이 있어요. 초안을 복사해 두고 최신 항목을 다시 열어 내용을 합쳐 주세요.'
                : '이 탭에 남겨 둔 초안을 복구했어요. 서버에 반영하려면 저장해 주세요.');
            } else adopt(selected);
          }
        } catch (e) { if (token === request.current) { setItem(null); setForm(null); setRecipient(''); setError(e.message); } }
      }
    }).catch((e) => { if (token === request.current) { setItems([]); setError(e.message); } });
    return () => { request.current += 1; };
  }, [user?.id, initialId]);

  const open = async (id) => {
    if (!leaveOk()) return;
    const token = ++request.current; setBusy('open'); setError(''); setNotice('');
    try { const next = await getHandoff(id); if (token === request.current) adopt(next); }
    catch (e) { await handleRequestError(e, token, id, true); }
    finally { if (token === request.current) setBusy(''); }
  };
  const mutate = async (action, payload = {}) => {
    if (busy || !user) return;
    const token = ++request.current; setBusy(action); setError(''); setNotice('');
    try {
      if (action === 'attach') payload = await readHandoffFile(file);
      if (token !== request.current) return;
      const next = action === 'create' ? await createHandoff(payload) : await changeHandoff(item, action, payload);
      if (token === request.current) {
        adopt(next, action === 'update'); upsert(next);
        setNotice(({ create: '내 작업으로 저장했어요. 받을 팀원을 지정하면 공유됩니다.', update: '진행 상황을 저장했어요. 이전 버전도 남아 있어요.',
          share: '지정한 팀원이 열 수 있어요. 링크를 복사해 전달하세요.', claim: '이 작업을 이어서 맡았어요. 진행 상황과 남은 일을 갱신하세요.', complete: '작업을 완료로 표시했어요.', reopen: '다시 진행 중으로 바꿨어요.',
          attach: '파일을 저장했어요. 이 작업을 볼 수 있는 팀원도 열거나 내려받을 수 있어요.', detach: '현재 첨부에서 뺐어요. 이전 기록에는 파일이 그대로 남아 있어요.' })[action]);
      }
    } catch (e) { await handleRequestError(e, token, item?.id); }
    finally { if (token === request.current) setBusy(''); }
  };
  const save = (event) => { event.preventDefault(); if (snapshot || (item && !item.can_edit)) return; mutate(item ? 'update' : 'create', handoffBody(form)); };
  const loadHistory = async (revision) => {
    const token = ++request.current; setBusy('history'); setError('');
    try {
      if (revision) { const next = await getHandoffVersion(item.id, revision); if (token === request.current) setSnapshot(next); }
      else { const next = await getHandoffHistory(item.id); if (token === request.current) setHistory(next); }
    } catch (e) { await handleRequestError(e, token, item.id); }
    finally { if (token === request.current) setBusy(''); }
  };
  const copy = async (kind, text) => {
    try { await navigator.clipboard.writeText(text); setCopied(kind); setError(''); }
    catch { setCopied(''); setError('복사하지 못했어요. 아래 표시된 내용을 직접 선택해 복사해 주세요.'); }
  };
  const visible = (items || []).filter((entry) => filter === 'all' || entry.role === filter);
  const displayed = snapshot ? { ...item, ...snapshot } : item;
  const requestText = displayed ? continuationRequest(displayed) : '';

  return <section className="comparison-section handoffs-section">
    <div className="comparison-inner">
      <button className="back-button" type="button" disabled={Boolean(busy)} onClick={() => {
        if (!file || window.confirm('첨부하지 않은 파일은 다시 선택해야 합니다. 작성 내용은 임시 보관됩니다. 이동할까요?')) onBack();
      }}>← 시작 화면으로</button>
      <p className="ws-help">작성 중인 내용은 이 탭에 하루 동안 임시 보관돼요. 다른 메뉴에서 돌아와도 이어 쓸 수 있어요. 로그아웃하면 지워지며 파일은 저장 후 첨부해 주세요.</p>
      <header className="handoff-heading"><div><p className="eyebrow">TEAM WORKSPACE</p><h2>하던 일의 다음을,<br />팀원과 이어가요.</h2>
        <p>어디까지 했고, 다음에는 무엇을 하면 될까요?<br />작업 맥락과 자료, AI 프롬프트를 한곳에 남겨 주세요.</p></div><span className="handoff-heading-note">내 작업 기록 → 팀원에게 전달 → 이어서 진행</span></header>
      <ol className="handoff-journey" aria-label="인수인계 사용 순서">
        <li><span>01</span><div><strong>하던 일 정리</strong><p>목적·진행 상황·다음 행동을 저장해요.</p></div></li>
        <li><span>02</span><div><strong>자료와 함께 전달</strong><p>파일을 첨부하고 받을 계정을 지정해요.</p></div></li>
        <li><span>03</span><div><strong>열어서 이어서 맡기</strong><p>받은 팀원이 진행을 갱신해요.</p></div></li>
      </ol>
      {user === undefined ? <p role="status">계정을 확인하는 중…</p> : !user ? <AuthSection embedded signupOpen={signupOpen} onDone={onLogin}
        reason="인수인계 내용은 작성자와 지정된 받는 팀원만 볼 수 있어요. 링크를 받았다면 지정된 계정으로 로그인하세요. 보관함에서 가져온 내용은 로그인 후 확인하고 저장합니다." /> : <>
        <div className="ws-step handoff-workspace">
          <div className="handoff-entry-grid"><div className="handoff-new-card"><span className="handoff-section-label">내가 넘길 일이 있나요?</span><h3>다음 담당자를 위한 작업 기록</h3><p>먼저 내 작업으로 저장하세요.<br />공유할 계정을 정하기 전에는 나만 볼 수 있어요.</p><button className="prompt-copy-button" type="button" disabled={Boolean(busy)} onClick={() => {
            if (leaveOk()) { request.current += 1; setItem(null); setForm(handoffForm()); setHistory(null); setSnapshot(null); setRecipient(''); setError(''); setNotice(''); setCopied(''); setFile(null);
              window.setTimeout(() => editor.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 30); }
          }}>새 작업 넘기기</button></div>
          <form className="handoff-open-form" onSubmit={(e) => { e.preventDefault(); try { open(parseHandoffLink(linkInput)); } catch (err) { setError(err.message); } }}>
            <span className="handoff-section-label">팀원이 링크를 보냈나요?</span><h3>받은 작업 이어가기</h3><p>지정된 계정으로 로그인한 뒤 열어 주세요.</p>
            <label className="task-input-label" htmlFor="handoff-link-input">받은 인수인계 링크·작업 코드 열기</label>
            <input id="handoff-link-input" className="ws-input" placeholder="받은 링크 또는 작업 코드를 붙여넣으세요" maxLength={2048} disabled={Boolean(busy)} value={linkInput} onChange={(e) => setLinkInput(e.target.value)} />
            <button className="prompt-reset-button" type="submit" disabled={Boolean(busy) || !linkInput.trim()}>받은 링크 열기</button>
          </form></div>
          <div className="handoff-list-heading"><div><span className="handoff-section-label">함께 이어가는 작업</span><h3>내 작업 모아보기</h3></div><button className="handoff-text-button" type="button" disabled={Boolean(busy)} onClick={async () => {
            const token = ++request.current; setBusy('list'); setError('');
            try { const next = await listHandoffs(); if (token === request.current) setItems(next); }
            catch (e) { if (token === request.current) setError(e.message); }
            finally { if (token === request.current) setBusy(''); }
          }}>목록 새로고침</button></div>
          <div className="handoff-filters" role="group" aria-label="인수인계 분류">{[['all', '전체'], ['owner', '내가 만든 작업'], ['recipient', '내가 받은 작업']].map(([value, label]) =>
            <button key={value} type="button" aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}<span aria-hidden="true">{items === null ? '…' : items.filter(entry => value === 'all' || entry.role === value).length}</span></button>)}</div>
          {items === null ? <p role="status">작업을 불러오는 중…</p> : !visible.length ? <p className="handoff-empty">아직 이 분류의 인수인계가 없어요.<br />새 작업을 저장하거나 받은 링크를 열어 보세요.</p>
            : <ul className="handoff-list">{visible.map((entry) => <li key={entry.id} className={item?.id === entry.id ? 'is-current' : ''}>
              <div><span className={`handoff-status handoff-status-${entry.status}`}>{HANDOFF_STATUS[entry.status]}</span><strong>{entry.title}</strong><p className="ws-help">{entry.owner} → {entry.recipient || '받을 팀원 지정 전'} · {entry.revision}번째 버전</p></div>
              <button className="prompt-reset-button" type="button" disabled={Boolean(busy)} onClick={() => open(entry.id)}>작업 열기</button>
            </li>)}</ul>}
        </div>
        {form && <div className="ws-step handoff-editor" ref={editor}>
          <div className="handoff-editor-heading"><span className="handoff-section-label">{snapshot ? '이전 기록' : item ? '지금 보고 있는 작업' : '새 인수인계 작성'}</span><h3>{item ? item.title : '새 작업의 맥락을 남겨요'}</h3>
            <p>{snapshot ? '지난 시점의 내용입니다. 현재 작업은 바뀌지 않아요.' : !item ? '필수 항목 네 가지를 채우고 저장하면 자료 첨부와 팀원 공유를 할 수 있어요.' : item.can_claim ? '맥락과 자료를 확인한 뒤 ‘이어서 맡기’를 눌러 주세요.' : item.can_edit ? '달라진 진행 상황과 다음 행동을 갱신하고 저장해 주세요.' : '저장된 맥락과 자료를 확인할 수 있어요.'}</p>
            {item && <span className={`handoff-status handoff-status-${item.status}`}>{HANDOFF_STATUS[item.status]}</span>}</div>
          {item && <p className="ws-help">작성자 {item.owner} · 받는 팀원 {item.recipient || '아직 지정 안 함'} · 현재 {item.revision}번째 저장 버전</p>}
          {snapshot ? <div className="handoff-snapshot" role="status"><strong>{snapshot.revision}번째 이전 기록을 보고 있어요 · 읽기 전용</strong>
            <p>{HANDOFF_STATUS[snapshot.status]} · 당시 받는 팀원 {snapshot.recipient || '지정 전'}</p>
            <button className="prompt-reset-button" type="button" disabled={Boolean(busy)} onClick={() => setSnapshot(null)}>현재 작업으로 돌아가기</button></div> : item && <>
            {!item.can_edit && <p className="ws-help">{item.can_claim ? '내용을 확인하고 ‘이어서 맡기’를 누르면 편집할 수 있어요.' : '현재는 읽기 전용입니다. 다음 담당자의 진행 내용은 이전 기록과 함께 확인할 수 있어요.'}</p>}
            <div className="prompt-actions">
              {item.can_claim && <button className="prompt-copy-button" type="button" disabled={Boolean(busy)} onClick={() => mutate('claim')}>이어서 맡기</button>}
              {item.can_complete && <button className="prompt-reset-button" type="button" disabled={Boolean(busy) || dirty} onClick={() => mutate('complete')}>작업 완료로 표시</button>}
              {item.can_reopen && <button className="prompt-reset-button" type="button" disabled={Boolean(busy)} onClick={() => mutate('reopen')}>다시 진행하기</button>}
            </div>
          </>}
          <HandoffFields form={snapshot ? handoffForm(displayed) : form} readOnly={Boolean(snapshot || (item && !item.can_edit))}
            busy={Boolean(busy)} existing={Boolean(item)} changed={contentDirty} onSave={save} onChange={(key, value) => { setForm((current) => ({ ...current, [key]: value })); setCopied(''); }} />
          {!snapshot && <p className="ws-help" role="status">{!item ? '아직 저장하지 않은 새 작업입니다.' : dirty ? '작성 중 · 아직 저장하지 않은 내용이 있어요. 공유·완료 전에 저장해 주세요.' : '저장된 내용입니다.'}</p>}
          <HandoffAttachments key={`${item?.id || 'new'}-${displayed?.revision || 0}-${Boolean(snapshot)}`} item={displayed} saved={Boolean(item)} canEdit={Boolean(item?.can_edit && !snapshot)}
            busy={Boolean(busy)} contentDirty={contentDirty} file={file} onSelect={setFile} onAttach={() => mutate('attach')} onDetach={(fileId) => mutate('detach', { fileId })} />
          {item?.can_share && !snapshot && <form className="handoff-share" onSubmit={(e) => { e.preventDefault(); mutate('share', { username: recipient }); }}>
            <h4>저장한 내용을 받을 팀원에게 공유</h4>
            <label className="task-input-label" htmlFor="handoff-recipient">받을 팀원 아이디</label>
            <input id="handoff-recipient" className="ws-input" maxLength={30} disabled={Boolean(busy)} value={recipient} onChange={(e) => setRecipient(e.target.value)} placeholder="같은 서비스에 가입한 팀원 아이디" />
            <p className="ws-help">아래 버튼을 누르면 작업 내용과 프롬프트를 해당 계정에서 볼 수 있어요. 이어받기 전에는 대상을 바꿀 수 있고, 이전 대상은 더 이상 열 수 없습니다.</p>
            <button className="prompt-copy-button" type="submit" disabled={Boolean(busy) || dirty || !recipient.trim()}>이 팀원에게 공유</button>
          </form>}
          {item?.recipient && !snapshot && <div className="handoff-link">
            <label className="task-input-label" htmlFor="handoff-share-link">팀원에게 전달할 링크</label>
            <input id="handoff-share-link" className="ws-input" readOnly value={handoffLink(item.id, window.location.href)} />
            <button className="prompt-reset-button" type="button" onClick={() => copy('link', handoffLink(item.id, window.location.href))}>{copied === 'link' ? '링크를 복사했어요' : '인수인계 링크 복사'}</button>
            <p className="ws-help">링크만으로 접근 권한이 생기지 않습니다. 작성자와 지정된 받는 계정만 열 수 있어요. localhost 링크는 다른 컴퓨터에서 접속할 수 없으므로 서비스 접속 주소를 확인하세요.</p>
          </div>}
          {displayed?.body.references.length > 0 && <div className="handoff-references"><h4>참고 자료 바로 확인</h4><ul>{displayed.body.references.map((ref) => <li key={ref}>
            {/^https?:\/\//i.test(ref) ? <a href={ref} target="_blank" rel="noreferrer">{ref}</a> : <code>{ref}</code>}</li>)}</ul></div>}
          {item && <>
            <details className="ws-raw"><summary>AI에 붙여 넣어 이어갈 요청문</summary><textarea className="task-input" aria-label="이어서 작업할 요청문" rows={10} readOnly value={requestText} /></details>
            <button className="prompt-reset-button" type="button" disabled={dirty && !snapshot} onClick={() => copy('request', requestText)}>{copied === 'request' ? '이어서 할 요청문을 복사했어요' : '맥락 + 프롬프트 복사'}</button>
            <p className="ws-help">{snapshot ? '지금 보고 있는 이전 기록으로 복사합니다.' : '마지막 저장 내용을 기준으로 복사합니다.'} AI 실행이나 파일 열기는 자동으로 하지 않습니다.</p>
            <div className="handoff-history"><button className="prompt-reset-button" type="button" disabled={Boolean(busy)} onClick={() => loadHistory()}>이전 기록 확인</button>
              {history && <ol>{history.map((version) => <li key={version.revision}><span>{version.revision}번째 · {HANDOFF_EVENTS[version.event]} · {version.actor || '삭제된 계정'} · {new Date(version.saved_at).toLocaleString('ko-KR')}</span>
                <button className="ws-small-button" type="button" disabled={Boolean(busy)} onClick={() => loadHistory(version.revision)}>{version.revision}번째 기록 보기</button></li>)}</ol>}
            </div>
          </>}
        </div>}
      </>}
      {error && <p className="ws-error" role="alert">{error}</p>}
      {notice && <p className="ws-help" role="status">{notice}</p>}
    </div>
  </section>;
}

export default HandoffsSection;

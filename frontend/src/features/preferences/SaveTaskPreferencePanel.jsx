import { useState } from 'react';
import { saveTaskPreference } from './preferencesApi';

function SaveTaskPreferencePanel({ item, comparison, draft, disabled, onBusy, onSaved, onOpen }) {
  const [title, setTitle] = useState(`${item.title} · 작업용`.slice(0, 100));
  const [note, setNote] = useState('');
  const [saved, setSaved] = useState(null);
  const [error, setError] = useState('');
  const unchanged = saved?.title === title.trim() && saved?.note === note.trim();
  const save = async (event) => {
    event.preventDefault(); setError(''); onBusy('save-task');
    try {
      const next = await saveTaskPreference(item, comparison, draft, title.trim(), note.trim());
      setSaved(next); onSaved(next);
    } catch (e) { setError(e.message); }
    finally { onBusy(''); }
  };
  return <div className="preference-save ws-step">
    <h4>조합한 방식을 다음에도 쓰고 싶나요?</h4>
    <p className="ws-help">이름을 붙여 내 보관함에 새 항목으로 저장하세요. 기존 개인 지침과 팀 기준은 그대로입니다. 이번 작업 입력과 실행 결과는 저장하지 않습니다.</p>
    <form onSubmit={save}>
      <label className="task-input-label" htmlFor="save-task-preference-title">작업용 지침 이름</label>
      <input id="save-task-preference-title" className="ws-input" value={title} maxLength={100} required disabled={disabled}
        placeholder="예: 팀 코드 구성 + 내 타입 작성" onChange={(e) => setTitle(e.target.value)} />
      <label className="task-input-label" htmlFor="save-task-preference-note">언제 쓸지 설명 (선택)</label>
      <input id="save-task-preference-note" className="ws-input" value={note} maxLength={1000} disabled={disabled}
        placeholder="예: 팀 프로젝트에서 새 React 화면을 만들 때" onChange={(e) => setNote(e.target.value)} />
      <div className="prompt-actions">
        <button className="prompt-copy-button" type="submit" disabled={disabled || !title.trim() || unchanged}>
          {unchanged ? '새 항목으로 저장했어요' : '작업용 지침을 새 항목으로 저장'}
        </button>
        {saved && <button className="prompt-reset-button" type="button" disabled={disabled} onClick={() => onOpen(saved.id)}>저장한 작업용 열기</button>}
      </div>
    </form>
    {unchanged && <p className="ws-help" role="status">‘{saved.title}’ 저장 완료 · 다음에는 보관함에서 ‘새 작업에 사용’을 누르세요. 팀에 다시 연결하지 않아도 저장한 지침 그대로 쓸 수 있어요.</p>}
    {error && <p className="ws-error" role="alert">{error}</p>}
  </div>;
}

export default SaveTaskPreferencePanel;

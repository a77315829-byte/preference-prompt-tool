import { useEffect, useState } from 'react';
import { axisValueLabel } from '../../shared/domainLabels';
import { previewComparedRestore, saveComparedRestore } from './preferencesApi';

function RestoreComparedPreferencePanel({ item, selectedAxes, disabled, onBusy, onSaved, onOpen }) {
  const [title, setTitle] = useState(`${item.title.slice(0, 80)} · 일부 되돌리기`);
  const [note, setNote] = useState('');
  const [preview, setPreview] = useState(null);
  const [saved, setSaved] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => { setPreview(null); setSaved(null); setError(''); }, [selectedAxes]);
  const selection = JSON.stringify([...selectedAxes].sort());
  const draft = preview?.selection === selection ? preview.draft : null;
  const currentSaved = saved?.selection === selection ? saved.item : null;
  const unchanged = currentSaved?.title === title.trim() && currentSaved?.note === note.trim();
  const sameTitle = title.trim() === item.title;
  const makePreview = async () => {
    onBusy('restore-preview'); setError(''); setPreview(null); setSaved(null);
    try { setPreview({ selection, draft: await previewComparedRestore(item, selectedAxes) }); }
    catch (e) { setError(e.message); }
    finally { onBusy(''); }
  };
  const save = async (event) => {
    event.preventDefault(); onBusy('restore-save'); setError('');
    try {
      const next = await saveComparedRestore(item, draft, title.trim(), note.trim());
      setSaved({ selection, item: next }); onSaved(next);
    } catch (e) { setError(e.message); }
    finally { onBusy(''); }
  };
  return <div className="restore-compared-preference">
    <h4>고른 항목만 이전 방식으로 되돌려 새로 저장</h4>
    <p className="ws-help">비교 표에서 되돌릴 항목을 고르세요. 선택하지 않은 항목은 현재 방식을 유지합니다. 체크하거나 미리 보기를 눌러도 기존 조합은 바뀌지 않습니다.</p>
    <p className="ws-help" role="status">되돌릴 항목 {selectedAxes.length}개 · 나머지는 현재 방식 유지</p>
    <button className="prompt-reset-button" type="button" disabled={disabled || selectedAxes.length === 0} onClick={makePreview}>되돌릴 결과 미리 보기</button>
    {!draft && selectedAxes.length > 0 && <p className="ws-help">선택을 바꾸면 미리 보기를 다시 확인한 뒤 저장하세요.</p>}
    {draft && <>
      <p className="ws-help"><strong>아래 항목을 이전 방식으로 저장합니다.</strong></p>
      <ul className="restore-result-list">{draft.provenance.axes.filter((a) => draft.restore_axes.includes(a.axis)).map((a) => <li key={a.axis}>
        <strong>{a.label}</strong>: {a.value ? axisValueLabel(a.axis, a.value) : '정하지 않음 · 지시 제외'}
        <span className={`preference-source preference-source--${a.source}`}>{a.source === 'personal' ? '내 선호' : a.source === 'team' ? '팀 기준' : '같은 기준'}</span>
      </li>)}</ul>
      <details className="ws-raw"><summary>새 항목에 저장할 전체 지침 보기</summary><pre className="prompt-box"><code>{draft.prompt}</code></pre></details>
      <form onSubmit={save}>
        <label className="task-input-label" htmlFor="restore-title">일부 되돌린 조합 이름</label>
        <input id="restore-title" className="ws-input" value={title} maxLength={100} required disabled={disabled} onChange={(e) => setTitle(e.target.value)} />
        {sameTitle && <p className="ws-help">기존 조합과 다른 이름을 붙여 주세요.</p>}
        <label className="task-input-label" htmlFor="restore-note">일부 되돌린 조합 설명 (선택)</label>
        <input id="restore-note" className="ws-input" value={note} maxLength={1000} disabled={disabled} onChange={(e) => setNote(e.target.value)} />
        <div className="prompt-actions">
          <button className="prompt-copy-button" type="submit" disabled={disabled || !title.trim() || sameTitle || unchanged}>
            {unchanged ? '되돌린 결과를 새로 저장했어요' : '되돌린 결과를 다른 이름으로 저장'}
          </button>
          {currentSaved && <button className="prompt-reset-button" type="button" disabled={disabled} onClick={() => onOpen(currentSaved.id)}>저장한 되돌리기 결과 열기</button>}
        </div>
      </form>
      {unchanged && <p className="ws-help" role="status">‘{currentSaved.title}’을 새 항목으로 저장했어요. 기존 ‘{item.title}’은 그대로입니다.</p>}
    </>}
    {error && <p className="ws-error" role="alert">{error}</p>}
  </div>;
}

export default RestoreComparedPreferencePanel;

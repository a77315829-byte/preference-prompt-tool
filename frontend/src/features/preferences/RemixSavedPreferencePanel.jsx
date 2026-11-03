import { useState } from 'react';
import { axisValueLabel } from '../../shared/domainLabels';
import { previewSavedRemix, saveSavedRemix } from './preferencesApi';
import SavedRemixComparison from './SavedRemixComparison';

function RemixSavedPreferencePanel({ item, disabled, onBusy, onSaved, onOpen }) {
  const [open, setOpen] = useState(false);
  const [choices, setChoices] = useState(() => Object.fromEntries(item.provenance.axes
    .filter((a) => a.personal_value !== a.team_value).map((a) => [a.axis, a.source])));
  const [title, setTitle] = useState(`${item.title.slice(0, 85)} · 다른 조합`);
  const [note, setNote] = useState('');
  const [draft, setDraft] = useState(null);
  const [saved, setSaved] = useState(null);
  const [error, setError] = useState('');
  const unchanged = saved?.title === title.trim() && saved?.note === note.trim();
  const sameTitle = title.trim() === item.title;
  const valueLabel = (axis, value) => value ? axisValueLabel(axis, value) : '정하지 않음 (해당 지시 제외)';
  const choose = (axis, source) => {
    setChoices((current) => ({ ...current, [axis]: source })); setDraft(null); setSaved(null); setError('');
  };
  const preview = async () => {
    onBusy('remix-preview'); setError(''); setDraft(null); setSaved(null);
    try { setDraft(await previewSavedRemix(item, choices)); }
    catch (e) { setError(e.message); }
    finally { onBusy(''); }
  };
  const save = async (event) => {
    event.preventDefault(); onBusy('remix-save'); setError('');
    try {
      const next = await saveSavedRemix(item, draft, title.trim(), note.trim());
      setSaved(next); onSaved(next);
    } catch (e) { setError(e.message); }
    finally { onBusy(''); }
  };
  return <div className="task-preference-mixer saved-preference-remix">
    <button className="prompt-reset-button" type="button" aria-expanded={open} disabled={disabled || !item.provenance_matches}
      onClick={() => setOpen((current) => !current)}>선택 바꿔 새 항목으로 저장</button>
    {!item.provenance_matches && <p className="ws-help">지침 본문·종류가 저장 당시 기록과 달라 다시 조합할 수 없어요. 팀과 비교해 새로 조합해 주세요.</p>}
    {open && <>
      <h4>저장한 선택을 바꿔 다른 버전 만들기</h4>
      <p className="ws-help">저장 당시의 내 선호와 팀 기준을 사용하며 기존 선택을 미리 표시했어요. 이 작업용과 원본 개인 지침·팀 기준은 그대로 유지합니다. 새 항목을 저장해 열면 바꾼 방식으로 새 작업을 할 수 있어요.</p>
      {item.provenance.axes.map((a) => a.personal_value === a.team_value
        ? <p key={a.axis} className="ws-help"><strong>{a.label}</strong> · 같은 기준: {valueLabel(a.axis, a.value)}</p>
        : <fieldset key={a.axis} disabled={disabled} className="preference-axis-choice">
          <legend>{a.label}</legend>
          {['personal', 'team'].map((source) => <label key={source}>
            <input type="radio" name={`remix-choice-${a.axis}`} value={source} checked={choices[a.axis] === source}
              onChange={() => choose(a.axis, source)} />
            {source === 'personal' ? '저장 당시 내 선호' : '저장 당시 팀 기준'}: {valueLabel(a.axis, a[`${source}_value`])}
          </label>)}
          {!a.team_agreed && <p className="ws-help">저장 당시 팀의 합의가 끝나지 않았던 항목입니다.</p>}
        </fieldset>)}
      <button className="prompt-reset-button" type="button" disabled={disabled} onClick={preview}>새 조합 미리 보기</button>
      {!draft && <p className="ws-help" role="status">선택을 확인하고 미리 보기를 눌러 주세요. 선택을 바꾸면 다시 확인해야 저장할 수 있습니다.</p>}
      {draft && <>
        <SavedRemixComparison before={draft.provenance.remixed_from} afterAxes={draft.provenance.axes} afterTitle={title} preview />
        <label className="task-input-label" htmlFor="remix-prompt-preview">새 항목에 저장할 지침 미리 보기</label>
        <textarea id="remix-prompt-preview" className="task-input" readOnly rows={8} value={draft.prompt} />
        <form onSubmit={save}>
          <label className="task-input-label" htmlFor="remix-title">새 조합 이름</label>
          <input id="remix-title" className="ws-input" value={title} maxLength={100} required disabled={disabled} onChange={(e) => setTitle(e.target.value)} />
          {sameTitle && <p className="ws-help">기존 작업용과 다른 이름을 붙여 주세요.</p>}
          <label className="task-input-label" htmlFor="remix-note">새 조합 설명 (선택)</label>
          <input id="remix-note" className="ws-input" value={note} maxLength={1000} disabled={disabled} onChange={(e) => setNote(e.target.value)} />
          <div className="prompt-actions">
            <button className="prompt-copy-button" type="submit" disabled={disabled || !title.trim() || sameTitle || unchanged}>
              {unchanged ? '새 조합을 저장했어요' : '다른 이름으로 새 조합 저장'}
            </button>
            {saved && <button className="prompt-reset-button" type="button" disabled={disabled} onClick={() => onOpen(saved.id)}>저장한 새 조합 열기</button>}
          </div>
        </form>
        {unchanged && <p className="ws-help" role="status">‘{saved.title}’을 새 항목으로 저장했어요. 기존 ‘{item.title}’은 그대로입니다.</p>}
      </>}
    </>}
    {error && <p className="ws-error" role="alert">{error}</p>}
  </div>;
}

export default RemixSavedPreferencePanel;

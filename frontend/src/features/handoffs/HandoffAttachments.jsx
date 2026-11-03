import { handoffFileUrl } from './handoffApi';

const sizeLabel = (size) => size >= 1024 * 1024 ? `${(size / 1024 / 1024).toFixed(1)}MB` : `${Math.max(1, Math.ceil(size / 1024))}KB`;

function HandoffAttachments({ item, saved, canEdit, busy, contentDirty, file, onSelect, onAttach, onDetach }) {
  const attachments = item?.body.attachments || [];
  const validFile = file && file.size > 0 && file.size <= 5 * 1024 * 1024;
  return <div className="handoff-attachments">
    <h4>참고 파일 첨부</h4>
    <p className="ws-help">저장한 파일은 작성자와 지정된 팀원이 열거나 내려받을 수 있어요. 하나당 5MB, 현재 최대 10개이며 이전 기록을 포함해 작업당 20MB까지입니다.</p>
    {!saved ? <p className="ws-help">먼저 ‘내 작업으로 저장’을 누르면 파일을 첨부할 수 있어요.</p> : <>
      {attachments.length ? <ul>{attachments.map((entry) => <li key={entry.id}>
        <div><strong>{entry.name}</strong><span className="ws-help"> · {sizeLabel(entry.size)}</span></div>
        <div className="prompt-actions">
          {entry.content_type !== 'application/octet-stream' && <a className="ws-small-button" href={handoffFileUrl(item.id, entry.id, item.revision, true)} target="_blank" rel="noreferrer">열기<span className="sr-only">: {entry.name} (새 탭)</span></a>}
          <a className="ws-small-button" href={handoffFileUrl(item.id, entry.id, item.revision)} download={entry.name}>내려받기<span className="sr-only">: {entry.name}</span></a>
          {canEdit && <button className="ws-small-button" type="button" disabled={busy || contentDirty || Boolean(file)} onClick={() => onDetach(entry.id)}>현재 첨부에서 빼기<span className="sr-only">: {entry.name}</span></button>}
        </div>
      </li>)}</ul> : <p className="ws-help">이 기록에 첨부한 파일이 없어요.</p>}
      {canEdit && <div className="handoff-upload">
        <label className="task-input-label" htmlFor="handoff-file">첨부할 파일 선택</label>
        <input id="handoff-file" type="file" disabled={busy || attachments.length >= 10} onChange={(e) => onSelect(e.target.files?.[0] || null)} />
        {file && <p className={validFile ? 'ws-help' : 'ws-error'} role="status">{file.name} · {sizeLabel(file.size)}{validFile ? ' · 아직 저장하지 않았어요.' : ' · 빈 파일 또는 5MB를 넘는 파일은 첨부할 수 없어요.'}</p>}
        <div className="prompt-actions"><button className="prompt-copy-button" type="button" disabled={busy || contentDirty || !validFile} onClick={onAttach}>{busy ? '처리하는 중…' : '첨부 파일 저장'}</button>
          {file && <button className="prompt-reset-button" type="button" disabled={busy} onClick={() => { onSelect(null); const input = document.getElementById('handoff-file'); if (input) input.value = ''; }}>선택 취소</button>}</div>
        <p className="ws-help">{contentDirty ? '작성 중인 내용을 먼저 저장한 뒤 파일을 첨부해 주세요.' : '파일을 선택하고 ‘첨부 파일 저장’을 누르면 현재 작업에 바로 저장돼요.'} 파일을 빼도 이전 기록의 첨부본은 보존됩니다. PDF·이미지·UTF-8 텍스트는 새 탭에서 열고, 다른 형식은 내려받아 확인하세요.</p>
      </div>}
    </>}
  </div>;
}

export default HandoffAttachments;

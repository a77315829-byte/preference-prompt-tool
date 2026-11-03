const FIELDS = [
  ['purpose', '작업 목적', 3000, 3, '왜 하는 작업인지, 어떤 결과가 필요한지 적어 주세요.'],
  ['progress', '어디까지 했나요?', 6000, 4, '완료한 부분과 현재 동작하는 상태를 적어 주세요.'],
  ['remaining', '남은 일과 다음 행동', 6000, 4, '다음 사람이 먼저 할 일, 확인할 문제를 적어 주세요. 없으면 없다고 적습니다.'],
  ['references', '참고 파일 경로·링크', 41000, 3, '한 줄에 하나씩: src/api.py 또는 https://…'],
  ['prompt', '사용한 프롬프트 (선택)', 20000, 7, '작업할 때 사용한 지침을 붙여 넣으세요. 보관함에서도 가져올 수 있어요.'],
];

function HandoffFields({ form, readOnly, busy, onChange, onSave, existing, changed = true }) {
  return <form className="handoff-fields" onSubmit={onSave}>
    <label className="task-input-label" htmlFor="handoff-title">작업 이름</label>
    <input id="handoff-title" className="ws-input" required maxLength={100} readOnly={readOnly} disabled={busy} value={form.title} onChange={(e) => onChange('title', e.target.value)} placeholder="예: 로그인 API 구현 이어받기" />
    {FIELDS.map(([key, label, limit, rows, placeholder]) => <div key={key}>
      <label className="task-input-label" htmlFor={`handoff-${key}`}>{label}</label>
      <textarea id={`handoff-${key}`} className="task-input" maxLength={limit} rows={rows} required={['purpose', 'progress', 'remaining'].includes(key)}
        readOnly={readOnly} disabled={busy} value={form[key]} onChange={(e) => onChange(key, e.target.value)} placeholder={placeholder} />
      {key === 'references' && <p className="ws-help">팀원이 접근할 수 있는 저장소 경로·공유 링크를 적어 주세요. 최대 20개입니다. 파일 자체는 작업을 저장한 뒤 ‘참고 파일 첨부’에서 추가할 수 있어요.</p>}
    </div>)}
    {!readOnly && <div className="prompt-actions"><button className="prompt-copy-button" type="submit" disabled={busy || !changed || !form.title.trim() || !form.purpose.trim() || !form.progress.trim() || !form.remaining.trim()}>
      {busy ? '처리하는 중…' : existing ? '변경 내용 저장' : '내 작업으로 저장'}
    </button></div>}
  </form>;
}

export default HandoffFields;

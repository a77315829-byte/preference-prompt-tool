import { LINEAGE_LABELS, lineageGroups, lineageOf } from './lineageModel';

export function PreviousPreference({ item, items, disabled, onOpen }) {
  const parent = lineageOf(item).parent;
  if (!parent) return null;
  const live = parent.id !== item.id && items.find((i) => i.id === parent.id);
  return <div className="previous-preference">
    <p className="ws-help">이전 작업용: {parent.title} · 당시 {parent.revision}번째 저장 버전</p>
    {live ? <>
      <button className="prompt-reset-button" type="button" disabled={disabled} onClick={() => onOpen(live.id, parent.revision)}>이전 작업용 바로 열기</button>
      {live.revision !== parent.revision && <p className="ws-help">이전 항목이 이후 수정되었습니다. 열면 현재 {live.revision}번째 버전을 봅니다. 저장 당시 비교 기록은 그대로입니다.</p>}
    </> : <p className="ws-help">{parent.id ? '이전 항목이 삭제되었거나 현재 계정에서 열 수 없어요. 저장 당시 비교 기록은 남아 있습니다.' : '이전 항목의 연결 기록이 없어 바로 열 수 없어요. 이름만으로 연결을 추측하지 않습니다.'}</p>}
  </div>;
}

function PreferenceLineage({ items, visibleIds, activeId, disabled, onOpen }) {
  return <div className="preference-lineage">
    <h3>작업용이 이어진 흐름</h3>
    <p className="ws-help">들여쓰기와 ‘이전’ 이름으로 어떤 작업용에서 만들어졌는지 확인하세요. 검색 결과와 이어진 조합도 함께 표시합니다. 항목을 누르면 열 수 있어요.</p>
    {lineageGroups(items, visibleIds).map((rows) => <ol key={rows[0].item.id} className="preference-lineage-group">
      {rows.map(({ item, depth }) => {
        const link = lineageOf(item);
        const parent = link.parent;
        const unavailable = parent && (!parent.id || !items.some((i) => i.id === parent.id) || parent.id === item.id);
        return <li key={item.id} style={{ marginLeft: `${Math.min(depth, 5) * 0.75}rem` }} aria-current={item.id === activeId ? 'true' : undefined}>
          <span className="ws-help">{depth > 0 ? '↳ ' : ''}{LINEAGE_LABELS[link.kind] || '저장한 지침'} · {item.revision}번째 버전</span>
          <button className="lineage-open" type="button" disabled={disabled || item.id === activeId} onClick={() => onOpen(item.id)}>{item.title}{item.id === activeId ? ' · 지금 보고 있어요' : ''}</button>
          {parent && !unavailable && <span className="ws-help">이전: {items.find((i) => i.id === parent.id)?.title}</span>}
          {unavailable && <span className="ws-help">{parent.id ? '이전 항목 열 수 없음' : '이전 연결 기록 없음'} · {parent.title}</span>}
        </li>;
      })}
    </ol>)}
  </div>;
}

export default PreferenceLineage;

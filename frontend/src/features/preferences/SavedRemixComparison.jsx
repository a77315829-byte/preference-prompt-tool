import { useState } from 'react';
import { axisValueLabel } from '../../shared/domainLabels';
import { compareRemixAxes } from './remixComparison';

const SOURCES = { personal: '내 선호', team: '팀 기준', shared: '같은 기준' };
const STATUS = { changed: '방식 변경', source: '출처만 변경', same: '같음', unknown: '확인 필요' };

function SavedRemixComparison({ before, afterAxes, afterTitle, matches = true, preview = false }) {
  const [showAll, setShowAll] = useState(false);
  if (!before) return null;
  if (!Array.isArray(before.axes)) return <p className="ws-help">이 저장본에는 바꾸기 전 항목 기록이 없어 전·후를 비교할 수 없어요. 다음에 선택을 바꿔 새 항목으로 저장하면 비교 기록도 함께 남습니다.</p>;
  const rows = compareRemixAxes(before.axes, afterAxes);
  const changed = rows.filter((r) => r.status === 'changed' || r.status === 'source').length;
  const same = rows.filter((r) => r.status === 'same').length;
  const unknown = rows.filter((r) => r.status === 'unknown').length;
  const shown = showAll ? rows : rows.filter((r) => r.status !== 'same');
  const cell = (axis, entry) => !entry || typeof entry.value !== 'string' ? '기록 없음' : <>
    <span className="remix-value">{entry.value ? axisValueLabel(axis, entry.value) : '정하지 않음 · 지시 제외'}</span>
    <span className={`preference-source preference-source--${entry.source}`}>{SOURCES[entry.source] || '출처 확인 필요'}</span>
  </>;
  return <div className="saved-remix-comparison" aria-label={preview ? '새 조합 미리 보기의 항목별 변경 비교' : '저장된 조합의 항목별 변경 비교'}>
    <h4>{preview ? '새 조합은 어떤 항목이 바뀌나요?' : '기존 작업용에서 무엇이 달라졌나요?'}</h4>
    <p className="ws-help">바꾸기 전: ‘{before.title}’의 {before.revision}번째 저장 버전 → 바꾼 후: ‘{afterTitle || '새 조합'}’</p>
    <p className="ws-help">선택을 바꿔 저장할 때의 항목 기록을 비교합니다. 기존 작업용은 그대로 유지합니다.</p>
    {!matches && <p className="comparison-pending" role="status">지침 본문·종류가 수정되어 아래 비교는 현재 내용과 다를 수 있어요. 처음 새 조합으로 저장한 당시의 기록입니다.</p>}
    <p className="remix-change-summary" role="status">전체 {rows.length}개 중 <strong>{changed}개 변경</strong> · {same}개 같음{unknown > 0 && ` · ${unknown}개 확인 필요`}</p>
    <button className="prompt-reset-button" type="button" aria-pressed={showAll} onClick={() => setShowAll((value) => !value)}>
      {showAll ? '바뀐 항목만 보기' : '전체 항목 보기'}
    </button>
    {shown.length === 0 ? <p className="ws-help">바뀐 항목이 없어요. 사용한 방식과 선택 출처가 모두 같습니다.</p> : <div className="preference-comparison-table"><table>
      <caption>{showAll ? '전체 항목의 바꾸기 전·후' : '바뀐 항목의 바꾸기 전·후'}</caption>
      <thead><tr><th scope="col">항목</th><th scope="col">바꾸기 전</th><th scope="col">바꾼 후</th></tr></thead>
      <tbody>{shown.map((r) => <tr key={r.axis} className={r.status === 'same' ? '' : 'is-different'}>
        <th scope="row">{r.label}<span className="remix-row-status">{STATUS[r.status]}</span></th>
        <td>{cell(r.axis, r.before)}</td><td>{cell(r.axis, r.after)}</td>
      </tr>)}</tbody>
    </table></div>}
  </div>;
}

export default SavedRemixComparison;

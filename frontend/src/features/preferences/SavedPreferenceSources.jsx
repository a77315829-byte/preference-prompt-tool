import { axisValueLabel } from '../../shared/domainLabels';

const SOURCE_LABELS = { personal: '내 선호', team: '팀 기준', shared: '같은 기준' };
const valueLabel = (axis, value) => value ? axisValueLabel(axis, value) : '정하지 않음 · 해당 지시 제외';

function SavedPreferenceSources({ item, editingPrompt = false }) {
  const origin = item.provenance;
  if (!origin) return <details className="ws-raw">
    <summary>항목별 선택 출처 안내</summary>
    <p className="ws-help">이 지침에는 항목별 선택 출처 기록이 없어요. 기록 기능이 생기기 전에 저장했거나 직접 추가한 지침은 본문만 보고 출처를 추측하지 않습니다. 팀과 항목별로 다시 조합해 새 항목으로 저장하면 선택 출처도 함께 남습니다.</p>
  </details>;
  return <div className="saved-preference-sources">
    <h4>이 지침의 항목별 선택 출처</h4>
    <p className="ws-help">저장 당시의 선택입니다. 내 선호는 ‘{origin.personal.title}’의 {origin.personal.revision}번째 저장 버전, 팀 기준은 ‘{origin.team.name}’에서 가져왔어요. 이후 원본이나 팀 기준이 바뀌어도 이 기록은 그대로입니다.</p>
    {(editingPrompt || !item.provenance_matches) && <p className="comparison-pending" role="status">
      {editingPrompt ? '지침 본문·종류를 수정 중입니다. 아래는 수정 전 저장 당시의 기록입니다.'
        : '저장 후 지침 본문·종류가 수정되었습니다. 아래는 처음 조합해 저장한 기록이며 현재 지침과 다를 수 있어요.'}
    </p>}
    <p className="preference-source-counts">{Object.entries(SOURCE_LABELS).map(([source, label]) => {
      const count = origin.axes.filter((a) => a.source === source).length;
      return count > 0 && <span key={source} className={`preference-source preference-source--${source}`}>{label} {count}개</span>;
    })}</p>
    <div className="preference-comparison-table"><table>
      <caption>저장 당시 항목별 선택 출처</caption>
      <thead><tr><th scope="col">항목</th><th scope="col">사용한 방식</th><th scope="col">선택 출처</th></tr></thead>
      <tbody>{origin.axes.map((a) => <tr key={a.axis}>
        <th scope="row">{a.label}</th><td>{valueLabel(a.axis, a.value)}</td>
        <td><span className={`preference-source preference-source--${a.source}`}>{SOURCE_LABELS[a.source]}</span>
          {a.source === 'shared' && <span className="ws-help"> · 개인·팀이 같았어요</span>}
          {a.source === 'team' && !a.team_agreed && <span className="comparison-pending">저장 당시 팀 합의 전</span>}</td>
      </tr>)}</tbody>
    </table></div>
  </div>;
}

export default SavedPreferenceSources;

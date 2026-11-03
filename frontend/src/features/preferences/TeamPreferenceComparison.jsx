import { useEffect, useRef, useState } from 'react';
import { axisValueLabel } from '../../shared/domainLabels';
import { fetchMyTeams, parseTeamInvite, readRecentTeams } from '../../shared/teams';
import { comparePreferenceTeam } from './preferencesApi';
import { promptChanges } from './comparisonText';

function TeamPreferenceComparison({ item, disabled, onChange }) {
  const [teams, setTeams] = useState([]);
  const [invite, setInvite] = useState('');
  const [language, setLanguage] = useState('');
  const [comparison, setComparison] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const request = useRef(0);

  useEffect(() => {
    let cancelled = false;
    setComparison(null); setError(''); setBusy(false); onChange(null);
    const recent = readRecentTeams();
    const adopt = (mine) => {
      if (cancelled) return;
      const unique = new Map([...recent, ...mine].filter((t) => t.domain_key === item.domain_key).map((t) => [t.code, t]));
      setTeams([...unique.values()]);
    };
    fetchMyTeams().then(adopt).catch(() => adopt([]));
    return () => { cancelled = true; request.current += 1; };
  }, [item.id, item.revision, item.domain_key, onChange]);

  const compare = async (event) => {
    event.preventDefault();
    const token = ++request.current;
    setBusy(true); setError(''); setComparison(null); onChange(null);
    try {
      const code = parseTeamInvite(invite);
      const next = await comparePreferenceTeam(item.id, item.revision, code, language);
      if (token === request.current) { setComparison(next); onChange(next); }
    } catch (e) { if (token === request.current) setError(e.message); }
    finally { if (token === request.current) setBusy(false); }
  };
  const editSelection = (value) => {
    request.current += 1; setBusy(false); setInvite(value); setComparison(null); setError(''); onChange(null);
  };
  const changes = comparison ? promptChanges(item.prompt, comparison.comparison_prompt) : [];
  const different = comparison?.axes.filter((a) => a.status === 'different').length || 0;

  return (
    <div className="preference-team-comparison">
      <h4>팀 기준과 무엇이 다를까요?</h4>
      <p className="ws-help">같은 종류의 팀을 골라 확인하세요. 비교하거나 이번 작업에 팀용을 선택해도 내 지침과 팀 기준은 바뀌지 않습니다.</p>
      <form onSubmit={compare}>
        {teams.length > 0 && <>
          <label className="task-input-label" htmlFor="preference-team-list">내 팀·최근 본 팀 중에서 고르기</label>
          <select id="preference-team-list" className="ws-input" value={teams.some((t) => t.code === invite) ? invite : ''} disabled={disabled || busy}
            onChange={(e) => editSelection(e.target.value)}>
            <option value="">팀을 선택하세요</option>
            {teams.map((t) => <option key={t.code} value={t.code}>{t.name || t.code}</option>)}
          </select>
        </>}
        <label className="task-input-label" htmlFor="preference-team-invite">또는 초대 링크·팀 코드 붙여넣기</label>
        <input id="preference-team-invite" className="ws-input" value={invite} maxLength={2048} disabled={disabled || busy} onChange={(e) => editSelection(e.target.value)} placeholder="같은 종류의 팀 초대를 넣어 주세요" />
        <details className="ws-raw"><summary>비교할 지침의 문구 언어 설정</summary>
          <p className="ws-help">문구의 언어를 맞추는 설정입니다. 한국어·영어 요약 작업의 종류는 바뀌지 않습니다.</p>
          <select className="ws-input" aria-label="팀 지침 문구 언어" value={language} disabled={disabled || busy} onChange={(e) => { setLanguage(e.target.value); setComparison(null); onChange(null); }}>
            <option value="">개인 기본 지침과 맞추기</option><option value="ko">한국어</option><option value="en">English</option>
          </select>
        </details>
        <div className="prompt-actions"><button className="prompt-reset-button" type="submit" disabled={disabled || busy || !invite.trim()}>
          {busy ? '비교하는 중…' : comparison ? '팀 기준 새로 확인' : '개인·팀 기준 비교하기'}
        </button></div>
      </form>
      {error && <p className="ws-error" role="alert">{error}</p>}
      {comparison && <>
        <p role="status"><strong>{comparison.team_name}</strong> · 선호를 합친 팀원 {comparison.team_members}명</p>
        <p className="ws-help">{comparison.personal_recognized
          ? `기본 지침에서 확인한 선호 중 ${different}개가 달라요. 미정 항목과 팀의 합의 상태도 확인하세요.`
          : '직접 수정·추가하거나 최적화한 지침은 선호 값을 확정하지 않습니다. 아래 본문 차이에서 내용을 확인해 주세요.'}</p>
        <div className="preference-comparison-table"><table>
          <caption>보관한 내 선호와 현재 팀 기준</caption>
          <thead><tr><th scope="col">비교 항목</th><th scope="col">개인용</th><th scope="col">팀용</th><th scope="col">차이</th></tr></thead>
          <tbody>{comparison.axes.map((a) => <tr key={a.axis} className={a.status === 'different' ? 'is-different' : ''}>
            <th scope="row">{a.label}</th>
            <td>{a.personal_value === null ? '본문 확인 필요' : a.personal_value ? axisValueLabel(a.axis, a.personal_value) : '정하지 않음'}</td>
            <td>{a.team_value ? axisValueLabel(a.axis, a.team_value) : '정하지 않음'}
              {!a.team_agreed && Object.keys(a.team_votes).length > 0 && <span className="comparison-pending">팀 합의 필요{a.team_value ? ' · 임시 기준' : ''}</span>}</td>
            <td>{{ same: '같음', different: '다름', unknown: '확인 필요', undecided: '미정 항목 있음' }[a.status]}</td>
          </tr>)}</tbody>
        </table></div>
        <details className="ws-raw" open={!comparison.personal_recognized || undefined}><summary>다른 본문 문장 보기 ({changes.length}곳)</summary>
          <p className="ws-help">이름은 비교하지 않고 개인·팀 대상 안내 문구는 맞춰 비교합니다. 아래는 문장 차이이며, 같은 뜻인지는 직접 확인해 주세요.</p>
          {changes.length === 0 ? <p>대상 안내 문구를 제외한 본문은 같아요.</p> : <ul className="preference-diff" tabIndex={0} aria-label="개인용과 팀용의 다른 문장">{changes.map((line, i) => (
            <li key={i} className={line.type}><strong>{line.type === 'removed' ? '개인용에 있는 문장' : '팀용에 있는 문장'}</strong><pre>{line.text}</pre></li>
          ))}</ul>}
        </details>
        <p className="ws-help">팀 기준은 확인한 시점의 내용입니다. 팀원 선호가 추가되면 ‘팀 기준 새로 확인’을 눌러 주세요.</p>
      </>}
    </div>
  );
}

export default TeamPreferenceComparison;

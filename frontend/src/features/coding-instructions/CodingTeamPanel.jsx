import { useEffect, useRef, useState } from 'react';
import TeamInvitation from '../../shared/components/TeamInvitation';
import { fetchMyTeams, fetchTeam, parseTeamInvite } from '../../shared/teams';
import { CODING_CHOICES } from './codingOptions';
import { codingWork, differentPreferences } from './workflowApi';

export default function CodingTeamPanel({ profile, user, onLogin, initialCode = '', onApply, onReset, onStart }) {
  const [code, setCode] = useState(initialCode);
  const [teams, setTeams] = useState([]);
  const [team, setTeam] = useState(null);
  const [name, setName] = useState('');
  const [rules, setRules] = useState('');
  const [teamPreferences, setTeamPreferences] = useState({});
  const [choices, setChoices] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const request = useRef(0);
  const adopt = next => {
    setTeam(next); setChoices({}); setRules((next.rules || []).join('\n'));
    setTeamPreferences(next.profile?.preferences || {}); onReset?.();
  };
  const refresh = () => fetchMyTeams().then(rows => setTeams(rows.filter(row => row.domain_key === 'coding_profile')));
  useEffect(() => { if (user) refresh().catch(e => setError(e.message)); }, [user?.id]);
  useEffect(() => () => { request.current += 1; }, []);
  const act = async work => {
    const token = ++request.current; setBusy(true); setError('');
    try { const next = await work(); if (token === request.current && next) adopt(next); }
    catch (e) { if (token === request.current) setError(e.message); }
    finally { if (token === request.current) setBusy(false); }
  };
  const open = value => act(async () => {
    const next = await fetchTeam(parseTeamInvite(value));
    if (next.domain_key !== 'coding_profile') throw new Error('이곳은 설명·주석·구성·출력 네 항목의 팀 기준입니다. 기존 React 비교 팀은 팀 메뉴에서 열어 주세요.');
    return next;
  });
  useEffect(() => { if (initialCode) { setCode(initialCode); open(initialCode); } }, [initialCode]);
  const ruleLines = () => rules.split('\n').map(line => line.trim()).filter(Boolean);
  const create = () => act(async () => {
    const next = (await codingWork('teams', { name, profile, rules: ruleLines() })).team;
    await refresh(); return next;
  });
  const join = () => act(async () => {
    const next = (await codingWork(`teams/${encodeURIComponent(team.code)}/join`, {})).team;
    await refresh(); return next;
  });
  const update = () => act(async () => (await codingWork(`teams/${encodeURIComponent(team.code)}/update`, {
    revision: team.revision, profile: { ...team.profile, preferences: teamPreferences }, rules: ruleLines(),
  })).team);
  const matches = profile && team?.profile && ['language', 'framework'].every(k => profile[k] === team.profile[k]);
  const differences = matches ? differentPreferences(profile, team.profile) : [];
  return <div className="coding-work-card">
    <h4>개인·팀 기준 연결</h4>
    <p>팀장이 정한 기본 설정과 내 선호를 비교합니다. 필수 규칙은 조합에 유지하며, 개인의 비교 기록과 추가 메모는 팀에 공개하지 않습니다.</p>
    {!user && <button type="button" className="coding-secondary-button" onClick={onLogin}>로그인하고 팀 기준 사용</button>}
    {user && <>
      <label>참여한 새 코딩 팀<select value={team?.code || ''} disabled={busy} onChange={e => { if (e.target.value) open(e.target.value); }}>
        <option value="">팀 선택</option>{teams.map(t => <option key={t.code} value={t.code}>{t.name}</option>)}
      </select></label>
      <label>초대 링크 또는 팀 코드<input value={code} onChange={e => setCode(e.target.value)} maxLength={2048} /></label>
      <button type="button" className="coding-secondary-button" disabled={busy || !code.trim()} onClick={() => open(code)}>팀 열기</button>
      {profile && !team && <details><summary>현재 네 가지 설정으로 팀 기준 만들기</summary>
        <p>개발 환경과 네 항목만 공유합니다. 자동 투표 결과가 아니라 팀장이 제안한 기본값이며 팀원과 검토해 주세요.</p>
        <label>팀 이름<input value={name} maxLength={60} onChange={e => setName(e.target.value)} /></label>
        <label>팀 필수 규칙 (한 줄에 하나, 최대 12개)<textarea value={rules} rows={4} maxLength={4800} onChange={e => setRules(e.target.value)} placeholder="예: 기존 공개 API의 요청·응답 형식을 유지한다." /></label>
        <button type="button" className="coding-primary-button" disabled={busy || !name.trim()} onClick={create}>팀 기준 만들기</button>
      </details>}
    </>}
    {team && <div className="coding-work-preview">
      <h4>{team.name}</h4>
      {team.requires_join ? <>
        <p>참여 전에는 팀 지침을 공개하지 않습니다. 참여해도 내 선호는 자동으로 공유되지 않아요.</p>
        <button type="button" className="coding-primary-button" disabled={busy || !team.invite_open} onClick={user ? join : onLogin}>{user ? '초대로 팀 참여' : '로그인하고 참여'}</button>
      </> : <>
        <p>{team.profile.language} · {team.profile.framework || '프레임워크 없음'} · 팀 기준 {team.revision}판</p>
        <p>팀원 {team.members.length}명 · 팀장이 설정한 기본값</p>
        <TeamInvitation key={team.code} team={team} onChange={adopt} />
        {team.rules.length > 0 ? <ul>{team.rules.map((rule, i) => <li key={i}>{rule}</li>)}</ul> : <p className="ws-help">아직 정한 필수 규칙이 없습니다.</p>}
        <p className="ws-help">규칙을 지침에 포함해도 준수를 보장하지는 않습니다. 실제 검사·리뷰로 확인하세요.</p>
        {team.can_manage && <details><summary>팀 기본값·필수 규칙 수정</summary>
          {Object.entries(CODING_CHOICES).map(([axis, options]) => <label key={axis}>{options.label}<select value={teamPreferences[axis] || ''}
            onChange={e => setTeamPreferences(current => ({ ...current, [axis]: e.target.value }))}>
            {Object.entries(options.options).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select></label>)}
          <label>팀 필수 규칙<textarea value={rules} rows={4} maxLength={4800} onChange={e => setRules(e.target.value)} /></label>
          <button type="button" className="coding-secondary-button" disabled={busy} onClick={update}>팀 기준 새 버전 저장</button>
        </details>}
        {profile && !matches && <p role="status">팀과 같은 언어·프레임워크로 개인 지침을 만든 뒤 비교해 주세요.</p>}
        {matches && <>
          <div className="coding-work-table"><table><thead><tr><th>항목</th><th>내 선호</th><th>팀 기준</th><th>이번 작업</th></tr></thead><tbody>
            {Object.entries(CODING_CHOICES).map(([axis, spec]) => <tr key={axis}><th>{spec.label}</th>
              <td>{spec.options[profile.preferences[axis]]}</td><td>{spec.options[team.profile.preferences[axis]]}</td>
              <td>{differences.includes(axis) ? <select aria-label={`${spec.label} 이번 작업 기준`} value={choices[axis] || ''}
                onChange={e => { setChoices(current => ({ ...current, [axis]: e.target.value })); onReset?.(); }}>
                <option value="">선택 필요</option><option value="personal">내 선호</option><option value="team">팀 기준</option>
              </select> : '동일'}</td></tr>)}
          </tbody></table></div>
          <button type="button" className="coding-primary-button" disabled={busy || differences.some(axis => !choices[axis])}
            onClick={() => act(async () => { await onApply?.({ code: team.code, revision: team.revision, choices }); })}>이번 작업용 지침 만들기</button>
        </>}
        {onStart && <button type="button" className="coding-primary-button" onClick={() => onStart(team.code, team.profile)}>내 코딩 선호를 만들고 이 팀과 비교</button>}
      </>}
      {profile && <button type="button" className="coding-text-button" onClick={() => { setTeam(null); setChoices({}); onReset?.(); }}>개인용으로 돌아가기·다른 팀 만들기</button>}
    </div>}
    {busy && <p role="status">팀 기준을 확인하고 있어요…</p>}
    {error && <p role="alert" className="ws-error">{error}</p>}
  </div>;
}

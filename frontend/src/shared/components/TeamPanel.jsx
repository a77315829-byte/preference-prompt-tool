import { useEffect, useState } from 'react';
import { fetchMe } from '../auth/authApi';
import { createTeam, fetchTeam, joinTeam, parseTeamInvite, rememberTeam } from '../teams';
import { categoryLabel } from '../domainLabels';
import TeamResult from './TeamResult';
import TeamInvitation from './TeamInvitation';

// 팀 모드: 내 선택 기록을 팀에 더하고, 팀원 모두의 비교를 합친 팀 공통
// 프롬프트를 본다 (서버 team.py). 원문은 보내지 않고 선택 기록만 더한다.
// 팀 결과는 상단 "팀 프롬프트" 화면에서 비교 없이 다시 볼 수 있다.
function TeamPanel({ sessionId, valueLabel = (axis, value) => value, initialCode = '', teamName = '', domainKey, onOpenTeam }) {
  const [teamInfo, setTeamInfo] = useState(initialCode ? { code: initialCode, name: teamName || initialCode, domain_key: domainKey } : null);
  const [invite, setInvite] = useState('');
  const [newName, setNewName] = useState('');
  const [mode, setMode] = useState('join');
  const [name, setName] = useState('');
  const [teamResult, setTeamResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [joined, setJoined] = useState(false);
  // 로그인했으면 서버가 이름 칸을 무시하고 아이디로 참여시킨다. 화면도 그렇게 보여 준다.
  const [me, setMe] = useState(null);
  const [authReady, setAuthReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchMe().then((data) => { if (!cancelled) { setMe(data.user); setAuthReady(true); } })
      .catch(() => { if (!cancelled) { setMe(null); setAuthReady(true); } });
    return () => { cancelled = true; };
  }, []);

  const run = async (request) => {
    setBusy(true);
    setError('');
    try {
      await request();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const join = () => run(async () => {
    const team = await joinTeam(teamInfo.code, sessionId, name.trim());
    setTeamResult(team);
    setJoined(true);
    rememberTeam(team);
  });
  const refresh = () => run(async () => {
    const team = await fetchTeam(teamInfo.code);
    setTeamResult(team);
    rememberTeam(team);
  });
  const findInvite = () => run(async () => {
    const team = await fetchTeam(parseTeamInvite(invite));
    if (team.domain_key !== domainKey) throw new Error(`이 팀은 ${categoryLabel(team.domain_key)} 기준을 모으고 있어요. 같은 카테고리에서 비교한 뒤 합쳐 주세요.`);
    setTeamInfo(team);
    rememberTeam(team);
  });
  const create = () => run(async () => {
    const team = await createTeam(newName.trim(), domainKey);
    setTeamInfo(team);
    rememberTeam(team);
  });

  return (
    <div className="team-panel">
      <p className="question-eyebrow">마지막 단계 · 내 선호를 팀 기준에 합치기</p>
      <p className="team-help">
        {joined ? '내 선호가 팀 기준에 반영됐어요. 아래에서 모인 의견과 공통 지침을 확인하세요.' : '비교를 마쳤어요. 아래 합치기 버튼을 누르면 내 선택이 팀 기준에 반영됩니다.'}
        {' '}원문과 생성 결과는 공유하지 않고 선택 기록만 합칩니다.
      </p>
      {!teamInfo && (
        <div className="ws-block">
          <div className="prompt-actions">
            <button className="prompt-reset-button" type="button" disabled={busy} aria-pressed={mode === 'join'} onClick={() => { setMode('join'); setError(''); }}>초대받은 팀 찾기</button>
            <button className="prompt-reset-button" type="button" disabled={busy} aria-pressed={mode === 'create'} onClick={() => { setMode('create'); setError(''); }}>이 선호로 새 팀 만들기</button>
          </div>
          {mode === 'join' ? (
            <div className="team-form">
              <input aria-label="초대 링크 또는 팀 코드" placeholder="받은 초대 링크 또는 기존 팀 코드" value={invite} maxLength={2048} onChange={(e) => setInvite(e.target.value)} />
              <button className="prompt-reset-button" type="button" disabled={busy || !invite.trim()} onClick={findInvite}>초대 확인하기</button>
            </div>
          ) : (
            <div className="team-form">
              <input aria-label="새 팀 이름" placeholder="새 팀 이름" value={newName} maxLength={60} onChange={(e) => setNewName(e.target.value)} />
              <button className="prompt-reset-button" type="button" disabled={busy || !newName.trim()} onClick={create}>팀 만들기</button>
            </div>
          )}
        </div>
      )}
      {teamInfo && <>
      <p><strong>{teamInfo.name || teamInfo.code}</strong> · {categoryLabel(teamInfo.domain_key)}</p>
      <div className="team-form">
        {!authReady ? <span>참여할 계정을 확인하는 중…</span> : me ? (
          <span className="team-me">{me.username} 으로 참여</span>
        ) : (
          <input aria-label="내 이름" placeholder="내 이름" value={name}
            onChange={(e) => setName(e.target.value)} maxLength={20} />
        )}
        <button className="prompt-copy-button" type="button" disabled={busy || !authReady || (!me && !name.trim())} onClick={join}>
          {busy ? '처리하는 중…' : joined ? '내 선호 다시 반영하기' : '내 선호를 팀 기준에 합치기'}
        </button>
        {joined && <button className="prompt-reset-button" type="button" disabled={busy} onClick={refresh}>팀 기준 새로고침</button>}
      </div>
      {authReady && !me && <p className="ws-help">팀에서 구분할 이름을 적어 주세요. 같은 이름으로 다시 합치면 이전 선택이 교체됩니다. 로그인하면 내 계정으로 참여합니다.</p>}
      </>}
      {error && <p className="connection-note" role="alert">{error}</p>}
      {joined && <p className="team-joined" role="status">반영 완료 · {teamInfo.name || teamInfo.code}의 팀 기준을 함께 만들었어요.</p>}
      {teamResult && <>
        <TeamInvitation key={teamResult.code} team={teamResult} />
        <TeamResult teamResult={teamResult} valueLabel={valueLabel} />
        {onOpenTeam && <div className="prompt-actions"><button className="prompt-reset-button" type="button" onClick={() => onOpenTeam(teamResult)}>팀 안내와 초대로 돌아가기</button></div>}
      </>}
    </div>
  );
}

export default TeamPanel;

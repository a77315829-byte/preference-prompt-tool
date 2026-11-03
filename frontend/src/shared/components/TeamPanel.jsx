import { useEffect, useState } from 'react';
import { fetchMe } from '../auth/authApi';
import { fetchTeam, joinTeam, rememberTeam } from '../teams';
import TeamResult from './TeamResult';

// 팀 모드: 내 선택 기록을 팀에 더하고, 팀원 모두의 비교를 합친 팀 공통
// 프롬프트를 본다 (서버 team.py). 원문은 보내지 않고 선택 기록만 더한다.
// 팀 결과는 상단 "팀 프롬프트" 화면에서 비교 없이 다시 볼 수 있다.
function TeamPanel({ sessionId, valueLabel = (axis, value) => value, initialCode = '' }) {
  const [code, setCode] = useState(initialCode);
  const [name, setName] = useState('');
  const [teamResult, setTeamResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  // 로그인했으면 서버가 이름 칸을 무시하고 아이디로 참여시킨다. 화면도 그렇게 보여 준다.
  const [me, setMe] = useState(null);

  useEffect(() => {
    fetchMe().then((data) => setMe(data.user)).catch(() => setMe(null));
  }, []);

  const run = async (request) => {
    setBusy(true);
    setError('');
    try {
      const team = await request();
      setTeamResult(team);
      rememberTeam(team);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const join = () => run(() => joinTeam(code.trim(), sessionId, name.trim()));
  const refresh = () => run(() => fetchTeam(code.trim()));

  return (
    <div className="team-panel">
      <p className="question-eyebrow">팀 프롬프트</p>
      <p className="team-help">
        팀원이 같은 팀 코드로 각자 비교를 마치고 더하면, 모두의 선택을 합친 팀 공통 프롬프트가 만들어집니다.
        원문은 보내지 않고 선택 기록만 더합니다. 로그인하면 내 아이디로 참여하고, 다른 사람이 그 이름을 쓸 수 없습니다.
        더한 뒤에는 상단 <strong>팀 프롬프트</strong> 메뉴에서 비교 없이 팀 결과를 다시 볼 수 있습니다.
      </p>
      <div className="team-form">
        <input aria-label="팀 코드" placeholder="팀 코드 (예: frontend-team)" value={code}
          onChange={(e) => setCode(e.target.value)} maxLength={32} />
        {me ? (
          <span className="team-me">{me.username} 으로 참여</span>
        ) : (
          <input aria-label="내 이름" placeholder="내 이름" value={name}
            onChange={(e) => setName(e.target.value)} maxLength={20} />
        )}
        <button className="prompt-copy-button" type="button" disabled={busy || !code.trim() || (!me && !name.trim())} onClick={join}>
          팀에 더하기
        </button>
        <button className="prompt-reset-button" type="button" disabled={busy || !code.trim()} onClick={refresh}>
          팀 결과 보기
        </button>
      </div>
      {error && <p className="connection-note">{error}</p>}

      {teamResult && <TeamResult teamResult={teamResult} valueLabel={valueLabel} />}
    </div>
  );
}

export default TeamPanel;

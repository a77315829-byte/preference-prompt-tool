import { useEffect, useState } from 'react';
import { fetchMe } from '../auth/authApi';
import ExportPanel from './ExportPanel';

// 팀 모드: 내 선택 기록을 팀에 더하고, 팀원 모두의 비교를 합친 팀 공통
// 프롬프트를 본다 (서버 team.py). 원문은 보내지 않고 선택 기록만 더한다.
async function call(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `요청에 실패했습니다 (${response.status})`);
  return body.team;
}

function TeamPanel({ sessionId, valueLabel = (axis, value) => value }) {
  const [code, setCode] = useState('');
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
      setTeamResult(await request());
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const join = () => run(() => call(`/teams/${encodeURIComponent(code.trim())}/members`, {
    method: 'POST',
    body: JSON.stringify({ sessionId, name: name.trim() }),
  }));
  const refresh = () => run(() => call(`/teams/${encodeURIComponent(code.trim())}`));

  return (
    <div className="team-panel">
      <p className="question-eyebrow">팀 프롬프트</p>
      <p className="team-help">
        팀원이 같은 팀 코드로 각자 비교를 마치고 더하면, 모두의 선택을 합친 팀 공통 프롬프트가 만들어집니다.
        원문은 보내지 않고 선택 기록만 더합니다. 로그인하면 내 아이디로 참여하고, 다른 사람이 그 이름을 쓸 수 없습니다.
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

      {teamResult && (
        <div className="team-result">
          <p><strong>{teamResult.code}</strong> · 팀원 {teamResult.members.length}명: {teamResult.members
            .map((m) => ((teamResult.signedIn || []).includes(m) ? `${m} (로그인)` : m)).join(', ')}</p>
          <ul className="team-agreements">
            {teamResult.agreements.map((a) => (
              <li key={a.axis} className={a.agreed ? 'agreed' : 'split'}>
                <strong>{a.label}</strong>
                {a.agreed
                  ? ` — 모두 같음: ${valueLabel(a.axis, a.team_value)}`
                  : ` — 합의 필요: ${Object.entries(a.votes).map(([v, n]) => `${valueLabel(a.axis, v)} ${n}명`).join(', ')}${
                    a.tied
                      ? ` (동률이라 팀이 정해야 합니다. 지금 팀 프롬프트는 임시로 ${valueLabel(a.axis, a.team_value)})`
                      : a.team_value === Object.keys(a.votes)[0]
                        ? ` (팀 프롬프트는 다수 쪽 ${valueLabel(a.axis, a.team_value)})`
                        : ` (모두의 비교를 합친 결과 팀 프롬프트는 ${valueLabel(a.axis, a.team_value)})`}`}
              </li>
            ))}
          </ul>
          <pre className="prompt-box"><code>{teamResult.prompt}</code></pre>
          <ExportPanel exports={teamResult.exports} />
        </div>
      )}
    </div>
  );
}

export default TeamPanel;

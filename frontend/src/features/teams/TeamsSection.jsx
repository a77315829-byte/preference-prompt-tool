import { useEffect, useRef, useState } from 'react';
import TeamResult from '../../shared/components/TeamResult';
import { axisValueLabel, categoryLabel } from '../../shared/domainLabels';
import {
  fetchMyTeams, fetchTeam, formatUtc, groupByCategory, readRecentTeams, rememberTeam,
} from '../../shared/teams';

// 팀 프롬프트 보기. 팀에 더하려면 그 카테고리 비교를 끝내야 하지만, 결과를 보는 데는
// 비교가 필요 없다 - 팀 코드만 있으면 된다 (GET /api/teams/<코드>). 로그인했으면 내가
// 참여한 팀을 카테고리별로 모아 보여 준다 (GET /api/teams).
function TeamsSection({ user, onBack, onLogin, onCompare }) {
  const [code, setCode] = useState('');
  const [myTeams, setMyTeams] = useState(null);
  const [recent, setRecent] = useState(() => readRecentTeams());
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const resultRef = useRef(null);

  useEffect(() => {
    if (!user) {
      setMyTeams(null);
      return;
    }
    fetchMyTeams().then(setMyTeams).catch((e) => { setMyTeams([]); setError(e.message); });
  }, [user?.id]);

  const open = async (teamCode) => {
    setBusy(true);
    setError('');
    try {
      const team = await fetchTeam(teamCode.trim());
      setResult(team);
      rememberTeam(team);
      setRecent(readRecentTeams());
      window.setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
    } catch (e) {
      setResult(null);
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const submitCode = (event) => {
    event.preventDefault();
    if (code.trim()) open(code);
  };

  // AWS 비용 보고 화면에는 팀 칸이 없어서 다시 비교해 더할 수 없다.
  const canCompare = (domainKey) => domainKey !== 'idle_tracker';
  const myCodes = new Set((myTeams || []).map((t) => t.code));
  const recentOthers = recent.filter((t) => !myCodes.has(t.code));

  const teamRow = (t, detail) => (
    <li key={t.code} className={result?.code === t.code ? 'is-open' : ''}>
      <span className="ws-saved-title">{t.code}</span>
      {detail && <span className="ws-help">{detail}</span>}
      <button className="ws-small-button" type="button" disabled={busy} onClick={() => open(t.code)}>보기</button>
    </li>
  );

  return (
    <section className="comparison-section teams-section" id="teams-section">
      <div className="comparison-inner">
        <button className="back-button" type="button" onClick={onBack}>← 카테고리로 돌아가기</button>
        <div className="comparison-heading">
          <p className="eyebrow">TEAM PROMPT</p>
          <h2>팀 프롬프트</h2>
          <p>
            팀원이 같은 팀 코드로 각자 비교를 마치고 결과 화면에서 <strong>팀에 더하기</strong>를 누르면, 모두의 선택을
            합친 팀 프롬프트가 만들어집니다. 여기서는 비교를 다시 하지 않고 팀 결과를 봅니다.
          </p>
        </div>

        <form className="ws-step" onSubmit={submitCode}>
          <p className="question-eyebrow">팀 코드로 보기</p>
          <div className="team-form">
            <input aria-label="볼 팀 코드" placeholder="팀 코드 (예: frontend-team)" value={code} maxLength={32}
              onChange={(e) => setCode(e.target.value)} />
            <button className="prompt-copy-button" type="submit" disabled={busy || !code.trim()}>보기</button>
          </div>
          <p className="ws-help">로그인하지 않아도 팀 코드만 있으면 볼 수 있습니다. 원문은 저장되지 않고 선택 기록만 합쳐집니다.</p>
        </form>

        <div className="ws-step">
          <p className="question-eyebrow">내 팀</p>
          {!user && (
            <div className="ws-item">
              <span className="ws-help">로그인하면 내가 참여한 팀이 카테고리별로 모여 보입니다.</span>
              <button className="prompt-copy-button" type="button" onClick={onLogin}>로그인</button>
            </div>
          )}
          {user && myTeams === null && <p className="ws-help">불러오는 중…</p>}
          {user && myTeams?.length === 0 && (
            <p className="ws-help">
              아직 내 아이디로 참여한 팀이 없습니다. 비교를 끝낸 결과 화면에서 팀 코드를 적고 "팀에 더하기"를 누르세요.
            </p>
          )}
          {user && myTeams?.length > 0 && groupByCategory(myTeams).map((group) => (
            <div className="teams-group" key={group.domainKey}>
              <p className="teams-category">{categoryLabel(group.domainKey)}</p>
              <ul className="ws-saved-list">
                {group.items.map((t) => teamRow(t, `팀원 ${t.members}명 · 마지막 참여 ${formatUtc(t.updated_at)}`))}
              </ul>
            </div>
          ))}
          {user && myTeams?.length > 0 && (
            <p className="ws-help">30일 동안 아무도 더하지 않은 팀은 지워집니다.</p>
          )}
        </div>

        {recentOthers.length > 0 && (
          <div className="ws-step">
            <p className="question-eyebrow">이 브라우저에서 최근 본 팀</p>
            <ul className="ws-saved-list">
              {recentOthers.map((t) => teamRow(t, categoryLabel(t.domain_key)))}
            </ul>
          </div>
        )}

        {error && <p className="ws-error" role="alert">{error}</p>}

        {result && (
          <div className="ws-step" ref={resultRef}>
            <p className="question-eyebrow">{categoryLabel(result.domain_key)} · 팀 결과</p>
            <TeamResult key={result.code} teamResult={result} valueLabel={axisValueLabel} />
            {canCompare(result.domain_key) && (
              <div className="prompt-actions">
                <button className="prompt-reset-button" type="button" onClick={() => onCompare(result.domain_key, result.code)}>
                  이 카테고리 비교하고 내 선택 더하기
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

export default TeamsSection;

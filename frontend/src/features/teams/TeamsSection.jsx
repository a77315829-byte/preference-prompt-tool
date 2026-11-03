import { useEffect, useRef, useState } from 'react';
import TeamResult from '../../shared/components/TeamResult';
import TeamInvitation from '../../shared/components/TeamInvitation';
import { CATEGORY_LABEL, axisValueLabel, categoryLabel } from '../../shared/domainLabels';
import {
  createTeam, fetchMyTeams, fetchTeam, formatUtc, groupByCategory, parseTeamInvite, readRecentTeams, rememberTeam,
} from '../../shared/teams';

// 팀 프롬프트 보기. 팀에 더하려면 그 카테고리 비교를 끝내야 하지만, 결과를 보는 데는
// 비교가 필요 없다 - 팀 코드만 있으면 된다 (GET /api/teams/<코드>). 로그인했으면 내가
// 참여한 팀을 카테고리별로 모아 보여 준다 (GET /api/teams).
function TeamsSection({ user, onBack, onLogin, onCompare, initialInvite = '' }) {
  const [code, setCode] = useState('');
  const [mode, setMode] = useState(initialInvite ? 'join' : 'create');
  const [teamName, setTeamName] = useState('');
  const [domainKey, setDomainKey] = useState('coding');
  const [myTeams, setMyTeams] = useState(null);
  const [recent, setRecent] = useState(() => readRecentTeams());
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const resultRef = useRef(null);
  const requestId = useRef(0);

  useEffect(() => {
    if (!user) {
      setMyTeams(null);
      return;
    }
    fetchMyTeams().then(setMyTeams).catch((e) => { setMyTeams([]); setError(e.message); });
  }, [user?.id]);

  const open = async (teamCode) => {
    const id = ++requestId.current;
    setBusy(true);
    setError('');
    setResult(null);
    try {
      const team = await fetchTeam(parseTeamInvite(teamCode));
      if (id !== requestId.current) return;
      setResult(team);
      rememberTeam(team);
      setRecent(readRecentTeams());
      window.setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
    } catch (e) {
      if (id !== requestId.current) return;
      setResult(null);
      setError(e.message);
    } finally {
      if (id === requestId.current) setBusy(false);
    }
  };

  useEffect(() => {
    if (initialInvite) {
      setMode('join');
      setCode(initialInvite);
      open(initialInvite);
    }
    return () => { requestId.current += 1; };
  }, [initialInvite]);

  const create = async (event) => {
    event.preventDefault();
    const id = ++requestId.current;
    setBusy(true);
    setError('');
    setResult(null);
    try {
      const team = await createTeam(teamName.trim(), domainKey);
      if (id !== requestId.current) return;
      setResult(team);
      rememberTeam(team);
      setRecent(readRecentTeams());
      if (user) fetchMyTeams().then(setMyTeams).catch(() => {});
      window.setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
    } catch (e) {
      if (id === requestId.current) setError(e.message);
    } finally {
      if (id === requestId.current) setBusy(false);
    }
  };

  const submitCode = (event) => {
    event.preventDefault();
    if (code.trim()) open(code);
  };

  const canCompare = (domainKey) => Object.hasOwn(CATEGORY_LABEL, domainKey);
  const myCodes = new Set((myTeams || []).map((t) => t.code));
  const recentOthers = recent.filter((t) => canCompare(t.domain_key) && !myCodes.has(t.code));

  const teamRow = (t, detail) => (
    <li key={t.code} className={result?.code === t.code ? 'is-open' : ''}>
      <span className="ws-saved-title">{t.name || t.code}</span>
      {detail && <span className="ws-help">{detail}</span>}
      <button className="ws-small-button" type="button" disabled={busy} onClick={() => open(t.code)}>보기</button>
    </li>
  );

  return (
    <section className="comparison-section teams-section" id="teams-section">
      <div className="comparison-inner">
        <button className="back-button" type="button" onClick={onBack}>← 카테고리로 돌아가기</button>
        <div className="comparison-heading">
          <p className="eyebrow">TEAM GUIDE</p>
          <h2>우리 팀의 AI 사용 기준을 맞춰요</h2>
          <p>
            코드 작성 방식이나 회의록 분량처럼, 팀원마다 원하는 AI 결과가 다를 수 있어요.
            각자의 선택을 모아 공통 지침을 만들고, 의견이 갈린 항목은 함께 확인하세요.
          </p>
        </div>

        <div className="ws-step">
          <p className="question-eyebrow">처음이라면, 여기서 시작하세요</p>
          <ol className="workflow-guide">
            <li><strong>1. 팀을 만들거나 초대를 열어요</strong><span>함께 맞출 기준을 고르고 팀원에게 초대 링크를 전달합니다.</span></li>
            <li><strong>2. 내 취향을 골라요</strong><span>각자 예시 두 개를 비교합니다. 아직 팀 기준에는 반영되지 않아요.</span></li>
            <li><strong>3. 내 선호를 합쳐요</strong><span>마지막 화면에서 합치기를 누르면 내 선택이 팀 기준에 반영됩니다.</span></li>
          </ol>
          <div className="prompt-actions">
            <button className={mode === 'create' ? 'prompt-copy-button' : 'prompt-reset-button'} type="button" aria-pressed={mode === 'create'} disabled={busy}
              onClick={() => { setMode('create'); setError(''); setResult(null); }}>새 팀 만들기</button>
            <button className={mode === 'join' ? 'prompt-copy-button' : 'prompt-reset-button'} type="button" aria-pressed={mode === 'join'} disabled={busy}
              onClick={() => { setMode('join'); setError(''); setResult(null); }}>초대받아서 참여하기</button>
          </div>
        </div>

        {mode === 'create' ? (
          <form className="ws-step" onSubmit={create}>
            <h3>우리 팀의 기준을 만들어요</h3>
            <label className="task-input-label" htmlFor="new-team-name">팀 이름</label>
            <input id="new-team-name" className="ws-input" placeholder="예: 함께 만드는 프론트엔드팀" maxLength={60} required value={teamName}
              onChange={(e) => setTeamName(e.target.value)} />
            <label className="task-input-label" htmlFor="new-team-domain">이번에 함께 맞출 기준</label>
            <select id="new-team-domain" className="ws-input" value={domainKey} onChange={(e) => setDomainKey(e.target.value)}>
              <option value="coding">코드 작성 방식</option>
              <option value="summarization_ko">한국어 문서 요약 방식</option>
              <option value="summarization">영어 문서 요약 방식</option>
            </select>
            <p className="ws-help">팀을 만들면 초대 링크가 준비됩니다. 비교 항목은 팀원 모두에게 동일하게 연결됩니다. 팀 생성만으로 AI를 호출하거나 선호를 반영하지 않습니다.</p>
            <div className="prompt-actions"><button className="prompt-copy-button" type="submit" disabled={busy || !teamName.trim()}>
              {busy ? '준비하는 중…' : '팀 만들고 초대 준비하기'}
            </button></div>
          </form>
        ) : (
        <form className="ws-step" onSubmit={submitCode}>
          <h3>받은 초대를 확인해요</h3>
          <label className="task-input-label" htmlFor="team-invite">초대 링크 또는 기존 팀 코드</label>
          <div className="team-form">
            <input id="team-invite" placeholder="팀원이 보낸 초대 링크를 붙여 넣으세요" value={code} maxLength={2048}
              onChange={(e) => setCode(e.target.value)} />
            <button className="prompt-copy-button" type="submit" disabled={busy || !code.trim()}>{busy ? '확인하는 중…' : '초대 확인하기'}</button>
          </div>
          <p className="ws-help">초대를 확인한 뒤 아래에서 내 선호 고르기를 시작하세요. 기존 팀 코드로도 참여할 수 있어요.</p>
        </form>
        )}

        {error && <p className="ws-error" role="alert">{error}</p>}
        {result && (
          <div className="ws-step team-start" ref={resultRef}>
            <p className="question-eyebrow">팀 준비 완료 · 다음은 내 선호 고르기</p>
            <h3>{result.name || result.code}</h3>
            <p>{categoryLabel(result.domain_key)} · 선호를 합친 팀원 {result.members.length}명</p>
            <p className="ws-help">{result.members.length ? '기존 팀 기준을 확인하고 내 선호를 더할 수 있어요.' : '아직 모인 선호가 없어요. 첫 번째로 내 취향을 골라 주세요.'}</p>
            {canCompare(result.domain_key) && (
              <div className="prompt-actions">
                <button className="prompt-copy-button" type="button" onClick={() => onCompare(result.domain_key, result.code, result.name || result.code)}>내 선호 고르기 시작</button>
              </div>
            )}
            <p className="ws-help">비교 후 ‘내 선호를 팀 기준에 합치기’를 눌러야 반영됩니다. 원문과 생성 결과는 팀에 공유하지 않습니다.</p>
            <TeamInvitation key={result.code} team={result} />
            {result.members.length > 0 && (
              <details className="ws-raw"><summary>현재 모인 팀 기준 보기</summary>
                <TeamResult key={result.code} teamResult={result} valueLabel={axisValueLabel} />
              </details>
            )}
          </div>
        )}

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
              아직 만든 팀이나 참여한 팀이 없습니다. 위에서 새 팀을 만들거나 받은 초대를 확인하세요.
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

      </div>
    </section>
  );
}

export default TeamsSection;

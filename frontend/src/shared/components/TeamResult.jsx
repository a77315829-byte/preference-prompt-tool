import { useState } from 'react';
import ExportPanel from './ExportPanel';
import PromptLanguageSwitch from './PromptLanguageSwitch';

// 팀 결과: 팀원, 항목마다 갈린 정도, 팀 프롬프트와 도구별 내보내기.
// 비교 결과 화면의 팀 칸과 팀 프롬프트 화면이 같이 쓴다.
function TeamResult({ teamResult, valueLabel = (axis, value) => value }) {
  const [language, setLanguage] = useState(null);
  return (
    <div className="team-result">
      <p><strong>{teamResult.code}</strong> · 팀원 {teamResult.members.length}명: {teamResult.members
        .map((m) => ((teamResult.signedIn || []).includes(m) ? `${m} (로그인)` : m)).join(', ')}</p>
      <ul className="team-agreements">
        {teamResult.agreements.map((a) => (
          <li key={a.axis} className={a.agreed ? 'agreed' : 'split'}>
            <strong>{a.label}</strong>
            {a.undecided
              ? ' — 아무도 선호를 정하지 않아 팀 프롬프트에 넣지 않았습니다'
              : a.agreed
              ? ` — 모두 같음: ${valueLabel(a.axis, a.team_value)}`
              : ` — 합의 필요: ${Object.entries(a.votes).map(([v, n]) => `${valueLabel(a.axis, v)} ${n}명`).join(', ')}${
                a.tied
                  ? (a.team_value
                    ? ` (동률이라 팀이 정해야 합니다. 지금 팀 프롬프트는 선호가 조금 더 기운 쪽인 ${valueLabel(a.axis, a.team_value)})`
                    : ' (의견이 같은 수로 갈려 팀이 정해야 합니다. 팀 프롬프트에는 넣지 않았습니다)')
                  : ` (팀 프롬프트는 다수 쪽 ${valueLabel(a.axis, a.team_value)} - 한 사람 한 표)`}`}
          </li>
        ))}
      </ul>
      <PromptLanguageSwitch
        languages={Object.keys(teamResult.prompts || {})}
        value={teamResult.prompts?.[language] ? language : teamResult.prompt_language}
        onChange={setLanguage}
      />
      <pre className="prompt-box"><code>{teamResult.prompts?.[language] || teamResult.prompt}</code></pre>
      <ExportPanel exports={teamResult.exports_by_language?.[language] || teamResult.exports} />
    </div>
  );
}

export default TeamResult;

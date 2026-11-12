import { CODING_CHOICES } from './codingOptions';
import './fastApiOptimization.css';
import { REVIEW_LABELS } from './CodingAnswerReview';
import CodingEvaluationBreakdown from './CodingEvaluationBreakdown';
import CodingSignalSummary from './CodingSignalSummary';

export function codingEnvironmentLabel(item) {
  const env = item.coding_profile || item.coding_environment;
  return env ? `${env.language} · ${env.framework || '프레임워크 지정 없음'}` : '';
}

function SavedCodingProfile({ item, editingPrompt, disabled, onCreate }) {
  const profile = item.coding_profile;
  if (!profile) return null;
  const optimization = item.coding_optimization;
  const teamContext = item.coding_team_context;
  return <div className="saved-coding-profile">
    <h4>저장 당시 개발 환경과 내 설정</h4>
    <p><strong>{codingEnvironmentLabel(item)}</strong> · {teamContext ? '개인·팀 기준을 조합한 작업용' : profile.comparison ? '예시 비교에서 고른 선호' : '직접 고른 선호'}</p>
    {teamContext && <details><summary>당시 팀 기준과 항목별 선택 출처</summary>
      <p>{teamContext.name} · {teamContext.revision}판 · 팀장이 정한 기본값과 직접 조합</p>
      <ul>{Object.entries(CODING_CHOICES).map(([key, field]) => <li key={key}>
        {field.label}: 개인 {field.options[teamContext.source_profile.preferences[key]]} / 팀 {field.options[teamContext.team_profile.preferences[key]]}
        {' → '}{teamContext.choices[key] === 'team' ? '팀 기준 채택' : teamContext.choices[key] === 'personal' ? '개인 기준 채택' : '같은 기준'}
      </li>)}</ul>
      <p>함께 보관한 필수 규칙: {teamContext.rules.join(' · ') || '없음'}</p>
      <p className="ws-help">저장 당시 기록입니다. 이후 팀 변경은 이 지침에 자동 반영하지 않습니다.</p>
    </details>}
    {profile.comparison && <p className="ws-help">비교에 사용한 예시: {profile.comparison.example?.label || '언어 기본 문법 · 프레임워크 전용 비교 아님'}</p>}
    <CodingSignalSummary comparison={profile.comparison} resolved />
    {optimization && <div className="saved-gepa-origin"><h4>GEPA로 다듬어 새로 보관한 지침</h4>
      <p className="ws-help">개발 환경과 아래 선호는 유지하고, 원래 지침 뒤에 보충 안내를 덧붙인 후보입니다. 기존 보관함 항목은 갱신하지 않았어요.</p>
      <details><summary>보충 안내와 개선 전 프롬프트 확인</summary><p className="ws-help">{optimization.guidance}</p>
        <textarea className="task-input" aria-label="GEPA 개선 전 원본 프롬프트" readOnly rows={8} value={optimization.original_prompt} />
        <p className="ws-help">{optimization.report?.limitation} {optimization.report?.preference_checks}</p>
        {optimization.report?.holdout_before && optimization.report?.holdout_after && <>
          <CodingEvaluationBreakdown result={{ profile, report: optimization.report, changed: true }} />
          <details className="fastapi-gepa-examples"><summary>저장된 별도 과제의 실제 AI 답변 비교</summary>
            {(optimization.report.holdout_before.tasks || []).map(task => {
              const after = optimization.report.holdout_after.tasks?.find(next => next.id === task.id);
              return <section key={task.id}><h5>{task.label}</h5><p>{task.request}</p><div className="fastapi-gepa-comparison">
                <label>기존 지침으로 받은 답변<textarea className="task-input" readOnly rows={12} value={task.response ?? '답변 기록 없음'} /></label>
                <label>후보 지침으로 받은 답변<textarea className="task-input" readOnly rows={12} value={after?.response ?? '답변 기록 없음'} /></label>
              </div></section>;
            })}
          </details>
        </>}
        {optimization.human_review && <div className="saved-human-review"><h5>저장할 때 내가 직접 확인한 내용</h5><p className="ws-help">자동 점수와 별개인 개인 판단이며 코드 품질 검증 결과가 아닙니다.</p>
          {Object.entries(optimization.human_review).map(([taskId, sides]) => <div key={taskId}><strong>{optimization.report?.holdout_before?.tasks?.find(task => task.id === taskId)?.label || '저장한 과제'}</strong>
            {Object.entries(sides).map(([side, choices]) => <p className="ws-help" key={side}>{side === 'original' ? '기존 답변' : '후보 답변'}: {Object.entries(choices).map(([key, mark]) => `${CODING_CHOICES[key]?.label || key} ${REVIEW_LABELS[mark] || mark}`).join(' · ')}</p>)}</div>)}
        </div>}
      </details></div>}
    <p className="ws-help">{editingPrompt || !item.coding_profile_matches
      ? '본문·종류가 저장 당시 설정과 다릅니다. 아래는 처음 저장한 설정이며 현재 지침에서 새로 추정한 값은 아닙니다.'
      : teamContext ? '아래는 개인·팀 기준을 조합한 결과입니다. 원래 개인 선호와 팀 기본값은 위 출처에서 따로 확인할 수 있습니다.'
      : optimization ? '아래는 GEPA 개선에서도 고정한 선택입니다. 개선 효과나 만족도가 검증되었다는 뜻은 아니며, 평가 기록과 직접 비교해 사용하세요.'
      : profile.comparison ? '코드 예시 비교와 직접 확인을 거쳐 고른 설정입니다. 비교 이력과 최종 설정은 구분해 표시합니다.'
        : '예시 비교로 추정한 결과가 아니라, 지침을 만들 때 직접 고른 설정입니다.'}</p>
    <ul className="saved-coding-choices">{Object.entries(CODING_CHOICES).map(([key, field]) => <li key={key}>
      <span>{field.label}</span><strong>{field.options[profile.preferences[key]]}</strong>
      {profile.comparison && <small>{profile.comparison.choices[key] === null ? '직접 확인한 설정' : '예시에서 선택'}</small>}</li>)}</ul>
    {profile.extra && <p className="ws-help coding-extra-snapshot">추가 선호: {profile.extra}</p>}
    {onCreate && <button className="prompt-reset-button" type="button" disabled={disabled} onClick={() => onCreate(profile)}>{optimization ? '저장한 선택으로 새 초안 만들기' : '이 설정으로 새 지침 만들기'}</button>}
    {optimization && <p className="ws-help">새 초안 만들기는 GEPA 보충 안내를 제외하고 선택 설정으로 다시 만듭니다. 저장한 개선본 그대로 쓰려면 ‘새 작업에 사용’을 선택하세요.</p>}
    {teamContext && <p className="ws-help">새 지침 만들기는 네 설정으로 새 초안을 만듭니다. 팀 필수 규칙까지 그대로 쓰려면 ‘새 작업에 사용’을 선택하세요.</p>}
    <p className="ws-help">‘새 작업에 사용’에서 네 항목의 팀 기준 연결·도구 내보내기·실제 작업 비교를 열 수 있어요. 기존 React 예시 비교 기록은 별도로 유지합니다.</p>
  </div>;
}

export default SavedCodingProfile;

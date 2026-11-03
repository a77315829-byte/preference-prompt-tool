import { CODING_CHOICES } from './codingOptions';
import './fastApiOptimization.css';
import { REVIEW_LABELS } from './CodingAnswerReview';

export function codingEnvironmentLabel(item) {
  const env = item.coding_profile || item.coding_environment;
  return env ? `${env.language} · ${env.framework || '프레임워크 지정 없음'}` : '';
}

function SavedCodingProfile({ item, editingPrompt, disabled, onCreate }) {
  const profile = item.coding_profile;
  if (!profile) return null;
  const optimization = item.coding_optimization;
  return <div className="saved-coding-profile">
    <h4>저장 당시 개발 환경과 내 설정</h4>
    <p><strong>{codingEnvironmentLabel(item)}</strong> · {profile.comparison ? '예시 비교에서 고른 선호' : '직접 고른 선호'}</p>
    {profile.comparison && <p className="ws-help">비교에 사용한 예시: {profile.comparison.example?.label || '언어 기본 문법 · 프레임워크 전용 비교 아님'}</p>}
    {optimization && <div className="saved-gepa-origin"><h4>GEPA로 다듬어 새로 보관한 지침</h4>
      <p className="ws-help">개발 환경과 아래 선호는 유지하고, 원래 지침 뒤에 보충 안내를 덧붙인 후보입니다. 기존 보관함 항목은 갱신하지 않았어요.</p>
      <details><summary>보충 안내와 개선 전 프롬프트 확인</summary><p className="ws-help">{optimization.guidance}</p>
        <textarea className="task-input" aria-label="GEPA 개선 전 원본 프롬프트" readOnly rows={8} value={optimization.original_prompt} />
        <p className="ws-help">{optimization.report?.limitation} {optimization.report?.preference_checks}</p>
        {optimization.report?.holdout_before && <p className="ws-help">개선에 쓰지 않은 별도 과제: {Math.round(optimization.report.holdout_before.score * 100)}점 → {Math.round(optimization.report.holdout_after.score * 100)}점 · 정적·형식 대리 평가</p>}
        {optimization.human_review && <div className="saved-human-review"><h5>저장할 때 내가 직접 확인한 내용</h5><p className="ws-help">자동 점수와 별개인 개인 판단이며 코드 품질 검증 결과가 아닙니다.</p>
          {Object.entries(optimization.human_review).map(([taskId, sides]) => <div key={taskId}><strong>{optimization.report?.holdout_before?.tasks?.find(task => task.id === taskId)?.label || '저장한 과제'}</strong>
            {Object.entries(sides).map(([side, choices]) => <p className="ws-help" key={side}>{side === 'original' ? '기존 답변' : '후보 답변'}: {Object.entries(choices).map(([key, mark]) => `${CODING_CHOICES[key]?.label || key} ${REVIEW_LABELS[mark] || mark}`).join(' · ')}</p>)}</div>)}
        </div>}
      </details></div>}
    <p className="ws-help">{editingPrompt || !item.coding_profile_matches
      ? '본문·종류가 저장 당시 설정과 다릅니다. 아래는 처음 저장한 설정이며 현재 지침에서 새로 추정한 값은 아닙니다.'
      : optimization ? '아래는 GEPA 개선에서도 고정한 선택입니다. 개선 효과나 만족도가 검증되었다는 뜻은 아니며, 평가 기록과 직접 비교해 사용하세요.'
      : profile.comparison ? '같은 기능의 코드 예시를 보고 고른 설정입니다. 판단을 보류한 항목은 당시 직접 설정을 유지했습니다.'
        : '예시 비교로 추정한 결과가 아니라, 지침을 만들 때 직접 고른 설정입니다.'}</p>
    <ul className="saved-coding-choices">{Object.entries(CODING_CHOICES).map(([key, field]) => <li key={key}>
      <span>{field.label}</span><strong>{field.options[profile.preferences[key]]}</strong>
      {profile.comparison && <small>{profile.comparison.choices[key] === null ? '직접 설정 · 비교 보류' : '예시에서 선택'}</small>}</li>)}</ul>
    {profile.extra && <p className="ws-help coding-extra-snapshot">추가 선호: {profile.extra}</p>}
    {onCreate && <button className="prompt-reset-button" type="button" disabled={disabled} onClick={() => onCreate(profile)}>{optimization ? '저장한 선택으로 새 초안 만들기' : '이 설정으로 새 지침 만들기'}</button>}
    {optimization && <p className="ws-help">새 초안 만들기는 GEPA 보충 안내를 제외하고 선택 설정으로 다시 만듭니다. 저장한 개선본 그대로 쓰려면 ‘새 작업에 사용’을 선택하세요.</p>}
    <p className="ws-help">현재는 개인용 지침으로 재사용합니다. React 예시 비교의 팀 기준과 자동으로 합치지는 않습니다.</p>
  </div>;
}

export default SavedCodingProfile;

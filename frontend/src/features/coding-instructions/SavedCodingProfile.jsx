import { CODING_CHOICES } from './codingOptions';

export function codingEnvironmentLabel(item) {
  const env = item.coding_profile || item.coding_environment;
  return env ? `${env.language} · ${env.framework || '프레임워크 지정 없음'}` : '';
}

function SavedCodingProfile({ item, editingPrompt, disabled, onCreate }) {
  const profile = item.coding_profile;
  if (!profile) return null;
  return <div className="saved-coding-profile">
    <h4>저장 당시 개발 환경과 내 설정</h4>
    <p><strong>{codingEnvironmentLabel(item)}</strong> · 직접 고른 선호</p>
    <p className="ws-help">{editingPrompt || !item.coding_profile_matches
      ? '본문·종류가 저장 당시 설정과 다릅니다. 아래는 처음 저장한 설정이며 현재 지침에서 새로 추정한 값은 아닙니다.'
      : '예시 비교로 추정한 결과가 아니라, 지침을 만들 때 직접 고른 설정입니다.'}</p>
    <ul>{Object.entries(CODING_CHOICES).map(([key, field]) => <li key={key}>{field.label}: {field.options[profile.preferences[key]]}</li>)}</ul>
    {profile.extra && <p className="ws-help coding-extra-snapshot">추가 선호: {profile.extra}</p>}
    {onCreate && <button className="prompt-reset-button" type="button" disabled={disabled} onClick={() => onCreate(profile)}>이 설정으로 새 지침 만들기</button>}
    <p className="ws-help">현재는 개인용 지침으로 재사용합니다. React 예시 비교의 팀 기준과 자동으로 합치지는 않습니다.</p>
  </div>;
}

export default SavedCodingProfile;

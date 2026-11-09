import { useState } from 'react';
import { FRAMEWORKS, LANGUAGES } from './codingOptions';

const NOTES = { FastAPI: 'Python으로 API 만들기', Django: '기능을 갖춘 웹 서비스', Flask: '가볍게 시작하는 웹 개발', 'Spring Boot': 'Java 서버와 API', React: '컴포넌트로 만드는 화면', 'Next.js': 'React 기반 웹 서비스', Vue: '화면과 인터랙션', Express: 'JavaScript 서버와 API' };

export default function CodingEnvironmentPicker({ profile, frameworkChosen, busy, onChange, onCompare, onDirect, onReuse }) {
  const [more, setMore] = useState(Boolean(profile.language && !LANGUAGES.slice(0, 6).includes(profile.language)));
  const [customLanguage, setCustomLanguage] = useState(Boolean(profile.language && !LANGUAGES.includes(profile.language)));
  const [customFramework, setCustomFramework] = useState(Boolean(profile.framework && !(FRAMEWORKS[profile.language] || []).includes(profile.framework)));
  const ready = profile.language.trim() && frameworkChosen && (!customFramework || profile.framework.trim());
  const language = (name) => {
    if (!customLanguage && profile.language === name) return;
    setCustomLanguage(false); setCustomFramework(false);
    onChange({ language: name, framework: '' }, false);
  };
  return <div className="coding-environment-screen">
    <div className="coding-screen-heading"><span className="coding-kicker">01 · 개발 환경</span>
      <h3>어떤 환경에서 개발하나요?</h3><p>지금 쓰는 언어와 도구를 눌러 주세요. 다음에는 코드 두 개를 보고 내 방식을 고릅니다.</p></div>
    <div className="coding-environment-grid">
      <fieldset className="coding-choice-surface tone-lavender" disabled={busy}>
        <legend>사용할 언어</legend><p>하나를 골라 주세요.</p>
        <div className="coding-language-buttons" role="group" aria-label="개발 언어 선택">
          {(more ? LANGUAGES : LANGUAGES.slice(0, 6)).map((name, index) => <button type="button" key={name}
            className={`coding-language-button tone-${['lavender', 'peach', 'mint'][index % 3]}`}
            aria-label={`${name} 선택`} aria-pressed={!customLanguage && profile.language === name} onClick={() => language(name)}>
            <strong>{name}</strong><span aria-hidden="true">{!customLanguage && profile.language === name ? '✓' : '↗'}</span>
          </button>)}
          <button type="button" className="coding-language-button" aria-label="언어 직접 입력" aria-pressed={customLanguage}
            onClick={() => { setCustomLanguage(true); setCustomFramework(false); onChange({ language: '', framework: '' }, false); }}><strong>직접 입력</strong><span aria-hidden="true">＋</span></button>
        </div>
        {!more && <button type="button" className="coding-text-button" onClick={() => setMore(true)}>다른 언어도 보기 · 전체 14개</button>}
        {customLanguage && <label className="coding-custom-field">사용할 언어 이름<input id="coding-language-custom" className="ws-input" maxLength={60} value={profile.language}
          onChange={event => onChange({ language: event.target.value, framework: '' }, false)} placeholder="예: Elixir, Julia, SQL" /></label>}
      </fieldset>
      <fieldset className="coding-choice-surface tone-mint" disabled={busy}>
        <legend>함께 쓸 프레임워크</legend><p>{profile.language.trim() ? `${profile.language}에서 사용할 도구를 골라 주세요.` : '언어를 고르면 함께 쓸 도구가 보여요.'}</p>
        <div className="coding-framework-buttons" role="group" aria-label="프레임워크 선택">
          {(FRAMEWORKS[profile.language] || []).map(name => <button key={name} type="button" className="coding-framework-button"
            disabled={!profile.language.trim()} aria-label={`${name} 선택`} aria-pressed={frameworkChosen && !customFramework && profile.framework === name}
            onClick={() => { setCustomFramework(false); onChange({ framework: name }, true); }}>
            <span><strong>{name}</strong><small>{NOTES[name] || '이 도구에 맞춘 개발 지침'}</small></span><span aria-hidden="true">{frameworkChosen && profile.framework === name ? '✓' : '＋'}</span>
          </button>)}
          <button type="button" className="coding-framework-button" aria-label="프레임워크 없이 선택" disabled={!profile.language.trim()}
            aria-pressed={frameworkChosen && !customFramework && !profile.framework} onClick={() => { setCustomFramework(false); onChange({ framework: '' }, true); }}>
            <span><strong>프레임워크 없이</strong><small>언어 기본 문법으로 시작할게요</small></span><span aria-hidden="true">{frameworkChosen && !customFramework && !profile.framework ? '✓' : '＋'}</span></button>
          <button type="button" className="coding-text-button" disabled={!profile.language.trim()} onClick={() => { setCustomFramework(true); onChange({ framework: '' }, true); }}>프레임워크 직접 입력</button>
        </div>
        {customFramework && <label className="coding-custom-field">사용할 프레임워크 이름<input id="coding-framework-custom" className="ws-input" maxLength={100} value={profile.framework}
          onChange={event => onChange({ framework: event.target.value }, true)} placeholder="이름과 필요한 버전을 적어 주세요" /></label>}
      </fieldset>
    </div>
    <div className="coding-next-bar"><div><small>내가 고른 개발 환경</small><strong>{profile.language || '언어 선택 전'}<span aria-hidden="true"> / </span>{frameworkChosen ? profile.framework || '프레임워크 없이' : '도구 선택 전'}</strong></div>
      <button type="button" className="coding-primary-button" disabled={busy || !ready} onClick={onReuse || onDirect}>
        {busy ? '예시를 불러오는 중…' : onReuse ? '저장한 선택으로 계속하기' : profile.language && !LANGUAGES.includes(profile.language) ? '설정 카드로 선택하기 →' : '설정 카드로 직접 고를게요'}</button>
    </div>
    <div className="coding-environment-alternatives">
      {onReuse && <button type="button" className="coding-text-button" disabled={busy || !ready} onClick={onDirect}>설정 카드로 직접 고를게요</button>}
      <button type="button" className="coding-secondary-button" disabled={busy || !ready || !LANGUAGES.includes(profile.language)} onClick={onCompare}>{onReuse ? '코드 예시부터 다시 비교할게요' : '코드 예시 비교 시작하기 →'}</button>
    </div>
  </div>;
}

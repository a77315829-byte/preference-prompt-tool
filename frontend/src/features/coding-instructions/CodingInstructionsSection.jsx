import { useEffect, useRef, useState } from 'react';
import SavePreferencePanel from '../preferences/SavePreferencePanel';
import { CODING_CHOICES, DEFAULT_CODING_PROFILE, FRAMEWORKS, LANGUAGES, previewCodingInstructions } from './codingOptions';

function CodingInstructionsSection({ user, signupOpen, onLogin, onOpenLibrary, onBack, onReactComparison, initialProfile }) {
  const [profile, setProfile] = useState(() => structuredClone(initialProfile || DEFAULT_CODING_PROFILE));
  const [customLanguage, setCustomLanguage] = useState(Boolean(initialProfile && !LANGUAGES.includes(initialProfile.language)));
  const [customFramework, setCustomFramework] = useState(Boolean(initialProfile?.framework && !(FRAMEWORKS[initialProfile.language] || []).includes(initialProfile.framework)));
  const [draft, setDraft] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const request = useRef(0);
  const resultRef = useRef(null);
  useEffect(() => () => { request.current += 1; }, []);
  const change = (changes) => { request.current += 1; setProfile((current) => ({ ...current, ...changes })); setDraft(null); setError(''); setCopied(false); };
  const generate = async (event) => {
    event.preventDefault(); const token = ++request.current;
    setBusy(true); setError(''); setCopied(false);
    try {
      const next = await previewCodingInstructions(profile);
      if (token === request.current) { setDraft(next); window.setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 30); }
    } catch (e) { if (token === request.current) setError(e.message); }
    finally { if (token === request.current) setBusy(false); }
  };
  const copy = async () => {
    try { await navigator.clipboard.writeText(draft.prompt); setCopied(true); setError(''); }
    catch { setError('복사하지 못했어요. 아래 지침을 직접 선택해 복사해 주세요.'); }
  };
  return <section className="comparison-section coding-instructions-section">
    <div className="comparison-inner">
      <button className="back-button" type="button" disabled={busy} onClick={onBack}>← 시작 화면으로</button>
      <div className="comparison-heading">
        <p className="eyebrow">MY CODING GUIDE</p>
        <h2>내 개발 환경에 맞는 지침을 만들어요</h2>
        <p>언어와 프레임워크를 고르고 원하는 작성 방식을 정하세요. 지침을 복사하거나 내 선호 보관함에 저장해 새 개발 요청에 다시 쓸 수 있어요.</p>
      </div>
      <div className="ws-step coding-react-entry">
        <strong>예시를 보면서 취향을 찾고 싶나요?</strong>
        <p className="ws-help">기존 TypeScript/React 코드 비교와 팀 기준 맞추기도 사용할 수 있어요.</p>
        <button className="prompt-reset-button" type="button" disabled={busy} onClick={onReactComparison}>React 예시 비교로 취향 찾기</button>
      </div>
      <form className="ws-step" onSubmit={generate}>
        <fieldset disabled={busy} className="coding-profile-fields">
          <legend>1. 어떤 환경에서 개발하나요?</legend>
          <div className="coding-profile-grid">
            <div>
              <label className="task-input-label" htmlFor="coding-language">개발 언어</label>
              <select id="coding-language" className="ws-input" value={customLanguage ? '__custom__' : profile.language} onChange={(e) => {
                const custom = e.target.value === '__custom__'; setCustomLanguage(custom); setCustomFramework(false);
                change({ language: custom ? '' : e.target.value, framework: '' });
              }}>
                {LANGUAGES.map((name) => <option key={name}>{name}</option>)}<option value="__custom__">직접 입력</option>
              </select>
              {customLanguage && <><label className="task-input-label" htmlFor="coding-language-custom">사용할 언어 이름</label>
                <input id="coding-language-custom" className="ws-input" required maxLength={60} value={profile.language} onChange={(e) => change({ language: e.target.value })} placeholder="예: Elixir, Julia, SQL" /></>}
            </div>
            <div>
              <label className="task-input-label" htmlFor="coding-framework">프레임워크·라이브러리</label>
              <select id="coding-framework" className="ws-input" value={customFramework ? '__custom__' : profile.framework} onChange={(e) => {
                const custom = e.target.value === '__custom__'; setCustomFramework(custom); change({ framework: custom ? '' : e.target.value });
              }}>
                <option value="">지정하지 않음</option>
                {(FRAMEWORKS[profile.language] || []).map((name) => <option key={name}>{name}</option>)}<option value="__custom__">직접 입력</option>
              </select>
              {customFramework && <><label className="task-input-label" htmlFor="coding-framework-custom">사용할 프레임워크 이름</label>
                <input id="coding-framework-custom" className="ws-input" required maxLength={100} value={profile.framework} onChange={(e) => change({ framework: e.target.value })} placeholder="이름과 필요한 버전도 적을 수 있어요" /></>}
            </div>
          </div>
          <p className="ws-help">목록에 없어도 직접 입력할 수 있어요. 언어를 바꾸면 프레임워크 선택은 초기화합니다.</p>
        </fieldset>
        <fieldset disabled={busy} className="coding-profile-fields">
          <legend>2. 어떤 방식으로 답을 받고 싶나요?</legend>
          <div className="coding-profile-grid">{Object.entries(CODING_CHOICES).map(([key, field]) => <div key={key}>
            <label className="task-input-label" htmlFor={`coding-choice-${key}`}>{field.label}</label>
            <select id={`coding-choice-${key}`} className="ws-input" value={profile.preferences[key]} onChange={(e) => change({ preferences: { ...profile.preferences, [key]: e.target.value } })}>
              {Object.entries(field.options).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>)}</div>
          <label className="task-input-label" htmlFor="coding-extra">추가 작성 선호 <span>(선택)</span></label>
          <textarea id="coding-extra" className="task-input" rows={3} maxLength={1000} value={profile.extra} onChange={(e) => change({ extra: e.target.value })} placeholder="예: 설명은 한국어로, 기존 함수 이름은 유지해 주세요." />
        </fieldset>
        <p className="ws-help">직접 고른 선호로 지침 문장을 조립합니다. 이 단계는 모델을 호출하거나 코드를 실행하지 않으며, 언어별 코드 품질을 검증하는 기능은 아닙니다.</p>
        <button className="prompt-copy-button" type="submit" disabled={busy || !profile.language.trim() || (customFramework && !profile.framework.trim())}>{busy ? '처리하는 중…' : '내 설정으로 지침 만들기'}</button>
        {!draft && <p className="ws-help" role="status">설정을 바꾼 뒤에는 지침을 다시 만들어 주세요.</p>}
      </form>
      {draft && <div className="ws-step coding-instructions-result" ref={resultRef}>
        <h3>3. 확인하고 다음 작업에도 쓰세요</h3>
        <p className="ws-help">{draft.profile.language} · {draft.profile.framework || '프레임워크 지정 없음'} · 직접 고른 선호</p>
        <label className="task-input-label" htmlFor="coding-instructions-prompt">내 코딩 지침</label>
        <textarea id="coding-instructions-prompt" className="task-input" readOnly rows={12} value={draft.prompt} onFocus={(e) => e.target.select()} />
        <button className="prompt-reset-button" type="button" disabled={busy} onClick={copy}>{copied ? '지침을 복사했어요' : '지침 복사'}</button>
        <SavePreferencePanel domainKey="coding" prompt={draft.prompt} codingProfile={draft.profile}
          initialTitle={`${draft.profile.language}${draft.profile.framework ? ` · ${draft.profile.framework}` : ''} 내 작성 방식`.slice(0, 100)}
          user={user} signupOpen={signupOpen} onLogin={onLogin} onOpenLibrary={onOpenLibrary} onBusy={setBusy} />
      </div>}
      {error && <p className="ws-error" role="alert">{error}</p>}
    </div>
  </section>;
}

export default CodingInstructionsSection;

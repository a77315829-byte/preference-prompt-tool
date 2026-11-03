import { useEffect, useState } from 'react';
import AuthSection from '../../shared/auth/AuthSection';
import { createPreference } from './preferencesApi';
import { PREFERENCE_CATEGORIES } from './preferenceText';

function SavePreferencePanel({ domainKey, prompt, user, signupOpen, onLogin, onOpenLibrary, codingProfile = null, initialTitle, onBusy }) {
  const [title, setTitle] = useState(initialTitle || (domainKey === 'coding' ? '내 코딩 방식' : '내 문서 요약 방식'));
  const [busy, setBusy] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(null);
  useEffect(() => { setSaved(null); }, [user?.id]);
  const unchanged = saved?.prompt === prompt && saved?.title === title.trim();
  if (!PREFERENCE_CATEGORIES[domainKey]) return null;

  const save = async (event) => {
    event.preventDefault();
    if (!user) { setLoginOpen(true); return; }
    setBusy(true); onBusy?.(true); setError('');
    try {
      const item = await createPreference({ title: title.trim(), domainKey, prompt,
        ...(codingProfile ? { codingProfile, note: `${codingProfile.language} / ${codingProfile.framework || '프레임워크 지정 없음'} · 직접 고른 작성 선호` } : {}) });
      setSaved(item);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); onBusy?.(false); }
  };

  return (
    <div className="preference-save ws-step">
      <h3>이 방식을 다음에도 쓰고 싶나요?</h3>
      <p className="ws-help">내 선호 보관함에 담으면 나중에 수정하거나 새 작업에 다시 쓸 수 있어요. 지금 보고 있는 지침만 저장하며, 이번 작업 원문은 보관함에 넣지 않습니다.</p>
      <form onSubmit={save}>
        <label className="task-input-label" htmlFor="save-preference-title">기억하기 쉬운 이름</label>
        <input id="save-preference-title" className="ws-input" value={title} maxLength={100} required disabled={busy}
          placeholder="예: 짧은 회의록 요약, 꼼꼼한 React 코드" onChange={(e) => setTitle(e.target.value)} />
        <p className="ws-help">{PREFERENCE_CATEGORIES[domainKey]} · {codingProfile ? '개발 환경과 직접 고른 선호, 지금 보이는 지침을 저장합니다.' : '프롬프트 언어를 바꾸면 현재 보이는 내용이 저장됩니다.'}</p>
        <div className="prompt-actions">
          <button className="prompt-copy-button" type="submit" disabled={busy || user === undefined || !title.trim() || !prompt.trim() || unchanged}>
            {busy ? '저장하는 중…' : unchanged ? '보관함에 저장했어요' : user ? '내 선호 보관함에 저장' : '로그인하고 보관함에 저장'}
          </button>
          {saved && onOpenLibrary && <button className="prompt-reset-button" type="button" onClick={() => onOpenLibrary(saved.id)}>저장한 지침 열기</button>}
        </div>
      </form>
      {error && <p className="ws-error" role="alert">{error}</p>}
      {unchanged && <p className="ws-help" role="status">저장 완료 · 다른 작업에도 같은 방식을 사용할 수 있어요.</p>}
      {loginOpen && !user && <AuthSection embedded signupOpen={signupOpen}
        reason="지금 만든 프롬프트는 그대로 남아 있어요. 로그인한 뒤 위 저장 버튼을 눌러 주세요."
        onBack={() => setLoginOpen(false)} onDone={(nextUser) => { onLogin(nextUser); setLoginOpen(false); }} />}
    </div>
  );
}

export default SavePreferencePanel;

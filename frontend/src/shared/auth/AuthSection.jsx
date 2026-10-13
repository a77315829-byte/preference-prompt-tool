import { useState } from 'react';
import { login, signup } from './authApi';

// 로그인 · 가입. 로그인이 필요한 기능(지금은 작업 공간 저장·다시 열기)에서 넘어오고,
// 끝나면 onDone 으로 원래 화면에 돌아간다. 비교·데모·다듬기는 로그인 없이 쓴다.
// embedded: 다른 화면 안에 펼치는 형태. 화면을 옮기면 그 화면의 작업 중 상태가
// 사라지므로, 작업 공간처럼 잃으면 안 되는 곳에서는 그 자리에서 로그인한다.
function AuthSection({ onDone, onBack, signupOpen = true, reason, embedded = false }) {
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const isSignup = mode === 'signup';
  const mismatch = isSignup && confirm && confirm !== password;

  const submit = async (event) => {
    event.preventDefault();
    if (mismatch) return;
    setBusy(true);
    setError('');
    try {
      const data = await (isSignup ? signup : login)(username.trim(), password);
      setPassword('');
      setConfirm('');
      onDone(data.user);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const form = (
        <form className="auth-form" onSubmit={submit}>
          <label className="task-input-label" htmlFor="auth-username">아이디</label>
          <input id="auth-username" className="ws-input" autoComplete="username" value={username}
            maxLength={30} onChange={(e) => setUsername(e.target.value)} />
          {isSignup && <p className="ws-help">영문·숫자·_ . - 로 3~30자</p>}

          <label className="task-input-label" htmlFor="auth-password">비밀번호</label>
          <input id="auth-password" className="ws-input" type="password" maxLength={128}
            autoComplete={isSignup ? 'new-password' : 'current-password'}
            value={password} onChange={(e) => setPassword(e.target.value)} />
          {isSignup && (
            <>
              <p className="ws-help">8자 이상, 아이디와 다르게</p>
              <label className="task-input-label" htmlFor="auth-confirm">비밀번호 확인</label>
              <input id="auth-confirm" className="ws-input" type="password" maxLength={128} autoComplete="new-password"
                value={confirm} onChange={(e) => setConfirm(e.target.value)} />
              {mismatch && <p className="ws-error">비밀번호가 서로 다릅니다.</p>}
            </>
          )}

          {error && <p className="ws-error" role="alert">{error}</p>}
          <div className="prompt-actions">
            <button className="prompt-copy-button" type="submit"
              disabled={busy || !username.trim() || !password || mismatch || (isSignup && !confirm)}>
              {busy ? '확인 중…' : isSignup ? '가입하고 시작' : '로그인'}
            </button>
            {(signupOpen || isSignup) && (
              <button className="prompt-reset-button" type="button" onClick={() => { setMode(isSignup ? 'login' : 'signup'); setError(''); }}>
                {isSignup ? '이미 계정이 있어요' : '계정 만들기'}
              </button>
            )}
          </div>
          <p className="ws-help">
            계정은 이 서버에 저장됩니다. 비밀번호는 원문이 아니라 해시로만 저장합니다.
          </p>
        </form>
  );

  if (embedded) {
    return (
      <div className="ws-block auth-embedded">
        <div className="ws-block-head">
          <strong>{isSignup ? '계정 만들기' : '로그인'}</strong>
          {onBack && <button className="ws-small-button" type="button" onClick={onBack}>닫기</button>}
        </div>
        {reason && <p className="ws-help">{reason}</p>}
        {form}
      </div>
    );
  }

  return (
    <section className="comparison-section auth-section" id="auth-section">
      <div className="comparison-inner">
        <button className="back-button" type="button" onClick={onBack}>← 돌아가기</button>
        <div className="comparison-heading">
          <p className="eyebrow">ACCOUNT</p>
          <h2>{isSignup ? '계정 만들기' : '로그인'}</h2>
          <p>{reason || '로그인하면 만든 프롬프트 프로젝트를 저장하고 다시 열 수 있습니다. 비교와 데모는 로그인 없이 쓸 수 있습니다.'}</p>
        </div>
        {form}
      </div>
    </section>
  );
}

export default AuthSection;

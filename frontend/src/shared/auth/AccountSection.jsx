import { useEffect, useState } from 'react';
import { changePassword, deleteAccount, fetchMe } from './authApi';

// 내 계정: 비밀번호 변경과 탈퇴. 둘 다 지금 비밀번호를 다시 받는다 - 로그인된 화면만
// 가진 사람이 바꾸거나 지우지 못하게.
function AccountSection({ user, onBack, onDeleted }) {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [deletePassword, setDeletePassword] = useState('');
  const [understood, setUnderstood] = useState(false);
  const [ownedShared, setOwnedShared] = useState(0);
  const [state, setState] = useState({ busy: '', error: '', done: '' });

  useEffect(() => {
    fetchMe().then((data) => setOwnedShared(data.ownedShared || 0)).catch(() => {});
  }, []);

  const run = async (busy, fn) => {
    setState({ busy, error: '', done: '' });
    try {
      const done = await fn();
      setState({ busy: '', error: '', done: done || '' });
    } catch (e) {
      setState({ busy: '', error: e.message || '문제가 발생했습니다.', done: '' });
    }
  };

  const mismatch = confirm && confirm !== next;

  const submitPassword = (event) => {
    event.preventDefault();
    if (mismatch) return;
    run('password', async () => {
      await changePassword(current, next);
      setCurrent('');
      setNext('');
      setConfirm('');
      return '비밀번호를 바꿨습니다. 다른 기기의 로그인은 모두 끊겼습니다.';
    });
  };

  const submitDelete = (event) => {
    event.preventDefault();
    if (!window.confirm(`'${user.username}' 계정과 저장한 프로젝트를 모두 지웁니다. 되돌릴 수 없습니다.`)) return;
    run('delete', async () => {
      await deleteAccount(deletePassword);
      onDeleted();
    });
  };

  return (
    <section className="comparison-section auth-section" id="account-section">
      <div className="comparison-inner">
        <button className="back-button" type="button" onClick={onBack}>← 돌아가기</button>
        <div className="comparison-heading">
          <p className="eyebrow">ACCOUNT</p>
          <h2>내 계정</h2>
          <p>{user.username} 님으로 로그인되어 있습니다.</p>
        </div>

        {state.error && <p className="ws-error" role="alert">{state.error}</p>}
        {state.done && <p className="ws-banner" role="status"><span>{state.done}</span></p>}

        <form className="auth-form ws-step" onSubmit={submitPassword}>
          <p className="question-eyebrow">비밀번호 변경</p>
          <label className="task-input-label" htmlFor="acc-current">지금 비밀번호</label>
          <input id="acc-current" className="ws-input" type="password" autoComplete="current-password"
            maxLength={128} value={current} onChange={(e) => setCurrent(e.target.value)} />
          <label className="task-input-label" htmlFor="acc-new">새 비밀번호</label>
          <input id="acc-new" className="ws-input" type="password" autoComplete="new-password"
            maxLength={128} value={next} onChange={(e) => setNext(e.target.value)} />
          <p className="ws-help">8자 이상, 아이디·지금 비밀번호와 다르게. 바꾸면 다른 기기의 로그인이 모두 끊깁니다.</p>
          <label className="task-input-label" htmlFor="acc-confirm">새 비밀번호 확인</label>
          <input id="acc-confirm" className="ws-input" type="password" autoComplete="new-password"
            maxLength={128} value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          {mismatch && <p className="ws-error">새 비밀번호가 서로 다릅니다.</p>}
          <div className="prompt-actions">
            <button className="prompt-copy-button" type="submit"
              disabled={Boolean(state.busy) || !current || !next || !confirm || mismatch}>
              {state.busy === 'password' ? '바꾸는 중…' : '비밀번호 바꾸기'}
            </button>
          </div>
        </form>

        <form className="auth-form ws-step" onSubmit={submitDelete}>
          <p className="question-eyebrow">탈퇴</p>
          <p className="ws-help">
            계정과 저장한 프로젝트·버전·자동 저장본이 모두 지워지고 되돌릴 수 없습니다.
            남이 나에게 공유한 프로젝트는 지워지지 않습니다.
          </p>
          {ownedShared > 0 && (
            <p className="ws-error">
              내가 만들어 다른 사람에게 공유한 프로젝트 {ownedShared}개가 그 사람들에게서도 사라집니다.
              남겨야 하면 먼저 그 사람이 "내 사본으로 저장"하게 해 주세요.
            </p>
          )}
          <label className="task-input-label" htmlFor="acc-delete">지금 비밀번호</label>
          <input id="acc-delete" className="ws-input" type="password" autoComplete="current-password"
            maxLength={128} value={deletePassword} onChange={(e) => setDeletePassword(e.target.value)} />
          <label className="ws-check-row">
            <input type="checkbox" checked={understood} onChange={(e) => setUnderstood(e.target.checked)} />
            되돌릴 수 없다는 것을 확인했습니다.
          </label>
          <div className="prompt-actions">
            <button className="prompt-reset-button ws-danger" type="submit"
              disabled={Boolean(state.busy) || !deletePassword || !understood}>
              {state.busy === 'delete' ? '지우는 중…' : '계정 지우기'}
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}

export default AccountSection;

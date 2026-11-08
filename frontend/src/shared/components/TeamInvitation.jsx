import { useState } from 'react';
import { setTeamInvitation, teamInviteUrl } from '../teams';

function TeamInvitation({ team, onChange }) {
  const [status, setStatus] = useState('');
  const [access, setAccess] = useState(null);
  const [busy, setBusy] = useState(false);
  const current = access || team;
  const link = teamInviteUrl(team.code, window.location.href);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      setStatus('초대 링크를 복사했어요. 팀원에게 전달해 주세요.');
    } catch {
      setStatus('복사하지 못했어요. 아래 초대 링크를 직접 선택해 복사해 주세요.');
    }
  };
  return (
    <div className="team-invitation">
      <h3>팀원 초대하기</h3>
      <p className="ws-help">{team.protected ? '팀 결과는 로그인한 참여자만 볼 수 있어요. 초대받은 사람은 비교를 마치고 선호를 합친 뒤 참여자가 됩니다. 초대는 7일간 열리며 팀장이 닫을 수 있어요.' : '익명으로 만든 공개 체험 팀입니다. 링크로 팀 기준을 볼 수 있으니 민감한 팀 이름이나 정보를 넣지 마세요. 계정으로 팀을 만들면 참여자만 결과를 볼 수 있어요.'}</p>
      {team.protected && <p className="ws-help" role="status">{current.invite_open ? `초대 열림 · ${new Date(current.invite_until * 1000).toLocaleString('ko-KR')}까지` : '초대 닫힘 · 새 참여를 받지 않아요. 기존 참여자는 계속 볼 수 있어요.'}</p>}
      <label className="task-input-label" htmlFor={`invite-${team.code}`}>초대 링크</label>
      <input id={`invite-${team.code}`} className="ws-input" readOnly value={link} onFocus={(e) => e.target.select()} />
      <div className="prompt-actions">
        <button className="prompt-reset-button" type="button" disabled={team.protected && !current.invite_open} onClick={copy}>초대 링크 복사</button>
        {team.can_manage && <button className="prompt-reset-button" type="button" disabled={busy} onClick={async () => {
          setBusy(true);
          try { const next = await setTeamInvitation(team.code, !current.invite_open); setAccess(next); onChange?.(next); setStatus('초대 설정을 바꿨어요.'); }
          catch (e) { setStatus(e.message); }
          finally { setBusy(false); }
        }}>{current.invite_open ? '새 참여 초대 닫기' : '같은 초대를 7일간 다시 열기'}</button>}
        <span className="ws-help">팀 코드: <code>{team.code}</code></span>
      </div>
      {status && <p className="ws-help" role="status">{status}</p>}
      {new URL(link).hostname.match(/^(localhost|127\.0\.0\.1|\[::1\])$/) && (
        <p className="ws-help">현재는 내 컴퓨터의 주소입니다. 다른 기기의 팀원에게 초대하려면 팀원이 접속할 수 있는 서비스 주소에서 링크를 복사하세요.</p>
      )}
    </div>
  );
}

export default TeamInvitation;

import { useState } from 'react';
import { teamInviteUrl } from '../teams';

function TeamInvitation({ team }) {
  const [status, setStatus] = useState('');
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
      <p className="ws-help">링크를 받은 팀원은 같은 비교 항목으로 참여할 수 있어요. 링크로 팀 기준을 볼 수 있으니 참여할 팀원에게 전달해 주세요.</p>
      <label className="task-input-label" htmlFor={`invite-${team.code}`}>초대 링크</label>
      <input id={`invite-${team.code}`} className="ws-input" readOnly value={link} onFocus={(e) => e.target.select()} />
      <div className="prompt-actions">
        <button className="prompt-reset-button" type="button" onClick={copy}>초대 링크 복사</button>
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

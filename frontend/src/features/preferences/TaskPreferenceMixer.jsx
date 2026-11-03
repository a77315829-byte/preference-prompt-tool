import { useEffect, useRef, useState } from 'react';
import { axisValueLabel } from '../../shared/domainLabels';
import { composeTaskPreference } from './preferencesApi';

function TaskPreferenceMixer({ item, comparison, disabled, onChange }) {
  const [choices, setChoices] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);
  const request = useRef(0);
  useEffect(() => () => { request.current += 1; }, []);
  const differing = comparison.axes.filter((a) => a.personal_value !== a.team_value);
  const complete = differing.every((a) => choices[a.axis]);
  const label = (axis, value) => value ? axisValueLabel(axis, value) : '정하지 않음 (해당 지시 제외)';
  const choose = (axis, source) => {
    request.current += 1; setBusy(false); setReady(false); setError('');
    setChoices((current) => ({ ...current, [axis]: source })); onChange(null);
  };
  const compose = async () => {
    const token = ++request.current;
    setBusy(true); setError(''); setReady(false); onChange(null);
    try {
      const draft = await composeTaskPreference(item, comparison, choices);
      if (token === request.current) { setReady(true); onChange(draft); }
    } catch (e) { if (token === request.current) setError(e.message); }
    finally { if (token === request.current) setBusy(false); }
  };
  return <div className="task-preference-mixer">
    <h4>항목별로 골라 이번 작업용 만들기</h4>
    <p className="ws-help">다른 항목마다 따를 쪽을 고르세요. 같은 항목은 그대로 반영하고 기존 개인 지침과 팀 기준은 유지합니다. 조합한 뒤 이름을 붙여 새 항목으로 보관할 수도 있어요.</p>
    {!comparison.personal_recognized ? <p className="ws-help">직접 수정·추가하거나 최적화한 지침은 항목을 정확히 구분할 수 없어 조합할 수 없어요. 본문 차이를 확인하고 개인용 또는 팀용 전체를 선택해 주세요.</p> : <>
      {differing.length === 0 ? <p>다른 항목이 없어요. 같은 기준으로 이번 작업용 지침을 만들 수 있습니다.</p> : differing.map((a) => (
        <fieldset key={a.axis} disabled={disabled || busy} className="preference-axis-choice">
          <legend>{a.label}</legend>
          {['personal', 'team'].map((source) => <label key={source}>
            <input type="radio" name={`task-choice-${a.axis}`} value={source} checked={choices[a.axis] === source}
              onChange={() => choose(a.axis, source)} />
            {source === 'personal' ? '내 선호' : '팀 기준'}: {label(a.axis, a[`${source}_value`])}
          </label>)}
          {!a.team_agreed && <p className="ws-help">팀의 합의가 끝나지 않은 항목입니다. 팀 기준을 골라도 합의 상태는 바뀌지 않습니다.</p>}
        </fieldset>
      ))}
      <p className="ws-help" role="status">{ready ? '이번 작업용을 선택했어요. 아래에서 지침을 확인하고 복사·실행하세요.' : `다른 항목 ${differing.length}개 중 ${differing.filter((a) => choices[a.axis]).length}개 선택`}</p>
      <button className="prompt-copy-button" type="button" disabled={disabled || busy || !complete} onClick={compose}>
        {busy ? '작업용 만드는 중…' : '이번 작업용 만들기'}
      </button>
    </>}
    {error && <p className="ws-error" role="alert">{error}</p>}
  </div>;
}

export default TaskPreferenceMixer;

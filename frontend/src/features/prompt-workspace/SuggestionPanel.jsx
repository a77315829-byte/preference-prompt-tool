import { useState } from 'react';
import { ChecksTable, RunColumn } from './CompareView';
import { lineDiff } from './lineDiff';
import { applySuggestions, runProject, suggestImprovements, trialSuggestions } from './workspaceApi';

// 개선 방향 추천 (계획서 10절 2차).
// 1) AI 가 고칠 곳을 제안한다 - 범주, 이유, 바꿀 문장.
// 2) 사용자가 적용할 제안을 고르면 수정안(지침 후보)을 만든다. 프로젝트는 아직 안 바뀐다.
// 3) 지금 지침과 수정안을 같은 입력으로 시험해 결과를 나란히 본다.
// 4) 사용자가 "이 수정안 적용"을 눌러야 바뀐다 (저장된 프로젝트면 새 버전으로 저장).
// 필수 규칙 문장을 바꾸는 제안은 코드가 찾아 따로 확인받는다.

function SuggestionPanel({ project, inputText, live, disabled, onApply }) {
  const [state, setState] = useState({ busy: '', error: '' });
  const [result, setResult] = useState(null); // { suggestions, notes, artifact_revision }
  const [picked, setPicked] = useState({});
  const [allowRules, setAllowRules] = useState(false);
  const [candidate, setCandidate] = useState(null); // { system_prompt, touches_rules }
  const [trial, setTrial] = useState(null); // { current, candidate }
  // 제안마다 같은 입력으로 시험한 결과: id -> { tested, fixed, broke, fail_before, fail_after }
  const [verdicts, setVerdicts] = useState({});

  const artifact = project.artifact;
  const outdated = result && result.artifact_revision !== artifact.revision;
  const chosen = (result?.suggestions || []).filter((s) => picked[s.id]);
  const touchesRules = chosen.some((s) => s.touches_rules.length > 0);

  const act = async (busy, fn) => {
    setState({ busy, error: '' });
    try {
      await fn();
      setState({ busy: '', error: '' });
    } catch (e) {
      setState({ busy: '', error: e.message || '문제가 발생했습니다.' });
    }
  };

  const ask = () => act('suggest', async () => {
    const data = await suggestImprovements(project);
    setResult(data);
    setVerdicts({});
    setPicked({});
    setCandidate(null);
    setTrial(null);
    setAllowRules(false);
  });

  const build = () => act('apply', async () => {
    const data = await applySuggestions(project, chosen, allowRules);
    setCandidate(data);
    setTrial(null);
  });

  const parseInput = () => {
    try {
      return JSON.parse(inputText);
    } catch (e) {
      throw new Error(`시험 입력이 올바른 JSON이 아닙니다: ${e.message}`);
    }
  };

  // 지금 지침의 결과가 같은 입력으로 이미 있으면 다시 부르지 않는다.
  const tryBoth = () => act('trial', async () => {
    const values = parseInput();
    const reusable = [...project.runs].reverse().find((r) => r.artifact_revision === artifact.revision
      && r.requirements_revision === project.requirements_revision && r.input_text === inputText);
    const current = reusable || (await runProject(project, values)).run;
    const candidateProject = { ...project, artifact: { ...artifact, system_prompt: candidate.system_prompt, revision: artifact.revision + 1 } };
    const next = (await runProject(candidateProject, values)).run;
    setTrial({ current: { ...current, input_text: inputText }, candidate: { ...next, input_text: inputText } });
  });

  // 좋아졌는지는 모델의 말이 아니라 시험으로 판단한다. 지금 지침 1회 + 시험할 제안 수만큼 부른다.
  const testable = (result?.suggestions || []).filter((s) => s.applicable && s.touches_rules.length === 0);
  const trialAll = () => act('trialAll', async () => {
    const data = await trialSuggestions(project, parseInput(), result.suggestions);
    setVerdicts(Object.fromEntries(data.results.map((r) => [r.id, r])));
  });

  const labels = chosen.map((s) => s.id).join(', ');
  const diff = candidate ? lineDiff(artifact.system_prompt, candidate.system_prompt) : null;

  return (
    <div className="ws-block ws-suggest">
      <div className="ws-block-head">
        <strong>개선 방향 추천</strong>
        <button className="ws-small-button" type="button" disabled={disabled || Boolean(state.busy)} onClick={ask}>
          {state.busy === 'suggest' ? '살펴보는 중…' : `${result ? '다시 ' : ''}추천받기${live ? ' (AI)' : ' (코드 점검만)'}`}
        </button>
      </div>
      <p className="ws-help">
        {live
          ? 'AI 가 고칠 곳을 제안합니다. 적용할 것을 고르고, 지금 지침과 수정안을 같은 입력으로 시험해 비교한 뒤 적용하세요. 마지막 시험의 실패 항목을 먼저 다룹니다.'
          : '코드로 확인할 수 있는 것(빠진 출력 형식·필수 규칙)만 찾습니다. AI 추천은 실제 생성 모드에서 나옵니다.'}
      </p>
      {state.error && <p className="ws-error">{state.error}</p>}
      {outdated && <p className="ws-error">추천을 받은 뒤 지침이 바뀌었습니다. 다시 추천받으세요.</p>}
      {result?.notes?.map((n) => <p className="ws-help" key={n}>{n}</p>)}
      {result && result.suggestions.length === 0 && <p className="ws-help">고칠 곳을 제안하지 않았습니다.</p>}
      {live && result && !outdated && testable.length > 0 && (
        <div className="prompt-actions">
          <button className="prompt-reset-button" type="button" disabled={Boolean(state.busy)} onClick={trialAll}>
            {state.busy === 'trialAll' ? '시험 중…' : `제안마다 시험해 보기 (AI ${testable.length + 1}회)`}
          </button>
          <span className="ws-help">지금 시험 입력으로 제안을 하나씩 적용해 돌리고, 검사가 어떻게 바뀌는지 셉니다.</span>
        </div>
      )}

      {result && !outdated && result.suggestions.map((s) => (
        <div className={`ws-suggestion ${s.applicable ? '' : 'is-advice'}`} key={s.id}>
          <label className="ws-check-row">
            <input type="checkbox" disabled={!s.applicable} checked={Boolean(picked[s.id])}
              onChange={(e) => { setPicked((p) => ({ ...p, [s.id]: e.target.checked })); setCandidate(null); setTrial(null); }} />
            <span>
              <span className={`ws-origin ${s.source === 'code' ? 'ws-origin-extracted' : 'ws-origin-suggested'}`}>
                {s.source === 'code' ? '코드 점검' : 'AI 제안'}
              </span>{' '}
              <span className="ws-origin ws-origin-user">{s.category_label}</span>{' '}
              <strong>{s.id} {s.title}</strong>
            </span>
          </label>
          {s.reason && <p className="ws-suggestion-reason">{s.reason}</p>}
          {s.edits.map((e, i) => (
            <pre className="ws-diff" key={i}>
              {e.find && <div className="ws-diff-removed">- {e.find}</div>}
              {e.replace && <div className="ws-diff-added">+ {e.replace}</div>}
            </pre>
          ))}
          {!s.applicable && <p className="ws-help">적용 불가 - {s.problem}. 읽을거리로만 참고하세요.</p>}
          {verdicts[s.id] && (verdicts[s.id].tested ? (
            <p className={`ws-verdict ${verdicts[s.id].broke.length ? 'is-worse' : verdicts[s.id].fixed.length ? 'is-better' : ''}`}>
              시험 결과: 실패 {verdicts[s.id].fail_before} → {verdicts[s.id].fail_after}
              {verdicts[s.id].fixed.length > 0 && ` · 고친 검사: ${verdicts[s.id].fixed.join(', ')}`}
              {verdicts[s.id].broke.length > 0 && ` · 새로 실패: ${verdicts[s.id].broke.join(', ')}`}
              {!verdicts[s.id].fixed.length && !verdicts[s.id].broke.length && ' · 검사 결과 변화 없음'}
            </p>
          ) : <p className="ws-help">시험 안 함 - {verdicts[s.id].reason}</p>)}
          {s.touches_rules.length > 0 && (
            <p className="ws-error">보호 문장({s.touches_rules.join(", ")})을 지우거나 바꿉니다.</p>
          )}
        </div>
      ))}

      {chosen.length > 0 && (
        <>
          {touchesRules && (
            <label className="ws-check-row">
              <input type="checkbox" checked={allowRules} onChange={(e) => setAllowRules(e.target.checked)} />
              보호 문장(필수 규칙·안전 문장)이 바뀌는 것을 확인했습니다. 필수 규칙이면 요구사항도 함께 고쳐야 어긋나지 않습니다.
            </label>
          )}
          <div className="prompt-actions">
            <button className="prompt-copy-button" type="button" disabled={Boolean(state.busy) || (touchesRules && !allowRules)} onClick={build}>
              {state.busy === 'apply' ? '만드는 중…' : `고른 제안(${labels})으로 수정안 만들기`}
            </button>
          </div>
        </>
      )}

      {candidate && (
        <>
          <p className="ws-compare-section">지침 차이 (지금 → 수정안)</p>
          <pre className="ws-diff">
            {diff.map((d, i) => (
              <div key={i} className={`ws-diff-${d.type}`}>{d.type === 'added' ? '+ ' : d.type === 'removed' ? '- ' : '  '}{d.text}</div>
            ))}
          </pre>
          <p className="ws-help">문장이 남아 있다고 뜻이 보존된 것은 아닙니다. 같은 입력으로 시험해 결과로 비교하세요.</p>
          <div className="prompt-actions">
            <button className="prompt-reset-button" type="button" disabled={Boolean(state.busy)} onClick={tryBoth}>
              {state.busy === 'trial' ? '시험 중…' : live ? '지금 지침과 수정안 시험 (AI)' : '두 지침의 메시지 구성 비교'}
            </button>
            <button className="prompt-copy-button" type="button" disabled={Boolean(state.busy)}
              onClick={() => onApply(candidate.system_prompt, trial?.candidate || null, `추천 적용: ${labels}`)}>
              이 수정안 적용
            </button>
          </div>
          {trial && (
            <>
              <div className="ws-compare-cols">
                <RunColumn title="지금 지침" run={trial.current} />
                <RunColumn title="수정안" run={trial.candidate} />
              </div>
              <ChecksTable a={trial.current} b={trial.candidate} labels={['지금', '수정안']} />
            </>
          )}
        </>
      )}
    </div>
  );
}

export default SuggestionPanel;

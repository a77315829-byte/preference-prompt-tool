import { useEffect, useMemo, useState } from 'react';
import { lineDiff } from './lineDiff';
import { fetchVersion } from './workspaceApi';

// 두 시점을 나란히 본다: 지금 편집 중 / 이 프로젝트의 시험 기록 / 저장한 버전.
// 무엇이 바뀌었는지(지침·요구사항)와 결과가 어떻게 달라졌는지(출력·검사)를 같이 보여 준다.
// 입력이 다른 두 실행은 결과 차이를 프롬프트 탓으로 단정할 수 없으므로 그렇게 알린다.

const STATUS_LABEL = { pass: '통과', fail: '실패', not_evaluated: '미평가' };
const RUN_STATUS = { ran: '모델 실행', preview: '메시지 구성만', input_error: '입력 오류', needs_review: '입력 확인 필요' };

const lastRun = (project) => (project?.runs?.length ? project.runs[project.runs.length - 1] : null);

function sideFrom(option, project, snapshot) {
  if (option.kind === 'current') {
    return { system: project.artifact?.system_prompt ?? null, run: lastRun(project), requirements: project.requirements };
  }
  if (option.kind === 'run') {
    const run = project.runs[option.index];
    return { system: run?.messages?.[0]?.content ?? null, run, requirements: null };
  }
  if (!snapshot) return null;
  return { system: snapshot.artifact?.system_prompt ?? null, run: lastRun(snapshot), requirements: snapshot.requirements };
}

function textsOf(requirements, key) {
  return new Set((requirements?.[key] || []).map((i) => (key === 'variables' ? i.name : i.text.trim())));
}

function RequirementDiff({ a, b }) {
  const rows = [['hard_rules', '필수 규칙'], ['preferences', '선호'], ['variables', '변수'], ['open_questions', '미결 사항']]
    .map(([key, label]) => {
      const before = textsOf(a, key);
      const after = textsOf(b, key);
      return {
        label,
        removed: [...before].filter((t) => !after.has(t)),
        added: [...after].filter((t) => !before.has(t)),
      };
    })
    .filter((r) => r.added.length || r.removed.length);
  const answered = (b?.resolved_questions || []).filter(
    (q) => !(a?.resolved_questions || []).some((x) => x.id === q.id && x.answer === q.answer),
  );
  if (!rows.length && !answered.length) return <p className="ws-help">요구사항은 같습니다.</p>;
  return (
    <ul className="ws-diff-list">
      {rows.map((r) => (
        <li key={r.label}>
          <strong>{r.label}</strong>
          {r.removed.map((t) => <div key={`-${t}`} className="ws-diff-removed">- {t}</div>)}
          {r.added.map((t) => <div key={`+${t}`} className="ws-diff-added">+ {t}</div>)}
        </li>
      ))}
      {answered.map((q) => (
        <li key={q.id}>
          <strong>답한 질문 {q.id}</strong>
          <div>{q.text}</div>
          <div className="ws-diff-added">답: {q.answer}{q.resolved_as ? ` → ${q.resolved_as}` : ' (프롬프트에 넣지 않음)'}</div>
        </li>
      ))}
    </ul>
  );
}

// 두 실행의 검사 결과를 이름으로 맞춰 나란히. 결과가 달라진 줄을 강조한다.
export function ChecksTable({ a, b, labels = ['기준', '비교'] }) {
  const names = [...new Set([...(a?.checks || []), ...(b?.checks || [])].map((c) => c.name))];
  if (!names.length) return null;
  const statusIn = (run, name) => run?.checks?.find((c) => c.name === name)?.status;
  return (
    <table className="ws-table">
      <thead><tr><th>검사</th><th>{labels[0]}</th><th>{labels[1]}</th></tr></thead>
      <tbody>
        {names.map((name) => {
          const before = statusIn(a, name);
          const after = statusIn(b, name);
          return (
            <tr key={name} className={before !== after ? 'ws-row-changed' : ''}>
              <td>{name}</td>
              <td>{before ? STATUS_LABEL[before] : '-'}</td>
              <td>{after ? STATUS_LABEL[after] : '-'}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function RunColumn({ title, run }) {
  if (!run) return <div className="ws-compare-col"><strong>{title}</strong><p className="ws-help">시험 기록이 없습니다.</p></div>;
  return (
    <div className="ws-compare-col">
      <strong>{title}</strong>
      <p className="ws-help">
        {RUN_STATUS[run.status] || run.status}
        {run.model ? ` · ${run.model}` : ''}
        {` · 프롬프트 rev ${run.artifact_revision}`}
      </p>
      <pre className="prompt-box ws-compare-output"><code>{run.output || '(모델 출력 없음)'}</code></pre>
    </div>
  );
}

function CompareView({ project, projectId, versions }) {
  const options = useMemo(() => [
    { key: 'current', kind: 'current', label: '지금 편집 중 (저장 안 됨)' },
    ...project.runs.map((run, index) => ({
      key: `run-${run.id}`, kind: 'run', index,
      label: `시험 #${index + 1} · rev ${run.artifact_revision} · ${RUN_STATUS[run.status] || run.status}`,
    })),
    ...(versions || []).map((v) => ({
      key: `v-${v.version}`, kind: 'version', version: v.version,
      label: `저장 v${v.version}${v.label ? ` · ${v.label}` : ''}`,
    })),
  ], [project.runs, versions]);

  const [leftKey, setLeftKey] = useState('');
  const [rightKey, setRightKey] = useState('current');
  const [snapshots, setSnapshots] = useState({});
  const [error, setError] = useState('');

  // 기본 비교: 직전 시험(없으면 마지막 저장본)과 지금.
  useEffect(() => {
    if (leftKey && options.some((o) => o.key === leftKey)) return;
    const fallback = options.filter((o) => o.key !== 'current');
    setLeftKey(fallback.length ? fallback[fallback.length - 1].key : 'current');
  }, [options, leftKey]);

  useEffect(() => {
    [leftKey, rightKey].forEach((key) => {
      const option = options.find((o) => o.key === key);
      if (option?.kind !== 'version' || snapshots[option.version] || !projectId) return;
      fetchVersion(projectId, option.version)
        .then(({ project: snap }) => setSnapshots((s) => ({ ...s, [option.version]: snap })))
        .catch((e) => setError(e.message));
    });
  }, [leftKey, rightKey, options, projectId, snapshots]);

  const pick = (key) => {
    const option = options.find((o) => o.key === key);
    if (!option) return null;
    return sideFrom(option, project, option.kind === 'version' ? snapshots[option.version] : null);
  };
  const a = pick(leftKey);
  const b = pick(rightKey);

  const diff = a?.system != null && b?.system != null ? lineDiff(a.system, b.system) : null;
  const changedLines = diff ? diff.filter((d) => d.type !== 'same').length : 0;

  const differentInput = a?.run && b?.run && a.run.input_hash !== b.run.input_hash;
  const sameRun = a?.run && b?.run && a.run.id === b.run.id;

  const picker = (value, onChange, label) => (
    <label className="ws-compare-pick">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => <option key={o.key} value={o.key}>{o.label}</option>)}
      </select>
    </label>
  );

  return (
    <div className="ws-block ws-compare">
      <strong>이전 결과와 비교</strong>
      <div className="ws-compare-pickers">
        {picker(leftKey, setLeftKey, '기준')}
        {picker(rightKey, setRightKey, '비교')}
      </div>
      {error && <p className="ws-error">{error}</p>}
      {(!a || !b) && <p className="ws-help">저장한 버전을 불러오는 중…</p>}

      {a && b && (
        <>
          <p className="ws-compare-section">지침 차이</p>
          {diff === null && <p className="ws-help">한쪽에 지침이 없습니다 (입력 오류로 멈춘 시험이거나 아직 만들지 않은 버전).</p>}
          {diff && changedLines === 0 && <p className="ws-help">지침이 같습니다.</p>}
          {diff && changedLines > 0 && (
            <pre className="ws-diff">
              {diff.map((d, i) => (
                <div key={i} className={`ws-diff-${d.type}`}>{d.type === 'added' ? '+ ' : d.type === 'removed' ? '- ' : '  '}{d.text}</div>
              ))}
            </pre>
          )}

          {a.requirements && b.requirements && (
            <>
              <p className="ws-compare-section">요구사항 차이</p>
              <RequirementDiff a={a.requirements} b={b.requirements} />
            </>
          )}

          <p className="ws-compare-section">결과</p>
          {sameRun && <p className="ws-help">두 쪽이 같은 시험 기록입니다.</p>}
          {differentInput && (
            <p className="ws-error">두 시험의 입력이 다릅니다. 결과 차이를 프롬프트 변경 때문이라고 단정할 수 없습니다.</p>
          )}
          <div className="ws-compare-cols">
            <RunColumn title="기준" run={a.run} />
            <RunColumn title="비교" run={b.run} />
          </div>

          <ChecksTable a={a.run} b={b.run} />
        </>
      )}
    </div>
  );
}

export default CompareView;

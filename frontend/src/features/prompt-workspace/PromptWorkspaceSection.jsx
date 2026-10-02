import { motion } from 'motion/react';
import { useEffect, useState } from 'react';
import {
  buildProject, checkProject, confirmProject, exportProject, fetchHealth, fetchSample,
  runProject, structureDescription,
} from './workspaceApi';

// 서비스에 연결할 프롬프트 만들기 (docs/developer_prompt_workspace_plan.md 1차).
// 설명 입력 -> 요구사항 확인 -> 프롬프트 생성·시험·내보내기.
// 확인 전 요구사항은 초안이고, 실행하지 않은 검사는 통과로 적지 않는다.

const ORIGIN_LABEL = { extracted: '입력에서 추출', suggested: 'AI 제안', user: '직접 입력' };
const STATUS_LABEL = { pass: '통과', fail: '실패', not_evaluated: '미평가' };
const GROUP_LABEL = { input: '입력 확인', contract: '형식 (출력 계약)', meaning: '의미 (값 대조)', rules: '필수 규칙' };
const RUN_LABEL = {
  ran: '모델 실행 완료',
  preview: '메시지 구성만 (모델 실행 안 함)',
  input_error: '입력 오류 - 모델을 부르지 않았습니다',
  needs_review: '확인이 필요한 입력 - 모델을 부르지 않았습니다',
};
const MAX_RUNS = 5;

const clone = (value) => JSON.parse(JSON.stringify(value));

function download(filename, blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function stageOf(project) {
  if (!project) return 'none';
  const confirmed = project.confirmed_requirements_revision === project.requirements_revision;
  if (!project.artifact) return confirmed ? 'confirmed' : 'draft';
  return project.artifact.built_from_requirements_revision === project.requirements_revision ? 'built' : 'stale_artifact';
}

const STAGE_LABEL = {
  draft: '초안 - 요구사항 확인 전',
  confirmed: '요구사항 확인됨',
  built: '확인된 요구사항으로 생성',
  stale_artifact: '요구사항이 바뀜 - 다시 확인하고 생성하세요',
};

function OriginBadge({ item }) {
  return (
    <span className={`ws-origin ws-origin-${item.origin}`} title={item.source_excerpt ? `원문: ${item.source_excerpt}` : ''}>
      {ORIGIN_LABEL[item.origin]}
    </span>
  );
}

function ItemList({ label, items, onChange, onRemove, onAdd, sourced = true, help }) {
  return (
    <div className="ws-block">
      <div className="ws-block-head">
        <strong>{label}</strong>
        <button className="ws-small-button" type="button" onClick={onAdd}>+ 추가</button>
      </div>
      {help && <p className="ws-help">{help}</p>}
      {items.length === 0 && <p className="ws-help">없음</p>}
      {items.map((item, index) => (
        <div className="ws-item" key={item.id}>
          <span className="ws-item-id">{item.id}</span>
          <input aria-label={`${label} ${item.id}`} value={item.text} onChange={(e) => onChange(index, e.target.value)} />
          {sourced && <OriginBadge item={item} />}
          <button className="ws-small-button" type="button" aria-label={`${item.id} 삭제`} onClick={() => onRemove(index)}>삭제</button>
          {sourced && item.source_excerpt && <p className="ws-excerpt">“{item.source_excerpt}”</p>}
        </div>
      ))}
    </div>
  );
}

function ChecksView({ checks }) {
  const groups = {};
  checks.forEach((c) => { (groups[c.group] = groups[c.group] || []).push(c); });
  return Object.entries(groups).map(([group, list]) => (
    <div className="ws-block" key={group}>
      <strong>{GROUP_LABEL[group] || group}</strong>
      <ul className="ws-checks">
        {list.map((c) => (
          <li key={c.name} className={`ws-check ws-check-${c.status}`}>
            <span className="ws-check-status">{STATUS_LABEL[c.status]}</span>
            <span>{c.name}{c.detail ? ` - ${c.detail}` : ''}</span>
          </li>
        ))}
      </ul>
    </div>
  ));
}

function PromptWorkspaceSection({ onBack }) {
  const [live, setLive] = useState(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [exampleOutput, setExampleOutput] = useState('');
  const [project, setProject] = useState(null);
  const [notes, setNotes] = useState([]);
  const [inputText, setInputText] = useState('');
  const [runInputs, setRunInputs] = useState({}); // run.id -> 실행 당시 입력 글
  const [artifactDirty, setArtifactDirty] = useState(false);
  const [contractText, setContractText] = useState('');
  const [newVariable, setNewVariable] = useState('');
  const [contractError, setContractError] = useState('');
  const [includeData, setIncludeData] = useState(false);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    fetchHealth().then((h) => setLive(Boolean(h.live))).catch(() => setLive(false));
  }, []);

  const stage = stageOf(project);
  const req = project?.requirements;

  const act = async (label, fn) => {
    setBusy(label);
    setError('');
    try {
      await fn();
    } catch (e) {
      setError(e.message || '문제가 발생했습니다.');
    } finally {
      setBusy('');
    }
  };

  const adopt = (nextProject, nextNotes = []) => {
    setProject(nextProject);
    setNotes(nextNotes);
    setContractText(JSON.stringify(nextProject.requirements.output_contract.fields, null, 2));
    setContractError('');
    setArtifactDirty(false);
  };

  // 요구사항을 고치면 revision 이 오르고 확인 상태가 풀린다.
  const editRequirements = (mutate) => {
    setProject((current) => {
      const next = clone(current);
      mutate(next.requirements);
      next.requirements_revision += 1;
      return next;
    });
  };

  const editList = (key) => ({
    onChange: (index, text) => editRequirements((r) => {
      const item = r[key][index];
      item.text = text;
      if ('origin' in item) item.origin = 'user';
    }),
    onRemove: (index) => editRequirements((r) => { r[key].splice(index, 1); }),
    onAdd: () => editRequirements((r) => {
      const prefix = { hard_rules: 'R', preferences: 'P', open_questions: 'Q' }[key];
      const used = new Set(r[key].map((i) => i.id));
      let n = r[key].length + 1;
      while (used.has(`${prefix}${n}`)) n += 1;
      const item = { id: `${prefix}${n}`, text: '새 항목' };
      if (key !== 'open_questions') Object.assign(item, { origin: 'user', source_excerpt: '' });
      r[key].push(item);
    }),
  });

  const startSample = () => act('sample', async () => {
    const data = await fetchSample();
    setTitle(data.project.title);
    setDescription(data.project.raw_description);
    setExampleOutput('');
    setInputText(JSON.stringify(data.input, null, 2));
    adopt(data.project, data.notes);
  });

  const structure = () => act('structure', async () => {
    const data = await structureDescription(title, description, exampleOutput);
    adopt(data.project, data.notes);
  });

  const confirmAndBuild = () => act('build', async () => {
    const confirmed = await confirmProject(project);
    const built = await buildProject(confirmed.project);
    adopt(built.project, notes);
  });

  const editArtifact = (field, value) => {
    setProject((current) => {
      const next = clone(current);
      next.artifact[field] = value;
      // 시험 뒤 첫 수정에서 revision 을 올린다 - 이전 결과가 '이전 버전'으로 갈린다.
      if (!artifactDirty) next.artifact.revision += 1;
      return next;
    });
    setArtifactDirty(true);
  };

  const applyContract = () => {
    try {
      const fields = JSON.parse(contractText);
      if (!Array.isArray(fields)) throw new Error('필드 목록(배열)이어야 합니다.');
      editRequirements((r) => { r.output_contract.fields = fields; });
      setContractError('');
    } catch (e) {
      setContractError(`출력 계약을 읽지 못했습니다: ${e.message}`);
    }
  };

  const runTest = () => act('run', async () => {
    let values;
    try {
      values = JSON.parse(inputText);
    } catch (e) {
      throw new Error(`시험 입력이 올바른 JSON이 아닙니다: ${e.message}`);
    }
    const { run } = await runProject(project, values);
    setRunInputs((current) => ({ ...current, [run.id]: inputText }));
    setProject((current) => ({ ...current, runs: [...current.runs, run].slice(-MAX_RUNS) }));
    setArtifactDirty(false);
  });

  const exportZip = () => act('export', async () => {
    let values = null;
    try { values = JSON.parse(inputText); } catch { values = null; }
    const data = await exportProject(project, values, includeData);
    const bytes = Uint8Array.from(atob(data.zipBase64), (ch) => ch.charCodeAt(0));
    download(data.filename, new Blob([bytes], { type: 'application/zip' }));
  });

  const saveProject = () => {
    download(`${project.id}-project.json`, new Blob([JSON.stringify(project, null, 2)], { type: 'application/json' }));
  };

  const importProject = (file) => act('import', async () => {
    let parsed;
    try {
      parsed = JSON.parse(await file.text());
    } catch {
      throw new Error('프로젝트 파일이 올바른 JSON이 아닙니다.');
    }
    const data = await checkProject(parsed);
    setTitle(data.project.title);
    setDescription(data.project.raw_description);
    setExampleOutput(data.project.example_output || '');
    adopt(data.project, ['불러온 프로젝트입니다. 시험 기록의 입력 글은 함께 저장되지 않아 현재 입력과 비교할 수 없습니다.']);
  });

  const lastRun = project?.runs?.[project.runs.length - 1];
  const lastRunStale = lastRun && (
    lastRun.artifact_revision !== project.artifact?.revision
    || lastRun.requirements_revision !== project.requirements_revision
    || runInputs[lastRun.id] !== inputText
  );
  const missingRules = project?.artifact
    ? req.hard_rules.filter((r) => !project.artifact.system_prompt.includes(r.text.trim()))
    : [];

  return (
    <section className="comparison-section ws-section" id="workspace-section">
      <div className="comparison-inner">
        <button className="back-button" type="button" onClick={onBack}>← 카테고리로 돌아가기</button>
        <div className="comparison-heading">
          <p className="eyebrow">SERVICE PROMPT · 1차 MVP</p>
          <h2>서비스에 연결할 프롬프트 만들기</h2>
          <p>
            업무 설명을 요구사항으로 정리하고, 확인한 요구사항으로 변수형 프롬프트를 만들어 샘플 입력으로
            시험한 뒤 개발용 파일로 내려받습니다.
          </p>
        </div>

        {/* A. 설명 입력 */}
        <div className="ws-step">
          <p className="question-eyebrow">1. 설명 입력</p>
          <label className="task-input-label" htmlFor="ws-title">작업 이름</label>
          <input id="ws-title" className="ws-input" value={title} maxLength={100} onChange={(e) => setTitle(e.target.value)} />
          <label className="task-input-label" htmlFor="ws-desc">업무 설명 <span>(자유롭게)</span></label>
          <textarea id="ws-desc" className="task-input" rows={4} value={description} maxLength={6000}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="예: 비용 보고를 핵심부터 읽고 싶습니다. 입력에 없는 금액은 만들지 마세요. JSON으로 받고 싶습니다." />
          <label className="task-input-label" htmlFor="ws-example">좋은 결과 예시 <span>(선택)</span></label>
          <textarea id="ws-example" className="task-input" rows={2} value={exampleOutput} maxLength={6000}
            onChange={(e) => setExampleOutput(e.target.value)} />
          <p className="connection-note">
            {live === null && '서버 상태를 확인하는 중…'}
            {live === true && '요구사항 정리와 시험 실행은 AI를 호출합니다 (서버의 하루 상한에 포함).'}
            {live === false && 'API 없이 실행 중입니다. AI 정리와 모델 실행은 쓸 수 없고, 샘플로 확인·생성·메시지 구성·내보내기를 해 볼 수 있습니다.'}
          </p>
          <div className="prompt-actions">
            <button className="prompt-reset-button" type="button" disabled={Boolean(busy)} onClick={startSample}>
              샘플로 시작 (합성 비용 데이터)
            </button>
            <button className="prompt-copy-button" type="button" disabled={Boolean(busy) || !live || !description.trim()} onClick={structure}>
              {busy === 'structure' ? '정리하는 중…' : '요구사항 정리 (AI)'}
            </button>
            <label className="ws-small-button ws-file">
              프로젝트 불러오기
              <input type="file" accept="application/json,.json" onChange={(e) => e.target.files[0] && importProject(e.target.files[0])} />
            </label>
          </div>
        </div>

        {error && <p className="ws-error" role="alert">{error}</p>}
        {notes.length > 0 && <ul className="ws-notes">{notes.map((n) => <li key={n}>{n}</li>)}</ul>}

        {/* B. 요구사항 확인 */}
        {project && (
          <motion.div className="ws-step" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
            <p className="question-eyebrow">2. 요구사항 확인</p>
            <p className={`ws-stage ws-stage-${stage}`}>{STAGE_LABEL[stage]} · revision {project.requirements_revision}</p>

            <div className="ws-block">
              <div className="ws-block-head"><strong>목적</strong><OriginBadge item={req.purpose} /></div>
              <textarea className="task-input" rows={2} value={req.purpose.text}
                onChange={(e) => editRequirements((r) => { r.purpose.text = e.target.value; r.purpose.origin = 'user'; })} />
              {req.purpose.source_excerpt && <p className="ws-excerpt">“{req.purpose.source_excerpt}”</p>}
            </div>

            <div className="ws-block">
              <strong>입력 변수</strong>
              <p className="ws-help">요청마다 코드가 채우는 값입니다. 템플릿에는 {'{{이름}}'} 으로 들어갑니다.</p>
              <table className="ws-table">
                <thead><tr><th>이름</th><th>타입</th><th>필수</th><th>설명</th><th>출처</th><th /></tr></thead>
                <tbody>
                  {req.variables.map((v, i) => (
                    <tr key={v.name}>
                      <td><code>{v.name}</code></td>
                      <td>
                        <select value={v.type} onChange={(e) => editRequirements((r) => { r.variables[i].type = e.target.value; })}>
                          {['string', 'number', 'integer', 'boolean', 'array', 'object'].map((t) => <option key={t}>{t}</option>)}
                        </select>
                      </td>
                      <td><input type="checkbox" checked={v.required} onChange={(e) => editRequirements((r) => { r.variables[i].required = e.target.checked; })} /></td>
                      <td>{v.description}</td>
                      <td><OriginBadge item={v} /></td>
                      <td>
                        <button className="ws-small-button" type="button" aria-label={`${v.name} 삭제`}
                          onClick={() => editRequirements((r) => { r.variables.splice(i, 1); })}>삭제</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="ws-item">
                <input aria-label="새 변수 이름" placeholder="새 변수 이름 (영문 소문자·_)" value={newVariable}
                  onChange={(e) => setNewVariable(e.target.value)} />
                <button className="ws-small-button" type="button"
                  disabled={!/^[a-z_][a-z0-9_]{0,39}$/.test(newVariable) || req.variables.some((v) => v.name === newVariable)}
                  onClick={() => {
                    editRequirements((r) => {
                      r.variables.push({ name: newVariable, description: '', type: 'string', required: true, origin: 'user', source_excerpt: '' });
                    });
                    setNewVariable('');
                  }}>
                  + 변수 추가
                </button>
              </div>
            </div>

            <ItemList label="필수 규칙" items={req.hard_rules} {...editList('hard_rules')}
              help="선호와 달리 어기면 안 되는 조건입니다. 고치면 요구사항을 다시 확인해야 합니다." />
            <ItemList label="선호" items={req.preferences} {...editList('preferences')} />
            <ItemList label="미결 사항" items={req.open_questions} sourced={false} {...editList('open_questions')}
              help="답을 규칙이나 선호에 반영한 뒤 지우세요. 남아 있으면 확인 완료로 표시하지 않습니다 (초안 저장은 가능)." />

            <div className="ws-block">
              <strong>출력 계약</strong>
              <p className="ws-help">
                이 도구의 제한된 형식입니다 (JSON Schema 표준 아님). 타입: string·number·integer·boolean·array·object,
                배열은 item_type 또는 item_fields, min_items·max_items.
              </p>
              <textarea className="task-input ws-code" rows={8} value={contractText} onChange={(e) => setContractText(e.target.value)} />
              <button className="ws-small-button" type="button" onClick={applyContract}>출력 계약 반영</button>
              {contractError && <p className="ws-error">{contractError}</p>}
            </div>

            <div className="prompt-actions">
              <button className="prompt-copy-button" type="button"
                disabled={Boolean(busy) || req.open_questions.length > 0}
                onClick={confirmAndBuild}>
                {busy === 'build' ? '만드는 중…' : '이 요구사항으로 만들기'}
              </button>
              <button className="prompt-reset-button" type="button" onClick={saveProject}>초안 저장 (JSON)</button>
            </div>
            {req.open_questions.length > 0 && (
              <p className="ws-help">미결 사항 {req.open_questions.length}개가 남아 있어 만들 수 없습니다.</p>
            )}
          </motion.div>
        )}

        {/* C. 편집·시험·내보내기 */}
        {project?.artifact && (
          <motion.div className="ws-step" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
            <p className="question-eyebrow">3. 프롬프트 편집 · 시험 · 내보내기</p>
            {stage === 'stale_artifact' && (
              <p className="ws-error">요구사항이 바뀌었습니다. 위에서 다시 만들기 전에는 시험할 수 없습니다.</p>
            )}
            {missingRules.length > 0 && (
              <p className="ws-error">
                필수 규칙 {missingRules.map((r) => r.id).join(', ')} 의 문장이 지금 프롬프트에 없습니다. 의도한 변경이면 요구사항을 고쳐 다시 만드세요.
              </p>
            )}
            <label className="task-input-label" htmlFor="ws-system">시스템 지침 <span>(revision {project.artifact.revision})</span></label>
            <textarea id="ws-system" className="task-input ws-code" rows={14} value={project.artifact.system_prompt}
              onChange={(e) => editArtifact('system_prompt', e.target.value)} />
            <label className="task-input-label" htmlFor="ws-template">입력 템플릿</label>
            <textarea id="ws-template" className="task-input ws-code" rows={6} value={project.artifact.input_template}
              onChange={(e) => editArtifact('input_template', e.target.value)} />

            <label className="task-input-label" htmlFor="ws-input">시험 입력 (JSON)</label>
            <textarea id="ws-input" className="task-input ws-code" rows={8} value={inputText} onChange={(e) => setInputText(e.target.value)} />
            <div className="prompt-actions">
              <button className="prompt-copy-button" type="button" disabled={Boolean(busy) || stage !== 'built'} onClick={runTest}>
                {busy === 'run' ? '실행 중…' : live ? '시험 실행 (AI)' : '메시지 구성 확인'}
              </button>
            </div>

            {lastRun && (
              <div className={`ws-run ${lastRunStale ? 'is-stale' : ''}`}>
                <p className="ws-stage">
                  {lastRunStale && <strong>이전 버전 결과 · </strong>}
                  {RUN_LABEL[lastRun.status]}
                  {lastRun.model && ` · 모델 ${lastRun.model}${lastRun.cached ? ' (캐시)' : ''}`}
                  {lastRun.elapsed_seconds != null && ` · ${lastRun.elapsed_seconds}초`}
                  {` · 프롬프트 revision ${lastRun.artifact_revision}`}
                </p>
                {lastRun.output && <pre className="prompt-box"><code>{lastRun.output}</code></pre>}
                {!lastRun.output && lastRun.messages && (
                  <pre className="prompt-box"><code>{lastRun.messages.map((m) => `[${m.role}]\n${m.content}`).join('\n\n')}</code></pre>
                )}
                <ChecksView checks={lastRun.checks} />
              </div>
            )}

            <div className="ws-block">
              <strong>내보내기</strong>
              <label className="ws-check-row">
                <input type="checkbox" checked={includeData} onChange={(e) => setIncludeData(e.target.checked)} />
                업무 설명 · 시험 입력 · 시험 결과를 묶음에 포함 (끄면 프롬프트·변수·계약만, 시험 입력은 빈 틀)
              </label>
              <div className="prompt-actions">
                <button className="prompt-copy-button" type="button" disabled={Boolean(busy)} onClick={exportZip}>ZIP 내려받기</button>
                <button className="prompt-reset-button" type="button" onClick={saveProject}>프로젝트 JSON 저장</button>
              </div>
              <p className="ws-help">
                프로젝트는 이 화면에만 있습니다. 새로고침하면 사라지므로 JSON 으로 저장해 두고 &quot;프로젝트 불러오기&quot;로 이어서 작업하세요.
              </p>
            </div>
          </motion.div>
        )}
      </div>
    </section>
  );
}

export default PromptWorkspaceSection;

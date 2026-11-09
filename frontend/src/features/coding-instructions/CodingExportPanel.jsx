import { useEffect, useRef, useState } from 'react';
import { codingWork, downloadText } from './workflowApi';

export default function CodingExportPanel({ prompt }) {
  const [target, setTarget] = useState('agents_md');
  const [existing, setExisting] = useState('');
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const request = useRef(0);
  useEffect(() => { request.current += 1; setPreview(null); setError(''); setBusy(false); }, [prompt, target, existing]);
  useEffect(() => () => { request.current += 1; }, []);
  const prepare = async () => {
    const token = ++request.current; setBusy(true); setError('');
    try {
      const data = await codingWork('exports', { prompt, target, existing });
      if (request.current === token) setPreview(data.export);
    } catch (e) { if (request.current === token) setError(e.message); }
    finally { if (request.current === token) setBusy(false); }
  };
  return <div className="coding-work-card">
    <h4>개발 도구에 적용하기</h4>
    <p>위에서 확인한 지침을 파일로 가져갑니다. 기존 규칙을 붙여 넣으면 변경 내용을 먼저 확인할 수 있어요.</p>
    <label>사용 도구<select value={target} onChange={e => setTarget(e.target.value)}>
      <option value="agents_md">Codex · AGENTS.md</option><option value="claude_code">Claude Code · CLAUDE.md</option>
      <option value="copilot">GitHub Copilot</option><option value="cursor">Cursor 규칙</option><option value="markdown">일반 Markdown</option>
    </select></label>
    <label>기존 지침 내용 (선택)<textarea value={existing} maxLength={40000} rows={4} onChange={e => setExisting(e.target.value)}
      placeholder="이미 지침 파일이 있다면 붙여 넣으세요. 이 도구가 만든 영역만 갱신하고 나머지는 유지합니다." /></label>
    <p className="ws-help">내용은 이 서비스 서버에서 파일 형식으로 정리합니다. 모델 API에 보내지 않으며 파일을 자동으로 덮어쓰지 않습니다.</p>
    <button type="button" className="coding-secondary-button" disabled={busy || !prompt} onClick={prepare}>{busy ? '준비 중…' : '파일과 변경 내용 확인'}</button>
    {error && <p role="alert" className="ws-error">{error}</p>}
    {preview && <div className="coding-work-preview">
      <p><strong>넣을 위치: <code>{preview.path}</code></strong></p>
      <p>{preview.scope}</p>
      {target === 'cursor' && <p className="ws-help">이 파일은 항상 적용하는 규칙입니다. 필요한 파일에서만 쓰려면 Cursor에서 적용 범위를 조정하세요.</p>}
      <details><summary>기존 내용과의 차이</summary><pre>{preview.diff || '변경 없음'}</pre></details>
      <label>저장할 내용<textarea readOnly rows={7} value={preview.content} /></label>
      <button type="button" className="coding-primary-button" onClick={() => downloadText(preview.filename, preview.content)}>{preview.filename} 내려받기</button>
      <p className="ws-help">{preview.verification}</p>
    </div>}
  </div>;
}

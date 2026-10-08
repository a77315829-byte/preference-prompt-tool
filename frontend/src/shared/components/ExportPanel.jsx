import { useState } from 'react';
import { IDLE_COPY_STATE, buttonLabel, copyResult, failedVariant, failureNotice } from './copyStatus.js';

// 만든 프롬프트를 도구별 형식으로 가져가는 곳. 형식은 서버(exporters.py)가
// 정해서 session.exports 로 보낸다 - 여기서는 복사하거나 파일로 내려받기만 한다.
//   kind "copy": 채팅 서비스 설정 칸에 붙여 넣는 글
//   kind "file": 저장소에 넣으면 도구가 자동으로 읽는 파일
function download(filename, content) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function ExportPanel({ exports }) {
  const [copyState, setCopyState] = useState(IDLE_COPY_STATE);

  if (!exports?.length) return null;

  // navigator.clipboard 가 없거나(비보안 접속) 쓰기가 거부돼도 같은 실패 경로로 간다.
  const copy = async (itemKey, variant, text) => {
    let ok = false;
    try {
      await navigator.clipboard.writeText(text);
      ok = true;
    } catch {
      ok = false;
    }
    setCopyState(copyResult(itemKey, variant, ok));
  };

  return (
    <div className="export-panel">
      <p className="question-eyebrow">바로 쓰기</p>
      <div className="export-list">
        {exports.map((item) => (
          <div className="export-item" key={item.key}>
            <div className="export-copy">
              <strong>{item.label}</strong>
              <span>{item.how_to}</span>
              {item.path && <code className="export-path">{item.path}</code>}
              {item.over_limit && (
                <span className="export-warning">
                  {item.char_count.toLocaleString()}자로 무료 요금제 한도({item.char_limit.toLocaleString()}자)를
                  넘습니다. 유료 요금제는 그대로 쓸 수 있고, 무료라면 짧은 판을 쓰세요.
                </span>
              )}
            </div>
            <div className="export-actions">
              {item.kind === 'file' ? (
                <button className="prompt-reset-button" type="button" onClick={() => download(item.filename, item.content)}>
                  {item.filename} 내려받기
                </button>
              ) : (
                <button className="prompt-reset-button" type="button" onClick={() => copy(item.key, 'full', item.content)}>
                  {buttonLabel(copyState, item.key, 'full')}
                </button>
              )}
              {item.compact && (
                <button className="prompt-reset-button" type="button" onClick={() => copy(item.key, 'compact', item.compact)}>
                  {buttonLabel(copyState, item.key, 'compact')}
                </button>
              )}
            </div>
            {failureNotice(copyState, item.key) && (
              <div className="export-failure">
                <span className="export-warning" role="alert">{failureNotice(copyState, item.key)}</span>
                <textarea
                  readOnly
                  rows={6}
                  aria-label={`${item.label} 내용`}
                  value={failedVariant(copyState, item.key) === 'compact' ? item.compact : item.content}
                  onFocus={(event) => event.target.select()}
                />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default ExportPanel;

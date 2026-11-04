import { useId, useState } from 'react';

export default function CodingExampleCode({ option, language }) {
  const [index, setIndex] = useState(0);
  const panelId = useId();
  const files = option.files || [{ name: `${language} 예시`, code: option.code }];
  const file = files[index] || files[0];
  return <div className="coding-code-preview">
    <div className="coding-code-toolbar">
      <span className="coding-editor-dots" aria-hidden="true"><i /><i /><i /></span>
      {files.length === 1 ? <span className="coding-file-name">{file.name}</span>
        : <div className="coding-file-buttons" role="group" aria-label={`${option.label} 예시 파일 선택`}>
          {files.map((item, at) => <button type="button" key={item.name} aria-pressed={index === at} aria-controls={panelId}
            onClick={() => setIndex(at)}>{item.name}</button>)}
        </div>}
    </div>
    <pre id={panelId} tabIndex={0} aria-label={`${file.name} 코드`}><code>{file.code}</code></pre>
    {files.length > 1 && <span className="coding-file-hint">파일 이름을 눌러 {files.length}개 파일을 확인할 수 있어요.</span>}
  </div>;
}

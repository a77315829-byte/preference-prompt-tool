import { useEffect, useMemo, useState } from 'react';

// 템플릿 라이브러리. 데이터는 서버(templates/library.yaml)에서 받는다.
// 모아 두는 공간은 이미 많아서, 여기의 차이는 "내 방식으로 바꾸기" 하나다 -
// 템플릿의 도메인으로 비교를 돌리고 결과는 템플릿 + 추정한 선호 절이 된다.
async function fetchTemplates() {
  const response = await fetch('/api/templates');
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `템플릿을 불러오지 못했습니다 (${response.status})`);
  return body.templates;
}

function TemplateLibrarySection({ onBack, onPersonalize }) {
  const [templates, setTemplates] = useState([]);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState('');
  const [openId, setOpenId] = useState('');

  useEffect(() => {
    fetchTemplates().then(setTemplates).catch((e) => setError(e.message));
  }, []);

  const groups = useMemo(() => {
    const byCategory = new Map();
    templates.forEach((t) => {
      if (!byCategory.has(t.category)) byCategory.set(t.category, []);
      byCategory.get(t.category).push(t);
    });
    return [...byCategory.entries()];
  }, [templates]);

  const copy = async (template) => {
    try {
      await navigator.clipboard.writeText(template.prompt);
      setCopied(template.id);
    } catch {
      setCopied('');
    }
  };

  return (
    <section className="comparison-section template-library">
      <div className="comparison-inner">
        <button className="back-button" type="button" onClick={onBack}>← 처음으로</button>
        <div className="comparison-heading">
          <p className="eyebrow">Template library</p>
          <h2>자주 쓰는 프롬프트에서 시작하세요.</h2>
          <p>
            그대로 복사해 써도 되고, <strong>내 방식으로 바꾸기</strong>를 누르면 몇 번의 비교로
            분량·표현 방식이 내 취향에 맞춰진 버전을 만듭니다.
          </p>
        </div>

        {error && <p className="connection-note">{error} (API 서버가 켜져 있는지 확인해 주세요.)</p>}

        {groups.map(([category, items]) => (
          <div className="template-group" key={category}>
            <p className="question-eyebrow">{category}</p>
            <div className="template-grid">
              {items.map((t) => (
                <article className="template-card" key={t.id}>
                  <strong>{t.title}</strong>
                  <span>{t.description}</span>
                  <button className="template-toggle" type="button" aria-expanded={openId === t.id}
                    onClick={() => setOpenId(openId === t.id ? '' : t.id)}>
                    {openId === t.id ? '내용 접기' : '내용 보기'}
                  </button>
                  {openId === t.id && <pre className="prompt-box"><code>{t.prompt}</code></pre>}
                  <small>{t.author} · {t.license}</small>
                  <div className="export-actions">
                    <button className="prompt-copy-button" type="button" onClick={() => onPersonalize(t)}>
                      내 방식으로 바꾸기
                    </button>
                    <button className="prompt-reset-button" type="button" onClick={() => copy(t)}>
                      {copied === t.id ? '복사했습니다 ✓' : '그대로 복사'}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default TemplateLibrarySection;

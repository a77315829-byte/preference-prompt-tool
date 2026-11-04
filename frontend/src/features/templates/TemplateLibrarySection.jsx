import { useEffect, useMemo, useRef, useState } from 'react';
import PromptPolishSection from '../polish/PromptPolishSection';

// 템플릿 라이브러리. 데이터는 서버(templates/library.yaml)에서 받는다.
// 선택 비교 지원 템플릿만 도메인의 선호를 붙인다. 업무 초안은 복사·점검으로 시작한다.
async function fetchTemplates() {
  const response = await fetch('/api/templates');
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `템플릿을 불러오지 못했습니다 (${response.status})`);
  return body.templates;
}

function TemplateLibrarySection({ onBack, onPersonalize, onWorkspace, initialCategory = '전체' }) {
  const [templates, setTemplates] = useState([]);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState('');
  const [openId, setOpenId] = useState('');
  const [category, setCategory] = useState(initialCategory || '전체');
  const [search, setSearch] = useState('');
  const [polish, setPolish] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const polishRef = useRef(null);
  useEffect(() => { if (polish) polishRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, [polish?.id]);

  useEffect(() => {
    fetchTemplates().then(setTemplates).catch((e) => setError(e.message)).finally(() => setLoaded(true));
  }, []);

  const groups = useMemo(() => {
    const byCategory = new Map();
    templates.forEach((t) => {
      if (category !== '전체' && t.category !== category) return;
      if (!`${t.title} ${t.description}`.toLowerCase().includes(search.trim().toLowerCase())) return;
      if (!byCategory.has(t.category)) byCategory.set(t.category, []);
      byCategory.get(t.category).push(t);
    });
    return [...byCategory.entries()];
  }, [templates, category, search]);

  const copy = async (template) => {
    setError('');
    try {
      await navigator.clipboard.writeText(template.prompt);
      setCopied(template.id);
    } catch {
      setCopied(''); setOpenId(template.id); setError('복사하지 못했어요. 펼친 내용을 직접 선택해 복사해 주세요.');
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
            회의·문서·개발 작업에 맞는 초안을 고르세요. 내용을 확인해 복사하고 새 자료에 다시 씁니다.
            선택 비교를 지원하는 템플릿에는 ‘내 방식으로 바꾸기’가 표시됩니다.
          </p>
        </div>
        <div className="template-toolbar ws-step">
          <label className="task-input-label" htmlFor="template-search">어떤 일에 쓸까요?</label>
          <input id="template-search" className="ws-input" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="회의, 인수인계, 버그, PR…" />
          <div className="prompt-actions" role="group" aria-label="템플릿 업무 분류">
            {['전체', '문서 요약', '코딩 도움', '팀 업무'].map((c) => <button className={category === c ? 'prompt-copy-button' : 'prompt-reset-button'}
              key={c} type="button" aria-pressed={category === c} onClick={() => setCategory(c)}>{c}</button>)}
          </div>
          <div className="prompt-actions">
            <button className="prompt-reset-button" type="button" onClick={() => setPolish({ id: 'own', prompt: '' })}>가진 요청문 점검하기</button>
            {onWorkspace && <button className="prompt-reset-button" type="button" onClick={onWorkspace}>직접 업무 지침 만들기</button>}
          </div>
          <p className="ws-help">업무용 초안은 실제 자료와 결과를 사람이 확인해야 합니다. 참고 자료는 업무 양식의 근거이며 이 도구의 효과를 검증한 자료는 아닙니다.</p>
        </div>
        {polish && <div className="template-polish-panel" ref={polishRef}><PromptPolishSection key={polish.id} embedded initialPrompt={polish.prompt} onBack={() => setPolish(null)} /></div>}

        {error && <p className="connection-note" role="alert">{error}</p>}
        {!loaded && <p role="status">템플릿을 불러오는 중…</p>}
        {loaded && !error && groups.length === 0 && <p role="status">조건에 맞는 템플릿이 없어요. 검색어나 분류를 바꿔 보세요.</p>}

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
                  {t.source_url && <a href={t.source_url} target="_blank" rel="noreferrer">업무 양식 참고 자료</a>}
                  <div className="export-actions">
                    {t.personalizable !== false && <button className="prompt-copy-button" type="button" onClick={() => onPersonalize(t)}>
                      내 방식으로 바꾸기
                    </button>}
                    <button className="prompt-reset-button" type="button" onClick={() => copy(t)}>
                      {copied === t.id ? '복사했습니다 ✓' : '그대로 복사'}
                    </button>
                    <button className="prompt-reset-button" type="button" onClick={() => setPolish({ id: t.id, prompt: t.prompt })}>요청문 점검</button>
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

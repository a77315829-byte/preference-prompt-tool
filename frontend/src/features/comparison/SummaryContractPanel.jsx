import { useEffect, useId, useRef, useState } from 'react';
import { characterCount, MAX_SOURCE_CHARS, MAX_TOPIC_CHARS } from './summaryInputPolicy';
import './SummaryContractPanel.css';

const LENGTHS = { short: '짧게 · 1~2문장', normal: '보통 · 3~4문장', long: '자세히 · 5문장 이상' };
const WORDING = { normal: '다시 표현하기', high: '원문 표현 많이 유지하기', fully: '완전한 원문 문장만 발췌하기' };
const RESOLUTIONS = [
  ['expand', '분량을 늘려 모두 담기'],
  ['shorten', '분량을 줄여 원문 안에서 발췌하기'],
  ['rephrase', '길이 유지 · 재서술 허용'],
  ['keep_limits', '길이·발췌 유지 · 일부 생략 허용'],
];

function describe(profile) {
  return `${LENGTHS[profile?.length] || '분량 미정'} / ${WORDING[profile?.extractiveness] || '표현 방식 미정'}`;
}

export default function SummaryContractPanel({ domainKey, initialSource = '', initialProfile = {} }) {
  const id = useId();
  const [source, setSource] = useState(initialSource);
  const [length, setLength] = useState(initialProfile.length || '');
  const [wording, setWording] = useState(initialProfile.extractiveness || '');
  const [topic, setTopic] = useState(initialProfile.topic || '');
  const [sentences, setSentences] = useState([]);
  const [required, setRequired] = useState([]);
  const [resolution, setResolution] = useState(null);
  const [conflict, setConflict] = useState(null);
  const [resolutionOptions, setResolutionOptions] = useState([]);
  const [result, setResult] = useState(null);
  const [language, setLanguage] = useState('ko');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState('');
  const revision = useRef(0);
  const pending = useRef(null);
  // Count Unicode characters like the server, rather than UTF-16 code units.
  const sourceLength = characterCount(source);
  const sourceTooLong = sourceLength > MAX_SOURCE_CHARS;
  const topicLength = characterCount(topic);
  const topicTooLong = topicLength > MAX_TOPIC_CHARS;

  useEffect(() => () => {
    revision.current += 1;
    pending.current?.abort();
  }, []);

  const invalidate = (keepConflict = false) => {
    revision.current += 1;
    pending.current?.abort();
    pending.current = null;
    setBusy(false);
    setResult(null);
    setError('');
    setCopied('');
    if (!keepConflict) {
      setConflict(null);
      setResolutionOptions([]);
      setResolution(null);
    }
  };

  const changeSource = (value) => {
    invalidate();
    setSource(value);
    setSentences([]);
    setRequired([]);
  };

  const toggleSentence = (sentence) => {
    invalidate();
    setRequired((previous) => previous.includes(sentence)
      ? previous.filter((item) => item !== sentence) : [...previous, sentence]);
  };

  const inspect = async (event) => {
    event.preventDefault();
    if (!source.trim() || sourceTooLong || topicTooLong || !length || !wording || busy) return;
    const ticket = ++revision.current;
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    setBusy(true);
    setError('');
    setResult(null);
    setCopied('');
    try {
      const response = await fetch('/api/summary-contract', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: controller.signal,
        body: JSON.stringify({ domainKey, profile: { length, extractiveness: wording, topic },
          sourceText: source, requiredSentences: required, resolution }),
      });
      const body = await response.json().catch(() => ({}));
      if (ticket !== revision.current) return;
      if (!response.ok) throw new Error(body.error || `조건을 확인하지 못했습니다 (${response.status}).`);
      if (!['needs_resolution', 'ready'].includes(body.status) || !Array.isArray(body.available_sentences)) {
        throw new Error('조건 확인 응답을 읽지 못했습니다. 다시 확인해 주세요.');
      }
      setSentences(body.available_sentences);
      setConflict(body.conflict || null);
      setResolutionOptions(body.available_resolutions || ['expand', 'rephrase', 'keep_limits']);
      setResult(body);
    } catch (cause) {
      if (ticket === revision.current && cause.name !== 'AbortError') {
        setError(cause.message || '조건을 확인하지 못했습니다.');
      }
    } finally {
      if (ticket === revision.current) {
        setBusy(false);
        pending.current = null;
      }
    }
  };

  const ready = result?.status === 'ready';
  const prompt = ready ? result.prompts?.[language] || '' : '';
  const task = ready ? result.task_requests?.[language] || '' : '';
  const copy = async (kind, text) => {
    if (!ready || !text) return;
    const ticket = revision.current;
    setError('');
    try {
      await navigator.clipboard.writeText(text);
      if (ticket === revision.current) setCopied(kind);
    } catch {
      if (ticket === revision.current) setError('복사하지 못했습니다. 아래 지침을 직접 선택해 복사해 주세요.');
    }
  };

  return (
    <section className="summary-contract" aria-labelledby={`${id}-heading`}>
      <h4 id={`${id}-heading`}>이번 원문의 조건 충돌 확인</h4>
      <p>아래 기존 선호 지침과 별도로, 이번 원문에서 꼭 남길 내용과 분량을 확인합니다. 조건 확인은 AI를 호출하지 않으며 입력 내용과 결과를 자동 저장하지 않습니다.</p>
      <form onSubmit={inspect}>
        <label htmlFor={`${id}-source`}>이번에 요약할 원문</label>
        <textarea id={`${id}-source`} className="summary-contract-source" value={source} rows={5}
          aria-invalid={sourceTooLong} aria-describedby={`${id}-source-help ${id}-source-count`}
          onChange={(event) => changeSource(event.target.value)} />
        <p id={`${id}-source-help`} className="summary-contract-help">비교에 쓴 원문으로 시작합니다. 다른 원문으로 바꾸면 남길 문장을 다시 고릅니다.</p>
        <p id={`${id}-source-count`} className={sourceTooLong ? 'summary-contract-error' : 'summary-contract-help'} role={sourceTooLong ? 'alert' : undefined}>
          {sourceLength.toLocaleString('ko-KR')} / {MAX_SOURCE_CHARS.toLocaleString('ko-KR')}자 · 공백 포함, 유니코드 문자 기준입니다. 조합형 이모지는 여러 글자로 셀 수 있습니다.
          {sourceTooLong && ' · 원문은 12,000자까지 확인할 수 있습니다. 붙여 넣은 내용은 그대로 유지했으니 직접 줄이거나 나눠 주세요.'}
        </p>
        <div className="summary-contract-fields">
          <label>요약 분량
            <select aria-label="요약 분량" value={length} onChange={(event) => { invalidate(); setLength(event.target.value); }}>
              <option value="">직접 선택해 주세요</option>
              {Object.entries(LENGTHS).map(([value, title]) => <option key={value} value={value}>{title}</option>)}
            </select>
          </label>
          <label>원문 표현 방식
            <select aria-label="원문 표현 방식" value={wording} onChange={(event) => { invalidate(); setWording(event.target.value); }}>
              <option value="">직접 선택해 주세요</option>
              {Object.entries(WORDING).map(([value, title]) => <option key={value} value={value}>{title}</option>)}
            </select>
          </label>
        </div>
        <label htmlFor={`${id}-topic`}>요약 초점 (선택)</label>
        <input id={`${id}-topic`} value={topic} placeholder="예: 일정 변경과 남은 위험"
          aria-invalid={topicTooLong} aria-describedby={`${id}-topic-count`}
          onChange={(event) => { invalidate(); setTopic(event.target.value); }} />
        <p id={`${id}-topic-count`} className={topicTooLong ? 'summary-contract-error' : 'summary-contract-help'}
          role={topicTooLong ? 'alert' : undefined}>
          {topicLength.toLocaleString('ko-KR')} / {MAX_TOPIC_CHARS}자
          {topicTooLong && ' · 요약 초점을 직접 줄여 주세요. 입력한 내용은 자르지 않았습니다.'}
        </p>
        {sentences.length > 0 ? (
          <details className="summary-contract-sentences">
            <summary>꼭 남길 내용이 있는 원문 문장 고르기 · {required.length}개 선택</summary>
            <p className="summary-contract-help">최대 8개입니다. 선택한 문장 속 내용을 우선 보존하도록 요청합니다. 문장 구분과 의미상 압축 가능 여부는 완벽히 판별하지 못합니다.</p>
            <div className="summary-contract-sentence-list">
              {sentences.map((sentence, index) => (
                <label key={`${index}-${sentence}`}>
                  <input type="checkbox" checked={required.includes(sentence)}
                    disabled={required.length >= 8 && !required.includes(sentence)}
                    onChange={() => toggleSentence(sentence)} />
                  <span>{sentence}</span>
                </label>
              ))}
            </div>
          </details>
        ) : <p className="summary-contract-help">조건 확인을 누르면 원문 문장을 골라 보존 요청을 추가할 수 있습니다.</p>}
        {conflict && (
          <div className="summary-contract-conflict">
            <p role="alert">{conflict.message}</p>
            <fieldset>
              <legend>충돌하는 조건 중 무엇을 바꿀까요?</legend>
              {RESOLUTIONS.filter(([value]) => resolutionOptions.includes(value)).map(([value, title]) => (
                <label key={value}>
                  <input type="radio" name={`${id}-resolution`} value={value} checked={resolution === value}
                    onChange={() => { invalidate(true); setResolution(value); }} />
                  <span>{title}</span>
                </label>
              ))}
            </fieldset>
            {!resolution && <p className="summary-contract-help">처리 방법을 고르고 다시 조건을 확인해 주세요. 지침은 아직 만들지 않았습니다.</p>}
          </div>
        )}
        <button className="prompt-reset-button" type="submit" disabled={busy || !source.trim() || sourceTooLong || topicTooLong || !length || !wording || (Boolean(conflict) && !resolution)}>
          {busy ? '조건 확인 중…' : '조건 확인'}
        </button>
      </form>
      {error && <p className="summary-contract-error" role="alert">{error}</p>}
      {result?.notices?.length > 0 && <ul className="summary-contract-notices">{result.notices.map((notice, index) => <li key={index}>{notice}</li>)}</ul>}
      {ready && (
        <div className="summary-contract-result" aria-live="polite">
          <h5>조건을 확인한 작업용 지침</h5>
          <dl>
            <dt>처음 고른 조건</dt><dd>{describe(result.original_profile)}</dd>
            <dt>이번에 적용할 조건</dt><dd>{describe(result.effective_profile)}</dd>
            <dt>조건 처리</dt><dd>{RESOLUTIONS.find(([value]) => value === result.resolution)?.[1] || '원래 조건 유지'}</dd>
            <dt>고른 내용의 보존 요청</dt><dd>{result.coverage_policy === 'prioritize_with_omission' || result.resolution === 'keep_limits'
              ? '분량에 맞춰 일부 생략 허용 · 전체 보존 아님' : '고른 내용 모두 보존 요청 · 실제 결과 확인 필요'}</dd>
          </dl>
          <p className="summary-contract-help">조건을 조립한 지침입니다. 실제 요약의 내용 보존이나 사실성이 검증됐다는 뜻은 아닙니다.</p>
          <label>지침 언어
            <select aria-label="조건 확인 지침 언어" value={language} onChange={(event) => { revision.current += 1; setLanguage(event.target.value); setCopied(''); }}>
              <option value="ko">한국어</option><option value="en">English</option>
            </select>
          </label>
          <pre className="summary-contract-prompt"><code>{prompt}</code></pre>
          <div className="prompt-actions">
            <button type="button" className="prompt-copy-button" disabled={!prompt} onClick={() => copy('prompt', prompt)}>
              {copied === 'prompt' ? '재사용 지침 복사 완료' : '재사용 지침만 복사'}
            </button>
            <button type="button" className="prompt-reset-button" disabled={!task} onClick={() => copy('task', task)}>
              {copied === 'task' ? '이번 작업 요청 복사 완료' : '원문·남길 문장과 함께 복사'}
            </button>
          </div>
          <p className="summary-contract-help">재사용 지침에는 원문과 선택 문장을 넣지 않습니다. ‘함께 복사’에는 이번 원문과 남길 내용이 포함됩니다.</p>
        </div>
      )}
    </section>
  );
}

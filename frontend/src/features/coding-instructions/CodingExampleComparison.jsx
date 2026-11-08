import { useEffect, useRef, useState } from 'react';
import CodingExampleCode from './CodingExampleCode';
import { comparisonSequence, comparisonSummary } from './repeatedComparison';

export default function CodingExampleComparison({ examples, initialChoices, initialProgress, onProgress, onFinish, onCancel }) {
  const [step, setStep] = useState(initialProgress?.step || 0);
  const [choices, setChoices] = useState(() => initialProgress?.choices || (examples.version === 3 ? {} : { ...initialChoices }));
  const heading = useRef(null);
  const container = useRef(null);
  const sequence = comparisonSequence(examples, choices);
  const index = Math.min(step, sequence.length - 1);
  const pair = sequence[index];
  const key = item => item.id || item.axis;
  const selected = choices[key(pair)];
  const answered = selected !== undefined;
  useEffect(() => { onProgress?.({ step, choices }); }, [step, choices, onProgress]);
  useEffect(() => {
    heading.current?.focus({ preventScroll: true });
    if (step > 0) container.current?.scrollIntoView({ block: 'start',
      behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ? 'auto' : 'smooth' });
  }, [step]);
  const choose = value => setChoices(current => ({ ...current, [key(pair)]: value }));
  const next = () => {
    if (!answered) return;
    if (index + 1 === sequence.length) {
      if (examples.version === 3) {
        const summary = comparisonSummary(sequence, choices);
        onFinish(Object.fromEntries(Object.entries(summary).map(([axis, value]) => [axis, value.value])), 3, examples.source,
          sequence.map(item => ({ id: item.id, value: choices[item.id] })), summary);
      } else if (sequence.every(item => Object.hasOwn(choices, key(item)))) onFinish({ ...choices }, examples.version, examples.source);
    } else setStep(index + 1);
  };
  const selectedLabel = pair.options.find(option => option.value === selected)?.label;
  return <section className="coding-example-comparison" aria-label="언어별 코드 예시 비교" ref={container}>
    <div className="coding-comparison-top"><span className="coding-kicker">02 · 선호 선택</span><span className="coding-environment-chip">{examples.language} / {examples.framework || '프레임워크 없이'}</span></div>
    <div className="coding-axis-progress" aria-label="선호 비교 항목">
      {sequence.map((item, at) => <button key={key(item)} type="button" aria-label={`${item.context ? `${item.context} · ` : ''}${item.label} 비교로 이동`} aria-current={index === at ? 'step' : undefined}
        disabled={at > index && !Object.hasOwn(choices, key(item))} onClick={() => setStep(at)}>
        <span aria-hidden="true">{Object.hasOwn(choices, key(item)) ? '✓' : at + 1}</span>{item.label}</button>)}
    </div>
    {examples.version === 3 && <p className="coding-selection-method-hint" role="status">{index + 1}번째 / {sequence.length}회{sequence.length === 8 ? ' · 선택이 엇갈리면 최대 2회 추가' : ' · 미확정 항목 추가 확인'} — {pair.context}</p>}
    <div className="coding-screen-heading"><h3 ref={heading} tabIndex={-1}>{pair.question}</h3><p>더 편한 쪽을 고르면 아래에 내 선택이 표시돼요. 선택한 뒤 다음 항목으로 넘어가세요.</p></div>
    <aside className="coding-example-scope" role="note"><strong>{examples.source?.kind === 'framework' ? `${examples.framework} 전용 코드 예시` : `${examples.language} 기본 문법 코드 예시`}</strong><p>{examples.notice}</p></aside>
    <details className="coding-example-context"><summary>비교하는 과제와 개발 환경 보기</summary>
      <p>{examples.source?.label}</p><p>예시 과제: {pair.task || examples.task}</p>
      {examples.references && <p>예시 작성 참고: {examples.references.map(url => <a key={url} href={url} target="_blank" rel="noreferrer">{examples.framework} 공식 문서</a>)}</p>}
    </details>
    {pair.before && <details className="coding-existing-code"><summary>변경 전 기존 코드 보기</summary><pre><code>{pair.before}</code></pre></details>}
    <div className="coding-example-options">
      {pair.options.map((option, index) => <article className={`coding-example-card tone-${index === 0 ? 'blue' : 'lavender'} ${selected === option.value ? 'is-selected' : ''}`} key={option.value}>
        <div className="coding-option-heading"><span className="coding-option-letter">{index === 0 ? 'A' : 'B'}</span><h4>{option.label}</h4>
          {selected === option.value && <span className="coding-option-check" aria-hidden="true">✓</span>}</div>
        <CodingExampleCode key={`${pair.axis}-${option.value}`} option={option} language={examples.language} />
        <p className="coding-option-explanation">{option.explanation}</p>
        <button type="button" className="coding-option-select" aria-label={`${option.label} 선택`} aria-pressed={selected === option.value} onClick={() => choose(option.value)}>
          {selected === option.value ? `${index === 0 ? 'A' : 'B'}를 골랐어요 ✓` : `${index === 0 ? 'A' : 'B'}가 더 편해요`}</button>
      </article>)}
    </div>
    <div className={`coding-picked-answer ${answered ? 'has-choice' : ''}`} role="status"><span>이번 항목의 내 선택</span>
      <strong>{!answered ? '아직 선택하지 않았어요' : selected === null ? '예시는 보류 · 설정 카드에서 직접 고를게요' : selectedLabel}</strong></div>
    <div className="coding-comparison-actions"><div>
      <button type="button" className="coding-text-button" aria-pressed={selected === null} onClick={() => choose(null)}>예시는 보류할게요</button>
      <button type="button" className="coding-text-button" disabled={step === 0} onClick={() => setStep(step - 1)}>이전 항목</button>
    </div><button type="button" className="coding-primary-button" disabled={!answered} onClick={next}>{index + 1 === sequence.length ? '4가지 선택 확인하기 →' : '이 선택으로 다음 →'}</button></div>
    <button type="button" className="coding-text-button coding-cancel-comparison" onClick={onCancel}>비교 취소</button>
  </section>;
}

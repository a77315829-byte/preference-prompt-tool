import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useRef, useState } from 'react';
import { checkPromptStructure, polishPrompt } from './polishApi';

const EXAMPLE_PROMPTS = [
  '회의록에서 결정 사항과 다음 할 일을 정리해줘',
  '이 코드에서 오류 가능성과 필요한 테스트를 검토해줘',
  '기술 문서에서 우리 팀이 바꿔야 할 부분을 알려줘',
];

// GEPA는 프롬프트가 실제로 만든 결과물을 채점하는 도구라, 여기 가져온
// 프롬프트 텍스트 하나만으로는 돌릴 수 없다(과제 입력도 채점 기준도
// 없다). 여기서는 코드가 구조를 점검하고 모델이 설명과 재작성본을 낸다.
// 실제 결과물의 개선 효과는 별도 검증 대상이다. agents/prompt_polish.py 참고.
const DEBOUNCE_MS = 500;

function PromptPolishSection({ onBack, initialPrompt = '', embedded = false }) {
  const [prompt, setPrompt] = useState(initialPrompt);
  const [checklist, setChecklist] = useState(null);
  const [checklistError, setChecklistError] = useState(false);
  const [polishState, setPolishState] = useState('idle'); // idle | loading | done | error
  const [result, setResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [copied, setCopied] = useState(false);
  const debounceRef = useRef(null);
  const editPrompt = (value) => { setPrompt(value); setResult(null); setPolishState('idle'); setCopied(false); setErrorMessage(''); };

  useEffect(() => {
    let cancelled = false;
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    const trimmed = prompt.trim();
    if (!trimmed) {
      setChecklist(null);
      setChecklistError(false);
      return undefined;
    }
    debounceRef.current = window.setTimeout(() => {
      checkPromptStructure(trimmed)
        .then((data) => {
          if (cancelled) return;
          setChecklist(data.checklist);
          setChecklistError(false);
        })
        .catch(() => {
          if (cancelled) return;
          setChecklistError(true);
        });
    }, DEBOUNCE_MS);
    return () => { cancelled = true; window.clearTimeout(debounceRef.current); };
  }, [prompt]);

  const handlePolish = () => {
    const trimmed = prompt.trim();
    if (!trimmed) return;
    setPolishState('loading');
    setErrorMessage('');
    setCopied(false);
    polishPrompt(trimmed)
      .then((data) => {
        setChecklist(data.checklist);
        setResult(data);
        setPolishState('done');
      })
      .catch((error) => {
        setErrorMessage(error.message || '다듬는 중 문제가 발생했습니다.');
        setPolishState('error');
      });
  };

  const handleAgain = () => {
    setResult(null);
    setPolishState('idle');
    setCopied(false);
  };

  const handleCopy = async () => {
    if (!result?.revisedPrompt) return;
    try {
      await navigator.clipboard.writeText(result.revisedPrompt);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <section className={embedded ? 'polish-section polish-embedded' : 'comparison-section polish-section'} id="polish-section">
      <div className="comparison-inner">
        <button className="back-button" type="button" onClick={onBack}>
          {embedded ? '요청문 점검 닫기' : '← 카테고리로 돌아가기'}
        </button>

        <div className="comparison-heading">
          <p className="eyebrow">PROMPT POLISH</p>
          <h2>AI에게 보낼 요청을 더 명확하게 다듬어요</h2>
          <p>
            맡길 일·원하는 결과·조건을 구조 점검합니다. AI 수정안은 버튼을 눌렀을 때 만들며, 검토 후 복사해 사용하세요.
            표현을 명확히 하는 도구이며 결과 품질이나 개인 선호 적합성을 검증하는 기능은 아닙니다.
          </p>

          <label className="task-input-label" htmlFor="polish-input">
            다듬을 요청문 <span>(AI에게 보내던 문장)</span>
          </label>
          <div className="task-input-row">
            <textarea
              id="polish-input"
              className="task-input polish-search-input"
              value={prompt}
              onChange={(event) => editPrompt(event.target.value)}
              disabled={polishState === 'loading'}
              rows={3}
              placeholder="예: 회의록을 팀에 보낼 수 있게 정리해줘"
            />
            <button
              className="task-start-button"
              type="button"
              disabled={!prompt.trim() || polishState === 'loading'}
              onClick={handlePolish}
            >
              {polishState === 'loading' ? '다듬는 중…' : embedded ? 'AI 수정안 만들기' : '다듬기'}
            </button>
          </div>

          <div className="polish-examples" aria-label="예시로 시작">
            {EXAMPLE_PROMPTS.map((example) => (
              <button
                key={example}
                type="button"
                className="polish-example-chip"
                disabled={polishState === 'loading'} onClick={() => editPrompt(example)}
              >
                {example}
              </button>
            ))}
          </div>
        </div>

        <AnimatePresence mode="wait">
          {checklist && (
            <motion.ul
              className="polish-checklist"
              aria-label="구조 점검 결과"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
            >
              {checklist.map((item) => (
                <li
                  key={item.name}
                  className={`polish-check ${item.passed ? 'is-passed' : 'is-failed'}`}
                  title={item.note}
                >
                  <span className="polish-check-mark" aria-hidden="true">
                    {item.passed ? '✓' : '!'}
                  </span>
                  {item.name}
                </li>
              ))}
            </motion.ul>
          )}
        </AnimatePresence>

        {checklistError && (
          <p className="connection-note" role="status">
            구조 점검을 불러오지 못했습니다. 다듬기는 그대로 눌러도 됩니다.
          </p>
        )}

        {polishState === 'error' && (
          <p className="connection-note" role="alert">
            {errorMessage}
          </p>
        )}

        <AnimatePresence>
          {polishState === 'done' && result && (
            <motion.div
              className="prompt-result"
              key="polish-result"
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, ease: 'easeOut' }}
            >
              <p className="question-eyebrow">무엇을 고쳤는지</p>
              <p className="polish-suggestions">{result.suggestions}</p>

              <h3>다듬은 요청문</h3>
              <p>
                [ ] 로 남은 자리는 사용자가 채울 내용입니다 - 모델이 없는 내용을
                지어내지 않습니다.
              </p>
              <pre className="prompt-box"><code>{result.revisedPrompt}</code></pre>
              <div className="prompt-actions">
                <button className="prompt-copy-button" type="button" onClick={handleCopy}>
                  {copied ? '복사했습니다 ✓' : '요청문 복사'}
                </button>
                <button className="prompt-reset-button" type="button" onClick={handleAgain}>
                  다시 다듬기
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </section>
  );
}

export default PromptPolishSection;

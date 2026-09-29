import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useRef, useState } from 'react';
import { checkPromptStructure, polishPrompt } from './polishApi';

const EXAMPLE_PROMPTS = [
  '요약해줘',
  '이 코드 리뷰해줘',
  '고객 문의에 답장 써줘',
];

// GEPA는 프롬프트가 실제로 만든 결과물을 채점하는 도구라, 여기 가져온
// 프롬프트 텍스트 하나만으로는 돌릴 수 없다(과제 입력도 채점 기준도
// 없다). 대신 GEPA가 증명한 원리 - 구조화된 피드백이 막연한 피드백보다
// 낫다 - 를 그대로 쓴다. 코드가 구조를 점검하고, 그 결과를 근거로
// 모델이 설명과 재작성본을 낸다. agents/prompt_polish.py 참고.
const DEBOUNCE_MS = 500;

function PromptPolishSection({ onBack }) {
  const [prompt, setPrompt] = useState('');
  const [checklist, setChecklist] = useState(null);
  const [checklistError, setChecklistError] = useState(false);
  const [polishState, setPolishState] = useState('idle'); // idle | loading | done | error
  const [result, setResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [copied, setCopied] = useState(false);
  const debounceRef = useRef(null);

  useEffect(() => {
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
          setChecklist(data.checklist);
          setChecklistError(false);
        })
        .catch(() => {
          setChecklistError(true);
        });
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(debounceRef.current);
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
    <section className="comparison-section polish-section" id="polish-section">
      <div className="comparison-inner">
        <button className="back-button" type="button" onClick={onBack}>
          ← 카테고리로 돌아가기
        </button>

        <div className="comparison-heading">
          <p className="eyebrow">PROMPT POLISH</p>
          <h2>가진 프롬프트, 구조부터 점검하고 다듬어요.</h2>
          <p>
            어디서 가져온 프롬프트든 붙여넣어 보세요. 역할·형식·제약·예시가
            빠졌는지 코드로 먼저 확인하고, 빠진 부분만 모델이 채워 다시
            씁니다.
          </p>

          <label className="task-input-label" htmlFor="polish-input">
            다듬을 프롬프트 <span>(어디서든 가져온 것이면 됩니다)</span>
          </label>
          <div className="task-input-row">
            <textarea
              id="polish-input"
              className="task-input polish-search-input"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              rows={3}
              placeholder="예: 회의록을 팀에 보낼 수 있게 정리해줘"
            />
            <button
              className="task-start-button"
              type="button"
              disabled={!prompt.trim() || polishState === 'loading'}
              onClick={handlePolish}
            >
              {polishState === 'loading' ? '다듬는 중…' : '다듬기'}
            </button>
          </div>

          <div className="polish-examples" aria-label="예시로 시작">
            {EXAMPLE_PROMPTS.map((example) => (
              <button
                key={example}
                type="button"
                className="polish-example-chip"
                onClick={() => setPrompt(example)}
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

              <h3>다듬은 프롬프트</h3>
              <p>
                [ ] 로 남은 자리는 사용자가 채울 내용입니다 - 모델이 없는 내용을
                지어내지 않습니다.
              </p>
              <pre className="prompt-box"><code>{result.revisedPrompt}</code></pre>
              <div className="prompt-actions">
                <button className="prompt-copy-button" type="button" onClick={handleCopy}>
                  {copied ? '복사했습니다 ✓' : '프롬프트 복사'}
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

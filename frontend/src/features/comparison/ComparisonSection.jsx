import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useMemo, useState } from 'react';
import { buildCodingPrompt, buildPreferencePrompt, codingComparisonAxes, otherComparisonAxes } from './comparisonData';
import { startPreferenceSession, submitPreferenceChoice } from './codingApi';

const DEFAULT_TASK = '클릭 횟수를 보여주는 TypeScript/React 버튼 컴포넌트를 만들어 주세요.';

const remoteAxisLabels = {
  code_structure: {
    eyebrow: '코드 구조',
    question: '작은 기능을 어떤 구성으로 만들까요?',
    options: { compact: '간결하게 작성', separated: '역할별 파일로 분리' },
  },
  style_management: {
    eyebrow: '스타일 관리',
    question: '디자인 값을 어떻게 관리할까요?',
    options: { direct: '스타일 값을 바로 작성', theme: '나중에 전체 디자인을 쉽게 수정' },
  },
  type_detail: {
    eyebrow: '타입 작성',
    question: 'TypeScript 타입을 어느 정도로 작성할까요?',
    options: { inferred: '필요한 타입만 작성', explicit: '타입을 꼼꼼하게 작성' },
  },
  length: {
    eyebrow: '길이',
    question: '결과를 어느 정도로 작성할까요?',
    options: { short: '핵심만 짧게', normal: '적당한 분량으로', long: '상세하게 작성' },
  },
  sentiment: {
    eyebrow: '어조',
    question: '어떤 느낌으로 작성할까요?',
    options: { negative: '아쉬운 점을 강조', neutral: '담담하게 정리', positive: '좋았던 점을 강조' },
  },
  formality: {
    eyebrow: '말투',
    question: '어떤 말투가 더 편한가요?',
    options: { casual: '편하고 친근하게', neutral: '담담하게', formal: '격식 있게' },
  },
  structure: {
    eyebrow: '구조',
    question: '내용을 어떤 구조로 정리할까요?',
    options: { prose: '문단으로 자연스럽게', bullets: '목록으로 한눈에' },
  },
  extractiveness: {
    eyebrow: '표현 방식',
    question: '원문의 표현을 얼마나 살릴까요?',
    options: { normal: '내 표현으로 바꿔 쓰기', high: '원문 표현을 살리기', fully: '원문 문장을 그대로 발췌' },
  },
  topic: {
    eyebrow: '강조할 내용',
    question: '특히 어떤 내용을 중심으로 볼까요?',
    options: {},
  },
};

function getRemoteAxis(pair) {
  if (!pair) return null;
  const axisId = Object.keys(remoteAxisLabels).find(
    (name) => pair.a.combo?.[name] !== pair.b.combo?.[name],
  ) || Object.keys(pair.a.combo || {})[0] || 'code_structure';
  const copy = remoteAxisLabels[axisId];
  return {
    id: `${pair.pair_id}-${axisId}`,
    eyebrow: copy.eyebrow,
    question: copy.question,
    options: [pair.a, pair.b].map((candidate, index) => ({
      id: index === 0 ? 'a' : 'b',
      title: copy.options[candidate.combo?.[axisId]] || `예시 ${index === 0 ? 'A' : 'B'}`,
      description: '실제 코딩 도메인 데모 생성기가 만든 예시입니다.',
      code: candidate.text,
    })),
  };
}

function ComparisonSection({ onBack, domainKey = 'coding' }) {
  const isCoding = domainKey === 'coding';
  const staticAxes = isCoding ? codingComparisonAxes : otherComparisonAxes[domainKey];
  const domainCopy = {
    coding: { eyebrow: 'Coding preference', title: '마음에 드는 쪽을 고르세요.', task: DEFAULT_TASK, label: '만들고 싶은 기능' },
    review: { eyebrow: 'Review preference', title: '어떤 리뷰가 더 마음에 드나요?', task: 'A ramen restaurant visit: rich broth, long wait, friendly staff.', label: '리뷰로 만들 메모' },
    email: { eyebrow: 'Email preference', title: '어떤 이메일이 더 편한가요?', task: 'Ask the vendor to confirm the Q4 delivery date and share the updated invoice.', label: '이메일로 만들 요청' },
    summarization: { eyebrow: 'Document preference', title: '어떤 요약이 더 편한가요?', task: 'The product team moved the release to Friday after reviewing the final accessibility checklist.', label: '요약할 원문' },
    summarization_ko: { eyebrow: '한국어 문서 preference', title: '어떤 한국어 요약이 더 편한가요?', task: '제품 팀은 접근성 점검표를 검토한 뒤 출시 일정을 금요일로 변경했습니다.', label: '요약할 한국어 원문' },
  }[domainKey] || {};
  const [answers, setAnswers] = useState({});
  const [copied, setCopied] = useState(false);
  const [taskDescription, setTaskDescription] = useState(domainCopy.task);
  const [remoteSession, setRemoteSession] = useState(null);
  const [connection, setConnection] = useState('connecting');
  const [sessionRequested, setSessionRequested] = useState(false);

  const requestRemoteSession = async (sourceText) => {
    setSessionRequested(true);
    setConnection('connecting');
    try {
      const { session } = await startPreferenceSession(domainKey, sourceText.trim() || domainCopy.task, 8);
      setRemoteSession(session);
      setConnection('connected');
    } catch {
      setConnection('offline');
    }
  };

  useEffect(() => {
    let cancelled = false;
    startPreferenceSession(domainKey, domainCopy.task, 8)
      .then(({ session }) => {
        if (!cancelled) {
          setRemoteSession(session);
          setSessionRequested(true);
          setConnection('connected');
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSessionRequested(true);
          setConnection('offline');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [domainKey]);

  const staticAxisIndex = (staticAxes || []).findIndex(({ id }) => !answers[id]);
  const isRemote = Boolean(remoteSession);
  const isComplete = isRemote ? remoteSession.done : staticAxisIndex === -1;
  const currentAxis = isRemote
    ? getRemoteAxis(remoteSession.pair)
    : staticAxes?.[staticAxisIndex];
  const prompt = useMemo(
    () => (isComplete ? (remoteSession?.prompt || (isCoding ? buildCodingPrompt(answers) : buildPreferencePrompt(domainKey, staticAxes || [], answers))) : ''),
    [answers, domainKey, isCoding, isComplete, remoteSession, staticAxes],
  );
  const progress = isRemote
    ? (remoteSession.answered / remoteSession.total_rounds) * 100
    : (((staticAxes?.length || 1) - (staticAxisIndex === -1 ? 0 : (staticAxes?.length || 1) - staticAxisIndex)) / (staticAxes?.length || 1)) * 100;

  const handleOptionSelect = async (axisId, optionId) => {
    setCopied(false);
    if (isRemote) {
      setConnection('submitting');
      try {
        const { session } = await submitPreferenceChoice(
          remoteSession.session_id,
          remoteSession.pair.pair_id,
          optionId,
        );
        setRemoteSession(session);
        setConnection('connected');
      } catch {
        setConnection('offline');
      }
      return;
    }
    setAnswers((currentAnswers) => ({ ...currentAnswers, [axisId]: optionId }));
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(prompt);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <section className="comparison-section" id="comparison-section">
      <div className="comparison-inner">
        <button className="back-button" type="button" onClick={onBack}>
          ← 카테고리 다시 선택
        </button>

        <div className="comparison-heading">
          <p className="eyebrow">{domainCopy.eyebrow}</p>
          <h2>{domainCopy.title}</h2>
          <p>
            정답은 없습니다. 더 편하게 느껴지는 예시를 고르면 선택 기록이
            프롬프트에 반영됩니다.
          </p>
          <label className="task-input-label" htmlFor={`${domainKey}-task`}>
            {domainCopy.label}을 적어보세요 <span>(선택)</span>
          </label>
          <div className="task-input-row">
            <textarea
              id={`${domainKey}-task`}
              className="task-input"
              value={taskDescription}
              onChange={(event) => setTaskDescription(event.target.value)}
              rows={2}
              placeholder={DEFAULT_TASK}
            />
            <button
              className="task-start-button"
              type="button"
              disabled={!taskDescription.trim() || connection === 'connecting'}
              onClick={() => requestRemoteSession(taskDescription)}
            >
              이 내용으로 시작
            </button>
          </div>
          <p className="connection-note" role="status">
            {connection === 'connected' && '실제 코딩 도메인 데모 생성기와 연결됨'}
            {connection === 'connecting' && '코딩 예시를 준비하는 중…'}
            {connection === 'submitting' && '선택을 기록하는 중…'}
            {connection === 'offline' && '로컬 예시로 계속 진행합니다 (API 없이도 사용 가능)'}
          </p>
        </div>

        <div className="comparison-progress" aria-label="진행 상황">
          <span className="comparison-progress-bar">
            <span style={{ width: `${progress}%` }} />
          </span>
          <span>
              {isComplete
              ? '선택 완료'
              : isRemote
                ? `${remoteSession.answered} / ${remoteSession.total_rounds}`
                : `${staticAxisIndex + 1} / ${staticAxes?.length || 0}`}
          </span>
        </div>

        <AnimatePresence mode="wait">
          {!isComplete && currentAxis && (
            <motion.div
              className="comparison-question"
              key={currentAxis.id}
              initial={{ opacity: 0, x: 28 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -28 }}
              transition={{ duration: 0.35, ease: 'easeOut' }}
            >
              <p className="question-eyebrow">{currentAxis.eyebrow}</p>
              <h3>{currentAxis.question}</h3>

              <div className="comparison-options">
                {currentAxis.options.map((option) => (
                  <button
                    className="comparison-option"
                    key={option.id}
                    type="button"
                    disabled={connection === 'submitting'}
                    onClick={() => handleOptionSelect(currentAxis.id, option.id)}
                  >
                    <span className="option-copy">
                      <strong>{option.title}</strong>
                      <span>{option.description}</span>
                    </span>
                    <pre><code>{option.code}</code></pre>
                    <span className="option-arrow" aria-hidden="true">→</span>
                  </button>
                ))}
              </div>
            </motion.div>
          )}

          {isComplete && (
            <motion.div
              className="prompt-result"
              key="prompt-result"
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, ease: 'easeOut' }}
            >
              <p className="question-eyebrow">Your preference prompt</p>
              <h3>나만의 {isCoding ? '코딩' : domainKey === 'review' ? '리뷰' : domainKey === 'email' ? '이메일' : '요약'} 프롬프트가 완성됐어요.</h3>
              <p>아래 내용을 복사해서 ChatGPT나 Claude에 바로 사용할 수 있습니다.</p>
              <pre className="prompt-box"><code>{prompt}</code></pre>
              <div className="prompt-actions">
                <button className="prompt-copy-button" type="button" onClick={handleCopy}>
                  {copied ? '복사했습니다 ✓' : '프롬프트 복사'}
                </button>
                <button className="prompt-reset-button" type="button" onClick={onBack}>
                  다시 선택하기
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {!sessionRequested && (
          <p className="comparison-fallback-note">무료 데모를 준비하고 있습니다.</p>
        )}
      </div>
    </section>
  );
}

export default ComparisonSection;

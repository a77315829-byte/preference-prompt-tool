import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useMemo, useState } from 'react';
import { buildCodingPrompt, buildPreferencePrompt, codingComparisonAxes, otherComparisonAxes } from './comparisonData';
import { fetchHealth, fetchSession, startOptimization, startPreferenceSession, submitPreferenceChoice, undoPreferenceChoice } from './codingApi';
import ExportPanel from '../../shared/components/ExportPanel';
import TeamPanel from '../../shared/components/TeamPanel';
import PromptLanguageSwitch from '../../shared/components/PromptLanguageSwitch';

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
  specificity: {
    eyebrow: '설명 밀도',
    question: '얼마나 구체적으로 설명할까요?',
    options: { normal: '큰 흐름만', high: '세부 내용까지' },
  },
  conciseness: {
    eyebrow: '문장 밀도',
    question: '문장을 얼마나 간결하게 다듬을까요?',
    options: { concise: '짧고 선명하게', moderate: '균형 있게', detailed: '맥락을 충분히' },
  },
  sentence_complexity: {
    eyebrow: '문장 난이도',
    question: '문장 구조를 어느 정도로 만들까요?',
    options: { simple: '쉽게 나누어 쓰기', moderate: '균형 있게', complex: '정교하게 연결하기' },
  },
  focus_on_entities: {
    eyebrow: '강조점',
    question: '무엇을 더 눈에 띄게 할까요?',
    options: { general: '전체 흐름 중심', mixed: '흐름과 대상을 함께', 'entity-focused': '이름과 숫자 중심' },
  },
  topic: {
    eyebrow: '강조할 내용',
    question: '특히 어떤 내용을 중심으로 볼까요?',
    options: {},
  },
};

function getRemoteAxis(pair, demoMode = true) {
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
      description: demoMode
        ? '규칙 기반 데모 생성기가 만든 예시입니다.'
        : 'AI가 입력한 원문으로 직접 쓴 예시입니다.',
      code: candidate.text,
    })),
  };
}

function ComparisonSection({ onBack, domainKey = 'coding', onSwitchDomain, template = null }) {
  const isCoding = domainKey === 'coding';
  const staticAxes = isCoding ? codingComparisonAxes : otherComparisonAxes[domainKey];
  const domainCopy = {
    coding: { eyebrow: 'Coding preference', title: '마음에 드는 쪽을 고르세요.', task: DEFAULT_TASK, label: '만들고 싶은 기능' },
    review: { eyebrow: 'Review preference', title: '어떤 리뷰가 더 마음에 드나요?', task: 'A ramen restaurant visit: rich broth, long wait, friendly staff.', label: '리뷰로 만들 메모' },
    email: { eyebrow: 'Email preference', title: '어떤 이메일이 더 편한가요?', task: 'Ask the vendor to confirm the Q4 delivery date and share the updated invoice.', label: '이메일로 만들 요청' },
    summarization: { eyebrow: 'Document preference', title: '어떤 요약이 더 편한가요?', task: 'The product team moved the release to Friday after reviewing the final accessibility checklist.', label: '요약할 원문' },
    summarization_ko: { eyebrow: '한국어 문서 preference', title: '어떤 한국어 요약이 더 편한가요?', task: '제품 팀은 접근성 점검표를 검토한 뒤 출시 일정을 금요일로 변경했습니다.', label: '요약할 한국어 원문' },
    summarization_hybrid: { eyebrow: 'Deep summary preference', title: '어떤 심화 요약이 더 편한가요?', task: 'The product team moved the release to Friday after reviewing the final accessibility checklist and tracking three unresolved issues.', label: '심화 요약할 원문' },
    macsum_eval_agent: { eyebrow: 'Document quality preference', title: '어떤 문서 다듬기가 더 편한가요?', task: 'The launch plan includes several updates, and the team needs a clear summary of owners, dates, and risks.', label: '다듬을 문서' },
  }[domainKey] || {};
  const [answers, setAnswers] = useState({});
  const [copied, setCopied] = useState(false);
  const [taskDescription, setTaskDescription] = useState(domainCopy.task);
  const [remoteSession, setRemoteSession] = useState(null);
  const [connection, setConnection] = useState('connecting');
  const [sessionRequested, setSessionRequested] = useState(false);
  const [optimizeError, setOptimizeError] = useState('');
  // 사용자가 고른 프롬프트 언어. 고르기 전에는 서버의 기본값을 쓴다.
  const [promptLanguage, setPromptLanguage] = useState(null);

  const requestRemoteSession = async (sourceText) => {
    setSessionRequested(true);
    setConnection('connecting');
    try {
      const { session } = await startPreferenceSession(domainKey, sourceText.trim() || domainCopy.task, 8, template?.id);
      setRemoteSession(session);
      setConnection('connected');
    } catch {
      setConnection('offline');
    }
  };

  // 데모 서버면 기본 예문으로 바로 세션을 연다 (무료). 실제 생성 서버면
  // 열지 않고 "이 내용으로 시작"을 기다린다 - 자동으로 열면 방문만으로 하루
  // 상한이 하나씩 줄고(개발 모드 StrictMode 에서는 둘), 사용자가 자기 글로
  // 시작하면 또 하나가 준다.
  useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then((health) => {
        if (cancelled) return null;
        if (health.live) {
          setConnection('idle');
          return null;
        }
        return startPreferenceSession(domainKey, domainCopy.task, 8, template?.id);
      })
      .then((result) => {
        if (!result) return;
        const { session } = result;
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
    ? getRemoteAxis(remoteSession.pair, remoteSession.demo_mode)
    : staticAxes?.[staticAxisIndex];
  // 서버가 언어별 프롬프트를 함께 준다. 기본값(보통 English)은 prompt_language.
  const promptLanguages = Object.keys(remoteSession?.prompts || {});
  const activeLanguage = promptLanguages.includes(promptLanguage) ? promptLanguage : remoteSession?.prompt_language;
  const prompt = useMemo(
    () => (isComplete
      ? (remoteSession?.prompts?.[activeLanguage] || remoteSession?.prompt
        || (isCoding ? buildCodingPrompt(answers) : buildPreferencePrompt(domainKey, staticAxes || [], answers)))
      : ''),
    [activeLanguage, answers, domainKey, isCoding, isComplete, remoteSession, staticAxes],
  );
  const exportsForLanguage = remoteSession?.exports_by_language?.[activeLanguage] || remoteSession?.exports;
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

  // 마지막 선택 되돌리기. 결과 화면에서 누르면 프롬프트가 사라지고 마지막 질문으로 돌아간다.
  const handleUndo = async () => {
    setConnection('submitting');
    try {
      const { session } = await undoPreferenceChoice(remoteSession.session_id);
      setRemoteSession(session);
      setCopied(false);
      setPromptLanguage(null);
      setConnection('connected');
    } catch {
      setConnection('offline');
    }
  };

  const optimizeStatus = remoteSession?.optimize_status || 'idle';
  const canOptimize = isRemote && isComplete && remoteSession.demo_mode === false;

  // 최적화가 도는 동안 1초마다 진행률을 물어본다. 끝나면 서버가 돌려준
  // session.prompt 가 최적화된 프롬프트로 바뀌어 있다.
  useEffect(() => {
    if (!remoteSession || optimizeStatus !== 'running') return undefined;
    const timer = setInterval(() => {
      fetchSession(remoteSession.session_id)
        .then(({ session }) => setRemoteSession(session))
        .catch(() => {});
    }, 1000);
    return () => clearInterval(timer);
  }, [remoteSession?.session_id, optimizeStatus]);

  const handleOptimize = async () => {
    setOptimizeError('');
    try {
      const { session } = await startOptimization(remoteSession.session_id);
      setRemoteSession(session);
    } catch (error) {
      setOptimizeError(error.message);
    }
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
          {template && (
            <p className="template-banner">
              템플릿 <strong>{template.title}</strong>을 내 방식으로 바꾸는 중입니다. 결과는 템플릿 본문에
              고른 선호가 더해진 프롬프트입니다.
            </p>
          )}
          {!template && onSwitchDomain && (domainKey === 'summarization' || domainKey === 'summarization_ko') && (
            <div className="language-switch" role="group" aria-label="요약 언어">
              {[['summarization', '영어 요약'], ['summarization_ko', '한국어 요약']].map(([key, label]) => (
                <button key={key} type="button" aria-pressed={domainKey === key}
                  disabled={domainKey === key} onClick={() => onSwitchDomain(key)}>
                  {label}
                </button>
              ))}
            </div>
          )}
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
            {connection === 'connected' && (remoteSession?.demo_mode === false
              ? 'AI 실시간 생성과 연결됨'
              : '데모 생성기와 연결됨 (규칙 기반 예시)')}
            {connection === 'connecting' && '예시를 준비하는 중…'}
            {connection === 'idle' && 'AI 실시간 생성 모드입니다. 내용을 확인하고 "이 내용으로 시작"을 누르면 예시를 만듭니다.'}
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
          {!isComplete && currentAxis && connection !== 'idle' && (
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
                    <pre className={isCoding ? undefined : 'option-prose'}><code>{option.code}</code></pre>
                    <span className="option-arrow" aria-hidden="true">→</span>
                  </button>
                ))}
              </div>
              {isRemote && (
                <div className="comparison-secondary-actions">
                  <button type="button" className="prompt-reset-button" disabled={connection === 'submitting'}
                    onClick={() => handleOptionSelect(currentAxis.id, 'tie')}>
                    비슷해요 · 고르기 어려워요
                  </button>
                  <button type="button" className="prompt-reset-button"
                    disabled={connection === 'submitting' || !remoteSession.answered}
                    onClick={handleUndo}>
                    ← 이전 선택 수정
                  </button>
                </div>
              )}
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
              <h3>나만의 {isCoding ? '코딩' : domainKey === 'review' ? '리뷰' : domainKey === 'email' ? '이메일' : domainKey === 'macsum_eval_agent' ? '문서 품질' : '요약'} 프롬프트가 완성됐어요.</h3>
              <p>아래 내용을 복사해서 ChatGPT나 Claude에 바로 사용할 수 있습니다.</p>
              <PromptLanguageSwitch
                languages={promptLanguages}
                value={activeLanguage}
                onChange={(language) => { setPromptLanguage(language); setCopied(false); }}
              />
              {remoteSession?.undecided_axes?.length > 0 && (
                <p className="connection-note">
                  {remoteSession.undecided_axes.map((a) => a.label).join(', ')}은(는) "비슷해요"만 골라 선호를 정하지 못해
                  프롬프트에 넣지 않았습니다. 넣고 싶으면 "마지막 선택 수정"으로 돌아가 한쪽을 골라 주세요.
                </p>
              )}
              <pre className="prompt-box"><code>{prompt}</code></pre>
              {canOptimize && optimizeStatus === 'running' && (
                <div className="comparison-progress" aria-label="최적화 진행 상황">
                  <span className="comparison-progress-bar">
                    <span style={{ width: `${Math.round(remoteSession.optimize_progress * 100)}%` }} />
                  </span>
                  <span>최적화 중 {Math.round(remoteSession.optimize_progress * 100)}%</span>
                </div>
              )}
              {canOptimize && optimizeStatus !== 'done' && (
                <p className="connection-note">
                  선호 기준 최적화(GEPA)의 기준: 이 카테고리의 예시 글 3개에 프롬프트를 적용해, 방금 고른
                  선호(분량, 표현 방식 등)를 결과물이 실제로 지키는지 코드로 채점합니다. AI가 고쳐 쓴
                  프롬프트는 이 점수가 오를 때만 채택하고, 입력한 글의 내용이 들어간 프롬프트는
                  버립니다.
                </p>
              )}
              {canOptimize && optimizeStatus === 'done' && (
                <p className="connection-note">
                  {remoteSession.optimize_changed
                    ? 'GEPA 로 최적화한 프롬프트입니다.'
                    : '최적화 후보가 기본 프롬프트보다 낫지 않아 기본 프롬프트를 그대로 유지했습니다.'}
                  {remoteSession.optimize_report && (
                    <>
                      {' '}선호 준수 점수(예시 글 {remoteSession.optimize_report.eval_inputs}개 평균, 1이 만점):{' '}
                      기본 {remoteSession.optimize_report.seed_score.toFixed(2)} → 최종{' '}
                      {remoteSession.optimize_report.final_score.toFixed(2)}.
                      {remoteSession.optimize_report.leaky_skipped > 0
                        && ` 입력한 글의 내용이 들어가 버린 후보 ${remoteSession.optimize_report.leaky_skipped}개는 제외했습니다.`}
                    </>
                  )}
                </p>
              )}
              {canOptimize && optimizeStatus === 'error' && (
                <p className="connection-note">최적화 중 API 호출이 실패했습니다. 위의 기본 프롬프트는 그대로 쓸 수 있습니다.</p>
              )}
              {optimizeError && <p className="connection-note">{optimizeError}</p>}
              {/* 최적화 중에는 옛 프롬프트를 내보내지 않도록 숨긴다. */}
              {optimizeStatus !== 'running' && <ExportPanel exports={exportsForLanguage} />}
              {isRemote && remoteSession.done && (
                <TeamPanel sessionId={remoteSession.session_id}
                  valueLabel={(axis, value) => remoteAxisLabels[axis]?.options?.[value] || value} />
              )}
              <div className="prompt-actions">
                <button className="prompt-copy-button" type="button" onClick={handleCopy}>
                  {copied ? '복사했습니다 ✓' : '프롬프트 복사'}
                </button>
                {canOptimize && optimizeStatus !== 'running' && optimizeStatus !== 'done' && (
                  <button className="prompt-reset-button" type="button" onClick={handleOptimize}>
                    선호 기준으로 최적화 (GEPA, 1~2분)
                  </button>
                )}
                {isRemote && optimizeStatus !== 'running' && (
                  <button className="prompt-reset-button" type="button" onClick={handleUndo}>
                    ← 마지막 선택 수정
                  </button>
                )}
                <button className="prompt-reset-button" type="button" onClick={onBack}>
                  다시 선택하기
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {!sessionRequested && connection !== 'idle' && (
          <p className="comparison-fallback-note">무료 데모를 준비하고 있습니다.</p>
        )}
      </div>
    </section>
  );
}

export default ComparisonSection;

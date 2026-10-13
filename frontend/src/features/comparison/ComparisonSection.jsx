import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { fetchHealth, fetchSession, startOptimization, startPreferenceSession, submitPreferenceChoice, undoPreferenceChoice } from './codingApi';
import ExportPanel from '../../shared/components/ExportPanel';
import TeamPanel from '../../shared/components/TeamPanel';
import PromptLanguageSwitch from '../../shared/components/PromptLanguageSwitch';

const DEFAULT_TASK = '클릭 횟수를 보여주는 TypeScript/React 버튼 컴포넌트를 만들어 주세요.';

const demoReasonText = {
  live_disabled: '무료 데모 모드입니다. AI를 호출하지 않고 준비된 예시로 비교합니다.',
  api_key_missing: 'API 키가 없어 무료 데모로 진행합니다. 입력한 기능의 코드는 생성하지 않습니다.',
  daily_limit: '오늘의 AI 생성 한도에 도달해 무료 데모로 진행합니다.',
  generation_failed: 'AI 생성이 실패해 무료 데모로 전환했습니다. 입력한 기능의 코드는 생성하지 않습니다.',
};

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

function codePreview(text) {
  const firstBlock = text.match(/```[^\n]*\n([\s\S]*?)```/);
  return firstBlock ? firstBlock[1].trim() : text;
}

function getRemoteAxis(pair, demoMode = true) {
  if (!pair) return null;
  const axisId = Object.keys(remoteAxisLabels).find(
    (name) => pair.a.combo?.[name] !== pair.b.combo?.[name],
  ) || Object.keys(pair.a.combo || {})[0] || 'code_structure';
  const copy = remoteAxisLabels[axisId] || {
    eyebrow: pair.axis_label || '선호 기준',
    question: pair.question || '어떤 결과가 더 마음에 드나요?',
    options: {},
  };
  return {
    id: `${pair.pair_id}-${axisId}`,
    eyebrow: copy.eyebrow,
    question: copy.question,
    options: [pair.a, pair.b].map((candidate, index) => ({
      id: index === 0 ? 'a' : 'b',
      title: copy.options[candidate.combo?.[axisId]] || `예시 ${index === 0 ? 'A' : 'B'}`,
      description: demoMode
        ? '규칙 기반 데모 생성기가 만든 예시입니다.'
        : 'AI가 입력한 내용을 기준으로 직접 쓴 예시입니다.',
      code: candidate.text,
      preview: codePreview(candidate.text),
    })),
  };
}

function ComparisonSection({ onBack, domainKey = 'coding', onSwitchDomain, template = null, initialDraft = null, onDraftChange }) {
  const isCoding = domainKey === 'coding';
  const domainCopy = {
    coding: { eyebrow: 'Coding preference', title: '마음에 드는 쪽을 고르세요.', task: DEFAULT_TASK, label: '만들고 싶은 기능' },
    review: { eyebrow: 'Review preference', title: '어떤 리뷰가 더 마음에 드나요?', task: 'A ramen restaurant visit: rich broth, long wait, friendly staff.', label: '리뷰로 만들 메모' },
    email: { eyebrow: 'Email preference', title: '어떤 이메일이 더 편한가요?', task: 'Ask the vendor to confirm the Q4 delivery date and share the updated invoice.', label: '이메일로 만들 요청' },
    summarization: { eyebrow: 'Document preference', title: '어떤 요약이 더 편한가요?', task: 'The product team moved the release to Friday after reviewing the final accessibility checklist. Three issues remain unresolved before launch. Dana will review the design changes on Thursday. The team will publish a revised plan after that review. The support team will prepare customer notices. The next status update is scheduled for Friday afternoon.', label: '요약할 원문' },
    summarization_ko: { eyebrow: '한국어 문서 preference', title: '어떤 한국어 요약이 더 편한가요?', task: '제품 팀은 접근성 점검표를 검토한 뒤 출시 일정을 금요일로 변경했습니다. 출시 전 해결해야 할 문제 세 가지가 남아 있습니다. 다나는 목요일에 디자인 변경 사항을 검토할 예정입니다. 팀은 검토 후 수정된 계획을 공개할 예정입니다. 고객 지원팀은 이용자 안내문을 준비합니다. 다음 진행 상황은 금요일 오후에 공유할 예정입니다.', label: '요약할 한국어 원문' },
    summarization_hybrid: { eyebrow: 'Deep summary preference', title: '어떤 심화 요약이 더 편한가요?', task: 'The product team moved the release to Friday after reviewing the final accessibility checklist. Three issues remain unresolved before launch. Dana will review the design changes on Thursday. The team will publish a revised plan after that review. The support team will prepare customer notices. The next status update is scheduled for Friday afternoon.', label: '심화 요약할 원문' },
    macsum_eval_agent: { eyebrow: 'Document quality preference', title: '어떤 문서 다듬기가 더 편한가요?', task: "The team hasn't confirmed the launch date because two risks remain open. Dana owns the design review, and Alex owns testing. The launch plan covers the October release.", label: '다듬을 문서' },
  }[domainKey] || {};
  const [copied, setCopied] = useState(false);
  const [copiedWithTask, setCopiedWithTask] = useState(false);
  const [taskDescription, setTaskDescription] = useState(initialDraft?.taskDescription || domainCopy.task);
  const [remoteSession, setRemoteSession] = useState(initialDraft?.session || null);
  const [connection, setConnection] = useState(initialDraft?.session ? 'connected' : 'checking');
  const [sessionError, setSessionError] = useState('');
  const [optimizeError, setOptimizeError] = useState('');
  // 사용자가 고른 프롬프트 언어. 고르기 전에는 서버의 기본값을 쓴다.
  const [promptLanguage, setPromptLanguage] = useState(null);
  const [previewOption, setPreviewOption] = useState(null);

  useEffect(() => {
    if (!previewOption) return undefined;
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setPreviewOption(null);
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [previewOption]);


  useEffect(() => {
    if (remoteSession) onDraftChange?.({ session: remoteSession, taskDescription });
  }, [remoteSession, taskDescription, onDraftChange]);

  const requestRemoteSession = async (sourceText) => {
    setConnection('connecting');
    setSessionError('');
    setCopied(false);
    setCopiedWithTask(false);
    try {
      const { session } = await startPreferenceSession(domainKey, sourceText.trim() || domainCopy.task, 8, template?.id);
      setRemoteSession(session);
      setConnection('connected');
    } catch (error) {
      setConnection('offline');
      setSessionError(error.message || '예시를 불러오지 못했습니다. 서버 연결을 확인해 주세요.');
    }
  };

  // 방문만으로 세션을 만들지 않는다. 사용자가 원문을 확인하고 시작해야
  // 데모/실제 모드 모두 자기 입력으로 생성하며, 실 API 쿼터도 낭비하지 않는다.
  useEffect(() => {
    if (initialDraft?.session) return undefined;
    let cancelled = false;
    fetchHealth()
      .then((health) => {
        if (!cancelled) setConnection(health.liveConfigured ? 'live-ready' : 'demo-ready');
      })
      .catch(() => {
        if (!cancelled) {
          setConnection('offline');
          setSessionError('로컬 서버에 연결할 수 없습니다. 데모도 서버를 실행해야 사용할 수 있습니다.');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [domainKey, initialDraft?.session]);

  const isRemote = Boolean(remoteSession);
  const isComplete = Boolean(remoteSession?.done);
  const currentAxis = getRemoteAxis(remoteSession?.pair, remoteSession?.demo_mode);
  useEffect(() => { setPreviewOption(null); }, [currentAxis?.id]);
  const otherPreviewOption = previewOption && currentAxis?.options?.find((option) => option.id !== previewOption.id);
  const identicalExamples = currentAxis?.options?.length === 2
    && currentAxis.options[0].code === currentAxis.options[1].code;
  // 서버가 언어별 프롬프트를 함께 준다. 기본값(보통 English)은 prompt_language.
  const promptLanguages = Object.keys(remoteSession?.prompts || {});
  const activeLanguage = promptLanguages.includes(promptLanguage) ? promptLanguage : remoteSession?.prompt_language;
  const prompt = useMemo(
    () => (isComplete
      ? (remoteSession?.prompts?.[activeLanguage] || remoteSession?.prompt || '')
      : ''),
    [activeLanguage, isComplete, remoteSession],
  );
  const exportsForLanguage = remoteSession?.exports_by_language?.[activeLanguage] || remoteSession?.exports;
  const progress = isRemote ? (remoteSession.answered / remoteSession.total_rounds) * 100 : 0;

  const handleOptionSelect = async (optionId) => {
    setCopied(false);
    setCopiedWithTask(false);
    setSessionError('');
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
      } catch (error) {
        setConnection('connected');
        setSessionError(error.message || '선택을 저장하지 못했습니다. 다시 시도해 주세요.');
      }
      return;
    }
  };

  // 마지막 선택 되돌리기. 결과 화면에서 누르면 프롬프트가 사라지고 마지막 질문으로 돌아간다.
  const handleUndo = async () => {
    setSessionError('');
    setConnection('submitting');
    try {
      const { session } = await undoPreferenceChoice(remoteSession.session_id);
      setRemoteSession(session);
      setCopied(false);
      setCopiedWithTask(false);
      setPromptLanguage(null);
      setConnection('connected');
    } catch (error) {
      setConnection('connected');
      setSessionError(error.message || '선택을 되돌리지 못했습니다. 다시 시도해 주세요.');
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

  const handleCopyWithTask = async () => {
    try {
      await navigator.clipboard.writeText(`${prompt}\n\n개발 요청:\n${remoteSession.source_text.trim()}`);
      setCopiedWithTask(true);
    } catch {
      setCopiedWithTask(false);
    }
  };

  return (
    <section className={`comparison-section preference-comparison ${isCoding ? 'is-coding' : ''} ${isRemote ? `has-session ${isComplete ? 'is-complete' : 'is-choosing'}` : 'is-setup'}`} id="comparison-section">
      <div className="comparison-inner">
        <button className="back-button" type="button" onClick={onBack}>
          ← 카테고리 다시 선택
        </button>

        <div className="comparison-heading">
          <p className="eyebrow">{domainCopy.eyebrow}</p>
          <h2>{isRemote ? (isComplete ? '선택이 프롬프트가 됐어요.' : domainCopy.title) : '비교할 내용을 알려주세요.'}</h2>
          {!isRemote && <p>내 작업에 가까운 내용을 적고, 두 예시 중 더 편한 쪽을 고르세요.</p>}
          {!isRemote && template && (
            <p className="template-banner">
              템플릿 <strong>{template.title}</strong>을 내 방식으로 바꾸는 중입니다. 결과는 템플릿 본문에
              고른 선호가 더해진 프롬프트입니다.
            </p>
          )}
          {!isRemote && !template && onSwitchDomain && (domainKey === 'summarization' || domainKey === 'summarization_ko') && (
            <div className="language-switch" role="group" aria-label="요약 언어">
              {[['summarization', '영어 요약'], ['summarization_ko', '한국어 요약']].map(([key, label]) => (
                <button key={key} type="button" aria-pressed={domainKey === key}
                  disabled={domainKey === key} onClick={() => onSwitchDomain(key)}>
                  {label}
                </button>
              ))}
            </div>
          )}
          {!isRemote && <label className="task-input-label" htmlFor={`${domainKey}-task`}>
            {domainCopy.label} 입력하기
          </label>}
          {!isRemote && isCoding && (
            <div className="coding-demo-guide">
              <p>만들고 싶은 기능을 적어주세요. 두 코드를 비교하며 코드 구성, 디자인 값 관리, 타입 작성 취향을 찾습니다.</p>
              {connection === 'live-ready' ? (
                <p>실시간 AI 모드에서는 입력한 기능을 기준으로 A/B 코드를 생성합니다. 생성 실패나 사용 한도 도달 시 준비된 과제의 데모로 전환될 수 있으며, 화면에 표시됩니다.</p>
              ) : (
                <p>무료 데모에서는 준비된 작은 과제로 작성 스타일만 비교합니다. 입력한 기능은 결과 프롬프트와 함께 복사할 수 있지만, 해당 기능의 코드를 생성하지는 않습니다.</p>
              )}
            </div>
          )}
          {!isRemote && <div className="task-input-row">
            <textarea
              id={`${domainKey}-task`}
              className="task-input"
              value={taskDescription}
              onChange={(event) => setTaskDescription(event.target.value)}
              rows={2}
              placeholder={domainCopy.task || '비교할 내용을 적어 주세요.'}
            />
            <button
              className="task-start-button"
              type="button"
              disabled={!taskDescription.trim() || connection === 'connecting' || connection === 'checking'}
              onClick={() => requestRemoteSession(taskDescription)}
            >
              이 내용으로 시작
            </button>
          </div>}
          {!isRemote && (domainKey === 'summarization' || domainKey === 'summarization_ko') && (
            <p className="comparison-source-hint">요약 길이를 비교하려면 여러 문장으로 된 원문을 입력해 주세요. 짧은 원문은 두 예시가 같아질 수 있습니다.</p>
          )}
          {isRemote && <p className="comparison-task-summary" title={taskDescription}>입력한 내용 · {taskDescription}</p>}
          {isRemote && isCoding && remoteSession.demo_mode && !isComplete && (
            <p className="coding-demo-warning" role="status">
              <span className="coding-demo-warning-full">현재 비교 과제: {remoteSession.coding_demo_task || '준비된 코딩 예시'} · 입력한 기능의 구현안이 아니라 작성 스타일을 비교하는 코드입니다.</span>
              <span className="coding-demo-warning-compact">준비된 예시입니다. 입력한 기능의 구현안은 아닙니다.</span>
            </p>
          )}
          <p className="connection-note" role="status">
            {connection === 'connected' && (remoteSession?.demo_mode === false
              ? 'AI 실시간 생성과 연결됨'
              : demoReasonText[remoteSession?.demo_reason] || '데모 생성기와 연결됨 (규칙 기반 예시)')}
            {connection === 'connecting' && '예시를 준비하는 중…'}
            {connection === 'live-ready' && 'AI 실시간 생성 모드입니다. 시작하면 모델 사용량이 발생할 수 있습니다.'}
            {connection === 'demo-ready' && '무료 데모 모드입니다. API 키 없이 예시를 만들 수 있습니다.'}
            {connection === 'checking' && '서버 연결을 확인하는 중…'}
            {connection === 'submitting' && '선택을 기록하는 중…'}
            {connection === 'offline' && '서버 연결을 확인해 주세요.'}
          </p>
          {sessionError && <p className="comparison-error" role="alert">{sessionError}</p>}
        </div>

        {isRemote && <div className="comparison-progress" aria-label="진행 상황">
          <span className="comparison-progress-bar">
            <span style={{ width: `${progress}%` }} />
          </span>
          <span>
              {isComplete
              ? '선택 완료'
              : `${remoteSession.answered} / ${remoteSession.total_rounds}`}
          </span>
        </div>}

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
              {identicalExamples && (
                <p className="comparison-identical-note" role="status">
                  두 예시가 같습니다. 아래 ‘비슷해요’를 고르거나, 카테고리로 돌아가 입력 내용을 바꿔 다시 시작해 주세요.
                </p>
              )}

              <div className="comparison-options">
                {currentAxis.options.map((option, index) => (
                  <div className="comparison-option-wrap" key={option.id}>
                    <button
                      className="comparison-option"
                      type="button"
                      disabled={connection === 'submitting'}
                      onClick={() => handleOptionSelect(option.id)}
                      aria-label={`예시 ${index === 0 ? 'A' : 'B'} 선택: ${option.title}`}
                    >
                      <span className="option-index">{index === 0 ? 'A' : 'B'} / {currentAxis.eyebrow}</span>
                      <span className="option-copy">
                        <strong>{option.title}</strong>
                        <span>{option.description}</span>
                      </span>
                      <pre className={isCoding ? undefined : 'option-prose'}><code>{isCoding ? option.preview : option.code}</code></pre>
                      <span className="option-arrow" aria-hidden="true">→</span>
                    </button>
                    <button
                      className="comparison-preview-button"
                      type="button"
                      onClick={() => setPreviewOption({ ...option, label: index === 0 ? 'A' : 'B' })}
                    >
                      {isCoding ? '코드 전체 보기' : '전체 보기'}
                    </button>
                  </div>
                ))}
              </div>
              {isRemote && (
                <div className="comparison-secondary-actions">
                  <button type="button" className="prompt-reset-button" disabled={connection === 'submitting'}
                    onClick={() => handleOptionSelect('tie')}>
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
              {isCoding && (
                <div className="coding-result-context">
                  <h4>이번에 만들 기능</h4>
                  <p>{remoteSession?.source_text}</p>
                  {remoteSession?.demo_mode && (
                    <p>무료 데모는 이 기능을 구현하지 않았습니다. 아래 시스템 프롬프트에는 선택한 코딩 스타일이 반영되며, 기능 요청은 함께 복사해 사용할 수 있습니다.</p>
                  )}
                  <h4>선택에서 찾은 취향</h4>
                  <ul>
                    {remoteSession?.axes?.filter((axis) => axis.estimate).map((axis) => (
                      <li key={axis.name}>
                        {remoteAxisLabels[axis.name]?.eyebrow || axis.name}: {' '}
                        {remoteAxisLabels[axis.name]?.options?.[axis.estimate] || axis.estimate}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
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
                <>
                  <p className="connection-note">최적화 중입니다. 완료 전에는 이전 프롬프트를 복사하거나 내보낼 수 없습니다.</p>
                  <div className="comparison-progress" aria-label="최적화 진행 상황">
                    <span className="comparison-progress-bar">
                      <span style={{ width: `${Math.round(remoteSession.optimize_progress * 100)}%` }} />
                    </span>
                    <span>최적화 중 {Math.round(remoteSession.optimize_progress * 100)}%</span>
                  </div>
                </>
              )}
              {canOptimize && optimizeStatus !== 'done' && (
                <p className="connection-note">
                  선호 기준 최적화(GEPA)는 이 카테고리의 예시 {isCoding ? '개발 요청' : '입력'} 3개에 프롬프트를
                  적용해, 선택한 선호({isCoding ? '코드 구성, 스타일 관리, 타입 작성' : '분량, 표현 방식 등'})를
                  결과물이 실제로 지키는지 채점합니다. AI가 고쳐 쓴 프롬프트는 점수가 오를 때만 채택하고,
                  이번에 입력한 {isCoding ? '개발 요청' : '내용'}이 박혀 재사용하기 어려운 프롬프트는 제외합니다.
                </p>
              )}
              {canOptimize && optimizeStatus === 'done' && (
                <p className="connection-note">
                  {remoteSession.optimize_changed
                    ? 'GEPA 로 최적화한 프롬프트입니다.'
                    : '최적화 후보가 기본 프롬프트보다 낫지 않아 기본 프롬프트를 그대로 유지했습니다.'}
                  {remoteSession.optimize_report && (
                    <>
                      {' '}선호 준수 점수(예시 {isCoding ? '개발 요청' : '입력'} {remoteSession.optimize_report.eval_inputs}개 평균, 1이 만점):{' '}
                      기본 {remoteSession.optimize_report.seed_score.toFixed(2)} → 최종{' '}
                      {remoteSession.optimize_report.final_score.toFixed(2)}.
                      {remoteSession.optimize_report.leaky_skipped > 0
                        && ` 이번 입력 내용이 들어가 버린 후보 ${remoteSession.optimize_report.leaky_skipped}개는 제외했습니다.`}
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
                <button className="prompt-copy-button" type="button" disabled={optimizeStatus === 'running'} onClick={handleCopy}>
                  {copied ? '복사했습니다 ✓' : '시스템 프롬프트 복사'}
                </button>
                {isCoding && (
                  <button className="prompt-reset-button" type="button" disabled={optimizeStatus === 'running'} onClick={handleCopyWithTask}>
                    {copiedWithTask ? '복사했습니다 ✓' : '프롬프트 + 개발 요청 복사'}
                  </button>
                )}
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

      </div>
      {previewOption && createPortal(
        <div className="comparison-preview-backdrop" onClick={() => setPreviewOption(null)}>
          <div className="comparison-preview-dialog" role="dialog" aria-modal="true" aria-label={`예시 ${previewOption.label} 전체 보기`} onClick={(event) => event.stopPropagation()}>
            <div className="comparison-preview-header">
              <div><span>예시 {previewOption.label}</span><h3>{previewOption.title}</h3></div>
              <button type="button" onClick={() => setPreviewOption(null)} aria-label="전체 보기 닫기">닫기 ×</button>
            </div>
            <pre className={isCoding ? undefined : 'option-prose'}><code>{previewOption.code}</code></pre>
            {otherPreviewOption && (
              <button type="button" className="comparison-preview-switch"
                onClick={() => setPreviewOption({ ...otherPreviewOption, label: previewOption.label === 'A' ? 'B' : 'A' })}>
                예시 {previewOption.label === 'A' ? 'B' : 'A'}도 보기 ↔
              </button>
            )}
            <button type="button" className="comparison-preview-select" disabled={connection === 'submitting'}
              onClick={() => { setPreviewOption(null); handleOptionSelect(previewOption.id); }}>
              이 예시 선택
            </button>
          </div>
        </div>, document.body,
      )}
    </section>
  );
}

export default ComparisonSection;

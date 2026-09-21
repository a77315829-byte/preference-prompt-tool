import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useMemo, useState } from 'react';
import { fetchAwsCostReport, startPreferenceSession, submitPreferenceChoice } from '../comparison/codingApi';

const FALLBACK_PAIRS = [
  {
    axis: 'detail_level',
    question: 'AWS 비용 결과를 어느 정도로 알려드릴까요?',
    options: [
      { id: 'a', value: 'summary', title: '핵심만 요약', description: '문제와 절약 금액을 빠르게 확인합니다.', code: '탄력적 IP 1개에서 월 ₩10,000이 낭비되고 있습니다.' },
      { id: 'b', value: 'detailed', title: '리소스와 해결 방법까지 자세히', description: '리소스 ID와 콘솔에서 할 일을 함께 확인합니다.', code: 'eipalloc-0a12bc34de56f7890\n→ EC2 > 탄력적 IP에서 릴리스하세요.' },
    ],
  },
  {
    axis: 'focus',
    question: '무엇을 먼저 볼까요?',
    options: [
      { id: 'a', value: 'cost', title: '낭비 비용 중심', description: '가장 큰 금액부터 보여드립니다.', code: '이번 달 예상 낭비 비용\n₩16,800' },
      { id: 'b', value: 'resource', title: '리소스 중심', description: '정리할 리소스와 상태를 먼저 보여드립니다.', code: '정리할 리소스 2개\n탄력적 IP · EBS 스냅샷' },
    ],
  },
];

const AXIS_COPY = {
  detail_level: {
    eyebrow: '상세도',
    question: 'AWS 비용 결과를 어느 정도로 알려드릴까요?',
    options: { summary: '핵심만 요약', detailed: '리소스와 해결 방법까지 자세히' },
  },
  focus: {
    eyebrow: '강조점',
    question: '무엇을 먼저 볼까요?',
    options: { cost: '낭비 비용 중심', resource: '리소스 중심' },
  },
};

function remotePairToQuestion(pair) {
  const axis = Object.keys(AXIS_COPY).find((name) => pair?.a?.combo?.[name] !== pair?.b?.combo?.[name]) || 'detail_level';
  const copy = AXIS_COPY[axis];
  return {
    id: `${pair.pair_id}-${axis}`,
    axis,
    eyebrow: copy.eyebrow,
    question: copy.question,
    options: [pair.a, pair.b].map((candidate, index) => ({
      id: index === 0 ? 'a' : 'b',
      value: candidate.combo?.[axis],
      title: copy.options[candidate.combo?.[axis]] || `예시 ${index === 0 ? 'A' : 'B'}`,
      description: axis === 'focus' ? '비용 점검 결과를 이 기준으로 정리합니다.' : '원하는 정보량에 맞춰 결과를 정리합니다.',
      code: candidate.text,
    })),
  };
}

function IdleTrackerSection({ onBack }) {
  const [report, setReport] = useState(null);
  const [reportState, setReportState] = useState('loading');
  const [phase, setPhase] = useState('report');
  const [session, setSession] = useState(null);
  const [answers, setAnswers] = useState({});
  const [connection, setConnection] = useState('connecting');
  const [copied, setCopied] = useState(false);

  const loadReport = (demoMode) => {
    setReportState('loading');
    fetchAwsCostReport({ demoMode })
      .then(({ report: nextReport }) => {
        setReport(nextReport);
        setReportState(nextReport.mode === 'aws' ? 'live' : 'demo');
      })
      .catch(() => {
        setReport({ mode: 'demo', totalCost: '₩16,800', findings: [] });
        setReportState('demo');
      });
  };

  useEffect(() => {
    let cancelled = false;
    fetchAwsCostReport({ demoMode: true })
      .then(({ report: nextReport }) => {
        if (!cancelled) {
          setReport(nextReport);
          setReportState(nextReport.mode === 'aws' ? 'live' : 'demo');
        }
      })
      .catch(() => {
        if (!cancelled) {
          setReport({ mode: 'demo', totalCost: '₩16,800', findings: [] });
          setReportState('demo');
        }
      });
    return () => { cancelled = true; };
  }, []);

  const startComparison = async () => {
    setPhase('compare');
    setConnection('connecting');
    try {
      const sourceText = report?.sourceText || 'AWS 비용 점검 결과에서 낭비되는 리소스와 해결 방법을 찾아주세요.';
      const { session: nextSession } = await startPreferenceSession('idle_tracker', sourceText, 2);
      setSession(nextSession);
      setConnection('connected');
    } catch {
      setConnection('offline');
    }
  };

  const question = session?.pair ? remotePairToQuestion(session.pair) : FALLBACK_PAIRS.find((pair) => !answers[pair.axis]);
  const isComplete = session ? session.done : Object.keys(answers).length === FALLBACK_PAIRS.length;
  const prompt = useMemo(() => {
    if (!isComplete) return '';
    if (session?.prompt) return session.prompt;
    const detail = answers.detail_level === 'detailed' ? '리소스 ID와 콘솔에서 실행할 해결 방법을 함께 제시' : '핵심 문제와 절약 금액을 먼저 요약';
    const focus = answers.focus === 'resource' ? '정리할 AWS 리소스를 중심으로 구성' : '낭비되는 비용을 금액 순서로 강조';
    return `AWS 비용 점검 결과를 ${detail}하고, ${focus}하여 한국어로 안내하세요.\n발견한 리소스마다 비용·원인·해결 방법을 포함하세요.`;
  }, [answers, isComplete, session]);

  const choose = async (option) => {
    setCopied(false);
    if (session?.pair) {
      setConnection('submitting');
      try {
        const { session: nextSession } = await submitPreferenceChoice(session.session_id, session.pair.pair_id, option.id);
        setSession(nextSession);
        setConnection('connected');
      } catch {
        setConnection('offline');
      }
      return;
    }
    setAnswers((current) => ({ ...current, [question.axis]: option.value }));
  };

  const copyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(prompt);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <section className="idle-tracker-section" id="idle-tracker-section">
      <div className="idle-tracker-inner">
        <button className="back-button" type="button" onClick={onBack}>← 카테고리 다시 선택</button>
        <div className="comparison-heading">
          <p className="eyebrow">AWS cost check</p>
          <h2>놓치고 있는 비용을 찾아볼까요?</h2>
          <p>연결된 리소스와 비용을 살펴보고, 내가 보고 싶은 방식의 점검 프롬프트를 만듭니다.</p>
        </div>

        {phase === 'report' && (
          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }}>
            <div className="aws-report-summary">
              <div><span>최근 30일 예상 낭비 비용</span><strong>{report?.totalCost || '불러오는 중…'}</strong></div>
              <div className="aws-report-summary-actions">
                <span className="aws-report-mode">{reportState === 'live' ? 'AWS Cost Explorer 연결됨' : 'API 없이 데모 중'}</span>
                <button className="aws-live-button" type="button" disabled={reportState === 'loading'} onClick={() => loadReport(false)}>
                  실제 AWS 연결 시도
                </button>
              </div>
            </div>
            <div className="aws-findings-grid">
              {(report?.findings || []).map((finding) => (
                <article className="aws-finding-card" key={finding.id}>
                  <div className="aws-finding-top"><span>{finding.service}</span><strong>{finding.cost}</strong></div>
                  <code>{finding.resourceId}</code>
                  <p>{finding.reason}</p>
                  <div className="aws-finding-action">{finding.resolution}</div>
                </article>
              ))}
            </div>
            <button className="task-start-button aws-start-button" type="button" disabled={reportState === 'loading'} onClick={startComparison}>
              이 결과로 맞춤 점검 방식 고르기 →
            </button>
          </motion.div>
        )}

        {phase === 'compare' && (
          <>
            <p className="connection-note" role="status">
              {connection === 'connected' && 'AWS 비용 점검 데모와 연결됨'}
              {connection === 'connecting' && '점검 예시를 준비하는 중…'}
              {connection === 'submitting' && '선택을 기록하는 중…'}
              {connection === 'offline' && '로컬 예시로 계속 진행합니다 (API 없이도 사용 가능)'}
            </p>
            <div className="comparison-progress"><span className="comparison-progress-bar"><span style={{ width: `${isComplete ? 100 : (session ? (session.answered / session.total_rounds) * 100 : (Object.keys(answers).length / FALLBACK_PAIRS.length) * 100)}%` }} /></span><span>{isComplete ? '선택 완료' : `${session ? session.answered : Object.keys(answers).length} / 2`}</span></div>
            <AnimatePresence mode="wait">
              {!isComplete && question && (
                <motion.div className="comparison-question" key={question.id || question.axis} initial={{ opacity: 0, x: 28 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -28 }}>
                  <p className="question-eyebrow">{question.eyebrow}</p>
                  <h3>{question.question}</h3>
                  <div className="comparison-options">{question.options.map((option) => (
                    <button className="comparison-option" type="button" key={option.id} disabled={connection === 'submitting'} onClick={() => choose(option)}>
                      <span className="option-copy"><strong>{option.title}</strong><span>{option.description}</span></span>
                      <pre><code>{option.code}</code></pre><span className="option-arrow" aria-hidden="true">→</span>
                    </button>
                  ))}</div>
                </motion.div>
              )}
              {isComplete && (
                <motion.div className="prompt-result" key="aws-prompt-result" initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}>
                  <p className="question-eyebrow">Your AWS prompt</p><h3>나만의 비용 점검 프롬프트가 완성됐어요.</h3>
                  <p>다음 비용 점검에 그대로 붙여 넣을 수 있습니다.</p><pre className="prompt-box"><code>{prompt}</code></pre>
                  <div className="prompt-actions"><button className="prompt-copy-button" type="button" onClick={copyPrompt}>{copied ? '복사했습니다 ✓' : '프롬프트 복사'}</button><button className="prompt-reset-button" type="button" onClick={onBack}>다시 선택하기</button></div>
                </motion.div>
              )}
            </AnimatePresence>
          </>
        )}
      </div>
    </section>
  );
}

export default IdleTrackerSection;

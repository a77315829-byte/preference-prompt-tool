import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useMemo, useState } from 'react';
import { fetchAwsCostReport, startPreferenceSession, submitPreferenceChoice } from '../comparison/codingApi';
import ExportPanel from '../../shared/components/ExportPanel';

const FALLBACK_PAIRS = [
  {
    axis: 'format',
    question: 'AWS 비용 내역을 어떤 형식으로 볼까요?',
    options: [
      {
        id: 'a',
        value: 'bullet_list',
        title: '개조식 요약 (불릿)',
        description: '항목별 금액과 비중을 불릿 리스트로 빠르게 확인합니다.',
        code: '- **Amazon EC2:** $25.00 (55.3%) — 주요 리전: ap-northeast-2\n- **Amazon RDS:** $15.00 (33.2%) — 주요 리전: ap-northeast-2\n- **기타 서비스 합계 (2건):** $5.20 (11.5%)',
      },
      {
        id: 'b',
        value: 'markdown_table',
        title: '마크다운 표 (테이블)',
        description: '서비스·리전·금액·비중을 표와 합계 행으로 정리합니다.',
        code: '| 서비스명 | 청구 금액 | 비중 |\n| :--- | :---: | :---: |\n| **Amazon EC2** | $25.00 | 55.3% |\n| **Amazon RDS** | $15.00 | 33.2% |\n| **합계** | **$45.20** | **100.0%** |',
      },
    ],
  },
  {
    axis: 'scope',
    question: '비용 데이터를 어디까지 자세히 볼까요?',
    options: [
      {
        id: 'a',
        value: 'summary_brief',
        title: '상위 핵심만 요약',
        description: '핵심 상위 2개 서비스만 보여주고 나머지는 기타 합계로 묶습니다.',
        code: '## 2. 핵심 과금 내역 (요약)\n- Amazon EC2: $25.00 (55.3%)\n- Amazon RDS: $15.00 (33.2%)\n- 기타 서비스 합계 (2건): $5.20 (11.5%)',
      },
      {
        id: 'b',
        value: 'deep_dive',
        title: '전체 서비스·Usage Type 상세',
        description: '소액 서비스와 세부 Usage Type 코드·리전까지 빠짐없이 나열합니다.',
        code: '## 2. 전체 과금 상세 내역 (Usage Type 기준)\n- Amazon EC2: $25.00\n  - [ap-northeast-2] APN2-BoxUsage:t2.micro: $20.00\n  - [ap-northeast-2] APN2-EBS:VolumeUsage.gp2: $5.00',
      },
    ],
  },
];

const AXIS_COPY = {
  format: {
    eyebrow: '출력 형식',
    question: 'AWS 비용 내역을 어떤 형식으로 볼까요?',
    options: { bullet_list: '개조식 요약 (불릿)', markdown_table: '마크다운 표 (테이블)' },
  },
  scope: {
    eyebrow: '보고 범위',
    question: '비용 데이터를 어디까지 자세히 볼까요?',
    options: { summary_brief: '상위 핵심만 요약', deep_dive: '전체 서비스·Usage Type 상세' },
  },
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
  const axis = Object.keys(AXIS_COPY).find((name) => pair?.a?.combo?.[name] !== pair?.b?.combo?.[name]) || 'format';
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
      description: axis === 'scope' ? '원하는 정보 밀도에 맞춰 비용 내역을 정리합니다.' : '원하는 시각적 형식으로 비용 내역을 정리합니다.',
      code: candidate.text,
    })),
  };
}

function IdleTrackerSection({ onBack, template = null }) {
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
        setReport({ mode: 'demo', totalCost: '$45.20', findings: [] });
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
          setReport({ mode: 'demo', totalCost: '$45.20', findings: [] });
          setReportState('demo');
        }
      });
    return () => { cancelled = true; };
  }, []);

  const startComparison = async () => {
    setPhase('compare');
    setConnection('connecting');
    try {
      const sourceText = report?.sourceText || '제공된 AWS 최신 가용 비용 데이터를 바탕으로 비용 분석 리포트를 한국어로 작성해 주세요.';
      const { session: nextSession } = await startPreferenceSession('idle_tracker', sourceText, 2, template?.id);
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
    const formatRule = answers.format === 'markdown_table'
      ? '과금 내역을 마크다운 표(|)와 합계 행으로 정리'
      : '과금 내역을 마크다운 불릿 리스트(- )로만 정리';
    const scopeRule = answers.scope === 'deep_dive'
      ? '소액 서비스와 리전·세부 Usage Type 코드까지 누락 없이 전부 표시'
      : '상위 2개 핵심 서비스만 개별 표시하고 나머지는 기타 서비스 합계로 통합';
    return `제공된 AWS 최신 가용 비용 데이터를 바탕으로 ${formatRule}하고, ${scopeRule}하여 4단 마크다운 리포트를 한국어로 작성하세요.\n데이터에 없는 유휴 상태나 금액은 절대 추측하지 마세요.`;
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
          <h2>이번 달 AWS 비용, 원하는 방식으로 확인하세요</h2>
          <p>조회된 비용과 리소스를 살펴보고, 내가 보고 싶은 방식의 점검 프롬프트를 만듭니다.</p>
        </div>

        {phase === 'report' && (
          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }}>
            <div className="aws-report-summary">
              <div><span>최근 30일 AWS 비용</span><strong>{report?.totalCost || '불러오는 중…'}</strong></div>
              <div className="aws-report-summary-actions">
                <span className="aws-report-mode">{reportState === 'live' ? 'AWS Cost Explorer 연결됨' : 'API 없이 데모 중'}</span>
                <button className="aws-live-button" type="button" disabled={reportState === 'loading'} onClick={() => loadReport(false)}>
                  실제 AWS 연결 시도
                </button>
              </div>
            </div>
            {report?.liveError && <p className="aws-live-error" role="status">{report.liveError}</p>}
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
              {connection === 'connected' && (session?.demo_mode === false ? 'AWS 비용 점검 AI 실시간 생성과 연결됨' : 'AWS 비용 점검 데모와 연결됨 (규칙 기반 예시)')}
              {connection === 'connecting' && '점검 예시를 준비하는 중…'}
              {connection === 'submitting' && '선택을 기록하는 중…'}
              {connection === 'offline' && '로컬 예시로 계속 진행합니다 (API 없이도 사용 가능)'}
            </p>
            <div className="comparison-progress"><span className="comparison-progress-bar"><span style={{ width: `${isComplete ? 100 : (session ? (session.answered / session.total_rounds) * 100 : (Object.keys(answers).length / FALLBACK_PAIRS.length) * 100)}%` }} /></span><span>{isComplete ? '선택 완료' : `${session ? session.answered : Object.keys(answers).length} / ${session ? session.total_rounds : FALLBACK_PAIRS.length}`}</span></div>
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
                  <ExportPanel exports={session?.exports} />
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
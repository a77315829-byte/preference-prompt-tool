import { useEffect, useRef, useState } from 'react';
import { CODING_CHOICES, codingOptimizationKind } from './codingOptions';
import './fastApiOptimization.css';

export const REVIEW_LABELS = { match: '잘 맞아요', needs_work: '보완이 필요해요', unsure: '판단 보류' };
const QUESTIONS = {
  explanation: '설명의 길이와 순서, 선택 이유가 내게 이해하기 편한가요?',
  comments: '의도와 주의점을 설명하나요? 코드를 그대로 반복하는 주석은 아닌가요?',
  structure: '역할이 적절히 나뉘고 실제로 연결되나요? 작업 규모에 비해 복잡하지 않나요?',
  output: '필요한 코드와 수정 위치가 충분해서 내 작업에 적용할 수 있나요?',
};

export function HumanAnswerReview({ profile, value = {}, onChange, disabled, prefix, observation = {}, guidance = {} }) {
  return <div className="coding-human-review" aria-label={`${prefix} 직접 확인`}>
    {Object.entries(CODING_CHOICES).map(([key, field]) => <div className="coding-human-axis" key={key}>
      <h5>{field.label}<small>{field.options[profile.preferences[key]]}</small></h5>
      <p>{guidance[key] || QUESTIONS[key]}</p>
      {observation[key] && <details><summary>답변에서 찾은 단서</summary><p>{observation[key]}</p></details>}
      <div className="coding-review-choices" role="group" aria-label={`${prefix} ${field.label} 확인`}>
        {Object.entries(REVIEW_LABELS).map(([mark, label]) => <button key={mark} className="coding-secondary-button" type="button" disabled={disabled} aria-pressed={value[key] === mark} onClick={() => onChange({ ...value, [key]: mark })}>{label}</button>)}
      </div>
    </div>)}
  </div>;
}

export default function CodingAnswerReview({ draft, disabled }) {
  const [answer, setAnswer] = useState('');
  const [inspection, setInspection] = useState(null);
  const [review, setReview] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const inspect = async () => {
    setBusy(true); setError('');
    try {
      const response = await fetch('/api/coding-instructions/review', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ profile: draft.profile, answer }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '답변 단서를 확인하지 못했어요.');
      if (active.current) { setInspection(data.inspection); setReview({}); }
    } catch (e) { if (active.current) setError(e.message); }
    finally { if (active.current) setBusy(false); }
  };
  const gepaSupported = Boolean(codingOptimizationKind(draft.profile));
  return <details className="coding-answer-review"><summary>받은 AI 답변 직접 확인 · 모든 언어</summary>
    <p className="ws-help">{draft.profile.language} · {draft.profile.framework || '프레임워크 없음'}의 실제 답변을 붙여 넣어 내 선호와 맞는지 확인하세요. 이 기능은 모델을 호출하거나 코드를 실행하지 않습니다. 붙인 답변은 현재 서비스 서버에서 단서를 찾고 보관함에 저장하거나 외부 AI에 보내지 않습니다.</p>
    {!gepaSupported && <p className="coding-review-support">이 환경은 공통 답변 확인을 지원합니다. 환경별 기능 검사와 GEPA 자동 개선은 아직 지원하지 않습니다.</p>}
    <label htmlFor="coding-received-answer" className="task-input-label">AI에서 받은 실제 답변</label>
    <textarea id="coding-received-answer" className="task-input" rows={8} maxLength={24000} value={answer} disabled={busy || disabled} onChange={event => { setAnswer(event.target.value); setInspection(null); setReview({}); setError(''); }} placeholder="평소 쓰는 AI에서 받은 설명과 코드 전체를 붙여 넣어 주세요." />
    <button className="coding-secondary-button" type="button" disabled={busy || disabled || !answer.trim()} onClick={inspect}>{busy ? '답변 단서를 확인하는 중…' : '답변 단서 확인하기'}</button>
    {error && <p className="ws-error" role="alert">{error}</p>}
    {inspection && <><p className="ws-help" role="status">설명 형식: {inspection.preferences.explanation ? '선택한 길이·단계 표시 기준 확인' : '형식 기준 미확인'}. 실제로 이해하기 편한지와 주석·역할 구성·출력 범위는 아래에서 직접 확인하세요. 정답이나 코드 품질 판정이 아닙니다.</p>
      <HumanAnswerReview profile={draft.profile} value={review} onChange={setReview} disabled={disabled} prefix="붙여 넣은 답변" observation={inspection.observations} guidance={inspection.guidance} />
      <p className="ws-help">직접 고른 확인 {Object.keys(review).length}/4항목 · 이 확인은 현재 화면에서만 유지하며 자동 평가 점수·원본 지침에 반영하지 않습니다.</p></>}
  </details>;
}

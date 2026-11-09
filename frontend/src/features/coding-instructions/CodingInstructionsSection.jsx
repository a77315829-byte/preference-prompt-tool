import { useEffect, useRef, useState } from 'react';
import SavePreferencePanel from '../preferences/SavePreferencePanel';
import { CODING_CHOICES, DEFAULT_CODING_PROFILE, LANGUAGES, loadCodingExamples, previewCodingInstructions } from './codingOptions';
import CodingEnvironmentPicker from './CodingEnvironmentPicker';
import CodingPreferenceChoices from './CodingPreferenceChoices';
import CodingExampleComparison from './CodingExampleComparison';
import CodingOptimizationPanel from './CodingOptimizationPanel';
import CodingAnswerReview from './CodingAnswerReview';
import CodingSignalSummary from './CodingSignalSummary';
import CodingWorkflowPanel from './CodingWorkflowPanel';
import { readDraft, useDraftCache } from '../../shared/draftCache';
import './codingFlow.css';

const emptyPreferences = () => Object.fromEntries(Object.keys(CODING_CHOICES).map(key => [key, null]));

export default function CodingInstructionsSection({ user, signupOpen, onLogin, onOpenLibrary, onBack, onReactComparison, initialProfile, onConsumeInitial, initialTeamCode = '' }) {
  const [restored] = useState(() => initialProfile ? null : readDraft('coding', user));
  const [profile, setProfile] = useState(() => structuredClone(initialProfile || restored?.profile || { ...DEFAULT_CODING_PROFILE, language: '', preferences: emptyPreferences() }));
  const [frameworkChosen, setFrameworkChosen] = useState(Boolean(initialProfile || restored?.frameworkChosen));
  const [stage, setStage] = useState(restored?.stage || 'environment');
  const [mode, setMode] = useState(restored?.mode || 'direct');
  const [examples, setExamples] = useState(restored?.examples || null);
  const [draft, setDraft] = useState(restored?.draft || null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [taskRequest, setTaskRequest] = useState(restored?.taskRequest || '');
  const [comparisonProgress, setComparisonProgress] = useState(restored?.comparisonProgress || null);
  const [copiedWithTask, setCopiedWithTask] = useState(false);
  const request = useRef(0);
  const screenRef = useRef(null);
  const previousStage = useRef(stage);
  const comparisonReturn = useRef(restored?.comparisonReturn || { stage: 'environment', mode: 'direct' });
  useDraftCache('coding', user, { profile, frameworkChosen, stage, mode, examples, draft, taskRequest,
    comparisonProgress, comparisonReturn: comparisonReturn.current });
  useEffect(() => { if (initialProfile) onConsumeInitial?.(); }, [initialProfile, onConsumeInitial]);
  useEffect(() => () => { request.current += 1; }, []);
  useEffect(() => { setCopiedWithTask(false); }, [draft]);
  useEffect(() => {
    screenRef.current?.focus({ preventScroll: true });
    if (previousStage.current !== stage) screenRef.current?.scrollIntoView({ block: 'start',
      behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ? 'auto' : 'smooth' });
    previousStage.current = stage;
  }, [stage]);
  const selectedCount = Object.keys(CODING_CHOICES).filter(key => Object.hasOwn(CODING_CHOICES[key].options, profile.preferences[key])).length;
  const allChosen = selectedCount === Object.keys(CODING_CHOICES).length;
  const canReview = allChosen || Boolean(profile.comparison);
  const step = stage === 'environment' ? 0 : stage === 'choose' ? 1 : 2;

  const changeEnvironment = (changes, confirmed) => {
    if (frameworkChosen === confirmed && Object.entries(changes).every(([key, value]) => profile[key] === value)) return;
    request.current += 1;
    setProfile(current => {
      const next = { ...current, ...changes, preferences: emptyPreferences() };
      delete next.comparison;
      return next;
    });
    setFrameworkChosen(confirmed); setExamples(null); setComparisonProgress(null); setDraft(null); setError(''); setCopied(false);
  };
  const choosePreference = (key, value) => {
    request.current += 1;
    setProfile(current => ({ ...current, preferences: { ...current.preferences, [key]: value },
      ...(current.comparison ? { comparison: { ...current.comparison, choices: { ...current.comparison.choices, [key]: null } } } : {}) }));
    setDraft(null); setError(''); setCopied(false);
  };
  const compare = async () => {
    if (busy || !LANGUAGES.includes(profile.language)) return;
    comparisonReturn.current = { stage, mode };
    const token = ++request.current;
    setBusy(true); setError('');
    // 조회 API의 검증용 값이며 화면의 미선택 항목이나 최종 프롬프트에는 반영하지 않는다.
    const lookup = { ...profile, preferences: Object.fromEntries(Object.keys(CODING_CHOICES).map(key => [key, profile.preferences[key] || DEFAULT_CODING_PROFILE.preferences[key]])) };
    delete lookup.comparison;
    try {
      const next = await loadCodingExamples(lookup);
      if (token === request.current) { setExamples(next); setComparisonProgress(null); setMode('comparison'); setStage('choose'); }
    } catch (e) { if (token === request.current) setError(e.message); }
    finally { if (token === request.current) setBusy(false); }
  };
  const cancelComparison = () => {
    setMode(comparisonReturn.current.mode); setStage(comparisonReturn.current.stage); setError('');
  };
  const finishComparison = (choices, version, source, rounds, summary) => {
    const preferences = { ...profile.preferences };
    for (const [key, value] of Object.entries(choices)) if (value !== null || version >= 3) preferences[key] = value;
    request.current += 1;
    setProfile({ ...profile, preferences, comparison: { version, choices, ...(version >= 2 ? { example: source } : {}),
      ...(version >= 3 ? { rounds, summary } : {}) } });
    setStage('review'); setDraft(null); setCopied(false); setError('');
  };
  const generate = async () => {
    if (!allChosen || !profile.language.trim() || !frameworkChosen || busy) return;
    const token = ++request.current;
    setBusy(true); setError(''); setCopied(false);
    try {
      const next = await previewCodingInstructions(profile);
      if (token === request.current) { setDraft(next); setStage('result'); }
    } catch (e) { if (token === request.current) setError(e.message); }
    finally { if (token === request.current) setBusy(false); }
  };
  const copy = async (includeTask = false) => {
    if (includeTask && !taskRequest.trim()) return;
    const text = includeTask ? `${draft.prompt}\n\n## 이번 작업 요청\n${taskRequest.trim()}` : draft.prompt;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(!includeTask); setCopiedWithTask(includeTask); setError('');
    }
    catch { setError('복사하지 못했어요. 화면에 보이는 프롬프트를 직접 선택해 복사해 주세요.'); }
  };
  const direct = () => { setMode('direct'); setStage('choose'); setError(''); };

  return <section className="comparison-section coding-instructions-section coding-flow">
    <div className="comparison-inner">
      <p className="ws-help">선택과 작성 내용은 이 탭에 임시 보관돼요. 메뉴를 옮겼다가 돌아와도 이어서 진행할 수 있어요. 로그아웃하면 지워집니다.</p>
      <button className="back-button" type="button" disabled={busy} onClick={onBack}>← 시작 화면으로</button>
      <header className="coding-flow-header"><div><span className="coding-flow-tag">MY CODING PREFERENCE</span>
        <h2>내가 고르는, 내 코딩 방식.</h2><p>원하는 답변 방식을 직접 고르거나, 코드 예시로 확인해요.<br />비교 횟수를 채울 필요 없이 내 선택을 확인하고 지침을 만들어요.</p></div>
        <div className="coding-flow-note">내 선택 → 내 프롬프트 → 다음 작업</div>
      </header>
      <ol className="coding-stepper" aria-label="코딩 프롬프트 만들기 단계">
        {['개발 환경', '선호 선택', '내 프롬프트'].map((label, index) => <li key={label}><button type="button" aria-current={step === index ? 'step' : undefined}
          disabled={busy || (index === 1 && stage === 'environment' && !examples && !allChosen) || (index === 2 && !canReview)}
          onClick={() => { if (index === 0) setStage('environment'); else if (index === 1) setStage('choose'); else setStage(draft ? 'result' : 'review'); }}>
          <span aria-hidden="true">{step > index ? '✓' : `0${index + 1}`}</span>{label}</button></li>)}
      </ol>
      <div className="coding-active-screen" ref={screenRef} tabIndex={-1}>
        {stage === 'environment' && <CodingEnvironmentPicker profile={profile} frameworkChosen={frameworkChosen} busy={busy} onChange={changeEnvironment}
          onCompare={compare} onDirect={direct} onReuse={allChosen ? () => setStage('review') : null} />}
        {stage === 'choose' && <div className="coding-selection-method">
          <div><span className="coding-kicker">선호를 고르는 방법</span><p>원하는 방식을 알고 있다면 직접 고르고, 이름만으로 판단하기 어렵다면 예시를 확인해 보세요.</p></div>
          <div role="group" aria-label="선호 선택 방법" className="coding-selection-method-buttons">
            <button type="button" aria-label="코드 예시로 고르기" disabled={busy || !LANGUAGES.includes(profile.language)} aria-pressed={mode === 'comparison'}
              onClick={() => { if (mode !== 'comparison') compare(); }}><strong>{busy ? '코드 예시를 불러오는 중…' : '코드 예시로 고르기'}</strong><span>A/B 코드를 보고 선택</span></button>
            <button type="button" aria-label="설정만 빠르게 고르기" disabled={busy} aria-pressed={mode === 'direct'} onClick={direct}><strong>설정만 빠르게 고르기</strong><span>원하는 답변 방식을 이미 알고 있어요</span></button>
          </div>
          <p className="coding-selection-method-hint">{!LANGUAGES.includes(profile.language) ? '직접 입력한 언어의 코드 예시는 아직 준비되지 않았어요. 아래 설정에서 내 방식을 골라 주세요.' : '새 비교는 최대 8회이며 원할 때 마칠 수 있어요. 한 번 고른 항목과 반복 일치한 항목을 구분하고, 미확정 항목은 직접 확인합니다. 비교를 취소하면 기존 선택을 유지합니다.'}</p>
        </div>}
        {stage === 'choose' && mode === 'comparison' && examples && <CodingExampleComparison examples={examples} initialChoices={profile.comparison?.choices}
          initialProgress={comparisonProgress} onProgress={setComparisonProgress}
          onFinish={finishComparison} onCancel={cancelComparison} />}
        {stage === 'choose' && mode === 'direct' && <>
          <div className="coding-screen-heading"><span className="coding-kicker">02 · 선호 선택</span><h3>어떤 답변이 더 편한가요?</h3><p>정답은 없어요. 네 가지 항목에서 내가 받고 싶은 방식을 하나씩 눌러 주세요.</p></div>
          <CodingPreferenceChoices profile={profile} onSelect={choosePreference} busy={busy} />
          <div className="coding-next-bar"><div><small>설명·주석·코드 구성·출력 방식</small><strong>{allChosen ? '답변 방식 4가지 선택 완료' : `답변 방식 ${selectedCount}가지 선택 · ${4 - selectedCount}가지 남음`}</strong></div>
            <button type="button" className="coding-primary-button" disabled={!allChosen || busy} onClick={() => setStage('review')}>내 선택 확인하기 →</button></div>
        </>}
        {stage === 'review' && <>
          <div className="coding-screen-heading"><span className="coding-kicker">03 · 내 선택 확인</span><h3>이 선택으로 프롬프트를 만들까요?</h3>
            <p>{profile.comparison?.example?.label || `${profile.language} · ${profile.framework || '프레임워크 없이'} · ${profile.comparison ? '기본 문법 예시에서 선택' : '카드에서 직접 선택'}`}</p>
            <p>아래 카드는 내가 고른 답변 방식이에요. 이 선택을 AI에게 전달할 지시문으로 정리해 드릴게요.</p></div>
          <CodingSignalSummary comparison={profile.comparison} resolved={allChosen} />
          {LANGUAGES.includes(profile.language) && <div className="coding-review-examples"><div><strong>설정 이름만으로 고르기 어려웠나요?</strong><p>코드 A/B를 보며 다시 고를 수 있어요. 비교를 취소하면 지금 선택을 유지해요.</p></div>
            <button type="button" className="coding-secondary-button" disabled={busy} onClick={compare}>{busy ? '코드 예시를 불러오는 중…' : '코드 예시를 보며 다시 고르기'}</button></div>}
          {!allChosen && <p className="coding-selection-status" role="status">아직 확정하지 않은 항목이 있어요. 아래 카드에서 남은 {4 - selectedCount}개를 직접 골라야 프롬프트를 만들 수 있어요.</p>}
          <CodingPreferenceChoices profile={profile} onSelect={choosePreference} busy={busy} />
          <label className="coding-custom-field" htmlFor="coding-extra">함께 전할 추가 선호 <span>(선택)</span></label>
          <textarea id="coding-extra" className="task-input" rows={2} maxLength={1000} value={profile.extra} disabled={busy}
            onChange={event => { request.current += 1; setProfile(current => ({ ...current, extra: event.target.value })); setDraft(null); setCopied(false); setError(''); }} placeholder="예: 설명은 한국어로, 기존 함수 이름은 그대로." />
          <div className="coding-next-bar"><div><small>프롬프트를 만들 준비</small><strong>{allChosen ? '답변 방식 4가지 선택 완료' : `답변 방식 ${selectedCount}가지 선택 · ${4 - selectedCount}가지 남음`}</strong></div>
            <button type="button" className="coding-primary-button" disabled={!allChosen || busy} onClick={generate}>{busy ? '프롬프트를 만드는 중…' : '내 선택으로 프롬프트 만들기'}</button></div>
          <button className="coding-text-button" type="button" disabled={busy} onClick={() => setStage('environment')}>개발 환경 다시 고르기</button>
        </>}
        {stage === 'result' && draft && <div className="coding-instructions-result">
          <div className="coding-result-banner"><h3>답변 방식 4가지 선택 완료</h3><p>{draft.profile.language} · {draft.profile.framework || '프레임워크 없이'} · 고른 방식을 AI에게 전달할 프롬프트로 정리했어요.</p></div>
          <CodingSignalSummary comparison={draft.profile.comparison} resolved />
          <div className="coding-result-layout">
            <section className="coding-summary-panel" aria-labelledby="coding-summary-title">
              <span className="coding-kicker">내 선택 요약</span><h3 id="coding-summary-title">내가 고른 답변 방식</h3>
              <p>아래 카드는 선택한 설정을 보여줘요.</p>
              <CodingPreferenceChoices profile={draft.profile} readOnly />
              <button className="coding-secondary-button" type="button" disabled={busy} onClick={() => setStage('review')}>선택 다시 바꾸기</button>
            </section>
            <section className="coding-actual-prompt-panel" aria-labelledby="coding-actual-prompt-title">
              <span className="coding-kicker">복사해서 사용할 지시문</span><h3 id="coding-actual-prompt-title">AI에 붙여넣을 프롬프트</h3>
              <p>아래 문장 전체가 실제 프롬프트예요. 복사해서 평소 사용하는 AI 대화창에 붙여넣으세요.</p>
              <label className="task-input-label" htmlFor="coding-instructions-prompt">내 선택이 반영된 프롬프트 전문</label>
              <textarea id="coding-instructions-prompt" className="task-input coding-visible-prompt" readOnly rows={16} value={draft.prompt} onFocus={event => event.target.select()} />
              <button className="coding-primary-button" type="button" disabled={busy} onClick={() => copy()}>{copied ? '프롬프트를 복사했어요' : '프롬프트 복사'}</button>
            </section>
          </div>
          <section className="coding-how-to-use" aria-labelledby="coding-usage-title">
            <h3 id="coding-usage-title">이 프롬프트로 작업 요청하기</h3>
            <p>위에서 만든 <strong>내 답변 방식</strong>에 아래에 적는 <strong>이번 작업</strong>을 합쳐서 한 번에 복사하는 곳이에요.</p>
            <ol><li><strong>1. 이번 작업 적기</strong><span>답변 방식은 이미 준비됐어요. 아래에는 AI에게 시킬 일만 적어 주세요.</span></li>
              <li><strong>2. 답변 방식과 함께 복사</strong><span>아래 복사 버튼을 누르면 내 답변 방식과 이번 작업이 함께 복사돼요.</span></li>
              <li><strong>3. AI 대화창에 붙여넣기</strong><span>평소 쓰는 AI에서 새 대화를 열고, 복사한 내용을 붙여넣어 보내세요.</span></li></ol>
            <label className="coding-custom-field" htmlFor="coding-new-task">이번에 AI에게 부탁할 일</label>
            <p id="coding-new-task-hint">무엇을 만들거나 고칠지 적어 주세요. 설명·주석 같은 답변 방식은 다시 적지 않아도 돼요.</p>
            <textarea id="coding-new-task" className="task-input" rows={3} maxLength={10000} value={taskRequest} disabled={busy}
              aria-describedby="coding-new-task-hint coding-task-copy-note"
              onChange={event => { setTaskRequest(event.target.value); setCopiedWithTask(false); }}
              placeholder="예: 회원가입 API를 만들어줘. 이메일 중복 검사와 비밀번호 검증을 포함해줘." />
            <div className="coding-result-actions"><button type="button" className="coding-primary-button" disabled={busy || !taskRequest.trim()} onClick={() => copy(true)}>{copiedWithTask ? '답변 방식과 이번 작업을 함께 복사했어요' : '내 답변 방식 + 이번 작업 복사'}</button></div>
            <p id="coding-task-copy-note">이번 작업을 적으면 함께 복사할 수 있어요. 답변 방식만 쓰려면 위의 ‘프롬프트 복사’를 눌러 주세요. AI는 붙여넣은 대화창에서 실행되며, 이번 작업 내용은 보관함에 저장되지 않아요.</p>
          </section>
          <CodingWorkflowPanel key={`workflow-${JSON.stringify([draft.profile, draft.prompt, user?.id])}`} draft={draft}
            user={user} signupOpen={signupOpen} onLogin={onLogin} onOpenLibrary={onOpenLibrary} initialTeamCode={initialTeamCode} task={taskRequest} />
          <CodingAnswerReview key={JSON.stringify([draft.profile, draft.prompt])} draft={draft} disabled={busy} />
          <CodingOptimizationPanel key={JSON.stringify([draft.profile, draft.prompt, user?.id])} draft={draft} user={user} signupOpen={signupOpen}
            onLogin={onLogin} onOpenLibrary={onOpenLibrary} onBusy={setBusy} disabled={busy} />
          <SavePreferencePanel domainKey="coding" prompt={draft.prompt} codingProfile={draft.profile} disabled={busy}
            initialTitle={`${draft.profile.language}${draft.profile.framework ? ` · ${draft.profile.framework}` : ''} 내 작성 방식`.slice(0, 100)}
            user={user} signupOpen={signupOpen} onLogin={onLogin} onOpenLibrary={onOpenLibrary} onBusy={setBusy} />
        </div>}
      </div>
      {error && <p className="ws-error" role="alert">{error}</p>}
      <aside className="coding-legacy-entry"><h3>팀과 React 코드 기준을 맞추고 싶나요?</h3>
        <p>새 지침의 설명·주석·구성·출력은 결과 화면에서 팀 기준과 연결할 수 있어요. 아래 기존 React 비교는 화면 구성·스타일·타입을 비교하는 별도 기록입니다.</p>
        <button type="button" className="coding-secondary-button" disabled={busy} onClick={onReactComparison}>React 예시 비교로 취향 찾기</button>
      </aside>
    </div>
  </section>;
}

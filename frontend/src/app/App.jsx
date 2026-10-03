import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useState } from 'react';
import ComparisonSection from '../features/comparison/ComparisonSection';
import IdleTrackerSection from '../features/idle-tracker/IdleTrackerSection';
import ScrollStory from '../features/landing/ScrollStory';
import PromptPolishSection from '../features/polish/PromptPolishSection';
import PromptWorkspaceSection from '../features/prompt-workspace/PromptWorkspaceSection';
import TemplateLibrarySection from '../features/templates/TemplateLibrarySection';
import AccountSection from '../shared/auth/AccountSection';
import AuthSection from '../shared/auth/AuthSection';
import { fetchMe, logout } from '../shared/auth/authApi';
import './App.css';
import '../features/landing/landing.css';

function App() {
  const [selectedCategory, setSelectedCategory] = useState('summary');
  const [activeFlow, setActiveFlow] = useState('category');
  // 템플릿 라이브러리에서 "내 방식으로 바꾸기"로 들어왔을 때의 템플릿.
  const [template, setTemplate] = useState(null);
  // 로그인 상태. undefined = 아직 모름, null = 로그인 안 함. 세션은 HttpOnly 쿠키라
  // 화면은 서버에 물어서만 안다.
  const [user, setUser] = useState(undefined);
  const [signupOpen, setSignupOpen] = useState(true);
  // 로그인 화면으로 오기 전 흐름. 로그인이 끝나면 거기로 돌아간다.
  const [returnFlow, setReturnFlow] = useState('category');
  const [authReason, setAuthReason] = useState('');

  useEffect(() => {
    fetchMe()
      .then((data) => { setUser(data.user); setSignupOpen(data.signupOpen !== false); })
      .catch(() => setUser(null));
  }, []);

  // 작업 공간에서 로그인을 누르면 화면을 옮기지 않고 그 안에 로그인 칸을 연다 -
  // 옮기면 작성 중인 프로젝트가 사라진다. 값이 바뀔 때마다 한 번 연다.
  const [workspaceLoginRequest, setWorkspaceLoginRequest] = useState(0);

  const requestLogin = (reason = '') => {
    if (activeFlow === 'workspace') {
      setWorkspaceLoginRequest((n) => n + 1);
      return;
    }
    setReturnFlow(activeFlow === 'login' ? 'category' : activeFlow);
    setAuthReason(reason);
    setActiveFlow('login');
  };

  const handleLogout = async () => {
    try { await logout(); } catch { /* 이미 끊긴 세션이어도 화면은 로그아웃 상태로 */ }
    setUser(null);
  };

  const requestScene = (scene) => {
    if (activeFlow !== 'category') {
      setActiveFlow('category');
      window.setTimeout(() => {
        window.dispatchEvent(new CustomEvent('narrative:scene', { detail: scene }));
      }, 30);
      return;
    }
    window.dispatchEvent(new CustomEvent('narrative:scene', { detail: scene }));
  };

  const handleCategoryContinue = () => {
    if (selectedCategory === 'coding') setActiveFlow('coding');
    else if (selectedCategory === 'idleTracker') setActiveFlow('idleTracker');
    else if (selectedCategory === 'review') setActiveFlow('review');
    else if (selectedCategory === 'email') setActiveFlow('email');
    else if (selectedCategory === 'summaryKo') setActiveFlow('summarization_ko');
    else if (selectedCategory === 'summaryHybrid') setActiveFlow('summarization_hybrid');
    else if (selectedCategory === 'macsumEval') setActiveFlow('macsum_eval_agent');
    else setActiveFlow('summarization');
  };

  const handleComparisonBack = () => {
    setTemplate(null);
    setActiveFlow('category');
  };

  // 템플릿의 도메인 이름이 곧 비교 화면의 흐름 이름이다 (AWS 만 화면 이름이 다르다).
  const handlePersonalizeTemplate = (picked) => {
    setTemplate(picked);
    setActiveFlow(picked.domain === 'idle_tracker' ? 'idleTracker' : picked.domain);
  };

  return (
    <main className={`site-shell ${activeFlow !== 'category' ? 'is-flow-open' : ''}`}>
      <nav className="site-nav" aria-label="주요 메뉴">
        <button className="brand-mark" type="button" onClick={() => requestScene(0)}>
          Preference Prompt<span aria-hidden="true">·</span>
        </button>

        <div className="nav-links" aria-label="페이지 이동">
          <button type="button" onClick={() => requestScene(1)}>사용 방법</button>
          <button type="button" onClick={() => requestScene(0)}>시작하기</button>
          <button type="button" onClick={() => { setTemplate(null); setActiveFlow('templates'); }}>템플릿</button>
          <button type="button" onClick={() => setActiveFlow('polish')}>프롬프트 다듬기</button>
          <button type="button" onClick={() => setActiveFlow('workspace')}>서비스용 프롬프트</button>
        </div>

        {user ? (
          <span className="nav-user">
            <button type="button" className="nav-account" title="내 계정" onClick={() => {
              setReturnFlow(activeFlow === 'account' ? 'category' : activeFlow);
              setActiveFlow('account');
            }}>{user.username}</button>
            <button type="button" onClick={handleLogout}>로그아웃</button>
          </span>
        ) : user === null && (
          <button className="nav-login" type="button" onClick={() => requestLogin()}>로그인</button>
        )}
        <button className="nav-button" type="button" onClick={() => requestScene(0)}>
          바로 시작
        </button>
      </nav>

      <AnimatePresence mode="wait" initial={false}>
        {activeFlow === 'category' && (
          <motion.div
            className="flow-view"
            key="category"
            initial={{ opacity: 0, scale: 1.02 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.985 }}
            transition={{ duration: 0.38, ease: [0.22, 1, 0.36, 1] }}
          >
            <ScrollStory
              selectedCategory={selectedCategory}
              onSelectCategory={setSelectedCategory}
              onContinue={handleCategoryContinue}
            />
          </motion.div>
        )}

        {['coding', 'review', 'email', 'summarization', 'summarization_ko', 'summarization_hybrid', 'macsum_eval_agent'].includes(activeFlow) && (
          <motion.div
            className="flow-view"
            key={activeFlow}
            initial={{ opacity: 0, y: 34, scale: 0.99 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -24, scale: 0.99 }}
            transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
          >
            <ComparisonSection onBack={handleComparisonBack} domainKey={activeFlow} onSwitchDomain={setActiveFlow} template={template} />
          </motion.div>
        )}

        {activeFlow === 'templates' && (
          <motion.div className="flow-view" key="templates" initial={{ opacity: 0, y: 34, scale: 0.99 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -24, scale: 0.99 }} transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}>
            <TemplateLibrarySection onBack={handleComparisonBack} onPersonalize={handlePersonalizeTemplate} />
          </motion.div>
        )}

        {activeFlow === 'polish' && (
          <motion.div className="flow-view" key="polish" initial={{ opacity: 0, y: 34, scale: 0.99 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -24, scale: 0.99 }} transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}>
            <PromptPolishSection onBack={handleComparisonBack} />
          </motion.div>
        )}

        {activeFlow === 'account' && user && (
          <motion.div className="flow-view" key="account" initial={{ opacity: 0, y: 34, scale: 0.99 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -24, scale: 0.99 }} transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}>
            <AccountSection user={user} onBack={() => setActiveFlow(returnFlow)}
              onDeleted={() => { setUser(null); setActiveFlow('category'); }} />
          </motion.div>
        )}

        {activeFlow === 'login' && (
          <motion.div className="flow-view" key="login" initial={{ opacity: 0, y: 34, scale: 0.99 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -24, scale: 0.99 }} transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}>
            <AuthSection signupOpen={signupOpen} reason={authReason}
              onBack={() => setActiveFlow(returnFlow)}
              onDone={(nextUser) => { setUser(nextUser); setActiveFlow(returnFlow); }} />
          </motion.div>
        )}

        {activeFlow === 'workspace' && (
          <motion.div className="flow-view" key="workspace" initial={{ opacity: 0, y: 34, scale: 0.99 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -24, scale: 0.99 }} transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}>
            <PromptWorkspaceSection onBack={handleComparisonBack} user={user} signupOpen={signupOpen}
              onLogin={setUser} loginRequest={workspaceLoginRequest} />
          </motion.div>
        )}

        {activeFlow === 'idleTracker' && (
          <motion.div className="flow-view" key="idleTracker" initial={{ opacity: 0, y: 34, scale: 0.99 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -24, scale: 0.99 }} transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}>
            <IdleTrackerSection onBack={handleComparisonBack} template={template} />
          </motion.div>
        )}

        {activeFlow === 'summary' && (
          <motion.div
            className="flow-view"
            key="summary"
            initial={{ opacity: 0, y: 34, scale: 0.99 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -24, scale: 0.99 }}
            transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
          >
            <section className="summary-notice" id="summary-notice" aria-labelledby="summary-notice-title">
              <div className="summary-notice-inner">
                <p className="section-kicker">DOCUMENT SUMMARY</p>
                <h2 id="summary-notice-title">문서 요약 기능도 준비되어 있습니다.</h2>
                <p>
                  기존 문서 요약 엔진과 Streamlit 화면은 그대로 보존되어 있습니다. React UI에서도
                  영어·한국어 문서 원문을 넣고 요약 결과를 비교해 원하는 길이와 표현 방식을 고를 수 있습니다.
                </p>
                <button className="prompt-reset-button" type="button" onClick={() => setActiveFlow('category')}>
                  카테고리로 돌아가기
                </button>
              </div>
            </section>
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}

export default App;

import { AnimatePresence, motion } from 'motion/react';
import { useState } from 'react';
import ComparisonSection from '../features/comparison/ComparisonSection';
import IdleTrackerSection from '../features/idle-tracker/IdleTrackerSection';
import ScrollStory from '../features/landing/ScrollStory';
import './App.css';
import '../features/landing/landing.css';

function App() {
  const [selectedCategory, setSelectedCategory] = useState('summary');
  const [activeFlow, setActiveFlow] = useState('category');

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
    setActiveFlow('category');
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
        </div>

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
            <ComparisonSection onBack={handleComparisonBack} domainKey={activeFlow} />
          </motion.div>
        )}

        {activeFlow === 'idleTracker' && (
          <motion.div className="flow-view" key="idleTracker" initial={{ opacity: 0, y: 34, scale: 0.99 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -24, scale: 0.99 }} transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}>
            <IdleTrackerSection onBack={handleComparisonBack} />
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

import { AnimatePresence, motion } from 'motion/react';
import { useEffect, useRef, useState } from 'react';
import CategoryDeck from './CategoryDeck';

const scenes = [
  {
    number: '01',
    kicker: 'CHOOSE',
    title: '좋아하는 결과를 고르면',
    description: '문서 요약, 코딩, AWS 비용 점검처럼 지금 필요한 카테고리를 선택합니다.',
    visual: 'category',
  },
  {
    number: '02',
    kicker: 'COMPARE',
    title: '더 마음에 드는 쪽을 고르고',
    description: '간결한 코드와 역할을 나눈 코드처럼, 눈앞의 예시를 비교합니다.',
    visual: 'compare',
  },
  {
    number: '03',
    kicker: 'REUSE',
    title: '나만의 프롬프트를 다시 씁니다',
    description: '선택 기록이 하나의 코딩 기준이 되어 다음 작업에도 이어집니다.',
    visual: 'result',
  },
];

// 앞에 보이는 핵심 카테고리. 타깃("AI 를 매일 쓰는 작은 개발팀")이 반복하는 일에
// 맞춘 세 가지다. 요약은 영어·한국어를 한 카드로 두고 비교 화면에서 언어를 고른다.
const coreCategories = [
  {
    id: 'summary',
    number: '01',
    label: 'DOCUMENT',
    title: '문서 요약',
    description: '회의록·기술 문서·기사를 내가 좋아하는 길이와 표현으로 요약합니다. 영어·한국어.',
    accent: 'blue',
  },
  {
    id: 'coding',
    number: '02',
    label: 'CODE',
    title: '코딩 도움',
    description: '선호하는 TypeScript와 React 작성 방식을 찾아 Copilot·Cursor 설정 파일로 가져갑니다.',
    accent: 'purple',
  },
  {
    id: 'idleTracker',
    number: '03',
    label: 'AWS COST',
    title: 'AWS 비용 보고',
    description: '서비스별 비용 현황을 내가 보기 편한 상세도와 강조점으로 보고받습니다.',
    accent: 'green',
  },
];

// 실험실: 엔진을 고치지 않고 붙는다는 확장성의 근거로 남겨 둔 카테고리.
// 제품 검증 범위 밖이라 기본 화면에서는 숨긴다.
const labCategories = [
  {
    id: 'summaryHybrid',
    number: 'L1',
    label: 'LAB · DEEP SUMMARY',
    title: '문서 요약 심화',
    description: '요약 길이와 원문 반영 정도를 더 세밀하게 맞춥니다.',
    accent: 'indigo',
  },
  {
    id: 'review',
    number: 'L2',
    label: 'LAB · REVIEW',
    title: '고객 리뷰 작성',
    description: '방문 메모를 내가 좋아하는 길이와 어조의 리뷰로 바꿉니다.',
    accent: 'orange',
  },
  {
    id: 'email',
    number: 'L3',
    label: 'LAB · EMAIL',
    title: '이메일 초안',
    description: '전달할 내용을 원하는 길이와 말투의 이메일로 정리합니다.',
    accent: 'teal',
  },
  {
    id: 'macsumEval',
    number: 'L4',
    label: 'LAB · DOC QUALITY',
    title: '문서 품질 평가',
    description: '문장을 얼마나 간결하고 읽기 쉽게 다듬을지 정합니다.',
    accent: 'rose',
  },
];

const labIds = new Set(labCategories.map(({ id }) => id));

function StoryVisual({ type }) {
  if (type === 'category') {
    return (
      <div className="story-visual-card story-visual-category">
        <div className="story-visual-label">START HERE</div>
          <div className="story-mini-options">
          <div className="story-mini-option story-mini-blue">문서 요약</div>
          <div className="story-mini-option story-mini-purple">코딩 도움</div>
          <div className="story-mini-option story-mini-green">AWS 비용</div>
        </div>
        <div className="story-visual-arrow" aria-hidden="true">↗</div>
      </div>
    );
  }

  if (type === 'compare') {
    return (
      <div className="story-visual-card story-visual-compare">
        <div className="story-visual-label">01 / CODE STRUCTURE</div>
        <p className="story-compare-question">어떤 코드가 더 편한가요?</p>
        <div className="story-compare-row">
          <div>
            <span>A</span>
            <strong>간결하게 작성</strong>
            <code>Button.jsx</code>
          </div>
          <div className="story-compare-selected">
            <span>B</span>
            <strong>역할별 파일로 분리</strong>
            <code>Button / hook / css</code>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="story-visual-card story-visual-result">
      <div className="story-visual-label">YOUR PROMPT</div>
      <div className="story-prompt-line">✓ structure: separated</div>
      <div className="story-prompt-line">✓ style: theme-based</div>
      <div className="story-prompt-line">✓ types: explicit</div>
      <div className="story-prompt-ready">재사용할 준비가 됐어요</div>
    </div>
  );
}

function NarrativeScene({ scene, direction }) {
  return (
    <motion.article
      className="narrative-scene narrative-story-scene"
      initial={{ opacity: 0, y: direction > 0 ? 90 : -90, scale: 0.94 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: direction > 0 ? -90 : 90, scale: 0.94 }}
      transition={{ duration: 0.48, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="narrative-copy">
        <span className="scroll-story-scene-number">{scene.number}</span>
        <p className="scroll-story-scene-kicker">{scene.kicker}</p>
        <h2>{scene.title}</h2>
        <p>{scene.description}</p>
      </div>
      <StoryVisual type={scene.visual} />
    </motion.article>
  );
}

function IntroScene({ selectedCategory, onSelectCategory, onContinue, direction }) {
  const [showLab, setShowLab] = useState(labIds.has(selectedCategory));
  const options = showLab ? [...coreCategories, ...labCategories] : coreCategories;
  const toggleLab = () => {
    // 실험실을 닫을 때 실험실 카드가 골라져 있으면, 보이지 않는 카드로
    // 시작하지 않게 첫 카드로 돌린다.
    if (showLab && labIds.has(selectedCategory)) onSelectCategory(coreCategories[0].id);
    setShowLab(!showLab);
  };
  return (
    <motion.article
      className="narrative-scene narrative-intro-scene"
      initial={{ opacity: 0, y: direction > 0 ? 90 : -90, scale: 0.94 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: direction > 0 ? -90 : 90, scale: 0.94 }}
      transition={{ duration: 0.48, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="narrative-intro-copy">
        <p className="hero-kicker">PREFERENCE PROMPT TOOL</p>
        <h1>
          좋아하는 결과를
          <br />
          <em>고르는 것</em>부터 시작하세요.
        </h1>
        <p>복잡한 프롬프트를 직접 작성하지 않아도, 선택만으로 나만의 기준을 만들 수 있습니다.</p>
      </div>

      <div className="narrative-category-stage">
        <div className="narrative-stage-heading">
          <div>
            <p className="stage-index">01 / START HERE</p>
            <h2>무엇을 도와드릴까요?</h2>
          </div>
          <span>카드를 옆으로 넘겨 필요한 작업을 고르세요.</span>
        </div>

        <CategoryDeck options={options} selectedCategory={selectedCategory}
          onSelect={onSelectCategory} onContinue={onContinue} />
        <div className="category-lab-toggle">
          <button type="button" onClick={toggleLab} aria-expanded={showLab}>
            {showLab ? '핵심 카테고리만 보기' : `실험실 카테고리 보기 (${labCategories.length})`}
          </button>
          <span>실험실은 같은 엔진에 도메인 정의만 더해 붙인 카테고리입니다. 품질은 검증 전입니다.</span>
        </div>
      </div>
    </motion.article>
  );
}

function ScrollStory({ selectedCategory, onSelectCategory, onContinue, sceneRequest }) {
  const [activeScene, setActiveScene] = useState(0);
  const [direction, setDirection] = useState(1);
  const touchStartY = useRef(null);
  const wheelLock = useRef(false);

  const moveScene = (nextScene) => {
    const clampedScene = Math.min(3, Math.max(0, nextScene));
    if (clampedScene === activeScene) return;
    setDirection(clampedScene > activeScene ? 1 : -1);
    setActiveScene(clampedScene);
  };

  useEffect(() => {
    const handleWheel = (event) => {
      if (event.target.closest('.narrative-category-stage')) return;
      event.preventDefault();
      if (wheelLock.current || Math.abs(event.deltaY) < 12) return;

      wheelLock.current = true;
      moveScene(activeScene + (event.deltaY > 0 ? 1 : -1));
      window.setTimeout(() => {
        wheelLock.current = false;
      }, 620);
    };

    const handleKeyDown = (event) => {
      if (event.defaultPrevented || event.target.closest('button, input, textarea, select, [contenteditable], .category-deck')) return;
      if (['ArrowDown', 'PageDown', ' ', 'ArrowRight'].includes(event.key)) {
        event.preventDefault();
        moveScene(activeScene + 1);
      }
      if (['ArrowUp', 'PageUp', 'ArrowLeft'].includes(event.key)) {
        event.preventDefault();
        moveScene(activeScene - 1);
      }
    };

    const handleTouchStart = (event) => {
      if (event.target.closest('.narrative-category-stage')) {
        touchStartY.current = null;
        return;
      }
      touchStartY.current = event.touches[0]?.clientY ?? null;
    };

    const handleTouchEnd = (event) => {
      if (touchStartY.current === null) return;
      const delta = touchStartY.current - (event.changedTouches[0]?.clientY ?? touchStartY.current);
      if (Math.abs(delta) > 40) moveScene(activeScene + (delta > 0 ? 1 : -1));
      touchStartY.current = null;
    };

    const root = document.querySelector('.narrative-shell');
    root?.addEventListener('wheel', handleWheel, { passive: false });
    root?.addEventListener('touchstart', handleTouchStart, { passive: true });
    root?.addEventListener('touchend', handleTouchEnd, { passive: true });
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      root?.removeEventListener('wheel', handleWheel);
      root?.removeEventListener('touchstart', handleTouchStart);
      root?.removeEventListener('touchend', handleTouchEnd);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [activeScene]);

  useEffect(() => {
    if (!sceneRequest) return;
    setDirection(sceneRequest.index > activeScene ? 1 : -1);
    setActiveScene(Math.min(3, Math.max(0, sceneRequest.index)));
  }, [sceneRequest?.sequence]);

  return (
    <section className="narrative-shell" id="how-it-works" aria-label="서비스 소개">
      <div className="narrative-rail" aria-label={`현재 ${activeScene + 1}번째 장면`}>
        {Array.from({ length: 10 }, (_, index) => (
          <span key={index} className={index === activeScene * 3 ? 'is-active' : ''} />
        ))}
      </div>

      <div className="narrative-scenes">
        <AnimatePresence mode="wait" initial={false}>
          {activeScene === 0 ? (
            <IntroScene
              key="intro"
              selectedCategory={selectedCategory}
              onSelectCategory={onSelectCategory}
              onContinue={onContinue}
              direction={direction}
            />
          ) : (
            <NarrativeScene
              key={scenes[activeScene - 1].number}
              scene={scenes[activeScene - 1]}
              direction={direction}
            />
          )}
        </AnimatePresence>
      </div>

      <div className={`narrative-footer ${activeScene === 0 ? 'is-intro' : ''}`}>
        <span>SCROLL TO EXPLORE</span>
        <span>{String(activeScene + 1).padStart(2, '0')} / 04</span>
      </div>
    </section>
  );
}

export default ScrollStory;

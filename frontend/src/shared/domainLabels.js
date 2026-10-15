// 카테고리(도메인)와 축 값의 화면 이름. 비교 화면과 팀 프롬프트 화면이 같이 쓴다.

export const CATEGORY_LABEL = {
  coding: '코딩 도움',
  idle_tracker: 'AWS 비용 보고',
  review: '고객 리뷰 작성',
  email: '이메일 초안',
  summarization: '문서 요약 (영어)',
  summarization_ko: '문서 요약 (한국어)',
  summarization_hybrid: '문서 요약 심화',
  macsum_eval_agent: '문서 품질 평가',
};

export const categoryLabel = (domainKey) => CATEGORY_LABEL[domainKey] || domainKey;

// 도메인 이름 -> 비교 화면 흐름 이름 (AWS 만 화면 이름이 다르다. App.jsx 와 같다).
export const flowOfDomain = (domainKey) => (domainKey === 'idle_tracker' ? 'idleTracker' : domainKey);

export const AXIS_LABELS = {
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

export const axisValueLabel = (axis, value) => AXIS_LABELS[axis]?.options?.[value] || value;

export const codingComparisonAxes = [
  {
    id: 'structure',
    eyebrow: '01 · 코드 구조',
    question: '작은 기능을 만들 때 어떤 구성이 더 편한가요?',
    options: [
      {
        id: 'compact',
        title: '간결하게 작성',
        description: '작은 기능은 한 파일에서 흐름을 빠르게 파악합니다.',
        code: `function Greeting({ name }) {
  return <p>안녕하세요, {name}님</p>;
}`,
      },
      {
        id: 'separated',
        title: '역할별 파일로 분리',
        description: '화면, 로직, 스타일을 나누어 각각의 역할을 분명하게 합니다.',
        code: `Greeting.jsx   // 화면
useGreeting.js // 로직
Greeting.css   // 스타일`,
      },
    ],
  },
  {
    id: 'styleManagement',
    eyebrow: '02 · 스타일 관리',
    question: '디자인을 관리할 때 어떤 방식이 더 마음에 드나요?',
    options: [
      {
        id: 'direct',
        title: '값을 직접 작성',
        description: '스타일 파일에서 색상과 간격을 바로 확인합니다.',
        code: `.button {
  padding: 12px 20px;
  background: #2563eb;
}`,
      },
      {
        id: 'theme',
        title: '나중에 전체 디자인을 쉽게 수정',
        description: '테마와 디자인 값을 한곳에서 관리해 일관성을 지킵니다.',
        code: `const theme = {
  colors: { primary: '#2563eb' },
  spacing: { md: '12px' },
};`,
      },
    ],
  },
  {
    id: 'typeDetail',
    eyebrow: '03 · 타입 작성',
    question: 'TypeScript 타입을 어느 정도로 작성할까요?',
    options: [
      {
        id: 'inferred',
        title: '필요한 곳만 작성',
        description: '간단한 값은 TypeScript의 추론을 활용해 코드를 짧게 씁니다.',
        code: `const count = 0;
const label = '시작하기';`,
      },
      {
        id: 'explicit',
        title: '타입을 꼼꼼하게 작성',
        description: 'Props와 함수의 입력·출력 타입을 명확하게 남깁니다.',
        code: `type ButtonProps = {
  label: string;
  onClick: () => void;
};`,
      },
    ],
  },
];

export function buildCodingPrompt(answers) {
  const selected = codingComparisonAxes.map((axis) => {
    const option = axis.options.find(({ id }) => id === answers[axis.id]);
    return `${axis.eyebrow}: ${option.title} — ${option.description}`;
  });

  return [
    '당신은 TypeScript와 React 코딩을 도와주는 AI입니다.',
    '아래 사용자의 선호를 모든 코드 예시에 일관되게 반영하세요.',
    '',
    ...selected.map((line) => `- ${line}`),
    '',
    '코드는 바로 실행할 수 있게 작성하고, 선택한 구조를 왜 사용했는지 짧게 설명하세요.',
  ].join('\n');
}

export const otherComparisonAxes = {
  summarization: [
    { id: 'length', eyebrow: '요약 길이', question: '요약을 어느 정도로 작성할까요?', options: [{ id: 'short', title: '핵심만 짧게', description: '중요한 내용만 2문장 안에 담습니다.', code: '핵심 내용만 짧게 정리합니다.' }, { id: 'long', title: '상세하게 정리', description: '배경과 세부 내용을 5문장 이상으로 설명합니다.', code: '배경과 핵심 내용을 자세히 정리합니다.' }] },
    { id: 'extractiveness', eyebrow: '표현 방식', question: '원문의 표현을 얼마나 살릴까요?', options: [{ id: 'normal', title: '내 표현으로 바꿔 쓰기', description: '내용은 유지하되 자연스럽게 다시 씁니다.', code: '원문을 자연스러운 표현으로 바꿔 씁니다.' }, { id: 'fully', title: '원문 문장을 그대로 발췌', description: '원문의 문장과 표현을 최대한 그대로 사용합니다.', code: '원문 문장을 그대로 골라 이어 붙입니다.' }] },
  ],
  summarization_ko: [
    { id: 'length', eyebrow: '요약 길이', question: '한국어 요약을 어느 정도로 작성할까요?', options: [{ id: 'short', title: '핵심만 짧게', description: '중요한 내용만 2문장 안에 담습니다.', code: '핵심 내용만 짧게 정리합니다.' }, { id: 'long', title: '상세하게 정리', description: '배경과 세부 내용을 5문장 이상으로 설명합니다.', code: '배경과 핵심 내용을 자세히 정리합니다.' }] },
    { id: 'extractiveness', eyebrow: '표현 방식', question: '원문의 표현을 얼마나 살릴까요?', options: [{ id: 'normal', title: '내 표현으로 바꿔 쓰기', description: '내용은 유지하되 자연스러운 한국어로 다시 씁니다.', code: '원문을 자연스러운 한국어로 바꿔 씁니다.' }, { id: 'fully', title: '원문 문장을 그대로 발췌', description: '원문의 문장과 표현을 최대한 그대로 사용합니다.', code: '원문 문장을 그대로 골라 이어 붙입니다.' }] },
  ],
  summarization_hybrid: [
    { id: 'length', eyebrow: '요약 길이', question: '요약을 어느 정도로 작성할까요?', options: [{ id: 'short', title: '핵심만 짧게', description: '가장 중요한 내용만 빠르게 파악합니다.', code: '핵심 내용만 짧게 정리합니다.' }, { id: 'long', title: '배경까지 상세하게', description: '핵심과 배경을 함께 읽을 수 있도록 정리합니다.', code: '배경과 세부 내용을 자세히 정리합니다.' }] },
    { id: 'extractiveness', eyebrow: '표현 방식', question: '원문의 표현을 얼마나 살릴까요?', options: [{ id: 'normal', title: '내 표현으로 바꿔 쓰기', description: '내용은 유지하되 자연스럽게 다시 씁니다.', code: '원문을 자연스러운 표현으로 바꿔 씁니다.' }, { id: 'fully', title: '원문 문장을 그대로 발췌', description: '원문의 문장과 표현을 최대한 그대로 사용합니다.', code: '원문 문장을 그대로 골라 이어 붙입니다.' }] },
    { id: 'specificity', eyebrow: '설명 밀도', question: '얼마나 구체적으로 설명할까요?', options: [{ id: 'normal', title: '큰 흐름만', description: '세부 숫자보다 전체 흐름과 결론을 먼저 보여줍니다.', code: '전체 흐름과 결론을 중심으로 설명합니다.' }, { id: 'high', title: '세부 내용까지', description: '날짜·수치·고유명사 같은 근거를 빠뜨리지 않습니다.', code: '날짜·수치·고유명사까지 구체적으로 설명합니다.' }] },
  ],
  review: [
    { id: 'length', eyebrow: '리뷰 길이', question: '리뷰를 어느 정도로 작성할까요?', options: [{ id: 'short', title: '핵심만 짧게', description: '두 문장 안에 경험을 담습니다.', code: 'Great food and quick service.' }, { id: 'long', title: '경험을 자세히', description: '좋았던 점과 아쉬운 점을 자세히 씁니다.', code: 'The broth was rich, and the staff explained every dish...' }] },
    { id: 'sentiment', eyebrow: '리뷰 어조', question: '어떤 느낌으로 작성할까요?', options: [{ id: 'neutral', title: '담담하게 정리', description: '장단점을 균형 있게 보여줍니다.', code: 'The food was good, although the wait was long.' }, { id: 'positive', title: '좋았던 점 강조', description: '만족스러운 경험을 중심으로 씁니다.', code: 'I loved the rich broth and would gladly return.' }] },
  ],
  email: [
    { id: 'length', eyebrow: '이메일 길이', question: '이메일을 어느 정도로 작성할까요?', options: [{ id: 'short', title: '짧고 빠르게', description: '핵심 요청만 두 문장으로 전달합니다.', code: 'Could you confirm the delivery date?\nThank you.' }, { id: 'long', title: '상황을 자세히', description: '배경과 다음 단계를 함께 설명합니다.', code: 'I am writing to follow up on our order...\nPlease let me know if anything changed.' }] },
    { id: 'formality', eyebrow: '이메일 말투', question: '어떤 말투가 더 편한가요?', options: [{ id: 'casual', title: '편하고 친근하게', description: '팀 동료에게 보내듯 자연스럽게 씁니다.', code: "Hi Alex, could you take a look? Thanks!" }, { id: 'formal', title: '격식 있게', description: '비즈니스 문장과 예의를 갖춥니다.', code: 'Dear Alex,\nCould you please confirm the delivery date?' }] },
  ],
  macsum_eval_agent: [
    { id: 'conciseness', eyebrow: '문장 밀도', question: '문장을 얼마나 간결하게 다듬을까요?', options: [{ id: 'concise', title: '짧고 선명하게', description: '겹치는 표현을 줄이고 핵심을 빠르게 전달합니다.', code: '핵심만 남기고 짧게 씁니다.' }, { id: 'detailed', title: '맥락을 충분히', description: '읽는 사람이 배경을 이해할 수 있도록 내용을 남깁니다.', code: '맥락과 설명을 충분히 남깁니다.' }] },
    { id: 'formality', eyebrow: '문장 말투', question: '어떤 말투로 다듬을까요?', options: [{ id: 'informal', title: '자연스럽고 편하게', description: '딱딱한 표현을 줄이고 읽기 편하게 씁니다.', code: '자연스럽고 편한 말투를 사용합니다.' }, { id: 'formal', title: '정돈되고 격식 있게', description: '보고서나 업무 문서에 맞는 표현을 사용합니다.', code: '정돈되고 격식 있는 말투를 사용합니다.' }] },
    { id: 'sentence_complexity', eyebrow: '문장 난이도', question: '문장 구조를 어느 정도로 만들까요?', options: [{ id: 'simple', title: '쉽게 나누어 쓰기', description: '긴 문장을 나누어 누구나 빠르게 읽게 합니다.', code: '문장을 짧고 쉽게 나누어 씁니다.' }, { id: 'complex', title: '정교하게 연결하기', description: '조건과 관계를 한 문장 안에서 정확하게 표현합니다.', code: '문장 관계를 정교하게 연결합니다.' }] },
    { id: 'focus_on_entities', eyebrow: '강조점', question: '무엇을 더 눈에 띄게 할까요?', options: [{ id: 'general', title: '전체 흐름 중심', description: '문서 전체의 맥락과 주제를 고르게 보여줍니다.', code: '전체 흐름과 주제를 고르게 보여줍니다.' }, { id: 'entity-focused', title: '이름과 숫자 중심', description: '사람, 제품, 기관, 수치 같은 핵심 대상을 강조합니다.', code: '핵심 대상과 수치를 눈에 띄게 표시합니다.' }] },
  ],
};

export function buildPreferencePrompt(domainKey, axes, answers) {
  const lines = axes.map((axis) => {
    const option = axis.options.find(({ id }) => id === answers[axis.id]);
    return option ? `- ${axis.eyebrow}: ${option.title} — ${option.description}` : null;
  }).filter(Boolean);
  const intro = domainKey === 'email'
    ? '이메일 초안'
      : domainKey === 'review'
        ? '고객 리뷰'
        : domainKey.startsWith('summarization')
          ? '문서 요약'
          : domainKey === 'macsum_eval_agent'
            ? '문서 품질 평가'
            : '개인화된 결과';
  return [`당신은 ${intro} 작성을 돕는 AI입니다.`, '아래 사용자의 선호를 모든 결과에 일관되게 반영하세요.', '', ...lines, '', '원문의 사실을 유지하고 바로 사용할 수 있는 결과를 작성하세요.'].join('\n');
}

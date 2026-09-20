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
  review: [
    { id: 'length', eyebrow: '리뷰 길이', question: '리뷰를 어느 정도로 작성할까요?', options: [{ id: 'short', title: '핵심만 짧게', description: '두 문장 안에 경험을 담습니다.', code: 'Great food and quick service.' }, { id: 'long', title: '경험을 자세히', description: '좋았던 점과 아쉬운 점을 자세히 씁니다.', code: 'The broth was rich, and the staff explained every dish...' }] },
    { id: 'sentiment', eyebrow: '리뷰 어조', question: '어떤 느낌으로 작성할까요?', options: [{ id: 'neutral', title: '담담하게 정리', description: '장단점을 균형 있게 보여줍니다.', code: 'The food was good, although the wait was long.' }, { id: 'positive', title: '좋았던 점 강조', description: '만족스러운 경험을 중심으로 씁니다.', code: 'I loved the rich broth and would gladly return.' }] },
  ],
  email: [
    { id: 'length', eyebrow: '이메일 길이', question: '이메일을 어느 정도로 작성할까요?', options: [{ id: 'short', title: '짧고 빠르게', description: '핵심 요청만 두 문장으로 전달합니다.', code: 'Could you confirm the delivery date?\nThank you.' }, { id: 'long', title: '상황을 자세히', description: '배경과 다음 단계를 함께 설명합니다.', code: 'I am writing to follow up on our order...\nPlease let me know if anything changed.' }] },
    { id: 'formality', eyebrow: '이메일 말투', question: '어떤 말투가 더 편한가요?', options: [{ id: 'casual', title: '편하고 친근하게', description: '팀 동료에게 보내듯 자연스럽게 씁니다.', code: "Hi Alex, could you take a look? Thanks!" }, { id: 'formal', title: '격식 있게', description: '비즈니스 문장과 예의를 갖춥니다.', code: 'Dear Alex,\nCould you please confirm the delivery date?' }] },
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
        : '개인화된 결과';
  return [`당신은 ${intro} 작성을 돕는 AI입니다.`, '아래 사용자의 선호를 모든 결과에 일관되게 반영하세요.', '', ...lines, '', '원문의 사실을 유지하고 바로 사용할 수 있는 결과를 작성하세요.'].join('\n');
}

export const PREFERENCE_CATEGORIES = {
  summarization_ko: '요약용 · 한국어', summarization: '요약용 · 영어', coding: '코딩용',
};

export const WORK_EXAMPLES = {
  summarization_ko: '출시 회의에서 일정을 다음 주 금요일로 정했습니다. 민수는 수요일까지 화면을 검토하고 지은은 목요일까지 테스트합니다. 외부 연동 일정은 아직 정해지지 않았습니다.',
  summarization: 'The team agreed to release next Friday. Dana will review the interface by Wednesday. Alex will finish testing on Thursday. The external integration date is still undecided.',
  coding: 'TypeScript와 React로 할 일 목록을 만들어 주세요. 항목 추가, 완료 표시, 삭제 기능이 필요합니다.',
};

export function composePreferenceRequest(prompt, task, domain) {
  if (!prompt?.trim() || !task?.trim()) return '';
  return `${prompt.trim()}\n\n---\n${domain === 'coding' ? '이번 개발 요청' : '이번에 요약할 원문'}\n\n${task.trim()}`;
}

// 내보내기 패널의 복사 상태를 버튼 문구와 안내로 바꾸는 순수 함수들.
// React·DOM·navigator 를 읽지 않는다 - 같은 상태면 같은 결과다.
//
// 상태는 마지막으로 시도한 복사 하나만 나타낸다.
//   { itemKey, variant, status }
//   variant: 'full' (일반 복사) | 'compact' (짧은 판 복사)
//   status:  'done' | 'failed'
export const COPY_FAILED_NOTICE = '복사하지 못했습니다. 내용을 직접 선택해 복사하세요';

export const IDLE_COPY_STATE = Object.freeze({ itemKey: '', variant: '', status: 'idle' });

const DONE_LABEL = '복사했습니다 ✓';
const DEFAULT_LABELS = { full: '복사', compact: '짧은 판 복사' };

export function copyResult(itemKey, variant, ok) {
  return { itemKey, variant, status: ok ? 'done' : 'failed' };
}

function isTarget(state, itemKey, variant) {
  return Boolean(state) && state.itemKey === itemKey && state.variant === variant;
}

export function buttonLabel(state, itemKey, variant) {
  if (isTarget(state, itemKey, variant) && state.status === 'done') return DONE_LABEL;
  return DEFAULT_LABELS[variant] ?? DEFAULT_LABELS.full;
}

// 해당 항목에서 복사가 실패했으면 어느 판이었는지('full'|'compact'), 아니면 ''.
export function failedVariant(state, itemKey) {
  if (state && state.status === 'failed' && state.itemKey === itemKey) return state.variant;
  return '';
}

export function failureNotice(state, itemKey) {
  return failedVariant(state, itemKey) ? COPY_FAILED_NOTICE : '';
}

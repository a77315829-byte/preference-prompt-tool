const API_BASE = '/api';

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.error || `API 요청에 실패했습니다 (${response.status})`);
  }
  return body;
}

// 타이핑마다 불러도 되는 무료 경로 - 모델을 부르지 않고 코드 점검만 돈다.
export function checkPromptStructure(prompt) {
  return request('/polish/checklist', {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  });
}

// 제출했을 때 한 번만 부르는 경로 - 체크리스트 + LLM 재작성.
export function polishPrompt(prompt) {
  return request('/polish', {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  });
}

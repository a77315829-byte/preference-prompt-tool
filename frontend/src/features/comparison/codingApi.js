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

// templateId: 템플릿 라이브러리의 "내 방식으로 바꾸기"로 시작할 때. 결과는
// 템플릿 본문 + 추정한 선호 절이 된다.
export function startPreferenceSession(domainKey, sourceText, totalRounds = 8, templateId = null) {
  return request('/sessions', {
    method: 'POST',
    body: JSON.stringify({
      domainKey,
      sourceText,
      demoMode: true,
      totalRounds,
      ...(templateId ? { templateId } : {}),
    }),
  });
}

export function submitPreferenceChoice(sessionId, pairId, chosen) {
  return request(`/sessions/${sessionId}/choices`, {
    method: 'POST',
    body: JSON.stringify({ pairId, chosen }),
  });
}

// GEPA 최적화는 수십 초 걸린다. 시작만 요청하고, 진행률과 결과는
// fetchSession 으로 폴링해 session.optimize_status/optimize_progress/prompt 에서 읽는다.
export function startOptimization(sessionId) {
  return request(`/sessions/${sessionId}/optimize`, { method: 'POST', body: '{}' });
}

export function fetchSession(sessionId) {
  return request(`/sessions/${sessionId}`);
}

export const startCodingSession =(sourceText) => startPreferenceSession('coding', sourceText, 8);
export const submitCodingChoice = submitPreferenceChoice;

export function fetchAwsCostReport({ demoMode = true, lookbackDays = 30 } = {}) {
  return request('/aws/costs', {
    method: 'POST',
    body: JSON.stringify({ demoMode, lookbackDays }),
  });
}

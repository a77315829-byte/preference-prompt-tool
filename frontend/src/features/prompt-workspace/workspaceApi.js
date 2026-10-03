// 개발자용 작업 공간 API (api_server.py 의 /api/workspace/*).
// 서버는 프로젝트를 들고 있지 않는다 - 화면이 단계마다 프로젝트 JSON 을 보낸다.
const API_BASE = '/api';

async function request(path, body) {
  const response = await fetch(`${API_BASE}${path}`, body === undefined
    ? {}
    : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `요청에 실패했습니다 (${response.status})`);
  return data;
}

export const fetchHealth = () => request('/health');
export const fetchSample = () => request('/workspace/sample');
export const structureDescription = (title, description, exampleOutput) =>
  request('/workspace/structure', { title, description, exampleOutput });
export const checkProject = (project) => request('/workspace/status', { project });
export const confirmProject = (project) => request('/workspace/confirm', { project });
export const buildProject = (project) => request('/workspace/build', { project });
export const runProject = (project, input) => request('/workspace/run', { project, input });
export const exportProject = (project, input, includeData) =>
  request('/workspace/export', { project, input, includeData });

// 미결 사항에 답하고 닫기. target: hard_rule | preference | none
export const resolveQuestion = (project, questionId, answer, target) =>
  request('/workspace/resolve', { project, questionId, answer, target });

// 저장소 (인증 없는 로컬 전용). 저장은 새 버전을 덧붙이고, 복원도 새 버전이다.
export const listProjects = () => request('/workspace/projects');
export const openProject = (id) => request(`/workspace/projects/${encodeURIComponent(id)}`);
export const fetchVersion = (id, version) =>
  request(`/workspace/projects/${encodeURIComponent(id)}/versions/${version}`);
export const saveProject = (project, label) => request('/workspace/projects', { project, label });
export const restoreVersion = (id, version) =>
  request(`/workspace/projects/${encodeURIComponent(id)}/restore`, { version });
export const deleteProject = (id) => request(`/workspace/projects/${encodeURIComponent(id)}/delete`, {});

// 프로젝트 공유 (소유자만). role: viewer | editor
export const shareProject = (id, username, role) =>
  request(`/workspace/projects/${encodeURIComponent(id)}/share`, { username, role });
export const unshareProject = (id, username) =>
  request(`/workspace/projects/${encodeURIComponent(id)}/unshare`, { username });

// 자동 저장. 버전이 아니라 사용자마다 하나인 작업 중 사본을 덮어쓴다.
export const saveDraft = (project) =>
  request(`/workspace/projects/${encodeURIComponent(project.id)}/draft`, { project });
export const discardDraft = (id) => request(`/workspace/projects/${encodeURIComponent(id)}/discard-draft`, {});

// 개선 방향 추천 (AI 1회) 과 고른 제안으로 만든 수정안 (AI 없음, 프로젝트는 안 바뀜).
export const suggestImprovements = (project) => request('/workspace/suggest', { project });
export const applySuggestions = (project, suggestions, allowRuleChanges) =>
  request('/workspace/apply-suggestions', { project, suggestions, allowRuleChanges });

// 제안마다 같은 입력으로 시험해 검사 변화를 센다 (지금 지침 1회 + 제안 수만큼 AI 호출).
export const trialSuggestions = (project, input, suggestions) =>
  request('/workspace/trial-suggestions', { project, input, suggestions });

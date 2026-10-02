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

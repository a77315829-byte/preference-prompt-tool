// 팀 모드 API (api_server.py 의 /api/teams, 서버 team.py). 원문은 보내지 않고 선택 기록만 더한다.

async function call(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `요청에 실패했습니다 (${response.status})`);
  return body;
}

export const fetchTeam = (code) => call(`/teams/${encodeURIComponent(code)}`).then((body) => body.team);
export const joinTeam = (code, sessionId, name) => call(`/teams/${encodeURIComponent(code)}/members`, {
  method: 'POST',
  body: JSON.stringify({ sessionId, name }),
}).then((body) => body.team);
// 로그인한 사람이 참여한 팀 목록 (팀원 수와 마지막 참여 시각만).
export const fetchMyTeams = () => call('/teams').then((body) => body.teams);

// 카테고리별로 묶는다. 목록이 최근순이므로 최근에 움직인 카테고리가 위에 온다.
export function groupByCategory(teams) {
  const groups = new Map();
  teams.forEach((t) => {
    if (!groups.has(t.domain_key)) groups.set(t.domain_key, []);
    groups.get(t.domain_key).push(t);
  });
  return [...groups.entries()].map(([domainKey, items]) => ({ domainKey, items }));
}

// 이 브라우저에서 최근 보거나 더한 팀 코드. 로그인하지 않은 팀원도 다시 찾을 수 있게.
// 서버에는 남지 않고, 지워져도 팀 코드로 다시 열면 된다.
const RECENT_KEY = 'ppt-recent-teams';
export const MAX_RECENT = 8;

export function withRecent(list, entry) {
  return [entry, ...list.filter((t) => t.code !== entry.code)].slice(0, MAX_RECENT);
}

export function readRecentTeams() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(RECENT_KEY) || '[]');
    return Array.isArray(parsed)
      ? parsed.filter((t) => t && typeof t.code === 'string' && typeof t.domain_key === 'string')
      : [];
  } catch {
    return [];
  }
}

export function rememberTeam(team) {
  try {
    const next = withRecent(readRecentTeams(), { code: team.code, domain_key: team.domain_key });
    window.localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    // 보관하지 못해도 팀 결과는 그대로 보인다.
  }
}

// "2026-10-15T09:30:00+00:00" -> "2026-10-15 09:30 UTC"
export const formatUtc = (iso) => (iso ? `${String(iso).replace('T', ' ').slice(0, 16)} UTC` : '');

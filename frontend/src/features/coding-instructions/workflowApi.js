export async function codingWork(path, body) {
  const response = await fetch(`/api/coding-work/${path}`, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || '코딩 작업 요청을 처리하지 못했어요.');
  return data;
}

export const ARM_LABELS = { general: '일반 지침', selected: '선택한 지침' };
export function differentPreferences(personal, team) {
  return Object.keys(personal.preferences).filter(key => personal.preferences[key] !== team.preferences[key]);
}
export function formatSeconds(value) {
  if (value === null || value === undefined) return '미측정';
  const seconds = Math.max(0, Math.floor(value));
  return `${Math.floor(seconds / 60)}분 ${seconds % 60}초`;
}
export function observedSeconds(trial, arm, phase, elapsedSinceFetch = 0) {
  const active = trial.active;
  return trial.arms[arm].seconds[phase] + (active?.arm === arm && active.phase === phase
    ? Math.max(0, trial.server_now - active.since + elapsedSinceFetch) : 0);
}
export function downloadText(filename, content, type = 'text/plain;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement('a');
  link.href = url; link.download = filename; document.body.appendChild(link); link.click(); link.remove();
  URL.revokeObjectURL(url);
}

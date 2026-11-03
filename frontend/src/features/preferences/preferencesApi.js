async function call(path = '', body) {
  const response = await fetch(`/api/preferences${path}`, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `요청에 실패했습니다 (${response.status})`);
  return data;
}

export const listPreferences = () => call().then((d) => d.preferences);
export const getPreference = (id) => call(`/${encodeURIComponent(id)}`).then((d) => d.preference);
export const createPreference = (body) => call('', body).then((d) => d.preference);
export const updatePreference = (id, body) => call(`/${encodeURIComponent(id)}/update`, body).then((d) => d.preference);
export const deletePreference = (id, revision) => call(`/${encodeURIComponent(id)}/delete`, { revision });
export const comparePreferenceTeam = (id, revision, teamCode, language = '') => call(`/${encodeURIComponent(id)}/compare-team`, { revision, teamCode, language }).then((d) => d.comparison);
export const composeTaskPreference = (item, comparison, choices) => call(`/${encodeURIComponent(item.id)}/compose-task`, {
  revision: item.revision, teamCode: comparison.team_code, teamSnapshot: comparison.team_snapshot,
  language: comparison.team_language, choices,
}).then((d) => d.draft);
export const saveTaskPreference = (item, comparison, draft, title, note) => call(`/${encodeURIComponent(item.id)}/save-task`, {
  revision: item.revision, teamCode: comparison.team_code, teamSnapshot: comparison.team_snapshot,
  language: comparison.team_language, choices: draft.choices, taskSnapshot: draft.snapshot, title, note,
}).then((d) => d.preference);
export const runPreference = (id, revision, task, selection = {}) => call(`/${encodeURIComponent(id)}/run`, { revision, task, ...selection });

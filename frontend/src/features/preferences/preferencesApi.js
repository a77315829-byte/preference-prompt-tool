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
export const runPreference = (id, revision, task) => call(`/${encodeURIComponent(id)}/run`, { revision, task });

import { useEffect } from 'react';

const prefix = 'ppt.draft.v1:';
const memory = new Map();
const keyFor = (kind, user) => `${prefix}${user?.id || 'anonymous'}:${kind}`;

export function readDraft(kind, user) {
  const key = keyFor(kind, user);
  if (memory.has(key)) {
    const saved = memory.get(key);
    if (Date.now() - saved.at < 86400000) return saved.value;
    memory.delete(key);
  }
  try {
    const saved = JSON.parse(window.sessionStorage.getItem(key));
    if (saved && Date.now() - saved.at < 86400000) return saved.value;
  } catch { /* Storage disabled or an obsolete draft: start safely. */ }
  return null;
}

export function writeDraft(kind, user, value) {
  const key = keyFor(kind, user);
  const saved = { at: Date.now(), value };
  memory.set(key, saved);
  try {
    window.sessionStorage.setItem(key, JSON.stringify(saved));
    return true;
  } catch { return false; }
}

export function clearAccountDrafts(user) {
  const accountPrefix = `${prefix}${user?.id || 'anonymous'}:`;
  for (const key of memory.keys()) if (key.startsWith(accountPrefix)) memory.delete(key);
  try {
    for (const key of Object.keys(window.sessionStorage)) if (key.startsWith(accountPrefix)) window.sessionStorage.removeItem(key);
  } catch { /* In-memory drafts are still cleared. */ }
}

export function moveAnonymousDrafts(user) {
  for (const kind of ['coding', 'handoff']) {
    const value = readDraft(kind, null);
    if (value) writeDraft(kind, user, value);
  }
  clearAccountDrafts(null);
}

export function useDraftCache(kind, user, value, enabled = true) {
  useEffect(() => {
    if (!enabled) return undefined;
    const persisted = writeDraft(kind, user, value);
    if (persisted) return undefined;
    const warn = event => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [kind, user?.id, value, enabled]);
}

import { useState } from 'react';

export type Filters = { query: string; onlyOpen: boolean };
export type Item = { id: string; title: string; open: boolean };
export type Props = { items: Item[]; onApply: (filters: Filters) => void };

export function Component({ items, onApply }: Props) {
  const empty = { query: '', onlyOpen: false };
  const [draft, setDraft] = useState<Filters>(empty);
  const [applied, setApplied] = useState<Filters>(empty);
  const dirty = draft.query.trim() !== applied.query || draft.onlyOpen !== applied.onlyOpen;
  function apply() {
    const next = { ...draft, query: draft.query.trim() };
    setDraft(next);
    setApplied(next);
    onApply(next);
  }
  function reset() {
    setDraft(empty);
    setApplied(empty);
    onApply(empty);
  }
  const visible = items.filter(item => item.title.toLowerCase().includes(applied.query.toLowerCase()) && (!applied.onlyOpen || item.open));
  return <section aria-label="Issue filters">
    <label>Search issues<input value={draft.query} onChange={event => setDraft({ ...draft, query: event.currentTarget.value })} /></label>
    <label><input type="checkbox" checked={draft.onlyOpen} onChange={event => setDraft({ ...draft, onlyOpen: event.currentTarget.checked })} />Only open</label>
    <button type="button" disabled={!dirty} onClick={apply}>Apply</button>
    <button type="button" onClick={reset}>Reset</button>
    <ul aria-label="Issues">{visible.map(item => <li key={item.id}>{item.title}</li>)}</ul>
    {visible.length === 0 && <p role="status">No issues</p>}
  </section>;
}

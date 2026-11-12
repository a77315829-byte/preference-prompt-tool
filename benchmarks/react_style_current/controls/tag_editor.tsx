import { useState } from 'react';

export type Props = { initialTags: string[]; onChange: (tags: string[]) => void };

export function Component({ initialTags, onChange }: Props) {
  const [tags, setTags] = useState(() => [...initialTags]);
  const [draft, setDraft] = useState('');
  const [error, setError] = useState('');
  function add() {
    const nextTag = draft.trim();
    if (!nextTag) { setError('Empty tag'); return; }
    if (tags.some(tag => tag.toLowerCase() === nextTag.toLowerCase())) { setError('Duplicate tag'); return; }
    const next = [...tags, nextTag];
    setTags(next);
    setDraft('');
    setError('');
    onChange(next);
  }
  function remove(tag: string) {
    const next = tags.filter(value => value !== tag);
    setTags(next);
    setError('');
    onChange(next);
  }
  return <section data-testid="panel" style={{ backgroundColor: '#f2f6fc', color: '#1d3150', padding: 16, display: 'grid', gap: 8 }}>
    <form aria-label="Tag editor" onSubmit={event => { event.preventDefault(); add(); }}>
      <label>Add tag<input type="text" value={draft} onChange={event => setDraft(event.currentTarget.value)} /></label>
      <button type="submit">Add</button>
    </form>
    {error && <p role="alert">{error}</p>}
    <ul aria-label="Tags">{tags.map(tag => <li key={tag}><span>{tag}</span><button type="button" onClick={() => remove(tag)}>Remove {tag}</button></li>)}</ul>
  </section>;
}

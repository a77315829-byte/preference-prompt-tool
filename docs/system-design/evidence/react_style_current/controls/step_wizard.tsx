import { useState } from 'react';

export type Props = { initialName: string; onSubmit: (name: string) => void };

export function Component({ initialName, onSubmit }: Props) {
  const [name, setName] = useState(initialName);
  const [review, setReview] = useState(false);
  const [invalid, setInvalid] = useState(false);
  function next() {
    const trimmed = name.trim();
    if (!trimmed) { setInvalid(true); return; }
    setName(trimmed);
    setInvalid(false);
    setReview(true);
  }
  return <section data-testid="panel" style={{ backgroundColor: '#f2f6fc', color: '#1d3150', padding: 16, display: 'grid', gap: 8 }}>
    {review ? <>
      <output aria-label="Review name">{name}</output>
      <button type="button" onClick={() => setReview(false)}>Back</button>
      <button type="button" onClick={() => onSubmit(name)}>Submit</button>
    </> : <form aria-label="Name wizard" onSubmit={event => { event.preventDefault(); next(); }}>
      <label>Name<input type="text" value={name} aria-invalid={invalid || undefined} onChange={event => setName(event.currentTarget.value)} /></label>
      {invalid && <p role="alert">Name required</p>}
      <button type="submit">Next</button>
    </form>}
  </section>;
}

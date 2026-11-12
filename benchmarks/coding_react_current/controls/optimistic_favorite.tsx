import { useState } from 'react';

export type Props = { initialValue: boolean; save: (next: boolean) => Promise<void> };

export function Component({ initialValue, save }: Props) {
  const [favorite, setFavorite] = useState(initialValue);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  async function toggle() {
    if (pending) return;
    const previous = favorite;
    const next = !previous;
    setFavorite(next);
    setPending(true);
    setError('');
    try {
      await save(next);
    } catch {
      setFavorite(previous);
      setError('Save failed');
    } finally {
      setPending(false);
    }
  }
  return <section aria-label="Favorite setting">
    <button type="button" aria-pressed={favorite} disabled={pending} onClick={toggle}>Favorite</button>
    {pending && <p role="status">Saving</p>}
    {error && <p role="alert">{error}</p>}
  </section>;
}

import { useEffect, useState } from 'react';

export type Item = { id: string; label: string };
export type Props = { items: Item[]; pageSize: number };

export function Component({ items, pageSize }: Props) {
  const [page, setPage] = useState(1);
  const total = Math.max(1, Math.ceil(items.length / pageSize));
  const current = Math.min(page, total);
  useEffect(() => { setPage(value => Math.min(value, total)); }, [total]);
  const visible = items.slice((current - 1) * pageSize, current * pageSize);
  return <section aria-label="Review queue">
    <ul aria-label="Queue items">{visible.map(item => <li key={item.id}>{item.label}</li>)}</ul>
    {items.length === 0 && <p role="status">No items</p>}
    <output aria-label="Page">{current} / {total}</output>
    <button type="button" disabled={current === 1} onClick={() => setPage(current - 1)}>Previous</button>
    <button type="button" disabled={current === total} onClick={() => setPage(current + 1)}>Next</button>
  </section>;
}

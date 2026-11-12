import { useState } from 'react';

export type Row = { id: string; label: string; score: number | null };
export type Props = { rows: Row[] };

export function Component({ rows }: Props) {
  const [direction, setDirection] = useState<'none' | 'ascending' | 'descending'>('none');
  const ordered = rows.map((row, index) => ({ row, index }));
  if (direction !== 'none') ordered.sort((a, b) => {
    if (a.row.score === null) return b.row.score === null ? a.index - b.index : 1;
    if (b.row.score === null) return -1;
    const difference = a.row.score - b.row.score;
    return difference === 0 ? a.index - b.index : direction === 'ascending' ? difference : -difference;
  });
  return <section data-testid="panel" style={{ backgroundColor: '#f2f6fc', color: '#1d3150', padding: 16, display: 'grid', gap: 8 }}>
    <button type="button" onClick={() => setDirection(direction === 'ascending' ? 'descending' : 'ascending')}>Sort score</button>
    <table aria-label="Rows"><thead><tr><th>Label</th><th aria-sort={direction}>Score</th></tr></thead>
      <tbody>{ordered.map(({ row }) => <tr key={row.id}><td>{row.label}</td><td>{row.score === null ? '—' : row.score}</td></tr>)}</tbody>
    </table>
    {rows.length === 0 && <p role="status">No rows</p>}
  </section>;
}

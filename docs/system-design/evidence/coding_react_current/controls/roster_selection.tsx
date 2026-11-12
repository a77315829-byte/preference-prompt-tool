import { useState } from 'react';

export type Row = { id: string; name: string; team: string };
export type Props = { rows: Row[]; onSelectionChange: (ids: string[]) => void };

export function Component({ rows, onSelectionChange }: Props) {
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<string[]>([]);
  const visible = rows.filter(row => row.name.toLowerCase().includes(query.trim().toLowerCase()));
  function toggle(id: string) {
    const next = selected.includes(id) ? selected.filter(value => value !== id) : [...selected, id];
    setSelected(next);
    onSelectionChange(next);
  }
  function selectVisible(select: boolean) {
    const ids = visible.map(row => row.id);
    const next = select ? [...selected, ...ids.filter(id => !selected.includes(id))] : selected.filter(id => !ids.includes(id));
    setSelected(next);
    onSelectionChange(next);
  }
  return <section aria-label="Team roster">
    <label>Search members<input value={query} onChange={event => setQuery(event.currentTarget.value)} /></label>
    <output aria-label="Selected count">{selected.length}</output>
    <button type="button" disabled={visible.length === 0} onClick={() => selectVisible(true)}>Select visible</button>
    <button type="button" disabled={visible.length === 0} onClick={() => selectVisible(false)}>Clear visible</button>
    <table><thead><tr><th>Select</th><th>Name</th><th>Team</th></tr></thead><tbody>
      {visible.map(row => <tr key={row.id}>
        <td><input type="checkbox" aria-label={`Select ${row.name}`} checked={selected.includes(row.id)} onChange={() => toggle(row.id)} /></td>
        <td>{row.name}</td><td>{row.team}</td>
      </tr>)}
    </tbody></table>
    {visible.length === 0 && <p role="status">No members</p>}
  </section>;
}

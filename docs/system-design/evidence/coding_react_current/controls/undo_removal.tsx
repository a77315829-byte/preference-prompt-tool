import { useState } from 'react';

export type Item = { id: string; label: string };
export type Props = { initialItems: Item[]; onChange: (items: Item[]) => void };

export function Component({ initialItems, onChange }: Props) {
  const [items, setItems] = useState(initialItems);
  const [removed, setRemoved] = useState<{ item: Item; index: number } | null>(null);
  function remove(id: string) {
    const index = items.findIndex(item => item.id === id);
    if (index < 0) return;
    const next = items.filter(item => item.id !== id);
    setRemoved({ item: items[index], index });
    setItems(next);
    onChange(next);
  }
  function undo() {
    if (!removed) return;
    const next = [...items];
    next.splice(removed.index, 0, removed.item);
    setItems(next);
    setRemoved(null);
    onChange(next);
  }
  return <section aria-label="Attachment list">
    <ul aria-label="Attachments">{items.map(item => <li key={item.id}>{item.label}<button type="button" aria-label={`Remove ${item.label}`} onClick={() => remove(item.id)}>Remove</button></li>)}</ul>
    {items.length === 0 && <p role="status">No attachments</p>}
    <button type="button" disabled={!removed} onClick={undo}>Undo</button>
  </section>;
}

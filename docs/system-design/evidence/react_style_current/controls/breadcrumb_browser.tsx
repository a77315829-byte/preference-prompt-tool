import { useState } from 'react';

export type Folder = { id: string; name: string; children: Folder[] };
export type Props = { folders: Folder[]; onNavigate: (path: string[]) => void };

export function Component({ folders, onNavigate }: Props) {
  const [path, setPath] = useState<string[]>([]);
  let current = folders;
  const names: string[] = [];
  for (const id of path) {
    const folder = current.find(item => item.id === id);
    if (!folder) break;
    names.push(folder.name);
    current = folder.children;
  }
  function navigate(next: string[]) {
    setPath(next);
    onNavigate(next);
  }
  return <section data-testid="panel" style={{ backgroundColor: '#f2f6fc', color: '#1d3150', padding: 16, display: 'grid', gap: 8 }}>
    <output aria-label="Current path">{'/' + names.join('/')}</output>
    <button type="button" disabled={path.length === 0} onClick={() => navigate(path.slice(0, -1))}>Back</button>
    <ul aria-label="Folders">{current.map(folder => <li key={folder.id}><button type="button" onClick={() => navigate([...path, folder.id])}>Enter {folder.name}</button></li>)}</ul>
    {current.length === 0 && <p role="status">No folders</p>}
  </section>;
}

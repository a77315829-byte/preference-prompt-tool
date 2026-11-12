import { useEffect, useState } from 'react';

export type Props = { text: string; maxChars: number };

export function Component({ text, maxChars }: Props) {
  const [expanded, setExpanded] = useState(false);
  useEffect(() => { setExpanded(false); }, [text, maxChars]);
  const long = text.length > maxChars;
  const preview = long && !expanded ? text.slice(0, maxChars) + '…' : text;
  return <section data-testid="panel" style={{ backgroundColor: '#f2f6fc', color: '#1d3150', padding: 16, display: 'grid', gap: 8 }}>
    <output aria-label="Preview">{preview}</output>
    {long && <button type="button" onClick={() => setExpanded(!expanded)}>{expanded ? 'Show less' : 'Show more'}</button>}
  </section>;
}

import { useState } from 'react';

export type Props = { initialValue: string; onChange: (value: string) => void };

export function Component({ initialValue, onChange }: Props) {
  const [value, setValue] = useState(initialValue);
  const [visible, setVisible] = useState(false);
  return <section data-testid="panel" style={{ backgroundColor: '#f2f6fc', color: '#1d3150', padding: 16, display: 'grid', gap: 8 }}>
    <label>Password<input type={visible ? 'text' : 'password'} value={value} onChange={event => { const next = event.currentTarget.value; setValue(next); onChange(next); }} /></label>
    <button type="button" aria-pressed={visible} onClick={() => setVisible(!visible)}>Toggle visibility</button>
  </section>;
}

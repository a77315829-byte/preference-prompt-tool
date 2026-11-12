import { useState } from 'react';

export type Unit = 'C' | 'F';
export type Props = { initialValue: string; initialUnit: Unit };

export function Component({ initialValue, initialUnit }: Props) {
  const [value, setValue] = useState(initialValue);
  const [unit, setUnit] = useState(initialUnit);
  const numeric = Number(value.trim());
  const converted = unit === 'C' ? numeric * 9 / 5 + 32 : (numeric - 32) * 5 / 9;
  const valid = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(value.trim()) && Number.isFinite(numeric) && Number.isFinite(converted);
  function swap() {
    if (!valid) return;
    setValue(converted.toFixed(2));
    setUnit(unit === 'C' ? 'F' : 'C');
  }
  return <section data-testid="panel" style={{ backgroundColor: '#f2f6fc', color: '#1d3150', padding: 16, display: 'grid', gap: 8 }}>
    <label>Temperature<input type="text" value={value} aria-invalid={!valid || undefined} onChange={event => setValue(event.currentTarget.value)} /></label>
    <label>From unit<select value={unit} onChange={event => setUnit(event.currentTarget.value === 'F' ? 'F' : 'C')}><option value="C">C</option><option value="F">F</option></select></label>
    <output aria-label="Converted">{valid ? `${converted.toFixed(2)} ${unit === 'C' ? 'F' : 'C'}` : 'Invalid temperature'}</output>
    <button type="button" disabled={!valid} onClick={swap}>Swap</button>
  </section>;
}

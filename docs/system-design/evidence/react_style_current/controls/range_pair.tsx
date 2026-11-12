import { useState } from 'react';

export type Range = { start: number; end: number };
export type Props = { min: number; max: number; onApply: (range: Range) => void };

export function Component({ min, max, onApply }: Props) {
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [errors, setErrors] = useState({ start: false, end: false, message: '' });
  const values = Array.from({ length: max - min + 1 }, (_, index) => min + index);
  function apply() {
    if (start === '' || end === '') {
      setErrors({ start: start === '', end: end === '', message: 'Choose both values' });
      return;
    }
    if (Number(start) > Number(end)) {
      setErrors({ start: false, end: true, message: 'Range order' });
      return;
    }
    setErrors({ start: false, end: false, message: '' });
    onApply({ start: Number(start), end: Number(end) });
  }
  return <section data-testid="panel" style={{ backgroundColor: '#f2f6fc', color: '#1d3150', padding: 16, display: 'grid', gap: 8 }}>
    <form aria-label="Range pair" onSubmit={event => { event.preventDefault(); apply(); }}>
      <label>Start<select value={start} aria-invalid={errors.start || undefined} onChange={event => setStart(event.currentTarget.value)}><option value="">Choose</option>{values.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
      <label>End<select value={end} aria-invalid={errors.end || undefined} onChange={event => setEnd(event.currentTarget.value)}><option value="">Choose</option>{values.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
      <button type="submit">Apply</button>
    </form>
    {errors.message && <p role="alert">{errors.message}</p>}
  </section>;
}

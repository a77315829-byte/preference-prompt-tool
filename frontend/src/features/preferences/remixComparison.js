export function compareRemixAxes(before, after) {
  const old = new Map(before.map((a) => [a.axis, a]));
  const next = new Map(after.map((a) => [a.axis, a]));
  return [...new Set([...old.keys(), ...next.keys()])].map((axis) => {
    const previous = old.get(axis);
    const current = next.get(axis);
    const complete = previous && current && typeof previous.value === 'string' && typeof current.value === 'string'
      && ['personal', 'team', 'shared'].includes(previous.source) && ['personal', 'team', 'shared'].includes(current.source);
    const status = !complete ? 'unknown' : previous.value !== current.value ? 'changed'
      : previous.source !== current.source ? 'source' : 'same';
    return { axis, label: current?.label || previous?.label || axis, before: previous, after: current, status };
  });
}

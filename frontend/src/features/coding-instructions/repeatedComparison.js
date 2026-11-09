export function comparisonSummary(pairs, answers, { allowSingle = false } = {}) {
  return Object.fromEntries([...new Set(pairs.map(pair => pair.axis))].map(axis => {
    const rounds = pairs.filter(pair => pair.axis === axis && Object.hasOwn(answers, pair.id));
    const values = rounds.map(pair => answers[pair.id]).filter(value => value !== null);
    const consistent = values.length >= 2 && new Set(values).size === 1;
    const single = allowSingle && values.length === 1;
    return [axis, { answered: values.length, total: rounds.length, consistent,
      value: consistent || single ? values[0] : null, status: consistent ? 'consistent' : new Set(values).size > 1 ? 'mixed' : single ? 'single' : 'unresolved' }];
  }));
}

export function comparisonSequence(examples, answers) {
  if (examples.version !== 3 || !examples.pairs.every(pair => Object.hasOwn(answers, pair.id))) return examples.pairs;
  const unresolved = Object.entries(comparisonSummary(examples.pairs, answers)).filter(([, value]) => !value.consistent).slice(0, 2).map(([axis]) => axis);
  return [...examples.pairs, ...examples.followups.filter(pair => unresolved.includes(pair.axis))];
}

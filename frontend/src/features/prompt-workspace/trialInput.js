// 간단한 업무 입력은 폼으로 보여 주고, 복잡하거나 잘못된 입력은 JSON 편집으로 남긴다.
export function readTrialInput(text, variables) {
  try {
    const values = JSON.parse(text);
    if (!values || typeof values !== 'object' || Array.isArray(values) || !variables.length) return null;
    const types = { string: 'string', number: 'number', integer: 'number', boolean: 'boolean' };
    return variables.every((v) => Object.hasOwn(types, v.type)
      && (values[v.name] == null || typeof values[v.name] === types[v.type])) ? values : null;
  } catch {
    return null;
  }
}

export function updateTrialInput(text, name, value) {
  const values = { ...JSON.parse(text), [name]: value };
  if (value === null) delete values[name];
  return JSON.stringify(values, null, 2);
}

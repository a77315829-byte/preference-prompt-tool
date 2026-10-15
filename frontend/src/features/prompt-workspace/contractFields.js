// 입력 변수 타입과 출력 계약을 화면에서 다루는 순수 함수.
// 출력 계약 규칙은 서버(prompt_workspace/models.py validate_contract_fields)와 같게 미리
// 알려 줄 뿐이고, 최종 판단은 서버가 한다.

export const FIELD_TYPES = ['string', 'number', 'integer', 'boolean', 'array', 'object'];
export const PRIMITIVE_TYPES = ['string', 'number', 'integer', 'boolean'];
// 목록 안 항목이 이름 붙은 칸 여러 개로 된 묶음일 때 (서버 형식의 item_fields).
export const OBJECT_ITEMS = 'fields';
export const MAX_FIELDS = 30;
export const MAX_DESCRIPTION = 1000;

export const TYPE_LABEL = {
  string: '글자',
  number: '숫자',
  integer: '정수',
  boolean: '예/아니오',
  array: '목록',
  object: '묶음',
};

// 선택지 표시: 한국어 뒤에 원래 이름을 남긴다 - 개발자는 그 이름으로 코드를 짠다.
export const typeLabel = (type) => (TYPE_LABEL[type] ? `${TYPE_LABEL[type]} (${type})` : type);

const NAME = /^[a-z_][a-z0-9_]{0,39}$/;
export const isValidName = (name) => typeof name === 'string' && NAME.test(name);

export function nextFieldName(fields) {
  const used = new Set(fields.map((f) => f.name));
  let n = fields.length + 1;
  while (used.has(`field_${n}`)) n += 1;
  return `field_${n}`;
}

export const newField = (fields) => ({ name: nextFieldName(fields), type: 'string', required: true, description: '' });

// 타입을 바꾸면 그 타입에만 있는 칸을 정리한다. 목록이 되면 기본으로 글자 목록.
export function withType(field, type) {
  const next = { ...field, type };
  if (type === 'array') {
    if (!next.item_type && !next.item_fields) next.item_type = 'string';
  } else {
    delete next.item_type;
    delete next.item_fields;
    delete next.min_items;
    delete next.max_items;
  }
  return next;
}

export const itemKindOf = (field) => (field.item_fields ? OBJECT_ITEMS : field.item_type || 'string');

export function withItemKind(field, kind) {
  const next = { ...field };
  if (kind === OBJECT_ITEMS) {
    delete next.item_type;
    next.item_fields = field.item_fields || [newField([])];
  } else {
    delete next.item_fields;
    next.item_type = kind;
  }
  return next;
}

// 개수 칸 입력. 비우면 제한 없음. 숫자로 읽히지 않으면 제한을 두지 않는다.
export function withBound(field, key, text) {
  const next = { ...field };
  const trimmed = String(text ?? '').trim();
  const value = Number(trimmed);
  if (trimmed === '' || Number.isNaN(value)) delete next[key];
  else next[key] = value;
  return next;
}

// 사람이 읽는 한 줄 설명. 예: "글자", "글자 목록", "목록 - 한 줄에 service·amount".
export function fieldSummary(field) {
  if (field.type !== 'array') return TYPE_LABEL[field.type] || field.type;
  if (field.item_fields) return `목록 - 한 줄에 ${field.item_fields.map((f) => f.name).join('·')}`;
  return `${TYPE_LABEL[field.item_type] || field.item_type} 목록`;
}

const isObject = (value) => Boolean(value) && typeof value === 'object' && !Array.isArray(value);

// JSON 으로 붙여 넣은 값이 표로 그릴 수 있는 모양인지. 문제가 있으면 그 문장, 없으면 ''.
// 이름·타입 같은 내용 검사는 contractProblems 가 한다.
export function contractShapeError(fields) {
  if (!Array.isArray(fields)) return '항목 목록([ ... ])이어야 합니다.';
  for (const [i, field] of fields.entries()) {
    if (!isObject(field)) return `${i + 1}번째 항목이 { ... } 객체가 아닙니다.`;
    if (field.item_fields !== undefined) {
      const inner = contractShapeError(field.item_fields);
      if (inner) return `${i + 1}번째 항목의 item_fields: ${inner}`;
    }
  }
  return '';
}

// 서버가 거부할 내용을 미리 찾는다. 문장 목록 (없으면 빈 목록).
export function contractProblems(fields, { nested = false, parent = '' } = {}) {
  const problems = [];
  const shape = contractShapeError(fields);
  if (shape) return [`${parent}${shape}`];
  if (fields.length > MAX_FIELDS) problems.push(`${parent || '출력 계약'}: 항목은 ${MAX_FIELDS}개까지입니다.`);
  const seen = new Set();
  fields.forEach((field, i) => {
    const where = `${parent}${isValidName(field.name) ? `'${field.name}'` : `${i + 1}번째 항목`}`;
    if (!isValidName(field.name)) {
      problems.push(`${where}: 이름은 영문 소문자나 _ 로 시작하고 영문 소문자·숫자·_ 만 씁니다 (40자 이내).`);
    } else if (seen.has(field.name)) {
      problems.push(`${where}: 같은 이름이 두 번 있습니다.`);
    }
    seen.add(field.name);
    const allowed = nested ? PRIMITIVE_TYPES : FIELD_TYPES;
    if (!allowed.includes(field.type)) {
      problems.push(`${where}: 타입은 ${allowed.map((t) => TYPE_LABEL[t]).join('·')} 중 하나여야 합니다.`);
      return;
    }
    if (typeof field.required !== 'boolean') {
      problems.push(`${where}: 필수 여부(required)를 true 나 false 로 정해 주세요.`);
    }
    if ((field.description || '').length > MAX_DESCRIPTION) {
      problems.push(`${where}: 설명은 ${MAX_DESCRIPTION}자 이내여야 합니다.`);
    }
    if (field.type !== 'array') return;
    if (field.item_fields) {
      problems.push(...contractProblems(field.item_fields, { nested: true, parent: `${where} 안의 ` }));
    } else if (!PRIMITIVE_TYPES.includes(field.item_type)) {
      problems.push(`${where}: 목록 안 항목의 타입을 골라 주세요.`);
    }
    const bounds = { min_items: '최소 개수', max_items: '최대 개수' };
    Object.entries(bounds).forEach(([key, label]) => {
      const value = field[key];
      if (value !== undefined && value !== null && !(Number.isInteger(value) && value >= 0)) {
        problems.push(`${where}: ${label}는 0 이상의 정수여야 합니다.`);
      }
    });
    if (Number.isInteger(field.min_items) && Number.isInteger(field.max_items) && field.min_items > field.max_items) {
      problems.push(`${where}: 최소 개수가 최대 개수보다 큽니다.`);
    }
  });
  return problems;
}

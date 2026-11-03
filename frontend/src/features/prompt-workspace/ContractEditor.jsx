import { Fragment } from 'react';
import {
  FIELD_TYPES, MAX_DESCRIPTION, MAX_FIELDS, OBJECT_ITEMS, PRIMITIVE_TYPES, TYPE_LABEL,
  itemKindOf, newField, typeLabel, withBound, withItemKind, withType,
} from './contractFields';

// 출력 계약을 표로 고친다. 목록(array) 항목은 아래 줄에서 안쪽 항목을 정하고, 안쪽이
// 여러 칸 묶음이면 같은 표를 한 단계만 더 연다 (서버 형식이 한 단계까지다).
function ContractEditor({ fields, onChange, nested = false, parentLabel = '' }) {
  const types = nested ? PRIMITIVE_TYPES : FIELD_TYPES;
  const update = (index, next) => onChange(fields.map((f, i) => (i === index ? next : f)));
  const remove = (index) => onChange(fields.filter((_, i) => i !== index));
  const label = (field, index) => `${parentLabel}${field.name || `${index + 1}번째 항목`}`;

  return (
    <div className={nested ? 'ws-contract ws-contract-nested' : 'ws-contract'}>
      {fields.length > 0 && (
        <table className="ws-table">
          <thead><tr><th>이름</th><th>타입</th><th>필수</th><th>설명</th><th /></tr></thead>
          <tbody>
            {fields.map((field, index) => (
              <Fragment key={index}>
                <tr>
                  <td>
                    <input className="ws-cell-input ws-code" aria-label={`${label(field, index)} 이름`} value={field.name}
                      maxLength={40} onChange={(e) => update(index, { ...field, name: e.target.value })} />
                  </td>
                  <td>
                    <select aria-label={`${label(field, index)} 타입`} value={field.type}
                      onChange={(e) => update(index, withType(field, e.target.value))}>
                      {types.map((t) => <option key={t} value={t}>{typeLabel(t)}</option>)}
                    </select>
                  </td>
                  <td>
                    <input type="checkbox" aria-label={`${label(field, index)} 필수`} checked={Boolean(field.required)}
                      onChange={(e) => update(index, { ...field, required: e.target.checked })} />
                  </td>
                  <td>
                    <input className="ws-cell-input" aria-label={`${label(field, index)} 설명`} value={field.description || ''}
                      maxLength={MAX_DESCRIPTION} placeholder="무엇을 담는 칸인지"
                      onChange={(e) => update(index, { ...field, description: e.target.value })} />
                  </td>
                  <td>
                    <button className="ws-small-button" type="button" aria-label={`${label(field, index)} 삭제`}
                      onClick={() => remove(index)}>삭제</button>
                  </td>
                </tr>
                {field.type === 'object' && (
                  <tr className="ws-contract-sub">
                    <td colSpan={5}><span className="ws-help">묶음은 안쪽 모양을 검사하지 않습니다. 칸을 정하려면 목록 + 여러 칸 묶음을 쓰세요.</span></td>
                  </tr>
                )}
                {field.type === 'array' && (
                  <tr className="ws-contract-sub">
                    <td colSpan={5}>
                      <div className="ws-contract-list">
                        <span>목록 안 항목</span>
                        <select aria-label={`${label(field, index)} 목록 안 항목`} value={itemKindOf(field)}
                          onChange={(e) => update(index, withItemKind(field, e.target.value))}>
                          {PRIMITIVE_TYPES.map((t) => <option key={t} value={t}>{typeLabel(t)}</option>)}
                          <option value={OBJECT_ITEMS}>여러 칸 묶음 (한 줄에 여러 값)</option>
                        </select>
                        <span>개수</span>
                        <input className="ws-cell-input ws-count" type="number" min={0} step={1} placeholder="최소"
                          aria-label={`${label(field, index)} 최소 개수`} value={field.min_items ?? ''}
                          onChange={(e) => update(index, withBound(field, 'min_items', e.target.value))} />
                        <span>~</span>
                        <input className="ws-cell-input ws-count" type="number" min={0} step={1} placeholder="최대"
                          aria-label={`${label(field, index)} 최대 개수`} value={field.max_items ?? ''}
                          onChange={(e) => update(index, withBound(field, 'max_items', e.target.value))} />
                        <span className="ws-help">비우면 제한 없음</span>
                      </div>
                      {field.item_fields && (
                        <ContractEditor nested fields={field.item_fields} parentLabel={`${label(field, index)} 안의 `}
                          onChange={(sub) => update(index, { ...field, item_fields: sub })} />
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      )}
      {fields.length === 0 && <p className="ws-help">{nested ? '칸이 없습니다.' : '정한 항목이 없습니다.'}</p>}
      <button className="ws-small-button ws-contract-add" type="button" disabled={fields.length >= MAX_FIELDS}
        onClick={() => onChange([...fields, newField(fields)])}>
        {nested ? '+ 칸 추가' : '+ 항목 추가'}
      </button>
      {!nested && (
        <p className="ws-help">
          타입: {FIELD_TYPES.map((t) => TYPE_LABEL[t]).join(' · ')}. 이름은 앱 코드가 결과를 꺼낼 때 쓰는 이름이라
          영문 소문자·숫자·_ 로 씁니다.
        </p>
      )}
    </div>
  );
}

export default ContractEditor;

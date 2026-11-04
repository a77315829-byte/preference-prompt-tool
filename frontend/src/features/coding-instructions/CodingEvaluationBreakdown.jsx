import { useState } from 'react';
import { CODING_CHOICES } from './codingOptions';

const CHECK_LABELS = { syntax: '코드 구문 구조', code_structure: 'Java 코드 구조', route: 'GET 경로 선언', binding: '환경·입력 연결', validation: '입력 제한', calculation: '출력·반환 계산식' };
const number = value => Number(value.toFixed(2)).toString();

function count(tasks, group, key) {
  const values = tasks.map(task => task[group]?.[key]);
  const known = values.filter(value => typeof value === 'boolean').length;
  return { passed: values.filter(value => value === true).length, known, total: tasks.length };
}
function countText(value) {
  return !value.known ? '기록 없음' : `${value.passed}/${value.total}개 확인${value.known < value.total ? ' · 일부 미기록' : ''}`;
}
function totals(tasks, group, keys) {
  const counts = keys.map(key => count(tasks, group, key));
  return counts.reduce((sum, value) => ({ passed: sum.passed + value.passed, known: sum.known + value.known, total: sum.total + value.total }), { passed: 0, known: 0, total: 0 });
}
function points(batch, rules) {
  const keys = Object.keys(rules?.checks || {});
  const preferenceKeys = rules?.preference_keys || Object.keys(CODING_CHOICES);
  if (!batch?.tasks?.length || keys.length !== 4 || !Number.isFinite(rules.function_weight) || !Number.isFinite(rules.preference_weight)) return null;
  let functionality = 0, preference = 0;
  for (const task of batch.tasks) {
    if (!keys.every(key => typeof task.checks?.[key] === 'boolean') || !preferenceKeys.every(key => typeof task.preferences?.[key] === 'boolean')) return null;
    if (task.checks[rules.gate]) {
      functionality += keys.filter(key => task.checks[key]).length / 4 * rules.function_weight * 100;
      preference += preferenceKeys.filter(key => task.preferences[key]).length / preferenceKeys.length * rules.preference_weight * 100;
    }
  }
  functionality /= batch.tasks.length; preference /= batch.tasks.length;
  if (Math.abs((functionality + preference) / 100 - batch.score) > .0002) return null;
  return { functionality, preference, total: functionality + preference };
}

export default function CodingEvaluationBreakdown({ result }) {
  const { report, profile } = result;
  const [scope, setScope] = useState('holdout');
  const before = scope === 'holdout' ? report.holdout_before : report.validation_before_details;
  const after = scope === 'holdout' ? report.holdout_after : report.validation_after_details;
  const beforeTasks = before?.tasks || [], afterTasks = after?.tasks || [];
  const rules = report.scoring;
  const manualKeys = rules?.manual_preferences || [];
  const automaticKeys = rules?.preference_keys || Object.keys(CODING_CHOICES);
  const checkKeys = Object.keys(rules?.checks || beforeTasks[0]?.checks || {});
  const beforeFunctions = totals(beforeTasks, 'checks', checkKeys), afterFunctions = totals(afterTasks, 'checks', checkKeys);
  const beforePreferences = totals(beforeTasks, 'preferences', automaticKeys), afterPreferences = totals(afterTasks, 'preferences', automaticKeys);
  const beforePoints = points(before, rules), afterPoints = points(after, rules);
  const holdoutDelta = report.holdout_after.score - report.holdout_before.score;
  const improved = result.changed && holdoutDelta > 0;
  return <section className="coding-evaluation" aria-labelledby="coding-evaluation-title">
    <h4 id="coding-evaluation-title">내가 고른 방식이 얼마나 확인됐나요?</h4>
    <div className={`fastapi-gepa-outcome coding-evaluation-verdict ${improved ? 'is-positive' : 'is-neutral'}`} role="status">
      <strong>{improved ? '별도 과제의 자동 검사에서 상승' : '이번 시도에서 추가 개선 확인 안 됨'}</strong>
      <p>{!result.changed ? '더 나은 후보를 찾지 못해 원본을 유지했어요. 아래 전후 결과는 같은 원본 기준이며, 탈락한 후보의 점수가 아니에요.'
        : holdoutDelta < 0 ? '후보 선택 과제에서는 올랐지만 별도 과제에서는 낮아졌어요. 원본 유지를 권하며 실제 답변을 비교해 주세요.'
          : holdoutDelta === 0 ? '후보 선택 과제에서는 올랐지만 별도 과제에서는 같아요. 전반적인 개선 효과는 아직 확인하지 못했어요.'
            : '준비된 별도 과제의 검사 결과예요. 실제 사용에서도 더 편한지는 답변을 직접 비교해 주세요.'}</p>
    </div>
    <div className="coding-evaluation-tabs" role="group" aria-label="항목별 검사에 사용할 과제">
      <button className="coding-secondary-button" type="button" aria-pressed={scope === 'holdout'} onClick={() => setScope('holdout')}>별도 확인 과제 {report.holdout_tasks}개</button>
      <button className="coding-secondary-button" type="button" aria-pressed={scope === 'validation'} onClick={() => setScope('validation')}>후보 선택 과제 {report.validation_tasks}개</button>
    </div>
    <p className="ws-help">{scope === 'holdout' ? '후보를 고르는 데 쓰지 않은 과제로 확인했어요.' : 'GEPA가 후보를 고를 때 참고한 과제예요. 독립적인 개선 증거로 보지 않아요.'} 각 항목의 ‘확인’은 자동 검사 기준 충족을 뜻해요.</p>
    {manualKeys.length > 0 && <p className="coding-review-support">평가 기준 v2 · 제목의 단계 번호도 인식해요. 주석·역할 구성은 직접 확인하며 자동 점수에서 제외합니다. 아래 ‘별도 과제의 실제 AI 답변도 비교하기’를 펼쳐 확인해 주세요. 이전 v1의 74점 등과 새 점수를 직접 비교해 개선됐다고 해석하지 않습니다.</p>}
    {!beforeTasks.length || !afterTasks.length ? <p className="ws-help">이 기록에는 이 과제의 항목별 검사 내역이 없어요. 과거 점수에서 반영 여부를 추측하지 않습니다.</p> : <>
      <div className="coding-evaluation-overview">
        <div><span>기능 정적 검사</span><strong>{countText(beforeFunctions)} → {countText(afterFunctions)}</strong><small>코드를 실행해 검증한 결과는 아니에요.</small></div>
        <div><span>내 답변 방식 · 과제별 자동 {automaticKeys.length}항목</span><strong>{countText(beforePreferences)} → {countText(afterPreferences)}</strong><small>{manualKeys.length ? '주석·역할 구성은 이 합계에 넣지 않아요. 실제 답변으로 직접 확인해 주세요.' : '미확인은 아래 기준을 못 찾았거나 검사할 수 없었던 항목이에요.'}</small></div>
      </div>
      <div className="coding-evaluation-table-wrap"><table className="coding-evaluation-table" aria-label="선택한 답변 방식별 전후 확인 결과">
        <thead><tr><th scope="col">내가 고른 답변 방식</th><th scope="col">이전</th><th scope="col">{result.changed ? '후보' : '원본 유지 후'}</th><th scope="col">변화</th></tr></thead>
        <tbody>{Object.entries(CODING_CHOICES).map(([key, field]) => {
          const a = count(beforeTasks, 'preferences', key), b = count(afterTasks, 'preferences', key);
          const manual = manualKeys.includes(key);
          const complete = a.known === a.total && b.known === b.total;
          const delta = b.passed - a.passed;
          return <tr key={key}><th scope="row">{field.label}<small>{field.options[profile.preferences[key]]}</small></th>
            <td><span className={manual ? 'is-manual' : a.passed === a.total && complete ? 'is-confirmed' : 'is-unconfirmed'}>{manual ? '직접 확인' : countText(a)}</span></td>
            <td><span className={manual ? 'is-manual' : b.passed === b.total && complete ? 'is-confirmed' : 'is-unconfirmed'}>{manual ? '직접 확인' : countText(b)}</span></td>
            <td>{manual ? '자동 점수 제외' : !complete ? '기록 부족' : delta > 0 ? '확인 증가' : delta < 0 ? '확인 감소' : b.passed === b.total ? '유지' : '추가 확인 필요'}</td></tr>;
        })}</tbody></table></div>
      <p className="ws-help">‘확인 못함’이 곧 선호 미반영이라는 뜻은 아니에요. 자동 검사는 설명·출력의 형식 단서만 확인하므로, 실제로 반영된 표현도 놓칠 수 있어요. 주석과 역할의 적절함은 답변을 직접 읽어 주세요.</p>
      <details className="coding-evaluation-details"><summary>답변 방식의 검사 기준과 과제별 근거</summary>
        {Object.entries(CODING_CHOICES).map(([key, field]) => <div key={key} className="coding-evaluation-evidence"><h5>{field.label}</h5><p>{rules?.preferences?.[key] || '이전 기록에 상세 검사 기준이 보관되지 않았어요.'}</p>
          {beforeTasks.map(task => {
            const next = afterTasks.find(item => item.id === task.id);
            const status = (item) => manualKeys.includes(key) ? '사람이 직접 확인할 항목' : typeof item?.preferences?.[key] !== 'boolean' ? '미기록' : item.preferences[key] ? '기준 충족' : '기준 미충족 또는 검사 불가';
            return <div key={task.id}><strong>{task.label}</strong><p>이전: {status(task)} · {task.observations?.[key] || '세부 측정값 미기록'}</p><p>{result.changed ? '후보' : '원본 유지 후'}: {status(next)} · {next?.observations?.[key] || '세부 측정값 미기록'}</p></div>;
          })}</div>)}
      </details>
      <details className="coding-evaluation-details"><summary>기능 정적 검사 항목 보기</summary><ul>{checkKeys.map(key => <li key={key}><strong>{CHECK_LABELS[key] || key}</strong>: {countText(count(beforeTasks, 'checks', key))} → {countText(count(afterTasks, 'checks', key))}<p>{rules?.checks?.[key] || '세부 기준 미기록'}</p></li>)}</ul></details>
    </>}
    <details className="coding-evaluation-details coding-evaluation-score"><summary>참고 점수 · 계산 근거 보기</summary>
      <p>이 점수는 이 도구가 정한 제한된 자동 검사 지표예요. 성공률·만족도·일반적인 프롬프트 품질 점수가 아닙니다. 숫자가 같으면 점수 상승은 확인되지 않은 거예요.</p>
      <p>후보 선택 과제: {number(report.validation_before * 100)}점 → {number(report.validation_after * 100)}점<br />별도 확인 과제: {number(report.holdout_before.score * 100)}점 → {number(report.holdout_after.score * 100)}점</p>
      {rules ? <p>기능 정적 검사 {number(rules.function_weight * 100)}점(4항목) + 답변 방식 자동 검사 {number(rules.preference_weight * 100)}점({automaticKeys.length}항목). 각 묶음의 자동 검사 항목은 같은 비중으로 계산하고 과제별 점수를 평균 내요. {manualKeys.length > 0 && '주석·역할 구성은 자동 점수에서 제외하며 사람의 판단으로 점수를 바꾸지 않습니다. '}기본 코드 구조를 확인하지 못한 과제는 0점 처리해요. 이 비중이 사용자 만족도를 예측한다고 검증된 것은 아닙니다.</p> : <p>이전 기록에는 계산 비중과 상세 근거가 보관되지 않았어요. 기록된 점수만 표시합니다.</p>}
      {beforePoints && afterPoints && <div className="coding-evaluation-formula"><p>이전: 기능 {number(beforePoints.functionality)} + 답변 방식 {number(beforePoints.preference)} = <strong>{number(beforePoints.total)}점</strong></p>
        <p>{result.changed ? '후보' : '원본 유지 후'}: 기능 {number(afterPoints.functionality)} + 답변 방식 {number(afterPoints.preference)} = <strong>{number(afterPoints.total)}점</strong></p><p>{number(beforePoints.total)}점은 정수로 반올림하면 {Math.round(beforePoints.total)}점이에요. 여기서는 차이가 숨지 않도록 소수점도 표시해요.</p></div>}
      <p>{report.limitation} {report.preference_checks}</p>
    </details>
  </section>;
}

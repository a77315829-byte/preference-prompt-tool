// 두 글의 줄 단위 차이 (LCS). 프롬프트는 수백 줄을 넘지 않으므로 O(n·m) 로 충분하다.
// 결과: [{ type: 'same' | 'removed' | 'added', text }]
export function lineDiff(before, after) {
  const a = (before || '').split('\n');
  const b = (after || '').split('\n');
  const rows = a.length + 1;
  const cols = b.length + 1;
  const table = Array.from({ length: rows }, () => new Uint16Array(cols));
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      table[i][j] = a[i] === b[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }
  const out = [];
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      out.push({ type: 'same', text: a[i] });
      i += 1;
      j += 1;
    } else if (table[i + 1][j] >= table[i][j + 1]) {
      out.push({ type: 'removed', text: a[i] });
      i += 1;
    } else {
      out.push({ type: 'added', text: b[j] });
      j += 1;
    }
  }
  while (i < a.length) { out.push({ type: 'removed', text: a[i] }); i += 1; }
  while (j < b.length) { out.push({ type: 'added', text: b[j] }); j += 1; }
  return out;
}

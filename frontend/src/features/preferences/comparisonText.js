import { lineDiff } from '../prompt-workspace/lineDiff.js';

export function promptChanges(personal, team) {
  const before = personal.replace(/\r\n/g, '\n').trim();
  const after = team.replace(/\r\n/g, '\n').trim();
  // 자유 입력에 줄바꿈이 매우 많으면 LCS 표를 크게 만들지 않고 원문 두 묶음을 보여 준다.
  if (before.split('\n').length > 400 || after.split('\n').length > 400) {
    if (before === after) return [];
    return [{ type: 'removed', text: before }, { type: 'added', text: after }];
  }
  return lineDiff(before, after).filter((row) => row.type !== 'same' && row.text.trim());
}

export function selectionMatches(output, task, item, basis, comparison, draft) {
  return output && output.task === task && output.revision === item.revision
    && (output.basis || 'personal') === basis
    && (basis === 'personal' || output.team_snapshot === comparison?.team_snapshot)
    && (basis !== 'custom' || output.task_snapshot === draft?.snapshot);
}

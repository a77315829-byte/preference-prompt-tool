export const HANDOFF_STATUS = { draft: '작성 중', shared: '받을 팀원에게 공유됨', active: '이어서 진행 중', done: '완료' };
export const HANDOFF_EVENTS = { created: '처음 작성', update: '내용 저장', share: '공유 대상 지정', claim: '이어서 맡음', complete: '작업 완료', reopen: '다시 진행' };

async function call(path = '', body) {
  const response = await fetch(`/api/handoffs${path}`, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `인수인계 요청에 실패했습니다 (${response.status})`);
  return data;
}
export const listHandoffs = () => call().then((r) => r.handoffs);
export const getHandoff = (id) => call(`/${encodeURIComponent(id)}`).then((r) => r.handoff);
export const createHandoff = (body) => call('', body).then((r) => r.handoff);
export const changeHandoff = (item, action, body = {}) => call(`/${encodeURIComponent(item.id)}/${action}`, { ...body, revision: item.revision }).then((r) => r.handoff);
export const getHandoffHistory = (id) => call(`/${encodeURIComponent(id)}/history`).then((r) => r.history);
export const getHandoffVersion = (id, revision) => call(`/${encodeURIComponent(id)}/history/${revision}`).then((r) => r.snapshot);

export const handoffForm = (item) => ({ title: item?.title || '', purpose: item?.body?.purpose || '', progress: item?.body?.progress || '',
  remaining: item?.body?.remaining || '', references: (item?.body?.references || []).join('\n'), prompt: item?.body?.prompt || '' });
export const handoffBody = (form) => ({ ...form, references: form.references.split(/\r?\n/).map((s) => s.trim()).filter(Boolean) });
export function parseHandoffLink(value) {
  let id = String(value || '').trim();
  if (/^https?:\/\//i.test(id)) { try { id = new URL(id).searchParams.get('handoff') || ''; } catch { id = ''; } }
  if (!/^[a-f0-9]{32}$/.test(id)) throw new Error('받은 인수인계 링크 또는 작업 코드를 확인해 주세요.');
  return id;
}
export function handoffLink(id, pageUrl) {
  const url = new URL(pageUrl); url.search = ''; url.hash = ''; url.searchParams.set('handoff', parseHandoffLink(id)); return url.href;
}
export function continuationRequest(item) {
  const body = item.body;
  return `${body.prompt ? `${body.prompt.trim()}\n\n---\n` : ''}다음 인수인계 기록을 참고해 남은 작업을 이어서 도와주세요. 빠진 정보와 먼저 확인할 점을 밝혀 주세요.\n\n작업: ${item.title}\n\n작업 목적\n${body.purpose}\n\n어디까지 했는지\n${body.progress}\n\n남은 일\n${body.remaining}\n\n참고 파일 경로·링크\n${body.references.join('\n') || '아직 없음'}`;
}

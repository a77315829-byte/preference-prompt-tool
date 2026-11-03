export const LINEAGE_LABELS = { task: '원래 작업용', remix: '새 조합', restore: '선택 항목 되돌림', personal: '개인 지침', derived: '파생 조합' };

export function lineageOf(item) {
  if (item.lineage) return item.lineage;
  const origin = item.provenance;
  return { kind: origin?.operation || (origin?.remixed_from ? 'derived' : origin ? 'task' : 'personal'), parent: origin?.remixed_from || null };
}

export function lineageGroups(items, visibleIds = items.map((i) => i.id)) {
  const byId = new Map(items.map((item) => [item.id, item]));
  const parents = new Map();
  for (const item of items) {
    const id = lineageOf(item).parent?.id;
    if (!byId.has(id) || id === item.id) continue;
    const seen = new Set([item.id]);
    let cursor = id;
    while (cursor && !seen.has(cursor)) { seen.add(cursor); cursor = parents.get(cursor); }
    if (!cursor) parents.set(item.id, id);
  }
  const children = new Map(items.map((i) => [i.id, []]));
  for (const item of items) if (parents.has(item.id)) children.get(parents.get(item.id)).push(item);
  const ordered = (list) => [...list].sort((a, b) => a.created_at?.localeCompare(b.created_at || '') || a.id.localeCompare(b.id));
  const groups = [];
  for (const root of ordered(items.filter((i) => !parents.has(i.id)))) {
    const rows = [];
    const visit = (item, depth) => { rows.push({ item, depth }); for (const child of ordered(children.get(item.id))) visit(child, depth + 1); };
    visit(root, 0);
    if (rows.some(({ item }) => visibleIds.includes(item.id))) groups.push(rows);
  }
  return groups;
}

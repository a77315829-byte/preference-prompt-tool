'use strict';

// Acceptance harness only. Candidates cannot read this file through the evaluator loader.
const assert = require('node:assert/strict');
const { JSDOM } = require('../../frontend/node_modules/jsdom');
let dom;
let savedGlobals;
const globalNames = ['window', 'document', 'navigator', 'HTMLElement', 'HTMLInputElement', 'HTMLSelectElement', 'HTMLTextAreaElement', 'Event', 'MouseEvent', 'KeyboardEvent', 'Node', 'IS_REACT_ACT_ENVIRONMENT'];

function installDom() {
  if (dom) return dom.window;
  dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://benchmark.invalid/' });
  savedGlobals = new Map(globalNames.map(name => [name, Object.getOwnPropertyDescriptor(globalThis, name)]));
  for (const name of globalNames) {
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value: name === 'IS_REACT_ACT_ENVIRONMENT' ? true : name === 'window' ? dom.window : name === 'document' ? dom.window.document : dom.window[name] });
  }
  return dom.window;
}

function cleanupDom() {
  if (!dom) return;
  dom.window.close();
  for (const [name, descriptor] of savedGlobals) {
    if (descriptor) Object.defineProperty(globalThis, name, descriptor);
    else delete globalThis[name];
  }
  dom = null;
}

function normalized(value) { return String(value ?? '').replace(/\s+/g, ' ').trim(); }
function accessibleName(element) {
  if (element.hasAttribute('aria-label')) return normalized(element.getAttribute('aria-label'));
  if (element.hasAttribute('aria-labelledby')) return normalized(element.getAttribute('aria-labelledby').split(/\s+/).map(id => element.ownerDocument.getElementById(id)?.textContent ?? '').join(' '));
  if (element.labels?.length) return normalized(Array.from(element.labels).map(label => label.textContent).join(' '));
  return normalized(element.textContent);
}
function findNamed(container, selector, name) {
  const found = Array.from(container.querySelectorAll(selector)).filter(node => accessibleName(node) === name);
  assert.equal(found.length, 1, `Expected one ${selector} named "${name}", found ${found.length}`);
  return found[0];
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function makeHarness(Component) {
  const React = require('../../frontend/node_modules/react');
  const { createRoot } = require('../../frontend/node_modules/react-dom/client');
  const container = document.createElement('div');
  document.body.append(container);
  const root = createRoot(container);
  const h = {
    container,
    mount: async props => { await React.act(async () => { root.render(React.createElement(Component, props)); }); },
    render: async element => { await React.act(async () => { root.render(element); }); },
    unmount: async () => { await React.act(async () => root.unmount()); container.remove(); },
    input: name => findNamed(container, 'input,textarea,select', name),
    button: name => findNamed(container, 'button', name),
    output: name => findNamed(container, 'output', name),
    list: name => Array.from(findNamed(container, 'ul', name).querySelectorAll('li')).map(node => normalized(node.textContent)),
    text: () => normalized(container.textContent),
    role: role => Array.from(container.querySelectorAll(`[role="${role}"]`)),
    click: async element => { await React.act(async () => element.click()); },
    fill: async (name, value) => {
      const input = h.input(name);
      const prototype = input.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : input.tagName === 'SELECT' ? window.HTMLSelectElement.prototype : window.HTMLInputElement.prototype;
      await React.act(async () => {
        Object.getOwnPropertyDescriptor(prototype, 'value').set.call(input, value);
        input.dispatchEvent(new window.Event('input', { bubbles: true }));
        input.dispatchEvent(new window.Event('change', { bubbles: true }));
      });
    },
    submit: async () => { await React.act(async () => {
      const form = container.querySelector('form');
      assert.ok(form, 'Expected a form');
      const allowed = form.dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
      assert.equal(allowed, false, 'Submit must prevent navigation');
    }); },
    key: async (element, key) => {
      let event;
      await React.act(async () => { element.focus(); event = new window.KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }); element.dispatchEvent(event); });
      return event;
    },
    settle: async callback => { await React.act(async () => { callback(); await Promise.resolve(); }); },
  };
  return h;
}

const suites = {};
function rosterTests() {
  const rows = [{ id: 'u7', name: 'Alice', team: 'Design' }, { id: 'u2', name: 'Bob', team: 'Platform' }, { id: 'u9', name: 'Caroline', team: 'Support' }];
  async function setup(h) { const calls = []; await h.mount({ rows, onSelectionChange: ids => calls.push([...ids]) }); return calls; }
  return [
    { name: 'initial_table_unselected_without_callback', run: async h => { const calls = await setup(h); assert.ok(h.container.querySelector('table')); const headings = Array.from(h.container.querySelectorAll('th')).map(node => normalized(node.textContent)); assert.ok(headings.includes('Name') && headings.includes('Team')); assert.equal(h.container.querySelectorAll('tbody tr').length, 3); assert.equal(h.output('Selected count').textContent, '0'); for (const row of rows) { assert.equal(h.input(`Select ${row.name}`).type, 'checkbox'); assert.equal(h.input(`Select ${row.name}`).checked, false); } assert.deepEqual(calls, []); } },
    { name: 'toggle_reports_stable_ids_once_and_deselects', run: async h => { const calls = await setup(h); await h.click(h.input('Select Bob')); assert.deepEqual(calls, [['u2']]); assert.equal(h.input('Select Bob').checked, true); await h.click(h.input('Select Bob')); assert.deepEqual(calls, [['u2'], []]); assert.equal(h.output('Selected count').textContent, '0'); } },
    { name: 'search_normalizes_case_and_whitespace', run: async h => { const calls = await setup(h); await h.fill('Search members', '  ALI  '); assert.equal(h.container.querySelectorAll('tbody tr').length, 1); assert.ok(h.input('Select Alice')); assert.deepEqual(calls, []); } },
    { name: 'hidden_selection_is_retained', run: async h => { const calls = await setup(h); await h.click(h.input('Select Bob')); await h.fill('Search members', 'Alice'); assert.equal(h.input('Select Alice').checked, false); assert.equal(h.output('Selected count').textContent, '1'); await h.fill('Search members', ''); assert.equal(h.input('Select Bob').checked, true); assert.equal(calls.length, 1); } },
    { name: 'reordered_new_row_objects_keep_identity', run: async h => { const calls = await setup(h); await h.click(h.input('Select Alice')); await h.mount({ rows: [rows[2], rows[0], rows[1]].map(row => ({ ...row })), onSelectionChange: ids => calls.push([...ids]) }); assert.equal(h.input('Select Alice').checked, true); assert.equal(h.input('Select Caroline').checked, false); assert.deepEqual(calls, [['u7']]); } },
    { name: 'select_visible_preserves_hidden_selection_and_order', run: async h => { const calls = await setup(h); await h.click(h.input('Select Bob')); await h.fill('Search members', 'ali'); await h.click(h.button('Select visible')); assert.deepEqual(calls, [['u2'], ['u2', 'u7']]); assert.equal(h.output('Selected count').textContent, '2'); } },
    { name: 'clear_visible_keeps_hidden_ids', run: async h => { const calls = await setup(h); await h.click(h.button('Select visible')); await h.fill('Search members', 'bo'); await h.click(h.button('Clear visible')); assert.deepEqual(calls, [['u7', 'u2', 'u9'], ['u7', 'u9']]); assert.equal(h.input('Select Bob').checked, false); assert.equal(h.output('Selected count').textContent, '2'); } },
    { name: 'repeated_bulk_selection_has_no_duplicate_ids', run: async h => { const calls = await setup(h); await h.click(h.button('Select visible')); await h.click(h.button('Select visible')); assert.deepEqual(calls, [['u7', 'u2', 'u9'], ['u7', 'u2', 'u9']]); assert.equal(h.output('Selected count').textContent, '3'); } },
    { name: 'empty_search_disables_bulk_actions', run: async h => { const calls = await setup(h); await h.fill('Search members', 'Nobody'); assert.equal(h.container.querySelectorAll('tbody tr').length, 0); assert.equal(h.button('Select visible').disabled, true); assert.equal(h.button('Clear visible').disabled, true); assert.ok(h.role('status').some(node => normalized(node.textContent) === 'No members')); assert.deepEqual(calls, []); } },
  ];
}
suites.roster_selection = rosterTests();
function reservationTests() {
  async function setup(h, capacity = 4) { const calls = []; await h.mount({ capacity, onReserve: value => calls.push({ ...value }) }); return calls; }
  async function enter(h, start = '2027-02-11', end = '2027-02-14', guests = '2') { await h.fill('Start date', start); await h.fill('End date', end); await h.fill('Guests', guests); }
  function invalid(h, name) { assert.equal(h.input(name).getAttribute('aria-invalid'), 'true', `${name} must be marked invalid`); assert.ok(h.role('alert').some(node => normalized(node.textContent).length > 0)); }
  return [
    { name: 'initial_fields_empty_and_no_callback', run: async h => { const calls = await setup(h); assert.ok(findNamed(h.container, 'form', 'Reservation')); for (const name of ['Start date', 'End date', 'Guests']) { assert.equal(h.input(name).value, ''); assert.equal(h.input(name).type, name === 'Guests' ? 'number' : 'date'); } assert.equal(h.button('Reserve').type, 'submit'); assert.deepEqual(calls, []); } },
    { name: 'empty_submit_marks_all_required_fields', run: async h => { const calls = await setup(h); await h.submit(); for (const name of ['Start date', 'End date', 'Guests']) invalid(h, name); assert.deepEqual(calls, []); } },
    { name: 'same_day_end_is_rejected', run: async h => { const calls = await setup(h); await enter(h, '2027-02-11', '2027-02-11'); await h.submit(); invalid(h, 'End date'); assert.deepEqual(calls, []); } },
    { name: 'earlier_end_is_rejected', run: async h => { const calls = await setup(h); await enter(h, '2027-02-11', '2027-02-10'); await h.submit(); invalid(h, 'End date'); assert.deepEqual(calls, []); } },
    { name: 'zero_negative_and_fractional_guests_rejected', run: async h => { const calls = await setup(h); await enter(h); for (const value of ['0', '-1', '1.5']) { await h.fill('Guests', value); await h.submit(); invalid(h, 'Guests'); } assert.deepEqual(calls, []); } },
    { name: 'over_capacity_rejected', run: async h => { const calls = await setup(h, 3); await enter(h, undefined, undefined, '4'); await h.submit(); invalid(h, 'Guests'); assert.deepEqual(calls, []); } },
    { name: 'capacity_boundary_is_valid_and_payload_numeric', run: async h => { const calls = await setup(h, 4); await enter(h, undefined, undefined, '4'); await h.submit(); assert.deepEqual(calls, [{ start: '2027-02-11', end: '2027-02-14', guests: 4 }]); assert.equal(h.input('Guests').value, '4'); assert.equal(h.role('alert').length, 0); } },
    { name: 'latest_capacity_used_after_parent_update', run: async h => { const calls = await setup(h, 5); await enter(h, undefined, undefined, '4'); await h.mount({ capacity: 2, onReserve: value => calls.push({ ...value }) }); await h.submit(); invalid(h, 'Guests'); assert.deepEqual(calls, []); } },
    { name: 'corrected_submission_clears_errors_and_keeps_fields', run: async h => { const calls = await setup(h); await h.submit(); await enter(h, '2028-12-31', '2029-01-01', '1'); await h.submit(); assert.deepEqual(calls, [{ start: '2028-12-31', end: '2029-01-01', guests: 1 }]); assert.equal(h.role('alert').length, 0); for (const name of ['Start date', 'End date', 'Guests']) assert.notEqual(h.input(name).getAttribute('aria-invalid'), 'true'); assert.equal(h.input('Start date').value, '2028-12-31'); assert.equal(h.input('End date').value, '2029-01-01'); } },
  ];
}
suites.reservation_validation = reservationTests();
function favoriteTests() {
  async function setup(h, initialValue = false) { const calls = []; const jobs = []; await h.mount({ initialValue, save: value => { calls.push(value); const job = deferred(); jobs.push(job); return job.promise; } }); return { calls, jobs }; }
  function pressed(h, value) { assert.equal(h.button('Favorite').getAttribute('aria-pressed'), String(value)); }
  return [
    { name: 'initial_boolean_rendered_without_save', run: async h => { const state = await setup(h, true); pressed(h, true); assert.equal(h.button('Favorite').disabled, false); assert.deepEqual(state.calls, []); assert.equal(h.role('status').length, 0); } },
    { name: 'click_optimistically_updates_before_settlement', run: async h => { const state = await setup(h); await h.click(h.button('Favorite')); pressed(h, true); assert.deepEqual(state.calls, [true]); assert.equal(h.button('Favorite').disabled, true); assert.ok(h.role('status').some(node => normalized(node.textContent) === 'Saving')); await h.settle(state.jobs[0].resolve); } },
    { name: 'pending_clicks_cannot_duplicate_save', run: async h => { const state = await setup(h); await h.click(h.button('Favorite')); await h.click(h.button('Favorite')); await h.click(h.button('Favorite')); assert.deepEqual(state.calls, [true]); await h.settle(state.jobs[0].resolve); } },
    { name: 'success_commits_value_and_reenables_button', run: async h => { const state = await setup(h); await h.click(h.button('Favorite')); await h.settle(state.jobs[0].resolve); pressed(h, true); assert.equal(h.button('Favorite').disabled, false); assert.equal(h.role('status').length, 0); assert.equal(h.role('alert').length, 0); } },
    { name: 'rejection_rolls_back_false_initial_value', run: async h => { const state = await setup(h); await h.click(h.button('Favorite')); await h.settle(() => state.jobs[0].reject(new Error('offline'))); pressed(h, false); assert.equal(h.button('Favorite').disabled, false); assert.equal(h.role('status').length, 0); assert.ok(h.role('alert').some(node => normalized(node.textContent) === 'Save failed')); } },
    { name: 'rejection_rolls_back_true_initial_value', run: async h => { const state = await setup(h, true); await h.click(h.button('Favorite')); pressed(h, false); assert.deepEqual(state.calls, [false]); await h.settle(() => state.jobs[0].reject(new Error('offline'))); pressed(h, true); } },
    { name: 'retry_clears_error_and_uses_restored_value', run: async h => { const state = await setup(h); await h.click(h.button('Favorite')); await h.settle(() => state.jobs[0].reject(new Error('offline'))); await h.click(h.button('Favorite')); assert.equal(h.role('alert').length, 0); assert.deepEqual(state.calls, [true, true]); pressed(h, true); await h.settle(state.jobs[1].resolve); pressed(h, true); assert.equal(h.button('Favorite').disabled, false); } },
    { name: 'second_successful_operation_saves_opposite_value', run: async h => { const state = await setup(h); await h.click(h.button('Favorite')); await h.settle(state.jobs[0].resolve); await h.click(h.button('Favorite')); pressed(h, false); assert.deepEqual(state.calls, [true, false]); await h.settle(state.jobs[1].resolve); pressed(h, false); } },
  ];
}
suites.optimistic_favorite = favoriteTests();
function accordionTests() {
  const items = [{ id: 'billing', title: 'Billing', body: 'Invoices arrive monthly' }, { id: 'retired', title: 'Legacy', body: 'Unavailable details', disabled: true }, { id: 'security', title: 'Security', body: 'Use a passkey' }, { id: 'exports', title: 'Exports', body: 'Download your records' }];
  // Compare identity as a boolean: Node assertion diffs of DOM nodes traverse React fibers.
  function focused(h, name) { assert.ok(document.activeElement === h.button(name), `Expected focus on "${name}"`); }
  return [
    { name: 'starts_closed_with_disabled_heading', run: async h => { await h.mount({ items }); for (const item of items) assert.equal(h.button(item.title).getAttribute('aria-expanded'), 'false'); assert.equal(h.role('region').length, 0); assert.equal(h.button('Legacy').disabled, true); } },
    { name: 'click_toggles_panel_and_semantic_links', run: async h => { await h.mount({ items }); await h.click(h.button('Billing')); const button = h.button('Billing'); const panels = h.role('region'); assert.equal(panels.length, 1); assert.equal(button.getAttribute('aria-expanded'), 'true'); assert.equal(panels[0].id, button.getAttribute('aria-controls')); assert.equal(panels[0].getAttribute('aria-labelledby'), button.id); assert.ok(button.id); assert.equal(normalized(panels[0].textContent), items[0].body); await h.click(button); assert.equal(h.role('region').length, 0); assert.equal(button.getAttribute('aria-expanded'), 'false'); } },
    { name: 'opening_second_panel_removes_first', run: async h => { await h.mount({ items }); await h.click(h.button('Billing')); await h.click(h.button('Security')); assert.equal(h.role('region').length, 1); assert.equal(normalized(h.role('region')[0].textContent), items[2].body); assert.equal(h.button('Billing').getAttribute('aria-expanded'), 'false'); assert.ok(!h.text().includes(items[0].body)); } },
    { name: 'arrow_down_skips_disabled_and_wraps', run: async h => { await h.mount({ items }); const event = await h.key(h.button('Billing'), 'ArrowDown'); focused(h, 'Security'); assert.equal(event.defaultPrevented, true); await h.key(h.button('Exports'), 'ArrowDown'); focused(h, 'Billing'); } },
    { name: 'arrow_up_skips_disabled_and_wraps', run: async h => { await h.mount({ items }); const event = await h.key(h.button('Security'), 'ArrowUp'); focused(h, 'Billing'); assert.equal(event.defaultPrevented, true); await h.key(h.button('Billing'), 'ArrowUp'); focused(h, 'Exports'); } },
    { name: 'home_end_target_enabled_extremes', run: async h => { const edged = [{ ...items[1], id: 'first-disabled', title: 'First disabled' }, ...items, { ...items[1], id: 'last-disabled', title: 'Last disabled' }]; await h.mount({ items: edged }); const home = await h.key(h.button('Security'), 'Home'); focused(h, 'Billing'); const end = await h.key(h.button('Security'), 'End'); focused(h, 'Exports'); assert.equal(home.defaultPrevented, true); assert.equal(end.defaultPrevented, true); } },
    { name: 'focus_navigation_does_not_change_open_panel', run: async h => { await h.mount({ items }); await h.click(h.button('Billing')); await h.key(h.button('Billing'), 'ArrowDown'); assert.equal(h.button('Billing').getAttribute('aria-expanded'), 'true'); assert.equal(h.button('Security').getAttribute('aria-expanded'), 'false'); assert.equal(normalized(h.role('region')[0].textContent), items[0].body); } },
    { name: 'disabled_heading_cannot_open', run: async h => { await h.mount({ items }); await h.click(h.button('Legacy')); assert.equal(h.role('region').length, 0); assert.equal(h.button('Legacy').getAttribute('aria-expanded'), 'false'); } },
    { name: 'empty_and_single_enabled_lists_are_safe', run: async h => { await h.mount({ items: [] }); assert.equal(h.container.querySelectorAll('button').length, 0); await h.mount({ items: [items[1], items[2]] }); await h.key(h.button('Security'), 'ArrowDown'); focused(h, 'Security'); await h.key(h.button('Security'), 'ArrowUp'); focused(h, 'Security'); await h.click(h.button('Security')); assert.equal(h.role('region').length, 1); } },
    { name: 'two_instances_have_unique_trigger_and_panel_ids', run: async (h, Component) => { const React = require('../../frontend/node_modules/react'); await h.render(React.createElement(React.Fragment, null, React.createElement(Component, { items: [items[0]] }), React.createElement(Component, { items: [items[0]] }))); const buttons = Array.from(h.container.querySelectorAll('button')); assert.equal(buttons.length, 2); await h.click(buttons[0]); await h.click(buttons[1]); const identified = Array.from(h.container.querySelectorAll('[id]')).map(node => node.id); assert.equal(new Set(identified).size, identified.length); for (const button of buttons) { assert.ok(document.getElementById(button.getAttribute('aria-controls'))); assert.ok(button.id); } } },
  ];
}
suites.accordion_keyboard = accordionTests();
function paginationTests() {
  const items = Object.freeze(Array.from({ length: 7 }, (_, index) => Object.freeze({ id: `q${index + 1}`, label: `Review ${index + 1}` })));
  function page(h, current, total) { assert.equal(h.output('Page').textContent.replace(/\s/g, ''), `${current}/${total}`); }
  async function next(h, count = 1) { for (let i = 0; i < count; i++) await h.click(h.button('Next')); }
  return [
    { name: 'first_page_has_expected_slice_and_boundaries', run: async h => { await h.mount({ items, pageSize: 3 }); page(h, 1, 3); assert.deepEqual(h.list('Queue items'), ['Review 1', 'Review 2', 'Review 3']); assert.equal(h.button('Previous').disabled, true); assert.equal(h.button('Next').disabled, false); } },
    { name: 'next_and_previous_move_exactly_one_page', run: async h => { await h.mount({ items, pageSize: 2 }); await next(h, 2); page(h, 3, 4); assert.deepEqual(h.list('Queue items'), ['Review 5', 'Review 6']); await h.click(h.button('Previous')); page(h, 2, 4); assert.deepEqual(h.list('Queue items'), ['Review 3', 'Review 4']); } },
    { name: 'partial_last_page_disables_next', run: async h => { await h.mount({ items, pageSize: 3 }); await next(h, 2); page(h, 3, 3); assert.deepEqual(h.list('Queue items'), ['Review 7']); assert.equal(h.button('Next').disabled, true); await next(h); page(h, 3, 3); } },
    { name: 'shrink_clamps_and_growth_does_not_restore_stale_page', run: async h => { await h.mount({ items, pageSize: 2 }); await next(h, 3); await h.mount({ items: items.slice(0, 3), pageSize: 2 }); page(h, 2, 2); assert.deepEqual(h.list('Queue items'), ['Review 3']); await h.mount({ items, pageSize: 2 }); page(h, 2, 4); assert.deepEqual(h.list('Queue items'), ['Review 3', 'Review 4']); } },
    { name: 'empty_after_navigation_is_page_one_with_no_items', run: async h => { await h.mount({ items, pageSize: 2 }); await next(h, 2); await h.mount({ items: [], pageSize: 2 }); page(h, 1, 1); assert.deepEqual(h.list('Queue items'), []); assert.equal(h.button('Next').disabled, true); assert.equal(h.button('Previous').disabled, true); assert.ok(h.role('status').some(node => normalized(node.textContent) === 'No items')); } },
    { name: 'larger_page_size_clamps_current_page', run: async h => { await h.mount({ items, pageSize: 2 }); await next(h, 3); await h.mount({ items, pageSize: 4 }); page(h, 2, 2); assert.deepEqual(h.list('Queue items'), ['Review 5', 'Review 6', 'Review 7']); } },
    { name: 'valid_page_survives_data_and_page_size_updates', run: async h => { await h.mount({ items, pageSize: 2 }); await next(h); const updated = items.map(item => ({ ...item, label: `${item.label} updated` })); await h.mount({ items: updated, pageSize: 3 }); page(h, 2, 3); assert.deepEqual(h.list('Queue items'), ['Review 4 updated', 'Review 5 updated', 'Review 6 updated']); } },
    { name: 'empty_to_populated_removes_empty_message', run: async h => { await h.mount({ items: [], pageSize: 3 }); page(h, 1, 1); await h.mount({ items, pageSize: 3 }); page(h, 1, 3); assert.equal(h.role('status').filter(node => normalized(node.textContent) === 'No items').length, 0); assert.deepEqual(h.list('Queue items'), ['Review 1', 'Review 2', 'Review 3']); } },
  ];
}
suites.queue_pagination = paginationTests();
function undoTests() {
  const items = Object.freeze([{ id: 'f8', label: 'Agenda.pdf' }, { id: 'f3', label: 'Budget.csv' }, { id: 'f6', label: 'Diagram.png' }].map(item => Object.freeze(item)));
  function ids(values) { return values.map(item => item.id); }
  function visible(h) { return Array.from(findNamed(h.container, 'ul', 'Attachments').querySelectorAll('button')).map(button => accessibleName(button).replace(/^Remove /, '')); }
  async function setup(h, initialItems = items) { const calls = []; await h.mount({ initialItems, onChange: values => calls.push(Array.from(values, item => ({ ...item }))) }); return calls; }
  return [
    { name: 'initial_order_and_undo_disabled_without_callback', run: async h => { const calls = await setup(h); assert.deepEqual(visible(h), items.map(item => item.label)); assert.equal(h.button('Undo').disabled, true); assert.deepEqual(calls, []); } },
    { name: 'remove_targets_id_and_reports_remaining_order', run: async h => { const calls = await setup(h); await h.click(h.button('Remove Budget.csv')); assert.deepEqual(visible(h), ['Agenda.pdf', 'Diagram.png']); assert.deepEqual(calls.map(ids), [['f8', 'f6']]); assert.equal(h.button('Undo').disabled, false); assert.deepEqual(ids(items), ['f8', 'f3', 'f6']); } },
    { name: 'undo_middle_restores_original_position', run: async h => { const calls = await setup(h); await h.click(h.button('Remove Budget.csv')); await h.click(h.button('Undo')); assert.deepEqual(visible(h), ['Agenda.pdf', 'Budget.csv', 'Diagram.png']); assert.deepEqual(calls.map(ids), [['f8', 'f6'], ['f8', 'f3', 'f6']]); assert.equal(h.button('Undo').disabled, true); } },
    { name: 'undo_first_restores_front', run: async h => { await setup(h); await h.click(h.button('Remove Agenda.pdf')); await h.click(h.button('Undo')); assert.deepEqual(visible(h), ['Agenda.pdf', 'Budget.csv', 'Diagram.png']); } },
    { name: 'undo_last_preserves_end_position', run: async h => { await setup(h); await h.click(h.button('Remove Diagram.png')); await h.click(h.button('Undo')); assert.deepEqual(visible(h), ['Agenda.pdf', 'Budget.csv', 'Diagram.png']); } },
    { name: 'consecutive_removals_keep_only_latest_undo', run: async h => { const calls = await setup(h); await h.click(h.button('Remove Agenda.pdf')); await h.click(h.button('Remove Budget.csv')); await h.click(h.button('Undo')); assert.deepEqual(visible(h), ['Budget.csv', 'Diagram.png']); assert.deepEqual(calls.map(ids), [['f3', 'f6'], ['f6'], ['f3', 'f6']]); assert.equal(h.button('Undo').disabled, true); } },
    { name: 'undo_cannot_restore_twice_or_duplicate_item', run: async h => { const calls = await setup(h); await h.click(h.button('Remove Budget.csv')); await h.click(h.button('Undo')); await h.click(h.button('Undo')); assert.equal(calls.length, 2); assert.deepEqual(visible(h), ['Agenda.pdf', 'Budget.csv', 'Diagram.png']); } },
    { name: 'removing_only_attachment_shows_empty_then_undo_clears_it', run: async h => { const calls = await setup(h, [items[1]]); await h.click(h.button('Remove Budget.csv')); assert.deepEqual(visible(h), []); assert.ok(h.role('status').some(node => normalized(node.textContent) === 'No attachments')); await h.click(h.button('Undo')); assert.deepEqual(visible(h), ['Budget.csv']); assert.equal(h.role('status').filter(node => normalized(node.textContent) === 'No attachments').length, 0); assert.deepEqual(calls.map(ids), [[], ['f3']]); } },
  ];
}
suites.undo_removal = undoTests();
function resourceTests() {
  return [
    { name: 'idle_renders_prompt_without_retry', run: async h => { const calls = []; await h.mount({ resource: { status: 'idle' }, onRetry: () => calls.push('retry') }); assert.deepEqual(h.role('status').map(node => normalized(node.textContent)), ['Choose a project']); assert.equal(h.container.querySelectorAll('button').length, 0); assert.deepEqual(calls, []); } },
    { name: 'loading_renders_only_loading_state', run: async h => { await h.mount({ resource: { status: 'loading' }, onRetry: () => {} }); assert.deepEqual(h.role('status').map(node => normalized(node.textContent)), ['Loading project']); assert.equal(h.role('alert').length, 0); assert.equal(h.container.querySelectorAll('button,h2,li').length, 0); } },
    { name: 'error_message_and_retry_callback_once_per_click', run: async h => { const calls = []; await h.mount({ resource: { status: 'error', message: 'Project is unavailable' }, onRetry: (...args) => calls.push(args) }); assert.equal(calls.length, 0); assert.deepEqual(h.role('alert').map(node => normalized(node.textContent)), ['Project is unavailable']); await h.click(h.button('Retry')); await h.click(h.button('Retry')); assert.equal(calls.length, 2); assert.ok(calls.every(args => args.length === 0), 'Retry callbacks must receive zero arguments'); } },
    { name: 'ready_renders_title_and_ordered_duplicate_members', run: async h => { await h.mount({ resource: { status: 'ready', title: 'Orion', members: ['Min', 'Alex', 'Min'] }, onRetry: () => {} }); assert.equal(normalized(h.container.querySelector('h2')?.textContent), 'Orion'); assert.deepEqual(h.list('Members'), ['Min', 'Alex', 'Min']); assert.equal(h.role('alert').length, 0); assert.equal(h.container.querySelectorAll('button').length, 0); } },
    { name: 'ready_empty_members_has_explicit_empty_state', run: async h => { await h.mount({ resource: { status: 'ready', title: 'Empty project', members: [] }, onRetry: () => {} }); assert.equal(normalized(h.container.querySelector('h2')?.textContent), 'Empty project'); assert.ok(h.role('status').some(node => normalized(node.textContent) === 'No members')); assert.equal(h.container.querySelectorAll('ul').length, 0); } },
    { name: 'error_to_ready_removes_old_error_and_retry', run: async h => { const calls = []; const onRetry = () => calls.push('retry'); await h.mount({ resource: { status: 'error', message: 'Old failure' }, onRetry }); await h.mount({ resource: { status: 'ready', title: 'New project', members: ['Jordan'] }, onRetry }); assert.equal(h.role('alert').length, 0); assert.equal(h.container.querySelectorAll('button').length, 0); assert.ok(!h.text().includes('Old failure')); assert.deepEqual(h.list('Members'), ['Jordan']); assert.deepEqual(calls, []); } },
    { name: 'ready_to_loading_to_idle_removes_stale_data', run: async h => { const onRetry = () => {}; await h.mount({ resource: { status: 'ready', title: 'Previous project', members: ['Pat'] }, onRetry }); await h.mount({ resource: { status: 'loading' }, onRetry }); assert.ok(!h.text().includes('Previous project')); assert.equal(h.container.querySelectorAll('h2,li').length, 0); assert.ok(h.text().includes('Loading project')); await h.mount({ resource: { status: 'idle' }, onRetry }); assert.ok(!h.text().includes('Loading project')); assert.ok(h.text().includes('Choose a project')); } },
    { name: 'payload_markup_is_rendered_as_text', run: async h => { const markup = '<img src=x onerror=alert(1)>'; await h.mount({ resource: { status: 'error', message: markup }, onRetry: () => {} }); assert.equal(h.role('alert')[0]?.textContent, markup); assert.equal(h.container.querySelectorAll('img,script').length, 0); await h.mount({ resource: { status: 'ready', title: '<b>Project</b>', members: ['<i>Member</i>'] }, onRetry: () => {} }); assert.equal(h.container.querySelector('h2')?.textContent, '<b>Project</b>'); assert.deepEqual(h.list('Members'), ['<i>Member</i>']); assert.equal(h.container.querySelectorAll('b,i,img,script').length, 0); } },
  ];
}
suites.resource_union = resourceTests();
function draftTests() {
  const items = Object.freeze([{ id: 'i8', title: 'Login problem', open: true }, { id: 'i2', title: 'Login documentation', open: false }, { id: 'i5', title: 'Export crash', open: true }].map(item => Object.freeze(item)));
  async function setup(h) { const calls = []; await h.mount({ items, onApply: filters => calls.push({ ...filters }) }); return calls; }
  return [
    { name: 'initial_all_items_and_clean_draft', run: async h => { const calls = await setup(h); assert.deepEqual(h.list('Issues'), items.map(item => item.title)); assert.equal(h.input('Search issues').value, ''); assert.equal(h.input('Only open').checked, false); assert.equal(h.button('Apply').disabled, true); assert.deepEqual(calls, []); } },
    { name: 'typing_draft_does_not_filter_or_call_owner', run: async h => { const calls = await setup(h); await h.fill('Search issues', 'Login'); assert.deepEqual(h.list('Issues'), items.map(item => item.title)); assert.equal(h.button('Apply').disabled, false); assert.deepEqual(calls, []); } },
    { name: 'draft_checkbox_does_not_filter_or_call_owner', run: async h => { const calls = await setup(h); await h.click(h.input('Only open')); assert.equal(h.input('Only open').checked, true); assert.deepEqual(h.list('Issues'), items.map(item => item.title)); assert.deepEqual(calls, []); } },
    { name: 'apply_trims_query_and_combines_filters', run: async h => { const calls = await setup(h); await h.fill('Search issues', '  lOgIn  '); await h.click(h.input('Only open')); await h.click(h.button('Apply')); assert.deepEqual(h.list('Issues'), ['Login problem']); assert.deepEqual(calls, [{ query: 'lOgIn', onlyOpen: true }]); assert.equal(h.input('Search issues').value, 'lOgIn'); assert.equal(h.button('Apply').disabled, true); } },
    { name: 'dirty_comparison_trims_but_preserves_case', run: async h => { await setup(h); await h.fill('Search issues', '   '); assert.equal(h.button('Apply').disabled, true); await h.fill('Search issues', 'Login'); await h.click(h.button('Apply')); await h.fill('Search issues', ' Login '); assert.equal(h.button('Apply').disabled, true); await h.fill('Search issues', 'login'); assert.equal(h.button('Apply').disabled, false); } },
    { name: 'reset_clears_applied_and_unapplied_draft_once', run: async h => { const calls = await setup(h); await h.fill('Search issues', 'Login'); await h.click(h.input('Only open')); await h.click(h.button('Apply')); await h.fill('Search issues', 'Export'); await h.click(h.button('Reset')); assert.equal(h.input('Search issues').value, ''); assert.equal(h.input('Only open').checked, false); assert.equal(h.button('Apply').disabled, true); assert.deepEqual(h.list('Issues'), items.map(item => item.title)); assert.deepEqual(calls, [{ query: 'Login', onlyOpen: true }, { query: '', onlyOpen: false }]); } },
    { name: 'new_items_use_applied_filters_while_draft_is_pending', run: async h => { const calls = await setup(h); await h.fill('Search issues', 'Login'); await h.click(h.button('Apply')); await h.fill('Search issues', 'Export'); const updated = [...items, { id: 'i10', title: 'Login timeout', open: true }]; await h.mount({ items: updated, onApply: filters => calls.push({ ...filters }) }); assert.deepEqual(h.list('Issues'), ['Login problem', 'Login documentation', 'Login timeout']); assert.equal(h.input('Search issues').value, 'Export'); assert.deepEqual(calls, [{ query: 'Login', onlyOpen: false }]); } },
    { name: 'no_match_after_apply_shows_empty_state', run: async h => { const calls = await setup(h); await h.fill('Search issues', 'missing'); await h.click(h.button('Apply')); assert.deepEqual(h.list('Issues'), []); assert.ok(h.role('status').some(node => normalized(node.textContent) === 'No issues')); assert.deepEqual(calls, [{ query: 'missing', onlyOpen: false }]); } },
    { name: 'reset_from_clean_state_is_explicit_callback', run: async h => { const calls = await setup(h); await h.click(h.button('Reset')); assert.deepEqual(calls, [{ query: '', onlyOpen: false }]); assert.deepEqual(h.list('Issues'), items.map(item => item.title)); assert.deepEqual(items.map(item => item.id), ['i8', 'i2', 'i5']); } },
  ];
}
suites.draft_filters = draftTests();
function testNames(taskId) { return (suites[taskId] ?? []).map(test => test.name); }
async function runTask(taskId, componentExports) {
  assert.ok(dom, 'Call installDom() before loading candidates or react-dom/client');
  const suite = suites[taskId];
  assert.ok(suite, `Unknown task ${taskId}`);
  if (typeof componentExports.Component !== 'function' && typeof componentExports.Component !== 'object') return suite.map(test => ({ name: test.name, passed: false, error: 'Missing exported Component' }));
  const results = [];
  for (const test of suite) {
    const h = makeHarness(componentExports.Component);
    const runtimeErrors = [];
    const captureError = event => { runtimeErrors.push(event.error ?? event.reason ?? new Error(event.message || 'Unhandled candidate event error')); event.preventDefault(); };
    window.addEventListener('error', captureError);
    window.addEventListener('unhandledrejection', captureError);
    let error;
    try { await test.run(h, componentExports.Component); } catch (caught) { error = caught; }
    try { await h.unmount(); } catch (caught) { error ??= caught; }
    window.removeEventListener('error', captureError);
    window.removeEventListener('unhandledrejection', captureError);
    error ??= runtimeErrors[0];
    results.push({ name: test.name, passed: !error, ...(error ? { error: String(error.message ?? error).slice(0, 1600) } : {}) });
  }
  return results;
}

module.exports = { installDom, cleanupDom, runTask, testNames };

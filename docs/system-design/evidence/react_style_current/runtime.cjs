'use strict';

// Behavior-only acceptance harness. CSS values and source style are reviewed separately.
// Shared DOM/event helpers are adapted from coding_react_current; its files remain unchanged.
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
  if (element.labels?.length) return normalized(Array.from(element.labels).map(label => {
    const textOnly = label.cloneNode(true);
    textOnly.querySelectorAll('input,textarea,select,button,output').forEach(node => node.remove());
    return textOnly.textContent;
  }).join(' '));
  return normalized(element.textContent);
}
function findNamed(container, selector, name) {
  const found = Array.from(container.querySelectorAll(selector)).filter(node => accessibleName(node) === name);
  assert.equal(found.length, 1, `Expected one ${selector} named "${name}", found ${found.length}`);
  return found[0];
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
    unmount: async () => { await React.act(async () => root.unmount()); container.remove(); },
    input: name => findNamed(container, 'input,textarea,select', name),
    button: name => findNamed(container, 'button', name),
    output: name => findNamed(container, 'output', name),
    list: name => findNamed(container, 'ul', name),
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
    submit: async name => { await React.act(async () => {
      const form = findNamed(container, 'form', name);
      const allowed = form.dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
      assert.equal(allowed, false, 'Submit must prevent navigation');
    }); },
  };
  return h;
}
function alertText(h) { return h.role('alert').map(node => normalized(node.textContent)); }
function hasStatus(h, text) { return h.role('status').some(node => normalized(node.textContent) === text); }
function isInvalid(h, name) { return h.input(name).getAttribute('aria-invalid') === 'true'; }
function buttons(h) { return Array.from(h.container.querySelectorAll('button')).map(accessibleName); }
function tagNames(h) { return Array.from(h.list('Tags').querySelectorAll('li')).map(node => node.querySelector('span')?.textContent); }
function rowLabels(h) { return Array.from(findNamed(h.container, 'table', 'Rows').querySelectorAll('tbody tr')).map(row => row.cells[0].textContent); }
function sortState(h) { return findNamed(h.container, 'th', 'Score').getAttribute('aria-sort'); }
function folderNames(h) { return Array.from(h.list('Folders').querySelectorAll('li button')).map(accessibleName); }

const suites = {};

function tagTests() {
  const initial = Object.freeze(['Orchid', 'Birch']);
  async function setup(h) { const calls = []; await h.mount({ initialTags: initial, onChange: values => calls.push([...values]) }); return calls; }
  return [
    { name: 'initial_tags_order_and_no_callback', run: async h => { const calls = await setup(h); assert.deepEqual(tagNames(h), ['Orchid', 'Birch']); assert.equal(h.input('Add tag').value, ''); assert.equal(h.button('Add').type, 'submit'); assert.deepEqual(calls, []); } },
    { name: 'blank_submission_preserves_draft_and_tags', run: async h => { const calls = await setup(h); await h.fill('Add tag', '   '); await h.submit('Tag editor'); assert.deepEqual(alertText(h), ['Empty tag']); assert.deepEqual(tagNames(h), ['Orchid', 'Birch']); assert.equal(h.input('Add tag').value, '   '); assert.deepEqual(calls, []); } },
    { name: 'duplicate_comparison_trims_and_ignores_case', run: async h => { const calls = await setup(h); await h.fill('Add tag', '  oRcHiD  '); await h.submit('Tag editor'); assert.deepEqual(alertText(h), ['Duplicate tag']); assert.deepEqual(tagNames(h), ['Orchid', 'Birch']); assert.equal(h.input('Add tag').value, '  oRcHiD  '); assert.deepEqual(calls, []); } },
    { name: 'valid_add_trims_preserves_case_and_clears_error', run: async h => { const calls = await setup(h); await h.submit('Tag editor'); await h.fill('Add tag', '  Maple  '); assert.deepEqual(calls, []); await h.submit('Tag editor'); assert.deepEqual(tagNames(h), ['Orchid', 'Birch', 'Maple']); assert.equal(h.input('Add tag').value, ''); assert.deepEqual(alertText(h), []); assert.deepEqual(calls, [['Orchid', 'Birch', 'Maple']]); assert.deepEqual(initial, ['Orchid', 'Birch']); } },
    { name: 'remove_exact_tag_and_clear_error', run: async h => { const calls = await setup(h); await h.submit('Tag editor'); await h.click(h.button('Remove Orchid')); assert.deepEqual(tagNames(h), ['Birch']); assert.deepEqual(alertText(h), []); await h.click(h.button('Remove Birch')); assert.deepEqual(tagNames(h), []); assert.deepEqual(calls, [['Birch'], []]); } },
    { name: 'rerender_preserves_local_values_and_uses_new_callback', run: async h => { const old = await setup(h); const calls = []; await h.fill('Add tag', 'Elm'); await h.mount({ initialTags: ['ignored'], onChange: values => calls.push([...values]) }); assert.deepEqual(tagNames(h), ['Orchid', 'Birch']); assert.equal(h.input('Add tag').value, 'Elm'); await h.submit('Tag editor'); assert.deepEqual(old, []); assert.deepEqual(calls, [['Orchid', 'Birch', 'Elm']]); } },
    { name: 'new_tag_is_text_and_can_be_removed', run: async h => { const calls = await setup(h); const label = '<b>Spruce</b>'; await h.fill('Add tag', label); await h.submit('Tag editor'); assert.deepEqual(tagNames(h), ['Orchid', 'Birch', label]); assert.equal(h.container.querySelectorAll('b,script').length, 0); await h.click(h.button(`Remove ${label}`)); assert.deepEqual(calls, [['Orchid', 'Birch', label], ['Orchid', 'Birch']]); } },
  ];
}
suites.tag_editor = tagTests();

function tableTests() {
  const rows = Object.freeze([
    { id: 'r4', label: 'Quartz', score: 13 }, { id: 'r1', label: 'Willow', score: null },
    { id: 'r8', label: 'Fern', score: -4 }, { id: 'r5', label: 'Cedar', score: 2 },
    { id: 'r2', label: 'Ash', score: 2 }, { id: 'r9', label: 'Moss', score: null },
  ].map(row => Object.freeze(row)));
  const ascending = ['Fern', 'Cedar', 'Ash', 'Quartz', 'Willow', 'Moss'];
  const descending = ['Quartz', 'Cedar', 'Ash', 'Fern', 'Willow', 'Moss'];
  return [
    { name: 'initial_order_and_null_display', run: async h => { await h.mount({ rows }); assert.deepEqual(rowLabels(h), rows.map(row => row.label)); assert.equal(sortState(h), 'none'); assert.deepEqual(Array.from(h.container.querySelectorAll('tbody tr')).map(row => row.cells[1].textContent), ['13', '—', '-4', '2', '2', '—']); } },
    { name: 'ascending_is_numeric_stable_and_nulls_last', run: async h => { await h.mount({ rows }); await h.click(h.button('Sort score')); assert.deepEqual(rowLabels(h), ascending); assert.equal(sortState(h), 'ascending'); } },
    { name: 'descending_keeps_ties_and_nulls_stable', run: async h => { await h.mount({ rows }); await h.click(h.button('Sort score')); await h.click(h.button('Sort score')); assert.deepEqual(rowLabels(h), descending); assert.equal(sortState(h), 'descending'); } },
    { name: 'third_click_returns_to_ascending_without_mutation', run: async h => { await h.mount({ rows }); for (let i = 0; i < 3; i++) await h.click(h.button('Sort score')); assert.deepEqual(rowLabels(h), ascending); assert.equal(sortState(h), 'ascending'); assert.deepEqual(rows.map(row => row.id), ['r4', 'r1', 'r8', 'r5', 'r2', 'r9']); } },
    { name: 'new_rows_keep_direction_and_current_tie_order', run: async h => { await h.mount({ rows }); await h.click(h.button('Sort score')); await h.click(h.button('Sort score')); const updated = [rows[4], { id: 'r7', label: 'Pine', score: 100 }, rows[3], rows[5], rows[1]]; await h.mount({ rows: updated }); assert.deepEqual(rowLabels(h), ['Pine', 'Ash', 'Cedar', 'Moss', 'Willow']); assert.equal(sortState(h), 'descending'); } },
    { name: 'empty_rows_then_new_data_remain_usable', run: async h => { await h.mount({ rows: [] }); assert.deepEqual(rowLabels(h), []); assert.ok(hasStatus(h, 'No rows')); await h.click(h.button('Sort score')); await h.mount({ rows }); assert.deepEqual(rowLabels(h), ascending); assert.equal(hasStatus(h, 'No rows'), false); } },
    { name: 'labels_are_text_and_equal_numeric_values_keep_order', run: async h => { const label = '<i>Juniper</i>'; await h.mount({ rows: [{ id: 'a', label, score: 0 }, { id: 'b', label: 'Fir', score: 0 }] }); await h.click(h.button('Sort score')); await h.click(h.button('Sort score')); assert.deepEqual(rowLabels(h), [label, 'Fir']); assert.equal(h.container.querySelectorAll('i,script').length, 0); } },
  ];
}
suites.sortable_table = tableTests();

function wizardTests() {
  async function setup(h, initialName = '') { const calls = []; await h.mount({ initialName, onSubmit: name => calls.push(name) }); return calls; }
  return [
    { name: 'initial_edit_stage_uses_initial_name', run: async h => { const calls = await setup(h, 'Iris'); assert.equal(h.input('Name').value, 'Iris'); assert.deepEqual(buttons(h), ['Next']); assert.equal(h.container.querySelectorAll('output').length, 0); assert.deepEqual(calls, []); } },
    { name: 'blank_next_stays_in_edit_and_reports_error', run: async h => { const calls = await setup(h); await h.fill('Name', '  '); await h.submit('Name wizard'); assert.equal(isInvalid(h, 'Name'), true); assert.deepEqual(alertText(h), ['Name required']); assert.deepEqual(buttons(h), ['Next']); assert.deepEqual(calls, []); } },
    { name: 'valid_next_trims_name_and_clears_error', run: async h => { const calls = await setup(h); await h.submit('Name wizard'); await h.fill('Name', '  Nori  '); await h.submit('Name wizard'); assert.equal(h.output('Review name').textContent, 'Nori'); assert.deepEqual(buttons(h).sort(), ['Back', 'Submit']); assert.equal(h.container.querySelectorAll('input').length, 0); assert.deepEqual(alertText(h), []); assert.deepEqual(calls, []); } },
    { name: 'back_preserves_name_and_next_uses_edits', run: async h => { const calls = await setup(h, '  Ari '); await h.submit('Name wizard'); await h.click(h.button('Back')); assert.equal(h.input('Name').value, 'Ari'); await h.fill('Name', '  Sora '); await h.submit('Name wizard'); assert.equal(h.output('Review name').textContent, 'Sora'); assert.deepEqual(calls, []); } },
    { name: 'submit_calls_once_per_click_and_keeps_review', run: async h => { const calls = await setup(h, 'Rin'); await h.submit('Name wizard'); await h.click(h.button('Submit')); assert.deepEqual(calls, ['Rin']); assert.equal(h.output('Review name').textContent, 'Rin'); await h.click(h.button('Submit')); assert.deepEqual(calls, ['Rin', 'Rin']); } },
    { name: 'rerender_preserves_stage_and_uses_latest_submit', run: async h => { const old = await setup(h, 'Mina'); await h.submit('Name wizard'); const calls = []; await h.mount({ initialName: 'ignored', onSubmit: name => calls.push(name) }); assert.equal(h.output('Review name').textContent, 'Mina'); await h.click(h.button('Submit')); assert.deepEqual(old, []); assert.deepEqual(calls, ['Mina']); } },
    { name: 'review_renders_name_as_plain_text', run: async h => { const name = '<img src=x>'; const calls = await setup(h, name); await h.submit('Name wizard'); assert.equal(h.output('Review name').textContent, name); assert.equal(h.container.querySelectorAll('img,script').length, 0); await h.click(h.button('Back')); assert.equal(h.input('Name').value, name); assert.deepEqual(calls, []); } },
  ];
}
suites.step_wizard = wizardTests();

function converterTests() {
  return [
    { name: 'initial_celsius_zero_converts_to_fahrenheit', run: async h => { await h.mount({ initialValue: '0', initialUnit: 'C' }); assert.equal(h.input('Temperature').type, 'text'); assert.equal(h.input('Temperature').value, '0'); assert.equal(h.input('From unit').value, 'C'); assert.equal(h.output('Converted').textContent, '32.00 F'); assert.equal(h.button('Swap').disabled, false); } },
    { name: 'decimal_sign_and_whitespace_preserve_raw_input', run: async h => { await h.mount({ initialValue: '0', initialUnit: 'C' }); for (const [raw, expected] of [['  -12.5  ', '9.50 F'], ['+.5', '32.90 F'], ['1.', '33.80 F']]) { await h.fill('Temperature', raw); assert.equal(h.input('Temperature').value, raw); assert.equal(h.output('Converted').textContent, expected); assert.equal(isInvalid(h, 'Temperature'), false); } } },
    { name: 'fahrenheit_and_select_change_use_current_raw_value', run: async h => { await h.mount({ initialValue: ' 212 ', initialUnit: 'F' }); assert.equal(h.output('Converted').textContent, '100.00 C'); await h.fill('From unit', 'C'); assert.equal(h.input('Temperature').value, ' 212 '); assert.equal(h.output('Converted').textContent, '413.60 F'); } },
    { name: 'invalid_formats_disable_swap_then_recover', run: async h => { await h.mount({ initialValue: '', initialUnit: 'C' }); for (const raw of ['', '  ', '12cats', '1e2', '0x10', 'Infinity', '+', '.']) { await h.fill('Temperature', raw); assert.equal(h.output('Converted').textContent, 'Invalid temperature'); assert.equal(isInvalid(h, 'Temperature'), true); assert.equal(h.button('Swap').disabled, true); } await h.fill('Temperature', '-40'); assert.equal(h.output('Converted').textContent, '-40.00 F'); assert.equal(isInvalid(h, 'Temperature'), false); assert.equal(h.button('Swap').disabled, false); } },
    { name: 'swap_moves_calculated_value_and_reverses_unit_twice', run: async h => { await h.mount({ initialValue: '100', initialUnit: 'C' }); await h.click(h.button('Swap')); assert.equal(h.input('Temperature').value, '212.00'); assert.equal(h.input('From unit').value, 'F'); assert.equal(h.output('Converted').textContent, '100.00 C'); await h.click(h.button('Swap')); assert.equal(h.input('Temperature').value, '100.00'); assert.equal(h.input('From unit').value, 'C'); assert.equal(h.output('Converted').textContent, '212.00 F'); } },
    { name: 'rerender_does_not_reset_local_temperature_or_unit', run: async h => { await h.mount({ initialValue: '0', initialUnit: 'C' }); await h.fill('Temperature', ' 50 '); await h.fill('From unit', 'F'); await h.mount({ initialValue: '999', initialUnit: 'C' }); assert.equal(h.input('Temperature').value, ' 50 '); assert.equal(h.input('From unit').value, 'F'); assert.equal(h.output('Converted').textContent, '10.00 C'); } },
    { name: 'overflow_input_and_result_are_invalid', run: async h => { await h.mount({ initialValue: '9'.repeat(400), initialUnit: 'C' }); assert.equal(isInvalid(h, 'Temperature'), true); assert.equal(h.output('Converted').textContent, 'Invalid temperature'); await h.fill('Temperature', '1' + '0'.repeat(308)); assert.equal(h.output('Converted').textContent, 'Invalid temperature'); assert.equal(h.button('Swap').disabled, true); } },
  ];
}
suites.unit_converter = converterTests();

function passwordTests() {
  async function setup(h, initialValue = 'Fox!29') { const calls = []; await h.mount({ initialValue, onChange: value => calls.push(value) }); return calls; }
  return [
    { name: 'initial_value_is_masked_without_callback', run: async h => { const calls = await setup(h); assert.equal(h.input('Password').value, 'Fox!29'); assert.equal(h.input('Password').type, 'password'); assert.equal(h.button('Toggle visibility').getAttribute('aria-pressed'), 'false'); assert.deepEqual(calls, []); } },
    { name: 'reveal_and_hide_preserve_value', run: async h => { const calls = await setup(h); await h.click(h.button('Toggle visibility')); assert.equal(h.input('Password').type, 'text'); assert.equal(h.button('Toggle visibility').getAttribute('aria-pressed'), 'true'); assert.equal(h.input('Password').value, 'Fox!29'); await h.click(h.button('Toggle visibility')); assert.equal(h.input('Password').type, 'password'); assert.equal(h.button('Toggle visibility').getAttribute('aria-pressed'), 'false'); assert.equal(h.input('Password').value, 'Fox!29'); assert.deepEqual(calls, []); } },
    { name: 'editing_preserves_raw_string_and_calls_once', run: async h => { const calls = await setup(h); await h.fill('Password', '  spaced !  '); assert.equal(h.input('Password').value, '  spaced !  '); assert.deepEqual(calls, ['  spaced !  ']); } },
    { name: 'visible_edit_survives_multiple_toggles', run: async h => { const calls = await setup(h); await h.click(h.button('Toggle visibility')); await h.fill('Password', 'new#42'); for (let i = 0; i < 3; i++) await h.click(h.button('Toggle visibility')); assert.equal(h.input('Password').type, 'password'); assert.equal(h.input('Password').value, 'new#42'); assert.deepEqual(calls, ['new#42']); } },
    { name: 'empty_value_is_retained_when_toggled', run: async h => { const calls = await setup(h); await h.fill('Password', ''); await h.click(h.button('Toggle visibility')); assert.equal(h.input('Password').value, ''); assert.equal(h.input('Password').type, 'text'); assert.deepEqual(calls, ['']); } },
    { name: 'rerender_keeps_value_visibility_and_uses_latest_callback', run: async h => { const old = await setup(h); await h.click(h.button('Toggle visibility')); const calls = []; await h.mount({ initialValue: 'ignored', onChange: value => calls.push(value) }); assert.equal(h.input('Password').value, 'Fox!29'); assert.equal(h.input('Password').type, 'text'); await h.fill('Password', 'changed'); assert.deepEqual(old, []); assert.deepEqual(calls, ['changed']); } },
    { name: 'markup_like_value_is_only_input_text', run: async h => { const value = '<svg onload=x>'; const calls = await setup(h, value); await h.click(h.button('Toggle visibility')); assert.equal(h.input('Password').value, value); assert.equal(h.container.querySelectorAll('svg,script').length, 0); assert.deepEqual(calls, []); } },
  ];
}
suites.password_visibility = passwordTests();

function expanderTests() {
  return [
    { name: 'long_text_initially_has_exact_truncated_preview', run: async h => { await h.mount({ text: 'Willow river path', maxChars: 6 }); assert.equal(h.output('Preview').textContent, 'Willow…'); assert.deepEqual(buttons(h), ['Show more']); } },
    { name: 'expand_same_props_and_collapse_preserve_whitespace', run: async h => { const props = { text: '  moss\ntrail  ', maxChars: 4 }; await h.mount(props); await h.click(h.button('Show more')); assert.equal(h.output('Preview').textContent, props.text); await h.mount({ ...props }); assert.equal(h.output('Preview').textContent, props.text); await h.click(h.button('Show less')); assert.equal(h.output('Preview').textContent, '  mo…'); } },
    { name: 'short_and_exact_length_text_have_no_toggle', run: async h => { await h.mount({ text: 'Pine', maxChars: 8 }); assert.equal(h.output('Preview').textContent, 'Pine'); assert.deepEqual(buttons(h), []); await h.mount({ text: 'Cedar', maxChars: 5 }); assert.equal(h.output('Preview').textContent, 'Cedar'); assert.deepEqual(buttons(h), []); } },
    { name: 'empty_text_and_zero_limit_follow_same_rule', run: async h => { await h.mount({ text: '', maxChars: 0 }); assert.equal(h.output('Preview').textContent, ''); assert.deepEqual(buttons(h), []); await h.mount({ text: 'a', maxChars: 0 }); assert.equal(h.output('Preview').textContent, '…'); await h.click(h.button('Show more')); assert.equal(h.output('Preview').textContent, 'a'); } },
    { name: 'changed_text_resets_expanded_state', run: async h => { await h.mount({ text: 'First meadow', maxChars: 5 }); await h.click(h.button('Show more')); await h.mount({ text: 'Second meadow', maxChars: 5 }); assert.equal(h.output('Preview').textContent, 'Secon…'); assert.deepEqual(buttons(h), ['Show more']); } },
    { name: 'changed_limit_resets_expanded_state', run: async h => { await h.mount({ text: 'Bright forest', maxChars: 3 }); await h.click(h.button('Show more')); await h.mount({ text: 'Bright forest', maxChars: 6 }); assert.equal(h.output('Preview').textContent, 'Bright…'); assert.deepEqual(buttons(h), ['Show more']); } },
    { name: 'markup_text_never_creates_elements', run: async h => { const text = '<b>Birch</b>'; await h.mount({ text, maxChars: 3 }); assert.equal(h.output('Preview').textContent, '<b>…'); await h.click(h.button('Show more')); assert.equal(h.output('Preview').textContent, text); assert.equal(h.container.querySelectorAll('b,script').length, 0); } },
  ];
}
suites.text_expander = expanderTests();

function rangeTests() {
  async function setup(h, min = -2, max = 3) { const calls = []; await h.mount({ min, max, onApply: value => calls.push({ ...value }) }); return calls; }
  return [
    { name: 'initial_options_include_bounds_and_empty_selection', run: async h => { const calls = await setup(h); for (const name of ['Start', 'End']) { assert.equal(h.input(name).value, ''); assert.deepEqual(Array.from(h.input(name).options).map(option => [option.value, option.textContent]), [['', 'Choose'], ['-2', '-2'], ['-1', '-1'], ['0', '0'], ['1', '1'], ['2', '2'], ['3', '3']]); } assert.equal(h.button('Apply').type, 'submit'); assert.deepEqual(calls, []); } },
    { name: 'missing_both_values_reports_both_fields', run: async h => { const calls = await setup(h); await h.submit('Range pair'); assert.equal(isInvalid(h, 'Start'), true); assert.equal(isInvalid(h, 'End'), true); assert.deepEqual(alertText(h), ['Choose both values']); assert.deepEqual(calls, []); } },
    { name: 'one_missing_value_marks_only_missing_field', run: async h => { const calls = await setup(h); await h.fill('Start', '0'); await h.submit('Range pair'); assert.equal(isInvalid(h, 'Start'), false); assert.equal(isInvalid(h, 'End'), true); assert.deepEqual(alertText(h), ['Choose both values']); assert.deepEqual(calls, []); } },
    { name: 'reversed_range_is_rejected_on_end', run: async h => { const calls = await setup(h); await h.fill('Start', '3'); await h.fill('End', '-2'); assert.deepEqual(calls, []); await h.submit('Range pair'); assert.equal(isInvalid(h, 'Start'), false); assert.equal(isInvalid(h, 'End'), true); assert.deepEqual(alertText(h), ['Range order']); assert.deepEqual(calls, []); } },
    { name: 'valid_negative_to_positive_range_clears_errors', run: async h => { const calls = await setup(h); await h.submit('Range pair'); await h.fill('Start', '-2'); await h.fill('End', '3'); await h.submit('Range pair'); assert.deepEqual(calls, [{ start: -2, end: 3 }]); assert.equal(h.input('Start').value, '-2'); assert.equal(h.input('End').value, '3'); assert.equal(isInvalid(h, 'Start'), false); assert.equal(isInvalid(h, 'End'), false); assert.deepEqual(alertText(h), []); } },
    { name: 'equal_zero_endpoints_and_single_option_range_are_valid', run: async h => { const calls = await setup(h, 0, 0); await h.fill('Start', '0'); await h.fill('End', '0'); await h.submit('Range pair'); assert.deepEqual(calls, [{ start: 0, end: 0 }]); assert.deepEqual(Array.from(h.input('Start').options).map(option => option.value), ['', '0']); } },
    { name: 'rerender_keeps_selection_and_uses_latest_callback', run: async h => { const old = await setup(h); await h.fill('Start', '-1'); await h.fill('End', '2'); const calls = []; await h.mount({ min: -2, max: 3, onApply: value => calls.push({ ...value }) }); assert.equal(h.input('Start').value, '-1'); assert.equal(h.input('End').value, '2'); assert.deepEqual(calls, []); await h.submit('Range pair'); assert.deepEqual(old, []); assert.deepEqual(calls, [{ start: -1, end: 2 }]); } },
  ];
}
suites.range_pair = rangeTests();

function breadcrumbTests() {
  function tree() { return [{ id: 'garden', name: 'Garden', children: [{ id: 'shade', name: 'Shade', children: [{ id: 'ferns', name: 'Ferns', children: [] }] }, { id: 'sun', name: 'Sun', children: [] }] }, { id: 'archive', name: 'Archive', children: [] }]; }
  function freezeTree(folders) { return Object.freeze(folders.map(folder => Object.freeze({ ...folder, children: freezeTree(folder.children) }))); }
  async function setup(h) { const calls = []; const folders = freezeTree(tree()); await h.mount({ folders, onNavigate: path => calls.push([...path]) }); return { calls, folders }; }
  return [
    { name: 'initial_root_lists_only_direct_children', run: async h => { const { calls } = await setup(h); assert.equal(h.output('Current path').textContent, '/'); assert.deepEqual(folderNames(h), ['Enter Garden', 'Enter Archive']); assert.equal(h.button('Back').disabled, true); await h.click(h.button('Back')); assert.deepEqual(calls, []); } },
    { name: 'enter_uses_ids_and_shows_direct_children', run: async h => { const { calls } = await setup(h); await h.click(h.button('Enter Garden')); assert.equal(h.output('Current path').textContent, '/Garden'); assert.deepEqual(folderNames(h), ['Enter Shade', 'Enter Sun']); assert.equal(h.button('Back').disabled, false); assert.deepEqual(calls, [['garden']]); } },
    { name: 'nested_enter_and_back_move_one_level', run: async h => { const { calls } = await setup(h); await h.click(h.button('Enter Garden')); await h.click(h.button('Enter Shade')); assert.equal(h.output('Current path').textContent, '/Garden/Shade'); assert.deepEqual(folderNames(h), ['Enter Ferns']); await h.click(h.button('Back')); assert.equal(h.output('Current path').textContent, '/Garden'); await h.click(h.button('Back')); assert.equal(h.output('Current path').textContent, '/'); assert.equal(h.button('Back').disabled, true); assert.deepEqual(calls, [['garden'], ['garden', 'shade'], ['garden'], []]); } },
    { name: 'leaf_empty_state_then_back_recovers_siblings', run: async h => { const { calls } = await setup(h); await h.click(h.button('Enter Archive')); assert.equal(h.output('Current path').textContent, '/Archive'); assert.deepEqual(folderNames(h), []); assert.ok(hasStatus(h, 'No folders')); await h.click(h.button('Back')); assert.equal(hasStatus(h, 'No folders'), false); assert.deepEqual(folderNames(h), ['Enter Garden', 'Enter Archive']); assert.deepEqual(calls, [['archive'], []]); } },
    { name: 'same_id_new_objects_keep_path_and_update_names', run: async h => { const { calls, folders } = await setup(h); await h.click(h.button('Enter Garden')); await h.click(h.button('Enter Shade')); const updated = tree(); updated[0].name = 'Courtyard'; updated[0].children[0].name = 'Canopy'; updated[0].children[0].children[0].name = 'Moss'; const latest = []; await h.mount({ folders: updated, onNavigate: path => latest.push([...path]) }); assert.equal(h.output('Current path').textContent, '/Courtyard/Canopy'); assert.deepEqual(folderNames(h), ['Enter Moss']); assert.deepEqual(latest, []); await h.click(h.button('Enter Moss')); assert.deepEqual(latest, [['garden', 'shade', 'ferns']]); assert.deepEqual(calls, [['garden'], ['garden', 'shade']]); assert.equal(folders[0].name, 'Garden'); } },
    { name: 'empty_root_keeps_disabled_back_without_navigation', run: async h => { const calls = []; await h.mount({ folders: [], onNavigate: path => calls.push([...path]) }); assert.equal(h.output('Current path').textContent, '/'); assert.deepEqual(folderNames(h), []); assert.ok(hasStatus(h, 'No folders')); assert.equal(h.button('Back').disabled, true); await h.click(h.button('Back')); assert.deepEqual(calls, []); } },
    { name: 'folder_names_are_plain_text_not_external_paths', run: async h => { const name = '<b>Notes'; const calls = []; await h.mount({ folders: [{ id: 'notes-id', name, children: [] }], onNavigate: path => calls.push([...path]) }); await h.click(h.button(`Enter ${name}`)); assert.equal(h.output('Current path').textContent, '/' + name); assert.equal(h.container.querySelectorAll('b,a,script').length, 0); assert.deepEqual(calls, [['notes-id']]); assert.equal(window.location.href, 'http://benchmark.invalid/'); } },
  ];
}
suites.breadcrumb_browser = breadcrumbTests();

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
    try { await test.run(h); } catch (caught) { error = caught; }
    try { await h.unmount(); } catch (caught) { error ??= caught; }
    window.removeEventListener('error', captureError);
    window.removeEventListener('unhandledrejection', captureError);
    error ??= runtimeErrors[0];
    results.push({ name: test.name, passed: !error, ...(error ? { error: String(error.message ?? error).slice(0, 1600) } : {}) });
  }
  return results;
}

module.exports = { installDom, cleanupDom, runTask, testNames };

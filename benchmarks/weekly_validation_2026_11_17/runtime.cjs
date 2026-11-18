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

const suites = {};
function t(name, run) { return { name, run }; }
function out(h, name) { return h.output(name).textContent; }
function lis(h, name) { return Array.from(h.list(name).querySelectorAll('li')).map(x => x.textContent); }
function alert(h) { return h.role('alert').map(x => x.textContent).join('|'); }
function panel(h) { assert.equal(h.container.querySelectorAll('[data-testid="panel"]').length, 1); }
suites.reading_history = [
 t('initial_empty_null_and_no_callback', async h => { const calls=[]; await h.mount({onRecord:x=>calls.push(x)}); panel(h); assert.equal(out(h,'Latest'),'None'); assert.deepEqual(lis(h,'History'),[]); assert.equal(h.input('Reading').value,''); assert.deepEqual(calls,[]); }),
 t('valid_signed_duplicate_readings_and_clear_input', async h => { const calls=[]; await h.mount({onRecord:x=>calls.push(x)}); for(const v of [' -12 ','0','0']) { await h.fill('Reading',v); await h.click(h.button('Record')); } assert.deepEqual(lis(h,'History'),['-12','0','0']); assert.equal(out(h,'Latest'),'0'); assert.equal(h.input('Reading').value,''); assert.deepEqual(calls,[-12,0,0]); }),
 t('invalid_integer_strings_preserve_state', async h => { const calls=[]; await h.mount({onRecord:x=>calls.push(x)}); await h.fill('Reading','7'); await h.click(h.button('Record')); for(const v of ['', ' ', '1.2', '1e2', '+2', '9007199254740992']) { await h.fill('Reading',v); await h.click(h.button('Record')); assert.equal(alert(h),'Invalid reading'); assert.equal(out(h,'Latest'),'7'); assert.equal(h.input('Reading').value,v); } assert.deepEqual(lis(h,'History'),['7']); assert.deepEqual(calls,[7]); }),
 t('clear_removes_history_latest_error_without_callback', async h => { const calls=[]; await h.mount({onRecord:x=>calls.push(x)}); await h.fill('Reading','8'); await h.click(h.button('Record')); await h.fill('Reading','x'); await h.click(h.button('Record')); await h.click(h.button('Clear')); assert.deepEqual(lis(h,'History'),[]); assert.equal(out(h,'Latest'),'None'); assert.equal(alert(h),''); assert.equal(h.input('Reading').value,''); assert.deepEqual(calls,[8]); }),
 t('new_callback_retains_state_and_success_clears_error', async h => { const old=[],calls=[]; await h.mount({onRecord:x=>old.push(x)}); await h.fill('Reading','4'); await h.click(h.button('Record')); await h.mount({onRecord:x=>calls.push(x)}); assert.equal(out(h,'Latest'),'4'); await h.fill('Reading','bad'); await h.click(h.button('Record')); await h.fill('Reading','9'); await h.click(h.button('Record')); assert.equal(alert(h),''); assert.deepEqual(lis(h,'History'),['4','9']); assert.deepEqual(old,[4]); assert.deepEqual(calls,[9]); }),
];
suites.cent_split = [
 t('initial_remainder_allocation',async h=>{await h.mount({initialCents:'10',initialPeople:'3'});panel(h);assert.equal(out(h,'Allocation'),'4, 3, 3');}),
 t('zero_and_more_people_than_cents',async h=>{await h.mount({initialCents:'0',initialPeople:'4'});assert.equal(out(h,'Allocation'),'0, 0, 0, 0');await h.fill('Cents','2');assert.equal(out(h,'Allocation'),'1, 1, 0, 0');}),
 t('invalid_values_and_bounds',async h=>{await h.mount({initialCents:'8',initialPeople:'2'});for(const v of ['','-1','1.5','1e2','9007199254740992']){await h.fill('Cents',v);assert.equal(out(h,'Allocation'),'Invalid allocation');}await h.fill('Cents','8');for(const v of ['0','21','2.0','+2','']){await h.fill('People',v);assert.equal(out(h,'Allocation'),'Invalid allocation');}}),
 t('trim_only_for_calculation_and_live_people_change',async h=>{await h.mount({initialCents:' 09 ',initialPeople:' 2 '});assert.equal(out(h,'Allocation'),'5, 4');assert.equal(h.input('Cents').value,' 09 ');await h.fill('People','3');assert.equal(out(h,'Allocation'),'3, 3, 3');}),
 t('prop_updates_preserve_edited_values',async h=>{await h.mount({initialCents:'4',initialPeople:'2'});await h.fill('Cents','11');await h.mount({initialCents:'99',initialPeople:'4'});assert.equal(out(h,'Allocation'),'6, 5');assert.equal(h.input('People').value,'2');}),
];
suites.signal_cycle = [
 t('initial_stop_reset_disabled_no_callback',async h=>{const calls=[];await h.mount({onChange:x=>calls.push(x)});panel(h);assert.equal(out(h,'Signal'),'stop');assert.equal(h.button('Reset').disabled,true);await h.click(h.button('Reset'));assert.deepEqual(calls,[]);}),
 t('three_steps_cycle_in_order',async h=>{const calls=[];await h.mount({onChange:x=>calls.push(x)});for(const value of ['ready','go','stop']){await h.click(h.button('Next'));assert.equal(out(h,'Signal'),value);}assert.deepEqual(calls,['ready','go','stop']);}),
 t('reset_from_ready_calls_once',async h=>{const calls=[];await h.mount({onChange:x=>calls.push(x)});await h.click(h.button('Next'));await h.click(h.button('Reset'));await h.click(h.button('Reset'));assert.equal(out(h,'Signal'),'stop');assert.deepEqual(calls,['ready','stop']);}),
 t('reset_from_go_restores_cycle',async h=>{const calls=[];await h.mount({onChange:x=>calls.push(x)});await h.click(h.button('Next'));await h.click(h.button('Next'));await h.click(h.button('Reset'));await h.click(h.button('Next'));assert.equal(out(h,'Signal'),'ready');assert.deepEqual(calls,['ready','go','stop','ready']);}),
 t('new_callback_preserves_state',async h=>{const old=[],calls=[];await h.mount({onChange:x=>old.push(x)});await h.click(h.button('Next'));await h.mount({onChange:x=>calls.push(x)});assert.equal(out(h,'Signal'),'ready');await h.click(h.button('Next'));assert.deepEqual(old,['ready']);assert.deepEqual(calls,['go']);}),
];
suites.text_normalizer = [
 t('initial_whitespace_preserved',async h=>{await h.mount({initialText:' Ab\n '});panel(h);assert.equal(out(h,'Result'),' Ab\n ');assert.equal(out(h,'Characters'),'5');assert.equal(h.input('Trim').checked,false);assert.equal(h.input('Case').value,'keep');}),
 t('case_conversion_does_not_overwrite_input',async h=>{await h.mount({initialText:'Hello'});await h.fill('Case','upper');assert.equal(out(h,'Result'),'HELLO');await h.fill('Case','lower');assert.equal(out(h,'Result'),'hello');assert.equal(h.input('Text').value,'Hello');}),
 t('trim_and_unicode_string_length',async h=>{await h.mount({initialText:'  😀a  '});await h.click(h.input('Trim'));assert.equal(out(h,'Result'),'😀a');assert.equal(out(h,'Characters'),'3');await h.fill('Text','  ');assert.equal(out(h,'Result'),'');assert.equal(out(h,'Characters'),'0');}),
 t('props_do_not_reset_options_or_local_text',async h=>{await h.mount({initialText:'one'});await h.fill('Text',' two ');await h.fill('Case','upper');await h.click(h.input('Trim'));await h.mount({initialText:'other'});assert.equal(out(h,'Result'),'TWO');assert.equal(h.input('Text').value,' two ');}),
 t('markup_is_safe_text_and_keep_reverses_case_mode',async h=>{await h.mount({initialText:'<b>Ab</b>'});await h.fill('Case','upper');await h.fill('Case','keep');assert.equal(out(h,'Result'),'<b>Ab</b>');assert.equal(h.container.querySelectorAll('b,script').length,0);}),
];
const cards=()=>Object.freeze([{id:'a',text:'Alpha'},{id:'b',text:'Beta'}].map(Object.freeze));
suites.question_deck = [
 t('initial_card_and_zero_completed',async h=>{const calls=[];await h.mount({cards:cards(),onFinish:x=>calls.push([...x])});panel(h);assert.equal(out(h,'Current'),'Alpha');assert.equal(out(h,'Completed'),'0');assert.equal(h.button('Next').disabled,false);assert.deepEqual(calls,[]);}),
 t('complete_exactly_once_at_end',async h=>{const calls=[];await h.mount({cards:cards(),onFinish:x=>calls.push([...x])});await h.click(h.button('Next'));assert.equal(out(h,'Current'),'Beta');assert.deepEqual(calls,[]);await h.click(h.button('Next'));assert.equal(out(h,'Current'),'Done');assert.equal(out(h,'Completed'),'2');assert.equal(h.button('Next').disabled,true);await h.click(h.button('Next'));assert.deepEqual(calls,[['a','b']]);}),
 t('restart_and_second_completion',async h=>{const calls=[];await h.mount({cards:cards(),onFinish:x=>calls.push([...x])});for(let i=0;i<2;i++)await h.click(h.button('Next'));await h.click(h.button('Restart'));assert.equal(out(h,'Completed'),'0');assert.equal(out(h,'Current'),'Alpha');for(let i=0;i<2;i++)await h.click(h.button('Next'));assert.deepEqual(calls,[['a','b'],['a','b']]);}),
 t('empty_deck_never_finishes',async h=>{const calls=[];await h.mount({cards:[],onFinish:x=>calls.push([...x])});assert.equal(out(h,'Current'),'Done');assert.equal(h.button('Next').disabled,true);await h.click(h.button('Next'));await h.click(h.button('Restart'));assert.equal(out(h,'Completed'),'0');assert.deepEqual(calls,[]);}),
 t('prop_snapshot_latest_callback_and_safe_text',async h=>{const old=[],calls=[],original=Object.freeze([Object.freeze({id:'q',text:'<b>Q</b>'})]);await h.mount({cards:original,onFinish:x=>old.push([...x])});await h.mount({cards:cards(),onFinish:x=>calls.push([...x])});assert.equal(out(h,'Current'),'<b>Q</b>');assert.equal(h.container.querySelectorAll('b,script').length,0);await h.click(h.button('Next'));assert.deepEqual(old,[]);assert.deepEqual(calls,[['q']]);assert.equal(original[0].text,'<b>Q</b>');}),
];
suites.weighted_counter = [
 t('initial_value_and_reset_disabled',async h=>{const calls=[];await h.mount({initialValue:5,step:2,onChange:x=>calls.push(x)});panel(h);assert.equal(out(h,'Value'),'5');assert.equal(h.button('Reset').disabled,true);await h.click(h.button('Reset'));assert.deepEqual(calls,[]);}),
 t('add_subtract_and_negative_values',async h=>{const calls=[];await h.mount({initialValue:1,step:3,onChange:x=>calls.push(x)});await h.click(h.button('Subtract'));assert.equal(out(h,'Value'),'-2');await h.click(h.button('Add'));assert.equal(out(h,'Value'),'1');assert.deepEqual(calls,[-2,1]);}),
 t('reset_once_to_mounted_baseline',async h=>{const calls=[];await h.mount({initialValue:4,step:2,onChange:x=>calls.push(x)});await h.click(h.button('Add'));await h.click(h.button('Add'));await h.click(h.button('Reset'));await h.click(h.button('Reset'));assert.equal(out(h,'Value'),'4');assert.deepEqual(calls,[6,8,4]);}),
 t('latest_step_callback_preserved_baseline',async h=>{const old=[],calls=[];await h.mount({initialValue:4,step:2,onChange:x=>old.push(x)});await h.click(h.button('Add'));await h.mount({initialValue:99,step:5,onChange:x=>calls.push(x)});assert.equal(out(h,'Value'),'6');await h.click(h.button('Add'));assert.equal(out(h,'Value'),'11');await h.click(h.button('Reset'));assert.equal(out(h,'Value'),'4');assert.deepEqual(old,[6]);assert.deepEqual(calls,[11,4]);}),
 t('return_by_arithmetic_disables_reset',async h=>{const calls=[];await h.mount({initialValue:0,step:7,onChange:x=>calls.push(x)});await h.click(h.button('Add'));await h.click(h.button('Subtract'));assert.equal(h.button('Reset').disabled,true);await h.click(h.button('Reset'));assert.deepEqual(calls,[7,0]);}),
];
suites.comparison_snapshot = [
 t('initial_no_comparison',async h=>{const calls=[];await h.mount({onCompare:x=>calls.push(x)});panel(h);assert.equal(out(h,'Result'),'Not compared');assert.equal(h.input('Left').value,'');assert.equal(h.input('Right').value,'');assert.deepEqual(calls,[]);}),
 t('compare_numeric_less_equal_greater',async h=>{const calls=[];await h.mount({onCompare:x=>calls.push(x)});for(const [l,r,result] of [['2','10','less'],[' -3 ','-3','equal'],['0','-1','greater']]){await h.fill('Left',l);await h.fill('Right',r);await h.click(h.button('Compare'));assert.equal(out(h,'Result'),result);}assert.deepEqual(calls,['less','equal','greater']);}),
 t('editing_preserves_committed_result',async h=>{const calls=[];await h.mount({onCompare:x=>calls.push(x)});await h.fill('Left','1');await h.fill('Right','2');await h.click(h.button('Compare'));await h.fill('Left','99');assert.equal(out(h,'Result'),'less');assert.deepEqual(calls,['less']);}),
 t('invalid_attempts_preserve_result_and_success_clears_error',async h=>{const calls=[];await h.mount({onCompare:x=>calls.push(x)});await h.fill('Left','2');await h.fill('Right','1');await h.click(h.button('Compare'));for(const v of ['', '2.3','1e1','+1','9007199254740992']){await h.fill('Left',v);await h.click(h.button('Compare'));assert.equal(alert(h),'Invalid integers');assert.equal(out(h,'Result'),'greater');}await h.fill('Left','0');assert.equal(alert(h),'Invalid integers');await h.click(h.button('Compare'));assert.equal(alert(h),'');assert.deepEqual(calls,['greater','less']);}),
 t('new_callback_preserves_inputs_and_rejects_invalid_right',async h=>{const old=[],calls=[];await h.mount({onCompare:x=>old.push(x)});await h.fill('Left','3');await h.fill('Right','bad');await h.mount({onCompare:x=>calls.push(x)});assert.equal(h.input('Left').value,'3');await h.click(h.button('Compare'));assert.equal(out(h,'Result'),'Not compared');await h.fill('Right','3');await h.click(h.button('Compare'));assert.deepEqual(old,[]);assert.deepEqual(calls,['equal']);}),
];
function items(){return Object.freeze([{id:'a',label:'A'},{id:'b',label:'B'},{id:'c',label:'C'}].map(Object.freeze));}
function itemLabels(h){return Array.from(h.list('Items').querySelectorAll('li span')).map(x=>x.textContent);}
suites.item_reorder = [
 t('initial_order_boundaries_no_callback',async h=>{const calls=[];await h.mount({initialItems:items(),onChange:x=>calls.push([...x])});panel(h);assert.deepEqual(itemLabels(h),['A','B','C']);assert.equal(h.button('Up a').disabled,true);assert.equal(h.button('Down c').disabled,true);await h.click(h.button('Up a'));assert.deepEqual(calls,[]);}),
 t('move_up_then_down_exact_order',async h=>{const calls=[];await h.mount({initialItems:items(),onChange:x=>calls.push([...x])});await h.click(h.button('Up b'));assert.deepEqual(itemLabels(h),['B','A','C']);await h.click(h.button('Down b'));assert.deepEqual(itemLabels(h),['A','B','C']);assert.deepEqual(calls,[['b','a','c'],['a','b','c']]);}),
 t('move_to_boundary_and_preserve_input',async h=>{const calls=[],initialItems=items();await h.mount({initialItems,onChange:x=>calls.push([...x])});await h.click(h.button('Up c'));await h.click(h.button('Up c'));assert.deepEqual(itemLabels(h),['C','A','B']);assert.equal(h.button('Up c').disabled,true);await h.click(h.button('Up c'));assert.deepEqual(calls,[['a','c','b'],['c','a','b']]);assert.deepEqual(initialItems.map(x=>x.id),['a','b','c']);}),
 t('empty_list_is_inert',async h=>{const calls=[];await h.mount({initialItems:[],onChange:x=>calls.push([...x])});assert.equal(h.role('status')[0].textContent,'No items');assert.deepEqual(itemLabels(h),[]);assert.deepEqual(calls,[]);}),
 t('props_preserve_items_latest_callback_and_markup_text',async h=>{const old=[],calls=[];await h.mount({initialItems:[{id:'x',label:'<b>X</b>'},{id:'y',label:'Y'}],onChange:x=>old.push([...x])});await h.mount({initialItems:items(),onChange:x=>calls.push([...x])});assert.deepEqual(itemLabels(h),['<b>X</b>','Y']);assert.equal(h.container.querySelectorAll('b,script').length,0);await h.click(h.button('Down x'));assert.deepEqual(calls,[['y','x']]);assert.deepEqual(old,[]);}),
];
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

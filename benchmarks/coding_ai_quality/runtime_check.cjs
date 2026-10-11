// Exercise only the frozen calibration scenarios, after type-check and bundle.
const { JSDOM } = require('../../frontend/node_modules/jsdom');
const [task, bundle] = process.argv.slice(2);
const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', {
  url: 'http://localhost/',
});
global.window = dom.window;
global.document = dom.window.document;
global.navigator = dom.window.navigator;
global.HTMLElement = dom.window.HTMLElement;
global.IS_REACT_ACT_ENVIRONMENT = true;
const React = require('../../frontend/node_modules/react');
const { createRoot } = require('../../frontend/node_modules/react-dom/client');

async function check() {
  const Component = require(bundle).default;
  if (typeof Component !== 'function') throw new Error('Default React component export is missing');
  const container = document.getElementById('root');
  const root = createRoot(container);
  await React.act(async () => root.render(React.createElement(Component)));
  const has = (value) => container.textContent.includes(value);
  const click = async (label) => {
    const button = [...container.querySelectorAll('button')].find((item) =>
      item.textContent.trim() === label || item.getAttribute('aria-label') === label);
    if (!button) throw new Error(`Missing button: ${label}`);
    await React.act(async () => button.dispatchEvent(new window.MouseEvent('click', { bubbles: true })));
  };
  const checks = [];
  if (task === 'counter_reset') {
    checks.push(has('0'));
    await click('증가');
    await click('증가');
    checks.push(has('2'));
    await click('초기화');
    checks.push(has('0'));
  } else if (task === 'product_search') {
    checks.push(['사과', '바나나', '딸기'].every(has));
    const input = container.querySelector('input');
    if (!input) throw new Error('Missing search input');
    const setValue = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    const enter = async (value) => {
      await React.act(async () => {
        setValue.call(input, value);
        input.dispatchEvent(new window.Event('input', { bubbles: true }));
      });
    };
    await enter('바나나');
    checks.push(has('바나나') && !has('사과') && !has('딸기'));
    await enter('없는상품');
    checks.push(has('검색 결과 없음'));
  } else {
    throw new Error(`Unknown task: ${task}`);
  }
  await React.act(async () => root.unmount());
  process.stdout.write(JSON.stringify(checks));
  if (!checks.every(Boolean)) process.exitCode = 1;
}

check().catch((error) => {
  process.stderr.write(String(error.stack || error));
  process.exitCode = 1;
});

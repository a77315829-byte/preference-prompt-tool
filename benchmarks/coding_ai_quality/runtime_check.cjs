// Exercise frozen calibration and holdout scenarios, after type-check and bundle.
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
  const exports = require(bundle);
  const namedExport = task === 'signup_validation' ? 'SignupForm' :
    task === 'todo_toggle' ? 'TodoList' :
    task === 'confirm_dialog' ? 'ConfirmDialog' :
    task === 'text_preview' ? 'TextPreview' :
    task === 'password_visibility' ? 'PasswordVisibility' :
    task === 'faq_toggle' ? 'FaqToggle' : null;
  const exportedComponents = Object.entries(exports).filter(([name, value]) =>
    /^[A-Z]/.test(name) && typeof value === 'function');
  const Component = exports.default || (namedExport && exports[namedExport]) ||
    (exportedComponents.length === 1 ? exportedComponents[0][1] : null);
  if (typeof Component !== 'function') throw new Error('React component export is missing');
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
  } else if (task === 'signup_validation') {
    const form = container.querySelector('form');
    const inputs = [...container.querySelectorAll('input')];
    if (!form || inputs.length < 2) throw new Error('Missing signup form or inputs');
    const submit = async () => React.act(async () => {
      form.dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
    });
    const setValue = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    const enter = async (input, value) => React.act(async () => {
      setValue.call(input, value);
      input.dispatchEvent(new window.Event('input', { bubbles: true }));
    });
    const errorFor = (input) => {
      const describedBy = input.getAttribute('aria-describedby');
      return input.getAttribute('aria-invalid') === 'true'
        && describedBy && document.getElementById(describedBy)?.textContent.trim();
    };
    await submit();
    checks.push(!has('가입 완료') && Boolean(errorFor(inputs[0])) && Boolean(errorFor(inputs[1])));
    await enter(inputs[0], '홍길동');
    await enter(inputs[1], 'invalid-email');
    await submit();
    checks.push(!has('가입 완료') && Boolean(errorFor(inputs[1])));
    await enter(inputs[1], 'user@example.com');
    await submit();
    checks.push(has('가입 완료'));
  } else if (task === 'todo_toggle') {
    const boxes = [...container.querySelectorAll('input[type="checkbox"]')];
    if (boxes.length < 2) throw new Error('Missing todo checkboxes');
    checks.push(has('문서 읽기') && has('테스트 작성') && has('완료 0/2')
      && boxes.every((box) => !box.checked));
    await React.act(async () => boxes[0].click());
    checks.push(has('완료 1/2') && boxes[0].checked);
    await React.act(async () => boxes[0].click());
    checks.push(has('완료 0/2') && !boxes[0].checked);
  } else if (task === 'confirm_dialog') {
    checks.push(!has('정말 삭제할까요?') && !has('삭제되었습니다'));
    await click('삭제하기');
    checks.push(has('정말 삭제할까요?')
      && [...container.querySelectorAll('button')].some((button) => button.textContent.trim() === '취소')
      && [...container.querySelectorAll('button')].some((button) => button.textContent.trim() === '삭제 확인'));
    await click('취소');
    checks.push(!has('정말 삭제할까요?') && !has('삭제되었습니다'));
    await click('삭제하기');
    await click('삭제 확인');
    checks.push(!has('정말 삭제할까요?') && has('삭제되었습니다'));
  } else if (task === 'faq_toggle') {
    const answer = '배송은 2~3일 걸립니다.';
    const button = () => [...container.querySelectorAll('button')].find((item) =>
      ['답변 보기', '답변 닫기'].includes(item.textContent.trim()));
    checks.push(has('배송은 얼마나 걸리나요?') && !has(answer)
      && button()?.textContent.trim() === '답변 보기'
      && button()?.getAttribute('aria-expanded') === 'false');
    await click('답변 보기');
    checks.push(has(answer) && button()?.textContent.trim() === '답변 닫기'
      && button()?.getAttribute('aria-expanded') === 'true');
    await click('답변 닫기');
    checks.push(!has(answer) && button()?.textContent.trim() === '답변 보기'
      && button()?.getAttribute('aria-expanded') === 'false');
  } else if (task === 'password_visibility') {
    const input = container.querySelector('input');
    if (!input) throw new Error('Missing password input');
    checks.push(input.type === 'password' && has('비밀번호 보기'));
    const setValue = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    await React.act(async () => {
      setValue.call(input, 'abc123');
      input.dispatchEvent(new window.Event('input', { bubbles: true }));
    });
    await click('비밀번호 보기');
    checks.push(input.type === 'text' && input.value === 'abc123' && has('비밀번호 숨기기'));
    await click('비밀번호 숨기기');
    checks.push(input.type === 'password' && input.value === 'abc123' && has('비밀번호 보기'));
  } else if (task === 'text_preview') {
    const input = container.querySelector('textarea');
    if (!input) throw new Error('Missing preview textarea');
    const previewHas = (value) => {
      const visible = container.cloneNode(true);
      visible.querySelectorAll('textarea').forEach((item) => item.remove());
      return visible.textContent.includes(value);
    };
    checks.push(previewHas('미리보기 없음'));
    const setValue = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
    const enter = async (value) => React.act(async () => {
      setValue.call(input, value);
      input.dispatchEvent(new window.Event('input', { bubbles: true }));
    });
    const first20 = '1234567890 1234567\nX';
    await enter(first20);
    checks.push(previewHas(first20) && !previewHas('…'));
    await enter(`${first20}Z`);
    checks.push(previewHas(`${first20}…`) && !previewHas(`${first20}Z`));
    await enter('');
    checks.push(previewHas('미리보기 없음'));
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

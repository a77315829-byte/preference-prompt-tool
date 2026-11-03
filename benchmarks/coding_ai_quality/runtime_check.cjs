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
    task === 'faq_toggle' ? 'FaqToggle' :
    task === 'cart_quantity' ? 'CartQuantity' :
    task === 'tab_switch' ? 'TabSwitch' :
    task === 'char_counter' ? 'CharCounter' :
    task === 'star_rating' ? 'StarRating' :
    task === 'like_toggle' ? 'LikeToggle' :
    task === 'temperature_convert' ? 'TemperatureConvert' : null;
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
  } else if (task === 'faq_multi') {
    const buttons = [...container.querySelectorAll('button[aria-expanded]')];
    const states = () => buttons.map((button) => button.getAttribute('aria-expanded'));
    const toggle = async (index) => React.act(async () => {
      buttons[index].dispatchEvent(new window.MouseEvent('click', { bubbles: true }));
    });
    const answersMatch = () => buttons.every((button) => {
      const answer = document.getElementById(button.getAttribute('aria-controls'));
      return button.getAttribute('aria-expanded') === 'true'
        ? Boolean(answer && !answer.hidden && answer.textContent.trim())
        : !answer || answer.hidden;
    });
    checks.push(buttons.length === 3 && states().every((state) => state === 'false') && answersMatch());
    await toggle(0);
    checks.push(JSON.stringify(states()) === '["true","false","false"]' && answersMatch());
    await toggle(1);
    checks.push(JSON.stringify(states()) === '["true","true","false"]' && answersMatch());
    await toggle(0);
    checks.push(JSON.stringify(states()) === '["false","true","false"]' && answersMatch());
    await toggle(2);
    checks.push(JSON.stringify(states()) === '["false","true","true"]' && answersMatch());
    await toggle(1);
    await toggle(2);
    checks.push(states().every((state) => state === 'false') && answersMatch());
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
  } else if (task === 'cart_quantity') {
    const displays = (quantity, total) => {
      const content = container.textContent.replace(/\s+/g, ' ');
      return content.includes('머그컵')
        && content.includes(`수량 ${quantity}`)
        && content.includes(`총 ${total.toLocaleString('ko-KR')}원`);
    };
    checks.push(displays(1, 5000));
    await click('추가');
    await click('추가');
    checks.push(displays(3, 15000));
    await click('빼기');
    checks.push(displays(2, 10000));
    await click('빼기');
    await click('빼기');
    checks.push(displays(1, 5000));
  } else if (task === 'tab_switch') {
    const notice = '이번 주 점검은 없습니다.';
    const event = '신규 가입 시 쿠폰을 드립니다.';
    const tab = (label) => [...container.querySelectorAll('[role="tab"]')].find((item) =>
      item.textContent.trim() === label);
    const shown = (el) => {
      for (let node = el; node && node !== container; node = node.parentElement) {
        if (node.hidden || window.getComputedStyle(node).display === 'none') return false;
      }
      return true;
    };
    const visible = (text) => [...container.querySelectorAll('*')].some((el) =>
      el.children.length === 0 && el.textContent.includes(text) && shown(el));
    const selected = (label) => tab(label)?.getAttribute('aria-selected') === 'true';
    checks.push(Boolean(tab('공지') && tab('이벤트')) && selected('공지') && !selected('이벤트')
      && visible(notice) && !visible(event));
    await React.act(async () => tab('이벤트').dispatchEvent(new window.MouseEvent('click', { bubbles: true })));
    checks.push(selected('이벤트') && !selected('공지') && visible(event) && !visible(notice));
    await React.act(async () => tab('공지').dispatchEvent(new window.MouseEvent('click', { bubbles: true })));
    checks.push(selected('공지') && !selected('이벤트') && visible(notice) && !visible(event));
  } else if (task === 'char_counter') {
    const input = container.querySelector('textarea');
    if (!input) throw new Error('Missing textarea');
    const submit = () => [...container.querySelectorAll('button')].find((item) => item.textContent.trim() === '제출');
    const setValue = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
    const enter = async (value) => React.act(async () => {
      setValue.call(input, value);
      input.dispatchEvent(new window.Event('input', { bubbles: true }));
    });
    const over = '20자를 넘었습니다';
    checks.push(has('0/20자') && !has(over) && submit() && !submit().disabled);
    await enter('가나다라마');
    checks.push(has('5/20자') && !has(over) && !submit().disabled);
    await enter('가'.repeat(21));
    checks.push(has('21/20자') && has(over) && submit().disabled);
    await enter('가'.repeat(20));
    checks.push(has('20/20자') && !has(over) && !submit().disabled);
  } else if (task === 'star_rating') {
    const star = (n) => [...container.querySelectorAll('button')].find((item) =>
      item.getAttribute('aria-label') === `별 ${n}개`);
    const pressed = () => [1, 2, 3, 4, 5].map((n) => star(n)?.getAttribute('aria-pressed'));
    checks.push([1, 2, 3, 4, 5].every((n) => star(n)) && has('평점 0점')
      && pressed().every((value) => value === 'false'));
    await click('별 3개');
    checks.push(has('평점 3점') && JSON.stringify(pressed()) === '["true","true","true","false","false"]');
    await click('별 1개');
    checks.push(has('평점 1점') && !has('평점 3점')
      && JSON.stringify(pressed()) === '["true","false","false","false","false"]');
  } else if (task === 'like_toggle') {
    const button = () => [...container.querySelectorAll('button')].find((item) =>
      ['좋아요', '좋아요 취소'].includes(item.textContent.trim()));
    const text = () => container.textContent.replace(/\s+/g, ' ');
    checks.push(text().includes('좋아요 10') && button()?.textContent.trim() === '좋아요'
      && button()?.getAttribute('aria-pressed') === 'false');
    await click('좋아요');
    checks.push(text().includes('좋아요 11') && !text().includes('좋아요 10')
      && button()?.textContent.trim() === '좋아요 취소' && button()?.getAttribute('aria-pressed') === 'true');
    await click('좋아요 취소');
    checks.push(text().includes('좋아요 10') && !text().includes('좋아요 11')
      && button()?.textContent.trim() === '좋아요' && button()?.getAttribute('aria-pressed') === 'false');
  } else if (task === 'temperature_convert') {
    const input = container.querySelector('input');
    if (!input) throw new Error('Missing input');
    const setValue = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    const enter = async (value) => React.act(async () => {
      setValue.call(input, value);
      input.dispatchEvent(new window.Event('input', { bubbles: true }));
    });
    const prompt = '숫자를 입력하세요';
    checks.push(has('화씨 32°F') && !has(prompt));
    await enter('100');
    checks.push(has('화씨 212°F') && !has(prompt));
    await enter('37.5');
    checks.push(has('화씨 99.5°F') && !has(prompt));
    await enter('');
    checks.push(has(prompt) && !/화씨\s*-?\d/.test(container.textContent));
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

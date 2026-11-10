// Offline prototype: builds explicit instructions and inspects replies; never executes generated code.
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const requireFrontend = createRequire(new URL('../../frontend/package.json', import.meta.url));
const ts = requireFrontend('typescript');
export const VERSION = 'coding-contract-v1';
const explanations = ['none', 'brief', 'steps'];
const deliveries = ['markdown', 'json'];

function validateProfile(profile) {
  if (!profile || !explanations.includes(profile.explanation) || !deliveries.includes(profile.delivery)) {
    throw new Error('explanation: none/brief/steps, delivery: markdown/json을 선택하세요.');
  }
}

export function buildPrompt(profile) {
  validateProfile(profile);
  const explanation = {
    none: '설명을 추가하지 않는다. JSON 형식이면 explanation을 빈 배열로 둔다.',
    brief: '설명을 1~3개 항목으로 작성한다. Markdown에서는 각 항목을 "- "로 시작하고 한 줄에 하나씩 쓴다.',
    steps: '설명을 3~5개 순서 항목으로 작성한다. Markdown에서는 1.부터 연속 번호를 붙이고 한 줄에 하나씩 쓴다.',
  }[profile.explanation];
  const delivery = profile.delivery === 'markdown'
    ? '응답을 "### Component.tsx"로 시작한다. 다음에 완전한 파일을 담은 ```tsx 코드 블록을 정확히 하나 둔다. 설명이 필요하면 코드 블록 뒤에만 둔다.'
    : '응답은 JSON 객체 하나로만 작성한다. 최상위 키는 files와 explanation 두 개다. files는 {"Component.tsx":"완전한 TSX 코드"}, explanation은 설명 문자열 배열이다. Markdown 코드 펜스나 JSON 밖 문장은 쓰지 않는다.';
  return [
    'TypeScript/React의 작은 단일 파일 컴포넌트 작업을 수행하라.',
    '사용자가 고른 아래 전달 규칙을 새 작업마다 적용하라. 이 규칙은 취향 추정이나 코드 품질 보증이 아니다.',
    '', '## 선택한 답변 조건', `- ${delivery}`, `- ${explanation}`,
    '', '## 공통 조건',
    '- Component.tsx 전체를 생략 없이 제공한다. 부분 코드·추가 파일·추가 코드 블록은 제공하지 않는다.',
    '- 컴포넌트는 대문자로 시작하는 이름의 export function 또는 export const 함수로 선언한다. 익명 default export, 클래스, re-export는 이번 검사 범위에서 제외한다.',
    '- 작업에서 지정한 컴포넌트 이름과 공개 인터페이스를 지킨다. 기능 요구사항을 형식보다 우선한다.',
    '- React 외의 패키지와 로컬 파일 import를 추가하지 않는다. 명시적인 any 타입은 사용하지 않는다.',
    '- 설명이 있는 경우 변경 이유·주의점·사용 방법을 다룬다. 항목 수 통과가 설명의 유용성을 보장하지는 않는다.',
    '- 실제 실행하지 않았다면 테스트를 통과했다고 주장하지 않는다.',
    '- 단일 파일로 해결할 수 없거나 규칙이 작업과 충돌하면 구현을 꾸며 내지 말고 충돌을 알린다. 이 경우 자동 검사는 통과가 아닌 미지원으로 별도 기록한다.',
    '', '## 이번 작업', '아래에 별도로 전달된 작업 요구사항을 구현하라.',
  ].join('\n');
}

function unpackReply(answer, profile) {
  if (typeof answer !== 'string' || answer.length > 100_000) throw new Error('답변은 100,000자 이내 문자열이어야 합니다.');
  if (profile.delivery === 'json') {
    const body = JSON.parse(answer);
    if (!body || Array.isArray(body) || Object.keys(body).sort().join(',') !== 'explanation,files'
      || !body.files || Array.isArray(body.files) || Object.keys(body.files).join(',') !== 'Component.tsx'
      || typeof body.files['Component.tsx'] !== 'string' || !Array.isArray(body.explanation)
      || body.explanation.some(item => typeof item !== 'string' || !item.trim() || /[\r\n]/.test(item))) {
      throw new Error('정해진 files/explanation JSON 구조와 한 줄 설명 항목이 필요합니다.');
    }
    return { code: body.files['Component.tsx'], items: body.explanation };
  }
  const match = answer.trim().match(/^### Component\.tsx\s*\n```tsx\s*\n([\s\S]*?)\n```([\s\S]*)$/);
  if (!match || match[2].includes('```')) throw new Error('파일 제목, 단일 TSX 코드 블록, 뒤쪽 설명 순서가 필요합니다.');
  const items = match[2].trim() ? match[2].trim().split(/\r?\n/).filter(line => line.trim()) : [];
  if (profile.explanation === 'brief' && items.some(line => !/^- \S/.test(line))) throw new Error('설명은 - 목록이어야 합니다.');
  if (profile.explanation === 'steps' && items.some((line, i) => !line.startsWith(`${i + 1}. `) || !line.slice(3).trim())) {
    throw new Error('단계 설명은 1부터 이어지는 번호 목록이어야 합니다.');
  }
  return { code: match[1], items };
}

export function inspectReply(answer, profile) {
  validateProfile(profile);
  const result = {
    version: VERSION, profile: { ...profile }, checks: {},
    functionalCorrectness: 'not_run', typeCorrectness: 'not_run', semanticQuality: 'not_measured',
    jointSuccess: null,
  };
  let parsed;
  try { parsed = unpackReply(answer, profile); result.checks.delivery = true; }
  catch (error) {
    result.checks.delivery = false; result.detail = error.message;
    result.contractSatisfied = false; return result;
  }
  const count = parsed.items.length;
  result.checks.explanation = profile.explanation === 'none' ? count === 0
    : profile.explanation === 'brief' ? count >= 1 && count <= 3 : count >= 3 && count <= 5;
  const source = ts.createSourceFile('Component.tsx', parsed.code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  result.checks.syntax = source.parseDiagnostics.length === 0 && source.statements.length > 0;
  result.checks.noExplicitAny = true;
  result.checks.imports = true;
  result.checks.exportedComponent = false;
  const isComponentName = node => node?.name && ts.isIdentifier(node.name) && /^[A-Z]/.test(node.name.text);
  const isExported = node => node.modifiers?.some(modifier => modifier.kind === ts.SyntaxKind.ExportKeyword);
  function visit(node) {
    if (node.kind === ts.SyntaxKind.AnyKeyword) result.checks.noExplicitAny = false;
    if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node) && node.moduleSpecifier) {
      if (!node.moduleSpecifier || !ts.isStringLiteral(node.moduleSpecifier) || node.moduleSpecifier.text !== 'react') result.checks.imports = false;
    }
    if (ts.isImportEqualsDeclaration(node) || ts.isCallExpression(node)
      && (node.expression.kind === ts.SyntaxKind.ImportKeyword || ts.isIdentifier(node.expression) && node.expression.text === 'require')) result.checks.imports = false;
    if (ts.isFunctionDeclaration(node) && isExported(node) && isComponentName(node) && node.body) result.checks.exportedComponent = true;
    if (ts.isVariableStatement(node) && isExported(node) && node.declarationList.declarations.some(declaration =>
      isComponentName(declaration) && declaration.initializer && (ts.isArrowFunction(declaration.initializer) || ts.isFunctionExpression(declaration.initializer)))) result.checks.exportedComponent = true;
    ts.forEachChild(node, visit);
  }
  visit(source);
  result.explanationItems = count;
  result.contractSatisfied = Object.values(result.checks).every(value => value === true);
  return result;
}

// CLI generates a reusable prompt or checks a locally supplied reply, with no network access.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [operation, explanation = 'brief', delivery = 'markdown', answerPath] = process.argv.slice(2);
  if (operation === 'prompt') console.log(buildPrompt({ explanation, delivery }));
  else if (operation === 'inspect' && answerPath) {
    const report = inspectReply(readFileSync(answerPath, 'utf8'), { explanation, delivery });
    console.log(JSON.stringify(report, null, 2));
    if (!report.contractSatisfied) process.exitCode = 1;
  } else throw new Error('Usage: node contract.mjs prompt <none|brief|steps> <markdown|json> OR inspect <explanation> <delivery> <answer-file>');
}

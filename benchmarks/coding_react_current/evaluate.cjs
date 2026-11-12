'use strict';

// Reviewed, bounded local execution. The VM and AST gate are not an OS sandbox.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createRequire } = require('node:module');

const FRONTEND = path.resolve(__dirname, '../../frontend');
const frontendRequire = createRequire(path.join(FRONTEND, 'package.json'));
const ts = frontendRequire('typescript');
const VIRTUAL_ROOT = path.join(FRONTEND, '__coding_react_candidate__');
const WITNESS = '__contract_witness__.tsx';
const MAX_SOURCE_BYTES = 256 * 1024;
const ALLOWED_PACKAGES = new Set(['react', 'react/jsx-runtime', 'react/jsx-dev-runtime']);
const BLOCKED_NAMES = new Set([
  'require', 'eval', 'Function', 'process', 'Buffer', 'globalThis', 'global',
  'constructor', '__proto__', 'fetch', 'XMLHttpRequest', 'WebSocket', 'Worker',
  'localStorage', 'sessionStorage', 'navigator', 'location',
  'self', 'parent', 'top', 'frames', 'importScripts', 'setTimeout', 'setInterval',
  'setImmediate', 'queueMicrotask', 'WebAssembly', 'module', '__filename', '__dirname',
]);

function errorText(error) {
  return error && typeof error.message === 'string' ? error.message : String(error);
}

function position(source, node) {
  const point = source.getLineAndCharacterOfPosition(node.getStart(source));
  return { file: source.fileName, line: point.line + 1, column: point.character + 1 };
}

function diagnosticJson(diagnostic) {
  const result = {
    code: diagnostic.code,
    category: ts.DiagnosticCategory[diagnostic.category].toLowerCase(),
    message: ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n'),
  };
  if (diagnostic.file) {
    const relative = path.relative(VIRTUAL_ROOT, diagnostic.file.fileName);
    result.file = !relative.startsWith('..') ? relative.replaceAll('\\', '/') : diagnostic.file.fileName;
    if (diagnostic.start !== undefined) {
      const point = diagnostic.file.getLineAndCharacterOfPosition(diagnostic.start);
      result.line = point.line + 1;
      result.column = point.character + 1;
    }
  }
  return result;
}

function validateFiles(candidate) {
  const errors = [];
  if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate) ||
      !candidate.files || typeof candidate.files !== 'object' || Array.isArray(candidate.files)) {
    return { errors: ['Candidate must be an object containing a files object.'], files: null };
  }
  const entries = Object.entries(candidate.files);
  if (entries.length < 1 || entries.length > 10) errors.push('Provide between 1 and 10 source files.');
  if (!Object.hasOwn(candidate.files, 'Component.tsx')) errors.push('Component.tsx is required.');
  let bytes = 0;
  const seen = new Set();
  for (const [filename, source] of entries) {
    if (!/^(?:[A-Za-z0-9_-][A-Za-z0-9_.-]*\/)*[A-Za-z0-9_-][A-Za-z0-9_.-]*\.tsx?$/.test(filename) ||
        filename.toLowerCase().endsWith('.d.ts') || filename.toLowerCase() === WITNESS ||
        filename.split('/').some(part => part.endsWith('.') || /^(?:con|prn|aux|nul|com\d|lpt\d)(?:\.|$)/i.test(part))) {
      errors.push(`Unsafe or unsupported source path: ${filename}`);
    }
    if (seen.has(filename.toLowerCase())) errors.push(`Case-insensitive duplicate path: ${filename}`);
    seen.add(filename.toLowerCase());
    if (typeof source !== 'string') errors.push(`Source must be a string: ${filename}`);
    else bytes += Buffer.byteLength(source, 'utf8');
  }
  if (bytes > MAX_SOURCE_BYTES) errors.push(`Source exceeds ${MAX_SOURCE_BYTES} bytes.`);
  return { errors, files: errors.length ? null : candidate.files };
}

function resolveRelative(specifier, fromFile, files) {
  if (!specifier.startsWith('./') && !specifier.startsWith('../')) return null;
  if (specifier.includes('\\') || specifier.includes('\0')) return null;
  const normalized = path.posix.normalize(path.posix.join(path.posix.dirname(fromFile), specifier));
  if (normalized === '..' || normalized.startsWith('../') || path.posix.isAbsolute(normalized)) return null;
  const choices = [normalized, `${normalized}.ts`, `${normalized}.tsx`, `${normalized}/index.ts`, `${normalized}/index.tsx`];
  // TypeScript accepts .js specifiers that refer to a .ts/.tsx source.
  if (normalized.endsWith('.js')) choices.push(`${normalized.slice(0, -3)}.ts`, `${normalized.slice(0, -3)}.tsx`);
  return choices.find(name => Object.hasOwn(files, name)) || null;
}

function inspectCandidate(candidate) {
  const validation = validateFiles(candidate);
  const result = {
    passed: false,
    errors: validation.errors.map(message => ({ kind: 'input', message })),
    explicitAny: [],
    typeSuppressions: [],
  };
  if (!validation.files) return result;
  const files = validation.files;
  for (const [filename, text] of Object.entries(files)) {
    const source = ts.createSourceFile(filename, text, ts.ScriptTarget.ES2022, true,
      filename.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
    for (const diagnostic of source.parseDiagnostics) {
      result.errors.push({ kind: 'syntax', ...diagnosticJson(diagnostic), file: filename });
    }
    const scanner = ts.createScanner(ts.ScriptTarget.ES2022, false,
      filename.endsWith('.tsx') ? ts.LanguageVariant.JSX : ts.LanguageVariant.Standard, text);
    for (let token = scanner.scan(); token !== ts.SyntaxKind.EndOfFileToken; token = scanner.scan()) {
      if (token !== ts.SyntaxKind.SingleLineCommentTrivia && token !== ts.SyntaxKind.MultiLineCommentTrivia) continue;
      const comment = scanner.getTokenText();
      for (const match of comment.matchAll(/@ts-(ignore|nocheck|expect-error)\b/g)) {
        const point = source.getLineAndCharacterOfPosition(scanner.getTokenPos() + match.index);
        result.typeSuppressions.push({ file: filename, line: point.line + 1, directive: `@ts-${match[1]}` });
      }
    }
    if (source.referencedFiles.length || source.typeReferenceDirectives.length || source.libReferenceDirectives.length || source.hasNoDefaultLib) {
      result.errors.push({ kind: 'safety', file: filename, message: 'Triple-slash reference directives are not allowed.' });
    }
    function reject(node, message) {
      result.errors.push({ kind: 'safety', ...position(source, node), message });
    }
    function inspectImport(node, specifier) {
      if (!specifier || !ts.isStringLiteral(specifier)) {
        reject(node, 'Module specifier must be a static string.');
      } else if (!ALLOWED_PACKAGES.has(specifier.text) && !resolveRelative(specifier.text, filename, files)) {
        reject(node, `Import is outside the candidate module allowlist: ${specifier.text}`);
      }
    }
    function walk(node) {
      if (node.kind === ts.SyntaxKind.AnyKeyword) result.explicitAny.push(position(source, node));
      if ((ts.isIdentifier(node) || ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) && BLOCKED_NAMES.has(node.text)) {
        reject(node, `Blocked runtime identifier or member: ${node.text}`);
      }
      if (ts.isIdentifier(node) && node.text.startsWith('__candidate_')) reject(node, 'Evaluator internal names are reserved.');
      if (ts.isImportDeclaration(node) || (ts.isExportDeclaration(node) && node.moduleSpecifier)) inspectImport(node, node.moduleSpecifier);
      if (ts.isImportTypeNode(node)) {
        inspectImport(node, ts.isLiteralTypeNode(node.argument) ? node.argument.literal : null);
      }
      if (ts.isImportEqualsDeclaration(node)) reject(node, 'Import-equals declarations are not allowed.');
      if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) reject(node, 'Dynamic import is not allowed.');
      if (ts.isMetaProperty(node)) reject(node, 'Meta properties are not allowed.');
      if (ts.isModuleDeclaration(node)) reject(node, 'Namespaces and ambient module augmentation are not allowed.');
      ts.forEachChild(node, walk);
    }
    walk(source);
  }
  result.passed = result.errors.length === 0;
  return result;
}

function typecheckCandidate(task, candidate, inspection = inspectCandidate(candidate)) {
  const validation = validateFiles(candidate);
  if (!validation.files) throw new Error(validation.errors.join(' '));
  if (!task || typeof task.contract_types !== 'string' || !task.contract_types.trim()) {
    throw new Error('Task must provide contract_types declaring ExpectedProps.');
  }
  const canonical = filename => path.resolve(filename).replaceAll('\\', '/').toLowerCase();
  const sources = new Map();
  for (const [name, text] of Object.entries(validation.files)) sources.set(canonical(path.join(VIRTUAL_ROOT, name)), text);
  const witnessPath = path.join(VIRTUAL_ROOT, WITNESS);
  sources.set(canonical(witnessPath), [
    "import { Component } from './Component';",
    "import type { Props as CandidateProps } from './Component';",
    "import type { ComponentType } from 'react';",
    task.contract_types,
    'const checked: ComponentType<ExpectedProps> = Component;',
    'declare const declaredProps: CandidateProps;',
    'const propsMatch: ExpectedProps = declaredProps;',
    'declare const expectedProps: ExpectedProps;',
    'const acceptsExpectedProps: CandidateProps = expectedProps;',
    'void checked;',
    'void propsMatch;',
    'void acceptsExpectedProps;',
  ].join('\n'));
  const options = {
    strict: true,
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.CommonJS,
    moduleResolution: ts.ModuleResolutionKind.Node10,
    jsx: ts.JsxEmit.ReactJSX,
    lib: ['lib.es2022.d.ts', 'lib.dom.d.ts', 'lib.dom.iterable.d.ts'],
    types: ['react', 'react-dom'],
    typeRoots: [path.join(FRONTEND, 'node_modules/@types')],
    esModuleInterop: true,
    allowSyntheticDefaultImports: true,
    forceConsistentCasingInFileNames: true,
    skipLibCheck: true,
    noEmit: true,
  };
  const host = ts.createCompilerHost(options);
  const originalRead = host.readFile.bind(host);
  const originalExists = host.fileExists.bind(host);
  const originalDirectory = host.directoryExists.bind(host);
  const directories = new Set();
  for (const filename of sources.keys()) {
    let directory = path.dirname(filename);
    while (directory !== path.dirname(directory)) {
      directories.add(canonical(directory));
      directory = path.dirname(directory);
    }
  }
  host.readFile = filename => sources.get(canonical(filename)) ?? originalRead(filename);
  host.fileExists = filename => sources.has(canonical(filename)) || originalExists(filename);
  host.directoryExists = directory => directories.has(canonical(directory)) || originalDirectory(directory);
  host.getSourceFile = (filename, languageVersion, onError) => {
    const text = host.readFile(filename);
    if (text === undefined) {
      if (onError) onError(`Cannot read ${filename}`);
      return undefined;
    }
    return ts.createSourceFile(filename, text, languageVersion, true);
  };
  const program = ts.createProgram({
    rootNames: [...Object.keys(validation.files).map(name => path.join(VIRTUAL_ROOT, name)), witnessPath],
    options,
    host,
  });
  const diagnostics = ts.getPreEmitDiagnostics(program).map(diagnosticJson);
  const compilerPassed = !diagnostics.some(item => item.category === 'error');
  return {
    status: 'completed',
    compilerPassed,
    passed: compilerPassed && inspection.typeSuppressions.length === 0 && inspection.explicitAny.length === 0,
    diagnostics,
    explicitAny: inspection.explicitAny,
    typeSuppressions: inspection.typeSuppressions,
  };
}

function recordConsole(target, level, args) {
  if (target.length >= 200) return;
  const message = args.map(value => {
    if (typeof value === 'string') return value;
    if (value === null || ['number', 'boolean', 'undefined', 'bigint'].includes(typeof value)) return String(value);
    return `[${typeof value}]`;
  }).join(' ').slice(0, 4000);
  target.push({ level, message });
}

function loadCandidate(candidate, { reviewed = false, consoleMessages = [] } = {}) {
  if (!reviewed) throw new Error('Runtime requires explicit reviewed=true authorization.');
  const inspection = inspectCandidate(candidate);
  if (!inspection.passed) throw new Error('Candidate failed the AST safety gate.');
  const files = candidate.files;
  const modules = new Map();
  const allowed = new Map([...ALLOWED_PACKAGES].map(name => [name, frontendRequire(name)]));
  const sandbox = Object.create(null);
  // These globals refer only to the newly installed, resource-disabled JSDOM.
  // Its normal DOM APIs support keyboard focus and refs in candidate components.
  if (globalThis.window) sandbox.window = globalThis.window;
  if (globalThis.document) sandbox.document = globalThis.document;
  for (const name of ['Node', 'Element', 'HTMLElement', 'HTMLInputElement', 'HTMLButtonElement',
    'HTMLSelectElement', 'HTMLTextAreaElement', 'HTMLFormElement', 'Event', 'MouseEvent', 'KeyboardEvent', 'FocusEvent']) {
    if (globalThis.window?.[name]) sandbox[name] = globalThis.window[name];
  }
  sandbox.console = Object.freeze(Object.fromEntries(['log', 'info', 'warn', 'error', 'debug'].map(level => [
    level, (...args) => recordConsole(consoleMessages, level, args),
  ])));
  const context = vm.createContext(sandbox, { name: 'reviewed-react-candidate', codeGeneration: { strings: false, wasm: false } });
  function load(filename) {
    if (modules.has(filename)) return modules.get(filename).exports;
    const result = ts.transpileModule(files[filename], {
      fileName: filename,
      compilerOptions: {
        target: ts.ScriptTarget.ES2022,
        module: ts.ModuleKind.CommonJS,
        jsx: ts.JsxEmit.ReactJSX,
        esModuleInterop: true,
      },
      reportDiagnostics: true,
    });
    const errors = (result.diagnostics || []).filter(item => item.category === ts.DiagnosticCategory.Error);
    if (errors.length) throw new Error(errors.map(item => ts.flattenDiagnosticMessageText(item.messageText, '\n')).join('\n'));
    const module = { exports: {} };
    modules.set(filename, module);
    const localRequire = specifier => {
      if (allowed.has(specifier)) return allowed.get(specifier);
      const relative = resolveRelative(specifier, filename, files);
      if (!relative) throw new Error(`Runtime import is not permitted: ${specifier}`);
      return load(relative);
    };
    // Top-level execution is bounded here; compilation and React callbacks are
    // bounded by the caller's whole-child-process timeout.
    sandbox.__candidate_module = module;
    sandbox.__candidate_require = localRequire;
    try {
      const script = new vm.Script(`(function (exports, require, module) {\n${result.outputText}\n})(__candidate_module.exports, __candidate_require, __candidate_module);`, { filename });
      script.runInContext(context, { timeout: 2000 });
    } finally {
      delete sandbox.__candidate_module;
      delete sandbox.__candidate_require;
    }
    return module.exports;
  }
  return load('Component.tsx');
}

function expectedTestNames(runtime, taskId) {
  const names = typeof runtime.testNames === 'function' ? runtime.testNames(taskId) : runtime.testNames?.[taskId];
  if (!Array.isArray(names) || !names.length || names.some(name => typeof name !== 'string') || new Set(names).size !== names.length) {
    throw new Error(`Runtime must declare nonempty unique testNames for ${taskId}.`);
  }
  return names;
}

async function evaluateCandidate(task, candidate, { reviewed = false, runtime } = {}) {
  const inspection = inspectCandidate(candidate);
  const report = {
    evaluatorVersion: 'coding-react-current-v1',
    taskId: task?.id ?? null,
    safety: inspection,
    types: { status: 'skipped', passed: false, reason: 'safety_gate' },
    runtime: { status: 'skipped', passed: false, reason: 'safety_gate', checks: [] },
    console: [],
  };
  if (!inspection.passed) return report;
  try {
    report.types = typecheckCandidate(task, candidate, inspection);
  } catch (error) {
    report.types = { status: 'harness_error', passed: false, error: errorText(error) };
  }
  if (!reviewed) {
    report.runtime.reason = 'explicit_review_required';
    return report;
  }
  let stage = 'harness';
  let installed = false;
  const originalConsole = Object.fromEntries(['log', 'info', 'warn', 'error', 'debug'].map(level => [level, console[level]]));
  try {
    runtime = runtime || require('./runtime.cjs');
    const names = expectedTestNames(runtime, task.id);
    if (typeof runtime.installDom !== 'function' || typeof runtime.cleanupDom !== 'function' || typeof runtime.runTask !== 'function') {
      throw new Error('Runtime must export installDom, cleanupDom, and runTask.');
    }
    for (const level of Object.keys(originalConsole)) console[level] = (...args) => recordConsole(report.console, level, args);
    installed = true;
    await runtime.installDom();
    stage = 'candidate_load';
    const exports = loadCandidate(candidate, { reviewed: true, consoleMessages: report.console });
    stage = 'runtime';
    const checks = await runtime.runTask(task.id, exports);
    stage = 'harness';
    if (!Array.isArray(checks) || checks.length !== names.length ||
        new Set(checks.map(check => check?.name)).size !== names.length ||
        checks.some(check => !names.includes(check?.name) || typeof check.passed !== 'boolean')) {
      throw new Error('Runtime returned missing, duplicate, unexpected, or malformed checks.');
    }
    report.runtime = {
      status: 'completed',
      passed: checks.every(check => check.passed),
      checks: checks.map(check => ({ name: check.name, passed: check.passed, ...(check.error ? { error: String(check.error) } : {}) })),
    };
  } catch (error) {
    report.runtime = {
      status: stage === 'candidate_load' ? 'candidate_error' : 'harness_error',
      passed: false,
      stage,
      error: errorText(error),
      checks: [],
    };
  } finally {
    if (installed) {
      try { await runtime.cleanupDom(); }
      catch (error) {
        report.runtime = { ...report.runtime, status: 'harness_error', passed: false, cleanupError: errorText(error) };
      }
    }
    for (const [level, original] of Object.entries(originalConsole)) console[level] = original;
  }
  return report;
}

async function main(argv = process.argv.slice(2)) {
  if (argv.length !== 3 || argv[2] !== '--reviewed') {
    throw new Error('Usage: node evaluate.cjs <taskId> <candidate.json> --reviewed. Review source before authorizing local execution.');
  }
  const [taskId, candidatePath] = argv;
  const taskData = JSON.parse(fs.readFileSync(path.join(__dirname, 'tasks.json'), 'utf8'));
  const tasks = Array.isArray(taskData) ? taskData : taskData.tasks;
  const task = tasks?.find(item => item.id === taskId);
  if (!task) throw new Error(`Unknown task: ${taskId}`);
  if (fs.statSync(candidatePath).size > MAX_SOURCE_BYTES * 2) throw new Error('Candidate JSON file exceeds the input size limit.');
  const candidate = JSON.parse(fs.readFileSync(candidatePath, 'utf8'));
  return evaluateCandidate(task, candidate, { reviewed: true });
}

module.exports = { inspectCandidate, typecheckCandidate, loadCandidate, evaluateCandidate, resolveRelative, main };

if (require.main === module) {
  main().then(report => process.stdout.write(`${JSON.stringify(report)}\n`)).catch(error => {
    process.stdout.write(`${JSON.stringify({ evaluatorVersion: 'coding-react-current-v1', fatalError: errorText(error) })}\n`);
    process.exitCode = 2;
  });
}

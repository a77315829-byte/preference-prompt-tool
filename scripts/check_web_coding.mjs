// Parse generated source with the installed TypeScript parser. Never import/eval it.
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
const require = createRequire(new URL('../frontend/package.json', import.meta.url));
const ts = require('typescript');
const input = JSON.parse(readFileSync(0, 'utf8'));
const { task, codes, language, mode } = input;
const checks = { syntax: false, binding: false, validation: false, calculation: false };
const RESPONSE = Symbol('response'), ELEMENT = Symbol('element'), SOURCE = Symbol('source');
const COMPUTED = Symbol('computed'), TEMPLATE = Symbol('vue-template');
const SEARCH_PARAMS = Symbol('search-params');
const NEST_INSTANCE = Symbol('nest-instance'), NEST_ERROR = Symbol('nest-error'), THIS = Symbol('this');
let steps = 0;
const own = (object, key) => object != null && Object.hasOwn(object, key);
const text = node => node.getText();
const fail = () => { throw new Error('Unsupported source pattern'); };

function parse(code) {
  const source = ts.createSourceFile(language === 'TypeScript' ? 'answer.tsx' : 'answer.jsx', code, ts.ScriptTarget.Latest, true,
    language === 'TypeScript' ? ts.ScriptKind.TSX : ts.ScriptKind.JSX);
  if (source.parseDiagnostics.length) fail();
  let count = 0, stack = [[source, 0]];
  while (stack.length) {
    const [node, depth] = stack.pop();
    if (++count > 8000 || depth > 70) fail();
    if (language === 'JavaScript' && (node.type || ts.isTypeAliasDeclaration(node) || ts.isInterfaceDeclaration(node) || ts.isAsExpression(node))) fail();
    ts.forEachChild(node, child => { stack.push([child, depth + 1]); });
  }
  return source;
}

function catalog(sources) {
  const functions = new Map(), globals = new Map(), imports = new Map(), calls = [];
  const add = (name, value, destination) => { if (destination.has(name)) fail(); destination.set(name, value); };
  for (const source of sources) {
    for (const node of source.statements) {
      if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
        if (node.importClause?.name) imports.set(text(node.importClause.name), node.moduleSpecifier.text);
        if (node.importClause?.namedBindings && ts.isNamedImports(node.importClause.namedBindings)) for (const item of node.importClause.namedBindings.elements) imports.set(text(item.name), node.moduleSpecifier.text);
      }
      if (ts.isFunctionDeclaration(node) && node.name) { node.origin = source; add(text(node.name), node, functions); }
      if (ts.isVariableStatement(node)) for (const declaration of node.declarationList.declarations) {
        if (!ts.isIdentifier(declaration.name) || !declaration.initializer) continue;
        const name = text(declaration.name), value = declaration.initializer;
        value.origin = source;
        add(name, value, ts.isArrowFunction(value) || ts.isFunctionExpression(value) ? functions : globals);
      }
    }
    const stack = [source];
    while (stack.length) { const node = stack.pop(); if (ts.isCallExpression(node)) calls.push(node); ts.forEachChild(node, child => { stack.push(child); }); }
  }
  return { functions, globals, imports, calls };
}

function bind(name, value, env) {
  if (ts.isIdentifier(name)) { env[text(name)] = value; return; }
  if (ts.isObjectBindingPattern(name)) {
    for (const item of name.elements) {
      if (item.dotDotDotToken || item.initializer) fail();
      const key = item.propertyName ? text(item.propertyName) : text(item.name);
      bind(item.name, own(value, key) ? value[key] : undefined, env);
    }
    return;
  }
  fail();
}

function invoke(fn, args, state, depth, receiver = null) {
  if (depth > 20 || fn.parameters.length !== args.length) fail();
  const env = Object.create(null);
  env[SOURCE] = fn.origin;
  if (state.nest) env[THIS] = receiver;
  fn.parameters.forEach((parameter, index) => bind(parameter.name, args[index], env));
  if (!ts.isBlock(fn.body)) return value(fn.body, env, state, depth + 1);
  return statements(fn.body.statements, env, state, depth + 1).value;
}

function statements(nodes, env, state, depth) {
  for (const node of nodes) {
    if (++steps > 2000 || depth > 30) fail();
    if (ts.isReturnStatement(node)) return { returned: true, value: value(node.expression, env, state, depth + 1) };
    if (state.nest && ts.isThrowStatement(node)) {
      const error = value(node.expression,env,state,depth + 1);
      if (!error?.[NEST_ERROR]) fail();
      throw error;
    }
    if (ts.isVariableStatement(node)) { for (const declaration of node.declarationList.declarations) bind(declaration.name, value(declaration.initializer, env, state, depth + 1), env); continue; }
    if (ts.isIfStatement(node)) {
      const branch = value(node.expression, env, state, depth + 1) ? node.thenStatement : node.elseStatement;
      if (branch) { const result = statements(ts.isBlock(branch) ? branch.statements : [branch], env, state, depth + 1); if (result.returned) return result; }
      continue;
    }
    if (ts.isBlock(node)) { const result = statements(node.statements, env, state, depth + 1); if (result.returned) return result; continue; }
    // Response sends without return are allowed only as the final statement.
    if (ts.isExpressionStatement(node) && node === nodes[nodes.length - 1]) return { returned: true, value: value(node.expression, env, state, depth + 1) };
    fail();
  }
  return { returned: false, value: undefined };
}

function value(node, env, state, depth = 0) {
  if (!node || ++steps > 2000 || depth > 35) fail();
  if (ts.isParenthesizedExpression(node) || ts.isAsExpression(node) || ts.isNonNullExpression(node)) return value(node.expression, env, state, depth + 1);
  if (ts.isNumericLiteral(node)) { const n = Number(node.text); if (Math.abs(n) > 1e8) fail(); return n; }
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text;
  if (node.kind === ts.SyntaxKind.TrueKeyword) return true;
  if (node.kind === ts.SyntaxKind.FalseKeyword) return false;
  if (state.nest && node.kind === ts.SyntaxKind.ThisKeyword && env[THIS]) return env[THIS];
  if (mode === 'nextjs' && node.kind === ts.SyntaxKind.NullKeyword) return null;
  if (ts.isIdentifier(node)) {
    const name = text(node);
    if (own(env, name)) return env[TEMPLATE] && env[name]?.[COMPUTED] ? computedValue(env[name], state, depth + 1) : env[name];
    if (name === 'undefined') return undefined;
    if (state.globals.has(name)) return value(state.globals.get(name), env, state, depth + 1);
    fail();
  }
  if (ts.isPropertyAccessExpression(node)) { const object = value(node.expression, env, state, depth + 1), key = text(node.name); return object?.[COMPUTED] && key === 'value' ? computedValue(object,state,depth + 1) : own(object, key) ? object[key] : undefined; }
  if (ts.isObjectLiteralExpression(node)) {
    const result = Object.create(null);
    for (const property of node.properties) {
      if (ts.isPropertyAssignment(property)) result[ts.isStringLiteral(property.name) ? property.name.text : text(property.name)] = value(property.initializer, env, state, depth + 1);
      else if (ts.isShorthandPropertyAssignment(property)) result[text(property.name)] = value(property.name, env, state, depth + 1);
      else fail();
    }
    return result;
  }
  if (ts.isPrefixUnaryExpression(node)) {
    const operand = value(node.operand, env, state, depth + 1);
    if (node.operator === ts.SyntaxKind.ExclamationToken) return !operand;
    if (node.operator === ts.SyntaxKind.MinusToken && typeof operand === 'number') return -operand;
    fail();
  }
  if (ts.isBinaryExpression(node)) {
    const operator = node.operatorToken.kind, left = value(node.left, env, state, depth + 1);
    if (operator === ts.SyntaxKind.BarBarToken) return left || value(node.right, env, state, depth + 1);
    if (operator === ts.SyntaxKind.AmpersandAmpersandToken) return left && value(node.right, env, state, depth + 1);
    if (mode === 'nextjs' && operator === ts.SyntaxKind.QuestionQuestionToken) return left ?? value(node.right,env,state,depth + 1);
    const right = value(node.right, env, state, depth + 1);
    if (['nextjs','nestjs'].includes(mode) && [ts.SyntaxKind.EqualsEqualsEqualsToken,ts.SyntaxKind.ExclamationEqualsEqualsToken].includes(operator)) return operator === ts.SyntaxKind.EqualsEqualsEqualsToken ? left === right : left !== right;
    if (typeof left !== 'number' || typeof right !== 'number' || Math.max(Math.abs(left), Math.abs(right)) > 1e12) fail();
    if (operator === ts.SyntaxKind.PlusToken) return left + right;
    if (operator === ts.SyntaxKind.MinusToken) return left - right;
    if (operator === ts.SyntaxKind.AsteriskToken) return left * right;
    if (operator === ts.SyntaxKind.LessThanToken) return left < right;
    if (operator === ts.SyntaxKind.GreaterThanToken) return left > right;
    if (operator === ts.SyntaxKind.EqualsEqualsEqualsToken) return left === right;
    fail();
  }
  if (ts.isConditionalExpression(node)) return value(value(node.condition, env, state, depth + 1) ? node.whenTrue : node.whenFalse, env, state, depth + 1);
  if (state.nest && ts.isNewExpression(node) && ts.isIdentifier(node.expression) && state.nest.common(env[SOURCE],text(node.expression)) === 'BadRequestException') {
    if (node.arguments?.length !== 1) fail();
    const message = value(node.arguments[0],env,state,depth + 1);
    if (typeof message !== 'string') fail();
    return { [NEST_ERROR]:true,status:400,message };
  }
  if (mode === 'nextjs' && ts.isNewExpression(node) && ts.isIdentifier(node.expression) && text(node.expression) === 'URL' && node.arguments?.length === 1) {
    const url = value(node.arguments[0],env,state,depth + 1);
    if (typeof url !== 'string' || url.length > 2000) fail();
    return { searchParams:{ [SEARCH_PARAMS]:true,params:new URL(url).searchParams } };
  }
  if (ts.isCallExpression(node)) {
    const fn = node.expression;
    if (state.vueImports?.get(text(fn)) === 'computed' && node.arguments.length === 1) {
      const callback = node.arguments[0];
      if (!ts.isArrowFunction(callback) || callback.parameters.length) fail();
      return { [COMPUTED]:true, body:callback.body, env };
    }
    const args = node.arguments.map(argument => value(argument, env, state, depth + 1));
    if (ts.isIdentifier(fn)) {
      if (text(fn) === 'Number' && args.length === 1 && (['string', 'number', 'undefined'].includes(typeof args[0]) || (mode === 'nextjs' && args[0] === null))) return Number(args[0]);
      if (state.functions.has(text(fn))) {
        const target = state.functions.get(text(fn));
        if (target.origin !== env[SOURCE] && !state.imports.has(text(fn))) fail();
        return invoke(target, args, state, depth + 1);
      }
    }
    if (ts.isPropertyAccessExpression(fn)) {
      const name = text(fn.name);
      if (ts.isIdentifier(fn.expression) && text(fn.expression) === 'Number' && name === 'isFinite' && args.length === 1) return Number.isFinite(args[0]);
      if (mode === 'nextjs' && ts.isIdentifier(fn.expression) && name === 'json' && (text(fn.expression) === 'Response' || state.nextResponses?.has(text(fn.expression)))) {
        if (args.length < 1 || args.length > 2 || (args[1] !== undefined && (args[1] === null || typeof args[1] !== 'object' || Object.keys(args[1]).some(key => key !== 'status')))) fail();
        const status = args[1]?.status ?? 200;
        if (![200,400].includes(status)) fail();
        return { [RESPONSE]:true,status,body:args[0] };
      }
      const receiver = value(fn.expression, env, state, depth + 1);
      if (state.nest && receiver?.[NEST_INSTANCE]) return state.nest.method(receiver,name,args,depth + 1);
      if (mode === 'nextjs' && receiver?.[SEARCH_PARAMS] && name === 'get' && args.length === 1 && typeof args[0] === 'string') return receiver.params.get(args[0]);
      if (['nextjs','nestjs'].includes(mode) && typeof receiver === 'string' && name === 'trim' && !args.length) return receiver.trim();
      if (receiver?.[RESPONSE] && name === 'status' && args.length === 1 && [200, 400].includes(args[0])) return { [RESPONSE]: true, status: args[0] };
      if (receiver?.[RESPONSE] && name === 'json' && args.length === 1) return { [RESPONSE]: true, status: receiver.status, body: args[0] };
    }
    fail();
  }
  if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
    const opening = ts.isJsxElement(node) ? node.openingElement : node;
    const tag = text(opening.tagName), attrs = Object.create(null), children = [];
    for (const attribute of opening.attributes.properties) {
      if (!ts.isJsxAttribute(attribute)) fail();
      attrs[text(attribute.name)] = !attribute.initializer ? true : ts.isStringLiteral(attribute.initializer) ? attribute.initializer.text : value(attribute.initializer.expression, env, state, depth + 1);
    }
    if (ts.isJsxElement(node)) for (const child of node.children) {
      if (ts.isJsxText(child)) children.push(child.text.trim());
      else if (ts.isJsxExpression(child)) { if (child.expression) children.push(value(child.expression, env, state, depth + 1)); }
      else children.push(value(child, env, state, depth + 1));
    }
    if (state.functions.has(tag)) {
      const target = state.functions.get(tag);
      if (target.origin !== env[SOURCE] && !state.imports.has(tag)) fail();
      return invoke(target, [{ ...attrs, children }], state, depth + 1);
    }
    return { [ELEMENT]: true, tag, attrs, children };
  }
  fail();
}

function elements(tree) {
  if (!tree?.[ELEMENT]) return [];
  return [tree, ...tree.children.flatMap(elements)];
}
function content(tree) {
  return tree?.[ELEMENT] ? tree.children.map(content).join('') : typeof tree === 'string' || typeof tree === 'number' ? String(tree) : '';
}

function computedValue(item, state, depth) {
  if (depth > 30 || ++steps > 2000) fail();
  return ts.isBlock(item.body) ? statements(item.body.statements,{ ...item.env },state,depth + 1).value : value(item.body,item.env,state,depth + 1);
}

function checkNestjs() {
  if (language !== 'TypeScript') fail();
  const wrapped = new Set();
  const sources = codes.map(code => {
    try { return parse(code); }
    catch {
      if (!task.patch) fail();
      const source = parse(`class __NestPatch {\n${code}\n}`);
      if (source.statements.length !== 1 || source.statements[0].members.length !== 1 || !ts.isMethodDeclaration(source.statements[0].members[0])) fail();
      wrapped.add(source); return source;
    }
  });
  const returnSources = sources.filter(source => source.statements.length === 1 && ts.isReturnStatement(source.statements[0]));
  if (wrapped.size + returnSources.length > 1) fail();
  const partial = Boolean(task.patch && (wrapped.size || returnSources.length));
  const baseline = partial ? parse(task.original) : null;
  const allSources = baseline ? [baseline,...sources] : sources;
  const state = catalog(allSources), imports = new Map(), classes = new Map();
  for (const source of allSources) {
    const names = new Map(); imports.set(source,names);
    for (const node of source.statements) {
      if (ts.isImportDeclaration(node)) {
        if (node.importClause?.namedBindings && ts.isNamedImports(node.importClause.namedBindings)) for (const item of node.importClause.namedBindings.elements) {
          if (names.has(text(item.name))) fail();
          names.set(text(item.name),{ module:node.moduleSpecifier.text,name:text(item.propertyName || item.name),typeOnly:node.importClause.isTypeOnly || item.isTypeOnly });
        }
      } else if (ts.isClassDeclaration(node)) {
        if (wrapped.has(source)) continue;
        if (!node.name || classes.has(text(node.name)) || node.heritageClauses?.length) fail();
        const model = { node,source,methods:new Map() };
        for (const member of node.members) {
          if (ts.isMethodDeclaration(member) && member.name && member.body) {
            const name = text(member.name);
            if (model.methods.has(name) || member.modifiers?.some(item => item.kind === ts.SyntaxKind.StaticKeyword)) fail();
            member.origin = source; model.methods.set(name,member);
          } else if (!ts.isConstructorDeclaration(member)) fail();
        }
        classes.set(text(node.name),model);
      } else if (!ts.isFunctionDeclaration(node) && !ts.isVariableStatement(node) && !ts.isInterfaceDeclaration(node) && !ts.isTypeAliasDeclaration(node) && !(partial && ts.isReturnStatement(node))) fail();
    }
  }
  if (partial) {
    for (const source of sources) for (const [name,binding] of imports.get(source)) imports.get(baseline).set(name,binding);
    const model = classes.get('QuoteController'), prior = model?.methods.get(task.entry);
    if (!prior) fail();
    if (wrapped.size) {
      const snippet = [...wrapped][0].statements[0].members[0];
      if (text(snippet.name) !== task.entry) fail();
      snippet.origin = baseline; model.methods.set(task.entry,snippet);
    } else model.methods.set(task.entry,{ ...prior,body:{ ...prior.body,statements:[...prior.body.statements.slice(0,-1),returnSources[0].statements[0]] } });
  }
  const common = (source,name) => {
    const entry = imports.get(source)?.get(name);
    return entry?.module === '@nestjs/common' && !entry.typeOnly ? entry.name : undefined;
  };
  const decorator = (node,kind,source) => {
    const matches = (ts.getDecorators(node) || []).map(item => item.expression).filter(expr => ts.isCallExpression(expr) && ts.isIdentifier(expr.expression) && common(source,text(expr.expression)) === kind);
    if (matches.length > 1) fail();
    return matches[0];
  };
  const literal = call => {
    if (!call || call.arguments.length !== 1 || !ts.isStringLiteral(call.arguments[0])) fail();
    return call.arguments[0].text;
  };
  const resolveClass = (source,name) => {
    const local = classes.get(name);
    if (local?.source === source) return local;
    const binding = imports.get(source)?.get(name);
    if (!binding || binding.typeOnly) fail();
    const target = classes.get(binding.name);
    if (!target) fail();
    return target;
  };
  const reserved = new Set(['Number']);
  for (const [source,names] of imports) for (const name of names.keys()) if (common(source,name)) reserved.add(name);
  for (const name of reserved) if (state.functions.has(name) || state.globals.has(name) || classes.has(name) || name === 'Number' && state.imports.has(name)) fail();
  for (const source of allSources) {
    const stack = [source];
    while (stack.length) {
      const node = stack.pop();
      if (ts.isDecorator(node)) {
        const expression = node.expression;
        const sourceContext = wrapped.has(source) ? baseline : source;
        if (!ts.isCallExpression(expression) || !ts.isIdentifier(expression.expression) || !['Controller','Get','Query','Module','Injectable'].includes(common(sourceContext,text(expression.expression)))) fail();
      }
      if ((ts.isParameter(node) || ts.isVariableDeclaration(node)) && (!ts.isIdentifier(node.name) || reserved.has(text(node.name)))) fail();
      ts.forEachChild(node,child => { stack.push(child); });
    }
  }
  state.nest = { common,method(instance,name,args,depth) {
    const method = instance[NEST_INSTANCE].methods.get(name);
    if (!method) fail();
    return invoke(method,args,state,depth,instance);
  } };
  const instantiate = (model,providers,depth=0,service=false) => {
    if (depth > 10 || service && !decorator(model.node,'Injectable',model.source)) fail();
    const result = { [NEST_INSTANCE]:model };
    const constructors = model.node.members.filter(ts.isConstructorDeclaration);
    if (constructors.length > 1) fail();
    for (const ctor of constructors) {
      if (!ctor.body || ctor.body.statements.length) fail();
      for (const param of ctor.parameters) {
        if (!ts.isIdentifier(param.name) || !ts.isTypeReferenceNode(param.type) || !ts.isIdentifier(param.type.typeName) || !param.modifiers?.some(item => [ts.SyntaxKind.PrivateKeyword,ts.SyntaxKind.PublicKeyword,ts.SyntaxKind.ProtectedKeyword,ts.SyntaxKind.ReadonlyKeyword].includes(item.kind)) || ts.getDecorators(param)?.length || param.initializer) fail();
        const dependency = resolveClass(model.source,text(param.type.typeName));
        if (!providers.has(dependency)) fail();
        result[text(param.name)] = instantiate(dependency,providers,depth+1,true);
      }
    }
    return result;
  };
  checks.syntax = true;
  const candidates = [];
  for (const module of classes.values()) {
    const registration = decorator(module.node,'Module',module.source);
    if (!registration) continue;
    if (registration.arguments.length !== 1 || !ts.isObjectLiteralExpression(registration.arguments[0])) fail();
    const lists = new Map();
    for (const property of registration.arguments[0].properties) {
      if (!ts.isPropertyAssignment(property) || lists.has(text(property.name)) || !['controllers','providers'].includes(text(property.name)) || !ts.isArrayLiteralExpression(property.initializer)) fail();
      lists.set(text(property.name),property.initializer.elements.map(item => { if (!ts.isIdentifier(item)) fail(); return resolveClass(module.source,text(item)); }));
    }
    for (const controller of lists.get('controllers') || []) {
      const prefix = literal(decorator(controller.node,'Controller',controller.source));
      for (const method of controller.methods.values()) {
        const get = decorator(method,'Get',method.origin);
        if (!get) continue;
        const route = '/' + [prefix,literal(get)].map(part => part.replace(/^\/+|\/+$/g,'')).filter(Boolean).join('/');
        if (route !== task.route) continue;
        const queries = method.parameters.map(param => literal(decorator(param,'Query',method.origin)));
        if (queries.length !== 2 || new Set(queries).size !== 2 || !queries.includes(task.left) || !queries.includes(task.right)) continue;
        const instance = instantiate(controller,new Set(lists.get('providers') || []));
        candidates.push({ method,instance,queries });
      }
    }
  }
  checks.binding = candidates.length === 1;
  const complete = !partial && checks.binding;
  if (checks.binding) {
    const { method,instance,queries } = candidates[0];
    const run = (a,b) => {
      steps=0;
      const query = { [task.left]:a === undefined ? undefined : String(a),[task.right]:b === undefined ? undefined : String(b) };
      try { return { body:invoke(method,queries.map(key => query[key]),state,0,instance),status:200 }; }
      catch(error) { if (!error?.[NEST_ERROR]) throw error; return error; }
    };
    checks.validation = [[-1,1],[1,-1],[undefined,1],[1,undefined],['',1],[1,''],['  ',1],[1,'  '],['abc',1],[1,'abc'],['Infinity',1],[1,'Infinity']].every(([a,b]) => run(a,b).status === 400);
    checks.calculation = [[0,0],[7,3],[19,2]].every(([a,b]) => {
      const result = run(a,b);
      return result.status === 200 && Object.keys(result.body || {}).length === 1 && result.body?.[task.key] === a*b+task.fee;
    });
  }
  return { checks,has_import:complete,complete,partial };
}

function checkNextjs() {
  const sources = codes.map(parse), raw = catalog(sources), baseline = parse(task.original);
  const exported = fn => {
    if (!fn) return false;
    const declaration = ts.isFunctionDeclaration(fn) ? fn : fn.parent?.parent?.parent;
    return Boolean(declaration?.modifiers?.some(item => item.kind === ts.SyntaxKind.ExportKeyword)) && !declaration.modifiers.some(item => item.kind === ts.SyntaxKind.DefaultKeyword);
  };
  const replacement = raw.functions.get('GET');
  let partial = false, state = raw, origin = replacement?.origin;
  const returnOnly = sources.length === 1 && sources[0].statements.length === 1 && ts.isReturnStatement(sources[0].statements[0]);
  if (task.patch && (returnOnly || (replacement && !exported(replacement)))) {
    state = catalog([baseline]);
    const prior = state.functions.get('GET');
    state.functions.set('GET',replacement ? { ...prior,parameters:replacement.parameters,body:replacement.body,origin:replacement.origin } :
      { ...prior,body:{ ...prior.body,statements:[...prior.body.statements.slice(0,-1),sources[0].statements[0]] } });
    for (const [name,fn] of raw.functions) if (name !== 'GET') state.functions.set(name,fn);
    for (const [name,node] of raw.globals) state.globals.set(name,node);
    for (const [name,module] of raw.imports) state.imports.set(name,module);
    partial = true; origin = baseline;
  }
  state.nextResponses = new Set();
  for (const source of partial ? [baseline,...sources] : sources) {
    for (const node of source.statements) {
      if (ts.isImportDeclaration(node)) {
        if (node.moduleSpecifier.text === 'next/server' && !node.importClause?.isTypeOnly && node.importClause?.namedBindings && ts.isNamedImports(node.importClause.namedBindings)) {
          for (const item of node.importClause.namedBindings.elements) if (!item.isTypeOnly && text(item.propertyName || item.name) === 'NextResponse') state.nextResponses.add(text(item.name));
        }
      } else if (!ts.isFunctionDeclaration(node) && !ts.isVariableStatement(node) && !ts.isInterfaceDeclaration(node) && !ts.isTypeAliasDeclaration(node) && !(partial && ts.isReturnStatement(node))) fail();
    }
  }
  const reserved = new Set(['Number','URL','Response',...state.nextResponses]);
  for (const name of reserved) if (state.functions.has(name) || state.globals.has(name) || (['Number','URL','Response'].includes(name) && state.imports.has(name))) fail();
  for (const source of sources) {
    const stack = [source];
    while (stack.length) {
      const node = stack.pop();
      if ((ts.isParameter(node) || ts.isVariableDeclaration(node)) && (!ts.isIdentifier(node.name) ? node.name.elements.some(item => reserved.has(text(item.name))) : reserved.has(text(node.name)))) fail();
      ts.forEachChild(node,child => { stack.push(child); });
    }
  }
  checks.syntax = true;
  const fn = state.functions.get('GET');
  const filename = input.file_names?.[sources.indexOf(origin)];
  const complete = Boolean(replacement && exported(replacement) && [task.file,'src/'+task.file].includes(filename));
  checks.binding = Boolean(fn && fn.parameters.length === 1 && (partial || complete));
  const run = (a,b) => {
    steps = 0;
    const url = new URL('https://evaluation.invalid'+task.route);
    if (a !== undefined) url.searchParams.set(task.left,String(a));
    if (b !== undefined) url.searchParams.set(task.right,String(b));
    const searchParams = { [SEARCH_PARAMS]:true,params:url.searchParams };
    return invoke(fn,[{ url:String(url),nextUrl:{ searchParams } }],state,0);
  };
  if (checks.binding) {
    checks.validation = [[-1,1],[1,-1],[undefined,1],[1,undefined],['',1],[1,''],['  ',1],[1,'  '],['abc',1],[1,'abc'],['Infinity',1],[1,'Infinity']].every(([a,b]) => {
      const result = run(a,b);
      return result?.[RESPONSE] && result.status === 400 && typeof result.body?.error === 'string';
    });
    checks.calculation = [[0,0],[7,3],[19,2]].every(([a,b]) => {
      const result = run(a,b);
      return result?.[RESPONSE] && result.status === 200 && Object.keys(result.body || {}).length === 1 && result.body?.[task.key] === a*b+task.fee;
    });
  }
  return { checks,has_import:complete,complete,partial };
}

// Conservative Vue subset. This reads SFC blocks and template expressions; it is
// not a Vue compiler and never executes or imports the supplied component.
function vueBlocks(code) {
  const result = {};
  let rest = code.trim();
  while (rest) {
    const match = /^<(script|template|style)\b([^>]*)>([\s\S]*?)<\/\1>\s*/.exec(rest);
    if (!match || own(result, match[1])) fail();
    const [, tag, attributes, body] = match;
    if (tag === 'script') {
      const expected = language === 'TypeScript' ? /^\s*setup\s+lang\s*=\s*(['"])ts\1\s*$/ : /^\s*setup\s*$/;
      if (!expected.test(attributes)) fail();
    } else if (tag === 'template' && attributes.trim()) fail();
    result[tag] = body;
    rest = rest.slice(match[0].length).trim();
  }
  return result;
}

function expression(source) {
  const file = parse(`const __vue_expression = (${source});`);
  if (file.statements.length !== 1 || !ts.isVariableStatement(file.statements[0])) fail();
  return file.statements[0].declarationList.declarations[0].initializer;
}

function vueTemplate(source) {
  const root = { tag: 'root', attrs: {}, children: [] }, stack = [root];
  let offset = 0, count = 0;
  while (offset < source.length) {
    if (++count > 2000 || stack.length > 35) fail();
    const rest = source.slice(offset);
    if (rest.startsWith('<!--')) {
      const end = rest.indexOf('-->'); if (end < 0) fail(); offset += end + 3; continue;
    }
    if (rest.startsWith('{{')) {
      const end = rest.indexOf('}}'); if (end < 0) fail();
      stack.at(-1).children.push({ expression: expression(rest.slice(2, end)) }); offset += end + 2; continue;
    }
    if (rest.startsWith('<')) {
      const match = /^<\/?[a-z][\w-]*(?:\s+[^<>"']*|"[^"]*"|'[^']*')*\s*\/?\s*>/i.exec(rest);
      if (!match) fail();
      const token = match[0], closing = token.startsWith('</'), tag = /^<\/?([\w-]+)/.exec(token)[1];
      if (!['output','p','div','section','span'].includes(tag)) fail();
      if (closing) {
        if (token !== `</${tag}>` || stack.length < 2 || stack.pop().tag !== tag) fail();
      } else {
        const attrs = Object.create(null);
        let remainder = token.slice(tag.length + 1).replace(/\/?\s*>$/, '').trim();
        while (remainder) {
          const attribute = /^([\w:-]+)(?:\s*=\s*("[^"]*"|'[^']*'))?(?:\s+|$)/.exec(remainder);
          if (!attribute) fail();
          const [, key, quoted] = attribute;
          if (!['v-if','v-else-if','v-else','data-testid','class','role'].includes(key) || own(attrs,key)) fail();
          if ((key === 'v-else') === Boolean(quoted)) fail();
          attrs[key] = quoted ? quoted.slice(1,-1) : true;
          if (key === 'v-if' || key === 'v-else-if') attrs[key] = expression(attrs[key]);
          remainder = remainder.slice(attribute[0].length).trim();
        }
        if (['v-if','v-else-if','v-else'].filter(key => own(attrs,key)).length > 1) fail();
        const node = { tag, attrs, children: [] };
        stack.at(-1).children.push(node);
        if (!/\/\s*>$/.test(token)) stack.push(node);
      }
      offset += token.length; continue;
    }
    const match = /^[^<{]+/.exec(rest); if (!match) fail();
    if (match[0].trim()) stack.at(-1).children.push(match[0].trim());
    offset += match[0].length;
  }
  if (stack.length !== 1) fail();
  return root;
}

function renderVue(nodes, env, state) {
  const result = []; let chain = null;
  for (const node of nodes) {
    if (++steps > 2000) fail();
    if (typeof node === 'string') { result.push(node); chain = null; continue; }
    if (node.expression) {
      const evaluated = value(node.expression, env, state);
      if (!['string','number'].includes(typeof evaluated)) fail();
      result.push(evaluated); chain = null; continue;
    }
    let show = true;
    if (own(node.attrs,'v-if')) { show = Boolean(value(node.attrs['v-if'],env,state)); chain = show; }
    else if (own(node.attrs,'v-else-if') || own(node.attrs,'v-else')) {
      if (chain === null) fail();
      show = !chain && (!own(node.attrs,'v-else-if') || Boolean(value(node.attrs['v-else-if'],env,state)));
      chain ||= show;
      if (own(node.attrs,'v-else')) chain = null;
    } else chain = null;
    if (show) result.push({ [ELEMENT]:true,tag:node.tag,attrs:node.attrs,children:renderVue(node.children,env,state) });
  }
  return result;
}

function checkVue() {
  let blocks = {}, helpers = [], full = false, partial = false;
  for (const code of codes) {
    if (code.trim().startsWith('<')) {
      const next = vueBlocks(code);
      if (next.script && next.template) full = true;
      for (const [key, body] of Object.entries(next)) { if (own(blocks,key)) fail(); blocks[key] = body; }
    } else helpers.push(code);
  }
  if (!blocks.script && !blocks.template) fail();
  const complete = Boolean(blocks.script && blocks.template);
  if (task.patch && !full) {
    const baseline = vueBlocks(task.original);
    blocks = { ...baseline, ...blocks }; partial = true;
  }
  if (!blocks.script || !blocks.template) fail();
  const source = parse(blocks.script), state = catalog([source, ...helpers.map(parse)]);
  const vueImports = new Map();
  for (const node of source.statements) {
    if (ts.isImportDeclaration(node) && node.moduleSpecifier.text === 'vue' && node.importClause?.namedBindings && ts.isNamedImports(node.importClause.namedBindings)) {
      for (const item of node.importClause.namedBindings.elements) vueImports.set(text(item.name),text(item.propertyName || item.name));
    }
  }
  state.vueImports = vueImports;
  for (const name of ['Number','defineProps', ...vueImports.keys()]) {
    if (state.functions.has(name) || (state.globals.has(name) && name !== 'defineProps') || (['Number','defineProps'].includes(name) && state.imports.has(name))) fail();
  }
  for (const file of [source, ...helpers.map(parse)]) {
    const stack = [file];
    while (stack.length) {
      const node = stack.pop();
      if (ts.isParameter(node) && (!ts.isIdentifier(node.name) || ['Number','defineProps',...vueImports.keys()].includes(text(node.name)))) fail();
      if (ts.isVariableDeclaration(node) && ['Number','defineProps',...vueImports.keys()].includes(text(node.name))) fail();
      ts.forEachChild(node,child => { stack.push(child); });
    }
  }
  const template = vueTemplate(blocks.template);
  checks.syntax = true;
  let propsCount = 0;
  const setup = (a,b) => {
    steps = 0;
    const env = Object.create(null); env[SOURCE] = source; propsCount = 0;
    for (const node of source.statements) {
      if (ts.isImportDeclaration(node) || ts.isFunctionDeclaration(node) || ts.isInterfaceDeclaration(node) || ts.isTypeAliasDeclaration(node)) continue;
      if (!ts.isVariableStatement(node)) fail();
      for (const declaration of node.declarationList.declarations) {
        const init = declaration.initializer;
        if (ts.isCallExpression(init) && ts.isIdentifier(init.expression) && text(init.expression) === 'defineProps') {
          if (state.imports.has('defineProps') || state.functions.has('defineProps') || ++propsCount !== 1) fail();
          const expected = new Set([task.left,task.right]);
          if (language === 'TypeScript') {
            const type = init.typeArguments?.[0];
            if (init.arguments.length || init.typeArguments.length !== 1 || !type || !ts.isTypeLiteralNode(type) || type.members.length !== 2) fail();
            for (const member of type.members) { if (!ts.isPropertySignature(member) || member.type?.kind !== ts.SyntaxKind.NumberKeyword || !expected.delete(text(member.name))) fail(); }
          } else {
            const argument = init.arguments[0];
            if (init.arguments.length !== 1 || !ts.isObjectLiteralExpression(argument) || argument.properties.length !== 2) fail();
            for (const property of argument.properties) {
              if (!ts.isPropertyAssignment(property) || !expected.delete(text(property.name))) fail();
              let propType = property.initializer;
              if (ts.isObjectLiteralExpression(propType)) {
                const options = new Map();
                for (const option of propType.properties) {
                  if (!ts.isPropertyAssignment(option) || options.has(text(option.name)) || !['type','required'].includes(text(option.name))) fail();
                  options.set(text(option.name),option.initializer);
                }
                if (options.has('required') && options.get('required').kind !== ts.SyntaxKind.TrueKeyword) fail();
                propType = options.get('type');
              }
              if (!propType || !ts.isIdentifier(propType) || text(propType) !== 'Number') fail();
            }
          }
          bind(declaration.name,{ [task.left]:a,[task.right]:b },env);
        } else {
          if (vueImports.has(text(declaration.name))) fail();
          bind(declaration.name,value(init,env,state),env);
        }
      }
    }
    if (propsCount !== 1) fail();
    const templateEnv = Object.assign(Object.create(null),env);
    templateEnv[TEMPLATE] = true;
    const root = { [ELEMENT]:true,tag:'root',attrs:{},children:renderVue(template.children,templateEnv,state) };
    return elements(root);
  };
  setup(0,0); checks.binding = true;
  checks.validation = [[-1,1],[1,-1],[undefined,1],[1,undefined],[NaN,1],[1,NaN],[Infinity,1],[1,Infinity],['abc',1],[1,'abc']].every(([a,b]) => {
    const items = setup(a,b);
    return items.some(item => item.tag !== 'root' && content(item) === '입력 오류') && !items.some(item => item.tag === 'output');
  });
  checks.calculation = [[0,0],[7,3],[19,2]].every(([a,b]) => {
    const items = setup(a,b), outputs = items.filter(item => item.tag === 'output' && item.attrs['data-testid'] === task.key);
    return outputs.length === 1 && content(outputs[0]) === String(a*b+task.fee) && !items.some(item => content(item).includes('입력 오류'));
  });
  return { checks,has_import:full,complete,partial };
}

try {
  if (!Array.isArray(codes) || !codes.length || codes.length > 8 || codes.join('').length > 24000) fail();
  if (mode === 'vue') { process.stdout.write(JSON.stringify(checkVue())); process.exit(0); }
  if (mode === 'nextjs') { process.stdout.write(JSON.stringify(checkNextjs())); process.exit(0); }
  if (mode === 'nestjs') { process.stdout.write(JSON.stringify(checkNestjs())); process.exit(0); }
  const sources = codes.map(parse), raw = catalog(sources);
  const importName = mode === 'react' ? 'react' : 'express';
  const hasImport = [...raw.imports.values()].includes(importName);
  let state = raw;
  if (task.patch && !hasImport) {
    const baseline = parse(task.original), merged = catalog([baseline]);
    const replacement = raw.functions.get(task.entry);
    if (replacement) merged.functions.set(task.entry, replacement);
    else if (sources.length === 1 && sources[0].statements.length === 1 && ts.isReturnStatement(sources[0].statements[0])) {
      const fn = merged.functions.get(task.entry);
      merged.functions.set(task.entry, { ...fn, body: { ...fn.body, statements: [...fn.body.statements.slice(0, -1), sources[0].statements[0]] } });
    } else fail();
    for (const [name, fn] of raw.functions) if (name !== task.entry) merged.functions.set(name, fn);
    for (const [name, module] of raw.imports) merged.imports.set(name, module);
    state = merged;
  }
  checks.syntax = true;
  let invokeTask;
  if (mode === 'express') {
    const apps = new Set([...state.globals].filter(([, node]) => ts.isCallExpression(node) && ts.isIdentifier(node.expression) && state.imports.get(text(node.expression)) === 'express').map(([name]) => name));
    const route = state.calls.find(node => ts.isPropertyAccessExpression(node.expression) && apps.has(text(node.expression.expression)) && text(node.expression.name) === 'get' && ts.isStringLiteral(node.arguments[0]) && node.arguments[0].text === task.route);
    const handler = route?.arguments[1];
    const fn = handler && (ts.isIdentifier(handler) ? state.functions.get(text(handler)) : ts.isArrowFunction(handler) || ts.isFunctionExpression(handler) ? handler : null);
    checks.binding = Boolean(fn && fn.parameters.length === 2);
    invokeTask = (a, b) => { steps = 0; return invoke(fn, [{ query: { [task.left]: a, [task.right]: b } }, { [RESPONSE]: true, status: 200 }], state, 0); };
    if (checks.binding) {
      checks.validation = [[-1, 1], [1, -1], [undefined, 1], [1, undefined], ['abc', 1]].every(([a,b]) => { const result = invokeTask(a,b); return result?.[RESPONSE] && result.status === 400 && typeof result.body?.error === 'string'; });
      checks.calculation = [[0,0],[7,3],[19,2]].every(([a,b]) => { const result = invokeTask(String(a),String(b)); return result?.[RESPONSE] && result.status === 200 && Object.keys(result.body || {}).length === 1 && result.body?.[task.key] === a*b+task.fee; });
    }
  } else {
    const fn = state.functions.get(task.entry);
    checks.binding = Boolean(fn && [...state.imports.values()].includes('react') && fn.parameters.length === 1);
    invokeTask = (a,b) => { steps = 0; return invoke(fn, [{ [task.left]: a, [task.right]: b }], state, 0); };
    if (checks.binding) {
      checks.validation = [[-1,1],[1,-1],[NaN,1],[undefined,1]].every(([a,b]) => elements(invokeTask(a,b)).some(element => content(element).includes('입력 오류')));
      checks.calculation = [[0,0],[7,3],[19,2]].every(([a,b]) => { const outputs = elements(invokeTask(a,b)).filter(element => element.tag === 'output' && element.attrs['data-testid'] === task.key); return outputs.length === 1 && content(outputs[0]) === String(a*b+task.fee); });
    }
  }
  process.stdout.write(JSON.stringify({ checks, has_import: hasImport }));
} catch {
  process.stdout.write(JSON.stringify({ checks, has_import: false }));
}

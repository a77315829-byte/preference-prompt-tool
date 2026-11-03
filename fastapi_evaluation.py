"""Prepared FastAPI tasks and bounded static checks. Never executes generated code."""
from __future__ import annotations

import ast
import copy
import re
import textwrap
from coding_evaluation_report import weighted_score
from coding_answer_review import inspect_answer

VERSION = 'fastapi-static-v2'
PREFERENCE_CHECKS = '설명 표시와 출력 형식만 자동 점수에 반영합니다. 주석의 적절함·역할 분리는 실제 답변을 보고 직접 확인하며 개수로 판정하지 않습니다. v1 점수와 직접 비교하지 마세요.'
LIMITATION = '준비 과제의 Python 문법·API 선언·제한된 계산식과 작성 형식을 검사합니다. 실제 서버 실행·보안·전체 기능 품질 검증은 아닙니다.'


def _task(name, route, key, left, right, fee, patch=False):
    expression = f'{left} * {right} + {fee}'
    original = (f'from fastapi import FastAPI, Query\napp = FastAPI()\n\n@app.get("{route}")\n'
                f'def calculate({left}: int = Query(ge=0), {right}: int = Query(ge=0)):\n'
                f'    return {{"{key}": {left} * {right} + 100}}\n')
    request = (f'Python/FastAPI로 GET {route} API를 작성하세요. 정수 쿼리 매개변수 {left}, {right}를 받고 '
               f'둘 다 음수를 거절해야 합니다. JSON 키 {key}의 값은 {expression}입니다. '
               '지정한 작성 선호를 따르세요. 코드는 파일 이름과 ```python 코드 블록으로 제시하세요. '
               '실행한 것처럼 주장하지 마세요.')
    if patch:
        request += ('\n기존 main.py를 아래와 같이 제공합니다. 변경 부분 중심 선호라면 calculate 함수 또는 '
                    '바뀐 return 줄을 제시하세요. 전체 코드 선호라면 필요한 전체 파일을 제시하세요.\n```python\n' + original + '```')
    return dict(id=name, label=name, input=request, route=route, key=key, left=left, right=right,
                fee=fee, patch=patch, original=original)


TRAIN = [_task('상품 결제 금액', '/checkout/amount', 'amount', 'price', 'quantity', 500),
         _task('배송비 변경', '/shipping/cost', 'cost', 'weight', 'rate', 2500, True)]
VALIDATION = [_task('예약 요금', '/booking/fee', 'fee', 'days', 'daily_rate', 700),
              _task('주문 수수료 변경', '/orders/charge', 'charge', 'count', 'unit_price', 900, True)]
HOLDOUT = [_task('대여 견적', '/rental/quote', 'quote', 'hours', 'hourly_rate', 1300),
           _task('인쇄 요금 변경', '/printing/price', 'price', 'pages', 'page_rate', 400, True)]


def _expression(node, values, functions, depth=0):
    """Interpret only a tiny arithmetic/return grammar, not Python bytecode."""
    if depth > 16:
        raise ValueError('계산식 깊이 초과')
    walk = lambda n, env=values: _expression(n, env, functions, depth+1)
    if isinstance(node, ast.Constant) and type(node.value) in (int, str):
        if isinstance(node.value, int) and abs(node.value) > 10**8:
            raise ValueError('상수 범위 초과')
        return node.value
    if isinstance(node, ast.Name) and node.id in values:
        return values[node.id]
    if isinstance(node, ast.Dict) and len(node.keys) <= 5:
        return {walk(k): walk(v) for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
        a, b = walk(node.left), walk(node.right)
        if type(a) is not int or type(b) is not int or max(abs(a), abs(b)) > 10**10:
            raise ValueError('정수 계산만 지원')
        return a+b if isinstance(node.op, ast.Add) else a-b if isinstance(node.op, ast.Sub) else a*b
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in functions and not node.keywords:
        fn = functions[node.func.id]
        args = [walk(a) for a in node.args]
        if len(args) != len(fn.args.args):
            raise ValueError('인자 불일치')
        return _function(fn, dict(zip([a.arg for a in fn.args.args], args)), functions, depth+1)
    raise ValueError('지원하지 않는 계산식')


def _function(fn, values, functions, depth=0):
    if depth > 16:
        raise ValueError('함수 깊이 초과')
    values = dict(values)
    for statement in fn.body:
        if isinstance(statement, ast.Return):
            return _expression(statement.value, values, functions, depth+1)
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            if any(not isinstance(t, ast.Name) for t in targets):
                raise ValueError('단순 변수만 지원')
            value = _expression(statement.value, values, functions, depth+1)
            for target in targets:
                values[target.id] = value
        elif not (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str)):
            raise ValueError('지원하지 않는 함수 본문')
    raise ValueError('반환식 없음')


def _is_query(node):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'Query'
            and any(k.arg == 'ge' and isinstance(k.value, ast.Constant) and k.value.value == 0 for k in node.keywords))


def _nonnegative(fn, name):
    args = fn.args.args
    defaults = dict(zip([a.arg for a in args[-len(fn.args.defaults):]], fn.args.defaults)) if fn.args.defaults else {}
    if _is_query(defaults.get(name)):
        return True
    arg = next((a for a in args if a.arg == name), None)
    return bool(arg and isinstance(arg.annotation, ast.Subscript)
                and any(_is_query(n) for n in ast.walk(arg.annotation)))


def evaluate(task, response, profile):
    checks = {'syntax': False, 'route': False, 'validation': False, 'calculation': False}
    preferences = {'explanation': False, 'comments': None, 'structure': None, 'output': False}
    observations = {}
    if not isinstance(response, str) or len(response) > 24000:
        return dict(score=0.0, checks=checks, preferences=preferences, feedback='응답이 비었거나 너무 깁니다.')
    if response.strip():
        inspection = inspect_answer(profile, response, task['patch'])
        preferences['explanation'] = inspection['preferences']['explanation']
        observations = inspection['observations']
    chunks = re.findall(r'```(?:python|py)?[ \t]*\n(.*?)```', response, re.S)
    prose = re.sub(r'```.*?```', '', response, flags=re.S).strip()
    try:
        if not 1 <= len(chunks) <= 8:
            raise ValueError('Python 코드 블록이 필요합니다.')
        raw = [ast.parse(textwrap.dedent(code)) for code in chunks]
        if sum(sum(1 for _ in ast.walk(tree)) for tree in raw) > 4000:
            raise ValueError('코드가 너무 깁니다.')
        trees = copy.deepcopy(raw)
        # A changed return line or calculate function is checked in its supplied context.
        if task['patch'] and len(trees) == 1 and not any(isinstance(n, ast.ImportFrom) and n.module == 'fastapi' for n in ast.walk(trees[0])):
            patch = trees[0].body
            original = ast.parse(task['original'])
            endpoint = original.body[-1]
            if len(patch) == 1 and isinstance(patch[0], ast.Return):
                endpoint.body = patch
            elif len(patch) == 1 and isinstance(patch[0], (ast.FunctionDef, ast.AsyncFunctionDef)) and patch[0].name == 'calculate':
                endpoint.body = patch[0].body
            else:
                raise ValueError('기존 calculate 함수 또는 return 줄의 변경을 확인하지 못했습니다.')
            trees = [original]
        checks['syntax'] = True
        functions = {node.name: node for tree in trees for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        nodes = [n for tree in trees for n in ast.walk(tree)]
        imports = {alias.name for n in nodes if isinstance(n, ast.ImportFrom) and n.module == 'fastapi' for alias in n.names}
        applications, routers = set(), {}
        for node in nodes:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                for target in node.targets:
                    if isinstance(target, ast.Name) and node.value.func.id == 'FastAPI' and 'FastAPI' in imports:
                        applications.add(target.id)
                    if isinstance(target, ast.Name) and node.value.func.id == 'APIRouter' and 'APIRouter' in imports:
                        prefix = next((k.value.value for k in node.value.keywords if k.arg == 'prefix' and isinstance(k.value, ast.Constant)), '')
                        routers[target.id] = prefix
        linked = {n.args[0].id for n in nodes if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and isinstance(n.func.value, ast.Name) and n.func.value.id in applications and n.func.attr == 'include_router'
                  and n.args and isinstance(n.args[0], ast.Name) and not n.keywords}
        def matches(fn):
            for d in fn.decorator_list:
                if not (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and isinstance(d.func.value, ast.Name)
                        and d.func.attr == 'get' and d.args and isinstance(d.args[0], ast.Constant)):
                    continue
                name = d.func.value.id
                prefix = '' if name in applications else routers.get(name) if name in linked else None
                if isinstance(prefix, str) and prefix + str(d.args[0].value) == task['route']:
                    return True
            return False
        endpoint = next((fn for fn in functions.values() if matches(fn)), None)
        checks['route'] = bool(endpoint)
        if endpoint:
            checks['validation'] = all(_nonnegative(endpoint, task[k]) for k in ('left', 'right'))
            samples = [(0, 0), (7, 3), (19, 2)]
            checks['calculation'] = all(_function(endpoint, {task['left']: a, task['right']: b}, functions)
                                       == {task['key']: a*b+task['fee']} for a, b in samples)
        raw_imports = any(isinstance(n, ast.ImportFrom) and n.module == 'fastapi' for tree in raw for n in ast.walk(tree))
        preferences['output'] = (not raw_imports if profile['preferences']['output'] == 'changes' and task['patch'] else raw_imports)
        observations['output'] += ' · FastAPI import ' + ('있음' if raw_imports else '없음')
    except (SyntaxError, ValueError, TypeError, KeyError, RecursionError):
        pass
    score = weighted_score(checks, preferences, 'syntax')
    failed = [key for key, ok in {**checks, **preferences}.items() if ok is False]
    feedback = ('정적 검사: ' + (', '.join(failed) + ' 항목을 개선하세요.' if failed else '모든 대리 검사 충족.')
                + '\n고정 선호: ' + str(profile['preferences'])
                + '\n주석과 역할 분리는 사람 확인 항목입니다. 개수를 늘려 자동 점수를 높이려 하지 마세요.'
                + '\n기존 지침을 바꾸지 않는 보충 안내만 제안하세요. 특정 과제의 경로·숫자를 지침에 복사하지 마세요.\n' + LIMITATION)
    return dict(score=score, checks=checks, preferences=preferences, observations=observations, feedback=feedback)

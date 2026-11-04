"""Bounded Spring Web source-pattern and arithmetic checks, never Java execution."""
from __future__ import annotations

import ast
import json
import re
from coding_evaluation_report import weighted_score
from coding_answer_review import inspect_answer

VERSION = 'spring-boot-static-v2'
LIMITATION = '준비 과제의 Java 코드 구조·Spring 요청 매핑·입력 거절 패턴·제한된 계산식과 작성 형식을 검사합니다. Java 컴파일·Spring 서버 실행·보안·전체 기능 품질 검증은 아닙니다.'
PREFERENCE_CHECKS = '설명 표시와 출력 형식만 자동 점수에 반영합니다. 주석의 적절함·역할 분리는 실제 답변을 보고 직접 확인하며 개수로 판정하지 않습니다. v1 점수와 직접 비교하지 마세요.'


def _task(label, route, key, left, right, fee, patch=False):
    original = f'''package com.example.demo;
import java.util.Map;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

@RestController
public class PriceController {{
    @GetMapping("{route}")
    public Map<String, Long> calculate(@RequestParam("{left}") long {left}, @RequestParam("{right}") long {right}) {{
        if ({left} < 0 || {right} < 0) {{
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST);
        }}
        return Map.of("{key}", {left} * {right} + 100L);
    }}
}}
'''
    request = (f'Java 17+/Spring Boot 3의 기존 Spring Web 프로젝트에 GET {route} API를 작성하세요. '
               f'필수 정수 쿼리 매개변수 {left}, {right}를 받으세요. 둘 중 하나라도 음수이면 '
               '직접 검사 후 ResponseStatusException(HttpStatus.BAD_REQUEST)로 거절하세요. '
               f'Map.of를 사용해 JSON 키 {key}, 값 {left} * {right} + {fee}를 반환하세요. '
               '추가 의존성 없이 기존 실행 클래스는 유지합니다. 선택한 작성 선호를 따르고 '
               '파일 이름과 ```java 코드 블록을 제시하세요. 컴파일하거나 실행했다고 주장하지 마세요.')
    if patch:
        request += ('\n기존 PriceController.java는 아래와 같습니다. 변경 부분 중심 선호라면 바뀐 calculate 메서드 전체 또는 '
                    'return 줄을 제시하고, 전체 코드 선호라면 필요한 전체 파일을 제시하세요.\n```java\n' + original + '```')
    return dict(id=label, label=label, input=request, route=route, key=key, left=left, right=right,
                fee=fee, patch=patch, original=original)


TRAIN = [_task('상품 청구 금액', '/billing/amount', 'amount', 'price', 'quantity', 600),
         _task('운송 비용 변경', '/transport/cost', 'cost', 'weight', 'rate', 2700, True)]
VALIDATION = [_task('숙박 요금', '/stay/fee', 'fee', 'nights', 'nightlyRate', 800),
              _task('입장 비용 변경', '/entry/charge', 'charge', 'count', 'unitPrice', 1100, True)]
HOLDOUT = [_task('장비 대여 견적', '/equipment/quote', 'quote', 'hours', 'hourlyRate', 1700),
           _task('출력 비용 변경', '/copies/price', 'price', 'pages', 'pageRate', 450, True)]

TOKEN = re.compile(r'\s+|//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\d+[lL]?|[A-Za-z_$][\w$]*|\|\||&&|[{}()\[\];,.@<>+=*\-!?:]')


def _tokens(code):
    result, comments, cursor = [], 0, 0
    for match in TOKEN.finditer(code):
        if code[cursor:match.start()].strip():
            raise ValueError('지원하지 않는 Java 토큰')
        value = match.group()
        cursor = match.end()
        if value.startswith(('//', '/*')):
            comments += 1
        elif not value.isspace():
            result.append(value)
    if code[cursor:].strip() or len(result) > 6000:
        raise ValueError('지원하지 않는 코드 또는 토큰 수 초과')
    return result, comments


def _pairs(tokens):
    stack, result = [], {}
    for index, value in enumerate(tokens):
        if value in ('(', '{', '['):
            stack.append((index, value))
        elif value in (')', '}', ']'):
            if not stack or stack[-1][1] != {')': '(', '}': '{', ']': '['}[value]:
                raise ValueError('괄호 불일치')
            start, _ = stack.pop()
            result[start] = index
    if stack:
        raise ValueError('닫히지 않은 괄호')
    return result


def _split(tokens):
    result, start, depth = [], 0, 0
    for i, token in enumerate(tokens):
        if token in ('(', '<', '['): depth += 1
        if token in (')', '>', ']'): depth -= 1
        if token == ',' and depth == 0:
            result.append(tokens[start:i]); start = i+1
    return result + [tokens[start:]] if tokens else []


def _prefix(tokens, index):
    start = index-1
    while start >= 0 and tokens[start] not in ('{', '}', ';'):
        start -= 1
    return tokens[start+1:index]


def _mapping(tokens, annotation):
    for i in range(len(tokens)-2):
        if tokens[i:i+2] == ['@', annotation] and tokens[i+2] == '(':
            end = _pairs(tokens)[i+2]
            args = tokens[i+3:end]
            for part in _split(args):
                if len(part) == 1 and part[0].startswith('"'):
                    return json.loads(part[0])
                keys = ('value', 'name') if annotation == 'RequestParam' else ('value', 'path')
                if len(part) == 3 and part[0] in keys and part[1] == '=' and part[2].startswith('"'):
                    return json.loads(part[2])
    return None


def _parse(tokens):
    pairs = _pairs(tokens)
    classes, methods, fields = [], [], {}
    for i in range(len(tokens)-2):
        if tokens[i] == 'class':
            opening = tokens.index('{', i+2)
            classes.append(dict(name=tokens[i+1], start=opening, end=pairs[opening], prefix=_prefix(tokens, i)))
    for i, token in enumerate(tokens):
        if token != '(' or i == 0 or tokens[i-1] in ('if', 'for', 'while', 'switch', 'catch', 'synchronized'):
            continue
        end = pairs[i]
        if end+1 >= len(tokens) or tokens[end+1] != '{':
            continue
        owner = next((c for c in reversed(classes) if c['start'] < i < c['end']), None)
        if not owner or tokens[i-1] == owner['name']:
            continue
        parameters = _split(tokens[i+1:end])
        if any(len(p) < 2 or p[-2] not in ('long', 'int', 'Long', 'Integer') for p in parameters):
            continue
        methods.append(dict(name=tokens[i-1], owner=owner, params=[p[-1] for p in parameters], parameters=parameters,
                            prefix=_prefix(tokens, i-1), body=tokens[end+2:pairs[end+1]]))
    class_names = {c['name'] for c in classes}
    for c in classes:
        for i in range(c['start']+1, c['end']-2):
            if tokens[i] in class_names and tokens[i+2] == ';':
                fields[c['name'], tokens[i+1]] = tokens[i]
    return classes, methods, fields


class _Rejected(ValueError):
    pass


def _negative_condition(tokens, values):
    parts = []
    current = []
    for token in tokens:
        if token == '||': parts.append(current); current = []
        elif token not in ('(', ')'): current.append(token)
    parts.append(current)
    if any(len(p) != 3 or p[0] not in values or p[1:] != ['<', '0'] for p in parts):
        raise ValueError('지원하지 않는 조건문')
    return any(values[p[0]] < 0 for p in parts)


def _value(tokens, values, method, registry, fields, depth):
    if depth > 16: raise ValueError('계산식 깊이 초과')
    source = ' '.join(tokens)
    source = re.sub(r'\(\s*(?:long|int)\s*\)', '', source)
    source = re.sub(r'\b(\d+)[lL]\b', r'\1', source)
    node = ast.parse(source.strip(), mode='eval').body
    def walk(n):
        if isinstance(n, ast.Constant) and type(n.value) in (int, str):
            if isinstance(n.value, int) and abs(n.value) > 10**8: raise ValueError('상수 범위 초과')
            return n.value
        if isinstance(n, ast.Name) and n.id in values: return values[n.id]
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult)):
            a, b = walk(n.left), walk(n.right)
            if type(a) is not int or type(b) is not int or max(abs(a), abs(b)) > 10**10: raise ValueError('계산 범위 초과')
            return a+b if isinstance(n.op, ast.Add) else a-b if isinstance(n.op, ast.Sub) else a*b
        if isinstance(n, ast.Call) and not n.keywords:
            if isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name):
                receiver, name = n.func.value.id, n.func.attr
                if receiver == 'Map' and name == 'of' and len(n.args) == 2:
                    return {walk(n.args[0]): walk(n.args[1])}
                if receiver == 'ResponseEntity' and name == 'ok' and len(n.args) == 1: return walk(n.args[0])
                owner = method['owner']['name'] if receiver == 'this' else fields.get((method['owner']['name'], receiver), receiver)
            elif isinstance(n.func, ast.Name):
                owner, name = method['owner']['name'], n.func.id
            elif (isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Attribute)
                  and isinstance(n.func.value.value, ast.Name) and n.func.value.value.id == 'this'):
                owner, name = fields.get((method['owner']['name'], n.func.value.attr)), n.func.attr
            else: raise ValueError('지원하지 않는 호출')
            target = registry.get((owner, name))
            args = [walk(a) for a in n.args]
            if not target or len(args) != len(target['params']): raise ValueError('보조 메서드 확인 불가')
            return _invoke(target, dict(zip(target['params'], args)), registry, fields, depth+1)
        raise ValueError('지원하지 않는 계산식')
    return walk(node)


def _invoke(method, values, registry, fields, depth=0):
    if depth > 16: raise ValueError('메서드 깊이 초과')
    tokens, cursor = method['body'], 0
    pairs = _pairs(tokens)
    while cursor < len(tokens):
        if tokens[cursor] == 'if':
            opening = cursor+1
            if tokens[opening] != '(': raise ValueError('조건문 확인 불가')
            close = pairs[opening]
            if tokens[close+1] == '{':
                end = pairs[close+1]; guard = tokens[close+2:end]
            else:
                end = tokens.index(';', close+1); guard = tokens[close+1:end+1]
            if guard != ['throw', 'new', 'ResponseStatusException', '(', 'HttpStatus', '.', 'BAD_REQUEST', ')', ';']:
                # An explanatory message is allowed, but only this exception constructor is recognized.
                if not (guard[:8] == ['throw', 'new', 'ResponseStatusException', '(', 'HttpStatus', '.', 'BAD_REQUEST', ',']
                        and len(guard) == 11 and guard[8].startswith('"') and guard[9:] == [')', ';']):
                    raise ValueError('입력 거절 패턴 확인 불가')
            if _negative_condition(tokens[opening+1:close], values): raise _Rejected('음수 거절')
            cursor = end+1
            continue
        end = tokens.index(';', cursor)
        statement = tokens[cursor:end]
        if statement[0] == 'return': return _value(statement[1:], values, method, registry, fields, depth+1)
        if len(statement) >= 4 and statement[0] in ('long', 'int', 'Long', 'Integer', 'var') and statement[2] == '=':
            values[statement[1]] = _value(statement[3:], values, method, registry, fields, depth+1)
        else: raise ValueError('지원하지 않는 메서드 본문')
        cursor = end+1
    raise ValueError('반환식 없음')


def evaluate(task, response, profile):
    checks = dict(code_structure=False, route=False, validation=False, calculation=False)
    preferences = {'explanation': False, 'comments': None, 'structure': None, 'output': False}
    observations = {}
    if not isinstance(response, str) or len(response) > 24000:
        return dict(score=0.0, checks=checks, preferences=preferences, feedback='응답이 비었거나 너무 깁니다.')
    if response.strip():
        inspection = inspect_answer(profile, response, task['patch'])
        preferences['explanation'] = inspection['preferences']['explanation']
        observations = inspection['observations']
    chunks = re.findall(r'```java[ \t]*\n(.*?)```', response, re.S)
    prose = re.sub(r'```.*?```', '', response, flags=re.S).strip()
    try:
        if not 1 <= len(chunks) <= 8: raise ValueError('Java 코드 블록이 필요합니다.')
        lexed = [_tokens(code) for code in chunks]
        raw = [t for tokens, _ in lexed for t in tokens]
        if len(raw) > 6000: raise ValueError('코드가 너무 깁니다.')
        materialized = raw
        if task['patch'] and 'class' not in raw and len(chunks) == 1:
            original, _ = _tokens(task['original'])
            if raw[0] == 'return' and raw[-1] == ';' and raw.count(';') == 1:
                start = len(original)-1-original[::-1].index('return')
                end = original.index(';', start)
                materialized = original[:start] + raw + original[end+1:]
            else:
                # Complete changed method with its mapping, in the supplied controller context.
                start = original.index('@', original.index('class'))
                end = _pairs(original)[original.index('{', original.index('calculate'))]
                materialized = original[:start] + raw + original[end+1:]
        classes, methods, fields = _parse(materialized)
        registry = {(m['owner']['name'], m['name']): m for m in methods}
        checks['code_structure'] = bool(classes and methods and len(registry) == len(methods))
        compact = ''.join(materialized)
        has_spring_imports = all(f'importorg.springframework.web.bind.annotation.{name};' in compact
                                or 'importorg.springframework.web.bind.annotation.*;' in compact
                                for name in ('RestController', 'GetMapping', 'RequestParam'))
        endpoint = next((m for m in methods if has_spring_imports and '@ RestController' in ' '.join(m['owner']['prefix'])
                         and (_mapping(m['owner']['prefix'], 'RequestMapping') or '') + (_mapping(m['prefix'], 'GetMapping') or '') == task['route']), None)
        checks['route'] = bool(endpoint)
        if endpoint:
            bindings = {}
            for parameter in endpoint['parameters']:
                name = _mapping(parameter, 'RequestParam')
                if name is None and parameter[:2] == ['@', 'RequestParam'] and (parameter[2] != '(' or parameter[3] == ')'):
                    name = parameter[-1]
                if name not in (task['left'], task['right']) or 'defaultValue' in parameter or 'false' in parameter:
                    raise ValueError('필수 쿼리 매개변수 불일치')
                bindings[parameter[-1]] = name
            if set(bindings.values()) != {task['left'], task['right']}: raise ValueError('매개변수 누락')
            def invoke(a, b):
                source = {task['left']: a, task['right']: b}
                return _invoke(endpoint, {var: source[key] for var, key in bindings.items()}, registry, fields)
            rejected = 0
            for a, b in [(-1, 1), (1, -1)]:
                try: invoke(a, b)
                except _Rejected: rejected += 1
            checks['validation'] = rejected == 2
            checks['calculation'] = all(invoke(a, b) == {task['key']: a*b+task['fee']} for a, b in [(0, 0), (7, 3), (19, 2)])
        preferences['output'] = 'class' not in raw if profile['preferences']['output'] == 'changes' and task['patch'] else 'class' in raw and 'import' in raw
        observations['output'] += ' · 클래스 선언 ' + ('있음' if 'class' in raw else '없음') + ' · import ' + ('있음' if 'import' in raw else '없음')
    except (SyntaxError, ValueError, TypeError, KeyError, IndexError, RecursionError):
        pass
    score = weighted_score(checks, preferences, 'code_structure')
    failed = [k for k, ok in {**checks, **preferences}.items() if ok is False]
    return dict(score=score, checks=checks, preferences=preferences, observations=observations,
                feedback=('정적 검사: ' + (', '.join(failed)+' 항목을 개선하세요.' if failed else '모든 대리 검사 충족.')
                          + '\n고정 선호: ' + str(profile['preferences'])
                          + '\n주석과 역할 분리는 사람 확인 항목입니다. 개수를 늘려 자동 점수를 높이려 하지 마세요.'
                          + '\n기존 지침을 유지하는 일반 보충 안내만 제안하고, 과제 경로·정답 숫자를 복사하지 마세요.\n' + LIMITATION))

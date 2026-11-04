"""Prepared Flask/Django tasks and bounded AST inspection, without either runtime."""
from __future__ import annotations

import ast
import copy
import re
import textwrap
from types import SimpleNamespace

from coding_answer_review import inspect_answer
from coding_evaluation_report import weighted_score
from python_web_ast import SourceCheck, Unsupported

VERSION = 'python-web-ast-v2'
LIMITATION = 'Python AST로 준비 과제의 경로·요청 입력·400 응답·제한된 계산식을 확인합니다. 생성 코드 import/실행·Flask/Django 서버·미들웨어·DB·설정·보안·전체 프로젝트 품질 검증은 아닙니다. 지원 문법 밖의 올바른 코드도 확인하지 못할 수 있습니다.'
PREFERENCE_CHECKS = '설명·출력 형식만 자동 점수에 반영합니다. 주석·역할 구성은 실제 답변에서 직접 확인합니다.'


def _task(mode, label, route, key, left, right, fee, patch):
    entry = 'quote'
    if mode == 'flask':
        prefix = f'from flask import Flask, request, jsonify\napp = Flask(__name__)\n\n@app.get("{route}")\n'
        signature = 'def quote():'
        request_input = 'request.args'
        error = 'return jsonify(error="입력 오류"), 400'
        result = f'return jsonify({key}={left} * {right} + 100)'
        urls = ''
        requirement = f'기존 Flask 2+ 프로젝트의 단일 모듈에 app = Flask(__name__)와 @app.get 또는 GET app.route로 GET {route}를 등록하세요. request.args를 사용하고 JSON 응답에는 jsonify를 사용하세요.'
    else:
        route += '/'
        prefix = 'from django.http import JsonResponse\nfrom django.urls import path\nfrom django.views.decorators.http import require_GET\n\n@require_GET\n'
        signature = 'def quote(request):'
        request_input = 'request.GET'
        error = 'return JsonResponse({"error": "입력 오류"}, status=400)'
        result = f'return JsonResponse({{"{key}": {left} * {right} + 100}})'
        urls = f'\nurlpatterns = [path("{route.lstrip("/")}", quote)]\n'
        requirement = f'기존 Django 프로젝트의 함수형 뷰 quote와 urlpatterns의 path로 GET {route}를 등록하세요. @require_GET, request.GET, JsonResponse를 사용하세요. 뷰와 URL을 같은 모듈 또는 views.py/urls.py로 나눌 수 있습니다.'
    original = (prefix + signature + f'\n    try:\n        {left} = int({request_input}.get("{left}"))\n'
        f'        {right} = int({request_input}.get("{right}"))\n    except (TypeError, ValueError):\n        {error}\n'
        f'    if {left} < 0 or {right} < 0:\n        {error}\n    {result}\n' + urls)
    request = (f'Python/{mode.title()}로 작성하세요. {requirement} 필수 정수 쿼리 {left}, {right}를 int로 변환하고 '
        f'누락·비정수·음수면 JSON error와 400을 반환하세요. 정상 응답은 JSON 키 {key}, 값 {left} * {right} + {fee}입니다. '
        '고른 작성 방식을 따르고 파일 이름과 ```python 코드 블록을 제시하세요. 추가 의존성·서버 시작 코드는 넣지 말고 실행했다고 주장하지 마세요.')
    if patch:
        request += f'\n기존 모듈은 아래와 같습니다. 변경 부분 선호면 quote 함수 전체 또는 마지막 return 줄만 제시하고, 전체 코드 선호면 필요한 전체 파일을 제시하세요.\n```python\n{original}```'
    return dict(id=f'{mode}-{label}',label=label,input=request,route=route,key=key,left=left,right=right,
                fee=fee,patch=patch,original=original,entry=entry)


def evaluation_for(mode):
    if mode not in ('flask','django'): raise ValueError('지원하지 않는 Python 웹 환경입니다.')
    def tasks(rows): return [_task(mode,*row) for row in rows]
    train = tasks([('주문 견적','/cart/quote','cart','unit_price','quantity',610,False),
                   ('보관 비용 변경','/locker/fee','locker','days','daily_rate',2100,True)])
    validation = tasks([('회의실 비용','/meeting/amount','meeting','hours','hourly_rate',810,False),
                        ('식사 견적 변경','/lunch/charge','lunch','count','unit_cost',1400,True)])
    holdout = tasks([('장비 예약','/devices/cost','device','periods','period_rate',1800,False),
                     ('복사 비용 변경','/documents/price','document','pages','page_price',470,True)])
    checks = {'syntax':'Python AST로 지원하는 구문 구조 확인. 생성 코드는 실행하지 않음.',
        'binding': 'Flask app·GET 경로·뷰 연결 확인.' if mode == 'flask' else 'Django urlpatterns·path·GET 전용 함수형 뷰 연결 확인.',
        'validation':'누락·비정수·두 음수 입력의 JSON 400 분기 확인.',
        'calculation':'세 정상 입력의 JSON 키와 제한된 반환 계산식 확인.'}
    return SimpleNamespace(VERSION=VERSION,LIMITATION=LIMITATION,PREFERENCE_CHECKS=PREFERENCE_CHECKS,
        TRAIN=train,VALIDATION=validation,HOLDOUT=holdout,CHECK_RULES=checks,
        OUTPUT_RULE='변경 과제는 기존 맥락에 적용한 quote 함수/return 부분 변경을 확인하며 필요한 import가 있어도 허용. 전체/새 구현은 프레임워크 import와 경로 설정을 포함하는 형식 확인.',
        evaluate=lambda task,response,profile:evaluate(mode,task,response,profile))


def evaluate(mode, task, response, profile):
    checks = dict(syntax=False,binding=False,validation=False,calculation=False)
    preferences = dict(explanation=False,comments=None,structure=None,output=False)
    observations = {}
    if isinstance(response,str) and response.strip() and len(response) <= 24000:
        inspection = inspect_answer(profile,response,task['patch'])
        observations = inspection['observations']; preferences['explanation'] = inspection['preferences']['explanation']
        try:
            chunks = re.findall(r'```(?:python|py)?[ \t]*\n(.*?)```',response,re.S)
            if not 1 <= len(chunks) <= 8: raise Unsupported('code blocks')
            codes = [textwrap.dedent(code) for code in chunks]
            raw = SourceCheck(codes,mode)
            imports = [q for imports in raw.imports.values() for q in imports.values()]
            framework_import = any(q == mode or q.startswith(mode+'.') for q in imports)
            materialized = raw
            partial_applied = False
            route_config = any(name == 'urlpatterns' or isinstance(value,ast.Call) and raw.qualified(value.func,index) == 'flask.Flask'
                for (index,name),value in raw.globals.items())
            if task['patch'] and (not framework_import or profile['preferences']['output'] == 'changes' and not route_config):
                partial_applied = True
                materialized = SourceCheck([task['original']],mode)
                base, origin = materialized.functions[task['entry']]
                replacement = raw.functions.get(task['entry'])
                replacement_node = replacement[0] if replacement else None
                if replacement_node is not None:
                    expected = 0 if mode == 'flask' else 1
                    if len(replacement_node.args.args)+len(replacement_node.args.posonlyargs) != expected: raise Unsupported('changed view signature')
                    base = copy.copy(base); base.body = replacement_node.body; base.args = replacement_node.args
                    if replacement_node.decorator_list: base.decorator_list = replacement_node.decorator_list
                elif len(raw.trees) == 1 and len(raw.trees[0].body) == 1 and isinstance(raw.trees[0].body[0],ast.Return):
                    base = copy.copy(base); base.body = base.body[:-1]+raw.trees[0].body
                else: raise Unsupported('changed quote function or return required')
                materialized.functions[task['entry']] = (base,origin)
                root_source = replacement[1] if replacement else 0
                materialized.imports[origin].update(raw.imports.get(root_source,{}))
                for name,(helper,source) in raw.functions.items():
                    if name != task['entry']:
                        helper_source = origin if source == root_source else source+1
                        materialized.functions[name] = (helper,helper_source)
                        materialized.imports.setdefault(helper_source,{}).update(raw.imports[source])
                for (index,key),value in raw.globals.items():
                    materialized.globals[origin if index == root_source else index+1,key] = value
            checks['syntax'] = True
            endpoint = materialized.endpoint(task)
            checks['binding'] = endpoint is not None
            if endpoint:
                cases = [(-1,1),(1,-1),(None,1),(1,None),('abc',1),('1.5',1)]
                def request(a,b):
                    query = {key:str(value) for key,value in [(task['left'],a),(task['right'],b)] if value is not None}
                    return materialized.response(endpoint,query)
                checks['validation'] = all(reply.status == 400 and isinstance(reply.body.get('error'),str) for reply in (request(a,b) for a,b in cases))
                checks['calculation'] = all(reply.status == 200 and reply.body == {task['key']:a*b+task['fee']}
                    for a,b in [(0,0),(7,3),(19,2)] for reply in [request(a,b)])
            preferences['output'] = partial_applied if task['patch'] and profile['preferences']['output'] == 'changes' else framework_import and not partial_applied
        except (SyntaxError,ValueError,TypeError,KeyError,RecursionError,IndexError):
            pass
    failed = [key for key,ok in {**checks,**preferences}.items() if ok is False]
    return dict(score=weighted_score(checks,preferences,'syntax'),checks=checks,preferences=preferences,observations=observations,
        feedback='정적 검사 미확인: '+', '.join(failed)+'\n고정 선호: '+str(profile['preferences'])
        +'\n주석·역할 구성은 사람이 확인합니다. 기존 선호를 유지하고 과제 경로·정답 숫자를 복사하지 마세요.\n'+LIMITATION)

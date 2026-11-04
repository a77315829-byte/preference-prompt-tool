import ast
import copy

import pytest

import api_server
from auth import AuthService
from coding_gepa import HEADING, coding_draft, compose_prompt, optimize_coding
from coding_optimization_jobs import CodingOptimizationJobs
from personal_prompts import PersonalPromptStore
from python_web_evaluation import evaluation_for
from tests.test_fastapi_optimization import wait_job
from tests.test_personal_prompts import request, signup
from tests.test_team import db, server

PROFILE = {'language':'Python','framework':'Flask','preferences':{
    'explanation':'brief','comments':'essential','structure':'compact','output':'complete'},'extra':''}


def answer(task, good=True):
    code = task['original'].replace('+ 100',f'+ {task["fee"]}' if good else '+ 99')
    return f'### app.py\n```python\n{code}```\n입력과 반환값을 확인하세요.'


@pytest.mark.parametrize('mode',['flask','django'])
def test_reference_rejects_wrong_route_calculation_missing_integer_and_negative_guards(mode):
    spec = evaluation_for(mode); task = spec.TRAIN[0]; profile = {**PROFILE,'framework':mode.title()}
    result = spec.evaluate(task,answer(task),profile)
    assert all(result['checks'].values()) and result['score'] == 1, result
    assert result['preferences']['structure'] is None and result['preferences']['comments'] is None
    assert not spec.evaluate(task,answer(task,False),profile)['checks']['calculation']
    wrong = answer(task).replace(task['route'] if mode == 'flask' else task['route'].lstrip('/'),'wrong-route')
    assert not spec.evaluate(task,wrong,profile)['checks']['binding']
    negative = answer(task).replace(f'{task["left"]} < 0',f'{task["left"]} < -9')
    assert not spec.evaluate(task,negative,profile)['checks']['validation']
    default = answer(task).replace(f'.get("{task["left"]}")',f'.get("{task["left"]}", 0)')
    assert not spec.evaluate(task,default,profile)['checks']['validation']
    if mode == 'django':
        assert not spec.evaluate(task,answer(task).replace('@require_GET',''),profile)['checks']['binding']
    else:
        assert not spec.evaluate(task,answer(task).replace('@app.get','@app.post'),profile)['checks']['binding']
        route = answer(task).replace(f'@app.get("{task["route"]}")',f'@app.route("{task["route"]}", methods=["GET"])')
        assert all(spec.evaluate(task,route,profile)['checks'].values())
        invalid_get = answer(task).replace(f'@app.get("{task["route"]}")',f'@app.get("{task["route"]}", methods=["POST"])')
        assert not spec.evaluate(task,invalid_get,profile)['checks']['binding']


@pytest.mark.parametrize('mode',['flask','django'])
def test_partial_return_and_whole_view_in_original_context_including_needed_imports(mode):
    spec = evaluation_for(mode); task = spec.TRAIN[1]
    profile = {**PROFILE,'framework':mode.title(),'preferences':{**PROFILE['preferences'],'output':'changes'}}
    code = task['original'].replace('+ 100',f'+ {task["fee"]}')
    tree = ast.parse(code); fn = next(node for node in tree.body if isinstance(node,ast.FunctionDef))
    returned = ast.get_source_segment(code,fn.body[-1])
    result = spec.evaluate(task,f'```python\n{returned}\n```',profile)
    assert all(result['checks'].values()) and result['preferences']['output'], result
    function = ast.get_source_segment(code,fn)
    if mode == 'django': function = function.replace('quote(request)','quote(req)').replace('request.GET','req.GET')
    assert all(spec.evaluate(task,f'```python\n{function}\n```',profile)['checks'].values())
    imports = 'from flask import jsonify, request' if mode == 'flask' else 'from django.http import JsonResponse'
    imported = spec.evaluate(task,f'```python\n{imports}\n{function}\n```',profile)
    assert all(imported['checks'].values()) and imported['preferences']['output']


@pytest.mark.parametrize('mode',['flask','django'])
def test_changed_view_can_call_new_helper_in_same_or_separate_code_block(mode):
    spec = evaluation_for(mode); task = spec.TRAIN[1]
    profile = {**PROFILE,'framework':mode.title(),'preferences':{**PROFILE['preferences'],'output':'changes','structure':'modular'}}
    code = task['original'].replace('+ 100',f'+ {task["fee"]}')
    fn = next(node for node in ast.parse(code).body if isinstance(node,ast.FunctionDef))
    function = ast.get_source_segment(code,fn).replace(f'{task["left"]} * {task["right"]} + {task["fee"]}',f'total({task["left"]}, {task["right"]})')
    helper = f'def total(a,b):\n    return a*b+{task["fee"]}\n'
    same = f'```python\n{function}\n{helper}\n```'
    split = f'```python\nfrom .prices import total\n{function}\n```\n```python\n{helper}\n```'
    assert all(spec.evaluate(task,same,profile)['checks'].values())
    assert all(spec.evaluate(task,split,profile)['checks'].values())


def test_django_views_and_urls_can_be_split_with_real_import_bindings_and_helpers():
    spec = evaluation_for('django'); task = spec.TRAIN[0]; profile = {**PROFILE,'framework':'Django'}
    full = task['original'].replace('+ 100',f'+ {task["fee"]}')
    views = full[:full.index('urlpatterns')].replace('from django.urls import path\n','')
    views = views.replace(f'{task["left"]} * {task["right"]} + {task["fee"]}',f'total({task["left"]}, {task["right"]})')
    helper = f'def total(a, b):\n    return a * b + {task["fee"]}\n'
    views = 'from .prices import total\n'+views
    urls = f'from django.urls import path\nfrom .views import quote as quote_view\nurlpatterns = [path("{task["route"].lstrip("/")}",quote_view)]\n'
    response = f'```python\n{views}\n```\n```python\n{urls}\n```\n```python\n{helper}\n```'
    assert all(spec.evaluate(task,response,profile)['checks'].values())
    assert not spec.evaluate(task,response.replace('from .prices import total\n',''),profile)['checks']['calculation']
    assert not spec.evaluate(task,response.replace('from .views import quote as quote_view\n',''),profile)['checks']['binding']


@pytest.mark.parametrize('mode',['flask','django'])
def test_helper_in_same_module_and_fake_framework_import_or_commented_route_do_not_pass(mode):
    spec = evaluation_for(mode); task = spec.TRAIN[0]; profile = {**PROFILE,'framework':mode.title()}
    code = task['original'].replace('+ 100',f'+ {task["fee"]}')
    code = code.replace(f'{task["left"]} * {task["right"]} + {task["fee"]}',f'total({task["left"]}, {task["right"]})')
    code += f'\ndef total(a,b):\n    return a*b+{task["fee"]}\n'
    assert all(spec.evaluate(task,f'```python\n{code}\n```',profile)['checks'].values())
    fake = code.replace('from flask import','from unrelated import') if mode == 'flask' else code.replace('from django.http import','from unrelated import')
    assert not all(spec.evaluate(task,f'```python\n{fake}\n```',profile)['checks'].values())
    hidden = code.replace('@app.get','# @app.get') if mode == 'flask' else code.replace('urlpatterns =','# urlpatterns =')
    assert not spec.evaluate(task,f'```python\n{hidden}\n```',profile)['checks']['binding']


@pytest.mark.parametrize('mode',['flask','django'])
def test_unknown_calls_never_execute_and_syntax_and_recursion_are_bounded(mode,tmp_path):
    spec = evaluation_for(mode); task = spec.TRAIN[0]; profile = {**PROFILE,'framework':mode.title()}
    marker = tmp_path/'must-not-exist'
    code = task['original'].replace('+ 100',f'+ {task["fee"]}')
    payload = f'    __import__("pathlib").Path({str(marker)!r}).touch()\n'
    position = code.index('    try:')
    dangerous = code[:position]+payload+code[position:]
    assert not spec.evaluate(task,f'```python\n{dangerous}\n```',profile)['checks']['calculation']
    assert not marker.exists()
    assert spec.evaluate(task,'```python\ndef broken(\n```',profile)['score'] == 0
    recursive = code.replace(f'{task["left"]} * {task["right"]} + {task["fee"]}','loop(1)')+'\ndef loop(value):\n    return loop(value)\n'
    assert not spec.evaluate(task,f'```python\n{recursive}\n```',profile)['checks']['calculation']


@pytest.mark.parametrize('mode',['flask','django'])
def test_actual_gepa_engine_with_test_models_and_new_save_keep_original_and_manual_review(mode,db):
    spec = evaluation_for(mode); profile = {**PROFILE,'framework':mode.title()}; calls=[]
    def fake(system,user,model,**kwargs):
        calls.append((system,user,model,str(kwargs['cache_dir'])))
        if model == 'reflection': return '```\n필수 입력의 오류 응답과 계산식을 확인하세요.\n```'
        task = next(task for task in spec.TRAIN+spec.VALIDATION+spec.HOLDOUT if task['input'] == user)
        return answer(task,HEADING in system)
    snapshot = copy.deepcopy(profile)
    result = optimize_coding(profile,task_model='task',reflection_model='reflection',generate=fake)
    assert result['changed'] and profile == snapshot
    assert result['report']['environment'] == mode and result['report']['version'] == 'python-web-ast-v2'
    assert result['report']['holdout_after']['score'] > result['report']['holdout_before']['score']
    assert len(calls) == len(set(calls)) and result['report']['model_calls'] <= 32
    assert all(mode+'_gepa' in call[3] for call in calls)
    assert {t['id'] for t in spec.TRAIN}.isdisjoint(t['id'] for t in spec.VALIDATION+spec.HOLDOUT)
    owner,_ = AuthService(db).signup('alice','password-alice-123'); store=PersonalPromptStore(db)
    draft = coding_draft(profile)
    original = store.create(owner.id,{'title':'원본','domainKey':'coding','codingProfile':profile,'prompt':draft['prompt']})
    jobs=CodingOptimizationJobs(); job=jobs.start(owner.id,profile,lambda *_:result,lambda:None,str)
    wait_job(jobs,owner.id,job['id'])
    review={spec.HOLDOUT[0]['id']:{'candidate':{'comments':'match'}}}
    saved=jobs.save(owner.id,job['id'],'새 후보',store,review)
    assert saved['coding_optimization']['human_review'] == review and saved['coding_profile_matches']
    assert store.get(owner.id,original['id']) == original
    assert saved['prompt'] == result['improved_prompt']
    with pytest.raises(ValueError): compose_prompt(draft['prompt'],str(spec.TRAIN[0]['fee']),profile)


def test_http_python_web_has_separate_flag_and_scope_and_rejects_wrong_framework(server,monkeypatch):
    monkeypatch.setattr(api_server,'PYTHON_WEB_GEPA_LIVE',False)
    monkeypatch.setattr(api_server,'_live_key_available',lambda *_:True)
    monkeypatch.setattr(api_server,'FASTAPI_GEPA_LIVE',True)
    path='/coding-instructions/optimizations'
    capabilities=request(server,path)[1]
    assert not capabilities['environments']['flask']['enabled'] and capabilities['environments']['fastapi']['enabled']
    alice=signup(server,'alice'); spent=[]
    monkeypatch.setattr(api_server,'_take',lambda *_:spent.append(1))
    base=coding_draft(PROFILE); body={'profile':PROFILE,'originalPrompt':base['prompt']}
    assert request(server,path,body,alice)[0] == 400 and not spent
    monkeypatch.setattr(api_server,'PYTHON_WEB_GEPA_LIVE',True)
    monkeypatch.setattr(api_server,'CODING_OPTIMIZATIONS',CodingOptimizationJobs())
    monkeypatch.setattr(api_server,'optimize_coding',lambda profile,**kwargs:{'changed':False,'profile':profile})
    assert request(server,path,body)[0] == 401
    assert request(server,path,body,alice)[0] == 202 and spent == [1]
    assert '함수형 뷰' in request(server,path)[1]['environments']['django']['evaluation_scope']
    with pytest.raises(ValueError): coding_draft({**PROFILE,'framework':'Django REST Framework'})

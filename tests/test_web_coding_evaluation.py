import copy
import json

import pytest

import api_server
from auth import AuthService
from coding_environments import environment_kind
from coding_gepa import HEADING, coding_draft, compose_prompt, optimize_coding
from coding_optimization_jobs import CodingOptimizationJobs
from personal_prompts import PersonalPromptStore
from web_coding_evaluation import available, evaluation_for
from tests.test_fastapi_optimization import wait_job
from tests.test_personal_prompts import request, signup
from tests.test_team import db, server

PROFILE = {'language':'TypeScript','framework':'React','preferences':{
    'explanation':'brief','comments':'essential','structure':'compact','output':'complete'},'extra':''}


def answer(task, language, good=True, patch=False):
    code = task['original'].replace('+ 100', f'+ {task["fee"]}' if good else '+ 99')
    if patch:
        code = next(line.strip() for line in code.splitlines() if 'return ' in line and ('<output' in line or 'res.json' in line))
    suffix = ('tsx' if language == 'TypeScript' else 'jsx') if 'Calculator' in task['entry'] else ('ts' if language == 'TypeScript' else 'js')
    return f'### answer.{suffix}\n```{suffix}\n{code}```\n입력과 반환할 값을 확인하세요.'


@pytest.mark.skipif(not available(), reason='Node and existing frontend TypeScript dependency required')
@pytest.mark.parametrize('mode,language', [('react','JavaScript'),('react','TypeScript'),('express','JavaScript'),('express','TypeScript')])
def test_reference_negative_missing_wrong_value_and_patch_context(mode, language):
    spec = evaluation_for(mode, language)
    profile = {**PROFILE,'language':language,'framework':mode.title()}
    task = spec.TRAIN[0]
    result = spec.evaluate(task,answer(task,language),profile)
    assert all(result['checks'].values()), result
    assert result['score'] == 1 and result['preferences']['comments'] is None
    assert not spec.evaluate(task,answer(task,language,False),profile)['checks']['calculation']
    no_guard = answer(task,language).replace(f'{task["left"]} < 0', f'{task["left"]} < -9')
    assert not spec.evaluate(task,no_guard,profile)['checks']['validation']
    if mode == 'express':
        assert not spec.evaluate(task,answer(task,language).replace(task['route'],'/wrong'),profile)['checks']['binding']
    else:
        assert not spec.evaluate(task,answer(task,language).replace(task['key'],'wrong'),profile)['checks']['calculation']
    changed = spec.TRAIN[1]
    changed_profile = {**profile,'preferences':{**profile['preferences'],'output':'changes'}}
    patch = spec.evaluate(changed,answer(changed,language,patch=True),changed_profile)
    assert all(patch['checks'].values()) and patch['preferences']['output'], patch


@pytest.mark.skipif(not available(), reason='Node and existing frontend TypeScript dependency required')
def test_comment_spoofing_generated_side_effects_and_types_in_javascript_do_not_pass(tmp_path):
    spec = evaluation_for('express','JavaScript'); task = spec.TRAIN[0]
    profile = {**PROFILE,'language':'JavaScript','framework':'Express'}
    reference = answer(task,'JavaScript')
    assert not spec.evaluate(task,reference.replace('app.get(', '// app.get('),profile)['checks']['binding']
    marker = tmp_path / 'must-not-be-created'
    dangerous = reference.replace('return res.json', f'require("fs").writeFileSync({json.dumps(str(marker))}, "bad");\nreturn res.json')
    assert not spec.evaluate(task,dangerous,profile)['checks']['calculation'] and not marker.exists()
    assert spec.evaluate(task,'```js\nfunction broken( {\n```',profile)['score'] == 0
    assert not spec.evaluate(task,reference.replace('const months =','const months: number ='),profile)['checks']['syntax']


@pytest.mark.skipif(not available(), reason='Node and existing frontend TypeScript dependency required')
@pytest.mark.parametrize('mode',['react','express'])
def test_separate_calculation_helper_is_followed_instead_of_counting_functions(mode):
    spec = evaluation_for(mode,'TypeScript'); task = spec.TRAIN[0]
    profile = {**PROFILE,'framework':mode.title(),'preferences':{**PROFILE['preferences'],'structure':'modular'}}
    source = answer(task,'TypeScript').replace(f'{task["left"]} * {task["right"]} + {task["fee"]}',f'calculateTotal({task["left"]}, {task["right"]})')
    source = source.replace('export ',"import { calculateTotal } from './total';\nexport ",1)
    source += f'\n### total.ts\n```ts\nexport function calculateTotal(a: number, b: number) {{ return a * b + {task["fee"]}; }}\n```'
    assert all(spec.evaluate(task,source,profile)['checks'].values())
    wrong = source.replace('return a * b +','return a + b +')
    assert not spec.evaluate(task,wrong,profile)['checks']['calculation']
    assert not spec.evaluate(task,source.replace("import { calculateTotal } from './total';",''),profile)['checks']['calculation']
    changed = spec.TRAIN[1]
    function = changed['original'][changed['original'].index('export function'):]
    if mode == 'express': function = function[:function.rfind('app.get(')]
    function = function.replace('+ 100',f'+ {changed["fee"]}').replace(f'{changed["left"]} * {changed["right"]} + {changed["fee"]}',f'calculateTotal({changed["left"]}, {changed["right"]})')
    suffix = 'tsx' if mode == 'react' else 'ts'
    partial = f"```{suffix}\nimport {{ calculateTotal }} from './total';\n{function}```\n```ts\nexport function calculateTotal(a: number, b: number) {{ return a * b + {changed['fee']}; }}\n```"
    change_profile = {**profile,'preferences':{**profile['preferences'],'output':'changes'}}
    assert all(spec.evaluate(changed,partial,change_profile)['checks'].values())


@pytest.mark.skipif(not available(), reason='Node and existing frontend TypeScript dependency required')
def test_gepa_runs_for_new_environment_and_saved_candidate_keeps_original_and_human_review(db):
    spec = evaluation_for('react','TypeScript'); calls = []
    def fake(system,user,model,**kwargs):
        calls.append((system,user,model,str(kwargs['cache_dir'])))
        if model == 'reflection': return '```\n입력 오류 분기와 요청한 계산식을 빠뜨리지 마세요.\n```'
        task = next(task for task in spec.TRAIN + spec.VALIDATION + spec.HOLDOUT if task['input'] == user)
        return answer(task,'TypeScript',HEADING in system)
    snapshot = copy.deepcopy(PROFILE)
    result = optimize_coding(PROFILE,task_model='task',reflection_model='reflection',generate=fake)
    assert PROFILE == snapshot and result['changed']
    assert result['report']['environment'] == 'typescript_react'
    assert result['report']['scoring']['checks'].keys() == {'syntax','binding','validation','calculation'}
    assert result['report']['scoring']['manual_preferences'] == ['comments','structure']
    assert all('typescript_react_gepa' in call[3] for call in calls)
    assert len(calls) == len(set(calls)) and result['report']['model_calls'] <= 32
    assert {task['id'] for task in spec.TRAIN}.isdisjoint(task['id'] for task in spec.VALIDATION+spec.HOLDOUT)
    owner,_ = AuthService(db).signup('alice','password-alice-123')
    store = PersonalPromptStore(db); draft = coding_draft(PROFILE)
    original = store.create(owner.id,{'title':'원본','domainKey':'coding','codingProfile':PROFILE,'prompt':draft['prompt']})
    jobs = CodingOptimizationJobs(); job = jobs.start(owner.id,PROFILE,lambda *_:result,lambda:None,str)
    wait_job(jobs,owner.id,job['id'])
    review = {spec.HOLDOUT[0]['id']:{'candidate':{'structure':'match'}}}
    saved = jobs.save(owner.id,job['id'],'새 React 후보',store,review)
    assert saved['coding_optimization']['human_review'] == review
    assert saved['coding_profile_matches'] and saved['prompt'] == result['improved_prompt']
    assert store.get(owner.id,original['id']) == original
    with pytest.raises(ValueError): compose_prompt(draft['prompt'],str(spec.TRAIN[0]['fee']),PROFILE)


def test_http_web_modes_have_independent_gate_and_unsupported_framework_is_not_promoted(server,monkeypatch):
    monkeypatch.setattr(api_server,'WEB_GEPA_LIVE',True)
    monkeypatch.setattr(api_server,'web_gepa_available',lambda:False)
    monkeypatch.setattr(api_server,'_live_key_available',lambda *_:True)
    path='/coding-instructions/optimizations'
    capabilities=request(server,path)[1]
    assert not capabilities['environments']['typescript_react']['enabled']
    assert 'Node' in capabilities['environments']['typescript_react']['reason']
    monkeypatch.setattr(api_server,'web_gepa_available',lambda:True)
    alice=signup(server,'alice'); spent=[]
    monkeypatch.setattr(api_server,'_take',lambda *_:spent.append(1))
    monkeypatch.setattr(api_server,'CODING_OPTIMIZATIONS',CodingOptimizationJobs())
    base=coding_draft(PROFILE)
    monkeypatch.setattr(api_server,'optimize_coding',lambda profile,**kwargs:{'changed':False,'profile':profile})
    assert request(server,path,{'profile':PROFILE,'originalPrompt':base['prompt']},alice)[0] == 202
    assert spent == [1]
    assert environment_kind({**PROFILE,'framework':'Nuxt'}) is None
    with pytest.raises(ValueError): coding_draft({**PROFILE,'framework':'Nuxt'})

import copy
import json

import pytest

import api_server
from auth import AuthService
from coding_environments import environment_kind
from coding_gepa import HEADING, coding_draft, compose_prompt, optimize_coding
from coding_optimization_jobs import CodingOptimizationJobs
from personal_prompts import PersonalPromptStore
from vue_coding_evaluation import evaluation_for
from web_coding_evaluation import available
from tests.test_fastapi_optimization import wait_job
from tests.test_personal_prompts import request, signup
from tests.test_team import db, server

PROFILE = {'language':'JavaScript','framework':'Vue','preferences':{
    'explanation':'brief','comments':'essential','structure':'compact','output':'complete'},'extra':''}


def answer(task, good=True, part=None):
    code = task['original'].replace('+ 100', f'+ {task["fee"]}' if good else '+ 99')
    if part == 'script': code = code[:code.index('<template>')]
    if part == 'template':
        code = code[code.index('<template>'):].replace('{{ total }}',f'{{{{ props.{task["left"]} * props.{task["right"]} + {task["fee"]} }}}}')
    return f'### Calculator.vue\n```vue\n{code}```\n입력과 표시할 값을 확인하세요.'


@pytest.mark.skipif(not available(), reason='Existing TypeScript parser required')
@pytest.mark.parametrize('language',['JavaScript','TypeScript'])
def test_reference_all_tasks_wrong_value_errors_props_template_and_partial(language):
    spec = evaluation_for(language); profile = {**PROFILE,'language':language}
    for task in spec.TRAIN+spec.VALIDATION+spec.HOLDOUT:
        result = spec.evaluate(task,answer(task),profile)
        assert all(result['checks'].values()) and result['score'] == 1, result
        assert result['preferences']['comments'] is None and result['preferences']['structure'] is None
        assert 'Calculator.vue' in result['observations']['structure']
        assert not spec.evaluate(task,answer(task,False),profile)['checks']['calculation']
        for part in ('script','template') if task['patch'] else ():
            changed = {**profile,'preferences':{**profile['preferences'],'output':'changes'}}
            result = spec.evaluate(task,answer(task,part=part),changed)
            assert all(result['checks'].values()) and result['preferences']['output'],result
    task = spec.TRAIN[0]; reference = answer(task)
    assert not spec.evaluate(task,reference.replace('v-else ',''),profile)['checks']['validation']
    assert not spec.evaluate(task,reference.replace(f'props.{task["left"]} < 0',f'props.{task["left"]} < -9'),profile)['checks']['validation']
    assert not spec.evaluate(task,reference.replace('data-testid="'+task['key']+'"','data-testid="wrong"'),profile)['checks']['calculation']
    assert not spec.evaluate(task,reference.replace('입력 오류','아무것도 없음'),profile)['checks']['validation']
    assert not spec.evaluate(task,reference.replace('</output>','</span>'),profile)['checks']['syntax']
    assert not spec.evaluate(task,reference.replace('defineProps','fakeProps'),profile)['checks']['binding']
    assert not spec.evaluate(task,reference.replace('Number.isFinite','Number.isInteger'),profile)['checks']['binding']
    if language == 'JavaScript':
        assert not spec.evaluate(task,reference.replace('const props =','const props: any ='),profile)['checks']['syntax']
        required = reference.replace(': Number', ': { type: Number, required: true }')
        assert all(spec.evaluate(task,required,profile)['checks'].values())


@pytest.mark.skipif(not available(), reason='Existing TypeScript parser required')
@pytest.mark.parametrize('language',['JavaScript','TypeScript'])
def test_helper_alias_direct_interpolation_and_import_in_partial(language):
    spec=evaluation_for(language); task=spec.TRAIN[1]
    profile={**PROFILE,'language':language,'preferences':{**PROFILE['preferences'],'output':'changes','structure':'modular'}}
    source=answer(task,part='script').replace('{ computed }','{ computed as derive }').replace('computed(', 'derive(')
    source=source.replace(f'props.{task["left"]} * props.{task["right"]} + {task["fee"]}',f'calculate(props.{task["left"]}, props.{task["right"]})')
    suffix='ts' if language=='TypeScript' else 'js'; typed=': number' if suffix=='ts' else ''
    helper=f'export function calculate(a{typed}, b{typed}) {{ return a * b + {task["fee"]}; }}'
    source=source.replace("import {", "import { calculate } from './total';\nimport {",1)
    source+=f'\n### total.{suffix}\n```{suffix}\n{helper}\n```'
    result=spec.evaluate(task,source,profile)
    assert all(result['checks'].values()) and result['preferences']['output'],result
    assert not spec.evaluate(task,source.replace('a * b','a + b'),profile)['checks']['calculation']
    assert not spec.evaluate(task,source.replace("import { calculate } from './total';",''),profile)['checks']['binding']
    assert all(spec.evaluate(task,answer(task,part='template'),profile)['checks'].values())
    split = answer(task,part='script') + '\n' + answer(task,part='template')
    result = spec.evaluate(task,split,profile)
    assert all(result['checks'].values()) and result['preferences']['output']
    assert not spec.evaluate(task,answer(task),profile)['preferences']['output']


@pytest.mark.skipif(not available(), reason='Existing TypeScript parser required')
def test_unsafe_code_spoofing_and_unsupported_sfc_never_execute(tmp_path):
    spec=evaluation_for('JavaScript'); task=spec.TRAIN[0]; source=answer(task)
    marker=tmp_path/'must-not-exist'
    unsafe=source.replace('const total =',f'require("fs").writeFileSync({json.dumps(str(marker))},"bad");\nconst total =')
    assert not spec.evaluate(task,unsafe,PROFILE)['checks']['binding'] and not marker.exists()
    assert not spec.evaluate(task,source.replace("from 'vue'","from 'fake-vue'"),PROFILE)['checks']['binding']
    assert not spec.evaluate(task,source.replace('const props =','const Number = 1;\nconst props ='),PROFILE)['checks']['syntax']
    assert not spec.evaluate(task,'```vue\n<!--'+task['original']+'-->\n```',PROFILE)['checks']['syntax']
    assert not spec.evaluate(task,source.replace('<script setup>','<script>'),PROFILE)['checks']['syntax']
    assert not spec.evaluate(task,source.replace('<p v-if','<p @click="danger()" v-if'),PROFILE)['checks']['syntax']
    assert not spec.evaluate(task,answer(task,part='script'),PROFILE)['checks']['syntax']


@pytest.mark.skipif(not available(), reason='Existing TypeScript parser required')
@pytest.mark.parametrize('language',['JavaScript','TypeScript'])
def test_actual_gepa_with_test_model_new_save_human_review_original_unchanged(language,db):
    profile={**PROFILE,'language':language}; spec=evaluation_for(language); calls=[]
    def fake(system,user,model,**kwargs):
        calls.append((system,user,model,str(kwargs['cache_dir'])))
        if model=='reflection': return '```\n입력 범위와 요청한 계산식, 오류 표시를 확인하세요.\n```'
        task=next(t for t in spec.TRAIN+spec.VALIDATION+spec.HOLDOUT if t['input']==user)
        return answer(task,HEADING in system)
    snapshot=copy.deepcopy(profile)
    result=optimize_coding(profile,task_model='task',reflection_model='reflection',generate=fake)
    assert profile==snapshot and result['changed']
    kind=language.lower()+'_vue'
    assert result['report']['environment']==kind and environment_kind(profile)==kind
    assert result['report']['scoring']['manual_preferences']==['comments','structure']
    assert 'script setup' in result['report']['scoring']['preferences']['output']
    assert all(kind+'_gepa' in call[3] for call in calls) and len(calls)==len(set(calls))
    assert result['report']['model_calls']<=32
    assert len({t['id'] for t in spec.TRAIN+spec.VALIDATION+spec.HOLDOUT})==6
    owner,_=AuthService(db).signup('alice','password-alice-123'); store=PersonalPromptStore(db)
    draft=coding_draft(profile)
    original=store.create(owner.id,{'title':'Vue 원본','domainKey':'coding','codingProfile':profile,'prompt':draft['prompt']})
    jobs=CodingOptimizationJobs(); job=jobs.start(owner.id,profile,lambda *_:result,lambda:None,str); wait_job(jobs,owner.id,job['id'])
    review={spec.HOLDOUT[0]['id']:{'candidate':{'structure':'match'}}}
    saved=jobs.save(owner.id,job['id'],'새 Vue 후보',store,review)
    assert saved['id']!=original['id'] and saved['coding_profile_matches']
    assert store.get(owner.id,saved['id'])['prompt']==result['improved_prompt']
    assert saved['coding_optimization']['human_review']==review
    assert store.get(owner.id,original['id'])==original
    with pytest.raises(ValueError): compose_prompt(draft['prompt'],str(spec.TRAIN[0]['fee']),profile)


def test_http_vue_capability_tool_gate_login_and_disabled_without_quota(server,monkeypatch):
    path='/coding-instructions/optimizations'; spent=[]
    monkeypatch.setattr(api_server,'_live_key_available',lambda *_:True)
    monkeypatch.setattr(api_server,'WEB_GEPA_LIVE',True)
    monkeypatch.setattr(api_server,'web_gepa_available',lambda:False)
    monkeypatch.setattr(api_server,'_take',lambda *_:spent.append(1))
    cap=request(server,path)[1]['environments']
    assert not cap['javascript_vue']['enabled'] and 'Node' in cap['typescript_vue']['reason']
    monkeypatch.setattr(api_server,'web_gepa_available',lambda:True)
    cap=request(server,path)[1]['environments']
    assert cap['javascript_vue']['enabled'] and cap['typescript_vue']['enabled']
    assert 'Vue' in cap['javascript_vue']['evaluation_scope'] and '반응성' in cap['javascript_vue']['evaluation_scope']
    body={'profile':PROFILE,'originalPrompt':coding_draft(PROFILE)['prompt']}
    assert request(server,path,body)[0]==401 and spent==[]
    alice=signup(server,'alice'); monkeypatch.setattr(api_server,'WEB_GEPA_LIVE',False)
    assert request(server,path,body,alice)[0]==400 and spent==[]
    assert environment_kind({**PROFILE,'framework':'Nuxt'}) is None

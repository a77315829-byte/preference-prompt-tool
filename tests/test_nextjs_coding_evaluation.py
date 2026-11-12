import copy
import json

import pytest

import api_server
from auth import AuthService
from coding_environments import environment_kind
from coding_gepa import HEADING, coding_draft, compose_prompt, optimize_coding
from coding_optimization_jobs import CodingOptimizationJobs
from personal_prompts import PersonalPromptStore
from nextjs_coding_evaluation import evaluation_for
from web_coding_evaluation import available
from tests.test_fastapi_optimization import wait_job
from tests.test_personal_prompts import request, signup
from tests.test_team import db, server

PROFILE = {'language':'TypeScript','framework':'Next.js','preferences':{
    'explanation':'brief','comments':'essential','structure':'compact','output':'complete'},'extra':''}


def answer(task, language='TypeScript', good=True, part=None):
    code=task['original'].replace('+ 100',f'+ {task["fee"]}' if good else '+ 99')
    if part=='return': code=next(line.strip() for line in code.splitlines() if 'return NextResponse.json' in line and task['key']+':' in line)
    if part=='function': code=code[code.index('export async function'):].replace('export async','async',1)
    return f'### {task["file"]}\n```{"ts" if language=="TypeScript" else "js"}\n{code}```\n입력과 반환값을 확인하세요.'


@pytest.mark.skipif(not available(),reason='Existing TypeScript parser required')
@pytest.mark.parametrize('language',['JavaScript','TypeScript'])
def test_all_tasks_and_partial_return_or_function(language):
    spec=evaluation_for(language); profile={**PROFILE,'language':language}
    for task in spec.TRAIN+spec.VALIDATION+spec.HOLDOUT:
        result=spec.evaluate(task,answer(task,language),profile)
        assert all(result['checks'].values()) and result['score']==1,result
        assert result['preferences']['comments'] is None and result['preferences']['structure'] is None
        assert not spec.evaluate(task,answer(task,language,False),profile)['checks']['calculation']
        if task['patch']:
            changed={**profile,'preferences':{**profile['preferences'],'output':'changes'}}
            for part in ('return','function'):
                result=spec.evaluate(task,answer(task,language,part=part),changed)
                assert all(result['checks'].values()) and result['preferences']['output'],result
            assert not spec.evaluate(task,answer(task,language),changed)['preferences']['output']


@pytest.mark.skipif(not available(),reason='Existing TypeScript parser required')
@pytest.mark.parametrize('language',['JavaScript','TypeScript'])
def test_wrong_file_export_input_status_empty_missing_and_aliases(language):
    spec=evaluation_for(language); task=spec.TRAIN[0]; profile={**PROFILE,'language':language}; source=answer(task,language)
    assert not spec.evaluate(task,source.replace(task['file'],'app/api/wrong/route.'+('ts' if language=='TypeScript' else 'js')),profile)['checks']['binding']
    assert not spec.evaluate(task,source.replace('export async','async'),profile)['checks']['binding']
    assert not spec.evaluate(task,source.replace('function GET','function POST'),profile)['checks']['binding']
    assert not spec.evaluate(task,source.replace(f"params.get('{task['left']}')","params.get('wrong')"),profile)['checks']['calculation']
    assert not spec.evaluate(task,source.replace('status: 400','status: 200'),profile)['checks']['validation']
    assert not spec.evaluate(task,source.replace(f"{task['left']}Raw.trim() === '' || ",''),profile)['checks']['validation']
    missing=source.replace(f'{task["left"]}Raw === null || ','').replace(f'{task["left"]}Raw.trim()',f"({task['left']}Raw ?? '0').trim()")
    assert not spec.evaluate(task,missing,profile)['checks']['validation']
    alias=source.replace('{ NextResponse','{ NextResponse as Reply').replace('NextResponse.json','Reply.json')
    assert all(spec.evaluate(task,alias,profile)['checks'].values())
    standard=source.replace('NextResponse.json','Response.json').replace('request.nextUrl.searchParams','new URL(request.url).searchParams')
    assert all(spec.evaluate(task,standard,profile)['checks'].values())
    assert all(spec.evaluate(task,source.replace('### app/','### src/app/'),profile)['checks'].values())


@pytest.mark.skipif(not available(),reason='Existing TypeScript parser required')
@pytest.mark.parametrize('language',['JavaScript','TypeScript'])
def test_separate_helper_and_partial_with_needed_import(language):
    spec=evaluation_for(language); task=spec.TRAIN[1]
    profile={**PROFILE,'language':language,'preferences':{**PROFILE['preferences'],'output':'changes','structure':'modular'}}
    source=answer(task,language,part='function').replace('NextResponse.json','Reply.json')
    source=source.replace(f'{task["left"]} * {task["right"]} + {task["fee"]}',f'calculate({task["left"]}, {task["right"]})')
    suffix='ts' if language=='TypeScript' else 'js'; typed=': number' if suffix=='ts' else ''
    source=source.replace('```'+suffix+'\n',"```"+suffix+"\nimport { NextResponse as Reply } from 'next/server';\nimport { calculate } from './total';\n",1)
    source+=f'\n### app/api/total.{suffix}\n```{suffix}\nexport function calculate(a{typed},b{typed}) {{ return a * b + {task["fee"]}; }}\n```'
    result=spec.evaluate(task,source,profile)
    assert all(result['checks'].values()) and result['preferences']['output'],result
    assert not spec.evaluate(task,source.replace('a * b','a + b'),profile)['checks']['calculation']
    assert not spec.evaluate(task,source.replace("import { calculate } from './total';",''),profile)['checks']['calculation']


@pytest.mark.skipif(not available(),reason='Existing TypeScript parser required')
def test_unsafe_code_fake_import_shadow_and_comment_never_execute(tmp_path):
    spec=evaluation_for('TypeScript'); task=spec.TRAIN[0]; source=answer(task)
    marker=tmp_path/'must-not-exist'
    unsafe=source.replace('const params =',f'require("fs").writeFileSync({json.dumps(str(marker))},"bad");\nconst params =')
    assert not spec.evaluate(task,unsafe,PROFILE)['checks']['validation'] and not marker.exists()
    assert not spec.evaluate(task,source.replace("'next/server'","'fake-next'"),PROFILE)['checks']['validation']
    assert not spec.evaluate(task,source.replace('const params =','const Number = 1;\nconst params ='),PROFILE)['checks']['syntax']
    assert not spec.evaluate(task,source.replace('export async function GET','// export async function GET'),PROFILE)['checks']['syntax']
    assert not spec.evaluate(task,source.replace('import { NextResponse, type NextRequest }','import type { NextResponse, NextRequest }'),PROFILE)['checks']['validation']
    assert not spec.evaluate(task,source.replace('export async function GET','export default async function GET'),PROFILE)['checks']['binding']
    assert not spec.evaluate(task,source.replace('### '+task['file'],'### some-file.ts\n// '+task['file']),PROFILE)['checks']['binding']


@pytest.mark.skipif(not available(),reason='Existing TypeScript parser required')
@pytest.mark.parametrize('language',['JavaScript','TypeScript'])
def test_actual_gepa_new_saved_candidate_keeps_original_and_human_review(language,db):
    profile={**PROFILE,'language':language}; spec=evaluation_for(language); calls=[]
    def fake(system,user,model,**kwargs):
        calls.append((system,user,model,str(kwargs['cache_dir'])))
        if model=='reflection': return '```\n입력 누락과 빈 값을 거절하고 요청한 계산식을 확인하세요.\n```'
        task=next(t for t in spec.TRAIN+spec.VALIDATION+spec.HOLDOUT if t['input']==user)
        return answer(task,language,HEADING in system)
    snapshot=copy.deepcopy(profile)
    result=optimize_coding(profile,task_model='task',reflection_model='reflection',generate=fake)
    assert result['changed'] and profile==snapshot
    kind=language.lower()+'_nextjs'
    assert result['report']['environment']==kind and environment_kind(profile)==kind
    assert result['report']['scoring']['manual_preferences']==['comments','structure']
    assert 'export GET' in result['report']['scoring']['preferences']['output']
    assert all(kind+'_gepa' in call[3] for call in calls) and len(calls)==len(set(calls))
    assert result['report']['model_calls']<=32 and len({t['id'] for t in spec.TRAIN+spec.VALIDATION+spec.HOLDOUT})==6
    owner,_=AuthService(db).signup('alice','password-alice-123'); store=PersonalPromptStore(db); draft=coding_draft(profile)
    original=store.create(owner.id,{'title':'Next 원본','domainKey':'coding','codingProfile':profile,'prompt':draft['prompt']})
    jobs=CodingOptimizationJobs(); job=jobs.start(owner.id,profile,lambda *_:result,lambda:None,str); wait_job(jobs,owner.id,job['id'])
    review={spec.HOLDOUT[0]['id']:{'candidate':{'structure':'match'}}}
    saved=jobs.save(owner.id,job['id'],'새 Next 후보',store,review)
    assert saved['id']!=original['id'] and saved['coding_profile_matches']
    assert store.get(owner.id,saved['id'])['prompt']==result['improved_prompt']
    assert saved['coding_optimization']['human_review']==review
    assert store.get(owner.id,original['id'])==original
    with pytest.raises(ValueError): compose_prompt(draft['prompt'],str(spec.TRAIN[0]['fee']),profile)


def test_http_next_capability_tool_gate_and_disabled_without_spending(server,monkeypatch):
    path='/coding-instructions/optimizations'; spent=[]
    monkeypatch.setattr(api_server,'_live_key_available',lambda *_:True)
    monkeypatch.setattr(api_server,'WEB_GEPA_LIVE',True)
    monkeypatch.setattr(api_server,'web_gepa_available',lambda:False)
    monkeypatch.setattr(api_server,'_take',lambda *_:spent.append(1))
    cap=request(server,path)[1]['environments']
    assert not cap['typescript_nextjs']['enabled'] and 'Node' in cap['javascript_nextjs']['reason']
    monkeypatch.setattr(api_server,'web_gepa_available',lambda:True)
    cap=request(server,path)[1]['environments']
    assert cap['typescript_nextjs']['enabled'] and cap['javascript_nextjs']['enabled']
    assert 'App Router' in cap['typescript_nextjs']['evaluation_scope'] and '캐싱' in cap['typescript_nextjs']['evaluation_scope']
    body={'profile':PROFILE,'originalPrompt':coding_draft(PROFILE)['prompt']}
    assert request(server,path,body)[0]==401 and spent==[]
    alice=signup(server,'alice'); monkeypatch.setattr(api_server,'WEB_GEPA_LIVE',False)
    assert request(server,path,body,alice)[0]==400 and spent==[]
    assert environment_kind({**PROFILE,'framework':'Nuxt'}) is None

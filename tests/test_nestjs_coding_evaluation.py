import copy
import json

import pytest

import api_server
from auth import AuthService
from coding_environments import environment_kind
from coding_gepa import HEADING, coding_draft, compose_prompt, optimize_coding
from coding_optimization_jobs import CodingOptimizationJobs
from personal_prompts import PersonalPromptStore
from nestjs_coding_evaluation import evaluation_for
from web_coding_evaluation import available
from tests.test_fastapi_optimization import wait_job
from tests.test_personal_prompts import request, signup
from tests.test_team import db, server

PROFILE = {'language':'TypeScript','framework':'NestJS','preferences':{
    'explanation':'brief','comments':'essential','structure':'compact','output':'complete'},'extra':''}
pytestmark = pytest.mark.skipif(not available(),reason='Existing TypeScript parser required')


def answer(task,good=True,part=None):
    source=task['original'].replace('+ 100',f'+ {task["fee"]}' if good else '+ 99')
    if part=='return': source=next(line.strip() for line in source.splitlines() if 'return {' in line)
    if part=='method': source=source[source.index("  @Get("):source.index('\n}\n@Module')]
    return f'### quote.controller.ts\n```ts\n{source}```\n입력과 반환값을 확인하세요.'


def service_source(task):
    source=answer(task)
    helper=f"@Injectable()\nexport class PricingService {{ calculate(a: number,b: number) {{ return a * b + {task['fee']}; }} }}\n"
    source=source.replace('Controller, Get','Injectable, Controller, Get').replace('@Controller(',helper+'@Controller(',1)
    source=source.replace('export class QuoteController {','export class QuoteController {\n  constructor(private readonly pricing: PricingService) {}')
    source=source.replace(f'{task["left"]} * {task["right"]} + {task["fee"]}',f'this.pricing.calculate({task["left"]}, {task["right"]})')
    return source.replace('controllers: [QuoteController]','controllers: [QuoteController], providers: [PricingService]')


def test_all_tasks_partial_method_return_and_unchanged_original():
    spec=evaluation_for()
    for task in spec.TRAIN+spec.VALIDATION+spec.HOLDOUT:
        result=spec.evaluate(task,answer(task),PROFILE)
        assert all(result['checks'].values()) and result['score']==1,result
        assert result['preferences']['comments'] is None and result['preferences']['structure'] is None
        assert not spec.evaluate(task,answer(task,False),PROFILE)['checks']['calculation']
        if task['patch']:
            changed={**PROFILE,'preferences':{**PROFILE['preferences'],'output':'changes'}}
            for part in ('method','return'):
                result=spec.evaluate(task,answer(task,part=part),changed)
                assert all(result['checks'].values()) and result['preferences']['output'],result
            assert not spec.evaluate(task,answer(task),changed)['preferences']['output']


def test_route_query_module_input_and_exception_are_real_ast_not_comment_counts():
    spec=evaluation_for(); task=spec.TRAIN[0]; source=answer(task)
    for wrong in [source.replace("@Get('quote')","@Post('quote')"),source.replace(task['prefix'],'wrong-prefix'),
                  source.replace(f"@Query('{task['left']}')","@Query('wrong')"),source.replace('controllers: [QuoteController]','controllers: []')]:
        assert not spec.evaluate(task,wrong,PROFILE)['checks']['binding']
    assert not spec.evaluate(task,source.replace(f'{task["left"]} < 0',f'{task["left"]} < -9'),PROFILE)['checks']['validation']
    assert not spec.evaluate(task,source.replace(f"{task['left']}Raw.trim() === '' || ",''),PROFILE)['checks']['validation']
    assert not spec.evaluate(task,source.replace("throw new BadRequestException('입력 오류')","return { error: '입력 오류' }"),PROFILE)['checks']['validation']
    assert not spec.evaluate(task,source.replace('throw new BadRequestException','throw new Error'),PROFILE)['checks']['validation']
    assert not spec.evaluate(task,source.replace("@Get('quote')","@HttpCode(500)\n  @Get('quote')"),PROFILE)['checks']['binding']
    assert not spec.evaluate(task,source.replace(f"@Query('{task['left']}')",f"@Query('{task['left']}', ParseIntPipe)"),PROFILE)['checks']['binding']
    alias=source.replace('Controller, Get','Controller as Endpoint, Get as Read').replace('@Controller(','@Endpoint(').replace('@Get(','@Read(')
    assert all(spec.evaluate(task,alias,PROFILE)['checks'].values())


def test_provider_registration_injection_and_actual_calculation_are_followed():
    spec=evaluation_for(); task=spec.TRAIN[0]; source=service_source(task)
    result=spec.evaluate(task,source,PROFILE)
    assert all(result['checks'].values()),result
    assert not spec.evaluate(task,source.replace('a * b','a + b'),PROFILE)['checks']['calculation']
    assert not spec.evaluate(task,source.replace(', providers: [PricingService]',''),PROFILE)['checks']['binding']
    assert not spec.evaluate(task,source.replace('@Injectable()',''),PROFILE)['checks']['binding']
    assert not spec.evaluate(task,source.replace('pricing: PricingService','pricing: MissingService'),PROFILE)['checks']['binding']
    assert not spec.evaluate(task,source.replace('this.pricing.calculate','this.pricing.missing'),PROFILE)['checks']['calculation']


def test_split_controller_service_module_requires_import_connections():
    spec=evaluation_for(); task=spec.TRAIN[0]
    source=service_source(task).split('```ts\n',1)[1].split('```',1)[0]
    imports=source[:source.index('@Injectable()')]
    service=source[source.index('@Injectable()'):source.index('@Controller(')]
    controller=source[source.index('@Controller('):source.index('@Module(')]
    module=source[source.index('@Module('):]
    answer= (f"```ts\n{imports}{service}```\n```ts\n{imports}import {{ PricingService }} from './pricing.service';\n{controller}```\n"
             f"```ts\n{imports}import {{ PricingService }} from './pricing.service';\nimport {{ QuoteController }} from './quote.controller';\n{module}```")
    result=spec.evaluate(task,answer,PROFILE)
    assert all(result['checks'].values()),result
    assert not spec.evaluate(task,answer.replace("import { QuoteController } from './quote.controller';",''),PROFILE)['checks']['binding']
    assert not spec.evaluate(task,answer.replace("import { PricingService } from './pricing.service';",''),PROFILE)['checks']['binding']
    assert not spec.evaluate(task,answer.replace('import { PricingService }','import type { PricingService }'),PROFILE)['checks']['binding']


def test_partial_with_import_alias_and_separate_pure_function():
    spec=evaluation_for(); task=spec.TRAIN[1]; profile={**PROFILE,'preferences':{**PROFILE['preferences'],'output':'changes'}}
    source=answer(task,part='method').replace('new BadRequestException','new InvalidInput')
    source=source.replace(f'{task["left"]} * {task["right"]} + {task["fee"]}',f'calculate({task["left"]},{task["right"]})')
    source+= f"\n```ts\nimport {{ BadRequestException as InvalidInput }} from '@nestjs/common';\nimport {{ calculate }} from './total';\n```\n```ts\nexport function calculate(a: number,b: number) {{ return a * b + {task['fee']}; }}\n```"
    result=spec.evaluate(task,source,profile)
    assert all(result['checks'].values()) and result['preferences']['output'],result
    assert not spec.evaluate(task,source.replace('a * b','a + b'),profile)['checks']['calculation']


def test_unsafe_fake_import_shadow_syntax_and_dependency_cycles_never_execute(tmp_path):
    spec=evaluation_for(); task=spec.TRAIN[0]; source=answer(task); marker=tmp_path/'must-not-exist'
    unsafe=source.replace('const '+task['left']+' =',f'require("fs").writeFileSync({json.dumps(str(marker))},"bad");\nconst {task["left"]} =')
    assert not spec.evaluate(task,unsafe,PROFILE)['checks']['validation'] and not marker.exists()
    assert not spec.evaluate(task,source.replace("'@nestjs/common'","'fake-nest'"),PROFILE)['checks']['binding']
    assert not spec.evaluate(task,source.replace('import {','import type {'),PROFILE)['checks']['binding']
    assert not spec.evaluate(task,source.replace('const '+task['left']+' =','const Number = 1;\nconst '+task['left']+' ='),PROFILE)['checks']['syntax']
    assert not spec.evaluate(task,source.replace('@Controller(','// @Controller('),PROFILE)['checks']['binding']
    assert not spec.evaluate(task,'```ts\n@Controller( {\n```',PROFILE)['checks']['syntax']
    cycle=service_source(task).replace('export class PricingService {','export class PricingService { constructor(private readonly nested: PricingService) {}')
    assert not spec.evaluate(task,cycle,PROFILE)['checks']['binding']


def test_actual_gepa_candidate_saved_with_human_review_and_original_preserved(db):
    spec=evaluation_for(); calls=[]
    def fake(system,user,model,**kwargs):
        calls.append((system,user,model,str(kwargs['cache_dir'])))
        if model=='reflection': return '```\n필수 입력과 모듈 등록, 요청한 계산식을 확인하세요.\n```'
        task=next(t for t in spec.TRAIN+spec.VALIDATION+spec.HOLDOUT if t['input']==user)
        return answer(task,HEADING in system)
    snapshot=copy.deepcopy(PROFILE)
    result=optimize_coding(PROFILE,task_model='task',reflection_model='reflection',generate=fake)
    assert result['changed'] and PROFILE==snapshot
    assert result['report']['environment']=='typescript_nestjs' and environment_kind(PROFILE)=='typescript_nestjs'
    assert result['report']['scoring']['manual_preferences']==['comments','structure']
    assert 'Controller' in result['report']['scoring']['preferences']['output']
    assert all('typescript_nestjs_gepa' in call[3] for call in calls) and len(calls)==len(set(calls))
    assert result['report']['model_calls']<=32 and len({t['id'] for t in spec.TRAIN+spec.VALIDATION+spec.HOLDOUT})==6
    owner,_=AuthService(db).signup('alice','password-alice-123'); store=PersonalPromptStore(db); draft=coding_draft(PROFILE)
    original=store.create(owner.id,{'title':'Nest 원본','domainKey':'coding','codingProfile':PROFILE,'prompt':draft['prompt']})
    jobs=CodingOptimizationJobs(); job=jobs.start(owner.id,PROFILE,lambda *_:result,lambda:None,str); wait_job(jobs,owner.id,job['id'])
    review={spec.HOLDOUT[0]['id']:{'candidate':{'structure':'match'}}}
    saved=jobs.save(owner.id,job['id'],'새 Nest 후보',store,review)
    assert saved['id']!=original['id'] and saved['coding_profile_matches']
    assert store.get(owner.id,saved['id'])['prompt']==result['improved_prompt']
    assert saved['coding_optimization']['human_review']==review and store.get(owner.id,original['id'])==original
    with pytest.raises(ValueError): compose_prompt(draft['prompt'],str(spec.TRAIN[0]['fee']),PROFILE)


def test_http_nest_gate_login_and_other_language_not_promoted(server,monkeypatch):
    path='/coding-instructions/optimizations'; spent=[]
    monkeypatch.setattr(api_server,'_live_key_available',lambda *_:True)
    monkeypatch.setattr(api_server,'WEB_GEPA_LIVE',True)
    monkeypatch.setattr(api_server,'web_gepa_available',lambda:False)
    monkeypatch.setattr(api_server,'_take',lambda *_:spent.append(1))
    cap=request(server,path)[1]['environments']
    assert not cap['typescript_nestjs']['enabled'] and 'Node' in cap['typescript_nestjs']['reason']
    monkeypatch.setattr(api_server,'web_gepa_available',lambda:True)
    cap=request(server,path)[1]['environments']
    assert cap['typescript_nestjs']['enabled'] and '서비스 주입' in cap['typescript_nestjs']['evaluation_scope']
    body={'profile':PROFILE,'originalPrompt':coding_draft(PROFILE)['prompt']}
    assert request(server,path,body)[0]==401 and spent==[]
    alice=signup(server,'alice'); monkeypatch.setattr(api_server,'WEB_GEPA_LIVE',False)
    assert request(server,path,body,alice)[0]==400 and spent==[]
    assert environment_kind({**PROFILE,'language':'JavaScript'}) is None
    with pytest.raises(ValueError): coding_draft({**PROFILE,'language':'JavaScript'})

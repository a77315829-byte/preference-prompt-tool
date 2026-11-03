import copy
import threading

import pytest

import api_server
from app_db import Database
from auth import AuthService
from coding_gepa import HEADING, coding_draft, compose_prompt, optimize_coding
from coding_optimization_jobs import CodingOptimizationJobs
from personal_prompts import PersonalPromptStore
from spring_boot_evaluation import TRAIN, VALIDATION, HOLDOUT, evaluate
from tests.test_fastapi_optimization import wait_job, PROFILE as FASTAPI_PROFILE
from tests.test_personal_prompts import request, signup
from tests.test_team import db, server

PROFILE = {'language': 'Java', 'framework': 'Spring Boot', 'preferences': {
    'explanation': 'brief', 'comments': 'essential', 'structure': 'compact', 'output': 'complete'}, 'extra': ''}
GUIDANCE = '필수 입력값의 음수 거절과 요구한 반환 계산식을 빠뜨리지 마세요.'


def answer(task, good=True):
    code = task['original'].replace('+ 100L', f'+ {task["fee"]}L' if good else '+ 99L')
    return f'### PriceController.java\n```java\n{code}```\n입력과 계산 결과를 확인하세요.'


def test_reference_source_contract_and_wrong_or_spoofed_patterns():
    task = TRAIN[0]
    good = evaluate(task, answer(task), PROFILE)
    assert all(good['checks'].values()) and good['score'] == 1
    assert not evaluate(task, answer(task, False), PROFILE)['checks']['calculation']
    assert not evaluate(task, answer(task).replace(task['route'], '/wrong'), PROFILE)['checks']['route']
    named = answer(task).replace(f'@RequestParam("{task["left"]}")', f'@RequestParam(name="{task["left"]}", required=true)')
    assert all(evaluate(task, named, PROFILE)['checks'].values())
    assert not evaluate(task, named.replace(f'name="{task["left"]}"', 'name="wrong"'), PROFILE)['checks']['calculation']
    assert not evaluate(task, answer(task).replace('import org.springframework.web.bind.annotation.*;', ''), PROFILE)['checks']['route']
    assert not evaluate(task, answer(task).replace(f'{task["left"]} < 0 || ', ''), PROFILE)['checks']['validation']
    assert not evaluate(task, answer(task).replace('throw new ResponseStatusException(HttpStatus.BAD_REQUEST);', '// throw new ResponseStatusException(HttpStatus.BAD_REQUEST);'), PROFILE)['checks']['validation']
    assert not evaluate(task, answer(task).replace('@GetMapping', '// @GetMapping'), PROFILE)['checks']['route']
    assert evaluate(task, '```java\nclass Broken {\n```', PROFILE)['score'] == 0
    side_effect = answer(task).replace('return Map.of', 'Runtime.getRuntime().exec("do-not-run");\n        return Map.of')
    assert not evaluate(task, side_effect, PROFILE)['checks']['calculation']


def test_changed_return_and_complete_method_are_checked_in_existing_context():
    task = TRAIN[1]
    profile = copy.deepcopy(PROFILE); profile['preferences']['output'] = 'changes'
    change = f'return Map.of("{task["key"]}", {task["left"]} * {task["right"]} + {task["fee"]}L);'
    result = evaluate(task, f'```java\n{change}\n```', profile)
    assert all(result['checks'].values()) and result['preferences']['output']
    source = task['original'].replace('+ 100L', f'+ {task["fee"]}L')
    method = source[source.index('@GetMapping'):source.rfind('}')].strip()
    assert all(evaluate(task, f'```java\n{method}\n```', profile)['checks'].values())


def test_separated_service_and_class_level_route_mapping():
    task = TRAIN[0]
    source = answer(task).replace('public class PriceController {', 'public class PriceController {\n    private final PriceService service;\n    public PriceController(PriceService service) { this.service = service; }')
    start = source.index('        if (')
    end = source.index('\n    }', start)
    method_body = source[start:end]
    source = source[:start] + f'        return Map.of("{task["key"]}", service.total({task["left"]}, {task["right"]}));' + source[end:]
    service = ('import org.springframework.stereotype.Service;\nimport org.springframework.http.HttpStatus;\n'
               'import org.springframework.web.server.ResponseStatusException;\n@Service\nclass PriceService {\n'
               f'    public long total(long {task["left"]}, long {task["right"]}) {{\n'
               + method_body.replace(f'Map.of("{task["key"]}", ', '').replace('L);', 'L;') + '\n    }\n}')
    combined = source + f'\n### PriceService.java\n```java\n{service}\n```'
    profile = copy.deepcopy(PROFILE); profile['preferences']['structure'] = 'modular'
    evaluated = evaluate(task, combined, profile)
    assert all(evaluated['checks'].values()) and evaluated['preferences']['structure'] is None, evaluated
    assert 'PriceService' in evaluated['observations']['structure']
    assert all(evaluate(task, combined.replace('service.total(', 'this.service.total('), profile)['checks'].values())
    prefix, suffix = task['route'].rsplit('/', 1)
    mapped = answer(task).replace('@RestController', f'@RestController\n@RequestMapping("{prefix}")').replace(f'@GetMapping("{task["route"]}")', f'@GetMapping("/{suffix}")')
    assert all(evaluate(task, mapped, PROFILE)['checks'].values())


def test_real_gepa_core_uses_only_spring_tasks_and_separate_cache():
    calls = []
    def fake(system, user, model, **kwargs):
        calls.append((system, user, model, kwargs['cache_dir']))
        if model == 'reflection': return f'```\n{GUIDANCE}\n```'
        task = next(t for t in TRAIN + VALIDATION + HOLDOUT if t['input'] == user)
        return answer(task, HEADING in system)
    original = copy.deepcopy(PROFILE)
    result = optimize_coding(PROFILE, task_model='task', reflection_model='reflection', generate=fake)
    assert PROFILE == original and result['changed']
    assert result['improved_prompt'].startswith(result['original_prompt'] + HEADING)
    assert result['report']['environment'] == 'spring_boot' and result['report']['version'] == 'spring-boot-static-v2'
    report = result['report']
    assert report['scoring']['gate'] == 'code_structure'
    assert len(report['validation_before_details']['tasks']) == 2
    assert report['validation_after_details']['score'] == report['validation_after']
    assert 'PriceController' in report['holdout_after']['tasks'][0]['observations']['structure']
    assert result['report']['validation_after'] > result['report']['validation_before']
    assert result['report']['holdout_after']['score'] > result['report']['holdout_before']['score']
    assert result['report']['model_calls'] <= 32 and result['report']['reflection_calls'] > 0
    assert all('spring_boot_gepa' in str(path) for _, _, _, path in calls)
    assert len(calls) == len(set(calls))
    assert {t['id'] for t in TRAIN}.isdisjoint(t['id'] for t in VALIDATION + HOLDOUT)
    assert {t['id'] for t in VALIDATION}.isdisjoint(t['id'] for t in HOLDOUT)


def test_draft_scope_and_leak_filter_follow_the_selected_framework():
    base = coding_draft(PROFILE)
    with pytest.raises(ValueError): coding_draft({**PROFILE, 'framework': 'Quarkus'})
    with pytest.raises(ValueError): coding_draft({**PROFILE, 'language': 'Python'})
    with pytest.raises(ValueError): compose_prompt(base['prompt'], TRAIN[0]['route'], PROFILE)
    with pytest.raises(ValueError): compose_prompt(base['prompt'], str(TRAIN[0]['fee']), PROFILE)
    assert compose_prompt(base['prompt'], GUIDANCE, PROFILE).startswith(base['prompt'])


def test_spring_candidate_save_restart_reuse_and_old_fastapi_preserved(db):
    owner, _ = AuthService(db).signup('alice', 'alice-password-123')
    store = PersonalPromptStore(db)
    originals = []
    for profile in (PROFILE, FASTAPI_PROFILE):
        draft = coding_draft(profile)
        originals.append(store.create(owner.id, {'title': profile['framework'], 'domainKey': 'coding', 'codingProfile': profile, 'prompt': draft['prompt']}))
    base = coding_draft(PROFILE)
    jobs = CodingOptimizationJobs()
    job = jobs.start(owner.id, PROFILE, lambda *_: {'profile': PROFILE, 'original_prompt': base['prompt'],
        'guidance': GUIDANCE, 'improved_prompt': compose_prompt(base['prompt'], GUIDANCE, PROFILE), 'changed': True,
        'report': {'environment': 'spring_boot', 'version': 'spring-boot-static-v1'}}, lambda: None, str)
    wait_job(jobs, owner.id, job['id'])
    saved = jobs.save(owner.id, job['id'], '새 Spring Boot 후보', store)
    assert saved['id'] not in {p['id'] for p in originals} and saved['coding_profile_matches']
    restored = PersonalPromptStore(Database(db.path)).get(owner.id, saved['id'])
    assert restored == saved and restored['coding_optimization']['original_prompt'] == base['prompt']
    assert restored['prompt'].endswith(GUIDANCE) and restored['coding_profile'] == PROFILE
    for old in originals: assert store.get(owner.id, old['id']) == old
    with pytest.raises(ValueError):
        store.create(owner.id, {'title': '위조', 'domainKey': 'coding', 'prompt': saved['prompt'], 'codingProfile': PROFILE,
                               'optimization': saved['coding_optimization']})


def test_shared_job_slots_prevent_switching_framework_to_bypass_running_job():
    jobs = CodingOptimizationJobs(); release = threading.Event(); spent = []
    def pending(*_):
        assert release.wait(3)
        return {'changed': False}
    try:
        job = jobs.start(1, FASTAPI_PROFILE, pending, lambda: spent.append(1), str)
        with pytest.raises(ValueError, match='진행 중'):
            jobs.start(1, PROFILE, pending, lambda: spent.append(2), str)
        assert spent == [1]
    finally: release.set()
    wait_job(jobs, 1, job['id'])


def test_http_spring_mode_is_separate_and_server_result_cannot_be_forged(server, monkeypatch):
    monkeypatch.setattr(api_server, 'CODING_OPTIMIZATIONS', CodingOptimizationJobs())
    monkeypatch.setattr(api_server, 'FASTAPI_GEPA_LIVE', True)
    monkeypatch.setattr(api_server, 'SPRING_BOOT_GEPA_LIVE', False)
    monkeypatch.setattr(api_server, '_live_key_available', lambda *_: True)
    spent = []; monkeypatch.setattr(api_server, '_take', lambda *_: spent.append(1))
    alice = signup(server, 'alice'); bob = signup(server, 'bob')
    base = coding_draft(PROFILE)
    payload = {'profile': PROFILE, 'originalPrompt': base['prompt']}
    path = '/coding-instructions/optimizations'
    available = request(server, path)[1]
    assert available['environments']['fastapi']['enabled'] and not available['environments']['spring_boot']['enabled']
    assert request(server, path, payload, alice)[0] == 400 and not spent
    monkeypatch.setattr(api_server, 'SPRING_BOOT_GEPA_LIVE', True)
    monkeypatch.setattr(api_server, 'optimize_coding', lambda profile, **kwargs: {'profile': profile, 'original_prompt': base['prompt'],
        'improved_prompt': compose_prompt(base['prompt'], GUIDANCE, profile), 'guidance': GUIDANCE, 'changed': True,
        'report': {'environment': 'spring_boot', 'version': 'spring-boot-static-v1'}})
    assert request(server, path, payload)[0] == 401
    assert request(server, path, {**payload, 'originalPrompt': 'stale'}, alice)[0] == 400 and not spent
    status, result, _ = request(server, path, payload, alice)
    assert status == 202 and spent == [1]
    job = result['job']; wait_job(api_server.CODING_OPTIMIZATIONS, api_server.AUTH.user_for(alice.split('=', 1)[1]).id, job['id'])
    route = path + '/' + job['id']
    assert request(server, route, cookie=bob)[0] == 404
    assert request(server, route+'/save', {'title': '타인'}, bob)[0] == 404
    status, saved, _ = request(server, route+'/save', {'title': 'Spring 새 항목', 'prompt': 'forged', 'owner': 2}, alice)
    assert status == 201 and saved['preference']['coding_profile']['language'] == 'Java'
    assert saved['preference']['prompt'] != 'forged' and saved['preference']['coding_profile_matches']

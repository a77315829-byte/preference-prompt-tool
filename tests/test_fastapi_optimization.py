import copy
import threading
import time
from types import SimpleNamespace

import pytest

import api_server
from auth import AuthService
from coding_instructions import build_coding_instructions
from coding_optimization_jobs import CodingOptimizationJobs
from fastapi_evaluation import TRAIN, VALIDATION, HOLDOUT, evaluate
from fastapi_optimization import HEADING, compose_prompt, fastapi_draft, optimize_fastapi
from personal_prompts import PersonalPromptStore
from tests.test_personal_prompts import request, signup
from tests.test_team import db, server

PROFILE = {'language': 'Python', 'framework': 'FastAPI', 'preferences': {
    'explanation': 'brief', 'comments': 'essential', 'structure': 'compact', 'output': 'complete'}, 'extra': ''}
GUIDANCE = '입력 제약과 반환할 JSON 값을 확인하고 요청한 계산을 빠뜨리지 마라.'


def answer(task, good=True):
    code = task['original'].replace('+ 100', f'+ {task["fee"]}' if good else '+ 99')
    return f'### main.py\n```python\n{code}```\n입력과 계산 결과를 확인하세요.'


def wait_job(jobs, owner, job_id):
    for _ in range(300):
        job = jobs.get(owner, job_id)
        if job['status'] != 'running':
            return job
        time.sleep(.01)
    pytest.fail('background job did not complete')


def test_static_checker_rejects_wrong_contract_and_never_executes_code(tmp_path):
    task = TRAIN[0]
    good = evaluate(task, answer(task), PROFILE)
    assert all(good['checks'].values()) and good['score'] == 1
    bad = evaluate(task, answer(task, False), PROFILE)
    assert not bad['checks']['calculation'] and bad['score'] < good['score']
    marker = tmp_path / 'must-not-exist'
    dangerous = answer(task).replace('return {', f'__import__("pathlib").Path({str(marker)!r}).touch()\n    return {{')
    assert not evaluate(task, dangerous, PROFILE)['checks']['calculation']
    assert not marker.exists()
    assert evaluate(task, '```python\ndef broken(\n```', PROFILE)['score'] == 0
    no_validation = answer(task).replace('Query(ge=0)', '0')
    assert not evaluate(task, no_validation, PROFILE)['checks']['validation']
    assert not evaluate(task, answer(task).replace(task['route'], '/wrong'), PROFILE)['checks']['route']


def test_change_snippet_is_checked_in_original_context_and_modular_helpers_work():
    task = TRAIN[1]
    profile = copy.deepcopy(PROFILE); profile['preferences']['output'] = 'changes'
    snippet = f'```python\nreturn {{"{task["key"]}": {task["left"]} * {task["right"]} + {task["fee"]}}}\n```'
    result = evaluate(task, snippet, profile)
    assert all(result['checks'].values()) and result['preferences']['output']
    modular = answer(TRAIN[0]).replace('return {"amount": price * quantity + 500}', 'return {"amount": total(price, quantity)}')
    modular = modular.replace('```\n입력', '\ndef total(price, quantity):\n    return price * quantity + 500\n```\n입력')
    assert evaluate(TRAIN[0], modular, PROFILE)['checks']['calculation']
    assert {t['id'] for t in TRAIN}.isdisjoint(t['id'] for t in VALIDATION + HOLDOUT)
    assert {t['id'] for t in VALIDATION}.isdisjoint(t['id'] for t in HOLDOUT)


def test_real_gepa_core_runs_with_fake_models_preserves_base_and_reports_unseen_tasks():
    calls = []
    def fake_generate(system, user, model, **kwargs):
        calls.append((system, user, model))
        if model == 'fake-reflection':
            return f'```\n{GUIDANCE}\n```'
        task = next(t for t in TRAIN + VALIDATION + HOLDOUT if t['input'] == user)
        return answer(task, HEADING in system)
    original = copy.deepcopy(PROFILE)
    report = optimize_fastapi(PROFILE, task_model='fake-task', reflection_model='fake-reflection', generate=fake_generate)
    assert PROFILE == original
    assert report['changed'] and report['guidance'] == GUIDANCE
    assert report['improved_prompt'].startswith(build_coding_instructions(PROFILE)['prompt'] + HEADING)
    assert report['report']['validation_after'] > report['report']['validation_before']
    assert report['report']['holdout_after']['score'] > report['report']['holdout_before']['score']
    assert report['report']['reflection_calls'] > 0 and report['report']['model_calls'] <= 32
    assert len(calls) == len(set(calls)), 'identical model requests must be memoized'


def test_nonimproving_or_leaking_candidate_returns_original():
    def optimizer(**kwargs):
        return SimpleNamespace(candidates=[{'guidance': ''}, {'guidance': TRAIN[0]['route']}], val_aggregate_scores=[.5, 1])
    result = optimize_fastapi(PROFILE, task_model='fake', reflection_model='fake', optimizer=optimizer,
        generate=lambda system, user, model, **kw: answer(next(t for t in TRAIN + VALIDATION + HOLDOUT if t['input'] == user)))
    assert not result['changed'] and result['original_prompt'] == result['improved_prompt']
    with pytest.raises(ValueError):
        fastapi_draft({**PROFILE, 'framework': 'Django'})
    with pytest.raises(ValueError):
        compose_prompt(result['original_prompt'], 'x'*4001)


def test_jobs_are_owner_scoped_deduplicate_and_save_only_new_server_result(db):
    user, _ = AuthService(db).signup('alice', 'alice-password-123')
    other, _ = AuthService(db).signup('bob', 'bob-password-123')
    store = PersonalPromptStore(db)
    base = build_coding_instructions(PROFILE)
    original = store.create(user.id, {'title': '원본', 'domainKey': 'coding', 'prompt': base['prompt'], 'codingProfile': PROFILE})
    jobs = CodingOptimizationJobs(); released = threading.Event(); consumed = []
    result = {'profile': PROFILE, 'original_prompt': base['prompt'], 'improved_prompt': compose_prompt(base['prompt'], GUIDANCE),
              'guidance': GUIDANCE, 'changed': True, 'report': {'version': 'test'}}
    def run(*_):
        assert released.wait(3)
        return result
    job = jobs.start(user.id, PROFILE, run, lambda: consumed.append(1), str)
    assert jobs.start(user.id, PROFILE, run, lambda: consumed.append(1), str)['id'] == job['id']
    assert consumed == [1]
    with pytest.raises(LookupError): jobs.get(other.id, job['id'])
    with pytest.raises(ValueError): jobs.save(user.id, job['id'], '아직 안 됨', store)
    released.set(); assert wait_job(jobs, user.id, job['id'])['status'] == 'done'
    saved = jobs.save(user.id, job['id'], 'GEPA 후보', store)
    assert saved['id'] != original['id'] and saved['prompt'] == result['improved_prompt']
    assert saved['coding_optimization']['original_prompt'] == original['prompt']
    assert saved['coding_profile_matches'] and saved['coding_profile'] == PROFILE
    assert store.get(user.id, original['id']) == original
    assert jobs.save(user.id, job['id'], 'retry', store)['id'] == saved['id']
    assert len(store.list_for(user.id)) == 2
    # Public create cannot forge a validated optimization with client metadata.
    with pytest.raises(ValueError):
        store.create(user.id, {'title': '위조', 'domainKey': 'coding', 'prompt': saved['prompt'], 'codingProfile': PROFILE,
                              'optimization': saved['coding_optimization']})
    edited = store.update(user.id, saved['id'], {'title': '직접 수정', 'domainKey': 'coding', 'prompt': '수동 편집', 'revision': 1})
    assert not edited['coding_profile_matches'] and edited['coding_optimization'] == saved['coding_optimization']


def test_http_start_status_save_permissions_mode_and_forged_body(server, monkeypatch):
    jobs = CodingOptimizationJobs()
    monkeypatch.setattr(api_server, 'CODING_OPTIMIZATIONS', jobs)
    monkeypatch.setattr(api_server, 'FASTAPI_GEPA_LIVE', False)
    monkeypatch.setattr(api_server, '_live_key_available', lambda *_: True)
    consumed = []
    monkeypatch.setattr(api_server, '_take', lambda *_: consumed.append(1))
    alice = signup(server, 'alice'); bob = signup(server, 'bob')
    base = build_coding_instructions(PROFILE)
    payload = {'profile': PROFILE, 'originalPrompt': base['prompt']}
    assert request(server, '/coding-instructions/optimizations', payload)[0] == 401
    assert request(server, '/coding-instructions/optimizations', payload, alice)[0] == 400
    assert not consumed
    monkeypatch.setattr(api_server, 'FASTAPI_GEPA_LIVE', True)
    assert request(server, '/coding-instructions/optimizations', cookie=alice)[1]['enabled'] is True
    assert request(server, '/coding-instructions/optimizations', {**payload, 'originalPrompt': 'stale'}, alice)[0] == 400
    monkeypatch.setattr(api_server, 'optimize_fastapi', lambda profile, **kw: {
        'profile': profile, 'original_prompt': base['prompt'], 'improved_prompt': compose_prompt(base['prompt'], GUIDANCE),
        'guidance': GUIDANCE, 'changed': True, 'report': {'version': 'test'}})
    status, data, _ = request(server, '/coding-instructions/optimizations', payload, alice)
    assert status == 202 and consumed == [1]
    path = '/coding-instructions/optimizations/' + data['job']['id']
    wait_job(jobs, api_server.AUTH.user_for(alice.split('=', 1)[1]).id, data['job']['id'])
    assert request(server, path, cookie=bob)[0] == 404
    assert request(server, path+'/save', {'title': '타인'}, bob)[0] == 404
    assert request(server, path+'/save', {'title': ' '}, alice)[0] == 400
    status, saved, _ = request(server, path+'/save', {'title': '새 후보', 'prompt': 'FORGED', 'profile': {}}, alice)
    assert status == 201 and saved['preference']['prompt'] != 'FORGED'
    assert request(server, '/preferences/'+saved['preference']['id'], cookie=alice)[1]['preference']['coding_optimization']['method'] == 'gepa'


def test_failures_release_running_slot_and_do_not_produce_saveable_item():
    jobs = CodingOptimizationJobs()
    def fail(*_): raise RuntimeError('private provider failure')
    job = jobs.start(1, PROFILE, fail, lambda: None, lambda _: '안전한 오류 안내')
    done = wait_job(jobs, 1, job['id'])
    assert done['status'] == 'error' and done['error'] == '안전한 오류 안내' and done['result'] is None
    assert jobs.start(1, PROFILE, fail, lambda: None, str)['id'] != job['id']


def test_call_budget_and_concurrent_jobs_are_bounded_before_spending():
    calls = []
    def too_many_reflections(**kwargs):
        for _ in range(8):
            kwargs['reflection_lm'](str(len(calls)))
    with pytest.raises(ValueError, match='한도'):
        optimize_fastapi(PROFILE, task_model='fake', reflection_model='fake', optimizer=too_many_reflections,
            generate=lambda *args, **kwargs: calls.append(args) or '새 안내')
    assert len(calls) == 4
    jobs = CodingOptimizationJobs(); release = threading.Event(); consumed = []
    def pending(*_):
        assert release.wait(3)
        return {'changed': False}
    try:
        first = jobs.start(1, PROFILE, pending, lambda: consumed.append(1), str)
        jobs.start(2, PROFILE, pending, lambda: consumed.append(2), str)
        with pytest.raises(ValueError, match='다른 개선'):
            jobs.start(3, PROFILE, pending, lambda: consumed.append(3), str)
        with pytest.raises(ValueError, match='진행 중'):
            jobs.start(1, {**PROFILE, 'extra': '한국어로 설명'}, pending, lambda: consumed.append(4), str)
        assert consumed == [1, 2]
    finally:
        release.set()
    wait_job(jobs, 1, first['id'])

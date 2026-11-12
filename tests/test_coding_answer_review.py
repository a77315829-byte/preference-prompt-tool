import copy
import pytest

from coding_answer_review import inspect_answer, validate_human_review
from coding_instructions import build_coding_instructions
from coding_optimization_jobs import CodingOptimizationJobs
from coding_gepa import compose_prompt
from personal_prompts import PersonalPromptStore
from auth import AuthService
from tests.test_spring_boot_optimization import PROFILE, answer
from tests.test_fastapi_optimization import wait_job
from tests.test_team import db, server
from tests.test_personal_prompts import request
from spring_boot_evaluation import TRAIN, evaluate


@pytest.mark.parametrize('heading', ['### 1. 입력 확인', '## 2) 로직 구현', '1. 입력 확인', '### 1단계: 입력 확인', '## 단계 2: 로직 구현'])
def test_numbered_headings_are_explanation_evidence_not_code_or_version_numbers(heading):
    profile = {**PROFILE, 'preferences': {**PROFILE['preferences'], 'explanation': 'steps'}}
    prose = f'{heading}\n' + '입력을 검증한 뒤 핵심 계산을 수행하고 반환 형식을 맞춥니다. 주요 선택 이유와 적용 방법을 단계별로 설명합니다. ' * 2
    assert inspect_answer(profile, prose)['preferences']['explanation']
    assert not inspect_answer(profile, '버전 1.8을 사용합니다. ' * 10 + '\n```java\n// ### 1. 코드 안 번호\n```')['preferences']['explanation']


def test_comment_and_class_spam_does_not_raise_score_and_patch_structure_is_not_penalized():
    base = answer(TRAIN[0])
    noisy = base.replace('```\n입력', '// 값 대입\n// 또 값 대입\nclass Empty {}\nclass MoreEmpty {}\n```\n입력')
    a, b = evaluate(TRAIN[0], base, PROFILE), evaluate(TRAIN[0], noisy, PROFILE)
    assert a['score'] == b['score']
    assert a['preferences']['comments'] is None and b['preferences']['structure'] is None
    assert '개수로 적절함을 판정하지 않음' in b['observations']['comments']
    patch = inspect_answer(PROFILE, '```java\nreturn Map.of("amount", service.total(price, quantity));\n```', True)
    assert patch['preferences']['structure'] is None
    assert '생략된 구조를 부족으로 판단하지 않음' in patch['observations']['structure']


@pytest.mark.parametrize('language', ['Python','Java','JavaScript','TypeScript','C','C++','C#','Go','Rust','Kotlin','Swift','Dart','PHP','Ruby','Elixir'])
def test_shared_review_accepts_all_listed_and_custom_environments_without_execution(language):
    profile = {**PROFILE, 'language': language, 'framework': '직접 입력한 도구'}
    result = inspect_answer(profile, '설명\n```text\nSystem.exit(1);\n```')
    assert result['version'] == 'coding-answer-review-v2'
    assert result['manual_required'] == ['comments', 'structure', 'output']
    assert result['preferences']['comments'] is None


def test_strings_are_not_comment_evidence_and_input_is_bounded():
    result = inspect_answer(PROFILE, '```java\nString value = "// fake";\n// 음수인 입력을 먼저 거절해요.\n```')
    assert 'fake' not in result['observations']['comments'] and '음수인 입력' in result['observations']['comments']
    with pytest.raises(ValueError): inspect_answer(PROFILE, 'x' * 24001)
    with pytest.raises(ValueError): inspect_answer(PROFILE, '')


def test_human_review_is_owner_scoped_new_item_metadata_and_cannot_replace_automatic_result(db):
    owner, _ = AuthService(db).signup('alice', 'password-alice-123')
    store = PersonalPromptStore(db)
    draft = build_coding_instructions(PROFILE)
    old = store.create(owner.id, {'title':'원본','domainKey':'coding','codingProfile':PROFILE,'prompt':draft['prompt']})
    guidance = '입력 제약을 확인하세요.'
    result = {'profile':PROFILE,'original_prompt':draft['prompt'],'improved_prompt':compose_prompt(draft['prompt'],guidance,PROFILE),
        'guidance':guidance,'changed':True,'report':{'holdout_before':{'tasks':[{'id':'one','label':'예시'}]},'version':'spring-boot-static-v2'}}
    snapshot = copy.deepcopy(result)
    jobs = CodingOptimizationJobs()
    job = jobs.start(owner.id,PROFILE,lambda *_:result,lambda:None,str)
    wait_job(jobs,owner.id,job['id'])
    with pytest.raises(ValueError): jobs.save(owner.id,job['id'],'위조',store,{'one':{'candidate':{'score':100}}})
    with pytest.raises(LookupError): jobs.save(owner.id+1,job['id'],'타인',store,{})
    review = {'one':{'original':{'comments':'needs_work'},'candidate':{'comments':'match','structure':'unsure'}}}
    saved = jobs.save(owner.id,job['id'],'내가 확인한 후보',store,review)
    assert saved['coding_optimization']['human_review'] == review
    assert saved['coding_optimization']['report'] == snapshot['report'] and result == snapshot
    assert store.get(owner.id,old['id']) == old
    assert jobs.save(owner.id,job['id'],'다시 저장',store,{}) == saved
    with pytest.raises(ValueError): validate_human_review({'unknown':{}},{'one'},True)


def test_http_review_works_without_live_model_or_login_and_rejects_bad_input(server, monkeypatch):
    import api_server
    monkeypatch.setattr(api_server,'optimize_coding',lambda *_:pytest.fail('no model/optimizer calls'))
    profile = {**PROFILE,'language':'C++','framework':'Qt'}
    status, data, _ = request(server,'/coding-instructions/review',{'profile':profile,'answer':'```cpp\n// 입력 범위를 먼저 확인합니다.\nint main() {}\n```'})
    assert status == 200 and data['inspection']['preferences']['structure'] is None
    assert request(server,'/coding-instructions/review',{'profile':profile,'answer':'x'*24001})[0] == 400


def test_v2_reuses_same_model_response_from_v1_cache_without_provider_call(tmp_path, monkeypatch):
    import json
    from engine import generator
    from coding_gepa import cached_generation
    current = tmp_path / 'spring-boot-static-v2'
    legacy = tmp_path / 'spring-boot-static-v1'
    legacy.mkdir()
    (legacy / (generator._cache_key('system','task','model')+'.json')).write_text(json.dumps({'output':'cached answer'}),encoding='utf-8')
    monkeypatch.setattr(generator,'generate_with_prompt',lambda *_args,**_kwargs:pytest.fail('cached answer must not be called again'))
    assert cached_generation('system','task','model',cache_dir=current,max_output_tokens=4000) == 'cached answer'

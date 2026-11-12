"""Shared bounded GEPA runner for supported coding environments."""
from __future__ import annotations

import json
from pathlib import Path

from coding_instructions import build_coding_instructions
from coding_evaluation_report import scoring_rules
from coding_environments import ENVIRONMENTS, environment_kind
import fastapi_evaluation

MAX_MODEL_CALLS = 32
MAX_REFLECTION_CALLS = 4
METRIC_CALLS = 18
HEADING = '\n\n## GEPA 보충 안내\n아래 안내가 기존 개발 환경·선호·추가 선호와 충돌하면 기존 지침을 우선하라.\n'


def cached_generation(system, user, model, *, cache_dir, max_output_tokens):
    from engine.generator import _cache_key, generate_with_prompt
    # Evaluation versions change scores, not a previously cached model response.
    legacy = cache_dir.with_name(cache_dir.name.rsplit('-v', 1)[0] + '-v1') / f'{_cache_key(system, user, model)}.json'
    if legacy.is_file():
        try:
            output = json.loads(legacy.read_text(encoding='utf-8'))['output']
            if isinstance(output, str) and output.strip():
                return output
        except (ValueError, KeyError, OSError):
            pass
    return generate_with_prompt(system, user, model, cache_dir=cache_dir, max_output_tokens=max_output_tokens)


def coding_optimization_kind(profile):
    return environment_kind(profile)


def coding_draft(raw):
    draft = build_coding_instructions(raw)
    if coding_optimization_kind(draft['profile']) is None:
        raise ValueError('현재 GEPA는 Python의 FastAPI/Flask/Django, Java/Spring Boot, JavaScript·TypeScript의 React/Express/Vue/Next.js와 TypeScript/NestJS에서 사용할 수 있어요.')
    return draft


def evaluation_for(profile):
    kind = coding_optimization_kind(profile)
    if kind == 'fastapi':
        return fastapi_evaluation
    if kind == 'spring_boot':
        import spring_boot_evaluation
        return spring_boot_evaluation
    if kind in ('flask','django'):
        from python_web_evaluation import evaluation_for as python_web_evaluation
        return python_web_evaluation(kind)
    if kind in ENVIRONMENTS and ENVIRONMENTS[kind][2] == 'vue':
        from vue_coding_evaluation import evaluation_for as vue_evaluation
        return vue_evaluation(profile['language'])
    if kind in ENVIRONMENTS and ENVIRONMENTS[kind][2] == 'nextjs':
        from nextjs_coding_evaluation import evaluation_for as nextjs_evaluation
        return nextjs_evaluation(profile['language'])
    if kind == 'typescript_nestjs':
        import nestjs_coding_evaluation
        return nestjs_coding_evaluation.evaluation_for()
    if kind in ENVIRONMENTS and ENVIRONMENTS[kind][2] in ('react', 'express'):
        from web_coding_evaluation import evaluation_for as web_evaluation
        return web_evaluation(ENVIRONMENTS[kind][2], profile['language'])
    raise ValueError('지원하지 않는 GEPA 개발 환경입니다.')


def compose_prompt(original, guidance, profile=None):
    spec = evaluation_for(profile) if profile is not None else fastapi_evaluation
    if not isinstance(guidance, str) or len(guidance) > 4000 or '\x00' in guidance:
        raise ValueError('GEPA 보충 안내의 형식을 확인하지 못했어요.')
    # Prepared task answers must not become a permanent user instruction.
    if any(t['route'] in guidance or str(t['fee']) in guidance for t in spec.TRAIN + spec.VALIDATION + spec.HOLDOUT):
        raise ValueError('특정 평가 과제 내용이 들어간 후보를 제외했어요.')
    return original + HEADING + guidance.strip() if guidance.strip() else original


def optimize_coding(profile, *, task_model, reflection_model, progress=None, generate=None, optimizer=None):
    from gepa import optimize
    from gepa.adapters.default_adapter.default_adapter import DefaultAdapter, EvaluationResult
    from gepa.core.adapter import EvaluationBatch
    if generate is None:
        generate = cached_generation
    draft = coding_draft(profile)
    profile, original = draft['profile'], draft['prompt']
    spec = evaluation_for(profile)
    TRAIN, VALIDATION, HOLDOUT = spec.TRAIN, spec.VALIDATION, spec.HOLDOUT
    VERSION, LIMITATION, evaluate = spec.VERSION, spec.LIMITATION, spec.evaluate
    kind = coding_optimization_kind(profile)
    cache_dir = Path(__file__).resolve().parent / 'cache' / f'{kind}_gepa' / VERSION
    calls = {'task': 0, 'reflection': 0}
    memo = {}

    def notify(stage):
        if progress:
            progress({'stage': stage, 'model_calls': sum(calls.values()), 'call_limit': MAX_MODEL_CALLS})

    def model_call(system, user, model, kind):
        key = (system, user, model)
        if key not in memo:
            if sum(calls.values()) >= MAX_MODEL_CALLS or (kind == 'reflection' and calls[kind] >= MAX_REFLECTION_CALLS):
                raise ValueError('이번 개선의 AI 호출 한도에 도달했어요. 원본은 그대로 유지됩니다.')
            calls[kind] += 1
            notify('GEPA가 지침을 다듬는 중' if kind == 'reflection' else '준비 과제의 답변을 확인하는 중')
            output = generate(system, user, model, cache_dir=cache_dir, max_output_tokens=4000)
            if not isinstance(output, str) or not output.strip() or len(output) > 24000:
                raise ValueError('AI 응답이 비었거나 너무 길어요. 원본은 그대로 유지됩니다.')
            memo[key] = output
        return memo[key]

    class LockedAdapter(DefaultAdapter):
        def evaluate(self, batch, candidate, capture_traces=False):
            try:
                effective = compose_prompt(original, candidate['guidance'], profile)
            except (ValueError, KeyError):
                feedback = '기존 선호를 보존하는 일반적인 보충 안내만 제안하세요. 과제 경로·정답·숫자 복사는 허용하지 않습니다.'
                return EvaluationBatch(outputs=[{'full_assistant_response': ''} for _ in batch], scores=[0.0]*len(batch),
                    trajectories=[{'data': t, 'full_assistant_response': '', 'feedback': feedback} for t in batch] if capture_traces else None)
            return super().evaluate(batch, {'guidance': effective}, capture_traces)

    adapter = LockedAdapter(
        model=lambda messages: model_call(messages[0]['content'], messages[1]['content'], task_model, 'task'),
        evaluator=lambda task, output: EvaluationResult(**{k: v for k, v in evaluate(task, output, profile).items() if k in ('score', 'feedback')}))

    def reflect(prompt):
        content = prompt if isinstance(prompt, str) else json.dumps(prompt, ensure_ascii=False)
        return model_call('Improve only the supplementary guidance component. The application always keeps the original user instructions fixed. '
                          'Do not include task-specific answers, routes or numeric constants. Return the proposed component in the exact format requested below.',
                          content, reflection_model, 'reflection')

    notify('GEPA 평가를 준비하는 중')
    result = (optimizer or optimize)(seed_candidate={'guidance': ''}, trainset=TRAIN, valset=VALIDATION,
        adapter=adapter, reflection_lm=reflect, max_metric_calls=METRIC_CALLS, reflection_minibatch_size=2,
        stop_callbacks=lambda _state: calls['reflection'] >= MAX_REFLECTION_CALLS,
        display_progress_bar=False, seed=0)

    def assess(prompt, tasks):
        rows = []
        for task in tasks:
            response = model_call(prompt, task['input'], task_model, 'task')
            rows.append({'id': task['id'], 'label': task['label'], 'request': task['input'], 'response': response,
                         **evaluate(task, response, profile)})
        return {'score': round(sum(r['score'] for r in rows)/len(rows), 4), 'tasks': rows,
                'contracts_passed': sum(all(r['checks'].values()) for r in rows)}

    before_val = assess(original, VALIDATION)
    guidance, improved, after_val = '', original, before_val
    for idx in sorted(range(len(result.candidates)), key=lambda i: result.val_aggregate_scores[i], reverse=True):
        if result.val_aggregate_scores[idx] <= result.val_aggregate_scores[0]:
            break
        candidate = result.candidates[idx].get('guidance')
        try:
            prompt = compose_prompt(original, candidate, profile)
        except ValueError:
            continue
        candidate_val = assess(prompt, VALIDATION)
        if candidate_val['score'] > before_val['score'] and candidate_val['contracts_passed'] >= before_val['contracts_passed']:
            guidance, improved, after_val = candidate.strip(), prompt, candidate_val
            break
    notify('개선에 쓰지 않은 별도 과제를 확인하는 중')
    before_test = assess(original, HOLDOUT)
    after_test = assess(improved, HOLDOUT) if improved != original else before_test
    rules = scoring_rules(kind, profile)
    if hasattr(spec, 'CHECK_RULES'):
        rules['checks'] = spec.CHECK_RULES
        rules['preferences']['output'] = getattr(spec,'OUTPUT_RULE','변경 부분 과제는 제공된 기존 파일의 함수 또는 마지막 return 줄에 적용. 전체/새 구현은 선택한 프레임워크 import 포함 여부로 형식만 확인.')
    report = {'version': VERSION, 'environment': kind, 'limitation': LIMITATION, 'validation_before': before_val['score'],
              'validation_after': after_val['score'], 'holdout_before': before_test, 'holdout_after': after_test,
              'validation_before_details': before_val, 'validation_after_details': after_val,
              'scoring': rules,
              'train_tasks': len(TRAIN), 'validation_tasks': len(VALIDATION), 'holdout_tasks': len(HOLDOUT),
              'model_calls': sum(calls.values()), 'task_calls': calls['task'], 'reflection_calls': calls['reflection'],
              'call_limit': MAX_MODEL_CALLS, 'task_model': task_model, 'reflection_model': reflection_model,
              'preference_checks': getattr(spec, 'PREFERENCE_CHECKS', '설명 길이·번호, 주석 수, 함수·파일 수, 변경/전체 출력의 형식 대리 검사입니다. 사용자 만족도는 직접 비교해야 합니다.')}
    return {'profile': profile, 'original_prompt': original, 'improved_prompt': improved,
            'guidance': guidance, 'changed': improved != original, 'report': report}

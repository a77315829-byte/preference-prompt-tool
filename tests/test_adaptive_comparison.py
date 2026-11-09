"""Optional comparison completion and evidence validation; no paid model calls."""
import copy

import pytest

import api_server
import service
from coding_elicitation import AXES, build_adaptive_coding_elicitation, summarize_rounds
from coding_instructions import build_coding_instructions
from tests.test_coding_elicitation import profile
from tests.test_personal_prompts import request, signup
from tests.test_team import db, server


def adaptive_profile(count, *, skip=(), conflict=()):
    raw = profile('Python', 'FastAPI')
    bank = build_adaptive_coding_elicitation(raw)
    rows = []
    for index, pair in enumerate(bank['pairs'][:count]):
        value = raw['preferences'][pair['axis']]
        if index in skip:
            value = None
        elif index in conflict:
            value = next(option['value'] for option in pair['options'] if option['value'] != value)
        rows.append({'id': pair['id'], 'value': value})
    summary = summarize_rounds(rows, bank, allow_single=True)
    return {**raw, 'comparison': {'version': 4, 'rounds': rows, 'example': bank['source'],
        'choices': {axis: summary[axis]['value'] for axis in AXES}}}


@pytest.mark.parametrize('count', [1, 4, 6, 8])
def test_any_answered_prefix_can_finish_and_preserves_evidence_strength(count):
    draft = build_coding_instructions(adaptive_profile(count))
    comparison = draft['profile']['comparison']
    assert len(comparison['rounds']) == count
    assert comparison['stop_reason'] == ('consistent' if count == 8 else 'user')
    assert f'예시 {count}회' in draft['prompt']
    for index, axis in enumerate(AXES):
        expected = 'consistent' if count > index + 4 else 'single' if count > index else 'unresolved'
        assert comparison['summary'][axis]['status'] == expected
    assert build_coding_instructions(draft['profile']) == draft


def test_skip_and_conflict_are_not_filled_with_default_preferences():
    raw = adaptive_profile(8, skip=(1, 5), conflict=(4,))
    comparison = build_coding_instructions(raw)['profile']['comparison']
    assert comparison['choices']['comments'] is None
    assert comparison['summary']['comments']['status'] == 'unresolved'
    assert comparison['choices']['explanation'] is None
    assert comparison['summary']['explanation']['status'] == 'mixed'
    assert comparison['stop_reason'] == 'limit'
    raw['comparison']['choices']['explanation'] = 'brief'
    with pytest.raises(ValueError, match='미확정'):
        build_coding_instructions(raw)


@pytest.mark.parametrize('mutation', ['empty', 'too_many', 'gap', 'duplicate', 'invalid_value', 'environment', 'missing_source', 'unseen_choice'])
def test_partial_records_still_require_valid_order_environment_and_choices(mutation):
    raw = adaptive_profile(4)
    comparison = raw['comparison']
    if mutation == 'empty': comparison['rounds'] = []
    elif mutation == 'too_many': comparison['rounds'] *= 3
    elif mutation == 'gap': comparison['rounds'].pop(0)
    elif mutation == 'duplicate': comparison['rounds'][1] = copy.deepcopy(comparison['rounds'][0])
    elif mutation == 'invalid_value': comparison['rounds'][0]['value'] = ['brief']
    elif mutation == 'environment': raw['framework'] = ''
    elif mutation == 'missing_source': comparison['example'] = None
    elif mutation == 'unseen_choice':
        comparison['rounds'].pop()
        comparison['choices']['output'] = raw['preferences']['output']
    with pytest.raises(ValueError):
        build_coding_instructions(raw)


def test_api_partial_comparison_save_reopen_and_legacy_protocol(server, monkeypatch):
    monkeypatch.setattr(api_server, '_take', lambda *_: pytest.fail('No model calls allowed'))
    raw = adaptive_profile(1)
    plain = {key: value for key, value in raw.items() if key != 'comparison'}
    status, data, _ = request(server, '/coding-instructions/examples', {'profile': plain, 'protocol': 'adaptive-v1'})
    assert status == 200 and data['examples']['version'] == 4
    assert data['examples']['max_rounds'] == 8 and not data['examples']['followups']
    assert request(server, '/coding-instructions/examples', {'profile': plain, 'protocol': 'repeated-v1'})[1]['examples']['version'] == 3
    draft = request(server, '/coding-instructions/preview', {'profile': raw})[1]['draft']
    cookie = signup(server, 'adaptive-user')
    status, data, _ = request(server, '/preferences', {'title': '1회 비교 후 직접 확인', 'domainKey': 'coding',
        'prompt': draft['prompt'], 'codingProfile': draft['profile']}, cookie)
    assert status == 201
    saved = request(server, f"/preferences/{data['preference']['id']}", cookie=cookie)[1]['preference']
    assert saved['coding_profile'] == draft['profile']
    assert request(server, '/coding-instructions/preview', {'profile': saved['coding_profile']})[1]['draft'] == draft


@pytest.mark.parametrize('domain_key', ['summarization', 'summarization_ko'])
def test_summary_stops_automatically_before_eight_and_undo_reopens(domain_key, monkeypatch):
    generated = []
    real_generate = service._generate_pair

    def track(state, *args):
        generated.append(state.answered)
        return real_generate(state, *args)

    monkeypatch.setattr(service, '_generate_pair', track)
    state = service.start_session('A sentence. Another sentence. ' * 30, domain_key,
        f'domains/{domain_key}.yaml', model='unused', demo_mode=True)
    preference = {'length': 'short', 'extractiveness': 'fully'}
    while not state.done:
        axis = next(key for key in preference if state.pair.a.combo[key] != state.pair.b.combo[key])
        chosen = 'a' if state.pair.a.combo[axis] == preference[axis] else 'b'
        state = service.submit_choice(state, state.pair.pair_id, chosen)
    assert state.answered < 8
    assert state.completion_reason == 'selection_resolved'
    assert len(generated) == state.answered  # No extra pair generated after completion.
    assert all(axis.total_rounds == state.answered for axis in state.axes)
    count, last_choice = state.answered, state.history[-1][2]
    state = service.undo_choice(state)
    assert not state.done and state.completion_reason is None
    assert state.total_rounds == state.round_limit and state.pair is not None
    state = service.submit_choice(state, state.pair.pair_id, last_choice)
    assert state.done and state.answered == count


def test_ties_and_budget_end_do_not_claim_a_preference_was_found():
    for limit in (1, 8):
        state = service.start_session('문서입니다. ' * 30, 'summarization_ko',
            'domains/summarization_ko.yaml', model='unused', demo_mode=True, total_rounds=limit)
        while not state.done:
            state = service.submit_choice(state, state.pair.pair_id, 'tie')
        assert state.answered <= limit
        assert state.completion_reason in ('round_limit', 'no_more_pairs')
        assert all(axis.estimate is None for axis in state.axes)

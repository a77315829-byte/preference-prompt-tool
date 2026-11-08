import ast
import copy

import pytest

from coding_elicitation import AXES, build_coding_elicitation, summarize_rounds
from coding_examples import SNIPPETS
from coding_instructions import build_coding_instructions


def profile(language='Python', framework=''):
    return {'language': language, 'framework': framework, 'extra': '', 'preferences':
            {'explanation': 'brief', 'comments': 'essential', 'structure': 'compact', 'output': 'complete'}}


def completed(raw, mixed=()):
    bank = build_coding_elicitation(raw)
    rows = []
    for index, pair in enumerate(bank['pairs']):
        value = raw['preferences'][pair['axis']]
        if index >= 4 and pair['axis'] in mixed:
            value = next(option['value'] for option in pair['options'] if option['value'] != value)
        rows.append({'id': pair['id'], 'value': value})
    for pair in bank['followups']:
        if pair['axis'] in list(mixed)[:2]:
            rows.append({'id': pair['id'], 'value': raw['preferences'][pair['axis']]})
    summary = summarize_rounds(rows, bank)
    return {**raw, 'comparison': {'version': 3, 'example': bank['source'], 'rounds': rows,
                                'choices': {axis: summary[axis]['value'] for axis in AXES}}}


@pytest.mark.parametrize('language', SNIPPETS)
def test_each_language_has_distinct_contexts_and_balanced_option_positions(language):
    raw = profile(language)
    bank = build_coding_elicitation(raw)
    assert len(bank['pairs']) == 8 and len(bank['followups']) == 4
    assert bank['pairs'][0]['options'][0]['value'] == bank['pairs'][4]['options'][1]['value']
    assert bank['pairs'][0]['options'][0]['code'] != bank['pairs'][4]['options'][1]['code']
    result = build_coding_instructions(completed(raw))
    assert all(item['consistent'] for item in result['profile']['comparison']['summary'].values())
    assert '8회' in result['prompt']


def test_conflicts_stay_unresolved_after_followup_and_cannot_be_forged():
    raw = completed(profile('Python', 'FastAPI'), ('explanation', 'comments', 'structure'))
    result = build_coding_instructions(raw)
    assert len(result['profile']['comparison']['rounds']) == 10
    assert result['profile']['comparison']['summary']['explanation']['status'] == 'mixed'
    assert result['profile']['comparison']['choices']['explanation'] is None
    forged = copy.deepcopy(raw)
    forged['comparison']['choices']['explanation'] = 'brief'
    with pytest.raises(ValueError, match='미확정'):
        build_coding_instructions(forged)
    for mutate in ('remove', 'duplicate', 'environment'):
        altered = copy.deepcopy(raw)
        if mutate == 'remove': altered['comparison']['rounds'].pop()
        elif mutate == 'duplicate': altered['comparison']['rounds'][1] = altered['comparison']['rounds'][0]
        else: altered['framework'] = ''
        with pytest.raises(ValueError):
            build_coding_instructions(altered)


def test_transformed_python_examples_parse_without_execution():
    for framework in ('', 'FastAPI'):
        bank = build_coding_elicitation(profile('Python', framework))
        for pair in bank['pairs'] + bank['followups']:
            if pair['axis'] == 'output':
                continue  # Partial patches intentionally require their displayed before context.
            for option in pair['options']:
                for file in option.get('files', [{'code': option['code']}]):
                    ast.parse(file['code'])

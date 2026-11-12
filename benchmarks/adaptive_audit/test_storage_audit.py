"""Read-only production audit. All database writes use pytest's local tmp_path."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app_db import Database
from coding_elicitation import AXES, build_adaptive_coding_elicitation, build_coding_elicitation, summarize_rounds
from coding_framework_examples import framework_example_source
from coding_gepa import coding_draft, compose_prompt
from coding_instructions import build_coding_instructions
from coding_work_exports import export_preview
from personal_prompts import PersonalPromptStore


def profile(version=4, count=1, language='Python', framework='FastAPI'):
    raw = dict(language=language, framework=framework, extra='', preferences=dict(
        explanation='brief', comments='essential', structure='compact', output='complete'))
    if version < 3:
        raw['comparison'] = dict(version=version, choices=raw['preferences'].copy())
        if version == 2:
            raw['comparison']['example'] = framework_example_source(language, framework)
        return raw
    bank = (build_adaptive_coding_elicitation if version == 4 else build_coding_elicitation)(raw)
    rounds = [dict(id=p['id'], value=raw['preferences'][p['axis']]) for p in bank['pairs'][:count]]
    summary = summarize_rounds(rounds, bank, allow_single=version == 4)
    raw['comparison'] = dict(version=version, rounds=rounds, example=bank['source'],
                             choices={axis: summary[axis]['value'] for axis in AXES})
    return raw


@pytest.mark.parametrize('version,count', [(1, 0), (2, 0), (3, 8)] + [(4, n) for n in range(1, 9)])
def test_roundtrip_and_manual_override(version, count, tmp_path):
    raw = profile(version, count)
    # This is the exact shape used by choosePreference after comparison.
    raw['preferences']['explanation'] = 'steps'
    raw['comparison']['choices']['explanation'] = None
    draft = build_coding_instructions(raw)
    db = Database(tmp_path / 'audit.db')
    with db.connect() as conn:
        conn.execute("INSERT INTO users(id, username, password_hash, created_at) VALUES (1, 'audit', 'unused', 'now')")
    store = PersonalPromptStore(db)
    saved = store.create(1, dict(title='audit', domainKey='coding', prompt=draft['prompt'], codingProfile=draft['profile']))
    reopened = PersonalPromptStore(Database(db.path)).get(1, saved['id'])
    assert reopened['coding_profile'] == draft['profile']
    assert reopened['coding_profile_matches'] is True
    assert build_coding_instructions(reopened['coding_profile']) == draft
    assert coding_draft(reopened['coding_profile']) == draft
    assert draft['prompt'] in export_preview({'prompt': draft['prompt']})['content']
    guidance = '검증할 입력 조건을 먼저 확인하라.'
    optimized = compose_prompt(draft['prompt'], guidance, draft['profile'])
    improved = store.create(1, dict(title='improved', domainKey='coding', prompt=optimized, codingProfile=draft['profile']),
        optimization=dict(method='gepa', original_prompt=draft['prompt'], guidance=guidance, report={}))
    assert improved['coding_profile'] == draft['profile']
    assert improved['coding_optimization']['original_prompt'] == draft['prompt']


def test_new_v4_rejects_other_language_evidence():
    raw = profile(language='Python', framework='')
    original_label = raw['comparison']['example']['label']
    raw['language'] = 'Ruby'
    assert original_label.startswith('Python')
    with pytest.raises(ValueError):
        build_coding_instructions(raw)


@pytest.mark.parametrize('mutation', ['summary', 'reason', 'source_label'])
def test_client_derived_metadata_is_ignored(mutation):
    raw = profile()
    expected = build_coding_instructions(raw)
    if mutation == 'summary': raw['comparison']['summary'] = {'explanation': {'status': 'consistent', 'value': 'steps'}}
    if mutation == 'reason': raw['comparison']['stop_reason'] = 'consistent'
    if mutation == 'source_label': raw['comparison']['example']['label'] = 'forged'
    assert build_coding_instructions(raw) == expected


@pytest.mark.parametrize('bad', [False, True, 1, 1.2, [], {}, 'other'])
def test_v4_malformed_round_value_rejected(bad):
    raw = profile()
    raw['comparison']['rounds'][0]['value'] = bad
    with pytest.raises(ValueError):
        build_coding_instructions(raw)


def test_v3_malformed_source_is_validation_error():
    raw = profile(3, 8)
    raw['comparison']['example'] = None
    with pytest.raises(ValueError):
        build_coding_instructions(raw)

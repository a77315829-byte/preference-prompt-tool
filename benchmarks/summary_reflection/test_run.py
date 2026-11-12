"""Integrity and conservative decision tests; no model calls."""
import copy

import pytest

from benchmarks.summary_reflection import run
from benchmarks.summary_reflection.audit import quotes


def test_write_refuses_overwrite(tmp_path):
    target = tmp_path / 'result.json'
    run.write(target, {'first': True})
    with pytest.raises(FileExistsError):
        run.write(target, {'first': False})
    assert run.read(target) == {'first': True}


def test_seal_detects_mutated_evidence_and_empty_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(run, 'ROOT', tmp_path)
    evidence, seal = tmp_path / 'evidence.json', tmp_path / 'seal.json'
    run.write(evidence, {'source': 'original'})
    run.seal(seal, [evidence])
    run.check_seal(seal)
    evidence.write_text('{}', encoding='utf-8')
    with pytest.raises(AssertionError):
        run.check_seal(seal)
    seal.write_text('{}', encoding='utf-8')
    with pytest.raises(AssertionError, match='Empty'):
        run.check_seal(seal)


@pytest.mark.parametrize('value', [[''], 'A', ['not present']])
def test_exact_evidence_rejects_empty_or_wrong_type(value):
    with pytest.raises(AssertionError):
        quotes(value, 'A B C')


def test_absent_claim_may_have_no_source_evidence():
    quotes([], 'A B C', allow_empty=True)


@pytest.mark.parametrize('candidate_facts,second_facts,wording,issues,eligible', [
    (3, 3, True, [], True),
    (2, 2, True, [], False),  # one extra fact is below the predefined threshold
    (3, 2, True, [], False),  # both reviewers must meet the threshold
    (3, 3, False, [], False),  # coverage cannot compensate for a condition regression
    (3, 3, True, [{'summary_quote': 'A', 'reason': 'unsupported', 'source_evidence': ['A']}], False),
])
def test_selection_requires_independent_gates(tmp_path, monkeypatch, candidate_facts, second_facts, wording, issues, eligible):
    monkeypatch.setattr(run, 'ROOT', tmp_path)
    monkeypatch.setattr(run, 'RUN', tmp_path / 'experiment')
    monkeypatch.setattr(run, 'verify', lambda stage: None)
    folder = run.RUN / 'selection'
    packet = [{'output_id': oid, 'case_id': 'D01', 'source': 'A B C', 'summary': 'A B C',
               'target': {'length': 'short', 'extractiveness': 'normal'}} for oid in ('B001', 'B002')]
    run.write(folder / 'blind_packet.json', packet)
    run.write(folder / 'blind_mapping.json', {'B001': {'arm': 'current', 'case_id': 'D01'},
                                             'B002': {'arm': 'candidate', 'case_id': 'D01'}})
    for reviewer, count in [('a', candidate_facts), ('b', second_facts)]:
        rows = []
        for oid, n in [('B001', 1), ('B002', count)]:
            rows.append({'output_id': oid, 'sentence_count': 1,
                         'wording_pass': wording if oid == 'B002' else True, 'wording_reason': 'Observed words',
                         'facts': [{'id': f'F{i+1}', 'preserved': i < n,
                                    'summary_evidence': [letter] if i < n else [], 'reason': 'Evidence'}
                                   for i, letter in enumerate('ABC')],
                         'issues': copy.deepcopy(issues) if oid == 'B002' else []})
        run.write(folder / f'review_{reviewer}.json', rows)
    run.score('selection')
    assert run.read(folder / 'decision.json')['eligible'] is eligible
    run.check_seal(folder / 'review_seal.json')

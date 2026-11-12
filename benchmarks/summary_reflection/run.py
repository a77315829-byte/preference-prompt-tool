"""Offline reflective prompt experiment. No model/API execution lives here."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from benchmarks.summary_agent_pilot.evaluate import validate_facts, validate_review, length_pass
from engine.domain_loader import load_domain
from engine.generator import build_final_prompt

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
RUN = BASE / 'results' / '2026-11-10'
OLD = [ROOT / 'benchmarks' / name / 'results' / '2026-11-10'
       for name in ('summary_agent_pilot', 'summary_agent_revision')]
SEED = 20261113


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def seal(path, paths):
    write(path, {str(p.relative_to(ROOT)): sha(p) for p in paths})


def check_seal(path):
    manifest = read(path)
    assert manifest, 'Empty hash manifest'
    for name, digest in manifest.items():
        assert sha(ROOT / name) == digest, name


def arms(stage):
    return ('current', 'candidate') if stage == 'selection' else ('manual', 'current', 'candidate')


def sample():
    assert not RUN.exists(), 'Existing run must never be overwritten'
    training = [c for folder in OLD for c in read(folder / 'cases.json')]
    excluded = {c['source_sha256'] for c in training}
    dataset = ROOT / 'data/macsum/dataset/macdoc/test.json'
    pool = []
    for index, row in enumerate(read(dataset)):
        source = '\n'.join(row['source'])
        digest = hashlib.sha256(source.encode()).hexdigest()
        if (digest not in excluded and 250 <= len(source.split()) <= 800
                and len(row['source']) >= 8
                and any(not r['control_attribute'].get('topic') for r in row['references'])):
            pool.append({'record_index': index, 'source': source, 'source_units': row['source'],
                         'source_sha256': digest, 'source_words': len(source.split())})
    random.Random(SEED).shuffle(pool)
    assert len(pool) >= 24
    profiles = [c['profile'] for c in read(OLD[0] / 'cases.json')]
    selection_pairs = [('short', 'fully'), ('short', 'normal'), ('normal', 'high'),
                       ('normal', 'fully'), ('long', 'normal'), ('long', 'high')]
    selection_profiles = [next(p for p in profiles if p['length'] == l and p['extractiveness'] == e)
                          for l, e in selection_pairs]
    final_profiles = profiles * 2
    random.Random(SEED + 1).shuffle(final_profiles)
    offset = 0
    for stage, targets, prefix in [('selection', selection_profiles, 'D'), ('final', final_profiles, 'T')]:
        cases = [dict(pool[offset+i], id=f'{prefix}{i+1:02d}', profile=p) for i, p in enumerate(targets)]
        offset += len(cases)
        write(RUN / stage / 'cases.json', cases)
    write(RUN / 'split.json', {'seed': SEED, 'dataset_sha256': sha(dataset),
          'training_sources': len(training), 'training_source_sha256': sorted(excluded),
          'eligible_new_sources': len(pool), 'selection_sources': 6, 'final_sources': 18,
          'prior_artifact_hashes': {str((p / 'cases.json').relative_to(ROOT)): sha(p / 'cases.json') for p in OLD},
          'policy': 'Observed prior 18 sources are development/training only. New 6 selection + 18 final, disjoint exact hashes; not a claim of model-pretraining exclusion.'})
    seal(RUN / 'split_seal.json', [RUN / 'split.json'] + [RUN / s / 'cases.json' for s in ('selection', 'final')])
    print('18 observed training documents; 6 new selection; 18 new final documents.')


def check_split():
    check_seal(RUN / 'split_seal.json')
    split = read(RUN / 'split.json')
    for name, digest in split['prior_artifact_hashes'].items():
        assert sha(ROOT / name) == digest, name
    assert sha(ROOT / 'data/macsum/dataset/macdoc/test.json') == split['dataset_sha256']
    seen = set(split['training_source_sha256'])
    for stage, n in [('selection', 6), ('final', 18)]:
        cases = read(RUN / stage / 'cases.json')
        hashes = {c['source_sha256'] for c in cases}
        assert len(cases) == len(hashes) == n and not seen & hashes
        for c in cases:
            assert hashlib.sha256(c['source'].encode()).hexdigest() == c['source_sha256']
        seen |= hashes


def freeze(stage):
    check_split()
    folder = RUN / stage
    cases = read(folder / 'cases.json')
    validate_facts(cases, read(folder / 'facts.json'))
    candidate = read(BASE / 'candidate.json')
    assert 0 < len(candidate['supplement'].split()) <= 220
    if stage == 'final':
        verify('selection')
        check_seal(RUN / 'selection' / 'review_seal.json')
    old_prompts = {tuple(sorted(c['profile'].items())): c['prompts']['manual'] for c in read(OLD[0] / 'cases.json')}
    domain = load_domain(ROOT / 'domains/summarization_grounded_v2.yaml')
    inputs = {arm: [] for arm in arms(stage)}
    for case in cases:
        current = build_final_prompt(domain, case['profile'], language='en')
        prompts = {'manual': old_prompts[tuple(sorted(case['profile'].items()))], 'current': current,
                   'candidate': current + '\n\n' + candidate['supplement']}
        for arm in arms(stage):
            inputs[arm].append({'id': case['id'], 'prompt': prompts[arm], 'source': case['source']})
    for arm, rows in inputs.items():
        write(folder / 'inputs' / f'{arm}.json', rows)
    write(folder / 'protocol.json', {'stage': stage, 'frozen_utc': datetime.now(timezone.utc).isoformat(),
          'arms': arms(stage), 'documents': len(cases), 'external_paid_api_calls': 0,
          'reflection': 'One fresh agent proposes one generic supplement from only the 18 already observed documents. No revision after selection or final results. This is not an execution of GEPA.',
          'selection_rule': 'Candidate eligible only if EACH blind reviewer records at least 2 additional preserved facts /18 over current, no fewer joint condition passes, and zero factual-issue outputs. Otherwise retain current. Final candidate is still compared as a research arm even if ineligible; no forced winner.',
          'final_adoption_rule': 'Research evidence for adoption requires selection eligibility AND each reviewer at least 2 extra preserved facts /54 vs BOTH manual and current, no fewer joint condition passes vs either, and zero factual flags. Still not sufficient for mandatory per-request GEPA.',
          'generation': 'Fresh context per arm, same inherited model/settings, first response cached, no paid APIs. Each agent sees only its input, not anchors/evaluation/other outputs. Operational same batch size within stage.',
          'review': 'Two fresh independent blinded agents with same runtime model, source and frozen three facts; no arms/prompts/automatic scores. All issue flags and disagreements audited. Same-model agreement is not human gold truth.',
          'limits': ['Small English MACSum-news sample', 'AI-selected anchors, three per document', 'Only one stochastic sample per condition', 'No human preference/time/adoption measurement', 'Not unseen in pretraining', 'No real GEPA latency or usage measurement']})
    paths = [folder / n for n in ('cases.json', 'facts.json', 'protocol.json')]
    paths += [folder / 'inputs' / f'{a}.json' for a in arms(stage)]
    paths += [BASE / 'candidate.json', BASE / 'rubric.json', Path(__file__),
              ROOT / 'benchmarks/summary_agent_pilot/evaluate.py', ROOT / 'engine/generator.py',
              ROOT / 'engine/domain_loader.py', ROOT / 'checks/summarization.py',
              ROOT / 'domains/summarization.yaml', ROOT / 'domains/summarization_grounded.yaml',
              ROOT / 'domains/summarization_grounded_v2.yaml', ROOT / 'checks/summarization_grounded.py',
              ROOT / 'checks/summarization_grounded_v2.py']
    if stage == 'final':
        paths += [RUN / 'selection' / n for n in ('decision.json', 'review_seal.json')]
    seal(folder / 'frozen.json', paths)
    print(f'Frozen {stage}; prompts, anchors, evaluation and code.')


def verify(stage):
    check_split()
    folder = RUN / stage
    check_seal(folder / 'frozen.json')
    if (folder / 'generation_seal.json').exists():
        check_seal(folder / 'generation_seal.json')
    if (folder / 'review_seal.json').exists():
        required = {str((folder / n).relative_to(ROOT)) for n in
                    ('review_a.json', 'review_b.json', 'scores.json', 'decision.json')}
        assert required <= set(read(folder / 'review_seal.json'))
        check_seal(folder / 'review_seal.json')


def blind(stage):
    verify(stage)
    from checks import summarization_grounded_v2 as checks
    from checks.summarization import _words, _bigrams
    folder = RUN / stage
    cases = {r['id']: r for r in read(folder / 'cases.json')}
    facts = {r['id']: r['facts'] for r in read(folder / 'facts.json')}
    entries = []
    for arm in arms(stage):
        rows = read(folder / 'outputs' / f'{arm}.json')
        assert len(rows) == len(cases) and {r['id'] for r in rows} == set(cases)
        for r in rows:
            assert isinstance(r['summary'], str) and r['summary'].strip()
            entries.append((arm, cases[r['id']], r['summary']))
    random.Random(SEED + (2 if stage == 'selection' else 3)).shuffle(entries)
    packet, mapping, automatic = [], {}, []
    domain = load_domain(ROOT / 'domains/summarization_grounded_v2.yaml')
    for i, (arm, c, summary) in enumerate(entries, 1):
        oid = f'B{i:03d}'
        packet.append({'output_id': oid, 'case_id': c['id'], 'source': c['source'], 'target': c['profile'],
                       'key_facts': facts[c['id']], 'summary': summary})
        mapping[oid] = {'arm': arm, 'case_id': c['id']}
        result = {'output_id': oid, **mapping[oid], 'words': len(summary.split()),
                  'word_ratio': len(summary.split()) / c['source_words']}
        for axis in ('length', 'extractiveness'):
            value = c['profile'][axis]
            spec = domain.axis(axis).check_for(value)
            score, feedback = getattr(checks, spec.fn)(summary, c['source'], value, spec.target)
            result[axis] = {'score': score, 'feedback': feedback}
        ob, sb = _bigrams(_words(summary)), _bigrams(_words(c['source']))
        result['bigram_overlap_diagnostic'] = len(ob & sb) / len(ob) if ob else 0
        automatic.append(result)
    write(folder / 'blind_packet.json', packet)
    write(folder / 'blind_mapping.json', mapping)
    write(folder / 'automatic.json', automatic)
    seal(folder / 'generation_seal.json', [folder / 'outputs' / f'{a}.json' for a in arms(stage)] +
         [folder / n for n in ('blind_packet.json', 'blind_mapping.json', 'automatic.json')])
    print(f'Sealed {len(packet)} anonymous {stage} outputs.')


def score(stage):
    verify(stage)
    folder = RUN / stage
    packet = read(folder / 'blind_packet.json')
    targets = {r['output_id']: r for r in packet}
    mapping = read(folder / 'blind_mapping.json')
    reviews = {k: read(folder / f'review_{k}.json') for k in ('a', 'b')}
    report = {'by_reviewer': {}, 'paired_document_coverage': {}, 'disagreements': [], 'all_factual_flag_ids': []}
    for key, rows in reviews.items():
        validate_review(rows, packet)
        counts, per_doc = {}, {}
        for arm in arms(stage):
            rr = [r for r in rows if mapping[r['output_id']]['arm'] == arm]
            lp = [length_pass(r['sentence_count'], targets[r['output_id']]['target']['length']) for r in rr]
            counts[arm] = {'outputs': len(rr), 'length_pass': sum(lp), 'wording_pass': sum(r['wording_pass'] for r in rr),
                          'joint_pass': sum(l and r['wording_pass'] for l, r in zip(lp, rr)),
                          'facts_preserved': sum(f['preserved'] for r in rr for f in r['facts']),
                          'facts_total': len(rr)*3, 'factual_issue_outputs': sum(bool(r['issues']) for r in rr)}
            per_doc[arm] = {mapping[r['output_id']]['case_id']: sum(f['preserved'] for f in r['facts']) for r in rr}
        report['by_reviewer'][key] = counts
        report['paired_document_coverage'][key] = {base: {
            'wins': sum(per_doc['candidate'][c] > v for c, v in per_doc[base].items()),
            'ties': sum(per_doc['candidate'][c] == v for c, v in per_doc[base].items()),
            'losses': sum(per_doc['candidate'][c] < v for c, v in per_doc[base].items())}
            for base in arms(stage) if base != 'candidate'}
    a, b = [{r['output_id']: r for r in reviews[k]} for k in ('a', 'b')]
    for oid in targets:
        fact_marks = [{f['id']: f['preserved'] for f in row[oid]['facts']} for row in (a, b)]
        if fact_marks[0] != fact_marks[1] or a[oid]['wording_pass'] != b[oid]['wording_pass'] or a[oid]['sentence_count'] != b[oid]['sentence_count']:
            report['disagreements'].append(oid)
        if a[oid]['issues'] or b[oid]['issues']:
            report['all_factual_flag_ids'].append(oid)
    write(folder / 'scores.json', report)
    eligible = all(c['candidate']['factual_issue_outputs'] == 0 and all(
        c['candidate']['facts_preserved'] >= c[base]['facts_preserved'] + 2 and
        c['candidate']['joint_pass'] >= c[base]['joint_pass']
        for base in arms(stage) if base != 'candidate') for c in report['by_reviewer'].values())
    if stage == 'final':
        verify('selection')
        check_seal(RUN / 'selection' / 'review_seal.json')
        eligible = eligible and read(RUN / 'selection' / 'decision.json')['eligible']
    write(folder / 'decision.json', {'eligible': eligible, 'default': 'candidate' if eligible else 'current',
          'basis': 'Pre-frozen conservative rule applied to both original reviewers; no retrospective regrading to select a winner.',
          'utc': datetime.now(timezone.utc).isoformat(), 'actual_gepa_executed': False})
    seal(folder / 'review_seal.json', [folder / f'review_{k}.json' for k in ('a','b')] +
         [folder / 'scores.json', folder / 'decision.json'])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print('Eligible:', eligible)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['sample','freeze','verify','blind','score'])
    parser.add_argument('--stage', choices=['selection','final'], default='selection')
    args = parser.parse_args()
    sample() if args.command == 'sample' else globals()[args.command](args.stage)

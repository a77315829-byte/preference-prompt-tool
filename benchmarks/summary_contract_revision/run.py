"""No-model-call three-arm comparison on fixed unused, conflict-focused sources."""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from engine.domain_loader import load_domain
from engine.generator import build_final_prompt
from summary_contracts import prepare_summary_contract, task_data_block
from benchmarks.summary_agent_pilot.evaluate import validate_facts, length_pass
from benchmarks.summary_reflection.audit import strict_review, quotes
from benchmarks.summary_gepa_offline.diagnostics import lcs_f1
from checks import summarization_grounded_v3 as checks

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
RUN = BASE / 'results/2026-11-10'
ARMS = ('manual', 'current', 'revised')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2); stream.write('\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def seal(path, paths):
    write(path, {str(p.relative_to(ROOT)): sha(p) for p in paths})


def check_seal(path):
    manifest = read(path)
    assert manifest
    for name, digest in manifest.items():
        assert sha(ROOT/name) == digest, name


def manual_prompt(profile):
    length = {'short': 'Use one or two sentences.', 'normal': 'Use three or four sentences.',
              'long': 'Use at least five sentences, with useful detail.'}[profile['length']]
    wording = {
        'normal': 'Mostly rewrite in your own words while preserving meaning. Names, quantities and necessary source expressions may be retained.',
        'high': 'Substantially reuse the original words and phrases. Reusing whole sentences is allowed; there is no upper limit on reuse.',
        'fully': 'Use only complete source sentences without changing words or punctuation. Whitespace normalization and omission of a leading (CNN) or (The Hollywood Reporter) publisher tag are allowed; no other edits, fragments or invented connections.'
    }[profile['extractiveness']]
    focus = 'Focus the summary on '+json.dumps(profile['topic'],ensure_ascii=False)+'. ' if profile.get('topic') else ''
    return ('Write an accurate English summary of the supplied source. '+length+' '+wording+' '+focus+
            'Retain the central event, main outcome or purpose, important quantities and essential qualifications. '
            'Preserve who made each claim and distinguish allegations, plans and uncertainty from confirmed facts. '
            'Use only source-supported information; do not invent facts or causal links. '
            'The task data identifies user-selected source passages and whether their information must all be kept '
            'or a feasible subset is permitted. These resolved conditions reflect the user\'s decision; do not silently change them. '
            'Preserve the requested information before peripheral background or repetition, and ensure quotations and pronouns remain attributable. '
            'Check omissions and unsupported certainty against the source before submitting. If mandatory conditions cannot jointly be met, '
            'request clarification instead of pretending success. Otherwise output only the summary without a title, explanation or checklist.')


def validate_extra(rows, packet):
    # Legacy evidence validator assumes every output is a summary with >=1 sentence.
    # Preserve an actual zero count for a non-sentence refusal; adapt only its
    # validation copy, never the saved review or reported score.
    for row in rows:
        assert type(row['sentence_count']) is int and row['sentence_count'] >= 0
        assert row['response_kind'] in ('summary', 'clarification', 'other')
    compatible = [dict(r, sentence_count=1) if r['sentence_count']==0 and r['response_kind']!='summary' else r for r in rows]
    strict_review(compatible, packet)
    by = {r['output_id']:r for r in packet}
    for row in rows:
        assert row['response_kind'] in ('summary', 'clarification', 'other')
        assert len(row['priorities']) == 3 and {p['id'] for p in row['priorities']} == {'P1','P2','P3'}
        for p in row['priorities']:
            assert type(p['preserved']) is bool and isinstance(p['reason'], str) and p['reason'].strip()
            quotes(p['summary_evidence'], by[row['output_id']]['summary'], allow_empty=not p['preserved'])


def freeze():
    cases=read(RUN/'evaluation_sources.json');annotations=read(RUN/'evaluation_annotations.json');sampling=read(RUN/'evaluation_sampling.json')
    validate_facts(cases,annotations)
    ann={r['id']:r for r in annotations};effective=[];inputs={a:[] for a in ARMS};references=[]
    old=load_domain(ROOT/'domains/summarization_grounded_v2.yaml')
    dataset=read(ROOT/sampling['dataset']['path'])
    assert sha(ROOT/sampling['dataset']['path'])==sampling['dataset']['file_sha256']
    for c in cases:
        assert len(ann[c['id']]['required_sentences'])==3
        body={'domainKey':'summarization','profile':c['original_profile'],'sourceText':c['source'],
              'requiredSentences':ann[c['id']]['required_sentences'],'resolution':c['requested_resolution']}
        resolved=prepare_summary_contract(body)
        assert resolved['status']=='ready'
        if c['requested_resolution']:
            assert prepare_summary_contract(dict(body,resolution=None))['status']=='needs_resolution'
        profile=resolved['effective_profile']
        effective.append({'id':c['id'],'profile':profile,'original_profile':c['original_profile'],
                          'resolution':resolved['resolution'],'required_sentences':resolved['required_sentences'],
                          'conflict':resolved['conflict'],'notices':resolved['notices']})
        common=task_data_block(c['source'],resolved['required_sentences'],resolved['resolution'],'en')
        prompts={'manual':manual_prompt(profile),'current':build_final_prompt(old,profile,language='en'),
                 'revised':resolved['prompts']['en']}
        for arm in ARMS:
            request=prompts[arm]+'\n\n'+common
            if arm=='revised':assert request==resolved['task_requests']['en']
            inputs[arm].append({'id':c['id'],'request':request})
        raw=dataset[c['record_index']]
        assert '\n'.join(raw['source'])==c['source']
        refs=[r for r in raw['references'] if not r['control_attribute'].get('topic')]
        matched=[r for r in refs if r['control_attribute'].get('length')==profile['length']]
        chosen=matched or refs
        references.append({'id':c['id'],'length_matched':bool(matched),'references':[r['summary'] for r in chosen]})
    write(RUN/'effective_conditions.json',effective)
    write(RUN/'references.json',references)
    for arm,rows in inputs.items():write(RUN/f'inputs/{arm}.json',rows)
    protocol={'frozen_utc':datetime.now(timezone.utc).isoformat(),'arms':ARMS,'sources':len(cases),'first_outputs':len(cases)*3,
        'design':'Conflict-focused, previously unused MACSum original val sources (not official test results). Exclude all63 prior observed sources and quarantine one initial selection with substantial prior-source overlap, before outputs. Preserve the initial sample and replace it deterministically, requiring word5gram Jaccard<.1. Six short/fully conflicts, two per explicit resolution; three non-conflict controls. Source/annotation worker did not see prompts or outputs.',
        'fairness':'All arms receive IDENTICAL source, user-selected priority sentences, coverage policy and effective conditions. Current uses unchanged v2 prompt export with those effective conditions. Revised is EXACT product contract task request. Manual is a deliberate strong source-faithful baseline written before generated outputs. Whole-prompt comparison, not a causal test of individual clauses.',
        'conflict_evaluation':'Conflict detection, unconfirmed-output blocking, consent and effective conditions are tested deterministically. All generators receive already-resolved conditions; improvement from making a decision is NOT credited to the revised model arm.',
        'content_scope':'Three private atomic core anchors per source. Three selected complete source sentences are SHARED model input and separately reviewed for their core information. Their overlap with anchors means this tests explicit-priority following, not unprompted core discovery or human preference inference.',
        'metrics':'Report grammatical length, wording, joint conditions, core anchors, selected-passage information, whole-summary factual flags and clarification responses separately. Keep_limits permits omission; absent points remain visible but do not automatically imply a violated obligation or hallucination. Do not sum metrics into a ranking score.',
        'review':'Two fresh blinded reviewers using source,target,shared priorities,private facts. No arm labels/prompts/automatic metrics/references/other reviews. Exact evidence required. Preserve original counts and audit disagreements/all factual flags.',
        'diagnostic':'Preselected topic-free, resolved-length-matched human references when available, otherwise all topic-free; maximum word-token LCS F1 per case. References never given to generators/reviewers. Not official ROUGE or factuality.',
        'generation':'Fresh independent agent per arm, inherited runtime, first response cached, no score-driven retries, no model API or dependencies. Codex usage consumed; exact model/decoding/token usage not exposed.',
        'adoption':'Ship deterministic checker and explicit conflict control, keep original base instructions. This pilot cannot establish statistical equivalence, general quality superiority, human convenience or required GEPA. New contract instructions apply only via explicit checked task path.',
        'stop':'One fixed three-arm comparison; no retuning/reselection/regeneration on these outputs. These9 sources become observed for all future runs.',
        'paid_model_api_calls':0,'gepa_run':False}
    write(RUN/'protocol.json',protocol)
    paths=[p for p in RUN.rglob('*.json') if 'outputs' not in p.parts]+[Path(__file__),BASE/'rubric.json',ROOT/'summary_contracts.py']
    paths += [ROOT/p for p in ['domains/summary_contract.yaml','domains/summarization.yaml','domains/summarization_grounded.yaml',
        'domains/summarization_grounded_v2.yaml','domains/summarization_grounded_v3.yaml','checks/summarization_grounded.py',
        'checks/summarization_grounded_v2.py','checks/summarization_grounded_v3.py','engine/generator.py','engine/domain_loader.py',
        'benchmarks/summary_reflection/audit.py','benchmarks/summary_agent_pilot/evaluate.py','benchmarks/summary_gepa_offline/diagnostics.py']]
    seal(RUN/'frozen.json',paths)
    (RUN/'outputs').mkdir(exist_ok=True)
    print('Frozen9sources,27requests,3policies. No model calls.')


def verify():
    check_seal(RUN/'frozen.json')
    cases=read(RUN/'evaluation_sources.json');sampling=read(RUN/'evaluation_sampling.json')
    hashes={c['source_sha256'] for c in cases}
    assert len(hashes)==len(cases)==9 and not hashes.intersection(sampling['exclusion_source_sha256'])
    assert all(hashlib.sha256(c['source'].encode()).hexdigest()==c['source_sha256'] for c in cases)
    for row in sampling['prior_case_files']:assert sha(ROOT/row['path'])==row['file_sha256']
    for name in ['generation_seal.json','review_seal.json']:
        if (RUN/name).exists():check_seal(RUN/name)


def blind():
    verify();cases={c['id']:c for c in read(RUN/'evaluation_sources.json')};ann={r['id']:r for r in read(RUN/'evaluation_annotations.json')}
    profiles={r['id']:r for r in read(RUN/'effective_conditions.json')};entries=[]
    for arm in ARMS:
        rows=read(RUN/f'outputs/{arm}.json')
        assert len(rows)==len(cases) and {r['id'] for r in rows}==set(cases)
        for r in rows:
            assert isinstance(r['summary'],str) and r['summary'].strip()
            entries.append((arm,r['id'],r['summary']))
    random.Random(20261135).shuffle(entries);packet=[];mapping={}
    for i,(arm,cid,summary) in enumerate(entries,1):
        oid=f'B{i:03d}';c=cases[cid];p=profiles[cid]
        packet.append({'output_id':oid,'case_id':cid,'source':c['source'],'target':p['profile'],
            'coverage_policy':'prioritize_with_omission' if p['resolution']=='keep_limits' else 'all_required',
            'required_passages':[{'id':f'P{j}','text':s} for j,s in enumerate(p['required_sentences'],1)],
            'key_facts':ann[cid]['facts'],'summary':summary})
        mapping[oid]={'arm':arm,'case_id':cid}
    write(RUN/'blind_packet.json',packet);write(RUN/'blind_mapping.json',mapping)
    seal(RUN/'generation_seal.json',[RUN/f'outputs/{a}.json' for a in ARMS]+[RUN/'blind_packet.json',RUN/'blind_mapping.json'])
    print('Sealed27anonymousoutputs.')


def score():
    verify();packet=read(RUN/'blind_packet.json');by={r['output_id']:r for r in packet};mapping=read(RUN/'blind_mapping.json')
    reviews={k:read(RUN/f'review_{k}.json') for k in ('a','b')};report={'by_reviewer':{},'disagreements':[],'factual_flags':[]}
    for key,rows in reviews.items():
        validate_extra(rows,packet);counts={}
        for arm in ARMS:
            rr=[r for r in rows if mapping[r['output_id']]['arm']==arm]
            lp=[length_pass(r['sentence_count'],by[r['output_id']]['target']['length']) for r in rr]
            counts[arm]={'outputs':len(rr),'length_pass':sum(lp),'wording_pass':sum(r['wording_pass'] for r in rr),
                'joint_pass':sum(l and r['wording_pass'] and r['response_kind']=='summary' for l,r in zip(lp,rr)),
                'core_preserved':sum(f['preserved'] for r in rr for f in r['facts']),'core_total':len(rr)*3,
                'priority_passages_preserved':sum(p['preserved'] for r in rr for p in r['priorities']),
                'priority_passages_total':len(rr)*3,'factual_issue_outputs':sum(bool(r['issues']) for r in rr),
                'non_summary_responses':sum(r['response_kind']!='summary' for r in rr)}
        report['by_reviewer'][key]=counts
    aa,bb=[{r['output_id']:r for r in reviews[k]} for k in ('a','b')]
    def signature(r):
        return (r['sentence_count'],r['wording_pass'],r['response_kind'],bool(r['issues']),
                sorted((f['id'],f['preserved']) for f in r['facts']),sorted((p['id'],p['preserved']) for p in r['priorities']))
    for oid in by:
        if signature(aa[oid])!=signature(bb[oid]):report['disagreements'].append(oid)
        if aa[oid]['issues'] or bb[oid]['issues']:report['factual_flags'].append(oid)
    write(RUN/'scores.json',report)
    seal(RUN/'review_seal.json',[RUN/f'review_{k}.json' for k in ('a','b')]+[RUN/'scores.json'])
    print(json.dumps(report,ensure_ascii=False,indent=2))


def diagnostics():
    verify();packet=read(RUN/'blind_packet.json');mapping=read(RUN/'blind_mapping.json')
    refs={r['id']:r for r in read(RUN/'references.json')};domain=load_domain(ROOT/'domains/summarization_grounded_v3.yaml');rows=[]
    for r in packet:
        entry={'output_id':r['output_id'],**mapping[r['output_id']],'words':len(r['summary'].split()),
               'automatic_sentences':len(checks.split_sentences(r['summary']))}
        for axis in ('length','extractiveness'):
            value=r['target'][axis];spec=domain.axis(axis).check_for(value)
            score,feedback=getattr(checks,spec.fn)(r['summary'],r['source'],value,spec.target)
            entry[axis]={'score':score,'feedback':feedback}
        entry['max_reference_word_lcs_f1']=max(lcs_f1(r['summary'],s) for s in refs[r['case_id']]['references'])
        rows.append(entry)
    means={arm:{'reference_word_lcs_f1':sum(r['max_reference_word_lcs_f1'] for r in rows if r['arm']==arm)/9,
                'words':sum(r['words'] for r in rows if r['arm']==arm)/9} for arm in ARMS}
    write(RUN/'diagnostics.json',{'means':means,'rows':rows,'notice':'Automatic heuristic/reference overlap only, not semantic quality or a selection metric.'})
    print(means)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['freeze','verify','blind','score','diagnostics'])
    globals()[parser.parse_args().command]()

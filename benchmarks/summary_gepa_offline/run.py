"""Dataset freezing and held-out comparison for the actual GEPA offline bridge."""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from engine.domain_loader import load_domain
from engine.generator import build_final_prompt
from benchmarks.summary_agent_pilot.evaluate import validate_facts, length_pass
from benchmarks.summary_reflection.audit import strict_review

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
RUN = BASE / 'results' / '2026-11-10'
SEED = 20261114


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
    assert manifest
    for name, digest in manifest.items():
        assert sha(ROOT / name) == digest, name


def sample():
    assert not RUN.exists(), 'Do not overwrite an experiment'
    observed = [ROOT / 'benchmarks' / name / 'results/2026-11-10/cases.json'
                for name in ['summary_agent_pilot', 'summary_agent_revision']]
    observed += [ROOT / f'benchmarks/summary_reflection/results/2026-11-10/{s}/cases.json'
                 for s in ['selection', 'final']]
    excluded = {c['source_sha256'] for p in observed for c in read(p)}
    all_profiles = [c['profile'] for c in read(observed[0])]
    six = [('short','normal'),('short','fully'),('normal','high'),('normal','fully'),('long','normal'),('long','high')]
    short_profiles = [next(p for p in all_profiles if (p['length'],p['extractiveness']) == pair) for pair in six]
    domain = load_domain(ROOT / 'domains/summarization_grounded_v2.yaml')
    source_files, inventory = {}, {}
    seen = set(excluded)
    for k, (stage, dataset_split, n, prefix) in enumerate([('train','train',6,'G'),('validation','val',6,'V'),('final','test',9,'H')]):
        path = ROOT / f'data/macsum/dataset/macdoc/{dataset_split}.json'
        source_files[str(path.relative_to(ROOT))] = sha(path)
        pool, pool_hashes = [], set()
        for index, record in enumerate(read(path)):
            source = '\n'.join(record['source'])
            digest = hashlib.sha256(source.encode()).hexdigest()
            if (digest not in seen and digest not in pool_hashes and 250 <= len(source.split()) <= 800
                    and len(record['source']) >= 8
                    and any(not r['control_attribute'].get('topic') for r in record['references'])):
                pool.append({'record_index':index,'dataset_split':dataset_split,'source':source,
                             'source_sha256':digest,'source_words':len(source.split())})
                pool_hashes.add(digest)
        random.Random(SEED+k).shuffle(pool)
        assert len(pool) >= n
        profiles = list(all_profiles if stage == 'final' else short_profiles)
        random.Random(SEED+10+k).shuffle(profiles)
        rows = [dict(c,id=f'{prefix}{i+1:02d}',profile=profiles[i],
                     base_prompt=build_final_prompt(domain,profiles[i],language='en')) for i,c in enumerate(pool[:n])]
        write(RUN / stage / 'cases.json',rows)
        seen.update(c['source_sha256'] for c in rows)
        inventory[stage] = {'eligible_pool':len(pool),'sampled':n,'dataset_split':dataset_split}
    write(RUN/'split.json',{'seed':SEED,'previously_observed_sources':len(excluded),
          'excluded_source_sha256':sorted(excluded),'inventory':inventory,'dataset_hashes':source_files,
          'prior_cases_hashes':{str(p.relative_to(ROOT)):sha(p) for p in observed},
          'scope':'All 21 sources distinct from the 42 sources in previous three summary studies; pretraining novelty not asserted.'})
    seal(RUN/'split_seal.json',[RUN/'split.json']+[RUN/s/'cases.json' for s in ['train','validation','final']])
    print(inventory)


def freeze():
    check_seal(RUN/'split_seal.json')
    seen = set(read(RUN/'split.json')['excluded_source_sha256'])
    for stage, n in [('train',6),('validation',6),('final',9)]:
        rows=read(RUN/stage/'cases.json')
        validate_facts(rows,read(RUN/stage/'facts.json'))
        hashes={r['source_sha256'] for r in rows}
        assert len(rows)==len(hashes)==n and not hashes & seen
        seen.update(hashes)
    protocol = {
      'frozen_utc':datetime.now(timezone.utc).isoformat(), 'actual_gepa_version':'0.1.4',
      'implementation':'Installed gepa.optimize drives candidate selection, reflection rendering/extraction, minibatch acceptance and full validation. File queue replaces ONLY model response transport; Codex agents supply fresh responses. No external model API.',
      'scope':'Isolated research adapter, not the production service.optimize configuration. Current prompt/conditions fixed; only appended generic supplement evolves. No product defaults changed automatically.',
      'splits':{'train':6,'validation':6,'final':9},
      'budget':{'reflection_proposals':2,'max_metric_calls':30,'max_supplement_words':220},
      'search':'Pareto parent selection; minibatch3; equal-or-improved minibatch admission; full validation; no merge; seed20261114. GEPA shared evaluation cache disabled to avoid list train/val ID collisions; adapter caches by source/profile/full prompt. First responses cached; no score-driven retries. Invalid supplements score -1 below every valid score and are excluded from final planning.',
      'training_metric':'Coverage of 3 frozen core facts, gated to zero on automatic/reviewed length/wording failure or reviewer factual flags. Single fresh blind reviewer per generated optimization batch; feedback includes exact evidence. Same-model judge limitations apply.',
      'final_primary':'Two independent fresh blinded reviewers: condition compliance, 3 frozen fact coverage, unsupported/contradicted claims separately. No final source/results used in GEPA or candidate choice.',
      'independent_diagnostic':'Reference word-token LCS F1 against topic-free length-matched human references, and output word count. Reference selection fixed before outputs and never supplied to GEPA/generators/reviewers. Overlap is not semantic/factual accuracy.',
      'final_selection':'Use GEPA best validation candidate, prefer seed if tied with it. If selected seed and a nonseed validation candidate exists, preselect highest-validation nonseed (earliest on ties) as clearly labelled exploratory arm. It never substitutes for GEPA selected output. If no nonseed admitted, compare selected seed honestly without claiming refinement.',
      'duplicate_prompt_policy':'Identical prompts share the first summary cache by document; report deterministic reuse, never independent samples. Distinct final prompts generated by separate fresh agents. Do not expose facts or prior outputs to generators.',
      'reporting':'Report all original reviewer counts, disagreements, all factual flags, content before/after, GEPA search logs and cache counts. Do not choose or retune on final scores. No mandatory-GEPA decision from one small study.',
      'limits':['No human labels/preferences/usability/time','Only English news','Single generation per distinct prompt/source','Same underlying-model bias','GEPA queue waits include manual orchestration, not product latency','Actual Codex token/billing meter not exposed']}
    write(RUN/'protocol.json',protocol)
    paths=[RUN/'split.json',RUN/'protocol.json',BASE/'run.py',BASE/'driver.py',BASE/'rubric.json',
           BASE/'diagnostics.py',RUN/'final/references.json',RUN/'annotation_limits.json',RUN/'anchor_audit.json']
    paths += [RUN/s/name for s in ['train','validation','final'] for name in ['cases.json','facts.json']]
    paths += [ROOT/p for p in ['engine/generator.py','engine/domain_loader.py','domains/summarization.yaml',
        'domains/summarization_grounded.yaml','domains/summarization_grounded_v2.yaml','checks/summarization.py',
        'checks/summarization_grounded.py','checks/summarization_grounded_v2.py',
        'benchmarks/summary_reflection/audit.py','benchmarks/summary_agent_pilot/evaluate.py']]
    paths += [ROOT/'.venv/Lib/site-packages/gepa'/p for p in ['api.py','core/engine.py','core/adapter.py',
        'core/data_loader.py','core/result.py','core/state.py','strategies/instruction_proposal.py',
        'proposer/reflective_mutation/reflective_mutation.py','utils/stop_condition.py']]
    seal(RUN/'frozen.json',paths)
    print('All splits/prompts/facts/metrics/code frozen before GEPA starts.')


def verify():
    check_seal(RUN/'split_seal.json')
    check_seal(RUN/'frozen.json')
    for name in ['final_input_seal.json','generation_seal.json','review_seal.json']:
        if (RUN/name).exists():check_seal(RUN/name)


def prepare_final():
    verify()
    result=read(RUN/'gepa_result.json')
    candidates=result['candidates']; scores=result['val_scores']
    invalid=[r['candidate'] for r in result.get('invalid_candidates',[])]
    valid=[i for i,c in enumerate(candidates) if c not in invalid and set(c)=={'supplement'}
           and isinstance(c['supplement'],str) and len(c['supplement'].split())<=220]
    assert 0 in valid and candidates[0]['supplement']=='', 'Valid unmodified seed required'
    best=max(valid,key=lambda i:scores[i])
    # Conservative tie: keep the fixed seed when it shares the highest validation mean.
    if scores[0]==scores[best]:best=0
    selected=candidates[best]['supplement']
    texts={'current':'','gepa':selected}
    exploratory=None
    nonseed=[i for i in valid if i!=0 and candidates[i]['supplement']]
    if best==0 and nonseed:
        exploratory=max(nonseed,key=lambda i:scores[i])
        texts['exploratory']=candidates[exploratory]['supplement']
    unique, aliases={},{}
    for arm,text in texts.items():
        same=next((name for name,value in unique.items() if value==text),None)
        if same is not None:aliases[arm]=same
        else:unique[arm]=text
    plan={'selected_index':best,'gepa_result_best_index':result['best_index'],'supplements':texts,
          'unique_generation_arms':list(unique),'aliases':aliases,'exploratory_index':exploratory,
          'selected_before_final_outputs':True,'not_adoption':'Selected here for evaluation only; no automatic product replacement.'}
    write(RUN/'final_plan.json',plan)
    for arm,supplement in unique.items():
        rows=[{'id':c['id'],'source':c['source'],'prompt':c['base_prompt']+('\n\n'+supplement if supplement else '')}
              for c in read(RUN/'final/cases.json')]
        write(RUN/'final/inputs'/f'{arm}.json',rows)
    seal(RUN/'final_input_seal.json',[RUN/'final_plan.json',RUN/'gepa_result.json']+
         [RUN/'final/inputs'/f'{a}.json' for a in unique])
    print(plan)


def blind():
    verify()
    plan=read(RUN/'final_plan.json'); cases={c['id']:c for c in read(RUN/'final/cases.json')}
    facts={r['id']:r['facts'] for r in read(RUN/'final/facts.json')}
    entries=[]
    for arm in plan['unique_generation_arms']:
        rows=read(RUN/'final/outputs'/f'{arm}.json')
        assert len(rows)==len(cases) and {r['id'] for r in rows}==set(cases)
        for r in rows:
            assert isinstance(r['summary'],str) and r['summary'].strip()
            entries.append((arm,cases[r['id']],r['summary']))
    random.Random(SEED+20).shuffle(entries)
    packet,mapping=[],{}
    for i,(arm,c,summary) in enumerate(entries,1):
        oid=f'E{i:03d}'
        packet.append({'output_id':oid,'case_id':c['id'],'source':c['source'],'target':c['profile'],
                       'key_facts':facts[c['id']],'summary':summary})
        mapping[oid]={'arm':arm,'case_id':c['id']}
    write(RUN/'final/blind_packet.json',packet);write(RUN/'final/blind_mapping.json',mapping)
    seal(RUN/'generation_seal.json',[RUN/'final/blind_packet.json',RUN/'final/blind_mapping.json']+
         [RUN/'final/outputs'/f'{a}.json' for a in plan['unique_generation_arms']])
    print('Sealed',len(packet),'distinct-prompt final summaries; aliases',plan['aliases'])


def score():
    verify()
    plan=read(RUN/'final_plan.json');packet=read(RUN/'final/blind_packet.json')
    by={r['output_id']:r for r in packet};mapping=read(RUN/'final/blind_mapping.json')
    reviews={k:read(RUN/f'final/review_{k}.json') for k in ['a','b']}
    report={'by_reviewer':{},'aliases':plan['aliases'],'disagreements':[],'factual_flags':[]}
    for key,rows in reviews.items():
        strict_review(rows,packet);counts={}
        for arm in plan['unique_generation_arms']:
            rr=[r for r in rows if mapping[r['output_id']]['arm']==arm]
            lp=[length_pass(r['sentence_count'],by[r['output_id']]['target']['length']) for r in rr]
            counts[arm]={'outputs':len(rr),'length_pass':sum(lp),'wording_pass':sum(r['wording_pass'] for r in rr),
                         'joint_pass':sum(l and r['wording_pass'] for l,r in zip(lp,rr)),
                         'facts_preserved':sum(f['preserved'] for r in rr for f in r['facts']),
                         'facts_total':len(rr)*3,'factual_issue_outputs':sum(bool(r['issues']) for r in rr)}
        for alias,original in plan['aliases'].items():counts[alias]=dict(counts[original],copied_from=original)
        report['by_reviewer'][key]=counts
    aa,bb=[{r['output_id']:r for r in reviews[k]} for k in ['a','b']]
    for oid in by:
        signatures=[(r[oid]['sentence_count'],r[oid]['wording_pass'],bool(r[oid]['issues']),
                     sorted((f['id'],f['preserved']) for f in r[oid]['facts'])) for r in [aa,bb]]
        if signatures[0]!=signatures[1]:report['disagreements'].append(oid)
        if aa[oid]['issues'] or bb[oid]['issues']:report['factual_flags'].append(oid)
    write(RUN/'final/scores.json',report)
    seal(RUN/'review_seal.json',[RUN/f'final/review_{k}.json' for k in ['a','b']]+[RUN/'final/scores.json'])
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['sample','freeze','verify','prepare_final','blind','score'])
    globals()[parser.parse_args().command]()

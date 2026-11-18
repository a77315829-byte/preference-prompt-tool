"""Aggregate fixed reviews and separate automated checks; no composite ranking."""
from datetime import datetime, timezone
from .prepare_sources import ROOT, BASE, sha, write
from .run import read, verify

def aggregate(summaries, styles):
    assert len(summaries)==12 and len(styles)==16
    summary_cases={r['id']:r for r in read(BASE/'summary_cases.json')}
    outputs={(r['arm'],r['id']):r['answer'] for r in read(BASE/'all_outputs.json')}
    for row in summaries:
        text=outputs[(row['arm'],row['id'])]
        assert len(row['facts'])==len(row['priorities'])==3
        assert {r['id'] for r in row['facts']}=={'F1','F2','F3'}
        assert {r['id'] for r in row['priorities']}=={'P1','P2','P3'}
        assert type(row['sentence_count']) is int and row['sentence_count']>=0
        assert type(row['length_pass']) is bool and type(row['wording_pass']) is bool
        for fact in row['facts']+row['priorities']:
            assert type(fact['preserved']) is bool and fact['reason']
            assert fact['evidence'] or not fact['preserved']
            for quote in fact['evidence']:assert quote in text,(row['id'],quote)
        for issue in row['issues']:
            assert issue['reason'] and issue['evidence'] in text
    for row in styles:
        text=outputs[(row['arm'],row['id'])]
        assert set(row['dimensions'])=={'code_structure','style_management','type_detail'}
        for value in row['dimensions'].values():
            assert type(value['match']) is bool and value['reason']
            for quote in value['evidence']:assert quote in text,(row['id'],quote)
    results={}
    for arm in ('manual','product'):
        ss=[r for r in summaries if r['arm']==arm];rr=[r for r in styles if r['arm']==arm]
        assert len(ss)==6 and len(rr)==8
        evaluations={r['id']:read(BASE/f"evaluation/{arm}/{r['id']}.json") for r in rr}
        passed=lambda result, key: bool((result.get(key) or {}).get('passed'))
        results[arm]={'summary':{'outputs':6,'length_pass':sum(r['length_pass'] for r in ss),
            'wording_pass':sum(r['wording_pass'] for r in ss),'joint_conditions':sum(r['length_pass'] and r['wording_pass'] for r in ss),
            'core_facts_preserved':sum(f['preserved'] for r in ss for f in r['facts']),'core_facts_total':18,
            'selected_passages_preserved':sum(f['preserved'] for r in ss for f in r['priorities']),'selected_passages_total':18,
            'all_required_policy_cases':sum(summary_cases[r['id']]['coverage_policy']=='all_required' for r in ss),
            'all_required_policy_met':sum(all(p['preserved'] for p in r['priorities']) for r in ss if summary_cases[r['id']]['coverage_policy']=='all_required'),
            'factual_issue_outputs':sum(bool(r['issues']) for r in ss),'non_summary_responses':sum(r['response_kind']!='summary' for r in ss)},
          'react':{'outputs':8,'type_pass':sum(passed(e,'types') for e in evaluations.values()),
            'all_behavior_pass':sum(passed(e,'runtime') for e in evaluations.values()),
            'behavior_checks_pass':sum(c['passed'] for e in evaluations.values() for c in (e.get('runtime') or {}).get('checks',[])),
            'behavior_checks_total':40,'style_axis_matches':{axis:sum(r['dimensions'][axis]['match'] for r in rr) for axis in ('code_structure','style_management','type_detail')},
            'all_three_style_match':sum(all(v['match'] for v in r['dimensions'].values()) for r in rr),
            'type_behavior_and_three_style':sum(passed(evaluations[r['id']],'types') and passed(evaluations[r['id']],'runtime') and all(v['match'] for v in r['dimensions'].values()) for r in rr)}}
    return results

def report():
    verify();mapping=read(BASE/'blind_mapping.json');reviews={};counts={};paths=[]
    for reviewer in ('a','b'):
        rows=[]
        files=sorted((BASE/f'reviews/{reviewer}').glob('*.json'))
        assert {p.stem for p in files}==set(mapping)
        for path in files:
            row=read(path);assert row['output_id']==path.stem
            meta=mapping[row['output_id']];assert row['kind']==meta['kind']
            rows.append({**row,**meta});paths.append(path)
        reviews[reviewer]={r['output_id']:r for r in rows}
        counts[reviewer]=aggregate([r for r in rows if r['kind']=='summary'],[r for r in rows if r['kind']=='react'])
    disagreements=[]
    for oid,meta in mapping.items():
        a=reviews['a'][oid];b=reviews['b'][oid];differences=[]
        if meta['kind']=='summary':
            for key in ('sentence_count','length_pass','wording_pass','response_kind'):
                if a[key]!=b[key]:differences.append({'field':key,'a':a[key],'b':b[key]})
            for key in ('facts','priorities'):
                aa={f['id']:f['preserved'] for f in a[key]};bb={f['id']:f['preserved'] for f in b[key]}
                for fid in aa:
                    if aa[fid]!=bb[fid]:differences.append({'field':key+'.'+fid,'a':aa[fid],'b':bb[fid]})
            if bool(a['issues'])!=bool(b['issues']):differences.append({'field':'has_factual_issue','a':bool(a['issues']),'b':bool(b['issues'])})
        else:
            for key in a['dimensions']:
                aa=a['dimensions'][key]['match'];bb=b['dimensions'][key]['match']
                if aa!=bb:differences.append({'field':key,'a':aa,'b':bb})
        if differences:disagreements.append({'output_id':oid,**meta,'differences':differences})
    write('scores.json',{'scope':'Descriptive fixed pilot counts; not statistical superiority/equivalence or human benefit. No composite score across summary content/conditions or React function/style. Two independent anonymous AI reviews; originals and disagreements retained.','by_reviewer':counts,'disagreements':disagreements})
    paths += [BASE/p for p in ('execution_review.json','scores.json')]
    write('review_seal.json',{'sealed_utc':datetime.now(timezone.utc).isoformat(),'files':{p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in paths}})
    print(counts);print('Disagreements:',len(disagreements))

def complete():
    verify()
    paths=sorted(p for p in BASE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='completion_seal.json')
    write('completion_seal.json',{'sealed_utc':datetime.now(timezone.utc).isoformat(),'files':{p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in paths}})
    print('Completion artifacts sealed.')

if __name__=='__main__':
    import sys
    {'report':report,'complete':complete}[sys.argv[1]]()

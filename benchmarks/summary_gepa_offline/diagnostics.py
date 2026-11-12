"""Reference overlap diagnostic, withheld from GEPA and all generators/reviewers."""
import argparse
import re

from benchmarks.summary_gepa_offline.run import ROOT, RUN, read, write, verify


def tokens(text):
    return re.findall(r'\w+', text.casefold())


def lcs_f1(left, right):
    """Whitespace-independent lowercase word-token LCS F1, without stemming."""
    a,b=tokens(left),tokens(right)
    if not a or not b:return 0.0
    previous=[0]*(len(b)+1)
    for token in a:
        current=[0]
        for j,other in enumerate(b,1):
            current.append(previous[j-1]+1 if token==other else max(current[-1],previous[j]))
        previous=current
    return 2*previous[-1]/(len(a)+len(b))


def prepare():
    data=read(ROOT/'data/macsum/dataset/macdoc/test.json')
    records=[]
    for c in read(RUN/'final/cases.json'):
        row=data[c['record_index']]
        assert '\n'.join(row['source'])==c['source']
        available=[r for r in row['references'] if not r['control_attribute'].get('topic')]
        matched=[r for r in available if r['control_attribute'].get('length')==c['profile']['length']]
        chosen=matched or available
        assert chosen
        records.append({'id':c['id'],'policy':'topic-free, requested-length match if available; otherwise all topic-free',
                        'length_matched':bool(matched),'references':[{'text':r['summary'],'control':r['control_attribute']} for r in chosen]})
    write(RUN/'final/references.json',records)
    print('Reference selection frozen before outputs; not used by GEPA.')


def measure():
    verify()
    refs={r['id']:r for r in read(RUN/'final/references.json')}
    plan=read(RUN/'final_plan.json');report={'arms':{},'method':'Maximum lowercase word-token LCS F1 over preselected human references; no stemming. Not an official ROUGE implementation or factuality metric.',
        'selection_use':'Never supplied to GEPA or generators/reviewers. Post-hoc diagnostic only; no candidate selection on this score.',
        'limitations':'Lexical/style overlap can penalize faithful alternatives and reward copied wording. Human references can omit details or contain errors.'}
    for arm in plan['unique_generation_arms']:
        records=[]
        for row in read(RUN/'final/outputs'/f'{arm}.json'):
            values=[lcs_f1(row['summary'],r['text']) for r in refs[row['id']]['references']]
            records.append({'id':row['id'],'max_reference_lcs_f1':max(values),'words':len(row['summary'].split())})
        report['arms'][arm]={'mean_max_reference_lcs_f1':sum(r['max_reference_lcs_f1'] for r in records)/len(records),
                             'mean_words':sum(r['words'] for r in records)/len(records),'records':records}
    for alias,source in plan['aliases'].items():report['arms'][alias]=dict(report['arms'][source],copied_from=source)
    write(RUN/'final/diagnostics.json',report)
    print({k:{n:v[n] for n in ['mean_max_reference_lcs_f1','mean_words']} for k,v in report['arms'].items()})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','measure'])
    globals()[p.parse_args().command]()

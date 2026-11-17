"""Create anonymized packets without generation instructions or automated scores."""
import random
from datetime import datetime, timezone
from .prepare_sources import ROOT, BASE, sha, write
from .run import read, verify

def extension():
    rubric=read(BASE/'rubric.json')
    write('reviewer_rubric.json',{'summary':rubric['summary'],'react':rubric['react']})
    write('review_extension.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),
       'reason':'Coordinator requested two fresh independent AI reviewers instead of the planned single investigator review.',
       'timing':'Added after input freeze and generation launch, before coordinator read any generated answer; only output file counts were inspected.',
       'unchanged':'All pre-frozen semantic/style criteria, tasks, core anchors, inputs and runtime checks remain unchanged.',
       'review':'Two new fork_turns=none agents, neither a generator, independently receive anonymous answers and source/task, target conditions and frozen facts only. No arm, generation prompt, automatic score, references, execution results or other review. Original judgments retained; disagreements reported, not reconciled to improve scores.',
       'limitation':'AI-assisted qualitative judgments, not human gold. Wording/code may reveal a strategy despite arm anonymization.',
       'frozen_rubric_sha256':sha((BASE/'rubric.json').read_bytes())})
    paths=[BASE/'reviewer_rubric.json',BASE/'review_extension.json',Path(__file__)]
    write('review_extension_seal.json',{'files':{p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in paths}})

def packet():
    verify();outputs=read(BASE/'all_outputs.json');random.Random(2026111709).shuffle(outputs)
    cases={r['id']:r for r in read(BASE/'summary_cases.json')};tasks={r['id']:r for r in read(BASE/'react_tasks.json')}
    mapping={};summary=[];react=[]
    for i,row in enumerate(outputs,1):
        oid=f'B{i:03d}';mapping[oid]={'id':row['id'],'arm':row['arm'],'kind':row['kind']}
        if row['kind']=='summary':
            c=cases[row['id']]
            summary.append({'output_id':oid,'kind':'summary','source':c['source'],'target':c['effective_profile'],
                'coverage_policy':c['coverage_policy'],'facts':c['facts'],
                'required_passages':[{'id':f'P{i}','text':s} for i,s in enumerate(c['required_sentences'],1)],'answer':row['answer']})
        else:
            t=tasks[row['id']]
            react.append({'output_id':oid,'kind':'react','task':t['requirements'],'contract_types':t['contract_types'],
                'target':t['target'],'common_requirements':'Complete named files; Component and Props exported from Component.tsx. Panel design: background #eef4ff, color #17345c, padding 12px, gap 6px, flex/grid; Korean explanation after code. No execution claims.','answer':row['answer']})
    write('blind_summary.json',summary);write('blind_react.json',react);write('blind_mapping.json',mapping)
    paths=[BASE/p for p in ('blind_summary.json','blind_react.json','blind_mapping.json')]
    write('blind_seal.json',{'files':{p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in paths}})
    print('Prepared 12 summary and 16 React anonymous answers.')

if __name__=='__main__':
    import sys
    from pathlib import Path
    {'extension':extension,'packet':packet}[sys.argv[1]]()

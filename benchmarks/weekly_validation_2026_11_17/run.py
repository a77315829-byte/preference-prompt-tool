"""Sealed first-response evaluation. No model calls and no output repairs."""
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone

from .prepare_sources import ROOT, BASE, sha, write

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def verify():
    for name in ('frozen.json','generation_seal.json','review_seal.json','completion_seal.json'):
        path=BASE/name
        if not path.exists():continue
        for filename,digest in read(path)['files'].items():
            assert sha((ROOT/filename).read_bytes())==digest,filename
    print('All present seals valid.')

def seal():
    verify()
    outputs=[]; paths=[]
    for arm in ('manual','product'):
        inputs=read(BASE/f'inputs/{arm}.json')
        files=list((BASE/f'outputs/{arm}').glob('*.json'))
        assert {p.stem for p in files}=={r['id'] for r in inputs}
        for item in inputs:
            path=BASE/f"outputs/{arm}/{item['id']}.json";row=read(path)
            assert row['id']==item['id'] and row['kind']==item['kind']
            assert isinstance(row['answer'],str) and row['answer'].strip()
            outputs.append({**row,'arm':arm});paths.append(path)
    write('all_outputs.json',outputs);paths.append(BASE/'all_outputs.json')
    write('generation_seal.json',{'sealed_utc':datetime.now(timezone.utc).isoformat(),'files':{p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in paths}})
    print('Sealed 28 first responses.')

def materialize():
    verify();records=[]
    for row in read(BASE/'all_outputs.json'):
        if row['kind']!='react':continue
        answer=row['answer'].replace('\r\n','\n');files={};provenance=[]
        fences=list(re.finditer(r'^```([^\n]*)\n(.*?)^```[ \t]*$',answer,re.M|re.S))
        for i,m in enumerate(fences):
            preceding=answer[fences[i-1].end() if i else 0:m.start()]
            names=re.findall(r'(?<![\w/.-])([A-Za-z0-9_-][A-Za-z0-9_./-]*\.(?:tsx|ts|css))(?![\w.-])',preceding+'\n'+m[1])
            if not names:
                raise ValueError('Unlabeled file in '+row['id'])
            name=names[-1]
            assert not name.startswith('/') and '..' not in name.split('/') and not name.endswith('.d.ts') and name not in files
            files[name]=m[2]
            provenance.append({'filename':name,'block_index':i,'start':m.start(2),'end':m.end(2),'reason':'Explicit nearest filename label; code copied byte-for-byte after line-ending normalization.'})
        assert 'Component.tsx' in files and 1<=len(files)<=10
        rel=f"materialized/{row['arm']}/{row['id']}.json"
        write(rel,{'files':files,'provenance':provenance})
        records.append({'arm':row['arm'],'id':row['id'],'path':rel,'sha256':sha((BASE/rel).read_bytes()),'provenance':provenance})
    write('applications.json',records)
    print('Materialized 16 React answers without code edits.')

def child_env():
    env={k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','PATH','PATHEXT','TEMP','TMP')}
    env.update(NODE_ENV='development',PYTHON_DOTENV_DISABLED='1')
    return env

def inspect():
    verify();records=[]
    for app in read(BASE/'applications.json'):
        proc=subprocess.run([shutil.which('node'),str(BASE/'evaluate.cjs'),app['id'],str(BASE/app['path']),'--inspect'],env=child_env(),capture_output=True,text=True,encoding='utf-8',timeout=45)
        result=json.loads(proc.stdout)
        records.append({'arm':app['arm'],'id':app['id'],'candidate_sha256':app['sha256'],'inspection':result})
    write('static_inspection.json',records)
    print('Static gate complete; semantic code review still required before execute.')

def execute():
    verify();review=read(BASE/'execution_review.json');assert review['approved'] is True
    audited={(r['arm'],r['id']):r for r in review['candidates']}
    for app in read(BASE/'applications.json'):
        assert audited[(app['arm'],app['id'])]['candidate_sha256']==sha((BASE/app['path']).read_bytes())
        dest=f"evaluation/{app['arm']}/{app['id']}.json"
        if (BASE/dest).exists():continue
        try:
            proc=subprocess.run([shutil.which('node'),str(BASE/'evaluate.cjs'),app['id'],str(BASE/app['path']),'--reviewed'],env=child_env(),capture_output=True,text=True,encoding='utf-8',timeout=90)
            result=json.loads(proc.stdout);result['process_returncode']=proc.returncode;result['process_stderr']=proc.stderr
        except subprocess.TimeoutExpired:
            result={'status':'timeout','types':None,'runtime':None}
        except (ValueError,OSError) as error:
            result={'status':'harness_error','error':str(error),'types':None,'runtime':None}
        write(dest,result);print(app['arm'],app['id'],result.get('runtime',{}).get('passed') if result.get('runtime') else result.get('status'),flush=True)

def automatic():
    verify()
    from checks import summarization_grounded_v3 as checks
    from engine.domain_loader import load_domain
    domain=load_domain(ROOT/'domains/summarization_grounded_v3.yaml')
    cases={c['id']:c for c in read(BASE/'summary_cases.json')};rows=[]
    for output in read(BASE/'all_outputs.json'):
        if output['kind']!='summary':continue
        c=cases[output['id']];summary=output['answer'];profile=c['effective_profile']
        row={'id':c['id'],'arm':output['arm'],'automatic_sentence_count':len(checks.split_sentences(summary)),
             'summary_words':len(summary.split()),'source_words':c['source_words']}
        for axis in ('length','extractiveness'):
            spec=domain.axis(axis).check_for(profile[axis]);score,feedback=getattr(checks,spec.fn)(summary,c['source'],profile[axis],spec.target)
            row[axis]={'score':score,'feedback':feedback}
        rows.append(row)
    write('summary_automatic.json',{'scope':'Heuristic conditions only, not semantic content or a quality ranking. Grammatical sentence review and exact evidence reported separately.','rows':rows})

if __name__=='__main__':
    import sys
    {'verify':verify,'seal':seal,'materialize':materialize,'inspect':inspect,'execute':execute,'automatic':automatic}[sys.argv[1]]()

"""Frozen current three-axis React study. No paid API calls."""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import random
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
RUN = BASE / 'results/2026-11-12'
ARMS = ('general', 'manual', 'product')
AXES = ('code_structure', 'style_management', 'type_detail')
VALUES = (('compact', 'separated'), ('direct', 'theme'), ('inferred', 'explicit'))
MANUAL = {
 'compact': 'Keep the small feature in one file, including its component, state handling and styles, with a concise organization.',
 'separated': 'Organize the component, state handling and styles into separate files according to their responsibilities. Clearly label every file and provide its code.',
 'direct': 'Place literal color, spacing and size values directly in the component or styling rules, where they can be seen immediately.',
 'theme': 'Put color, spacing and font design values together in a theme or set of design tokens. Reference these values in the component styling so a design change can be made centrally.',
 'inferred': 'Let TypeScript infer obvious local variable and simple return types instead of restating them. Add annotations only at public boundaries that need them.',
 'explicit': 'Write explicit annotations for props, function parameters and return values, state, and the main data structures.',
}
COMMON = '''환경: TypeScript 5.9.3 strict, React/ReactDOM 19.3.0. 기능 요구와 공개 타입 계약이 스타일 선택보다 우선합니다.
Component.tsx에서 Component와 Props를 named export 하세요. Props의 이름·필드·콜백 계약을 유지하세요. 필요한 모든 파일의 이름과 전체 코드를 fenced block으로 제시하세요.
React와 직접 제공한 상대경로 .ts/.tsx 파일 및 일반 .css 파일만 사용합니다. CSS는 import './styles.css' 같은 side-effect 방식만 허용하며 CSS Modules와 .d.ts 파일은 지원하지 않습니다. CSS @import, url(), 외부 폰트·리소스는 사용하지 마세요.
CSS의 역슬래시 escape는 사용하지 않습니다. at-rule은 @media, @supports, @keyframes, @-webkit-keyframes만 허용합니다. CSS 변수와 var()는 사용할 수 있습니다.
타입 추론을 선택했어도 빈 배열·null·유니언 상태나 CSS 속성 리터럴처럼 strict 컴파일에 필요한 타입은 명시할 수 있습니다. 이 기능상 예외를 제외한 로컬 변수·반환값·상태의 표기 수준은 제공된 스타일 지침을 따릅니다.
새 패키지·네트워크·파일시스템·저장소·타이머·동적 코드 실행을 사용하지 마세요. 명시적 any 또는 @ts-ignore/@ts-nocheck/@ts-expect-error로 검사를 우회하지 마세요.
과제에서 정한 영문 UI 문구는 그대로 쓰고 설명은 한국어로 작성하세요. 코드는 실행·테스트하지 않으며 실행했다고 주장하지 마세요.
'''

def read(path):
 return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write(path, value):
 path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('x',encoding='utf-8',newline='\n') as stream:
  json.dump(value,stream,ensure_ascii=False,indent=2); stream.write('\n')

def sha(path):
 return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def seal(path, paths):
 write(path,{str(p.relative_to(ROOT)):sha(p) for p in paths})

def check_seal(path):
 for name,digest in read(path).items(): assert sha(ROOT/name)==digest,name

def verify():
 for name in ('frozen.json','generation_seal.json','application_seal.json','review_seal.json'):
  if (RUN/name).exists(): check_seal(RUN/name)

def prepare():
 from engine.domain_loader import load_domain
 from engine.estimator import Estimator
 from engine.generator import build_final_prompt
 from service import final_prompt, final_combo
 domain=load_domain(ROOT/'domains/coding.yaml')
 tasks=read(BASE/'tasks.json')['tasks']; assert len(tasks)==8
 snapshots={}; assignments={}; inputs={a:[] for a in ARMS}
 for task,values in zip(tasks,itertools.product(*VALUES)):
  target=dict(zip(AXES,values)); assignments[task['id']]=target
  estimator=Estimator(domain)
  for axis,value in target.items(): estimator.utilities[axis][value]=1.0
  assert final_combo(domain,estimator)==target
  product=final_prompt(domain,estimator,language='en')
  assert product==build_final_prompt(domain,target,language='en')
  general=build_final_prompt(domain,{},language='en')
  head,tail=general.split('## Always',1)
  manual=head+'## Requested style\n'+'\n'.join('- '+MANUAL[v] for v in values)+'\n\n## Always'+tail
  snapshots[task['id']]={'target':target,'general':general,'manual':manual,'product':product}
  for arm in ARMS: inputs[arm].append({'id':task['id'],'request':snapshots[task['id']][arm]+'\n\n## Development request\n'+COMMON+'\n'+task['prompt']})
 write(RUN/'product_snapshots.json',snapshots);write(RUN/'assignment.json',assignments)
 for arm,offset in zip(ARMS,(0,3,6)):
  rows=inputs[arm];write(RUN/f'inputs/{arm}.json',rows[offset:]+rows[:offset])
 write(RUN/'environment.json',{'versions':{name:read(ROOT/'frontend/node_modules'/name/'package.json')['version'] for name in ('typescript','react','react-dom','jsdom','@types/react')},'source_sha256':{p:sha(ROOT/p) for p in ('domains/coding.yaml','engine/generator.py','engine/estimator.py','service.py')},'product_prompt_identity':True,'paid_model_api_calls':0})

def freeze():
 c=read(RUN/'controls_summary.json');assert c['all_references_pass'] and c['all_mutants_detected']
 paths=sorted(p for p in BASE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
 paths += [ROOT/p for p in read(RUN/'environment.json')['source_sha256']]
 seal(RUN/'frozen.json',paths)

def blind():
 verify();tasks={t['id']:t for t in read(BASE/'tasks.json')['tasks']};assignment=read(RUN/'assignment.json');entries=[]
 for arm in ARMS:
  rows=read(RUN/f'outputs/{arm}.json');assert len(rows)==8 and {r['id'] for r in rows}==set(tasks)
  for row in rows:
   assert isinstance(row['answer'],str) and row['answer'].strip();entries.append((arm,row['id'],row['answer']))
 random.Random(2026111203).shuffle(entries);packet=[];mapping={}
 for i,(arm,tid,answer) in enumerate(entries,1):
  oid=f'S{i:03d}';packet.append({'output_id':oid,'task_id':tid,'task':tasks[tid]['prompt'],'target':assignment[tid],'answer':answer});mapping[oid]={'arm':arm,'task_id':tid}
 write(RUN/'blind_packet.json',packet);write(RUN/'blind_mapping.json',mapping)
 seal(RUN/'generation_seal.json',[RUN/f'outputs/{a}.json' for a in ARMS]+[RUN/'blind_packet.json',RUN/'blind_mapping.json'])

def blocks(answer):
 text=answer.replace('\r\n','\n')
 return [{'language':m[1].strip(),'text':m[2],'start':m.start(2),'end':m.end(2)} for m in re.finditer(r'^```([^\n]*)\n(.*?)^```[ \t]*$',text,re.M|re.S)]

def materialize():
 verify();apps=read(RUN/'applications.json');packet=read(RUN/'blind_packet.json');assert set(apps)=={r['output_id'] for r in packet}
 for row in packet:
  oid=row['output_id'];app=apps[oid]
  if app.get('unresolved'):result={'status':'delivery_unresolved','reason':app['unresolved']}
  else:
   fences=blocks(row['answer']);files={};provenance=[]
   for op in app['files']:
    path=op['path'].removeprefix('./');idx=op['block']
    assert re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_-][A-Za-z0-9_.-]*)*\.(?:tsx|ts|css)',path)
    assert not path.endswith('.d.ts') and path not in files and isinstance(idx,int) and 0<=idx<len(fences)
    assert op['reason'].strip();files[path]=fences[idx]['text'];provenance.append(dict(op,start=fences[idx]['start'],end=fences[idx]['end']))
   assert 'Component.tsx' in files and 1<=len(files)<=10
   result={'status':'ready','files':files,'provenance':provenance}
  write(RUN/f'materialized/{oid}.json',result)
 seal(RUN/'application_seal.json',[RUN/'applications.json']+sorted((RUN/'materialized').glob('*.json')))

def execute():
 verify();audit=read(RUN/'execution_review.json');assert audit['approved'] is True
 env={k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','PATH','PATHEXT','TEMP','TMP')};env['NODE_ENV']='development'
 for row in read(RUN/'blind_packet.json'):
  oid=row['output_id'];candidate=RUN/f'materialized/{oid}.json';dest=RUN/f'evaluation/{oid}.json'
  if dest.exists():continue
  assert audit['candidate_sha256'][oid]==sha(candidate)
  if read(candidate)['status']!='ready':write(dest,{'status':'delivery_unresolved','types':None,'runtime':None});continue
  try:
   proc=subprocess.run([shutil.which('node'),str(BASE/'evaluate.cjs'),row['task_id'],str(candidate),'--reviewed'],cwd=BASE,env=env,capture_output=True,text=True,encoding='utf-8',timeout=45)
   result=json.loads(proc.stdout);result['process_returncode']=proc.returncode;result['process_stderr']=proc.stderr
  except subprocess.TimeoutExpired:result={'status':'timeout','types':None,'runtime':None}
  except (OSError,json.JSONDecodeError) as exc:result={'status':'evaluation_error','error':str(exc),'types':None,'runtime':None}
  write(dest,result);print(oid,result.get('status','evaluated'),flush=True)

def validate_review(rows,packet):
 by={r['output_id']:r for r in packet};assert len(rows)==len(by) and {r['output_id'] for r in rows}==set(by)
 for r in rows:
  assert set(r['dimensions'])==set(AXES)
  for v in r['dimensions'].values():
   assert type(v['match']) is bool and v['reason'].strip() and isinstance(v['answer_quotes'],list)
   for quote in v['answer_quotes']:assert quote and quote in by[r['output_id']]['answer']
  for name in ('ambiguities','other_observations','unsupported_execution_claims'):assert isinstance(r[name],list)
  for claim in r['unsupported_execution_claims']:assert claim['quote'] in by[r['output_id']]['answer'] and claim['reason'].strip()

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','freeze','verify','blind','materialize','execute']);globals()[parser.parse_args().command]()

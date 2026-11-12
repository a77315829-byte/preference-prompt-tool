"""Fixed arm aggregates; preserve disagreement and technical non-completion."""
from benchmarks.react_style_current.run import RUN,ARMS,AXES,read,write,verify,seal,validate_review

def aggregate():
 verify();packet=read(RUN/'blind_packet.json');mapping=read(RUN/'blind_mapping.json')
 evaluations={r['output_id']:read(RUN/f'evaluation/{r["output_id"]}.json') for r in packet}
 reviews={k:read(RUN/f'review_{k}.json') for k in ('a','b')}
 for rows in reviews.values():validate_review(rows,packet)
 report={'technical':{},'style_by_reviewer':{},'disagreements':[],'ambiguity_flags':[],'execution_claim_flags':[]}
 for arm in ARMS:
  ids=[oid for oid,m in mapping.items() if m['arm']==arm]
  out={'answers':len(ids),'delivery_ready':0,'compiler_pass':0,'clean_type_pass':0,'type_completed':0,'runtime_pass':0,'runtime_completed':0,'type_runtime_joint':0,'runtime_checks_passed':0,'runtime_checks_total':0,'unresolved_or_errors':[]}
  for oid in ids:
   e=evaluations[oid];t=e.get('types') or {};r=e.get('runtime') or {}
   out['delivery_ready']+=read(RUN/f'materialized/{oid}.json')['status']=='ready'
   out['compiler_pass']+=t.get('compilerPassed') is True;out['clean_type_pass']+=t.get('passed') is True
   out['type_completed']+=t.get('status')=='completed';out['runtime_pass']+=r.get('passed') is True;out['runtime_completed']+=r.get('status')=='completed'
   out['type_runtime_joint']+=t.get('passed') is True and r.get('passed') is True
   out['runtime_checks_passed']+=sum(c['passed'] for c in r.get('checks',[]));out['runtime_checks_total']+=len(r.get('checks',[]))
   if t.get('status')!='completed' or r.get('status')!='completed':out['unresolved_or_errors'].append({'output_id':oid,'status':e.get('status'),'type_status':t.get('status'),'runtime_status':r.get('status')})
  report['technical'][arm]=out
 by={k:{r['output_id']:r for r in rows} for k,rows in reviews.items()}
 for k,rows in reviews.items():
  totals={}
  for arm in ARMS:
   selected=[r for r in rows if mapping[r['output_id']]['arm']==arm]
   totals[arm]={'answers':len(selected),'dimensions':{axis:sum(r['dimensions'][axis]['match'] for r in selected) for axis in AXES},'all_three':sum(all(d['match'] for d in r['dimensions'].values()) for r in selected),'type_runtime_all_three_joint':sum(all(d['match'] for d in r['dimensions'].values()) and (evaluations[r['output_id']].get('types') or {}).get('passed') is True and (evaluations[r['output_id']].get('runtime') or {}).get('passed') is True for r in selected)}
  report['style_by_reviewer'][k]=totals
 for row in packet:
  oid=row['output_id'];a=by['a'][oid];b=by['b'][oid]
  dims=[axis for axis in AXES if a['dimensions'][axis]['match']!=b['dimensions'][axis]['match']]
  if dims:report['disagreements'].append({'output_id':oid,'dimensions':dims})
  if a['ambiguities'] or b['ambiguities']:report['ambiguity_flags'].append(oid)
  if a['unsupported_execution_claims'] or b['unsupported_execution_claims']:report['execution_claim_flags'].append(oid)
 report['limits']='Eight paired tasks, each assigned one unique style combination. Not eight independent replications per combination. General target match is not obedience to unsupplied instructions. AI review is not human preference evidence. No statistical superiority or equivalence proof.'
 write(RUN/'scores.json',report);seal(RUN/'review_seal.json',[RUN/f'review_{k}.json' for k in ('a','b')]+[RUN/'scores.json']+sorted((RUN/'evaluation').glob('*.json')))
 return report

if __name__=='__main__':
 import json
 print(json.dumps(aggregate(),ensure_ascii=False,indent=2))

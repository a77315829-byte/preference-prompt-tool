"""Prepare/freeze a no-API, first-response pilot. All writes are exclusive."""
import json
from datetime import datetime, timezone
from pathlib import Path

from engine.domain_loader import load_domain
from engine.generator import build_final_prompt
from summary_contracts import source_sentences, task_data_block
from summary_contracts_v2 import prepare_summary_contract
from benchmarks.summary_contract_revision.run import manual_prompt
from .prepare_sources import ROOT, BASE, sha, write
from .task_specs import tasks

MANUAL = {
 'compact':'Keep the component, logic and every style in a single TSX file. Do not create an extra CSS file; local helpers and inline/style objects are fine.',
 'separated':'Split the component from either styling or state/logic into meaningful files by responsibility. A connected styling file is sufficient even when state stays with the component. Do not invent extra components, empty modules or type-only files. Supply all required files completely.',
 'direct':'Place the literal design values directly in the relevant styles or JSX. Plain style objects or CSS rules are fine; do not introduce a semantic token/theme layer.',
 'theme':'Centralize design colors and spacing in named design tokens or a theme, then reference those values from actual styling. Same-file tokens are fine. Merely naming a literal style object theme is not a token layer.',
 'inferred':'Use inference for obvious local variables, function return values and primitive state; avoid React.FC and redundant useState<number>(0)-style annotations. Explicitly type public props, non-inferable empty-array/null state, intended unions and constrained CSS values when necessary. Prefer contextual inline event typing; annotate event parameters for standalone handlers. Necessary strict types do not violate inference.',
 'explicit':'Explicitly annotate public props, important data structures, state, function parameters and return types. Concise inline callbacks may use their contextual types; do not use type assertions as a substitute for an accurate public contract.'
}

SELECTED = [[0,10,11],[4,51,54],[1,13,19],[7,15,17],[0,1,2],[0,9,17]]
PROFILES = [('short','normal',None),('normal','normal',None),('short','fully','expand'),
            ('short','fully','rephrase'),('short','fully','keep_limits'),('normal','high',None)]
FACTS = [
 [('Malegaon police require cattle identification/photos after the Maharashtra beef ban.', [0,1]),
  ('Sale or consumption of beef may bring five years in prison.', [10]),
  ('Buffalo slaughter remains permissible.',[11])],
 [('The writer is horrified by the Genesis story of Lot.',[4]),
  ('The writer says their faith does not include such a punitive God.',[51]),
  ('Despite uncertainty and distress the writer will continue reading.',[46,47,50,54])],
 [('Warnock found an SUV dangling over a cliff in Lewiston, Idaho.',[1]),
  ('Warnock pulled Sitko out to safety.',[13]),
  ('Sitko went to hospital with only minor injuries.',[19])],
 [('Poulin publicly apologized for his Scary Lucy sculpture.',[7,8]),
  ('Poulin offered his own time and money to redo it.',[15]),
  ('The mayor refused and said the town wanted a different sculptor.',[16,17])],
 [('Actor Geoffrey Lewis died.',[0]),
  ('He was 79.',[1]),
  ('Family friend Michael Henderson reported he died Tuesday.',[2])],
 [('Two Denver TSA screeners were fired over the alleged groping scheme, according to police.',[0]),
  ('According to police the female screener admitted doing it at least 10 other times.',[9]),
  ('Charges were described as unlikely because no victim had been identified.',[17,18])],
]

def prepare():
    sources=json.loads((BASE/'summary_sources.json').read_text(encoding='utf-8'))
    cases=[]; inputs={'manual':[], 'product':[]}
    for c, indices, (length, wording, resolution), facts in zip(sources,SELECTED,PROFILES,FACTS):
        sentences=source_sentences(c['source'])
        body={'domainKey':'summarization','profile':{'length':length,'extractiveness':wording,'topic':''},
              'sourceText':c['source'],'requiredSentences':[sentences[i] for i in indices],'resolution':resolution}
        contract=prepare_summary_contract(body)
        assert contract['status']=='ready'
        if resolution:
            assert prepare_summary_contract({**body,'resolution':None})['status']=='needs_resolution'
        cases.append({**c,'request_body':body,'effective_profile':contract['effective_profile'],
                      'coverage_policy':contract['coverage_policy'],'resolution':contract['resolution'],
                      'required_sentences':contract['required_sentences'],
                      'facts':[{'id':f'F{i}','claim':claim,'source_evidence':[sentences[n] for n in ns]} for i,(claim,ns) in enumerate(facts,1)]})
        common=task_data_block(c['source'],contract['required_sentences'],contract['resolution'],'en')
        inputs['manual'].append({'id':c['id'],'kind':'summary','request':manual_prompt(contract['effective_profile'])+'\n\n'+common})
        inputs['product'].append({'id':c['id'],'kind':'summary','request':contract['task_requests']['en']})
    write('summary_cases.json',cases)
    react=tasks(); write('react_tasks.json',react)
    domain=load_domain(ROOT/'domains/coding/v2.yaml')
    snapshots=[]
    for task in react:
        product=build_final_prompt(domain,task['target'],language='en')
        manual='Implement the supplied TypeScript/React task accurately. Follow these confirmed style choices consistently:\n'+'\n'.join('- '+MANUAL[v] for v in task['target'].values())+'\nProvide complete usable code, preserve accessibility and the public interface, and do not add unrequested features.'
        snapshots.append({'id':task['id'],'target':task['target'],'manual':manual,'product':product})
        for arm, instruction in [('manual',manual),('product',product)]:
            inputs[arm].append({'id':task['id'],'kind':'react','request':instruction+'\n\n'+task['prompt']})
    write('product_snapshots.json',snapshots)
    for arm,rows in inputs.items():write(f'inputs/{arm}.json',rows)
    rubric={
      'summary':{'length':'Grammatical sentence count: short 1-2, normal 3-4, long >=5; automatic v3 count reported separately if disagreement.',
        'wording':'normal is predominantly paraphrase allowing names/numbers/necessary expressions; high substantially reuses phrases with no upper bound; fully uses only complete source sentences unchanged except publisher/whitespace allowance, without duplicate padding.',
        'content':'Review each frozen atomic fact against exact output evidence; separately review all three selected passages and every unsupported/distorted claim. Missing facts are not hallucinations. Keep_limits explicitly permits omission and does not require all selected facts.',
        'priority':'Semantic information, not exact copying, unless fully. Attribution, qualifiers, uncertainty and the author perspective must remain clear.',
        'no_composite_score':True},
      'react':{'code_structure':'compact: all needed code/styles in one TSX; separated: meaningful connected component/style OR component/state boundary; style-only split is sufficient, no three-file quota.',
        'style_management':'direct: literal design values in applied styles; theme: centralized semantic color/spacing tokens referenced by applied styles. A plain CSSProperties rule object is direct, not automatically theme.',
        'type_detail':'inferred: omit inferable local/return/primitive state annotations, permit necessary public/empty/null/union/CSS/event types. explicit: type props, principal functions/returns/state/data; contextual concise inline callbacks allowed, explain ambiguous cases.',
        'supporting':'Exact required panel values and unsubstantiated execution claims are checked separately. Do not count behavior bugs as style bugs automatically.'},
      'review':'One investigator qualitative review, explicitly not a blinded independent human gold evaluation. Preserve evidence/uncertainty. Type and behavior measured separately. No response repair or retries.'}
    write('rubric.json',rubric)
    write('protocol.json',{'prepared_utc':datetime.now(timezone.utc).isoformat(),'arms':['manual','product'],
      'summary_sources':6,'react_tasks':8,'first_responses':28,
      'design':'Strong investigator-written manual versus exact product builder requests. Targets already confirmed; whole-prompt comparison, not preference inference or causal attribution to one edited clause.',
      'newness':'Source scan in source_sampling.json. Eight new synthetic React tasks differ from both previous eight-task sets. Public corpus may be in training.',
      'generation':'Two fresh fork_turns=none Codex agents, inherited model/settings, each gets only its arm. Same task order. No tests/other arm/reference controls/old outputs. First response written once; no code execution; no paid API. One arm per conversation creates within-arm dependence.',
      'controls':'Pre-generation reference positive and behavior-mutant controls for each new React task; old inspected evaluator reused, new JSDOM suites. Every candidate reviewed before execution.',
      'evaluation':'TypeScript strict/public interface/any/suppression checks; 5 real React-JSDOM behavior checks per task; independent from 3-axis qualitative judgments. Summary automatic format plus evidence-based content review. Report failures and interpretation limits.',
      'limitations':['Small convenience pilot; task/profile confounded; no significance, superiority or statistical equivalence claim.','No Korean summaries, actual human preferences, UI convenience, adoption, or human time saving measured.','No actual browser/layout/security/server coverage; code review/VM is not an OS sandbox.','Exact Codex model version, sampling configuration, token cost not exposed. Agent elapsed time is not human time.','No GEPA execution or evidence for GEPA necessity.'],
      'paid_model_api_calls':0,'stop':'Freeze inputs/rubric/tests and hashes before generation; seal outputs before evaluation; never tune/regenerate on results.'})
    (BASE/'outputs').mkdir(exist_ok=True)
    print('Prepared 6 summaries, 8 React tasks, 28 requests; freeze after controls.')

def freeze():
    controls=json.loads((BASE/'controls_results.json').read_text(encoding='utf-8'))
    assert controls['all_references_pass'] and controls['all_mutants_detected']
    paths=[p for p in BASE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and 'outputs' not in p.parts]
    paths += [ROOT/p for p in ['domains/coding/v2.yaml','summary_contracts_v2.py','summary_contracts.py',
        'domains/summary_contract/v2.yaml','domains/summary_contract.yaml','domains/summarization_grounded_v2.yaml',
        'domains/summarization_grounded_v3.yaml','checks/summarization_grounded_v3.py','engine/generator.py',
        'engine/domain_loader.py','benchmarks/react_style_current/evaluate.cjs','benchmarks/summary_contract_revision/run.py']]
    write('frozen.json',{'frozen_utc':datetime.now(timezone.utc).isoformat(),'files':{p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted(paths)}})
    print('Inputs/tests/criteria sealed before generation.')

if __name__=='__main__':
    import sys
    {'prepare':prepare,'freeze':freeze}[sys.argv[1]]()

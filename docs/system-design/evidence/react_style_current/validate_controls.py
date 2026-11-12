"""Run source-reviewed evaluator controls before candidate generation."""
from concurrent.futures import ThreadPoolExecutor
import os
import shutil
import subprocess
import json
from benchmarks.react_style_current.run import BASE, RUN, read, write


def run(attempt):
    dest = RUN/f'controls_attempt{attempt}'
    dest.mkdir(parents=True, exist_ok=False)
    tasks = read(BASE/'tasks.json')['tasks']
    mutations = {m['task_id']: m for m in read(BASE/'controls/mutations.json')['mutations']}
    jobs = []
    for task in tasks:
        source = (BASE/f'controls/{task["id"]}.tsx').read_text(encoding='utf-8')
        broken = source
        for change in mutations[task['id']]['replacements']:
            assert broken.count(change['from']) == 1
            broken = broken.replace(change['from'], change['to'], 1)
        if task['kind'] == 'bug': assert task['starter_files']['Component.tsx'] == broken
        for kind, code in [('reference', source), ('mutant', broken)]:
            candidate = dest/f'{task["id"]}-{kind}-input.json'
            write(candidate, {'files': {'Component.tsx': code}})
            jobs.append((task['id'], kind, candidate))
    env = {k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','PATH','PATHEXT','TEMP','TMP')}
    env['NODE_ENV'] = 'development'
    def execute(job):
        tid, kind, candidate = job
        try:
            proc = subprocess.run([shutil.which('node'), str(BASE/'evaluate.cjs'), tid, str(candidate), '--reviewed'],
                cwd=BASE, env=env, text=True, encoding='utf-8', capture_output=True, timeout=60)
            try: report = json.loads(proc.stdout)
            except json.JSONDecodeError: report = {'harness_error': proc.stdout, 'stderr': proc.stderr}
            report['process_returncode'] = proc.returncode
        except subprocess.TimeoutExpired:
            report = {'harness_error': 'control process exceeded 60s', 'types': {}, 'runtime': {'status': 'timeout'}}
        write(dest/f'{tid}-{kind}.json', report)
        types = report.get('types', {}); runtime = report.get('runtime', {})
        print(tid, kind, 'types', types.get('passed'), 'runtime', runtime.get('passed'), flush=True)
        return {'task_id':tid, 'kind':kind, 'type_pass':types.get('passed') is True,
                'runtime_complete':runtime.get('status')=='completed', 'runtime_pass':runtime.get('passed') is True,
                'checks_total':len(runtime.get('checks', [])),
                'checks_passed':sum(c['passed'] for c in runtime.get('checks', []))}
    with ThreadPoolExecutor(max_workers=2) as pool: rows=list(pool.map(execute,jobs))
    result={'attempt':attempt,'rows':rows,
        'all_references_pass':all(r['type_pass'] and r['runtime_complete'] and r['runtime_pass'] for r in rows if r['kind']=='reference'),
        'all_mutants_detected':all(r['type_pass'] and r['runtime_complete'] and not r['runtime_pass'] for r in rows if r['kind']=='mutant')}
    write(dest/'summary.json',result)
    if result['all_references_pass'] and result['all_mutants_detected']:
        write(RUN/'controls_summary.json',result)
    else: raise SystemExit('Controls failed: inspect preserved attempt before freezing anything.')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('attempt',type=int);parser.add_argument('--reviewed',action='store_true')
    args=parser.parse_args()
    if not args.reviewed:raise SystemExit('Review control sources and evaluator before execution.')
    run(args.attempt)

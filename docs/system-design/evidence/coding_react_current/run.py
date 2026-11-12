"""Frozen current-product comparison; generation is supplied by Codex agents."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess

from coding_instructions import build_coding_instructions
from coding_work_trials import general_prompt
from benchmarks.coding_react_current.materialize import apply

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).resolve().parent
RUN = BASE / 'results/2026-11-12'
ARMS = ('general', 'manual', 'product')
PROFILES = {
    'P1': {'explanation': 'brief', 'comments': 'essential', 'structure': 'modular', 'output': 'changes'},
    'P2': {'explanation': 'steps', 'comments': 'detailed', 'structure': 'compact', 'output': 'complete'},
}
ASSIGN = {'roster_selection': 'P1', 'queue_pagination': 'P2', 'undo_removal': 'P1', 'draft_filters': 'P2',
          'reservation_validation': 'P1', 'optimistic_favorite': 'P2', 'accordion_keyboard': 'P1', 'resource_union': 'P2'}
MANUAL = {
    'P1': '답변은 코드부터 제시한 뒤 핵심적인 선택 이유와 사용 방법만 짧게 설명해 주세요. 주석은 코드만으로 드러나지 않는 의도·주의점이 필요한 곳에만 달고 코드의 동작을 그대로 되풀이하지 마세요. 기능별 책임이 드러나도록 함수·모듈·파일을 적절히 나누되 이 작업에 필요 없는 계층을 만들지 마세요. 기존 코드 수정은 적용할 파일·위치와 실제 바뀐 코드를 중심으로 주고, 새 파일/새 구현은 필요한 전체 코드를 주세요.',
    'P2': '해결 과정을 단계별로 설명하고 중요한 설계 선택의 이유와 사용 방법을 포함해 주세요. 핵심 로직과 주의할 부분에는 이해를 돕는 주석을 달되 명백한 문법 풀이를 반복하지 마세요. 작은 작업에 불필요한 추상화·파일 분리를 늘리지 말고 간결하게 구성하면서 TypeScript/React의 필수 구조는 지키세요. 필요한 모든 파일의 이름과 전체 코드를 빠짐없이 제시해 바로 적용할 수 있게 해 주세요.',
}
COMMON = '''실행 환경은 TypeScript 5.9.3 strict, React/ReactDOM 19.3.0입니다. 과제 기능·공개 타입 계약과 아래 제약은 모든 작성 선호보다 우선합니다.
실행 진입은 Component.tsx의 named export Component입니다. React 및 제공한 상대경로 .ts/.tsx 파일만 import할 수 있습니다. 새 패키지, CSS 파일, 네트워크·파일시스템·저장소 접근은 사용하지 마세요. 디자인 장식은 요구하지 않습니다.
추가 파일도 실행 소스 .ts/.tsx로 제공하며 별도 .d.ts 선언 파일은 사용하지 마세요.
명시적 any 또는 @ts-ignore/@ts-nocheck 같은 타입 검사 우회는 사용하지 마세요. props 및 callback 계약을 유지하세요. 기능에 필요한 보조 파일은 허용합니다.
설명은 한국어로 작성하고, 코드의 과제 지정 UI 문구와 타입 이름은 그대로 유지하세요. 파일 이름과 적용 위치가 분명하게 드러나게 답하세요.
코드 실행·테스트는 하지 않습니다. 실행했다고 주장하지 말고 확인 방법을 안내하세요. 아래 기존 코드가 있으면 그것만 현재 코드로 취급하세요.
'''


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
    for name, digest in read(path).items():
        assert sha(ROOT / name) == digest, name


def prepare():
    tasks = read(BASE/'tasks.json')['tasks']
    assert {t['id'] for t in tasks} == set(ASSIGN)
    snapshots = {}; inputs = {a: [] for a in ARMS}
    for name, prefs in PROFILES.items():
        profile = {'language': 'TypeScript', 'framework': 'React', 'extra': '', 'preferences': prefs}
        built = build_coding_instructions(profile)
        base = general_prompt(profile, [])
        before, after = base.split('## 항상 지킬 것', 1)
        manual = before + '## 답변 작성 요청\n' + MANUAL[name] + '\n\n## 항상 지킬 것' + after
        snapshots[name] = {'profile': built['profile'], 'general': base, 'manual': manual, 'product': built['prompt']}
    for task in tasks:
        profile_id = ASSIGN[task['id']]
        request = COMMON + '\n' + task['prompt']
        for arm in ARMS:
            inputs[arm].append({'id': task['id'], 'request': snapshots[profile_id][arm] + '\n\n## 이번 작업 요청\n' + request})
    write(RUN/'product_snapshots.json', snapshots)
    write(RUN/'assignment.json', ASSIGN)
    # Predeclared cyclic order offsets reduce a shared first/last-task position.
    for arm, offset in zip(ARMS, (0, 3, 6)):
        rows = inputs[arm]; write(RUN/f'inputs/{arm}.json', rows[offset:] + rows[:offset])
    versions = {name: read(ROOT/'frontend/node_modules'/name/'package.json')['version']
                for name in ['typescript', 'react', 'react-dom', 'jsdom', '@types/react', '@types/react-dom']}
    write(RUN/'environment.json', {'versions': versions, 'node': subprocess.check_output(['node', '--version'], text=True).strip(),
        'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'product_source_sha256': {p: sha(ROOT/p) for p in ['coding_instructions.py', 'coding_work_trials.py',
            'coding_examples.py', 'coding_framework_examples.py', 'coding_elicitation.py']}})


def freeze():
    controls = read(RUN/'controls_summary.json')
    assert controls['all_references_pass'] and controls['all_mutants_detected']
    paths = sorted(p for p in BASE.rglob('*') if p.is_file() and '__pycache__' not in p.parts
                   and p.suffix in ('.json', '.py', '.cjs', '.tsx', '.md', '.tap'))
    paths += [ROOT/p for p in read(RUN/'environment.json')['product_source_sha256']]
    seal(RUN/'frozen.json', paths)


def verify():
    check_seal(RUN/'frozen.json')
    for name in ['generation_seal.json', 'application_seal.json', 'review_seal.json']:
        if (RUN/name).exists(): check_seal(RUN/name)


def blind():
    verify(); tasks = {t['id']: t for t in read(BASE/'tasks.json')['tasks']}; entries = []
    for arm in ARMS:
        rows = read(RUN/f'outputs/{arm}.json')
        assert len(rows) == 8 and {r['id'] for r in rows} == set(tasks)
        for row in rows:
            assert isinstance(row['answer'], str) and row['answer'].strip()
            entries.append((arm, row['id'], row['answer']))
    random.Random(20261112).shuffle(entries); packet = []; mapping = {}
    for i, (arm, tid, answer) in enumerate(entries, 1):
        oid = f'R{i:03d}'; task = tasks[tid]
        packet.append({'output_id': oid, 'task_id': tid, 'task': task['prompt'], 'starter_files': task['starter_files'],
                       'target': PROFILES[ASSIGN[tid]], 'answer': answer})
        mapping[oid] = {'arm': arm, 'task_id': tid, 'profile_id': ASSIGN[tid]}
    write(RUN/'blind_packet.json', packet); write(RUN/'blind_mapping.json', mapping)
    seal(RUN/'generation_seal.json', [RUN/f'outputs/{a}.json' for a in ARMS] + [RUN/'blind_packet.json', RUN/'blind_mapping.json'])


def materialize():
    verify(); operations = read(RUN/'applications.json'); packet = read(RUN/'blind_packet.json')
    assert set(operations) == {r['output_id'] for r in packet}
    prepared = {}
    for row in packet:
        item = operations[row['output_id']]
        if item.get('unresolved'):
            result = {'status': 'delivery_unresolved', 'reason': item['unresolved']}
        else:
            try:
                result = {'status': 'ready', **apply(row['answer'], row['starter_files'], item['operations'])}
            except ValueError as exc:
                result = {'status': 'delivery_unresolved', 'reason': str(exc)}
        prepared[row['output_id']] = result
    for oid, result in prepared.items(): write(RUN/f'materialized/{oid}.json', result)
    seal(RUN/'application_seal.json', [RUN/'applications.json'] + sorted((RUN/'materialized').glob('*.json')))


def execute():
    verify(); audit = read(RUN/'execution_review.json')
    assert audit['approved'] is True
    env = {k: v for k, v in os.environ.items() if k.upper() in ('SYSTEMROOT', 'WINDIR', 'PATH', 'PATHEXT', 'TEMP', 'TMP')}
    env['NODE_ENV'] = 'development'
    for row in read(RUN/'blind_packet.json'):
        oid = row['output_id']; candidate = RUN/f'materialized/{oid}.json'; dest = RUN/f'evaluation/{oid}.json'
        if dest.exists(): continue  # first cached evaluation only
        assert audit['candidate_sha256'][oid] == sha(candidate)
        materialized = read(candidate)
        if materialized['status'] != 'ready':
            write(dest, {'status': 'delivery_unresolved', 'types': None, 'runtime': None}); continue
        try:
            proc = subprocess.run([shutil.which('node'), str(BASE/'evaluate.cjs'), row['task_id'], str(candidate), '--reviewed'],
                                  cwd=BASE, env=env, capture_output=True, text=True, encoding='utf-8', timeout=40)
            result = json.loads(proc.stdout)
            result['process_returncode'] = proc.returncode
            result['process_stderr'] = proc.stderr
        except subprocess.TimeoutExpired:
            result = {'status': 'timeout', 'types': None, 'runtime': None, 'notice': 'Timed out before complete evaluator result; not a success.'}
        except (json.JSONDecodeError, OSError) as exc:
            result = {'status': 'evaluation_error', 'types': None, 'runtime': None, 'error': str(exc)}
        write(dest, result)
        print(oid, result.get('status', 'evaluated'), flush=True)


def validate_review(rows, packet):
    by = {r['output_id']: r for r in packet}
    assert len(rows) == len(by) and {r['output_id'] for r in rows} == set(by)
    for row in rows:
        assert set(row['dimensions']) == set(PROFILES['P1'])
        for value in row['dimensions'].values():
            assert type(value['match']) is bool and isinstance(value['reason'], str) and value['reason'].strip()
            assert isinstance(value['answer_quotes'], list)
            for quote in value['answer_quotes']:
                assert isinstance(quote, str) and quote and quote in by[row['output_id']]['answer']
        assert isinstance(row['unsupported_execution_claims'], list) and isinstance(row['ambiguities'], list)
        for claim in row['unsupported_execution_claims']:
            assert claim['quote'] in by[row['output_id']]['answer'] and claim['reason'].strip()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('command', choices=['prepare', 'freeze', 'verify', 'blind', 'materialize', 'execute'])
    globals()[parser.parse_args().command]()

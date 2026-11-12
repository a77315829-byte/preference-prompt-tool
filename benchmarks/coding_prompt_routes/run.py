"""Three fresh Codex agents on a fixed real React bug; no paid model API."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import time
import zipfile

from benchmarks.react_task_sync.prepare import TASK, COMMON
from benchmarks.react_task_sync.evaluate import timestamp
from coding_elicitation import build_adaptive_coding_elicitation
from coding_instructions import build_coding_instructions
from coding_work_trials import general_prompt

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'tmp/coding-prompt-routes-20261109'
DEST = Path(__file__).parent / 'results/2026-11-09'
BASE = '3b6b550418dcaf8cb184563f699bdc727f5dd54b'
CHECKS = ROOT / 'benchmarks/react_task_sync/acceptance.test.mjs'
COMPONENT = 'frontend/src/features/coding-instructions/CodingTrialPanel.jsx'
ASSIGNMENT = {'arm_a': 'general', 'arm_b': 'direct_settings', 'arm_c': 'four_example_choices'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def prepare():
    RUN.mkdir(parents=True, exist_ok=False)
    profile = {'language': 'JavaScript', 'framework': 'React', 'extra': '', 'preferences': {
        'explanation': 'brief', 'comments': 'essential', 'structure': 'compact', 'output': 'changes'}}
    bank = build_adaptive_coding_elicitation(profile)
    rows = [{'id': pair['id'], 'value': profile['preferences'][pair['axis']]} for pair in bank['pairs'][:4]]
    elicited = {**profile, 'comparison': {'version': 4, 'example': bank['source'], 'rounds': rows,
                                       'choices': dict(profile['preferences'])}}
    direct = build_coding_instructions(profile)
    selected = build_coding_instructions(elicited)
    prompts = {'general': general_prompt(profile, []), 'direct_settings': direct['prompt'],
               'four_example_choices': selected['prompt']}
    instructions = COMMON + '\nnode_modules 안에 임시 파일·컴파일 결과도 쓰지 마세요. 필요한 파일은 작업 폴더 안에 새로 만드세요.\n'
    archive = subprocess.check_output(['git', 'archive', '--format=zip', BASE, 'frontend', 'CLAUDE.md', 'AGENTS.md'], cwd=ROOT)
    manifest = {'baseline_commit': BASE, 'prompt_builder_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'frozen_at_utc': datetime.now(timezone.utc).isoformat(), 'assignment': ASSIGNMENT,
        'acceptance_sha256': digest(CHECKS.read_bytes().replace(b'\r\n', b'\n')), 'profile': profile,
        'elicited_profile': selected['profile'], 'task': TASK, 'common_execution': instructions, 'arms': {},
        'preference_rules_identical': direct['prompt'].split('\n- ', 1)[1] == selected['prompt'].split('\n- ', 1)[1],
        'limitations': ['One previously used real JSX bug, one run per condition; not a new task sample.',
            'Experimenter-fixed identical preferences, not a human elicitation study or independent human checklist.',
            'Direct and example conditions differ in provenance wording, not their four preference rules.',
            'Agent time excludes initial human preference setup and is not human editing time.',
            'Same host and instruction-based separation, not an OS sandbox between arms.'],
        'paid_api_requests': 0, 'human_edit_seconds': None, 'human_preference': None}
    for arm, condition in ASSIGNMENT.items():
        dest = RUN / arm
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            bundle.extractall(dest)
        payload = prompts[condition] + '\n\n## 과제\n' + TASK + '\n## 실행 규칙\n' + instructions
        (dest / 'TASK.txt').write_text(payload, encoding='utf-8')
        manifest['arms'][arm] = {'condition': condition, 'prompt': prompts[condition], 'payload_sha256': digest(payload.encode()),
                                 'component_sha256': digest((dest / COMPONENT).read_bytes())}
    save(RUN / 'manifest.json', manifest)
    print(json.dumps({'directory': str(RUN), 'same_initial_code': len({x['component_sha256'] for x in manifest['arms'].values()}) == 1,
                      'preference_rules_identical': manifest['preference_rules_identical']}))


def evaluate(arm, reviewed):
    if not reviewed:
        raise SystemExit('Review candidate code before execution and pass --reviewed')
    manifest = json.loads((RUN / 'manifest.json').read_text(encoding='utf-8'))
    if digest(CHECKS.read_bytes().replace(b'\r\n', b'\n')) != manifest['acceptance_sha256']:
        raise SystemExit('Fixed acceptance checks changed')
    output = RUN / f'{arm}-evaluation.json'
    if output.exists():
        raise SystemExit('Preserve cached evaluation; do not silently rerun')
    work = RUN / ('arm_a' if arm == 'baseline' else arm)
    started = finished = None
    if arm != 'baseline':
        started = json.loads((work / 'started.json').read_text(encoding='utf-8-sig'))
        finished = json.loads((work / 'finished.json').read_text(encoding='utf-8-sig'))
    env = dict(os.environ, PPT_REACT_BENCH_TARGET=str(work / 'frontend'))
    tick = time.perf_counter()
    process = subprocess.run(['node', '--test', '--test-reporter=tap', str(CHECKS)], cwd=ROOT, env=env,
                             capture_output=True, text=True, encoding='utf-8', timeout=180)
    log = process.stdout + process.stderr
    (RUN / f'{arm}.tap').write_text(log, encoding='utf-8')
    cases = [{'name': name, 'passed': status == 'ok'} for status, name in
             re.findall(r'^(ok|not ok) \d+ - (R\d+[^\r\n]+)', log, flags=re.MULTILINE)]
    seconds = None if started is None else round((datetime.fromisoformat(timestamp(finished).replace('Z', '+00:00')) -
        datetime.fromisoformat(timestamp(started).replace('Z', '+00:00'))).total_seconds(), 3)
    result = {'arm': arm, 'agent_work_seconds': seconds, 'evaluation_seconds': round(time.perf_counter() - tick, 3),
        'exit_code': process.returncode, 'cases': cases, 'passed': sum(case['passed'] for case in cases), 'total': len(cases),
        'component_sha256': digest((work / COMPONENT).read_bytes()), 'started': started, 'finished': finished}
    if len(cases) != 9:
        result['evaluation_error'] = 'Not all fixed tests ran; no functional accuracy score'
    save(output, result)
    print(json.dumps({key: result[key] for key in ('arm', 'agent_work_seconds', 'passed', 'total', 'exit_code')}))


def collect():
    manifest = json.loads((RUN / 'manifest.json').read_text(encoding='utf-8'))
    DEST.mkdir(parents=True, exist_ok=True)
    archive = subprocess.check_output(['git', 'archive', '--format=zip', BASE, 'frontend'], cwd=ROOT)
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        original = {name: bundle.read(name) for name in bundle.namelist() if not name.endswith('/')}
    results = []
    for arm, condition in ASSIGNMENT.items():
        result = json.loads((RUN / f'{arm}-evaluation.json').read_text(encoding='utf-8'))
        work = RUN / arm
        if digest((work / COMPONENT).read_bytes()) != result['component_sha256']:
            raise SystemExit('Candidate changed after evaluation')
        changes = [name for name, data in original.items() if (work / name).read_bytes() != data]
        if changes != [COMPONENT]:
            raise SystemExit(f'Review unexpected tracked changes before collecting: {arm}: {changes}')
        patch = ''.join(difflib.unified_diff(original[COMPONENT].decode('utf-8').replace('\r\n', '\n').splitlines(True), (work / COMPONENT).read_text(encoding='utf-8').splitlines(True),
            fromfile='a/' + COMPONENT, tofile='b/' + COMPONENT))
        (DEST / f'{arm}.patch').write_text(patch, encoding='utf-8')
        (DEST / f'{arm}-prompt.txt').write_text((work / 'TASK.txt').read_text(encoding='utf-8'), encoding='utf-8')
        (DEST / f'{arm}.tap').write_text((RUN / f'{arm}.tap').read_text(encoding='utf-8').replace(str(ROOT), '$REPO'), encoding='utf-8')
        added_tests = []
        for candidate in (work / 'frontend/src').rglob('*.test.js'):
            name = candidate.relative_to(work).as_posix()
            if name not in original:
                target = DEST / f'{arm}-self-tests' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(candidate.read_bytes())
                added_tests.append(name)
        lines = patch.splitlines()
        results.append({**result, 'condition': condition, 'changed_files': changes,
                        'self_authored_tests': added_tests,
                        'added_lines': sum(line.startswith('+') and not line.startswith('+++') for line in lines),
                        'removed_lines': sum(line.startswith('-') and not line.startswith('---') for line in lines)})
    baseline_log = (RUN / 'baseline.tap').read_text(encoding='utf-8').replace(str(ROOT), '$REPO')
    (DEST / 'baseline.tap').write_text('\n'.join(line.rstrip() for line in baseline_log.splitlines()) + '\n', encoding='utf-8')
    save(DEST / 'protocol.json', manifest)
    save(DEST / 'summary.json', {'runs': results, 'baseline': json.loads((RUN / 'baseline-evaluation.json').read_text(encoding='utf-8')),
        'paid_api_requests': 0, 'human_edit_seconds': None, 'human_preference': None, 'limitations': manifest['limitations']})
    print(json.dumps({'results': str(DEST)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'baseline', 'arm_a', 'arm_b', 'arm_c', 'collect'])
    parser.add_argument('--reviewed', action='store_true')
    args = parser.parse_args()
    if args.action == 'prepare': prepare()
    elif args.action == 'collect': collect()
    else: evaluate(args.action, args.reviewed)

"""WBS v3.2 자료: v3.1의 16개 작업·일정·상태·선행을 그대로 두고 근거 두 가지를 붙인다.

1. 비고: 진행·보완 중인 작업에 남은 일을 적는다. 문구는 상세 WBS v1.0(wbs.json)의
   미완료 활동에 연결하고, 날짜는 그 활동의 계획일에서 계산한다.
2. GitHub 최초 커밋: 작업을 대표하는 경로가 기준 커밋 이력에 처음 추가된 날짜를 git에서 읽는다.

일정(계획안)과 상태는 바꾸지 않는다. 바뀌었다면 실패한다.
"""
from pathlib import Path
import json
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CODE_BASIS = 'cfd1fe44623b46ca8bf94da059c91e72945de517'  # microstone, 2026-11-12

# 작업 ID -> [(표시 이름, 저장소 경로)]. 코드·문서로 확인할 수 있는 작업만 적는다.
EVIDENCE = {
    '2.3': [('설계서', 'docs/system-design')],
    '3.1': [('엔진', 'engine'), ('요약 화면', 'frontend/src/features/comparison')],
    '3.2': [('React 비교', 'domains/coding.yaml'), ('답변 방식', 'coding_instructions.py')],
    '3.3': [('계정', 'auth.py'), ('보관함', 'personal_prompts.py')],
    '3.4': [('팀', 'team.py'), ('인수인계', 'handoffs.py')],
    '4.1': [('실험', 'experiments'), ('벤치마크', 'benchmarks')],
    '4.2': [('테스트', 'tests'), ('CI', '.github/workflows/tests.yml')],
}

# 작업 ID -> (비고 문구, 근거가 되는 v1.0 미완료 활동 ID). 활동이 있으면 계획일을 뒤에 붙인다.
NOTES = {
    '1.2': ('상위 UC 24개 확정. 하위 79개 상세화는 2.3', []),
    '1.3': ('전 기간 관리. 범위·일정 합의, 추적표 검토', ['1.1.6', '5.2.1']),
    '2.1': ('요약 v2·세션 정책 설계 변경 반영', ['2.1.9']),
    '2.2': ('요약 v2·세션 정책 설계 변경 반영', ['2.1.9']),
    '2.3': ('v1.1: 하위 UC 79개 상세화. 다음 판본', ['2.1.9']),
    '3.1': ('구현 완료. 새 원문 출력 검증은 4.1', []),
    '3.2': ('한·영 React 지침 의미 정렬', ['3.1.10']),
    '3.3': ('비교 세션 접근 정책 확정·구현', ['1.1.5', '4.1.6']),
    '4.1': ('새 원문·과제 고정, 요약 v2·React 재비교', ['4.2.5', '4.2.6', '4.2.7', '4.2.8']),
    '4.2': ('세션 접근 통합 검사, 변경분 전체 회귀', ['4.1.7', '4.1.8']),
}

FOOTNOTES = [
    '일정: 기존 학기 계획과 후속 계획을 묶은 일정안입니다. 과거 실제 시작·종료일을 뜻하지 않습니다.',
    'GitHub 최초 커밋: microstone 기준 커밋 이력에 해당 경로가 처음 추가된 날짜입니다. 작업의 시작·완료일이 아니며 계획 일정과 다를 수 있습니다.',
    '진행률: 완료 100%·예정 0%만 표시했습니다. 진행·보완 작업과 단계 요약의 비율은 미산정(-)입니다. 1단계 기간은 전 기간 관리 작업 1.3을 포함합니다.',
    '선행 관계: SS = 시작 후 병행 / 표기 없음 = 완료 후 시작. 4.1은 구현 전 엔진 단계 실험부터 이어지므로 구현 작업을 선행으로 두지 않았습니다.',
    '비고: 남은 일은 상세 WBS v1.0의 미완료 활동과 그 계획일입니다. 3.3의 세션 접근 정책은 요약·React 비교 세션(UC-02·03)에 적용하는 계정 격리 작업이며, 3.1의 완료는 요약 기능 구현 범위입니다.',
]


def first_commit_date(path):
    """기준 커밋 이력에서 path가 처음 추가된 작성일(YYYY-MM-DD)."""
    result = subprocess.run(
        ['git', 'log', CODE_BASIS, '--diff-filter=A', '--format=%as', '--', path],
        cwd=ROOT, capture_output=True, text=True, check=True)
    dates = result.stdout.split()
    assert dates, f'기준 커밋 이력에 없는 경로: {path}'
    return dates[-1]


def date_range(activities):
    """활동들의 계획 시작~종료를 '11/13~17' 같은 짧은 표기로 만든다."""
    start = min(a['plan_start'] for a in activities)
    end = max(a['plan_end'] for a in activities)
    first = f'{start[5:7]}/{start[8:]}'
    if start == end:
        return first
    if start[:7] == end[:7]:
        return f'{first}~{end[8:]}'
    return f'{first}~{end[5:7]}/{end[8:]}'


def main():
    previous = json.loads((HERE / 'wbs-v3.1.json').read_text(encoding='utf-8'))
    catalog = json.loads((ROOT / 'docs/system-design/usecase-catalog.json').read_text(encoding='utf-8'))
    detailed = {t['id']: t for t in json.loads((HERE / 'wbs.json').read_text(encoding='utf-8'))['tasks']}

    data = dict(previous)
    data.update(version='3.2', date='2026-11-13', status_date='2026-11-12', code_basis=CODE_BASIS,
                usecases=catalog['usecases'], notes=FOOTNOTES)
    data['groups'] = [dict(g, uc_scope='-') for g in previous['groups']]

    tasks = []
    for old in previous['tasks']:
        task = dict(old)
        text, activity_ids = NOTES.get(task['id'], ('', []))
        activities = [detailed[i] for i in activity_ids]
        pending = [a for a in activities if a['status'] != '완료 확인']
        assert len(pending) == len(activities), f'{task["id"]}: 이미 완료된 활동을 잔여로 인용함'
        if task['status'] == '완료':
            assert not pending, f'{task["id"]}: 완료 작업에 미완료 활동이 연결됨'
        if task['status'] in ('보완중', '진행중'):
            assert pending, f'{task["id"]}: 진행·보완 작업에 남은 일이 적혀 있지 않음'
        task['note'] = f'{text} ({date_range(pending)})' if pending else text
        task['note_activities'] = activity_ids
        task['github_first'] = [dict(label=label, path=path, date=first_commit_date(path))
                                for label, path in EVIDENCE.get(task['id'], [])]
        tasks.append(task)
    data['tasks'] = tasks

    kept = ('id', 'name', 'group', 'start', 'end', 'status', 'progress', 'predecessors', 'uc_scope')
    for old, new in zip(previous['tasks'], tasks):
        assert all(old[k] == new[k] for k in kept), f'{old["id"]}: v3.1의 일정·상태가 바뀜'
    known = {t['id'] for t in tasks}
    assert len(tasks) == 16 and len(data['groups']) == 5
    assert len(data['usecases']) == 24 and sum(len(u['children']) for u in data['usecases']) == 79
    assert all(u['wbs'] in known for u in data['usecases'])
    assert set(NOTES) <= known and set(EVIDENCE) <= known

    data['sources'] = previous['sources'] + ['docs/wbs/2026-11-12/wbs-v3.1.json',
                                             'docs/system-design/usecase-catalog.json',
                                             f'git log {CODE_BASIS[:7]} --diff-filter=A (GitHub 최초 커밋)']
    (HERE / 'wbs-v3.2.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('WBS 3.2: 5 phases / 16 activities; dates, status and dependencies unchanged from 3.1;',
          f'{sum(bool(t["note"]) for t in tasks)} notes, {sum(bool(t["github_first"]) for t in tasks)} tasks with commit evidence.')


if __name__ == '__main__':
    main()

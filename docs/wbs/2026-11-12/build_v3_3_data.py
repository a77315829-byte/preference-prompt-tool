"""WBS 3.3: preserve the plan, distinguish remaining work and add related UC links."""
from copy import deepcopy
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    previous = json.loads((HERE / 'wbs-v3.2.json').read_text(encoding='utf-8'))
    catalog = json.loads((ROOT / 'docs/system-design/usecase-catalog.json').read_text(encoding='utf-8'))
    data = deepcopy(previous)
    data.update(version='3.3', date='2026-11-13', design_version='1.2',
                usecases=catalog['usecases'], documentation_status_date='2026-11-13')
    data['repository_first_definition'] = (
        '기준 커밋 이력에서 해당 경로를 최초 추가한 커밋의 작성일. '
        'GitHub 업로드 시점이나 작업의 실제 시작·완료일을 뜻하지 않는다.')
    for task in data['tasks']:
        task['repository_first'] = task.pop('github_first')
        if task['id'] in ('2.1', '2.2', '2.3'):
            task['completed_documentation'] = '요약 v2의 길이 제한·상한/하한 충돌 처리 설명 반영'
            task['remaining_work'] = '비교 세션 접근·소유권·만료 정책 확정 후 설계·화면·명세 반영'
            task['note'] = ('요약 v2 문서 반영 완료. 세션 정책 확정 후 반영 (11/19~20)'
                            if task['id'] != '2.3' else
                            'UC·요약 v2 반영 완료. 세션 정책 확정 후 명세 갱신 (11/19~20)')
            task['note_activities_scope'] = '기존 2.1.9 중 세션 정책의 잔여 범위만 연결'
            task['documentation_evidence'] = ['docs/system-design/chapters/03-ui-design.md',
                                               'docs/system-design/chapters/04-processing-design.md']
        if task['id'] == '3.3':
            task['uc_scope'] = 'UC-01, 09~10, 19~24\n세션: UC-02·03'
            task['related_uc'] = ['UC-02', 'UC-03']
            task['requirements'] += ', NFR-01,05'
            task['note'] = '비교 세션 접근 정책 확정·구현 예정 (11/13~17)'
    data['notes'] = [
        '일정: 기존 계획안을 유지합니다. 제품 상태는 11/12, 문서 반영·UC 연결 보완은 11/13 확인 기준입니다.',
        '저장소 최초 추가일: 해당 경로를 최초 추가한 커밋의 작성일입니다. GitHub 업로드 시점이나 작업의 실제 시작·완료일이 아닙니다.',
        '진행률: 완료 100%·예정 0%만 표시합니다. 진행·보완·단계 요약은 미산정(-)입니다. 선행 SS는 시작 후 병행, 표기 없음은 완료 후 시작입니다.',
        '비고: 요약 v2의 길이·충돌 설명은 문서 반영 완료입니다. 2.1~2.3에는 세션 정책 확정 후 반영이 남고, 새 출력 검증은 4.1에서 진행합니다.',
        'UC 연결: 3.3은 UC-02·03의 세션 정책 보완 예정 작업입니다. 주 구현 3.1·공통 사용 3.2와 구별하며 현재 계정 격리가 완료됐다는 뜻이 아닙니다.'
    ]
    data['sources'] = [s.replace('GitHub 최초 커밋', '저장소 최초 추가일') for s in data['sources']]
    data['sources'] += ['docs/wbs/2026-11-12/wbs-v3.2.json',
                        'docs/system-design/chapters/03-ui-design.md',
                        'docs/system-design/chapters/04-processing-design.md']
    preserved = ('id', 'name', 'group', 'start', 'end', 'status', 'progress', 'predecessors')
    assert len(data['tasks']) == 16 and len(data['groups']) == 5
    for old, new in zip(previous['tasks'], data['tasks']):
        assert all(old[k] == new[k] for k in preserved), old['id']
        assert old['github_first'] == new['repository_first']
    assert len(data['usecases']) == 24 and sum(len(u['children']) for u in data['usecases']) == 79
    for u in data['usecases']:
        if u['id'] in ('UC-02', 'UC-03'):
            assert u['wbs'] == '3.1'
            assert any(x['id'] == '3.3' and x['role'] == '보완 예정' for x in u['related_wbs'])
    (HERE / 'wbs-v3.3.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print('v3.3: 16 tasks preserved; UC-02/03 related to planned WBS 3.3; documentation and pending work separated.')


if __name__ == '__main__':
    main()

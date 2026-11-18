"""WBS v3.4: preserve the v3.3 schedule/IDs; update only evidenced state."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
old = json.loads((HERE.parent / '2026-11-12/wbs-v3.3.json').read_text(encoding='utf-8'))
old.update(version='3.4', date='2026-11-18', status_date='2026-11-18',
           code_basis='0bbff8021717e22e2e9a204d70e02e0948803b76')
old['usecases'] = json.loads((ROOT / 'docs/system-design/usecase-catalog.json').read_text(encoding='utf-8'))['usecases']
changes = {
    '1.1': ('완료', '기존 범위 유지'),
    '1.2': ('완료', '24개 상위·79개 하위 UC 유지'),
    '1.3': ('진행중', '최종 제출 요건·팀 확인 대기'),
    '2.1': ('완료', '세션·저장·복구 정책 반영'),
    '2.2': ('완료', '조건 확인 지침 저장 흐름 반영'),
    '2.3': ('완료', '설계서 v1.3 발행·연결 갱신'),
    '3.1': ('완료', '충돌 확인 지침 별도 저장 구현'),
    '3.2': ('완료', 'React 한·영 v2 정렬'),
    '3.3': ('완료', '세션 격리·재사용·복구 보완'),
    '3.4': ('완료', '기존 팀 공유·인수인계 유지'),
    '4.1': ('완료', '6원문·8과제 재비교; 우위 미입증'),
    '4.2': ('완료', '로컬·CI·복구·화면 검사 완료'),
    '4.3': ('진행중', '잔여 오류 대응·인계 전 확인'),
    '5.1': ('진행중', '자동 시연 확보; 팀 리허설 대기'),
    '5.2': ('진행중', '최종 보고·발표 준비본 작성'),
    '5.3': ('예정', '제출 요건·팀 확인 후 인계'),
}
for task in old['tasks']:
    task['status'], task['note'] = changes[task['id']]
    task['progress'] = 1 if task['status'] == '완료' else (0 if task['status'] == '예정' else None)
for uc in old['usecases']:
    for related in uc.get('related_wbs', []):
        if related['id'] == '3.3' and related['role'] == '보완 예정':
            related['role'] = '세션 정책'
old['notes'] = [
    '일정은 v3.3의 계획안을 유지합니다. 선행 수행을 실제 계획일 변경 또는 공식 완료일로 해석하지 않습니다.',
    '완료는 현재 정의한 기술 범위 기준입니다. 진행·보완 작업의 진행률은 추정하지 않고 빈칸으로 둡니다.',
    '최신 출력 비교: 요약 조건 6/6·핵심 사실 17/18, React 타입 8/8·동작 40/40·세 축 8/8 (수동·제품 각각).',
    '실사용자 편의·만족·시간 절감은 미측정입니다. 팀원 PC 리허설과 공식 제출 요건 확인은 남아 있습니다.',
    '근거: docs/verification/2026-11-17-readiness/ 및 benchmarks/weekly_validation_2026_11_17/.'
]
old['status_basis'] = '2026-11-17 검증과 2026-11-18 문서 발행. 코드 기준 커밋과 문서 발행 커밋은 구분.'
(HERE / 'wbs-v3.4.json').write_text(json.dumps(old, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
print('Preserved 5 phases, 16 task IDs/names/schedules and 24 parent UC mappings.')

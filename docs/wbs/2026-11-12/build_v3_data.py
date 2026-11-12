"""Course-report WBS: five phases, sixteen broad activities, two levels."""
from pathlib import Path
from datetime import date,timedelta
import json

HERE=Path(__file__).resolve().parent
GROUPS=[('1','기획·분석','프로젝트 기획 및 요구사항 분석'),('2','설계','시스템 및 화면 설계'),('3','구현','핵심 기능 구현'),('4','검증·보완','비교 검증 및 기능 보완'),('5','최종 정리','운영·시연 및 최종 제출')]
ROWS=[
 ('1.1','주제 및 프로젝트 범위 정의','공통',[],'09-11','09-24','완료'),
 ('1.2','요구사항·유즈케이스 정리','FR-01~16',[('1.1','FS')],'09-25','10-08','완료'),
 ('1.3','역할 분담·일정·진행 관리','공통',[],'09-11','12-18','진행중'),
 ('2.1','시스템·DB·API 설계','FR-01~16',[('1.2','SS')],'10-02','11-20','보완중'),
 ('2.2','UI/UX 및 화면 흐름 설계','FR-01~16',[('1.2','SS')],'10-02','11-20','보완중'),
 ('2.3','분석·설계서 작성 및 수정','공통',[('2.1','SS'),('2.2','SS')],'11-06','11-20','보완중'),
 ('3.1','문서 요약 기능 구현','FR-02~03',[('2.1','SS'),('2.2','SS')],'10-09','11-12','완료'),
 ('3.2','코딩 도움·React 비교 구현','FR-04~06',[('2.1','SS'),('2.2','SS')],'10-09','11-16','보완중'),
 ('3.3','계정·지침 저장·재사용 구현','FR-01,07,12~16',[('2.1','SS')],'10-16','11-18','보완중'),
 ('3.4','팀 공유·인수인계 구현','FR-08~11',[('3.3','SS')],'10-16','11-12','완료'),
 ('4.1','요약·코딩 프롬프트 비교 검증','NFR-08',[('1.1','FS')],'09-25','11-19','진행중'),
 ('4.2','기능·권한·전체 회귀 검사','NFR-01~12',[('3.1','SS'),('3.4','SS')],'11-06','11-20','진행중'),
 ('4.3','잔여 오류 수정 및 재검사','NFR-12',[('4.2','SS')],'11-13','11-27','예정'),
 ('5.1','운영 점검·시연 안정화','공통',[('4.2','SS'),('4.3','SS')],'11-20','12-04','예정'),
 ('5.2','최종 보고서·발표 자료 작성','공통',[('5.1','FS')],'12-05','12-14','예정'),
 ('5.3','최종 점검·제출·인계','공통',[('5.2','FS')],'12-15','12-18','예정'),
]

def main():
    tasks=[]
    for code,name,req,deps,start,end,status in ROWS:
        tasks.append(dict(id=code,level=2,group=code.split('.')[0],name=name,requirements=req,
            predecessors=[dict(id=i,type=t) for i,t in deps],start='2026-'+start,end='2026-'+end,status=status,
            progress=1 if status=='완료' else 0 if status=='예정' else None))
    byid={t['id']:t for t in tasks}
    for t in tasks:
        assert t['end']>=t['start']
        for dep in t['predecessors']:
            prior=byid[dep['id']]
            assert t['start']>=prior['end' if dep['type']=='FS' else 'start'],(t,dep)
    visited,stack=set(),set()
    def visit(code):
        assert code not in stack
        if code in visited:return
        stack.add(code)
        for dep in byid[code]['predecessors']:visit(dep['id'])
        stack.remove(code);visited.add(code)
    for code in byid:visit(code)
    groups=[]
    for code,phase,name in GROUPS:
        children=[t for t in tasks if t['group']==code]
        groups.append(dict(id=code,level=1,phase=phase,name=name,start=min(t['start'] for t in children),end=max(t['end'] for t in children),status='요약'))
    data=dict(version='3.0',date='2026-11-12',title='Revealed 프로젝트 WBS 및 간트차트',groups=groups,tasks=tasks,
        weeks=[(date(2026,9,11)+timedelta(weeks=i)).isoformat() for i in range(15)],
        notes=[
            '시작·종료일은 기존 학기 계획과 후속 계획을 주요 작업 단위로 묶은 일정안이며 실제 작업일이 아닙니다.',
            '상태는 11/12 확인 범위 기준입니다. 완료 100%, 예정 0%만 표시하고 진행·보완 작업과 요약 행의 진행률은 미산정으로 둡니다.',
            'SS는 선행 작업 시작 후 병행, 표기 없는 연결은 선행 작업 완료 후 시작입니다. 기능 구현 완료와 출력 효과 검증은 별도입니다.'],
        scope='요약·코딩 두 기능, 계정·재사용, 팀 협업, 검증, 운영·최종 제출을 포함. 실사용자 연구·공개 배포 실행·과거 Streamlit 정리는 별도 후속.',
        reference='사용자 제공 중간 보고서_C-3조 (1) (1).pdf, 31쪽: WBS + 간트차트',
        sources=['docs/weekly_reports/2026-11-06/build_report_v0_2.py','docs/weekly_reports/2026-11-13/build_report_v0_5.py','docs/verification/2026-11-12-summary-policy/','docs/wbs/2026-11-12/wbs.json'])
    (HERE/'wbs-v3.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print('5 phases, 16 activities; dependency IDs, cycles and schedule relations checked.')

if __name__=='__main__':main()

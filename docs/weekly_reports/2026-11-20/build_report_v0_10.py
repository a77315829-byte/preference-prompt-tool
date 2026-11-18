"""11/20 course report: 11/13-19 period, only evidence confirmed by 11/17.

Preserve the original course template, earlier reports and frozen experiments.
Bundled PDF dependencies only; no application or model API execution.
"""
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote
import hashlib
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / '2026-11-13'))
import build_report_v0_4 as layout
from pypdf import PdfReader, PdfWriter

VERSION = '0.10'
OUT = ROOT / 'output/pdf/Revealed_진행현황_주간보고서_v0.10.pdf'
COPY = ROOT / 'outputs/Revealed_설계서_v1.2_WBS_v3.3' / OUT.name
PREVIOUS = ROOT / 'output/pdf/Revealed_진행현황_주간보고서_v0.9.pdf'
QA = ROOT / 'tmp/weekly_2026_11_20/v0_10'
REPO = 'https://github.com/a77315829-byte/preference-prompt-tool'
PUBLISHED = '4b40d115141709f8aeb7840a301e02fc206c408a'
GRAY, MUTED, TEAL = layout.GRAY, layout.MUTED, layout.TEAL


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


WBS = read('docs/wbs/2026-11-12/wbs-v3.3.json')
STATUS = read('docs/wbs/2026-11-17/status.json')
CHECKS = read('docs/verification/2026-11-17/results/validation.json')
SCORES = read('benchmarks/weekly_validation_2026_11_17/scores.json')
ACTIVE = {'1.3', '2.1', '2.2', '2.3', '3.2', '3.3', '4.1', '4.2', '4.3'}


class ReportPage(layout.ReportPage):
    def footer(self, number, backup=False, old_number=None):
        self.rect(0, 514, 780, 26, '#FFFFFF')
        self.text('Revealed | 2026.11.20 보고 | 실적 11/13~11/19 | 확인 기준 11/17',
                  34, 520, 620, 8, MUTED, maxh=13)
        self.text(f'v{VERSION}   {number}', 650, 518, 96, 9, MUTED, maxh=15, align=2)


def cover():
    original = PdfReader(layout.TEMPLATE).pages[0]
    p = ReportPage()
    p.text('선호 기반 프롬프트 자동 생성 도구', 35, 192, 463, 20, '#FFFFFF', True, maxh=32)
    p.text('팀 Revealed  ·  윤정우 · 고차원', 35, 228, 465, 14, '#FFFFFF', maxh=24)
    p.text('2026.11.20 보고  |  11주차  |  v0.10', 35, 379, 710, 15, bold=True, maxh=25)
    p.text('실적: 11/13 ~ 11/19   |   다음 계획: 11/20 ~ 11/26', 35, 412, 710, 13, MUTED, maxh=22)
    p.text('작성·실적 확인: 11/17까지  ·  본 보고 1~3쪽  ·  이번 주 상세 근거는 백업 4~11쪽',
           35, 443, 710, 10.5, MUTED, maxh=18)
    original.merge_page(p.finish())
    return original


def wbs():
    p = ReportPage()
    p.header('1. 프로젝트 일정 - WBS',
             '학기 전체 15주  |  실적 11/13~11/19 · 차주 11/20~11/26  |  WBS v3.3의 16개 작업 유지', 2)
    grid_x, cw, y0, rh = 345, 401/15, 151, 19
    p.rect(34, 111, 712, 40, GRAY)
    for x, width, label in [(34,35,'단계'),(69,31,'ID'),(100,202,'작업·산출물'),(302,43,'담당*')]:
        p.text(label, x+2, 122, width-4, 9.2, '#FFFFFF', True, maxh=17, align=1)
    p.rect(grid_x+10*cw, 111, cw, 40, '#B54A2F')
    for i, day in enumerate(layout.WEEKS):
        p.text(f'{i+1}주', grid_x+i*cw, 116, cw, 8.9, '#FFFFFF', True, maxh=15, align=1)
        p.text(day.strftime('%m/%d'), grid_x+i*cw, 135, cw, 7.5, '#FFFFFF', maxh=12, align=1)
    phases = {'1':'분석','2':'설계','3':'구현','4':'검증','5':'정리'}
    for i, task in enumerate(WBS['tasks']):
        y = y0+i*rh
        p.rect(34, y, 712, rh, '#F1F4F5' if i%2 else '#FFFFFF')
        p.rect(grid_x+10*cw, y, cw, rh, '#FFF0D9')
        owner = '윤정우' if task['group'] in ('2','3') else '공동'
        p.text(phases[task['group']], 36, y+4, 31, 8.1, maxh=13, align=1)
        p.text(task['id'], 71, y+4, 27, 8.4, maxh=13, align=1)
        p.text(task['name'], 104, y+4, 194, 8.7, maxh=13)
        p.text(owner, 304, y+4, 39, 8.1, maxh=13, align=1)
        start, end = date.fromisoformat(task['start']), date.fromisoformat(task['end'])
        for week, day in enumerate(layout.WEEKS):
            if start <= day+timedelta(days=6) and end >= day:
                p.rect(grid_x+week*cw+3, y+5, cw-6, 9, '#E5EAEE', '#8A9EAD')
        if task['id'] in ACTIVE:
            p.rect(grid_x+9*cw+5, y+6, cw-10, 7, TEAL)
        p.line(34, y+rh, 746, y+rh, '#DCE1E3', .5)
    for x in [34,69,100,302]+[grid_x+i*cw for i in range(16)]:
        p.line(x, y0, x, y0+16*rh, '#DAE1E4', .5)
    for x, color, label in [(35,'#E5EAEE','학기 계획'),(180,TEAL,'이번 주 활동 확인'),(408,'#FFF0D9','11/20 보고 위치')]:
        p.rect(x, 468, 14, 9, color, '#8A9EAD')
        p.text(label, x+20, 464, 190, 9.6, maxh=17)
    p.note('*담당은 기존 팀 계획안. 초록은 11/17까지 확인한 활동이며 전체 작업 완료율이 아니다.<br/>'
           '실적은 10주차 칸, 발표일은 11주차로 표시. 다음 단계는 잔여 오류 정리와 운영·시연 안정화.', 485)
    return p.finish()


def weekly():
    p = ReportPage(); p.header('2. 프로젝트 진행현황', '', 3)
    for x, label, color in [(34,'금주 실적 (11/13 ~ 11/19)','#808080'),(390,'차주 계획 (11/20 ~ 11/26)',GRAY)]:
        p.rect(x,84,356,32,color)
        p.text(label,x+9,89,338,13,'#FFFFFF',True,maxh=21,align=1)
    for x in [34,335,390,691,746]: p.line(x,116,x,400,'#C7CDD0',.7)
    for x in [34,390,746]: p.line(x,400,x,494,'#C7CDD0',.7)
    left = [
        ('기능 개선','React 한·영 지침 의미·필수 타입 예외 정렬<br/>이전 저장 지침 인식·로그인 후 제목 유지','11/17'),
        ('프롬프트 검증','새 요약 6원문·React 8과제 수동/제품 비교<br/>조건·내용·타입·동작 분리, 이번 표본 동률','11/17'),
        ('팀 공유·권한 보완','비교 세션의 계정·브라우저 소유권 적용<br/>만료·로그아웃 후 원문·결과 접근 차단','11/17'),
        ('분석·설계서 작성','세션 정책·새 검증 결과를 설계서에 반영<br/>UC·WBS 진행 상태·최종 완료 기준 갱신','11/17'),
    ]
    right = [
        ('실행 환경·시연 준비 (공동)','새 환경 설치·실행 안내 확인<br/>시연용 합성 계정·자료와 절차 준비','~11/22'),
        ('복구·접근 경계 점검 (공동)','저장 자료 백업·복원·재시작 점검<br/>로그아웃·만료·권한 거절 시나리오 확인','~11/24'),
        ('시연·잔여 오류 수정 (공동)','요약 설정→저장→새 작업 재사용 시연<br/>코딩 두 기능 확인·발견 오류 재검사','~11/25'),
        ('문서·공유 자료 정리 (공동)','변경분 GitHub 반영 후 자동 검사 확인<br/>시연 근거·설계/WBS·최종 제출 목록 정리','~11/26'),
    ]
    for x, items in [(34,left),(390,right)]:
        for i,(title,body,day) in enumerate(items):
            y=124+i*68
            p.rect(x+9,y+6,3.5,3.5,'#111111')
            p.text(title,x+19,y,277,11.5,bold=True,maxh=19)
            p.text(body,x+19,y+22,277,10.1,maxh=33)
            p.text(day,x+304,y+15,48,8.8,maxh=28,align=1)
    for x,title in [(34,'주요 이슈 및 의사결정 사항'),(390,'프로젝트 요청 사항')]:
        p.rect(x,400,356,30,'#EEEEEE')
        p.text(title,x+8,406,340,11.7,bold=True,maxh=20,align=1)
    for y in [400,430,494]: p.line(34,y,746,y,'#C7CDD0',1.5 if y==494 else .7)
    return p.finish()


def backup_index():
    p=ReportPage(); p.header('[Backup]', '이번 주 변경·새 검증과 다음 계획  |  질문 시 해당 쪽 확인',4)
    items=[('5쪽  React 지침과 이전 저장본 호환','한·영 의미·파일 분리·타입 예외를 맞추고 기존 지침을 보존'),
           ('6쪽  비교 세션 접근·만료 정책','계정·익명 브라우저 구분, 로그인 승계와 만료·로그아웃 정리'),
           ('7~8쪽  새 요약 원문·React 과제 검증','수동/제품 첫 응답 28개, 두 독립 검토, 조건과 내용·동작 분리'),
           ('9쪽  기술 검증과 설계·WBS 반영','최신 로컬 회귀·브라우저 확인, 수정된 UC·API·화면 설명'),
           ('10쪽  다음 주 완료 기준과 최종 범위','11/20~11/26 운영·시연 준비, 이후 최종 보고·발표·인계'),
           ('11쪽  GitHub와 분석·설계서 위치','게시된 공유본과 이번 주 로컬 개정 원고의 상태를 구분')]
    for i,(title,body) in enumerate(items):
        y=118+i*55
        p.rect(36,y+7,4,4,'#111111')
        p.text(title,51,y,694,13,bold=True,maxh=22)
        p.text(body,51,y+25,694,10.7,MUTED,maxh=19)
    p.note('실적 기간 11/13~11/19 중 11/17까지 확인한 결과만 포함. 11/18~19의 예정 작업을 완료로 쓰지 않았다.<br/>'
           '이미 발표한 이전 실험·기능 소개는 반복 수록하지 않았다. 사람의 편의성·시간 절감은 미측정이다.',465)
    return p.finish()


def react_changes():
    p=ReportPage(); p.header('[Backup] React 지침·저장본 호환 개선', '11/17  |  React 코드 스타일 3축 지침 v2  |  기존 AI 답변 방식 4항목 기능 유지',5)
    p.table(['개선 항목','이번 주 반영 내용','확인·보존 기준'],[
        ['파일 구성','한 파일은 TSX 하나, 별도 CSS 없음.<br/>역할별 분리는 스타일 또는 상태 로직을 분리.','불필요한 하위 컴포넌트와<br/>타입 전용 파일을 강제하지 않음.'],
        ['타입 예외','추론 가능한 타입은 반복하지 않되 빈 배열·null·<br/>유니언·CSS·Props·이벤트의 필요한 타입 허용.','한국어·영어의 의미를 맞춤.<br/>실제 생성 검증은 영어 기준.'],
        ['기능 우선','스타일보다 기능 요구를 우선하도록 정렬.<br/>요청한 데이터·문구·입출력과 접근성 유지.','임의 기능·라이브러리 추가 금지.<br/>8조합의 한·영 지침 검사.'],
        ['이전 저장본','기존 기본 생성문 전체와 일치하면 선택을 인식.<br/>새 조합을 요청할 때 현재 지침으로 미리 보기.','원본 저장 지침은 그대로 유지.<br/>직접 수정한 문장은 추측하지 않음.'],
    ],[125,357,230],y=116,heights=[70]*4,size=10.2)
    p.text('로그인 전환 시 저장 제목이 사라지던 문제도 수정해, 익명 비교 결과의 저장 흐름을 유지했습니다.',
           35,442,710,10.7,bold=True,maxh=21)
    p.note('새 경로: domains/coding/v2.yaml  |  이전 coding.yaml·고정 실험·저장 본문 보존.<br/>'
           '근거: docs/history/2026-11-17_weekly_completion.md',478)
    return p.finish()


def session_policy():
    p=ReportPage(); p.header('[Backup] 비교 세션 접근·만료 보완', '11/17  |  비교 원문·후보·결과의 임시 보관 정책  |  기존 팀 공유 권한과 함께 적용',6)
    p.table(['상황','구현한 동작','확인한 범위'],[
        ['다른 계정·브라우저','세션 ID만 알아서는 조회·선택·되돌리기·<br/>최적화·팀 반영에 접근할 수 없음.','두 계정 / 두 익명 브라우저.<br/>공통 404와 원문 비노출 확인.'],
        ['로그인 전환','같은 익명 브라우저가 로그인하면 비교를 승계.<br/>다른 계정 전환은 이전 비교를 폐기.','익명 선택·저장 제목 유지.<br/>이전 쿠키 재사용 거절.'],
        ['만료·로그아웃','생성 후 기본 12시간의 고정 만료.<br/>만료·로그아웃에는 원문·결과·복귀 정보 정리.','매 요청과 정확한 만료 경계 확인.<br/>화면 복귀·자동 만료 정리.'],
        ['늦은 응답·일시 장애','계산 중 로그아웃되면 늦은 결과를 반영하지 않음.<br/>일시 서버 오류에서는 진행 중 선택을 유지.','선택·최적화 결과 재생성 차단.<br/>401/403/404와 500 처리 구분.'],
    ],[125,357,230],y=116,heights=[70]*4,size=10.2)
    p.text('비교 원문을 영구 저장하도록 바꾸지 않았으며, 장기 재사용은 사용자가 지침을 명시적으로 저장합니다.',
           35,442,710,10.6,bold=True,maxh=21)
    p.note('브라우저 시연 검사는 합성 계정·임시 DB·36초 TTL로 실행. 공개 서비스 전체의 보안 인증은 아니다.<br/>'
           '근거: docs/verification/2026-11-17/README.md',478)
    return p.finish()


def summary_results():
    p=ReportPage(); p.header('[Backup] 새 요약 원문: 조건·내용 보존', '11/17  |  미사용 MACSum 영어 원문 6개  |  강한 수동 지침 vs 현재 제품 지침',7)
    p.text('같은 원문·확정 조건·보존 대상을 주고, 독립 생성자의 첫 응답을 비교했습니다.',35,115,710,12,bold=True,maxh=21)
    p.table(['분리 지표','수동','제품'],[
        ['분량·표현 조건 동시 준수','6/6','6/6'],
        ['핵심 사실 보존','17/18','17/18'],
        ['선택 문장의 정보 보존','17/18','17/18'],
        ['전체 보존을 요청한 사례의 의무 충족','5/5','5/5'],
        ['사실 오류로 판정된 응답','0/6','0/6'],
    ],[352,180,180],y=151,heights=[33]*5,size=11)
    p.text('두 방식 동률. 양쪽 모두 일부 생략을 허용한 같은 사례에서 정보 1개를 생략했습니다.',
           35,367,710,11.3,bold=True,maxh=21)
    p.text('• 생성 전 원문·조건·판정 기준 고정. 생성자와 다른 독립 AI 검토자 2명의 주요 판정이 같았습니다.<br/>'
           '• 누락은 17/18에 포함하되, 명시적으로 허용한 생략을 전체 보존 의무 위반으로 세지 않았습니다.<br/>'
           '• 해석의 경계와 부수 정보 생략도 기록했습니다. 원문 세부 정보 전체의 완전 보존율은 아닙니다.',
           35,407,710,10.4,maxh=57)
    p.note('18은 6원문 × 사전 지정 핵심 사실 3개. 영어 소표본·AI 의미 검토이며 공식 MACSum 전체 점수가 아니다.<br/>'
           '근거: benchmarks/weekly_validation_2026_11_17/README.md · scores.json',478)
    return p.finish()


def coding_results():
    p=ReportPage(); p.header('[Backup] 새 React 과제: 타입·동작·스타일', '11/17  |  새 합성 과제 8개 × 수동/제품  |  첫 응답 16개, 3축의 8조합',8)
    p.table(['분리 지표','수동','제품'],[
        ['응답 코드를 보충·수정 없이 적용','8/8','8/8'],
        ['strict 타입 검사','8/8','8/8'],
        ['실제 React/JSDOM 동작 검사','40/40','40/40'],
        ['구성·스타일 관리·타입 각각 일치','각 8/8','각 8/8'],
        ['세 스타일 축 동시 일치','8/8','8/8'],
    ],[352,180,180],y=116,heights=[38]*5,size=11)
    p.text('기능·스타일 모두 이번 과제를 통과했지만, 수동 프롬프트보다 우수하다는 결과는 아닙니다.',
           35,367,710,11.3,bold=True,maxh=21)
    p.text('• 과제당 이름 붙은 동작 검사 5개. 정답 8개 통과·오동작 변이 8개 검출 후 평가기를 고정했습니다.<br/>'
           '• 실행 전 코드 안전 검사, 두 독립 익명 검토자의 스타일 판정과 원문 인용을 보존했습니다.<br/>'
           '• 제품 설명 1개에 일본어 한 단어가 섞인 문제는 코드 스타일 점수와 별도로 기록했습니다.',
           35,407,710,10.4,maxh=57)
    p.note('유료 API 없이 Codex 보조 에이전트 사용. 실제 사용자의 선호 추정·수정 시간·팀 채택은 미측정.<br/>'
           '근거: benchmarks/weekly_validation_2026_11_17/README.md · evaluation/ · reviews/',478)
    return p.finish()


def verification_design():
    p=ReportPage(); p.header('[Backup] 기술 검증·설계·WBS 반영', '11/17  |  변경 후 전체 로컬 검사  |  설계서 개정 원고와 이전 발행 PDF 구분',9)
    p.table(['영역','이번 주 확인·갱신 결과','남은 범위·주의'],[
        ['백엔드 회귀','Python 1,433개 통과, 실패 0.<br/>세션 소유권·만료·구버전 지침 호환 확인.','Windows 심볼릭 링크 1개 건너뜀.<br/>실제 모델 API 검사 16개 제외.'],
        ['프론트·브라우저','프론트 136개·Chromium 6시나리오 통과.<br/>빌드 성공, 페이지 오류·외부 요청 0.','기존 큰 번들 경고 유지.<br/>공개 배포 전체 점검과는 구분.'],
        ['분석·설계서','2·3·6·7·8장에 세션 정책·API·화면을 반영.<br/>9장에 새 요약·React 검증과 한계 추가.','개정 원고 반영 완료.<br/>발행 PDF v1.2는 이전 스냅샷.'],
        ['UC·WBS·완료 기준','UC-02·03과 WBS 3.1/3.2/3.3 연결.<br/>5단계·16작업 유지, 11/17 진행 상태 기록.','작업 이름·일정·ID 유지.<br/>최종 시연·제출 단계는 예정.'],
    ],[125,357,230],y=116,heights=[70]*4,size=10.2)
    p.text('지난주 계획의 지침 정렬·세션 보완·새 출력 비교·회귀/문서 갱신을 이번 범위에서 완료했습니다.',
           35,442,710,10.6,bold=True,maxh=21)
    p.note('기준 코드: 로컬 917e8e4. 이 변경의 GitHub 게시·새 원격 CI 통과는 아직 확인한 성과로 적지 않았다.<br/>'
           '근거: docs/verification/2026-11-17/ · docs/system-design/ · docs/wbs/2026-11-17/',478)
    return p.finish()


def next_plan():
    p=ReportPage(); p.header('[Backup] 차주 완료 기준과 최종 범위', '11/20 ~ 11/26  |  기존 WBS 4.3 잔여 오류 정리·5.1 운영 및 시연 안정화',10)
    p.table(['차주 계획·기한*','확인할 완료 기준'],[
        ['실행·시연 준비 / ~11/22','새 환경 설치·실행 절차 확인, 시연용 합성 자료·계정 준비.<br/>성공 화면과 실행 조건을 기록한다.'],
        ['복구·권한 점검 / ~11/24','백업·복원·재시작 후 저장 자료 확인, 만료·권한 거절 복구 점검.<br/>실패를 기록하고 필요한 수정만 재검사한다.'],
        ['주요 흐름 시연 / ~11/25','요약 조건→충돌 해결→지침 저장→새 작업 재사용 연결 확인.<br/>코딩 두 기능도 유지되는지 팀 내부에서 시연한다.'],
        ['공유·문서 정리 / ~11/26','변경분 GitHub 게시 후 자동 검사 확인, 결과·실행 안내 연결.<br/>설계/WBS 개정과 최종 제출물 목록을 정리한다.'],
    ],[210,502],y=116,heights=[57]*4,size=10.5)
    p.text('최종 완료: 동작 제품 + 재현 가능한 분리 검증 + 최신 문서 + 시연·실행 안내',
           35,397,710,12,bold=True,maxh=22)
    p.text('학기 후반에는 최종 보고서·발표·영상·제출 버전을 완성합니다.<br/>'
           '사람의 편의성·시간 절감은 미검증으로 명시하고 GEPA 필수화·수동 대비 우위를 완료 조건에 넣지 않습니다.',
           35,434,710,10.5,maxh=35)
    p.note('*담당은 공동, 기한은 팀 합의용 계획. 수업의 공식 마감·필수 제출물은 별도 확인.<br/>'
           '기존 WBS: 운영·시연 11/20~12/04, 최종 자료 12/05~12/14, 최종 제출·인계 12/15~12/18.',478)
    return p.finish()


def github():
    p=ReportPage(); p.header('[Backup] GitHub 주소와 분석·설계서 위치', '게시된 공유본 링크와 이번 주 로컬 개정 원고를 구분  |  파란 링크 클릭',11)
    p.text('프로젝트 GitHub',35,112,710,13,bold=True,maxh=22)
    p.text(f'<link href="{REPO}" color="#164E8A"><u>{REPO}</u></link>',35,139,710,11.3,maxh=22)
    p.text('기존 공유본: docs/wbs-v3.2 / 4b40d11  ·  분석·설계서 v1.2 / WBS v3.3',35,174,710,10.6,MUTED,maxh=20)
    links=[
        ('전체 분석·설계서: docs/system-design/',
         '분석 01장 · 유즈케이스 02장 · 상세 설계 03~08장 · 검증 09장',
         'docs/system-design/README.md','분석·설계서 목차 및 PDF 안내'),
        ('WBS: docs/wbs/2026-11-12/',
         'PDF: output/pdf/ · Excel: outputs/wbs-20261112/ · 버전 v3.3',
         'docs/wbs/2026-11-12/README.md','WBS PDF·Excel 안내'),
    ]
    for i,(title,desc,path,label) in enumerate(links):
        y=213+i*77
        p.text(title,35,y,710,11.3,bold=True,maxh=20)
        p.text(desc,35,y+23,710,10.3,MUTED,maxh=18)
        url=REPO+'/blob/'+PUBLISHED+'/'+quote(path,safe='/')
        p.text(f'<link href="{url}" color="#164E8A"><u>{label}</u></link>',35,y+45,710,10.4,maxh=18)
    p.text('이번 주 로컬 개정: codex/weekly-2026-11-17 / 917e8e4 (아직 GitHub 미게시)',
           35,379,710,11,bold=True,maxh=21)
    p.text('설계 원고: docs/system-design/  ·  진행 WBS: docs/wbs/2026-11-17/<br/>'
           '기술 검사: docs/verification/2026-11-17/  ·  새 출력 비교: benchmarks/weekly_validation_2026_11_17/',
           35,409,710,9.6,MUTED,maxh=32)
    p.note('위 GitHub 링크는 게시된 11/13 공유본을 가리킨다. 11/17 정책·검증 원고가 이미 올라갔다고 표시하지 않았다.<br/>'
           '주간보고서 v0.10은 output/pdf/와 기존 통합 자료 폴더에 저장. GitHub 반영 뒤 최신 링크를 갱신한다.',478)
    return p.finish()


def main():
    assert CHECKS['python']['passed']==1433 and CHECKS['frontend']['passed']==136
    assert CHECKS['browser']['passed']==6 and CHECKS['build_passed']
    for review in SCORES['by_reviewer'].values():
        for arm in review.values():
            s,r=arm['summary'],arm['react']
            assert (s['joint_conditions'],s['core_facts_preserved'],s['core_facts_total'])==(6,17,18)
            assert (s['all_required_policy_met'],s['all_required_policy_cases'])==(5,5)
            assert (r['type_pass'],r['behavior_checks_pass'],r['all_three_style_match'])==(8,40,8)
    assert len(WBS['tasks'])==len(STATUS['tasks'])==16
    assert [(x['id'],x['name']) for x in WBS['tasks']]==[(x['id'],x['name']) for x in STATUS['tasks']]
    previous_hash=hashlib.sha256(PREVIOUS.read_bytes()).hexdigest()
    writer=PdfWriter()
    functions=[cover,wbs,weekly,backup_index,react_changes,session_policy,summary_results,
               coding_results,verification_design,next_plan,github]
    titles=['표지','1. 프로젝트 일정 - WBS','2. 프로젝트 진행현황','Backup','React 지침·호환 개선',
            '비교 세션 접근·만료','요약 검증','React 검증','기술 검증·설계·WBS','다음 계획·최종 범위','GitHub·문서 위치']
    for fn in functions: writer.add_page(fn())
    for i,title in enumerate(titles): writer.add_outline_item(title,i)
    writer.add_metadata({'/Title':'Revealed 주간보고서 v0.10 · 2026.11.20 발표',
                         '/Author':'윤정우 · 고차원',
                         '/Subject':'실적 11/13~11/19 (11/17 확인 기준), 차주 계획 11/20~11/26'})
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('wb') as stream: writer.write(stream)
    assert len(writer.pages)==11 and hashlib.sha256(PREVIOUS.read_bytes()).hexdigest()==previous_hash
    COPY.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(OUT,COPY)
    QA.mkdir(parents=True,exist_ok=True)
    manifest=dict(version=VERSION,report_date='2026-11-20',semester_week=11,
        actual_period=['2026-11-13','2026-11-19'],plan_period=['2026-11-20','2026-11-26'],
        evidence_cutoff='2026-11-17',pages=11,main_pages=[1,2,3],backup_pages=[4,11],
        achievement_groups=['기능 개선','프롬프트 검증','팀 공유·권한 보완','분석·설계서 작성'],
        issue_and_request_fields='blank',historical_backup_pages=0,text_overflows=0,
        wbs_tasks=16,activity_week=10,highlighted_wbs_ids=sorted(ACTIVE),
        previous_pdf_preserved=True,previous_pdf_sha256=previous_hash,
        output=OUT.relative_to(ROOT).as_posix(),copy=COPY.relative_to(ROOT).as_posix(),
        sha256=hashlib.sha256(OUT.read_bytes()).hexdigest(),paid_model_api_calls=0,
        source_commit='917e8e4',new_work_remote_published=False,visual_review='pending')
    (QA/'build_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'version':VERSION,'pages':11,'evidence_cutoff':'2026-11-17','copy_saved':True}))


if __name__=='__main__': main()

"""11/20 course report: 11/13-19 period, only evidence confirmed by 11/18.

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

VERSION = '0.11'
OUT = ROOT / 'output/pdf/Revealed_진행현황_주간보고서_v0.11.pdf'
COPY = ROOT / 'outputs/Revealed_최종제출_준비본_2026-11-18' / OUT.name
PREVIOUS = ROOT / 'output/pdf/Revealed_진행현황_주간보고서_v0.10.pdf'
QA = ROOT / 'tmp/weekly_2026_11_20/v0_11'
REPO = 'https://github.com/a77315829-byte/preference-prompt-tool'
PUBLISHED = '636a766f717f398951fb5e693d0e29b97ea95585'
GRAY, MUTED, TEAL = layout.GRAY, layout.MUTED, layout.TEAL


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


WBS = read('docs/wbs/2026-11-18/wbs-v3.4.json')
STATUS = read('docs/wbs/2026-11-17/status.json')
CHECKS = read('docs/verification/2026-11-17-readiness/results/validation.json')
FINAL = read('docs/final/2026-11-18/validation.json')
SCORES = read('benchmarks/weekly_validation_2026_11_17/scores.json')
ACTIVE = {'1.3', '2.1', '2.2', '2.3', '3.1', '3.2', '3.3', '4.1', '4.2', '4.3', '5.1', '5.2'}


class ReportPage(layout.ReportPage):
    def footer(self, number, backup=False, old_number=None):
        self.rect(0, 514, 780, 26, '#FFFFFF')
        self.text('Revealed | 2026.11.20 보고 | 실적 11/13~11/19 | 확인 기준 11/18',
                  34, 520, 620, 8, MUTED, maxh=13)
        self.text(f'v{VERSION}   {number}', 650, 518, 96, 9, MUTED, maxh=15, align=2)


def cover():
    original = PdfReader(layout.TEMPLATE).pages[0]
    p = ReportPage()
    p.text('선호 기반 프롬프트 자동 생성 도구', 35, 192, 463, 20, '#FFFFFF', True, maxh=32)
    p.text('팀 Revealed  ·  윤정우 · 고차원', 35, 228, 465, 14, '#FFFFFF', maxh=24)
    p.text('2026.11.20 보고  |  11주차  |  v0.11', 35, 379, 710, 15, bold=True, maxh=25)
    p.text('실적: 11/13 ~ 11/19   |   다음 계획: 11/20 ~ 11/26', 35, 412, 710, 13, MUTED, maxh=22)
    p.text('작성·실적 확인: 11/18까지  ·  본 보고 1~3쪽  ·  이번 주 상세 근거는 백업 4~13쪽',
           35, 443, 710, 10.5, MUTED, maxh=18)
    original.merge_page(p.finish())
    return original


def wbs():
    p = ReportPage()
    p.header('1. 프로젝트 일정 - WBS',
             '학기 전체 15주  |  실적 11/13~11/19 · 차주 11/20~11/26  |  WBS v3.4의 16개 작업 유지', 2)
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
    p.note('*담당은 기존 팀 계획안. 초록은 11/18까지 확인한 활동이며 전체 작업 완료율이 아니다.<br/>'
           '실적은 10주차, 발표일은 11주차. 5.1·5.2는 준비 선행이며 팀 리허설·제출 확정은 남아 있다.', 485)
    return p.finish()


def weekly():
    p = ReportPage(); p.header('2. 프로젝트 진행현황', '', 3)
    for x, label, color in [(34,'금주 실적 (11/13 ~ 11/19)','#808080'),(390,'차주 계획 (11/20 ~ 11/26)',GRAY)]:
        p.rect(x,84,356,32,color)
        p.text(label,x+9,89,338,13,'#FFFFFF',True,maxh=21,align=1)
    for x in [34,335,390,691,746]: p.line(x,116,x,400,'#C7CDD0',.7)
    for x in [34,390,746]: p.line(x,400,x,494,'#C7CDD0',.7)
    left = [
        ('기능 개선','React 한·영 지침·필수 타입 예외 정렬<br/>확정 요약 지침 저장→새 작업 재사용 연결','11/17'),
        ('프롬프트 검증','새 요약 6원문·React 8과제 수동/제품 비교<br/>조건·내용·타입·동작 분리, 이번 표본 동률','11/17'),
        ('팀 공유·권한 보완','비교 세션 소유권·만료·로그아웃 보호<br/>저장 자료 백업·복원·재시작 검증 완료','11/17'),
        ('분석·설계서 작성','설계서 v1.3·WBS v3.4 발행·UC 연결<br/>최종 보고·발표 준비본·시연 영상 정리','11/18'),
    ]
    right = [
        ('팀원 환경 실행 확인 (공동)','팀원 PC에서 설치·실행·복구 안내 수행<br/>실행 환경·결과와 발견 문제 기록','~11/22'),
        ('팀 시연·잔여 오류 수정 (공동)','요약 재사용·코딩 두 기능 참석 리허설<br/>실패가 발견된 흐름 수정 후 재검사','~11/24'),
        ('공식 제출 조건 확인 (공동)','지정 양식·발표 시간·채널·마감 확인<br/>준비본을 기준에 맞춰 보완','~11/25'),
        ('최종 자료 팀 검토 (공동)','보고서·발표·영상·실행 안내 교차 확인<br/>공유 권한·링크·제출 후보 목록 정리','~11/26'),
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
           ('9쪽  저장·복구·자동 검사 확인','요약 지침 저장·재사용, 복구 10항목, 생략 검사 3개 재확인'),
           ('10~11쪽  설계·WBS·최종 자료 발행','설계서 154쪽·WBS 16작업, 보고·발표 준비본과 실제 화면 영상'),
           ('12~13쪽  다음 계획과 GitHub 위치','남은 팀 리허설·공식 제출 요건, 최신 분석·설계서 공유 위치')]
    for i,(title,body) in enumerate(items):
        y=118+i*55
        p.rect(36,y+7,4,4,'#111111')
        p.text(title,51,y,694,13,bold=True,maxh=22)
        p.text(body,51,y+25,694,10.7,MUTED,maxh=19)
    p.note('실적 기간 11/13~11/19 중 11/18까지 확인한 결과만 포함. 11/19 예정 작업은 완료로 쓰지 않았다.<br/>'
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
    p=ReportPage(); p.header('[Backup] 지침 저장·복구·자동 검사 확인', '11/17 기술 검증  |  제품 코드 0bbff80  |  문서 게시 636a766의 CI도 확인',9)
    p.table(['영역','이번 주 확인·갱신 결과','남은 범위·주의'],[
        ['확정 지침 저장','현재 언어의 확정 요약 지침만 명시적으로 저장.<br/>보관함에서 새 작업에 재사용하는 흐름 연결.','원문·선택 문장은 저장하지 않음.<br/>새 원문의 조건 확인은 별도.'],
        ['백업·복원','SQLite 백업·해시·무결성 검사 추가.<br/>실제 HTTP 저장·재시작·복원 10항목 통과.','합성 자료·임시 DB로 확인.<br/>실사용 데이터 복구 실험 아님.'],
        ['로컬 검사','Python 1,440개·프론트 137개 통과.<br/>Chromium 6시나리오와 프론트 빌드 통과.','Windows 심볼릭 링크 1개 건너뜀.<br/>실제 모델 API 검사 16개 제외.'],
        ['원격 자동 검사','636a766의 브랜치·PR Tests 모두 성공.<br/>CI Python 1,438개·프론트 137개 통과.','자료 부재로 CI 3개 건너뜀.<br/>해당 3개는 최신 로컬 3/3 통과.'],
    ],[125,357,230],y=116,heights=[70]*4,size=10.2)
    p.text('운영·시연 준비를 앞당겨 수행했습니다. 자동 확인을 팀원 PC 실행·참석 리허설로 대신하지는 않습니다.',
           35,442,710,10.6,bold=True,maxh=21)
    p.note('근거: docs/verification/2026-11-17-readiness/ · Windows 생략 1개와 CI 자료 생략 3개는 서로 다름.<br/>'
           '확인한 Tests 실행: 44226960086 / 44226966256. 이번 v0.11 게시 커밋의 검사와는 별개.',478)
    return p.finish()


def design_release():
    p=ReportPage(); p.header('[Backup] 분석·설계서 v1.3 · WBS v3.4', '11/18  |  새 발행본과 UC 연결 갱신  |  이전 PDF·Excel 보존',10)
    p.table(['산출물','이번 주 반영·확인 내용','완료 범위'],[
        ['전체 분석·설계서','v1.3 PDF 154쪽으로 발행.<br/>세션 소유권·만료, 확정 지침 저장·복구 반영.','상위 UC 24개·하위 UC 79개.<br/>기존 다이어그램 77개 유지.'],
        ['WBS','v3.4 PDF 3쪽·Excel 3개 시트 발행.<br/>5단계·16작업의 상태·근거와 UC 연결 갱신.','작업 이름·ID·계획일 유지.<br/>수식·간트 입력 변경 반영 확인.'],
        ['문서 연결','요약·코딩 두 기능, 저장·접근 경계 설명 정렬.<br/>UC-02·03과 저장/공통 세션 작업 연결.','UC·WBS 대조, 링크 확인.<br/>새 출력 검증과 한계 함께 명시.'],
        ['남은 작업','WBS 5.1 운영·시연, 5.2 최종 자료는 진행 중.<br/>5.3 최종 제출·인계는 예정으로 유지.','준비본 발행과 공식 제출 구분.<br/>사람의 효과 미측정 유지.'],
    ],[125,357,230],y=116,heights=[70]*4,size=10.2)
    p.text('전체 설계를 새로 늘리는 단계에서, 구현·검증·산출물의 번호와 내용을 맞추는 단계로 진행했습니다.',
           35,442,710,10.6,bold=True,maxh=21)
    p.note('근거: docs/system-design/validation-v1.3.json · docs/wbs/2026-11-18/validation.json<br/>'
           '이전 분석·설계서 v1.2, WBS v3.3, 주간보고서 v0.10은 원본 그대로 보존.',478)
    return p.finish()


def final_materials():
    p=ReportPage(); p.header('[Backup] 최종 보고·발표·시연 준비본', '11/18  |  제출 준비를 선행 완료  |  공식 제출·사람의 사용자 실험은 아직 아님',11)
    p.table(['준비한 자료','구성·확인 결과','사용·마무리 조건'],[
        ['최종 보고서','준비본 v0.1 PDF 18쪽.<br/>목적·설계·분리 검증·한계·예상 질문 정리.','교수자 양식·제출 요건 확인 후<br/>팀 검토를 거쳐 확정.'],
        ['발표자료','준비본 v0.1 총 16장, 약 10분 설명.<br/>슬라이드별 대본·출처·예상 Q&A 포함.','사용자 Spaces에 보관.<br/>팀원 공유 권한은 별도 확인.'],
        ['실제 화면 영상','무음 WebM 1분 19.4초, 1440×1080.<br/>요약 충돌 해결·저장·재사용, 코딩 두 기능.','합성 계정·준비 예시로 녹화.<br/>실제 모델 생성 영상은 아님.'],
        ['시연·자료 묶음','실제 UI 6항목 재확인, 오류·외부 요청 0.<br/>5~7분 직접 시연 안내와 파일 목록 정리.','로컬 한 폴더로 자료 모음.<br/>팀원 PC·참석 리허설 필요.'],
    ],[125,357,230],y=116,heights=[70]*4,size=10.2)
    p.text('최종 보고·설계·WBS PDF 175쪽 전체 렌더, 발표 16장, Excel 3개 시트와 영상 재생을 확인했습니다.',
           35,442,710,10.4,bold=True,maxh=21)
    p.note('근거: docs/final/2026-11-18/validation.json · demo-results.json · presenter-notes.md<br/>'
           '새 모델 비교 실험을 추가한 작업이 아니다. 기존 동률·17/18 결과와 검증 한계를 보존.',478)
    return p.finish()


def next_plan():
    p=ReportPage(); p.header('[Backup] 차주 완료 기준과 최종 범위', '11/20 ~ 11/26  |  선행 완료한 준비 뒤, 팀 실행·제출 요건·최종 검토 진행',12)
    p.table(['차주 계획·기한*','확인할 완료 기준'],[
        ['팀원 환경 실행 / ~11/22','팀원 PC에서 설치·실행·백업·복구 안내를 따라 수행한다.<br/>환경과 성공 화면, 재현에 필요한 수정 사항을 기록한다.'],
        ['참석 리허설 / ~11/24','요약 충돌 해결→저장→재사용과 코딩 두 기능을 팀이 시연한다.<br/>발견한 실패만 수정하고 영향 범위를 다시 검사한다.'],
        ['공식 요건 확인 / ~11/25','지정 양식·발표 시간·제출 채널·마감·파일명을 확인한다.<br/>기존 준비본을 요건에 맞춰 보완한다.'],
        ['최종 자료 팀 검토 / ~11/26','보고·발표의 수치와 기능·영상·실행 안내를 교차 확인한다.<br/>팀 공유 권한과 GitHub 링크, 제출 후보 파일 목록을 정리한다.'],
    ],[210,502],y=116,heights=[57]*4,size=10.5)
    p.text('최종 완료: 동작 제품 + 재현 가능한 분리 검증 + 최신 문서 + 시연·실행 안내',
           35,397,710,12,bold=True,maxh=22)
    p.text('최종 보고·발표·영상의 준비본은 확보했으며, 팀 확인과 공식 제출은 남아 있습니다.<br/>'
           '사람의 편의성·시간 절감은 미검증으로 명시하고 GEPA 필수화·수동 대비 우위를 완료 조건에 넣지 않습니다.',
           35,434,710,10.5,maxh=35)
    p.note('*담당은 공동, 기한은 팀 합의용 계획. 수업의 공식 마감·필수 제출물은 별도 확인.<br/>'
           '기존 WBS: 운영·시연 11/20~12/04, 최종 자료 12/05~12/14, 최종 제출·인계 12/15~12/18.',478)
    return p.finish()


def github():
    p=ReportPage(); p.header('[Backup] GitHub 주소와 분석·설계서 위치', '게시 확인: docs/wbs-v3.2 · 636a766  |  파란 링크 클릭',13)
    p.text('프로젝트 GitHub',35,112,710,13,bold=True,maxh=22)
    p.text(f'<link href="{REPO}" color="#164E8A"><u>{REPO}</u></link>',35,139,710,11.3,maxh=22)
    p.text('PR #14에서 공유 중  ·  분석·설계서 v1.3 / WBS v3.4 / 최종 자료 준비본',35,174,710,10.6,MUTED,maxh=20)
    links=[
        ('전체 분석·설계서: docs/system-design/',
         '분석 01장 · 유즈케이스 02장 · 상세 설계 03~08장 · 검증 09장',
         'docs/system-design/README.md','분석·설계서 목차 및 PDF 안내'),
        ('WBS: docs/wbs/2026-11-18/',
         'PDF: output/pdf/ · Excel: outputs/wbs-20261118/ · 버전 v3.4',
         'docs/wbs/2026-11-18/README.md','WBS PDF·Excel 안내'),
        ('최종 보고·발표·영상: docs/final/2026-11-18/',
         '최종 보고서 PDF · 시연 WebM · 발표 대본·Q&A · 준비본 목록',
         'docs/final/2026-11-18/README.md','최종 자료 모음 안내'),
    ]
    for i,(title,desc,path,label) in enumerate(links):
        y=213+i*77
        p.text(title,35,y,710,11.3,bold=True,maxh=20)
        p.text(desc,35,y+23,710,10.3,MUTED,maxh=18)
        url=REPO+'/blob/'+PUBLISHED+'/'+quote(path,safe='/')
        p.text(f'<link href="{url}" color="#164E8A"><u>{label}</u></link>',35,y+45,710,10.4,maxh=18)
    p.note('위 문서 링크는 게시 확인한 636a766의 고정 버전. 최신 주간보고서는 docs/weekly_reports/에서 안내.<br/>'
           'v0.11 PDF는 output/pdf/와 로컬 최종제출 준비본 폴더에 보관. 공식 제출·병합 완료를 뜻하지 않음.',478)
    return p.finish()


def main():
    assert CHECKS['python']['passed']==1440 and CHECKS['frontend_passed']==137
    assert CHECKS['browser_passed']==6 and CHECKS['build_passed']
    assert CHECKS['storage_rehearsal_passed']==10 and CHECKS['three_current_recheck_passed']
    assert [FINAL['pdfs'][key]['pages'] for key in ['design','report','wbs']]==[154,18,3]
    assert FINAL['presentation']['slides']==16 and FINAL['demo']['passed']==6
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
               coding_results,verification_design,design_release,final_materials,next_plan,github]
    titles=['표지','1. 프로젝트 일정 - WBS','2. 프로젝트 진행현황','Backup','React 지침·호환 개선',
            '비교 세션 접근·만료','요약 검증','React 검증','저장·복구·자동 검사','설계·WBS 발행',
            '최종 보고·발표·시연','다음 계획·최종 범위','GitHub·문서 위치']
    for fn in functions: writer.add_page(fn())
    for i,title in enumerate(titles): writer.add_outline_item(title,i)
    writer.add_metadata({'/Title':'Revealed 주간보고서 v0.11 · 2026.11.20 발표',
                         '/Author':'윤정우 · 고차원',
                         '/Subject':'실적 11/13~11/19 (11/18 확인 기준), 차주 계획 11/20~11/26'})
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('wb') as stream: writer.write(stream)
    assert len(writer.pages)==13 and hashlib.sha256(PREVIOUS.read_bytes()).hexdigest()==previous_hash
    COPY.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(OUT,COPY)
    legacy_copy=ROOT/'outputs/Revealed_설계서_v1.2_WBS_v3.3'/OUT.name
    legacy_copy.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(OUT,legacy_copy)
    QA.mkdir(parents=True,exist_ok=True)
    manifest=dict(version=VERSION,report_date='2026-11-20',semester_week=11,
        actual_period=['2026-11-13','2026-11-19'],plan_period=['2026-11-20','2026-11-26'],
        evidence_cutoff='2026-11-18',pages=13,main_pages=[1,2,3],backup_pages=[4,13],
        achievement_groups=['기능 개선','프롬프트 검증','팀 공유·권한 보완','분석·설계서 작성'],
        issue_and_request_fields='blank',historical_backup_pages=0,text_overflows=0,
        wbs_tasks=16,activity_week=10,highlighted_wbs_ids=sorted(ACTIVE),
        previous_pdf_preserved=True,previous_pdf_sha256=previous_hash,
        output=OUT.relative_to(ROOT).as_posix(),copy=COPY.relative_to(ROOT).as_posix(),
        sha256=hashlib.sha256(OUT.read_bytes()).hexdigest(),paid_model_api_calls=0,
        source_commit='0bbff80',published_document_commit=PUBLISHED,
        prior_ci_run_ids=[44226960086,44226966256],
        new_work_remote_published=True,this_report_remote_published_at_build=False,visual_review='pending',
        additional_copy=legacy_copy.relative_to(ROOT).as_posix())
    (QA/'build_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'version':VERSION,'pages':13,'evidence_cutoff':'2026-11-18','copy_saved':True}))


if __name__=='__main__': main()

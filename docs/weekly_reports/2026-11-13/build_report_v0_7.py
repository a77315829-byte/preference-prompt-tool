"""Weekly v0.7: only this week's work; no copied historical backup pages."""
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote
import hashlib
import json
from pypdf import PdfReader, PdfWriter
import build_report_v0_4 as layout

ROOT = layout.ROOT
HERE = Path(__file__).resolve().parent
OUT = ROOT/'output/pdf/Revealed_진행현황_주간보고서_v0.7.pdf'
QA = ROOT/'tmp/weekly_2026_11_13/v0_7'
VERSION = '0.7'
REPO = 'https://github.com/a77315829-byte/preference-prompt-tool'
BRANCH = 'docs/wbs-v3.2'
MUTED, GRAY, TEAL = layout.MUTED, layout.GRAY, layout.TEAL


def read(relative):
    return json.loads((ROOT/relative).read_text(encoding='utf-8'))


POLICY = read('docs/verification/2026-11-12-summary-policy/results/validation.json')
INTEGRATION = read('docs/verification/2026-11-12/results.json')
CI = read('docs/verification/2026-11-12/ci/results.json')
SUMMARY = read('benchmarks/summary_contract_revision/results/2026-11-10/scores.json')
WBS = read('docs/wbs/2026-11-12/wbs-v3.3.json')
DESIGN = read('docs/system-design/validation.json')


class ReportPage(layout.ReportPage):
    def footer(self, number, backup=False, old_number=None):
        self.rect(0, 514, 780, 26, '#FFFFFF')
        self.text('Revealed | AI/SW융합프로젝트 | 2026.11.13 보고 | 실적 11/06~11/12',
                  34, 520, 620, 8, MUTED, maxh=13)
        self.text(f'v{VERSION}   {number}', 657, 518, 89, 9, MUTED, maxh=15, align=2)


def cover():
    original = PdfReader(layout.TEMPLATE).pages[0]
    p = ReportPage()
    p.text('선호 기반 프롬프트 자동 생성 도구', 35, 192, 463, 20, '#FFFFFF', True, maxh=32)
    p.text('팀 Revealed  ·  윤정우 · 고차원', 35, 228, 465, 14, '#FFFFFF', maxh=24)
    p.text('2026.11.13 보고  |  10주차  |  v0.7', 35, 379, 710, 15, bold=True, maxh=25)
    p.text('실적: 11/06 ~ 11/12   |   다음 계획: 11/13 ~ 11/19', 35, 412, 710, 13, MUTED, maxh=22)
    p.text('본문: 1. 프로젝트 일정  /  2. 프로젝트 진행현황  ·  이번 주 상세 근거는 백업',
           35, 443, 710, 10.5, MUTED, maxh=18)
    original.merge_page(p.finish())
    return original


def wbs():
    p = ReportPage()
    p.header('1. 프로젝트 일정 - WBS',
             '학기 전체 15주  |  실적 11/06~11/12 · 다음 계획 11/13~11/19  |  작업 ID·명칭은 WBS v3.3과 일치', 2)
    grid_x, cw, y0, rh = 345, 401/15, 151, 19
    p.rect(34, 111, 712, 40, GRAY)
    for x, width, label in [(34,35,'단계'),(69,31,'ID'),(100,202,'작업·산출물'),(302,43,'담당*')]:
        p.text(label, x+2, 122, width-4, 9.2, '#FFFFFF', True, maxh=17, align=1)
    p.rect(grid_x+9*cw, 111, cw, 40, '#B54A2F')
    for i, day in enumerate(layout.WEEKS):
        p.text(f'{i+1}주', grid_x+i*cw, 116, cw, 8.9, '#FFFFFF', True, maxh=15, align=1)
        p.text(day.strftime('%m/%d'), grid_x+i*cw, 135, cw, 7.5, '#FFFFFF', maxh=12, align=1)
    phases = {'1':'분석','2':'설계','3':'구현','4':'검증','5':'정리'}
    active = {'1.1','1.2','1.3','2.1','2.2','2.3','3.1','3.2','3.3','3.4','4.1','4.2'}
    for i, task in enumerate(WBS['tasks']):
        y = y0+i*rh
        p.rect(34, y, 712, rh, '#F1F4F5' if i%2 else '#FFFFFF')
        p.rect(grid_x+9*cw, y, cw, rh, '#FFF0D9')
        owner = '윤정우' if task['group'] in ('2','3') else '공동'
        p.text(phases[task['group']], 36, y+4, 31, 8.1, maxh=13, align=1)
        p.text(task['id'], 71, y+4, 27, 8.4, maxh=13, align=1)
        p.text(task['name'], 104, y+4, 194, 8.7, maxh=13)
        p.text(owner, 304, y+4, 39, 8.1, maxh=13, align=1)
        start, end = date.fromisoformat(task['start']), date.fromisoformat(task['end'])
        for week, day in enumerate(layout.WEEKS):
            if start <= day+timedelta(days=6) and end >= day:
                p.rect(grid_x+week*cw+3, y+5, cw-6, 9, '#E5EAEE', '#8A9EAD')
        if task['id'] in active:
            p.rect(grid_x+8*cw+5, y+6, cw-10, 7, TEAL)
        p.line(34, y+rh, 746, y+rh, '#DCE1E3', .5)
    for x in [34,69,100,302]+[grid_x+i*cw for i in range(16)]:
        p.line(x, y0, x, y0+16*rh, '#DAE1E4', .5)
    for x, color, label in [(35,'#E5EAEE','학기 계획'),(180,TEAL,'이번 주 활동 확인'),(408,'#FFF0D9','11/13 보고 위치')]:
        p.rect(x, 468, 14, 9, color, '#8A9EAD')
        p.text(label, x+20, 464, 190, 9.6, maxh=17)
    p.note('*담당은 기존 계획을 따른 제안이며 팀에서 확정. 초록은 이번 주 활동 기록이고 완료율이 아니다.<br/>'
           '지난주 실적 칸은 반복 표시하지 않음. 일정·명칭만 최신 WBS로 정렬하며 11/13 문서 개정을 금주 실적으로 합산하지 않음.', 485)
    return p.finish()


def weekly():
    p = ReportPage(); p.header('2. 프로젝트 진행현황', '', 3)
    for x, label, color in [(34,'금주 실적 (11/06 ~ 11/12)','#808080'),(390,'차주 계획 (11/13 ~ 11/19)',GRAY)]:
        p.rect(x,84,356,32,color)
        p.text(label,x+9,89,338,13,'#FFFFFF',True,maxh=21,align=1)
    for x in [34,335,390,691,746]: p.line(x,116,x,400,'#C7CDD0',.7)
    for x in [34,390,746]: p.line(x,400,x,494,'#C7CDD0',.7)
    left = [
        ('요약·코딩 사용 흐름 보완', '요약 12,000자 제한·상하한 충돌 처리 통일<br/>코딩 두 기능 분리·초안과 결과 복귀 보완', '11/09<br/>~11/12'),
        ('공유·권한 오류 수정과 통합 검사', '두 계정 공유·첨부·회수 등 18시나리오 통과<br/>권한 회수 뒤 남아 있던 화면·초안 정리', '11/12'),
        ('새 원문·과제의 독립 출력 비교', '요약 9원문·코딩 두 기능 각 8과제 비교<br/>조건과 내용·동작 분리, 수동 대비 동률', '11/10<br/>~11/12'),
        ('전체 설계서·최신 회귀 확인', '요구→화면→API·DB 분석·설계서 작성<br/>Python 1,399·프론트 129개 및 빌드 통과', '11/12'),
    ]
    right = [
        ('React 지침 의미 정렬 (윤정우)', '한국어·영어의 타입 예외·역할 분리 맞추기<br/>동일 조건표와 변경 지침을 고정', '~11/15'),
        ('비교 세션 권한 보완 (공동)', '접근·소유권·만료 정책 확정 및 구현<br/>두 계정·로그아웃·만료 경계 확인', '~11/17'),
        ('변경 지침 재비교 (고차원·공동)', '요약 v2 새 원문·React 변경분 새 과제<br/>수동과 조건·내용/타입·동작 분리 평가', '~11/19'),
        ('회귀·설계·WBS 동기화 (공동)', '수정 코드 전체 검사·빌드·대표 시연<br/>UC 하위 명세와 WBS 연결·근거 갱신', '~11/19'),
    ]
    for x, items in [(34,left),(390,right)]:
        for i,(title,body,day) in enumerate(items):
            y=124+i*68
            p.rect(x+9,y+6,3.5,3.5,'#111111')
            p.text(title,x+19,y,277,11.5,bold=True,maxh=19)
            p.text(body,x+19,y+22,277,10.1,maxh=33)
            p.text(day,x+304,y+15,48,8.8,maxh=28,align=1)
    for x,title,body in [
        (34,'주요 이슈 및 의사결정 사항',
         '검증 목표: 명시 조건 전달·내용 보존.<br/>수동 대비 우위·사람의 편의성은 미입증.<br/>GEPA는 원본 유지 결과에 따라 선택 적용.'),
        (390,'프로젝트 요청 사항',
         '세션 정책·담당과 차주 평가 범위 확정.<br/>유료 API 없이 검증, 공개 배포는 별도.<br/>이번 주 상세 근거 5~10쪽 / 저장소 11쪽.'),
    ]:
        p.rect(x,400,356,30,'#EEEEEE')
        p.text(title,x+8,406,340,11.7,bold=True,maxh=20,align=1)
        p.text(body,x+10,439,336,10.5,maxh=47)
    for y in [400,430,494]: p.line(34,y,746,y,'#C7CDD0',1.5 if y==494 else .7)
    return p.finish()


def backup_index():
    p=ReportPage(); p.header('[Backup]', '이번 주 실적의 상세 근거와 다음 계획  |  질문 시 해당 쪽 확인',4)
    items=[('5쪽  사용 흐름·오류 수정','요약 입력·충돌 처리와 권한 회수 화면, 코딩 두 기능·복귀 보완'),
           ('6~7쪽  요약·코딩 독립 출력 검증','새 원문·과제, 세 방식 비교, 조건과 내용·동작의 분리 판정'),
           ('8쪽  통합 검사·전체 회귀·CI','실행 시점별 검사 수와 건너뜀·제외, 유료 API 없는 실행 근거'),
           ('9쪽  전체 분석·설계서 작성','11/12 작성 범위와 요구사항·유즈케이스·화면·API·DB 연결'),
           ('10쪽  다음 계획과 완료 기준','11/13~11/19: 지침 정렬·세션 권한·새 출력 비교·회귀·문서'),
           ('11쪽  GitHub 주소와 자료 위치','분석·설계서와 WBS의 정확한 폴더·PDF·엑셀 위치')]
    for i,(title,body) in enumerate(items):
        y=118+i*55
        p.rect(36,y+7,4,4,'#111111')
        p.text(title,51,y,694,13,bold=True,maxh=22)
        p.text(body,51,y+25,694,10.7,MUTED,maxh=19)
    p.note('실적 기간은 11/06~11/12. 이미 보고한 기존 기능 소개·이전 실험·과거 설계 그림은 반복 수록하지 않았다.<br/>'
           '구현·기술 검사·모델 출력 비교를 구분한다. 사람의 선호·만족도·시간 절감은 이번 결과에 포함하지 않는다.',465)
    return p.finish()


def changes():
    p=ReportPage(); p.header('[Backup] 이번 주 사용 흐름·오류 수정', '11/09~11/12 변경  |  요약·코딩·공유 흐름의 보완 결과',5)
    p.table(['변경 항목','이번 주 수정한 동작','확인한 범위'],[
        ['요약 입력 한도','시작·조건 확인 모두 공백 포함 12,000자 기준.<br/>초과 원문을 자르지 않고 보존·안내 후 거절.','한글·이모지·공백 경계값.<br/>서버·화면의 동일 기준 확인.'],
        ['발췌 조건 충돌','최대보다 보존 문장이 많거나 최소보다 원문이<br/>적으면 지침 보류. 사용자가 분량·표현을 선택.','미선택 생성 차단·변경 후 초기화.<br/>기존 코딩 기능 유지.'],
        ['공유 권한 회수','거절된 작업의 이전 내용·초안이 화면에 남던<br/>문제 수정. 일시 장애·버전 충돌의 입력은 보존.','두 계정·실제 HTTP·브라우저의<br/>공유·첨부·회수 등 18시나리오.'],
        ['코딩·복귀 흐름','AI 답변 방식 설정 / React 코드 스타일 비교를<br/>별도 진입으로 제공. 초안·GEPA 결과 복귀 보완.','관련 회귀·모바일 진입 확인.<br/>모델 호출을 하지 않는 데모 검사.'],
    ],[128,354,230],y=116,heights=[72]*4,size=10.3)
    p.note('요약 v2 정책·동작은 11/12에 확인했지만, 새 원문에서의 모델 출력 품질은 차주에 별도 비교한다.<br/>'
           '근거: docs/history/2026-11-12_summary_length_policy.md 및 docs/verification/2026-11-12*/',456)
    return p.finish()


def summary_results():
    p=ReportPage(); p.header('[Backup] 요약: 조건 준수와 내용 보존', '11/10  |  새 MACSum 영어 원문 9개  |  수동·당시 현재본·충돌 처리 수정본',6)
    p.text('세 방식에 같은 보존 대상과 해결된 조건을 제공하고 첫 응답을 비교했습니다.',35,114,710,12,bold=True,maxh=21)
    p.table(['독립 지표','수동','당시 현재본','수정본'],[
        ['분량·표현 동시 준수','9/9','9/9','9/9'],
        ['핵심 명제 보존','25/27','25/27','25/27'],
        ['지정 보존 내용','25/27','25/27','25/27'],
        ['사실 문제 표시 응답','0/9','0/9','0/9'],
    ],[268,148,148,148],y=151,heights=[37]*4,size=11)
    p.text('결과: 세 방식 동률. 핵심 명제 2/27 누락이 남았으며 제품의 우위는 확인하지 못했습니다.',35,348,710,11.4,bold=True,maxh=21)
    p.text('실제 GEPA 탐색도 별도 실행: 개선 6개·후보 선택 6개·최종 9개를 분리했습니다.<br/>'
           '후보 선택에서 원본 0.7778, 후보 0.7222 / 0.6667로 원본을 유지했습니다.<br/>'
           '운영 GEPA를 필수로 돌리거나 무료 자동 제공할 근거로 해석하지 않습니다.',35,383,710,10.8,maxh=49)
    p.note('27은 9개 원문의 명제 수. 두 독립 검토자 집계가 같아도 사람의 선호·편의성 검증은 아니다.<br/>'
           '11/12 길이·충돌 v2 정책의 새 출력 검증과 구분. 근거: benchmarks/summary_contract_revision/ 및 summary_gepa_offline/',468)
    return p.finish()


def coding_results():
    p=ReportPage(); p.header('[Backup] 코딩 두 기능: 새 과제 비교', '11/12  |  TypeScript/React 기능별 8과제 × 일반·수동·제품  |  기능별 첫 응답 24개',7)
    p.table(['기능 / 독립 지표','일반 요청','수동','제품'],[
        ['AI 답변 방식 4항목 · strict 타입','8/8','8/8','8/8'],
        ['AI 답변 방식 · 실제 DOM 동작','69/69','69/69','69/69'],
        ['설명·주석·구성·출력 모두 일치','0/8','8/8','8/8'],
        ['React 스타일 3축 · strict 타입','8/8','8/8','8/8'],
        ['React 스타일 · 실제 DOM 동작','56/56','56/56','56/56'],
        ['구성·스타일 관리·타입 모두 일치','1/8','8/8','8/8'],
    ],[292,140,140,140],y=115,heights=[33]*6,size=10.7)
    p.text('수동·제품 모두 조건을 전달하고 이번 과제의 타입·동작을 유지했습니다. 수동 대비 우위는 없습니다.',35,356,710,11,bold=True,maxh=21)
    p.text('• 일반 요청에는 선호 조건을 주지 않았으므로 불일치를 지시 위반으로 보지 않습니다.<br/>'
           '• 4항목 판정 96/96 일치, React 축별 판정 71/72 일치. 불일치 1건은 그대로 보존했습니다.<br/>'
           '• 알려진 목표 조건을 사용한 작은 합성 과제입니다. 사람의 취향 추정·수정 시간은 미측정입니다.<br/>'
           '• React 영어 지침 기준이며 한국어와 의미 차이는 차주 보완 대상입니다.',35,390,710,10.4,maxh=65)
    p.note('유료 모델 API 0회, 독립 Codex 보조 에이전트 사용량은 소비. 운영 환경 전체의 코드 품질·보안을 입증하지 않음.<br/>'
           '근거: benchmarks/coding_react_current/ 및 benchmarks/react_style_current/',477)
    return p.finish()


def regression():
    p=ReportPage(); p.header('[Backup] 통합·회귀·CI 확인 결과', '11/12  |  변경 시점·환경별 기록 구분  |  검사 수를 서로 합산하지 않음',8)
    p.table(['검사 시점·범위','실제 확인 결과','해석·제외'],[
        ['최신 요약 정책 반영 후<br/>로컬 전체 회귀','Python 1,399 통과 · Windows 1 건너뜀<br/>프론트 129 통과 · 배포용 빌드 성공','실제 API 검사 16개 제외.<br/>기존 번들 크기 경고 유지.'],
        ['요약 v2 집중·화면','집중 검사 73 통과 · 실제 브라우저 8시나리오<br/>입력·상하한 충돌·모바일·코딩 진입 확인','모델 출력 품질 검사와 별개.<br/>합성 입력·데모·실제 HTTP.'],
        ['공유·권한 통합<br/>같은 날 앞선 실행','두 계정 18시나리오 통과 · 오류 수정 확인<br/>당시 Python 1,355 · 프론트 123 통과','공유·첨부·회수·버전 충돌.<br/>최신 회귀 수치와 합산 금지.'],
        ['GitHub CI<br/>c784808 기준','브랜치·PR·컨테이너 검사 성공<br/>Python 1,353 · 프론트 123 통과','자료 부재 3개 건너뜀.<br/>별도 로컬 재확인 3/3 통과.'],
    ],[166,328,218],y=115,heights=[65]*4,size=10.2)
    p.text('이전 확인 이후 바뀐 코드의 회귀를 다시 실행해, 앞선 통과 기록을 그대로 이월하지 않았습니다.',35,421,710,11.2,bold=True,maxh=21)
    p.note('유료 API 0회. 합성 계정·임시 DB·로컬 서버 검사이며 공개 배포·실사용 효과와 구분한다.<br/>'
           '근거: docs/verification/2026-11-12/ 및 docs/verification/2026-11-12-summary-policy/results/validation.json',468)
    return p.finish()


def design_results():
    p=ReportPage(); p.header('[Backup] 이번 주 전체 분석·설계서 작성', '실적 기준 11/12  |  기능 소개를 넘어 요구사항부터 검증 근거까지 연결',9)
    p.table(['영역','이번 주 작성·검토한 내용'],[
        ['분석·요구사항','목적·대상·범위, 기능·비기능 요구, 명시 조건 전달과 미검증 주장 구분'],
        ['사용자·화면','상위 유즈케이스 24개, 논리 화면 18개, 입력·오류·권한·복귀 상태'],
        ['처리·구성요소','선택·조건 해결·저장·팀 연결 처리, 클래스·시퀀스 등 도식 21개'],
        ['API·데이터','GET/POST 경로 90개, 테이블 16개, migration 14와 데이터 사전'],
        ['운영·검증','요구→화면→API·DB 대응, 독립 출력 평가·원자료·한계와 회귀 근거'],
    ],[145,567],y=116,heights=[42]*5,size=10.6)
    p.text('11/12 작성본: 전체 97쪽(v1.0). PDF 전체 렌더링 검수와 검증 사본의 해시 대조를 마쳤습니다.',35,378,710,11.2,bold=True,maxh=21)
    p.text('현재 공유본은 11/13에 UC 하위 명세·그림과 WBS 연결을 보완한 설계서 v1.2입니다.<br/>'
           '이 후속 개정과 PR #14 검사 완료는 요청한 실적 마감일 다음 날이므로 금주 실적으로 합산하지 않습니다.',
           35,417,710,10.6,maxh=34)
    p.note('최신 분석·설계서는 한 문서 안에 분석 장과 설계 장으로 구성. 최신본 위치·다운로드 링크는 마지막 11쪽.<br/>'
           '11/12 작성 근거: docs/system-design/validation.json · 후속 개정: validation-v1.2.json',478)
    return p.finish()


def next_plan():
    p=ReportPage(); p.header('[Backup] 다음 계획과 완료 기준', '11/13 ~ 11/19  |  이번 주에 끝난 입력 정책 개선을 다시 미완료 계획으로 넣지 않음',10)
    p.table(['계획·담당·기한','완료 기준','검증 원칙'],[
        ['React 지침 정렬<br/>윤정우 / ~11/15','한국어·영어의 역할 분리·타입 예외를 맞춤.<br/>공통 조건표·변경 전후 지침·회귀 근거 기록.','기존 저장본과 고정 실험 보존.<br/>변경한 생성기만 새 과제로 평가.'],
        ['비교 세션 권한<br/>공동 / ~11/17','접근·소유권·만료 정책을 확정하고 구현.<br/>다른 계정·로그아웃·만료 후 거절을 확인.','합성 두 계정·임시 DB.<br/>화면과 서버 응답 함께 확인.'],
        ['변경 지침 새 평가<br/>고차원·공동 / ~11/19','요약 v2는 새 원문, React 변경분은 새 과제.<br/>수동 대비 조건·내용/타입·동작 분리 보고.','원문·과제·기준을 먼저 고정.<br/>유료 API 없이 보조 에이전트.'],
        ['회귀·문서 연결<br/>공동 / ~11/19','동일 코드의 Python·프론트·빌드·시연 통과.<br/>하위 UC·WBS 연결 및 새 정책 설명 동기화.','실패·건너뜀·제외를 별도 기록.<br/>설계서·WBS·검사 근거 함께 갱신.'],
    ],[160,334,218],y=115,heights=[78]*4,size=10.2)
    p.note('담당·기한은 팀 합의용 계획. 11/13의 문서 연결 개정은 반영됐으며 제품 세션 정책·새 출력 비교는 별도 남은 범위.<br/>'
           '사람의 만족도·시간 절감은 측정하지 않았으며, 기존 평가 원문을 새 최종 평가로 재사용하지 않는다.',471)
    return p.finish()


def github():
    p=ReportPage(); p.header('[Backup] GitHub 주소와 분석·설계서 위치', '보고서·분석·설계서·WBS를 찾는 위치  |  아래 파란 링크 클릭',11)
    p.text('프로젝트 GitHub',35,112,710,13,bold=True,maxh=22)
    p.text(f'<link href="{REPO}" color="#164E8A"><u>{REPO}</u></link>',35,139,710,11.3,maxh=22)
    p.text('문서 브랜치: docs/wbs-v3.2  ·  현재 문서: 설계서 v1.2 / WBS v3.3',35,173,710,10.7,MUTED,maxh=20)
    locations=[
        ('전체 분석·설계서: docs/system-design/', '분석은 01-analysis.md · 유즈케이스는 02-usecases.md · 상세 설계는 03~08장',
         'docs/system-design/README.md','전체 목차·분석·설계 원본 열기'),
        ('공유용 PDF: docs/system-design/Revealed_Analysis_Design_v1.2.pdf', '전체 분석·설계서 151쪽 · 최신 목차·다운로드는 위 폴더 README',
         'docs/system-design/Revealed_Analysis_Design_v1.2.pdf','전체 분석·설계서 PDF 열기'),
        ('WBS: docs/wbs/2026-11-12/', 'WBS v3.3의 PDF·Excel·유즈케이스 연결표·검수 기록을 함께 안내',
         'docs/wbs/2026-11-12/README.md','WBS PDF·Excel 안내 열기'),
    ]
    for i,(title,desc,path,label) in enumerate(locations):
        y=214+i*75
        p.text(title,35,y,710,11.2,bold=True,maxh=20)
        p.text(desc,35,y+23,710,10.2,MUTED,maxh=18)
        url=REPO+'/blob/'+BRANCH+'/'+quote(path,safe='/')
        p.text(f'<link href="{url}" color="#164E8A"><u>{label}</u></link>',35,y+44,710,10.4,maxh=18)
    p.note('GitHub에서 저장소 → 브랜치 docs/wbs-v3.2 → docs → system-design 순서로 이동.<br/>'
           '분석서·설계서는 하나의 전체 문서에 포함. WBS PDF는 output/pdf/, Excel은 outputs/wbs-20261112/에 있음.',472)
    return p.finish()


def main():
    assert POLICY['backend_full']['passed']==1399 and POLICY['frontend']['pass']==129
    assert POLICY['backend_focused']['passed']==73 and POLICY['browser_passed']==8
    assert INTEGRATION['integration']['passed']==18 and CI['focused_rerun']['passed']==3
    assert all(v['joint_pass']==9 and v['core_preserved']==25 for review in SUMMARY['by_reviewer'].values() for v in review.values())
    assert DESIGN['pdf']['pages']==97 and len(WBS['tasks'])==16
    previous=ROOT/'output/pdf/Revealed_진행현황_주간보고서_v0.6.pdf'
    old_hash=hashlib.sha256(previous.read_bytes()).hexdigest()
    writer=PdfWriter()
    pages=[cover,wbs,weekly,backup_index,changes,summary_results,coding_results,regression,design_results,next_plan,github]
    for fn in pages:
        writer.add_page(fn())
    titles=['표지','1. 프로젝트 일정 - WBS','2. 프로젝트 진행현황','Backup','이번 주 수정',
            '요약 검증','코딩 검증','통합·회귀·CI','분석·설계서 작성','다음 계획','GitHub·자료 위치']
    for index,title in enumerate(titles): writer.add_outline_item(title,index)
    writer.add_metadata({'/Title':'Revealed 주간보고서 v0.7 · 실적 11/06~11/12',
                         '/Author':'윤정우 · 고차원','/Subject':'이번 주 실적과 11/13~11/19 계획; 과거 백업 제외'})
    with OUT.open('wb') as stream: writer.write(stream)
    assert len(writer.pages)==11 and hashlib.sha256(previous.read_bytes()).hexdigest()==old_hash
    QA.mkdir(parents=True,exist_ok=True)
    manifest=dict(version=VERSION,report_date='2026-11-13',actual_period=['2026-11-06','2026-11-12'],
                  plan_period=['2026-11-13','2026-11-19'],pages=11,main_pages=[1,2,3],backup_pages=[4,11],
                  historical_backup_pages=0,previous_pdf_preserved=True,previous_pdf_sha256=old_hash,
                  output=OUT.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(OUT.read_bytes()).hexdigest(),
                  paid_model_api_calls=0,visual_review='pending')
    (QA/'build_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False))


if __name__=='__main__': main()

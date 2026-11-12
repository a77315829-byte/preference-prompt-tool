"""2026-11-13 weekly report; evidence cutoff 2026-11-12.

Preserve the course template and historical backup. No model calls, app changes,
or mutations of previous reports/experiment results. Uses bundled dependencies.
"""
from pathlib import Path
from datetime import date
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "2026-11-06"))
from build_report_v0_2 import Page, WEEKS, WBS as OLD_WBS
from pypdf import PdfReader, PdfWriter

VERSION = "0.4"
REPORT_DATE = date(2026, 11, 13)
CUTOFF = "2026-11-12"
CURRENT_WEEK = 10
TEMPLATE = Path("C:/Users/Laptop_PC/Downloads/AI.SW 융합프로젝트_주간보고서_Template_v0.3 (1).pdf")
PREVIOUS = ROOT / "output/pdf/Revealed_진행현황_주간보고서_v0.3.pdf"
OUT = ROOT / "output/pdf/Revealed_진행현황_주간보고서_v0.4.pdf"
QA = ROOT / "tmp/weekly_2026_11_13/v0_4"
PUBLIC = "https://github.com/a77315829-byte/preference-prompt-tool/tree/codex/system-design-2026-11-12/docs/system-design"
GRAY, MUTED, TEAL, NAVY = "#515151", "#626A73", "#158C80", "#082452"


class ReportPage(Page):
    def footer(self, number, backup=False, old_number=None):
        self.rect(0, 514, 780, 26, "#FFFFFF")
        label = (f"과거 백업 | 11/06 v0.3 원문 {old_number}쪽 | 현재 실적·계획·판정은 3~10쪽"
                 if backup else "Revealed | AI/SW융합프로젝트 | 2026.11.13 | 10주차 | 실적 확인 11/12까지")
        self.text(label, 34, 520, 620, 8, MUTED, maxh=13)
        self.text(f"v{VERSION}   {number}", 657, 518, 89, 9, MUTED, maxh=15, align=2)

    def note(self, value, y=478):
        self.text(value, 35, y, 710, 9, MUTED, maxh=29)

    def table(self, headings, rows, widths, y=120, heights=None, size=10.5):
        assert sum(widths) == 712
        heights = heights or [46] * len(rows)
        x = 34
        for label, width in zip(headings, widths):
            self.rect(x, y, width, 29, GRAY)
            self.text(label, x+8, y+6, width-16, 10.5, "#FFFFFF", True, maxh=18)
            x += width
        y += 29
        for i, (row, height) in enumerate(zip(rows, heights)):
            x = 34
            self.rect(34, y, 712, height, "#F1F4F5" if i % 2 == 0 else "#FFFFFF")
            for value, width in zip(row, widths):
                self.text(value, x+8, y+8, width-16, size, maxh=height-14)
                self.line(x, y, x, y+height, "#DCE1E3", .5)
                x += width
            self.line(746, y, 746, y+height, "#DCE1E3", .5)
            self.line(34, y+height, 746, y+height, "#DCE1E3", .5)
            y += height
        return y


def cover():
    original = PdfReader(TEMPLATE).pages[0]
    p = ReportPage()
    p.text("선호 기반 프롬프트 자동 생성 도구", 35, 192, 463, 20, "#FFFFFF", True, maxh=32)
    p.text("팀 Revealed  ·  윤정우 · 고차원", 35, 228, 465, 14, "#FFFFFF", maxh=24)
    p.text("2026.11.13 보고  |  10주차  |  v0.4", 35, 379, 710, 15, bold=True, maxh=25)
    p.text("금주 11/07 ~ 11/13   |   차주 11/14 ~ 11/20", 35, 412, 710, 13, MUTED, maxh=22)
    p.text("작성·실적 확인: 11/12까지  ·  본 보고 1~3쪽  ·  검증과 지난주 계획 대조는 백업", 35,
           443, 710, 10.5, MUTED, maxh=18)
    original.merge_page(p.finish())
    return original


def wbs():
    p = ReportPage()
    p.header("1. 프로젝트 일정 - WBS",
             "1주차 09/11 ~ 15주차 12/18  |  보고일 11/13, 현재 10주차  |  독립 검증·전체 설계 정리 후 통합 안정화", 2)
    grid_x, cw, y0, rh = 304, 442/15, 151, 32
    rows = [
        ("분석", "1.1", "주제·요구 정리", "검증 목표 구체화", "공동", 0),
        ("분석", "1.2", "선호·코딩 실험", "새 과제 결과 확보", "고차원", 1),
        ("설계", "2.1", "설계문서 작성·검토", "전체 설계서 v1.0", "윤정우", 4),
        ("구현", "3.1", "개인 지침·재사용", "복귀·요약 조건 보완", "윤정우", 2),
        ("구현", "3.2", "팀 조합·인수인계", "권한·팀 지침 보완", "윤정우", 3),
        ("검증", "4.1", "통합 검사·복귀 보완", "최신 전체 재검사 필요", "공동", 5),
        ("검증", "4.2", "독립 평가·권한 검증", "출력 검증·통합 잔여", "공동", 6),
        ("이행", "5.1", "운영 점검·시연 안정화", "로컬 확인·배포 미완료", "윤정우", 7),
        ("안정화", "5.2", "최종 결과·발표", "예정", "공동", 8),
    ]
    # Activities through Nov 12 fall in semester week 9, despite the week-10 report.
    new_activity = {0, 1, 2, 3, 4, 5, 6, 7}
    p.rect(34, 111, 712, 40, GRAY)
    for x, width, label in [(34,35,"단계"),(69,31,"ID"),(100,159,"작업·산출물"),(259,45,"담당")]:
        p.text(label, x+2, 122, width-4, 9.5, "#FFFFFF", True, maxh=17, align=1)
    current_x = grid_x+(CURRENT_WEEK-1)*cw
    p.rect(current_x, 111, cw, 40, "#B54A2F")
    for i, day in enumerate(WEEKS):
        x = grid_x+i*cw
        p.text(f"{i+1}주", x, 116, cw, 9.4, "#FFFFFF", True, maxh=15, align=1)
        p.text(day.strftime("%m/%d"), x, 135, cw, 7.8, "#FFFFFF", maxh=12, align=1)
    for ri, (phase, wid, task, status, owner, wi) in enumerate(rows):
        y = y0+ri*rh
        p.rect(34, y, 712, rh, "#F1F4F5" if ri%2 else "#FFFFFF")
        p.rect(current_x, y, cw, rh, "#FFF0D9")
        p.text(phase,36,y+10,31,8.3,maxh=14,align=1)
        p.text(wid,71,y+10,27,8.7,maxh=14,align=1)
        p.text(task,106,y+3,149,9.3,bold=True,maxh=14)
        p.text(status,106,y+17,149,8,MUTED,maxh=13)
        p.text(owner,261,y+10,41,8.6,maxh=14,align=1)
        plan, actual = (list(v) for v in OLD_WBS[wi][3:])
        if wi in new_activity:
            actual = sorted(set(actual+[9]))
        if wi in {0, 1, 2, 3, 6}:
            plan = sorted(set(plan+[9,10,11]))
        for week in plan:
            p.rect(grid_x+(week-1)*cw+3,y+9,cw-6,14,"#E5EAEE","#8A9EAD")
        for week in actual:
            p.rect(grid_x+(week-1)*cw+5,y+11,cw-10,10,TEAL)
        p.line(34,y+rh,746,y+rh,"#DCE1E3",.5)
    for x in [34,69,100,259]+[grid_x+i*cw for i in range(16)]:
        p.line(x,y0,x,y0+len(rows)*rh,"#DAE1E4",.5)
    for x, color, label, width in [(35,"#E5EAEE","학기 일정안",110),(180,TEAL,"기록으로 확인한 활동",170),(408,"#FFF0D9","보고일 10주차",170)]:
        p.rect(x,455,14,9,color,"#8A9EAD")
        p.text(label,x+20,450,width,10,maxh=17)
    p.note("주차는 금요일 시작. 11/09~12 실적은 9주차 칸에 표시하고, 11/13 보고 위치는 10주차로 표시.<br/>"
           "초록 칸은 활동 기록이며 전체 작업 완료율이 아님. 담당은 기존 계획 기준, 차주 실행 일정은 3·9쪽 참조.")
    return p.finish()


def weekly():
    p = ReportPage()
    p.header("2. 프로젝트 진행현황", "", 3)
    for x,label,color in [(34,"금주 실적 (11/07 ~ 11/13)","#808080"),(390,"차주 계획 (11/14 ~ 11/20)",GRAY)]:
        p.rect(x,84,356,32,color)
        p.text(label,x+9,89,338,13,"#FFFFFF",True,maxh=21,align=1)
    for x in [34,335,390,691,746]:
        p.line(x,116,x,400,"#C7CDD0",.7)
    for x in [34,390,746]:
        p.line(x,400,x,494,"#C7CDD0",.7)
    left = [
        ("개인 지침·사용 화면", "초안·GEPA 결과 복귀와 재사용 보완<br/>요약 조건 충돌 처리·코딩 두 기능 구분", "11/09<br/>~11/10"),
        ("팀 공유·업무 연결", "팀 권한·지침 조합·내보내기 보완<br/>관련 검사 통과, 두 계정 종합 시연 잔여", "11/09<br/>~11/10"),
        ("설계·검증·운영", "전체 분석·설계서 97쪽과 근거 공개<br/>11/09 전체 1,160개 통과·최신 재검사 필요", "11/09<br/>~11/12"),
        ("요약·코딩 독립 검증", "요약 새 원문 9개·코딩 각 8과제 비교<br/>수동 대비 동률, GEPA 원본 유지", "11/10<br/>~11/12"),
    ]
    right = [
        ("입력·지침 경계 보완 (윤정우)", "요약 길이 정책·조건 충돌 경로 통일<br/>React 한국어·영어 지침 의미 맞추기", "~11/16"),
        ("팀 기능·권한 통합 검사 (공동)", "두 계정 공유·첨부·회수·충돌 시연<br/>비교 세션 접근 정책 결정·검사", "~11/18"),
        ("최신 전체 회귀·문서 갱신 (공동)", "Python·프론트 전체 검사와 빌드<br/>요구→화면→API·DB 및 시연 결과 갱신", "~11/19"),
        ("변경 지침 재검증 (고차원·공동)", "새 원문·과제와 기준을 생성 전 고정<br/>수동과 재비교·유료 API 없이 진행", "~11/20"),
    ]
    for x, items in [(34,left),(390,right)]:
        for i,(title,body,day) in enumerate(items):
            y=124+i*68
            p.rect(x+9,y+6,3.5,3.5,"#111111")
            p.text(title,x+19,y,277,11.8,bold=True,maxh=19)
            p.text(body,x+19,y+22,277,10.6,maxh=33)
            p.text(day,x+304,y+15,48,8.8,maxh=28,align=1)
    for x,title,body in [
        (34,"주요 이슈 및 의사결정 사항",
         "목표: 명시 조건 전달·내용 보존 검증.<br/>수동 대비 우위·사람의 편의성은 미입증.<br/>지난주 계획: 2묶음 완료·2묶음 일부 완료."),
        (390,"프로젝트 요청 사항",
         "두 계정 시연 분담·차주 완료 기준 확인.<br/>최신 전체 회귀·공개 배포는 완료 아님.<br/>실적은 11/12까지, 상세 근거는 5~10쪽."),
    ]:
        p.rect(x,400,356,30,"#EEEEEE")
        p.text(title,x+8,406,340,11.7,bold=True,maxh=20,align=1)
        p.text(body,x+10,439,336,10.7,maxh=47)
    for y in [400,430,494]:
        p.line(34,y,746,y,"#C7CDD0",1.5 if y==494 else .7)
    return p.finish()


def backup_index():
    p=ReportPage()
    p.header("[Backup]", "현재 근거는 5~10쪽  |  이전 상세 기록과 그림은 11~28쪽에 보존",4)
    sections=[
        ("5쪽  지난주 계획 대비 완료 여부", "v0.3 본문 3쪽의 네 계획을 구현·검사·미완료 기준으로 대조"),
        ("6~7쪽  이번 주 독립 검증 결과", "요약의 조건·내용 보존, 코딩 두 기능의 타입·동작·조건을 분리 보고"),
        ("8~10쪽  설계서·차주 완료 기준·근거", "97쪽 전체 설계서, 남은 통합 검증, 생성 전 평가 기준, 원자료 위치"),
        ("11~28쪽  11/06 보고의 과거 백업", "기존 기능·실험·설계 도식·화면 보존. 당시 계획·이슈는 현재 판정이 아님"),
    ]
    for i,(title,body) in enumerate(sections):
        y=123+i*73
        p.rect(36,y+8,4,4,"#111111")
        p.text(title,51,y,694,15,bold=True,maxh=24)
        p.text(body,51,y+31,694,11.2,MUTED,maxh=22)
    p.note("보고 기간은 기존 v0.3의 토~금 양식을 계승. 11/13 예정 보고용이며 실제 완료 기록은 11/12까지다.<br/>"
           "이번 요약·현재 코딩 검증은 유료 모델 API 0회. 과거 Luna 유료 파일럿과 구별하며 Codex 사용량은 소비한다.",465)
    return p.finish()


PLAN_AUDIT = [
    {"plan":"저장·재사용과 복귀 보완", "status":"완료(구현·관련 검사)",
     "evidence":["docs/history/2026-11-09_microstone_improvements.md","docs/history/2026-11-10_goal_and_ui_check.md"],
     "limits":"대표 연결 시나리오 3개는 JSDOM+실제 Python 함수·임시 DB이며 실제 HTTP/재로그인/OS 클립보드는 아님. 유료 GEPA 실호출 미실시."},
    {"plan":"팀 기능·권한 점검", "status":"일부 완료",
     "evidence":["docs/history/2026-11-09_coding_workflow.md","docs/system-design/chapters/08-operations-quality.md"],
     "limits":"권한·버전·원본 보존 관련 검사와 단일 계정 화면 기록은 있음. 두 브라우저 계정의 공유→첨부→회수→충돌 전체 시연을 마친 기록은 확인하지 못함."},
    {"plan":"설계 대응·전체 회귀 확인", "status":"일부 완료",
     "evidence":["docs/system-design/validation.json","docs/history/2026-11-09_coding_workflow.md","tmp/workflow-full-tests.log"],
     "limits":"전체 설계서 완료. 11/09 not-api 1160 passed, 1 skipped, 16 deselected. 이후 11/10~12 변경을 모두 포함한 최신 전체 재검사 기록은 확인하지 못함."},
    {"plan":"독립 평가 준비", "status":"완료(새 평가 실행 포함)",
     "evidence":["benchmarks/summary_contract_revision/results/2026-11-10/scores.json","benchmarks/coding_react_current/results/2026-11-12/scores.json","benchmarks/react_style_current/results/2026-11-12/scores.json"],
     "limits":"요약 9원문과 코딩 별도 8과제씩 첫 답변 평가 완료. 이전 코딩 1~3차와 같은 조건의 4차 확증 또는 실제 사용자 실험은 아님."},
]


def previous_plan():
    p=ReportPage()
    p.header("[Backup] 지난주 계획은 모두 끝났나?", "v0.3의 11/07~11/13 계획 대조  |  판단 기준일 11/12  |  두 묶음 완료·두 묶음 일부 완료",5)
    rows=[
        ["저장·재사용<br/>복귀 보완<br/><b>완료*</b>",
         "초안 24시간 임시 보존·GEPA 작업 7일 보관.<br/>계정별 복귀·중단 상태 처리, 대표 연결 3시나리오<br/>및 저장/재사용 2,820 대조 사례 확인.",
         "*구현·관련 검사 기준.<br/>실제 HTTP·재로그인·클립보드<br/>종합 시연, 유료 실행은 별도."],
        ["팀 기능·권한<br/><b>일부 완료</b>",
         "팀 권한·초대·버전 충돌·원본 보존 검사.<br/>팀 생성·조합·내보내기 화면 확인.<br/>두 계정 전체 사용자 흐름 완료 기록은 미확인.",
         "공유→첨부→수신자 변경·회수<br/>→이전 링크 거절→버전 충돌을<br/>두 브라우저 계정에서 기록."],
        ["설계 대응<br/>전체 회귀<br/><b>일부 완료</b>",
         "97쪽 설계서·요구/화면/API/DB 대응 완료.<br/>11/09 Python 전체 1,160 통과·1 건너뜀.<br/>그 뒤 변경은 개별 검사·실험 근거로 구분.",
         "최신 코드 전체 Python·프론트<br/>검사 및 빌드 재실행 필요.<br/>과거 통과를 현재 통과로 이월 금지."],
        ["독립 평가<br/><b>완료*</b>",
         "새 과제와 판정 기준을 고정하고 실제 실행.<br/>요약 9원문, 코딩 두 기능 각 8과제.<br/>첫 답변·실행 결과·검토 불일치까지 보존.",
         "*새 평가 준비·실행 완료.<br/>기존 1~3차의 4차 확증과 다름.<br/>사람의 편의성·시간은 미측정."],
    ]
    p.table(["지난주 계획·판정","확인한 근거","남은 범위·완료 조건"],rows,[136,340,236],heights=[79,79,79,79],size=10.4)
    p.note("완료율은 계산하지 않음. 2,820은 중복 조건을 포함한 프로그램 대조 사례 수이며 사람/독립 과제 수가 아님.<br/>"
           "근거: [H1~H3, E1~E3, D1] (10쪽). 공개 배포·Streamlit 삭제는 여전히 완료로 처리하지 않는다.")
    return p.finish()


def summary_results():
    p=ReportPage()
    p.header("[Backup] 요약: 조건 준수와 내용 보존", "11/10 최종 비교  |  개선에 쓰지 않은 MACSum 영어 원문 9개  |  별도 유료 모델 API 0회",6)
    p.text("수정: 보존할 문장 확인 → 조건 충돌 시 생성 보류 → 사용자가 해결 방법 선택",35,113,710,12,bold=True,maxh=20)
    p.text("평가도 실제 지시문과 같은 분량·표현 조건으로 맞췄다. 수동·당시 현재본·수정본에 같은 보존 대상과<br/>"
           "해결된 조건을 제공하고, 핵심 명제·지정 내용·사실 문제는 별도로 판정했다.",35,144,710,11,maxh=33)
    p.table(["독립 지표","수동 프롬프트","당시 현재본","충돌 처리 수정본"],[
        ["분량·표현 동시 준수","9/9","9/9","9/9"],
        ["핵심 명제 보존","25/27","25/27","25/27"],
        ["지정 보존 내용","25/27","25/27","25/27"],
        ["사실 문제 표시 응답","0/9","0/9","0/9"],
    ],[232,160,160,160],y=193,heights=[34]*4,size=11)
    p.text("해석: 세 방식 동률. 수정본의 내용 보존 우위는 확인되지 않았으며 누락 2/27이 남았다.",35,374,710,11.5,bold=True,maxh=20)
    p.text("GEPA: 개선 6개·후보 선택 6개·최종 9개 분리. 후보 선택 점수는 원본 0.7778, 후보 0.7222/0.6667로<br/>"
           "원본을 채택했다. 무조건 실행할 근거가 없어 선택적으로 유지한다. 실패 성찰 실험도 안정적 이득은 미확보.",
           35,411,710,10.7,maxh=34)
    p.note("두 검토자의 집계 일치. 27은 9개 원문의 핵심 명제 수이며 독립 원문 27개가 아님. 실제 사용자 취향은 미검증.<br/>"
           "근거: [E1, E4, D1] (10쪽). 과거 GEPA 평가의 문장 분리 오류·비채택 후보 비교 한계도 설계서 9장에 보존.")
    return p.finish()


def coding_results():
    p=ReportPage()
    p.header("[Backup] 코딩 두 기능: 각각 새 과제로 검증", "11/12  |  기능별 새 합성 TypeScript/React 8과제 × 일반·수동·제품 = 각 24개 첫 답변",7)
    p.table(["기능 / 독립 지표","일반 요청","수동 프롬프트","제품 프롬프트"],[
        ["AI 답변 방식 4항목 · strict 타입","8/8","8/8","8/8"],
        ["AI 답변 방식 · 실제 DOM 검사","69/69","69/69","69/69"],
        ["설명·주석·구성·출력 모두 일치","0/8","8/8","8/8"],
        ["React 코드 스타일 3축 · strict 타입","8/8","8/8","8/8"],
        ["React 스타일 · 실제 DOM 검사","56/56","56/56","56/56"],
        ["구성·스타일 값·타입 모두 일치","1/8","8/8","8/8"],
    ],[292,140,140,140],y=115,heights=[33]*6,size=10.7)
    p.text("확보: 지정 조건을 지침으로 전달했고, 이번 과제의 타입·동작을 유지했다. 수동 대비 우위는 없음.",
           35,356,710,11.3,bold=True,maxh=20)
    p.text("• 일반에는 취향 조건을 주지 않았으므로 낮은 조건 일치는 지시 위반이 아니다.<br/>"
           "• 4항목 판정 96/96 일치, 스타일 판정 71/72 일치. 불일치 1건은 보존했고 전체 조건 집계는 같았다.<br/>"
           "• 알려진 목표를 넣은 작은 합성 과제다. 사람의 선호 발견·편의성·수정 시간·운영 품질은 미측정.<br/>"
           "• React 영어 지침+공통 strict 예외 조건의 결과. 한국어와 의미 차이는 남아 있으며 차주 보완 대상.",
           35,389,710,10.5,maxh=65)
    p.note("ReactDOM/JSDOM 동작 실행과 실제 TypeScript 검사를 수행. 전체 브라우저·보안 검사 또는 운영 GEPA의 검증이 아님.<br/>"
           "근거: [E2, E3, D1] (10쪽). 두 기능 점수는 합산하지 않으며 Codex 사용량과 별도로 유료 모델 API 호출은 0회.")
    return p.finish()


def design_results():
    p=ReportPage()
    p.header("[Backup] 전체 분석·설계서와 현재 범위", "주간보고와 별도 산출물  |  Revealed 분석·설계서 v1.0 · 97쪽 · 11/12 기준",8)
    p.table(["설계 영역","이번에 정리한 내용"],[
        ["분석·요구사항","제품 목적·대상·범위, 기능/비기능 요구, 근거와 미검증 주장 구분"],
        ["사용자·화면","상세 유즈케이스 24개, 논리 화면 18개, 입력·오류·권한·복귀 상태"],
        ["처리·구조","선택·조건 해결·저장·재사용·팀 연결 처리와 클래스/시퀀스 등 도식 21개"],
        ["API·데이터","GET/POST 경로 90개, SQLite 테이블 16개, migration 14와 데이터 사전"],
        ["운영·검증","접근 권한·비용·저장·실패 복구, 독립 평가 원자료·한계, 요구 추적"],
    ],[145,567],y=118,heights=[40]*5,size=10.6)
    p.text("GitHub에 문서 전용 공간과 읽기 전용 검증 근거를 게시했습니다.",35,369,710,12,bold=True,maxh=21)
    p.text(f'<link href="{PUBLIC}" color="#164E8A"><u>전체 분석·설계서 및 원자료 열기</u></link>  ·  codex/system-design-2026-11-12  ·  8531b21',
           35,400,710,10.8,maxh=18)
    p.text("운영 보완: 비교 메모리 세션의 계정 접근 정책, 긴 요약 원문의 절단/거절 방식 차이,<br/>"
           "React 영어·한국어 지침 의미 차이를 발견했다. 문서화와 제품 수정 완료를 구별한다.",35,435,710,10.8,maxh=33)
    p.note("기준: 로컬 HEAD 4302412 + 진행 중이던 요약 수정. 문서 게시가 앱 변경의 원격 반영·배포 완료를 의미하지 않는다.<br/>"
           "근거: [D1] (10쪽). 전체 PDF를 렌더링해 확인했으며 코드·데이터 사전·실험 사본의 해시를 기록했다.")
    return p.finish()


def next_acceptance():
    p=ReportPage()
    p.header("[Backup] 차주 계획과 완료 기준", "11/14~11/20 계획  |  새 기능 확대보다 입력 경계·권한·최신 회귀를 우선",9)
    p.table(["계획·담당·기한","완료로 판단할 근거","범위·실행 원칙"],[
        ["입력·지침 의미 정렬<br/>윤정우 / ~11/16",
         "요약 두 경로의 길이 제한·오류 안내 대조.<br/>한·영 React 3축 지침의 예외·역할 분리 정렬.<br/>경계값·조건 충돌·출력 회귀 사례 통과.",
         "변경 근거와 전후 지침을 기록.<br/>기존 저장본을 자동 덮어쓰지 않음."],
        ["권한·두 계정 통합<br/>공동 / ~11/18",
         "공유·첨부·대상 변경·회수·버전 충돌 실행.<br/>원본 보존·접근 거절·로그아웃 복귀 확인.<br/>비교 세션 접근 정책과 관련 검사 확정.",
         "임시 계정·테스트 DB 사용.<br/>계정별 화면과 서버 응답을<br/>함께 기록."],
        ["최신 전체 회귀<br/>공동 / ~11/19",
         "동일 코드 기준 Python not-api, 프론트 단위<br/>검사, 빌드·대표 시연의 결과/실패 원인 기록.<br/>설계서·요구 추적·근거 파일 동기화.",
         "실패·건너뜀·제외를 따로 보고.<br/>코드 SHA·환경·날짜 고정.<br/>배포는 별도 완료 기준."],
        ["변경 지침 재검증<br/>고차원·공동 / ~11/20",
         "변경한 경로에 한해 새 원문/과제·수동 기준<br/>·평가 기준을 생성 전에 고정. 첫 응답 보존.<br/>조건·내용/타입·동작 결과를 별도로 보고.",
         "유료 API 없이 독립 보조 에이전트.<br/>우위가 없으면 동률/저하로 기록.<br/>표본 수·채택 기준은 실행 전 확정."],
    ],[161,328,223],y=115,heights=[80,80,80,80],size=10.2)
    p.note("실제 사용자 모집이 없는 이번 단계에서는 만족도·시간 절감·숨은 취향 추정 정확도를 성공 지표로 주장하지 않는다.<br/>"
           "과거 4차 확증, 공개 배포, 로그인하지 못한 Streamlit 삭제를 이번에 완료한 일로 보고하지 않는다.")
    return p.finish()


SOURCES = [
    ("H1", "복귀·권한 개선 (11/09)", "docs/history/2026-11-09_microstone_improvements.md"),
    ("H2", "팀 지침·전체 회귀 (11/09)", "docs/history/2026-11-09_coding_workflow.md"),
    ("H3", "재사용·두 경로·UI 확인 (11/10)", "docs/history/2026-11-10_goal_and_ui_check.md"),
    ("E1", "요약 조건·보존 최종 비교", "benchmarks/summary_contract_revision/results/2026-11-10/scores.json"),
    ("E2", "AI 답변 방식 4항목 비교", "benchmarks/coding_react_current/results/2026-11-12/scores.json"),
    ("E3", "React 코드 스타일 3축 비교", "benchmarks/react_style_current/results/2026-11-12/scores.json"),
    ("E4", "실제 GEPA 오프라인 탐색", "benchmarks/summary_gepa_offline/README.md"),
    ("D1", "전체 설계서·문서 QA", "docs/system-design/validation.json"),
]


def sources():
    p=ReportPage()
    p.header("[Backup] 보고 근거와 읽는 순서", "수치는 실험 원자료와 대조  |  기존 결과를 재생성·수정하지 않고 보고에 인용",10)
    y=116
    for sid,title,path in SOURCES:
        p.text(f"[{sid}] {title}",35,y,710,10.6,bold=True,maxh=17)
        p.text(path,35,y+18,710,8.8,MUTED,maxh=14)
        y+=39
    p.text(f'<link href="{PUBLIC}" color="#164E8A"><u>공개 설계서·검증 근거 폴더</u></link>  →  chapters/09-verification.md, evidence/',
           35,442,710,10.5,maxh=18)
    p.note("위 H/E 경로는 로컬 저장소 기준. 공개 문서의 실험 사본은 원본 해시와 대조했으며 전체 앱 코드를 공개한 것은 아님.<br/>"
           "지난주 계획 원본은 v0.3 3쪽. 11~28쪽은 그 보고의 과거 백업이며 최신 수치·계획은 앞의 3~9쪽을 적용.")
    return p.finish()


def verify_evidence():
    def read(path):
        return json.loads((ROOT/path).read_text(encoding="utf-8"))
    summary=read(SOURCES[3][2])
    for reviewer in ["a","b"]:
        for arm in ["manual","current","revised"]:
            values=summary["by_reviewer"][reviewer][arm]
            assert (values["outputs"],values["joint_pass"],values["core_preserved"],values["core_total"],values["factual_issue_outputs"]) == (9,9,25,27,0)
    for source,checks,section,key,general in [(SOURCES[4][2],69,"target_match_by_reviewer","all_four",0),
                                            (SOURCES[5][2],56,"style_by_reviewer","all_three",1)]:
        data=read(source)
        for arm in ["general","manual","product"]:
            values=data["technical"][arm]
            assert values["clean_type_pass"] == values["runtime_pass"] == 8
            assert values["runtime_checks_passed"] == values["runtime_checks_total"] == checks
            for reviewer in ["a","b"]:
                assert data[section][reviewer][arm][key] == (general if arm=="general" else 8)
    assert "1160 passed, 1 skipped, 16 deselected" in (ROOT/"tmp/workflow-full-tests.log").read_text(encoding="utf-8")
    assert len(PdfReader(ROOT/"docs/system-design/Revealed_Analysis_Design_v1.0.pdf").pages)==97
    paths=[PREVIOUS,TEMPLATE,ROOT/"docs/system-design/Revealed_Analysis_Design_v1.0.pdf"]+[ROOT/path for _,_,path in SOURCES]
    return {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def main():
    hashes=verify_evidence()
    previous=PdfReader(PREVIOUS)
    assert len(previous.pages)==22
    writer=PdfWriter()
    fns=[cover,wbs,weekly,backup_index,previous_plan,summary_results,coding_results,design_results,next_acceptance,sources]
    for fn in fns:
        writer.add_page(fn())
    for i in range(4,len(previous.pages)):
        page=previous.pages[i]
        footer=ReportPage()
        footer.footer(len(writer.pages)+1,True,i+1)
        page.merge_page(footer.finish())
        writer.add_page(page)
    titles=["표지","1. 프로젝트 일정 - WBS","2. 프로젝트 진행현황","Backup",
            "지난주 계획 대비 완료 여부","요약 검증","코딩 두 기능 검증","전체 설계서","차주 완료 기준","근거 목록"]
    for i,title in enumerate(titles):
        writer.add_outline_item(title,i)
    writer.add_outline_item("11/06 보고의 과거 백업",10)
    writer.add_metadata({"/Title":"Revealed 주간보고서 v0.4 · 2026-11-13 · 10주차",
                         "/Author":"윤정우 · 고차원","/Subject":"금주 실적·차주 계획·지난주 계획 달성 대조 / 11월 12일까지 확인"})
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open("wb") as stream:
        writer.write(stream)
    for path,digest in hashes.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest, path
    QA.mkdir(parents=True,exist_ok=True)
    manifest={"version":VERSION,"report_date":REPORT_DATE.isoformat(),"evidence_cutoff":CUTOFF,"week":CURRENT_WEEK,
              "report_period":["2026-11-07","2026-11-13"],"next_period":["2026-11-14","2026-11-20"],
              "pages":len(writer.pages),"main_pages":[1,2,3],"current_backup_pages":[4,5,6,7,8,9,10],
              "historical_backup":{"v0.3":[5,22],"v0.4":[11,28]},
              "output":str(OUT.relative_to(ROOT)),"sha256":hashlib.sha256(OUT.read_bytes()).hexdigest(),
              "previous_plan_audit":PLAN_AUDIT,"read_only_sources":hashes,
              "checks":{"numeric_evidence":True,"paragraph_overflow":False,"previous_sources_unchanged":True},
              "visual_review":"pending"}
    (QA/"build_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    (HERE/"plan_audit.json").write_text(json.dumps(PLAN_AUDIT,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Written {OUT}: {len(writer.pages)} pages; numeric evidence checked; sources unchanged")


if __name__ == "__main__":
    main()

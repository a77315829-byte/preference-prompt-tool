"""Restore the course template and consolidate four weekly sections.

v0.1 and v0.2 are immutable inputs. The first three pages follow the original
cover -> WBS -> weekly actuals/plans order. Detailed source bodies stay in backup.
"""
from pathlib import Path
import hashlib
import json

from pypdf import PdfReader, PdfWriter
from build_report_v0_2 import Page, ROOT, WEEKS, CURRENT_WEEK, BACKUPS, WBS

VERSION = "0.3"
SOURCE = ROOT / "output/pdf/Revealed_진행현황_주간보고서_v0.1.pdf"
PREVIOUS = ROOT / "output/pdf/Revealed_진행현황_주간보고서_v0.2.pdf"
TEMPLATE = Path("C:/Users/Laptop_PC/Downloads/AI.SW 융합프로젝트_주간보고서_Template_v0.3 (1).pdf")
OUT = ROOT / f"output/pdf/Revealed_진행현황_주간보고서_v{VERSION}.pdf"
QA = ROOT / "tmp/weekly_2026_11_06/v0_3"
GRAY, MUTED, TEAL, NAVY = "#515151", "#626A73", "#158C80", "#082452"


class ReportPage(Page):
    def footer(self, number, backup=False, old_number=None):
        self.rect(0, 514, 780, 26, "#FFFFFF")
        label = (f"백업 | v0.1 상세 기록 · 원문 {old_number}쪽 | 금주·차주 요약은 3쪽"
                 if backup else "Revealed | AI/SW융합프로젝트 | 2026.11.06 | 9주차")
        self.text(label, 34, 520, 620, 8, MUTED, maxh=13)
        self.text(f"v{VERSION}   {number}", 657, 518, 89, 9, MUTED,
                  maxh=15, align=2)


def cover():
    # Reuse the actual supplied cover, including university identity, colors,
    # semester label and original typography; overlay only team/report fields.
    original = PdfReader(TEMPLATE).pages[0]
    p = ReportPage()
    p.text("선호 기반 프롬프트 자동 생성 도구", 35, 192, 463, 20,
           "#FFFFFF", True, maxh=32)
    p.text("팀 Revealed  ·  윤정우 · 고차원", 35, 228, 465, 14,
           "#FFFFFF", maxh=24)
    p.text("2026.11.06 보고  |  9주차  |  v0.3", 35, 379, 710, 15,
           bold=True, maxh=25)
    p.text("금주 10/31 ~ 11/06   |   차주 11/07 ~ 11/13", 35, 412,
           710, 13, MUTED, maxh=22)
    p.text("금주 실적과 차주 계획을 한 페이지로 정리  ·  상세 근거는 백업", 35,
           443, 710, 10.5, MUTED, maxh=18)
    original.merge_page(p.finish())
    return original


def wbs():
    p = ReportPage()
    p.header("1. 프로젝트 일정 - WBS",
             "1주차 09/11 ~ 15주차 12/18  |  보고일 11/06, 현재 9주차  |  핵심 구현 후 통합·독립 검증 준비", 2)
    # Preserve the template's stage/ID/task/owner columns and grey header.
    grid_x, cw, y0, rh = 304, 442/15, 151, 32
    rows = [
        ("분석", "1.1", "주제·요구 정리", "기존 기반 확보", "공동", 0),
        ("분석", "1.2", "선호·코딩 실험", "1~3차 결과 확보", "고차원", 1),
        ("설계", "2.1", "설계문서 작성·검토", "작성·검수 반영", "윤정우", 4),
        ("구현", "3.1", "개인 지침·재사용", "핵심 구현", "윤정우", 2),
        ("구현", "3.2", "팀 조합·인수인계", "핵심 구현", "윤정우", 3),
        ("검증", "4.1", "통합 검사·복귀 보완", "문제 확인·진행", "공동", 5),
        ("검증", "4.2", "독립 평가·권한 검증", "조건·과제 준비", "공동", 6),
        ("이행", "5.1", "운영 점검·시연 안정화", "실행 구조 준비", "윤정우", 7),
        ("안정화", "5.2", "최종 결과·발표", "예정", "공동", 8),
    ]
    p.rect(34, 111, 712, 40, GRAY)
    for x,w,label in [(34,35,"단계"), (69,31,"ID"), (100,159,"작업·산출물"), (259,45,"담당")]:
        p.text(label,x+2,122,w-4,9.5,"#FFFFFF",True,maxh=17,align=1)
    current_x=grid_x+(CURRENT_WEEK-1)*cw
    p.rect(current_x,111,cw,40,"#B54A2F")
    for i,day in enumerate(WEEKS):
        x=grid_x+i*cw
        p.text(f"{i+1}주",x,116,cw,9.4,"#FFFFFF",True,maxh=15,align=1)
        p.text(day.strftime("%m/%d"),x,135,cw,7.8,"#FFFFFF",maxh=12,align=1)
    for ri,(phase,wid,task,status,owner,wi) in enumerate(rows):
        y=y0+ri*rh
        p.rect(34,y,712,rh,"#F1F4F5" if ri%2 else "#FFFFFF")
        p.rect(current_x,y,cw,rh,"#FFF0D9")
        p.text(phase,36,y+10,31,8.3,maxh=14,align=1)
        p.text(wid,71,y+10,27,8.7,maxh=14,align=1)
        p.text(task,106,y+3,149,9.3,bold=True,maxh=14)
        p.text(status,106,y+17,149,8.0,MUTED,maxh=13)
        p.text(owner,261,y+10,41,8.6,maxh=14,align=1)
        plan,actual=WBS[wi][3:]
        for week in plan:
            x=grid_x+(week-1)*cw
            p.rect(x+3,y+9,cw-6,14,"#E5EAEE","#8A9EAD")
        for week in actual:
            x=grid_x+(week-1)*cw
            p.rect(x+5,y+11,cw-10,10,TEAL)
        p.line(34,y+rh,746,y+rh,"#DCE1E3",.5)
    for x in [34,69,100,259]+[grid_x+i*cw for i in range(16)]:
        p.line(x,y0,x,y0+len(rows)*rh,"#DAE1E4",.5)
    p.rect(35,455,14,9,"#E5EAEE","#8A9EAD")
    p.text("학기 일정안",55,450,110,10,maxh=17)
    p.rect(180,455,14,9,TEAL)
    p.text("기록으로 확인한 활동",200,450,170,10,maxh=17)
    p.rect(408,455,14,9,"#FFF0D9","#B54A2F")
    p.text("현재 9주차",429,450,120,10,maxh=17)
    p.text("금주 재정리한 학기 일정안. 과거 1~7주차의 주별 실적·완료율은 미집계이며, 채운 칸도 전체 완료를 뜻하지 않음.<br/>"
           "8주차: 11/03~05 구현·실험·검사·문서화 / 9주차: UML 검수 반영·로컬 재기동 확인. 향후 담당·일정은 계획.",
           35,481,710,9.0,MUTED,maxh=28)
    return p.finish()


def weekly():
    p=ReportPage()
    p.header("2. 프로젝트 진행현황", "", 3)
    # Match the supplied weekly template: two side-by-side columns, a date
    # column within each half, and the two original issue/request boxes below.
    for x,label,color in [(34,"금주 실적 (10/31 ~ 11/06)","#808080"),
                          (390,"차주 계획 (11/07 ~ 11/13)",GRAY)]:
        p.rect(x,84,356,32,color)
        p.text(label,x+9,89,338,13,"#FFFFFF",True,maxh=21,align=1)
    for x in [34,335,390,691,746]:
        p.line(x,116,x,400,"#C7CDD0",.7)
    for x in [34,390,746]:
        p.line(x,400,x,494,"#C7CDD0",.7)
    left=[
        ("개인 지침·사용 화면 (윤정우)",
         "환경·선호 선택 → 생성·저장·재사용 연결<br/>예시 비교·답변 확인·GEPA 경로 정리", "11/03<br/>~11/04"),
        ("팀 공유·업무 연결 (윤정우)",
         "기준 조합·출처·인수인계·첨부 구현<br/>업무 템플릿 24개와 요청문 점검 정리", "11/03<br/>~11/04"),
        ("설계·검증·운영 (윤정우·공동)",
         "별도 설계문서 작성·UML 검수 반영<br/>회귀 결과·남은 문제·로컬 실행 확인", "11/04<br/>~11/06"),
        ("기존 코딩 실험 (고차원)",
         "1~3차 결과와 재채점 근거 정리<br/>스타일 이득·2/3차 기능 저하 함께 보고", "11/03<br/>~11/04"),
    ]
    right=[
        ("저장·재사용과 복귀 보완 (윤정우)",
         "React 대표 흐름 확정·입력 보존<br/>GEPA 작업 상태·완료 결과 재열람", "~11/10"),
        ("팀 기능·권한 점검 (공동)",
         "두 계정의 공유·첨부·버전 충돌 확인<br/>조합 원본 보존·출처·연결 점검", "~11/11"),
        ("설계 대응·전체 회귀 확인 (공동)",
         "요구사항 → 화면 → API·DB 대응 검토<br/>복귀 수정 후 같은 환경의 전체 검사", "~11/12"),
        ("독립 평가 준비 (고차원)",
         "독립 과제·기능/스타일 판정 기준 확정<br/>실행 결과만 기록, 미실행은 계획 유지", "~11/13"),
    ]
    for x,items in [(34,left),(390,right)]:
        for i,(title,body,day) in enumerate(items):
            y=124+i*68
            p.rect(x+9,y+6,3.5,3.5,"#111111")
            p.text(title,x+19,y,277,11.8,bold=True,maxh=19)
            p.text(body,x+19,y+22,277,10.9,maxh=33)
            p.text(day,x+304,y+15,48,8.8,maxh=28,align=1)
    for x,title,body in [
        (34,"주요 이슈 및 의사결정 사항",
         "초안·GEPA 작업 복귀 문제 미해결.<br/>전체 회귀 재확인 필요·공개 배포 미완료.<br/>기능 저하 원인 미분리·4차 확증 미실행."),
        (390,"프로젝트 요청 사항",
         "저장·재사용 시연과 차주 검증을 우선.<br/>차주 우선순위·독립 평가 범위 의견 요청.<br/>상세 실험·검사·설계는 백업 5~22쪽 참조."),
    ]:
        p.rect(x,400,356,30,"#EEEEEE")
        p.text(title,x+8,406,340,11.7,bold=True,maxh=20,align=1)
        p.text(body,x+10,439,336,10.7,maxh=47)
    p.line(34,400,746,400,"#C7CDD0",.7)
    p.line(34,430,746,430,"#C7CDD0",.7)
    p.line(34,494,746,494,"#C7CDD0",1.5)
    return p.finish()


def backup_index():
    p=ReportPage()
    p.header("[Backup]", "상세 설명은 질문 시 활용  |  금주 실적·차주 계획의 통합 요약은 3쪽", 4)
    sections=[
        ("5~8쪽  기능별 상세 진행현황", "개인 지침 / 팀 활용 / 설계·검증·운영 / 고차원 코딩 실험"),
        ("9~11쪽  연구 연결·계획·근거 링크", "11/05 작성 당시 상세 계획은 기록으로 보존. 최신 주간 계획은 3쪽 적용"),
        ("12~20쪽  설계 참고 자료", "요구사항 / 시스템·UML / ERD·테이블 / API / 화면 정의"),
        ("21~22쪽  실제 구현 화면", "11/04 예시 계정의 개인 지침·보관함·팀 활용 화면"),
    ]
    for i,(title,body) in enumerate(sections):
        y=125+i*74
        p.rect(36,y+8,4,4,"#111111")
        p.text(title,51,y,694,15,bold=True,maxh=24)
        p.text(body,51,y+31,694,11.3,MUTED,maxh=21)
    p.text("설계문서는 별도 산출물로 관리하며, 기존 참고 도식은 요청대로 백업에 보존합니다.<br/>"
           "백업 본문·그림·수치·링크는 v0.1 그대로 두고, 쪽 번호와 백업 안내만 갱신했습니다.",
           35,454,710,10.7,MUTED,maxh=35)
    return p.finish()


def main():
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [SOURCE,PREVIOUS]}
    source=PdfReader(SOURCE)
    assert len(source.pages)==21 and CURRENT_WEEK==9
    writer=PdfWriter()
    for fn in [cover,wbs,weekly,backup_index]:
        writer.add_page(fn())
    for old_number,_ in BACKUPS:
        original=source.pages[old_number-1]
        footer=ReportPage()
        footer.footer(len(writer.pages)+1,True,old_number)
        original.merge_page(footer.finish())
        writer.add_page(original)
    for title,idx in [("표지",0),("1. 프로젝트 일정 - WBS",1),("2. 프로젝트 진행현황",2),("Backup",3)]:
        writer.add_outline_item(title,idx)
    for idx,(_,title) in enumerate(BACKUPS,start=4):
        writer.add_outline_item(title,idx)
    writer.add_metadata({"/Title":"Revealed 주간보고서 v0.3 2026년 11월 6일 9주차",
                         "/Author":"윤정우 · 고차원", "/Subject":"기존 템플릿 기반 금주 실적과 차주 계획 통합"})
    with OUT.open("wb") as f:
        writer.write(f)
    for path,digest in hashes.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest
    QA.mkdir(parents=True,exist_ok=True)
    (QA/"build_manifest.json").write_text(json.dumps({
        "version":VERSION,"report_date":"2026-11-06","week":9,"pages":len(writer.pages),
        "source":str(SOURCE.relative_to(ROOT)),"source_sha256":hashes[str(SOURCE)],
        "previous_sha256":hashes[str(PREVIOUS)],"output":str(OUT.relative_to(ROOT)),
        "template":str(TEMPLATE),"main_pages":[1,2,3],"progress_page":3,
        "backup_mapping":[{"page":i+5,"source_page":old,"title":title} for i,(old,title) in enumerate(BACKUPS)],
    },ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Written {OUT.name}: {len(writer.pages)} pages; original template; one progress page")


if __name__=="__main__":
    main()

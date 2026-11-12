"""Weekly report v0.2: three main pages, prior details retained as backup.

Historical source v0.1 is read only. Later delivered revisions must increment
VERSION and write a new output; do not replace a previous delivered version.
"""
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
import hashlib
import json

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor, white
from reportlab.platypus import Paragraph, Table, TableStyle

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
VERSION = "0.2"
REPORT_DATE = date(2026, 11, 6)
SEMESTER_START = date(2026, 9, 11)
WEEKS = [SEMESTER_START + timedelta(weeks=i) for i in range(15)]
CURRENT_WEEK = (REPORT_DATE - SEMESTER_START).days // 7 + 1
SOURCE = ROOT / "output/pdf/Revealed_진행현황_주간보고서_v0.1.pdf"
OUT = ROOT / f"output/pdf/Revealed_진행현황_주간보고서_v{VERSION}.pdf"
QA = ROOT / "tmp/weekly_2026_11_06/v0_2"
W, H = 780, 540
INK, MUTED, NAVY = "#17202D", "#63707A", "#082452"
TEAL, PALE, LINE, ORANGE = "#158C80", "#EFF5F4", "#D7DEE2", "#B54A2F"
pdfmetrics.registerFont(TTFont("MG", "C:/Windows/Fonts/malgun.ttf"))
pdfmetrics.registerFont(TTFont("MGB", "C:/Windows/Fonts/malgunbd.ttf"))
pdfmetrics.registerFontFamily("MG", normal="MG", bold="MGB")


class Page:
    def __init__(self):
        self.buf = BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=(W, H))
        self.overflows = []

    def rect(self, x, y, w, h, fill, stroke=None):
        self.c.setFillColor(HexColor(fill))
        self.c.setStrokeColor(HexColor(stroke or fill))
        self.c.setLineWidth(.6)
        self.c.rect(x, H-y-h, w, h, fill=1, stroke=bool(stroke))

    def text(self, value, x, y, w, size=11, color=INK, bold=False,
             maxh=100, align=0):
        style = ParagraphStyle("p", fontName="MGB" if bold else "MG",
                               fontSize=size, leading=size*1.36,
                               wordWrap="CJK", textColor=HexColor(color),
                               alignment=align)
        p = Paragraph(str(value), style)
        _, h = p.wrap(w, 1500)
        if h > maxh+.3:
            self.overflows.append((str(value)[:70], round(h, 1), maxh))
        p.drawOn(self.c, x, H-y-h)
        return h

    def line(self, x1, y1, x2, y2, color=LINE, width=.7):
        self.c.setStrokeColor(HexColor(color))
        self.c.setLineWidth(width)
        self.c.line(x1, H-y1, x2, H-y2)

    def footer(self, number, backup=False, old_number=None):
        # Mask only the old footer, leaving every backup body unchanged.
        self.rect(0, 514, W, 26, "#FFFFFF")
        label = (f"백업 | v0.1 상세 기록 · 원문 {old_number}쪽 | 금주 요약·최신 계획은 2쪽"
                 if backup else "Revealed | AI/SW융합프로젝트 | 보고일 2026.11.06 | 9주차")
        self.text(label, 34, 520, 620, 8.0, MUTED, maxh=13)
        self.text(f"v{VERSION}   {number}", 657, 518, 89, 9, MUTED,
                  maxh=15, align=2)

    def header(self, title, sub, number):
        self.text(title, 34, 25, 712, 21, bold=True, maxh=31)
        self.rect(34, 64, 712, 3, "#111111")
        self.text(sub, 35, 77, 710, 10.1, MUTED, maxh=28)
        self.footer(number)

    def finish(self):
        assert not self.overflows, self.overflows
        self.c.showPage()
        self.c.save()
        return PdfReader(BytesIO(self.buf.getvalue())).pages[0]


def cover():
    p = Page()
    p.text("2026년 2학기  AI/SW융합프로젝트", 36, 32, 708, 13, MUTED,
           maxh=21)
    p.rect(34, 99, 712, 231, NAVY)
    p.text("주간보고서", 58, 123, 660, 32, "#FFFFFF", True, maxh=47)
    p.text("선호 기반 프롬프트 자동 생성 도구", 60, 186, 650, 20,
           "#FFFFFF", True, maxh=34)
    p.text("팀 Revealed  |  윤정우 · 고차원", 61, 236, 650, 15,
           "#FFFFFF", maxh=25)
    p.text("2026.11.06 보고  ·  9주차  ·  v0.2", 61, 283, 650, 14,
           "#FFFFFF", maxh=24)
    p.text("금주 핵심", 35, 361, 110, 13, TEAL, True, maxh=22)
    p.text("지침 선택·저장·재사용과 팀 활용 기능을 연결하고,<br/>"
           "코딩 실험 결과와 남은 검증 과제를 함께 정리했습니다.",
           145, 359, 600, 16, bold=True, maxh=49)
    p.text("금주 10/31~11/06  |  차주 11/07~11/13", 35, 431, 710,
           12, MUTED, maxh=20)
    p.text("본 보고 1~3쪽  ·  상세 근거·설계 자료는 4쪽부터 백업", 35,
           464, 710, 11, MUTED, maxh=18)
    p.footer(1)
    return p.finish()


def progress():
    p = Page()
    p.header("1. 프로젝트 진행현황", "금주 10/31~11/06  |  차주 11/07~11/13  |  완료한 일과 남은 검증을 구분", 2)
    p.rect(34, 109, 712, 31, PALE)
    p.text("이번 주: 지침 생성에서 저장·재사용까지 연결하고, 팀 활용·설계·실험 근거를 정리", 45, 116,
           690, 11.8, NAVY, True, maxh=18)
    rows = [
        ["영역·담당", "금주 수행·확인 결과", "차주 계획·완료 기준"],
        ["개인 지침<br/><b>윤정우</b>",
         "<b>환경·4항목 선호 선택 → 지침 생성·보관·재사용 연결</b><br/>"
         "예시 비교·직접 설정, 선택 출처·본문 불일치 안내 구현.<br/>"
         "답변 확인과 13개 환경의 선택적 GEPA 경로 연결.",
         "<b>저장·재사용 시연 및 복귀 보완</b><br/>"
         "React 대표 흐름 고정, 메뉴 이동 시 초안<br/>보존·GEPA 작업 결과 재열람 점검."],
        ["팀 활용<br/><b>윤정우</b>",
         "<b>팀 기준 조합·출처 이력과 지정 계정 인수인계 구현</b><br/>"
         "원본 보존·재조합·되돌림, 참고 파일·버전 기록 연결.<br/>"
         "업무 템플릿 24개와 요청문 점검 정리.",
         "<b>두 계정의 기능·권한 점검</b><br/>"
         "공유·첨부 접근·수신자 변경·버전 충돌<br/>시나리오와 원본 미변경 결과 기록."],
        ["문서·검증<br/><b>윤정우·공동</b>",
         "<b>별도 설계문서 작성·UML 검수 반영</b><br/>"
         "11/04 기록: 프론트 86개·빌드 통과, Python 1,083개<br/>"
         "통과·1개 실패. 실패 항목의 UTF-8 단독 재실행은 통과.<br/>"
         "호스팅 실행·저장 유지 준비, 11/06 로컬 데모 재기동 확인.",
         "<b>같은 환경에서 전체 회귀 재확인</b><br/>"
         "초안·작업 복귀 문제 수정 후 검사.<br/>"
         "설계·코드 대응과 공유본 정리.<br/>공개 배포는 미완료 상태로 관리."],
        ["코딩 실험<br/><b>고차원</b>",
         "<b>1~3차 결과·재채점 근거와 후속 평가 조건 정리</b><br/>"
         "A=지침 없음, B=선택 조립 지침. 아래는 B-A(%p).<br/>"
         "스타일: <b>+28.89 / +27.78 / +23.33</b><br/>"
         "기능: <b>-1.67 / -16.67 / -6.67</b> (각 1·2·3차).",
         "<b>독립 과제와 판정 기준 확정</b><br/>"
         "기능·스타일·미확인을 따로 기록.<br/>"
         "1차 기능 구간은 0 포함, 저하 원인은 미분리.<br/>4차 확증은 과제 부족으로 미실행."],
    ]
    widths = [94, 366, 252]
    heights = [29, 66, 66, 83, 83]
    def cell(s, heading=False):
        return Paragraph(s, ParagraphStyle("cell", fontName="MGB" if heading else "MG",
                         fontSize=10.3, leading=14.4, wordWrap="CJK",
                         textColor=white if heading else HexColor(INK)))
    cells = [[cell(s, i==0) for s in r] for i, r in enumerate(rows)]
    for ri, row in enumerate(cells):
        for ci, item in enumerate(row):
            _, content_h = item.wrap(widths[ci]-18, 1000)
            assert content_h <= heights[ri]-12, (ri, ci, content_h)
    t = Table(cells, colWidths=widths, rowHeights=heights)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), HexColor(NAVY)),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, HexColor("#F4F6F7")]),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 9), ("RIGHTPADDING", (0,0), (-1,-1), 9),
        ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LINEBELOW", (0,0), (-1,-1), .5, HexColor(LINE)),
        ("LINEAFTER", (0,1), (1,-1), .4, HexColor(LINE)),
    ]))
    t.wrap(712, 1000)
    t.drawOn(p.c, 34, H-149-sum(heights))
    p.text("검증 범위: 단독 재실행을 전체 통과로 합산하지 않음. GEPA 연결·구현을 성능·사용자 효과 검증으로 해석하지 않음.<br/>"
           "실험의 1·2차 기능 수치는 평가 도구 수정 후 재채점. 상세 실적·조건·한계는 백업 5~11쪽 참조.",
           35, 483, 710, 9.0, MUTED, maxh=27)
    return p.finish()


# Schedule bars are a planning frame reconstructed this week, not fabricated
# historical weekly completion. Filled cells alone represent dated evidence.
WBS = [
    ("1", "주제·요구 정리", "기존 기반 확보", [1,2,3], []),
    ("2", "선호·코딩 실험", "1~3차 결과 확보", list(range(3,9)), [8]),
    ("3", "개인 지침·재사용", "핵심 구현", list(range(5,10)), [8]),
    ("4", "팀 조합·인수인계", "핵심 구현", list(range(6,10)), [8]),
    ("5", "설계문서 작성·검토", "작성·검수 반영", [8,9,10], [8,9]),
    ("6", "통합 검사·복귀 보완", "문제 확인·진행", [8,9,10,11], [8]),
    ("7", "독립 평가·권한 검증", "조건·과제 준비", [10,11,12], []),
    ("8", "운영 점검·시연 안정화", "실행 구조 준비", list(range(8,15)), [8,9]),
    ("9", "최종 결과·발표", "예정", [14,15], []),
]


def wbs():
    p = Page()
    p.header("2. 15주차 WBS와 현재 위치", "수업 09/11~12/18  |  보고일 11/06 = 9주차  |  현재: 핵심 구현 후 통합·독립 검증 준비", 3)
    p.rect(34, 109, 712, 31, PALE)
    p.text("확보: 핵심 기능·3차까지의 실험 결과·설계문서  /  남은 일: 복귀 오류·독립 평가·운영 검증", 45,
           117, 690, 11.0, NAVY, True, maxh=18)
    grid_x, cw, y0, rh = 331, 415/15, 185, 29.5
    current_x = grid_x+(CURRENT_WEEK-1)*cw
    p.rect(current_x, 145, cw, 40+rh*len(WBS), "#FFF0D9")
    p.rect(34, 147, 297, 38, NAVY)
    p.text("ID", 39, 156, 25, 9.5, "#FFFFFF", True, maxh=16)
    p.text("작업", 72, 156, 155, 10.2, "#FFFFFF", True, maxh=17)
    p.text("현재 상태", 232, 156, 92, 10.2, "#FFFFFF", True, maxh=17)
    for i, day in enumerate(WEEKS):
        x = grid_x+i*cw
        p.rect(x, 147, cw, 38, ORANGE if i+1==CURRENT_WEEK else NAVY)
        p.text(f"{i+1}주", x, 150, cw, 9.4, "#FFFFFF", True, maxh=15, align=1)
        p.text(day.strftime("%m/%d"), x, 168, cw, 7.6, "#FFFFFF", maxh=12, align=1)
    for ri, (wid, task, status, plan, actual) in enumerate(WBS):
        y = y0+ri*rh
        p.rect(34, y, 297, rh, "#F4F6F7" if ri%2 else "#FFFFFF")
        p.text(wid, 40, y+7, 24, 10.2, maxh=17)
        p.text(task, 71, y+7, 155, 10.2, bold=True, maxh=17)
        p.text(status, 230, y+7, 98, 9.0, MUTED, maxh=17)
        for wk in plan:
            x = grid_x+(wk-1)*cw
            p.rect(x+3, y+8, cw-6, 14, "#E5EAEE", "#8A9EAD")
        for wk in actual:
            x = grid_x+(wk-1)*cw
            p.rect(x+5, y+10, cw-10, 10, TEAL)
        p.line(34, y+rh, 746, y+rh)
    for i in range(16):
        p.line(grid_x+i*cw, y0, grid_x+i*cw, y0+rh*len(WBS), "#DCE3E7", .4)
    p.rect(35, 463, 15, 10, "#E5EAEE", "#8A9EAD")
    p.text("학기 일정안", 56, 460, 104, 9.5, maxh=16)
    p.rect(177, 463, 15, 10, TEAL)
    p.text("기록으로 확인한 활동", 198, 460, 153, 9.5, maxh=16)
    p.rect(375, 463, 15, 10, "#FFF0D9", ORANGE)
    p.text("현재 9주차", 396, 460, 130, 9.5, maxh=16)
    p.text("채운 칸도 전체 완료를 뜻하지 않음", 543, 460, 202, 9.1, MUTED, maxh=16)
    p.text("금주 재정리한 학기 일정안이며 1~7주차의 주별 실적·완료율은 미집계. 상태는 보고일에 확인한 범위만 표시.<br/>"
           "8주차: 11/03~05 구현·실험 정리·검사·문서화 / 9주차: UML 검수 반영·로컬 재기동 확인. 후속 일정은 계획.",
           35, 484, 710, 8.8, MUTED, maxh=27)
    return p.finish()


# Current PDF page numbers and original v0.1 page numbers are both explicit.
BACKUPS = [
    (3, "개인 지침·화면 상세"), (4, "팀 공유·업무 상세"),
    (5, "문서·검증·운영 상세"), (6, "고차원 코딩 실험 상세"),
    (7, "기존 연구와 구현의 연결"), (19, "11/05 작성 당시 후속 계획"),
    (20, "코드·실험 근거와 공유 경로"),
] + [(i, label) for i, label in zip(range(8,19), [
    "기능 요구사항", "비기능 요구사항", "시스템 구성도", "개인 지침 유스케이스",
    "인증·저장 클래스", "ERD", "테이블 정의 요약", "핵심 API", "화면 정의·와이어프레임",
    "개인 지침 구현 화면", "팀 활용 구현 화면",
])]


def backup_index():
    p = Page()
    p.header("백업 자료", "본 보고는 1~3쪽  |  아래 자료는 질문이 있을 때만 활용", 4)
    sections = [
        ("05~08쪽", "금주 작업·코딩 실험의 상세 근거", "개인 지침 / 팀 활용 / 검사 기록 / 실험 조건·독립 지표"),
        ("09~11쪽", "연구 연결·이전 상세 계획·근거 링크", "11/05 작성 당시 계획을 보존. 현재 금주·차주 기준은 2쪽 적용"),
        ("12~20쪽", "별도 설계문서의 참고 도식", "요구사항 / 시스템·UML / ERD·테이블 / API / 화면 정의"),
        ("21~22쪽", "실제 구현 화면", "11/04 예시 계정의 지침·보관함·팀 활용 화면"),
    ]
    for i, (pages, title, body) in enumerate(sections):
        y = 119+i*76
        p.rect(34, y, 712, 65, PALE if i%2==0 else "#F4F6F7")
        p.text(pages, 46, y+18, 95, 13, TEAL, True, maxh=22)
        p.text(title, 158, y+10, 572, 14, bold=True, maxh=23)
        p.text(body, 158, y+38, 572, 10.3, MUTED, maxh=18)
    p.text("설계문서는 별도 산출물로 관리", 35, 447, 710, 13, bold=True, maxh=21)
    p.text("기존 설계 본문은 수정하지 않고 백업에 보존했습니다. 수정 가능한 전체 설계문서와 UML 별첨을 별도로 공유합니다.<br/>"
           "백업은 v0.1의 내용·수치·그림·링크를 유지하고, 이 문서의 쪽 번호와 백업 표시만 갱신했습니다.",
           35, 476, 710, 10, MUTED, maxh=29)
    return p.finish()


def main():
    assert CURRENT_WEEK == 9
    assert WEEKS[-1] == date(2026,12,18)
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    source = PdfReader(SOURCE)
    assert len(source.pages) == 21
    writer = PdfWriter()
    for func in [cover, progress, wbs, backup_index]:
        writer.add_page(func())
    for old_number, _ in BACKUPS:
        original = source.pages[old_number-1]
        footer = Page()
        footer.footer(len(writer.pages)+1, backup=True, old_number=old_number)
        original.merge_page(footer.finish())
        writer.add_page(original)
    for title, idx in [("표지",0), ("금주 진행현황",1), ("15주차 WBS",2), ("백업 자료",3)]:
        writer.add_outline_item(title, idx)
    for idx, (_, label) in enumerate(BACKUPS, start=4):
        writer.add_outline_item(label, idx)
    writer.add_metadata({"/Title": "Revealed 주간보고서 v0.2 2026년 11월 6일 9주차",
                         "/Author": "윤정우 · 고차원", "/Subject": "금주 진행현황과 15주차 WBS"})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("wb") as out:
        writer.write(out)
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == source_hash
    QA.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": VERSION, "report_date": REPORT_DATE.isoformat(), "week": CURRENT_WEEK,
        "semester_start": SEMESTER_START.isoformat(), "semester_end": WEEKS[-1].isoformat(),
        "main_pages": [1,2,3], "backup_index_page":4,
        "backup_mapping": [{"page":i+5, "source_page":old, "title":title} for i,(old,title) in enumerate(BACKUPS)],
        "source": str(SOURCE.relative_to(ROOT)), "source_sha256":source_hash,
        "output":str(OUT.relative_to(ROOT)), "pages":len(writer.pages),
    }
    (QA/"build_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Written {OUT.name}: {len(writer.pages)} pages, week {CURRENT_WEEK}")


if __name__ == "__main__":
    main()

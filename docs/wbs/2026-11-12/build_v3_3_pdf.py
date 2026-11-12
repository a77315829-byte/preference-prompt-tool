"""보고서형 WBS v3.3 PDF: WBS 표, 간트차트, 주 구현·관련 UC 연결표의 3쪽.

v3.0/v3.1의 build_v3_pdf.py와 같은 판형·색을 쓰되 별도 파일로 두어 이전 판본을 그대로 다시 만들 수 있게 한다.
"""
from pathlib import Path
from datetime import date, timedelta
from xml.sax.saxutils import escape
import json
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
D = json.loads((HERE / 'wbs-v3.3.json').read_text(encoding='utf-8'))
OUT = ROOT / 'output/pdf/Revealed_WBS_v3.3_보고서형.pdf'
pdfmetrics.registerFont(TTFont('MG', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MGB', 'C:/Windows/Fonts/malgunbd.ttf'))
W, H = landscape(A3)
M = 36
CW = W - 2 * M
INK, GRID, BLUE, GRAY = '#25344B', '#CCD3DD', '#DAE4F2', '#EBEEF2'
STATUS_COLOR = {'완료': '#E7F1EA', '보완중': '#FFF2CC', '진행중': '#E6EEF8', '예정': '#F7F7F7'}
PAGES = 3


def p(lines, size=10.5, bold=False, center=False):
    """문자열 또는 줄 목록을 표 칸용 문단으로 만든다."""
    if not isinstance(lines, (list, tuple)):
        lines = [lines]
    style = ParagraphStyle('cell', fontName='MGB' if bold else 'MG', fontSize=size, leading=size * 1.25,
                           textColor=colors.HexColor(INK), wordWrap='CJK', alignment=1 if center else 0)
    return Paragraph('<br/>'.join(escape(str(s)) for s in lines), style)


def text(c, s, x, y, w, size=11, bold=False):
    obj = p(s, size, bold)
    _, height = obj.wrap(w, 100)
    obj.drawOn(c, x, y - height)


def heading(c, title, sub, page):
    text(c, title, M, H - 30, CW, 22, True)
    text(c, sub, M, H - 67, CW, 11)
    c.setStrokeColor(colors.HexColor(INK))
    c.line(M, H - 92, W - M, H - 92)
    footer = (f'Revealed  |  문서 {D["date"]} / 상태 {D["status_date"]}  |  '
              f'코드 기준 microstone {D["code_basis"][:7]}  |  보고서형 WBS v{D["version"]}')
    text(c, footer, M, 26, 800, 9)
    text(c, f'{page} / {PAGES}', W - M - 50, 26, 50, 9)


def deps(t):
    return ', '.join(x['id'] + (' SS' if x['type'] == 'SS' else '') for x in t['predecessors']) or '-'


def days(t):
    return (date.fromisoformat(t['end']) - date.fromisoformat(t['start'])).days + 1


def evidence_lines(t):
    return [f'{e["date"][5:]} {e["label"]}' for e in t['repository_first']] or ['-']


def wbs_page(c):
    heading(c, 'WBS  |  전체 개발 계획',
            '5개 단계 / 16개 주요 작업 · 일정은 계획안 · 제품 상태 11/12 / 문서 반영·UC 연결 11/13 기준 · 설계서 v1.2 연계', 1)
    header = ['WBS ID', 'Level', '단계', '작업명', '연결 UC', '선행 작업', '시작일(안)', '종료일(안)',
              '기간(일)', '진행률', '상태', '저장소 최초 추가일', '비고(반영·남은 일)']
    rows = [[p(s, 10.5, True) for s in header]]
    spans, summaries, status_cells = [], [], []
    row_heights = [34]
    for g in D['groups']:
        first = len(rows)
        summaries.append(first)
        cells = [g['id'], 1, g['phase'], g['name'], g['uc_scope'], '-', g['start'], g['end'], days(g), '-', '요약', '-', '']
        rows.append([p(v, 10, True) for v in cells])
        row_heights.append(27)
        for t in [x for x in D['tasks'] if x['group'] == g['id']]:
            pct = '-' if t['progress'] is None else f'{t["progress"]:.0%}'
            cells = [t['id'], 2, '', t['name'], t['uc_scope'], deps(t), t['start'], t['end'], days(t), pct, t['status']]
            row = [p(str(v).splitlines(), 9.5 if i == 4 else 10) for i, v in enumerate(cells)]
            row += [p(evidence_lines(t), 8.5), p(t['note'] or '-', 8.5)]
            rows.append(row)
            row_heights.append(41 if t['id'] == '3.3' else 27)
            status_cells.append((len(rows) - 1, t['status']))
        spans.append((first, len(rows) - 1))
    fixed = [52, 40, 64, 176, 106, 82, 68, 68, 52, 46, 48, 110]
    table = Table(rows, colWidths=fixed + [CW - sum(fixed)], rowHeights=row_heights)
    style = [('GRID', (0, 0), (-1, -1), .45, colors.HexColor(GRID)),
             ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(BLUE)),
             ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
             ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
             ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]
    for r in summaries:
        style.append(('BACKGROUND', (0, r), (-1, r), colors.HexColor(GRAY)))
    for first, last in spans:
        style += [('SPAN', (2, first), (2, last)), ('BACKGROUND', (2, first), (2, last), colors.HexColor(GRAY))]
    for r, state in status_cells:
        style.append(('BACKGROUND', (10, r), (10, r), colors.HexColor(STATUS_COLOR[state])))
    table.setStyle(TableStyle(style))
    _, height = table.wrap(CW, H)
    table.drawOn(c, M, H - 105 - height)
    for i, note in enumerate(D['notes']):
        text(c, note, M, 114 - 19 * i, CW, 9.5)


def week_marks(t):
    """주차 칸 번호 -> 표식. 1주차 이전의 커밋은 첫 칸에 ◀로 적는다."""
    first_week = date.fromisoformat(D['weeks'][0])
    marks = {}
    for e in t['repository_first']:
        when = date.fromisoformat(e['date'])
        index = 0 if when < first_week else (when - first_week).days // 7
        mark = '◀' if when < first_week else '●'
        marks[index] = marks.get(index, '') + mark
    return marks


def gantt_page(c):
    heading(c, '간트차트  |  학기 전체 일정',
            '2026.09.11~12.18 · 파란 칸은 계획 구간 · ●는 저장소 최초 추가일이 속한 주 · 문서 기준: 10주차(11/13)', 2)
    widths = [48, 280, 85] + [(CW - 413) / 15] * 15
    week_style = ParagraphStyle('week', fontName='MGB', fontSize=10, leading=14, textColor=colors.HexColor(INK), alignment=1)
    rows = [[p('ID', 11, True), p('주요 작업', 11, True), p('상태', 11, True)]
            + [Paragraph(f'{i + 1}주<br/>{s[5:].replace("-", "/")}', week_style) for i, s in enumerate(D['weeks'])]]
    current_col = 12  # 10주차(11/13)
    style = [('GRID', (0, 0), (-1, -1), .45, colors.HexColor(GRID)),
             ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(BLUE)),
             ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 7),
             ('LEFTPADDING', (3, 1), (-1, -1), 0), ('RIGHTPADDING', (3, 1), (-1, -1), 0),
             ('BACKGROUND', (current_col, 0), (current_col, 0), colors.HexColor('#FFDCA5'))]
    for ri, t in enumerate(D['tasks'], 1):
        marks = week_marks(t)
        rows.append([p(t['id'], 11), p(t['name'], 11), p(t['status'], 11)]
                    + [p(marks.get(wi, ''), 10, center=True) for wi in range(15)])
        if ri % 2 == 0:
            style.append(('BACKGROUND', (0, ri), (2, ri), colors.HexColor('#F6F7F9')))
        for wi, week in enumerate(D['weeks']):
            start = date.fromisoformat(week)
            end = start + timedelta(days=6)
            if date.fromisoformat(t['start']) <= end and date.fromisoformat(t['end']) >= start:
                style.append(('BACKGROUND', (wi + 3, ri), (wi + 3, ri), colors.HexColor('#AFC4E0')))
        if t['id'].endswith('.1'):
            style.append(('LINEABOVE', (0, ri), (-1, ri), 1, colors.HexColor('#8B99AB')))
    table = Table(rows, colWidths=widths, rowHeights=[42] + [31] * 16)
    table.setStyle(TableStyle(style))
    _, height = table.wrap(CW, H)
    table.drawOn(c, M, H - 110 - height)
    notes = ['파란 칸 = 계획 기간 / 주황색 머리글 = 현재 기준 주차. 완료 여부는 상태 열로 확인합니다.',
             '● = 해당 경로의 최초 추가 커밋 작성 주, ◀ = 1주차(09/11) 이전. GitHub 업로드 시점이 아니며 날짜와 대상은 WBS 표의 저장소 최초 추가일 열에 있습니다.',
             '주요 범위: 요약·코딩, 계정·지침 재사용, 팀 공유·인수인계, 비교 검증, 기능 검사, 운영·최종 제출.',
             '일정과 상태를 바꾸려면 함께 제공한 Excel의 WBS 시트를 수정하면 됩니다. 간트차트가 함께 갱신됩니다.',
             '실사용자 연구·공개 배포 실행·과거 Streamlit 정리는 별도 후속으로 유지합니다.']
    for i, note in enumerate(notes):
        text(c, note, M, 166 - 27 * i, CW, 10.5)


def usecase_page(c):
    heading(c, '유즈케이스 연결표  |  설계서와 WBS 대응',
            '상위 24개·하위 79개 UC · 주 구현과 공통 사용·보완 예정 관계 구분 · 하위 UC는 부모의 연결 범위를 상속', 3)
    rows = [[p(x, 10, True) for x in ['상위 UC', '유즈케이스 이름', '하위 UC 범위', '주 구현 WBS', '관련 WBS', '관련 요구사항']]]
    for u in D['usecases']:
        children = u['children']
        related = ', '.join(x['id']+' '+('예정' if x['role']=='보완 예정' else x['role']) for x in u.get('related_wbs',[])) or '-'
        rows.append([p(u['id'], 10.5), p(u['name'], 10.5), p(children[0]['id'] + ' ~ ' + children[-1]['id'], 10.5),
                     p(u['wbs'], 10.5), p(related, 9.5), p(u['requirements'], 10.5)])
    table = Table(rows, colWidths=[70, 300, 230, 80, 160, CW - 840], rowHeights=[30] + [24] * 24)
    table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), .4, colors.HexColor(GRID)),
                               ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(BLUE)),
                               ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    _, height = table.wrap(CW, H)
    table.drawOn(c, M, H - 105 - height)
    text(c, 'UC-02·03의 주 구현은 3.1입니다. UC-03은 3.2에서도 공통 사용하며, 두 UC의 3.3은 세션 접근·소유권·만료 정책 보완 예정입니다.', M, 105, CW, 10)
    text(c, '3.3의 예정 연결은 현재 계정 격리 완료를 뜻하지 않습니다. 하위 연결도 해당 보완 범위에만 적용합니다. 분석·설계·회귀는 전체 UC를 다룹니다.', M, 82, CW, 10)
    text(c, 'WBS는 프로젝트 작업 범위, UC는 사용자 목표입니다. 설계서 v1.2와 공통 기능명·주 구현·관련 WBS를 일치시켰습니다. 작업 수는 중복 합산하지 않습니다.', M, 59, CW, 10)


def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=(W, H))
    c.setTitle(D['title'])
    c.setAuthor('Revealed')
    wbs_page(c)
    c.showPage()
    gantt_page(c)
    c.showPage()
    usecase_page(c)
    c.save()
    print(OUT)


if __name__ == '__main__':
    build()

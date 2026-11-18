"""Report-style two-level WBS table and semester Gantt, two pages."""
from pathlib import Path
from datetime import date,timedelta
from xml.sax.saxutils import escape
import json
import sys
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3,landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph,Table,TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parents[3]
REV='3.1' if '--uc-links' in sys.argv else '3.0'
D=json.loads((Path(__file__).parent/('wbs-v3.1.json' if REV=='3.1' else 'wbs-v3.json')).read_text(encoding='utf-8'))
OUT=ROOT/f'output/pdf/Revealed_WBS_v{REV}_보고서형.pdf'
pdfmetrics.registerFont(TTFont('MG','C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MGB','C:/Windows/Fonts/malgunbd.ttf'))
W,H=landscape(A3);M=36;CW=W-2*M
INK='#25344B';GRID='#CCD3DD';BLUE='#DAE4F2';GRAY='#EBEEF2'
def p(s,size=11,bold=False):
    return Paragraph(escape(str(s)),ParagraphStyle('cell',fontName='MGB' if bold else 'MG',fontSize=size,leading=size*1.35,textColor=colors.HexColor(INK),wordWrap='CJK'))
def text(c,s,x,y,w,size=11,bold=False):
    obj=p(s,size,bold);_,height=obj.wrap(w,100)
    obj.drawOn(c,x,y-height)
def heading(c,title,sub,page):
    text(c,title,M,H-30,CW,22,True);text(c,sub,M,H-67,CW,11)
    c.setStrokeColor(colors.HexColor(INK));c.line(M,H-92,W-M,H-92)
    text(c,f'Revealed  |  문서 {D["date"]} / 상태 2026-11-12  |  보고서형 WBS v{REV}',M,26,700,9)
    text(c,f'{page} / {3 if REV=="3.1" else 2}',W-M-50,26,50,9)
def deps(t):return ', '.join(x['id']+(' SS' if x['type']=='SS' else '') for x in t['predecessors']) or '-'
def days(t):return (date.fromisoformat(t['end'])-date.fromisoformat(t['start'])).days+1
def build():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(OUT),pagesize=(W,H));c.setTitle(D['title']);c.setAuthor('Revealed')
    heading(c,'WBS  |  전체 개발 계획','중간보고서 표 형식 · 5개 단계 / 16개 주요 작업 · 일정은 계획안, 상태는 11/12 확인 기준',1)
    rows=[[p(s,11,True) for s in ['WBS ID','Level','단계','작업명','연결 UC' if REV=='3.1' else '관련 요구사항','선행 작업','시작일(안)','종료일(안)','기간(일)','진행률','상태']]]
    spans=[];summaries=[];status_cells=[]
    for g in D['groups']:
        first=len(rows);summaries.append(first)
        rows.append([g['id'],1,g['phase'],g['name'],'공통','-',g['start'],g['end'],days(g),'-','요약'])
        for t in [x for x in D['tasks'] if x['group']==g['id']]:
            pct='-' if t['progress'] is None else f'{t["progress"]:.0%}'
            rows.append([t['id'],2,'',t['name'],t.get('uc_scope',t['requirements']),deps(t),t['start'],t['end'],days(t),pct,t['status']])
            status_cells.append((len(rows)-1,t['status']))
        spans.append((first,len(rows)-1))
    for r in range(1,len(rows)):
        rows[r]=[p(v,9.5 if i==4 and REV=='3.1' else 10.5,r in summaries) for i,v in enumerate(rows[r])]
    widths=[60,42,82,250,116,98,91,91,70,70,CW-970]
    table=Table(rows,colWidths=widths,rowHeights=[35]+[28]*21)
    style=[('GRID',(0,0),(-1,-1),.45,colors.HexColor(GRID)),('BACKGROUND',(0,0),(-1,0),colors.HexColor(BLUE)),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7)]
    for r in summaries:style.extend([('BACKGROUND',(0,r),(-1,r),colors.HexColor(GRAY))])
    for first,last in spans:style.extend([('SPAN',(2,first),(2,last)),('BACKGROUND',(2,first),(2,last),colors.HexColor(GRAY))])
    for r,state in status_cells:
        color={'완료':'#E7F1EA','보완중':'#FFF2CC','진행중':'#E6EEF8','예정':'#F7F7F7'}[state]
        style.append(('BACKGROUND',(10,r),(10,r),colors.HexColor(color)))
    table.setStyle(TableStyle(style));_,height=table.wrap(CW,H)
    table.drawOn(c,M,H-105-height)
    text(c,'일정: 기존 학기 계획과 후속 계획을 묶은 일정안입니다. 과거 실제 시작·종료일을 뜻하지 않습니다.',M,101,CW,10)
    text(c,'진행률: 완료 100%·예정 0%만 표시했습니다. 진행·보완 작업과 단계 요약의 비율은 미산정(-)입니다.',M,78,CW,10)
    text(c,'선행 관계: SS = 시작 후 병행 / 표기 없음 = 완료 후 시작. 요약 기능 구현 완료와 출력 효과 검증은 구분합니다.',M,55,CW,10)
    c.showPage()
    heading(c,'간트차트  |  학기 전체 일정','2026.09.11~12.18 · 표의 시작일·종료일과 같은 계획 구간 · 문서 기준: '+('10주차(11/13)' if REV=='3.1' else '9주차(11/12)'),2)
    widths=[48,280,85]+[(CW-413)/15]*15
    rows=[[p('ID',11,True),p('주요 작업',11,True),p('상태',11,True)]+[p(f'{i+1}주<br/>{s[5:].replace("-","/")}',10,True) for i,s in enumerate(D['weeks'])]]
    # Explicit newlines inside the header paragraph, no literal markup in table cells.
    for i,s in enumerate(D['weeks']):
        rows[0][3+i]=Paragraph(f'{i+1}주<br/>{s[5:].replace("-","/")}',ParagraphStyle('week',fontName='MGB',fontSize=10,leading=14,textColor=colors.HexColor(INK),alignment=1))
    for t in D['tasks']:rows.append([p(t['id']),p(t['name']),p(t['status'])]+['']*15)
    table=Table(rows,colWidths=widths,rowHeights=[42]+[31]*16)
    current_col=12 if REV=='3.1' else 11
    style=[('GRID',(0,0),(-1,-1),.45,colors.HexColor(GRID)),('BACKGROUND',(0,0),(-1,0),colors.HexColor(BLUE)),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),7),('BACKGROUND',(current_col,0),(current_col,0),colors.HexColor('#FFDCA5'))]
    for ri,t in enumerate(D['tasks'],1):
        if ri%2==0:style.append(('BACKGROUND',(0,ri),(2,ri),colors.HexColor('#F6F7F9')))
        for wi,week in enumerate(D['weeks']):
            start=date.fromisoformat(week);end=start+timedelta(days=6)
            if date.fromisoformat(t['start'])<=end and date.fromisoformat(t['end'])>=start:
                style.append(('BACKGROUND',(wi+3,ri),(wi+3,ri),colors.HexColor('#AFC4E0')))
        if t['id'].endswith('.1'):style.append(('LINEABOVE',(0,ri),(-1,ri),1,colors.HexColor('#8B99AB')))
    table.setStyle(TableStyle(style));_,height=table.wrap(CW,H);table.drawOn(c,M,H-110-height)
    text(c,'파란 칸 = 계획 기간 / 주황색 머리글 = 현재 기준 주차. 완료 여부는 상태 열로 확인합니다.',M,153,CW,11)
    text(c,'주요 범위: 요약·코딩, 계정·지침 재사용, 팀 공유·인수인계, 비교 검증, 기능 검사, 운영·최종 제출.',M,123,CW,11)
    text(c,'일정과 상태를 바꾸려면 함께 제공한 Excel의 WBS 시트를 수정하면 됩니다. 간트차트가 함께 갱신됩니다.',M,93,CW,11)
    text(c,'실사용자 연구·공개 배포 실행·과거 Streamlit 정리는 별도 후속으로 유지합니다.',M,63,CW,10)
    if REV=='3.1':
        c.showPage()
        heading(c,'유즈케이스 연결표  |  설계서와 WBS 대응','상위 24개·하위 79개 UC · 하위 UC는 부모의 구현 WBS를 상속 · 신규 일정 작업으로 중복 합산하지 않음',3)
        rows=[[p(x,11,True) for x in ['상위 UC','유즈케이스 이름','하위 UC 범위','구현 WBS','관련 요구사항']]]
        for u in D['usecases']:
            children=u['children'];childrange=children[0]['id']+' ~ '+children[-1]['id']
            rows.append([p(u['id']),p(u['name']),p(childrange),p(u['wbs']),p(u['requirements'])])
        t=Table(rows,colWidths=[85,355,275,100,CW-815],rowHeights=[30]+[24]*24)
        t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.4,colors.HexColor(GRID)),('BACKGROUND',(0,0),(-1,0),colors.HexColor(BLUE)),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
        _,th=t.wrap(CW,H);t.drawOn(c,M,H-105-th)
        text(c,'공통 UC-03은 요약(3.1)과 React 비교(3.2)가 함께 사용합니다. 분석 1.2·설계 2.1~2.3·회귀 4.2는 전체 UC에 적용합니다.',M,105,CW,10)
        text(c,'3.3의 지원 범위에는 개선·답변 확인·파일 내보내기·실제 작업 기록·템플릿·업무 공간을 포함합니다.',M,82,CW,10)
        text(c,'WBS는 프로젝트 작업 범위, UC는 사용자 목표입니다. 같은 기능의 명칭과 ID를 연결하며 모든 작업명을 UC와 같게 만들지는 않습니다.',M,59,CW,10)
    c.save();print(OUT)

if __name__=='__main__':build()

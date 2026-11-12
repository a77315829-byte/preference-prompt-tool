"""Render the complete analysis/design chapters, with Korean fonts and PDF bookmarks."""
from pathlib import Path
import hashlib
import html
import json
import re
from urllib.parse import quote
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak, Image, Table, TableStyle, KeepTogether
from reportlab.platypus.tableofcontents import TableOfContents

HERE=Path(__file__).resolve().parent
DEST=HERE/'Revealed_Analysis_Design_v1.0.pdf'
BASE='https://github.com/a77315829-byte/preference-prompt-tool/blob/codex/system-design-2026-11-12/docs/system-design/'
pdfmetrics.registerFont(TTFont('Malgun','C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBold','C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFontFamily('Malgun',normal='Malgun',bold='MalgunBold',italic='Malgun',boldItalic='MalgunBold')
INK=colors.HexColor('#20314c');MUTED=colors.HexColor('#556579');ACCENT=colors.HexColor('#5864a6')
BODY=ParagraphStyle('Body',fontName='Malgun',fontSize=9.7,leading=15.5,textColor=INK,spaceAfter=9,wordWrap='CJK',splitLongWords=True)
H1=ParagraphStyle('Chapter',parent=BODY,fontName='MalgunBold',fontSize=20,leading=28,spaceAfter=18,keepWithNext=True)
H2=ParagraphStyle('Section',parent=BODY,fontName='MalgunBold',fontSize=12.5,leading=20,spaceBefore=14,spaceAfter=8,keepWithNext=True)
UC=ParagraphStyle('Section',parent=H2,spaceBefore=10)
H3=ParagraphStyle('Subsection',parent=BODY,fontName='MalgunBold',fontSize=10.5,leading=17,spaceBefore=10,spaceAfter=6,keepWithNext=True)
CAP=ParagraphStyle('Caption',parent=BODY,fontSize=8.5,leading=12.5,textColor=MUTED,spaceAfter=12)
CELL=ParagraphStyle('Cell',parent=BODY,fontSize=8.1,leading=12.2,spaceAfter=0)
TITLE=ParagraphStyle('Cover',parent=H1,fontSize=30,leading=42,spaceAfter=20)
WIDTH=A4[0]-92

def inline(source, parent=HERE):
    source=html.escape(source)
    source=re.sub(r'\*\*(.*?)\*\*',r'<b>\1</b>',source)
    source=re.sub(r'`([^`]+)`',r'<font color="#40548a">\1</font>',source)
    def link(match):
        label,url=match.group(1),html.unescape(match.group(2))
        if '://' not in url:
            local=(parent/url).resolve().relative_to(HERE).as_posix()
            url=BASE+quote(local,safe='/#')
        return f'<link href="{html.escape(url,quote=True)}" color="#40548a">{label}</link>'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',link,source)

def footer(c,doc):
    c.saveState();c.setStrokeColor(colors.HexColor('#d4dbe5'))
    c.line(46,43,A4[0]-46,43);c.setFillColor(MUTED);c.setFont('Malgun',8)
    c.drawString(46,28,'Revealed  |  전체 분석·설계서 v1.0  |  2026-11-12')
    c.drawRightString(A4[0]-46,28,str(doc.page));c.restoreState()

class Report(BaseDocTemplate):
    def afterFlowable(self,flowable):
        if not isinstance(flowable,Paragraph):return
        title=flowable.getPlainText()
        if flowable.style.name not in ('Chapter','Section'):return
        key='heading-'+hashlib.sha1(title.encode()).hexdigest()[:16]
        if flowable.style.name=='Chapter' and re.match(r'^\d+\.',title):
            self.canv.bookmarkPage(key);self.canv.addOutlineEntry(title,key,0)
            self.notify('TOCEntry',(0,title,self.page,key))
        elif flowable.style.name=='Section' and re.match(r'^(?:\d+\.\d+|UC-\d+)',title):
            self.canv.bookmarkPage(key);self.canv.addOutlineEntry(title,key,1)

def table(lines,parent):
    rows=[[v.strip() for v in line.strip().strip('|').split('|')] for line in lines]
    rows=[r for r in rows if not all(re.fullmatch(r':?-+:?',v.replace(' ','')) for v in r)]
    count=len(rows[0]);assert all(len(r)==count for r in rows),rows[0]
    if count==4:
        if rows[0][0] in ('ID','순서'): weights=[.12,.26,.31,.31]
        elif rows[0][0]=='열':weights=[.24,.12,.23,.41]
        else:weights=[.20,.26,.27,.27]
    elif count==3:weights=[.23,.36,.41]
    elif count==2:weights=[.30,.70]
    elif count==5:weights=[.12,.15,.30,.21,.22]
    else:weights=[1/count]*count
    cells=[[Paragraph(inline(v,parent),CELL) for v in r] for r in rows]
    t=Table(cells,colWidths=[WIDTH*w for w in weights],repeatRows=1,hAlign='LEFT',splitByRow=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9edf8')),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f7f9fc')]),
        ('LINEBELOW',(0,0),(-1,0),.7,ACCENT),
        ('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#d8dfe9')),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),
        ('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
    ]))
    return t

def append_chapter(story,path):
    lines=path.read_text(encoding='utf-8').splitlines();i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        if line.startswith('# '):
            story.extend([PageBreak(),Paragraph(inline(line[2:],path.parent),H1)]);i+=1;continue
        if line.startswith('## '):
            story.append(Paragraph(inline(line[3:],path.parent),UC if line.startswith('## UC-') else H2));i+=1;continue
        if line.startswith('### '):
            story.append(Paragraph(inline(line[4:],path.parent),H3));i+=1;continue
        if line.startswith('#### '):
            story.append(Paragraph(inline(line[5:],path.parent),H3));i+=1;continue
        match=re.fullmatch(r'!\[([^]]*)\]\(([^)]+)\)',line)
        if match:
            target=(path.parent/match[2]).resolve();im=Image(str(target));ratio=WIDTH/im.imageWidth
            im.drawWidth=WIDTH;im.drawHeight=im.imageHeight*ratio
            group=[im,Spacer(1,5),Paragraph(match[1],CAP)]
            if story and isinstance(story[-1],Paragraph) and story[-1].style.name in ('Section','Subsection'):
                group.insert(0,story.pop())
            story.append(KeepTogether(group));i+=1;continue
        if line.startswith('|'):
            group=[]
            while i<len(lines) and lines[i].strip().startswith('|'):group.append(lines[i]);i+=1
            rendered=table(group,path.parent)
            if len(group)<=8:
                elements=[rendered,Spacer(1,11)]
                if story and isinstance(story[-1],Paragraph) and story[-1].style.name in ('Section','Subsection'):
                    elements.insert(0,story.pop())
                story.append(KeepTogether(elements))
            else:story.extend([rendered,Spacer(1,11)])
            continue
        if line=='---':i+=1;continue
        if line.startswith('- '):
            story.append(Paragraph('• '+inline(line[2:],path.parent),BODY));i+=1;continue
        para=[line];i+=1
        while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','![','- ')):
            para.append(lines[i].strip());i+=1
        story.append(Paragraph(inline(' '.join(para),path.parent),BODY))

def build():
    doc=Report(str(DEST),pagesize=A4,leftMargin=46,rightMargin=46,topMargin=48,bottomMargin=57,title='Revealed 전체 분석·설계서',author='Revealed',allowSplitting=True)
    frame=Frame(46,57,WIDTH,A4[1]-105,id='body',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
    doc.addPageTemplates(PageTemplate(id='report',frames=frame,onPage=footer))
    story=[Spacer(1,60),Paragraph('Revealed',ParagraphStyle('Brand',parent=TITLE,textColor=ACCENT,fontSize=38)),
           Paragraph('전체 분석·설계서',TITLE),Paragraph('조건 선택 · 지침 재사용 · 결과 검증',H2),Spacer(1,30),
           Paragraph('AI/SW융합프로젝트<br/>윤정우 · 고차원<br/>기준일 2026년 11월 12일 · v1.0',BODY),Spacer(1,30),
           Paragraph('문제·요구사항에서 유즈케이스, 화면, 처리 흐름, 구성요소, API, 데이터, 운영, 검증까지 이어지는 전체 시스템 명세입니다. 주간보고 내용은 마지막 부록에 두었습니다.',BODY),
           Paragraph('24개 유즈케이스 · 18개 논리 화면 · 90개 GET/POST API<br/>16개 테이블 · 21개 그림 · 독립 보조 에이전트 검증',BODY),
           Paragraph('구현한 기능, 검사로 확인한 결과, 보완할 부분과 사람의 미측정 효과를 구분합니다. 문서 공개는 앱 배포를 의미하지 않습니다.',CAP),
           PageBreak(),Paragraph('목차',H1)]
    toc=TableOfContents();toc.levelStyles=[ParagraphStyle('TOC',parent=BODY,fontSize=11,leading=22,spaceBefore=9)]
    story.extend([toc,Spacer(1,22),Paragraph('PDF 책갈피에서 각 장의 세부 절로 이동할 수 있습니다. 편집 가능한 본문·그림 생성 코드·검증 근거는 GitHub docs/system-design에 보관합니다.',BODY)])
    chapters=sorted((HERE/'chapters').glob('[0-9][0-9]-*.md'))
    assert len(chapters)==11,chapters
    for path in chapters:append_chapter(story,path)
    doc.multiBuild(story)
    from pypdf import PdfReader
    pages=len(PdfReader(DEST).pages)
    result={'pdf':DEST.name,'pages':pages,'chapters':[p.relative_to(HERE).as_posix() for p in chapters],
            'diagram_count':len(list((HERE/'diagrams').glob('*.png'))),'sha256':hashlib.sha256(DEST.read_bytes()).hexdigest()}
    (HERE/'pdf-build.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':build()

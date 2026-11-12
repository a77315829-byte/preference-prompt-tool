"""One-page deliverable hierarchy; the companion workbook holds the dictionary."""
from pathlib import Path
from xml.sax.saxutils import escape
import json
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3,landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parents[3]
DATA=json.loads((Path(__file__).parent/'wbs-v2.json').read_text(encoding='utf-8'))
OUT=ROOT/'output/pdf/Revealed_WBS_v2.0_한장.pdf'
pdfmetrics.registerFont(TTFont('MG','C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MGB','C:/Windows/Fonts/malgunbd.ttf'))
INK='#26334D'; NAVY='#344667'; MUTED='#59677C'; LINE='#CAD4E1'; PALE='#F3F6FA'
W,H=landscape(A3)
def para(c,text,x,y,width,size=11,color=INK,bold=False,max_height=100):
    style=ParagraphStyle('p',fontName='MGB' if bold else 'MG',fontSize=size,leading=size*1.45,textColor=colors.HexColor(color),wordWrap='CJK')
    obj=Paragraph(escape(text).replace('\n','<br/>'),style)
    _,height=obj.wrap(width,max_height)
    assert height<=max_height,(text,height,max_height)
    obj.drawOn(c,x,y-height)
    return height

def build():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(OUT),pagesize=(W,H))
    c.setTitle('Revealed 산출물 중심 WBS v2.0');c.setAuthor('Revealed 프로젝트')
    para(c,'REVEALED  /  WBS v2.0',36,H-27,700,11,MUTED,bold=True)
    para(c,'프로젝트 전체 범위를 한눈에',36,H-53,800,26,NAVY,bold=True)
    para(c,'산출물 중심 분해 · 프로젝트 → 주요 산출물 → 작업 패키지',36,H-99,800,12,MUTED)
    para(c,'2026.11.12  |  구조 수정안',W-260,H-32,230,11,MUTED)
    root_y=H-197;root_x=W/2-190
    c.setFillColor(colors.HexColor(NAVY));c.roundRect(root_x,root_y,380,56,8,fill=1,stroke=0)
    para(c,'1  Revealed 프로젝트',root_x+18,root_y+43,344,19,'#FFFFFF',True,40)
    gap=14; margin=36;cw=(W-2*margin-6*gap)/7
    centers=[margin+i*(cw+gap)+cw/2 for i in range(7)]
    branch_y=root_y-30;group_y=branch_y-78
    c.setStrokeColor(colors.HexColor(LINE));c.setLineWidth(1.3)
    c.line(W/2,root_y,W/2,branch_y);c.line(centers[0],branch_y,centers[-1],branch_y)
    for i,g in enumerate(DATA['groups']):
        x=margin+i*(cw+gap);cx=centers[i]
        c.line(cx,branch_y,cx,group_y+59)
        c.setFillColor(colors.HexColor('#E8EDF5'));c.roundRect(x,group_y,cw,59,6,fill=1,stroke=0)
        para(c,g['id'],x+12,group_y+49,cw-24,10,MUTED,True,20)
        para(c,g['title'],x+12,group_y+30,cw-24,13,NAVY,True,25)
        own=[p for p in DATA['packages'] if p['parent']==g['id']]
        stem=x+5;c.line(cx,group_y,cx,group_y-12);c.line(stem,group_y-12,cx,group_y-12)
        bottom=group_y-26-(len(own)-1)*70-33
        c.line(stem,group_y-12,stem,bottom)
        for j,p in enumerate(own):
            y=group_y-26-j*70-65
            c.line(stem,y+33,x+14,y+33)
            c.setFillColor(colors.HexColor(PALE));c.roundRect(x+14,y,cw-14,65,5,fill=1,stroke=0)
            para(c,p['id'],x+25,y+55,cw-37,9.5,MUTED,True,18)
            label=p['title'].replace('설계·사용 문서 인도본','설계·사용 문서\n인도본')
            para(c,label,x+25,y+36,cw-37,12,INK,False,35)
    y=133
    c.setStrokeColor(colors.HexColor(LINE));c.line(36,y+14,W-36,y+14)
    para(c,'읽는 법',36,y,80,11,NAVY,True)
    para(c,'29개 작업 패키지의 포함 범위·경계·완료 기준은 함께 제공한 Excel의 「WBS 사전」에서 확인합니다.',114,y,W-150,11)
    para(c,'범위',36,y-24,80,11,NAVY,True)
    para(c,'기존 73개 필수 활동을 한 번씩 연결했습니다. 실사용자 연구·공개 배포·과거 Streamlit 정리는 별도 후속 목록에 보존합니다.',114,y-24,W-150,10.5)
    para(c,'관리',36,y-48,80,11,NAVY,True)
    para(c,'이 그림은 범위를 나타냅니다. 일정·진행률은 별도 관리하며, 담당자와 범위 합의 후 관리 기준본으로 확정합니다.',114,y-48,W-150,10.5)
    source_y=39
    for label,url,x,width in [
        ('PMI WBS 실무 표준(3판) 공식 소개',DATA['standards'][0]['url'],36,255),
        ('PMI 100% 규칙·표현 방식',DATA['standards'][1]['url'],320,240),
        ('NASA WBS Handbook §2.1·3.3.4·3.4.4',DATA['standards'][2]['url'],585,355)]:
        para(c,label,x,source_y,width,9,MUTED)
        c.linkURL(url,(x,source_y-17,x+width,source_y+1),relative=0,thickness=0)
    para(c,'A3 가로 · 1 / 1',W-164,source_y,130,9,MUTED)
    c.save();print(OUT)

if __name__=='__main__':build()

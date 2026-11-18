"""Render the final-report preparation draft with the existing document typography."""
from pathlib import Path
import importlib.util
import hashlib
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('design', ROOT/'docs/system-design/build_v1_3.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
OUT=ROOT/'output/pdf/Revealed_최종보고서_준비본_v0.1.pdf'

def footer(c,doc):
    c.saveState();c.setStrokeColor(m.colors.HexColor('#d4dbe5'))
    c.line(46,43,m.A4[0]-46,43);c.setFillColor(m.MUTED);c.setFont('Malgun',8)
    c.drawString(46,28,'Revealed  |  최종보고서 준비본 v0.1  |  2026-11-18')
    c.drawRightString(m.A4[0]-46,28,str(doc.page));c.restoreState()

def build():
    doc=m.Report(str(OUT),pagesize=m.A4,leftMargin=46,rightMargin=46,topMargin=48,bottomMargin=57,
                 title='Revealed 최종보고서 준비본 v0.1',author='Revealed',allowSplitting=True)
    frame=m.Frame(46,57,m.WIDTH,m.A4[1]-105,id='body',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
    doc.addPageTemplates(m.PageTemplate(id='report',frames=frame,onPage=footer))
    story=[m.Spacer(1,65),m.Paragraph('Revealed',m.TITLE),m.Paragraph('최종보고서 준비본',m.H1),
           m.Paragraph('요약 조건을 재사용 가능한 지침으로',m.H2),m.Spacer(1,30),
           m.Paragraph('AI/SW융합프로젝트<br/>윤정우 · 고차원<br/>v0.1 · 2026년 11월 18일',m.BODY),m.Spacer(1,24),
           m.Paragraph('확인한 결과 조건을 지침으로 조립하고, 새로운 원문·과제에서 조건 준수와 내용 보존·기능 동작을 분리해 확인한 개발 결과를 정리합니다.',m.BODY),
           m.Paragraph('코드 기준 0bbff80 · 출력·운영 근거 2026-11-17<br/>수동 대비 우위·실사용자 시간 절감은 미입증<br/>공식 제출 양식·팀 리허설 확인 후 확정',m.CAP),
           m.PageBreak(),m.Paragraph('목차',m.H1)]
    toc=m.TableOfContents();toc.levelStyles=[m.ParagraphStyle('ReportTOC',parent=m.BODY,fontSize=10,leading=22,spaceBefore=5)]
    story.append(toc)
    m.append_chapter(story,HERE/'report.md')
    doc.multiBuild(story)
    from pypdf import PdfReader
    result={'path':OUT.relative_to(ROOT).as_posix(),'pages':len(PdfReader(OUT).pages),'sha256':hashlib.sha256(OUT.read_bytes()).hexdigest()}
    (HERE/'report-build.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__': build()

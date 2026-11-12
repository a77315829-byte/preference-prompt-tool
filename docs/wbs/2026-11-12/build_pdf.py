"""Render the project WBS baseline as a readable report, using bundled ReportLab."""
from pathlib import Path
from datetime import date, timedelta
from collections import Counter
from xml.sax.saxutils import escape
import json

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, LongTable, KeepTogether, CondPageBreak

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
DATA=json.loads((HERE/'wbs.json').read_text(encoding='utf-8'))
OUT=ROOT/'output/pdf/Revealed_전체상세_WBS_v1.0.pdf'
pdfmetrics.registerFont(TTFont('Malgun','C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBold','C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFontFamily('Malgun',normal='Malgun',bold='MalgunBold',italic='Malgun',boldItalic='MalgunBold')
NAVY=colors.HexColor('#344667'); INK=colors.HexColor('#26334D'); MUTED=colors.HexColor('#64748B')
PALE=colors.HexColor('#EEF2F7'); LINE=colors.HexColor('#D8DFE8')
STATES={'완료 확인':'#E5F1E9','예정':'#EDF2FF','검토 대기':'#FFF0CB','선택 후속':'#F0EDF7','외부 대기':'#FCE8E6'}
W,H=landscape(A4); M=34; CONTENT=W-M*2
styles={
 'title':ParagraphStyle('title',fontName='MalgunBold',fontSize=23,leading=31,textColor=NAVY,spaceAfter=14),
 'h1':ParagraphStyle('h1',fontName='MalgunBold',fontSize=17,leading=23,textColor=NAVY,spaceAfter=10,keepWithNext=True),
 'h2':ParagraphStyle('h2',fontName='MalgunBold',fontSize=12,leading=18,textColor=NAVY,spaceBefore=9,spaceAfter=7,keepWithNext=True),
 'body':ParagraphStyle('body',fontName='Malgun',fontSize=10,leading=15,textColor=INK,spaceAfter=7,wordWrap='CJK'),
 'small':ParagraphStyle('small',fontName='Malgun',fontSize=8.5,leading=12.5,textColor=MUTED,spaceAfter=5,wordWrap='CJK'),
 'caption':ParagraphStyle('caption',fontName='Malgun',fontSize=8.5,leading=12.5,textColor=MUTED,spaceAfter=5,wordWrap='CJK'),
 'cell':ParagraphStyle('cell',fontName='Malgun',fontSize=9,leading=13.5,textColor=INK,wordWrap='CJK'),
 'head':ParagraphStyle('head',fontName='MalgunBold',fontSize=9,leading=13,textColor=colors.white,wordWrap='CJK'),
}
def p(text,style='body',raw=False):return Paragraph(text if raw else escape(str(text)).replace('\n','<br/>'),styles[style])
def table(headers,rows,widths,small=False):
    t=LongTable([[p(h,'head') for h in headers]]+[[v if isinstance(v,Paragraph) else p(v,'cell') for v in row] for row in rows],
                colWidths=widths,repeatRows=1,hAlign='LEFT',splitByRow=True)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('VALIGN',(0,0),(-1,-1),'TOP'),
                          ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
                          ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
                          ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F7F8FB')]),
                          ('LINEBELOW',(0,0),(-1,0),.5,NAVY),('LINEBELOW',(0,1),(-1,-1),.35,LINE)]))
    return t

def page(canvas,doc):
    canvas.saveState();canvas.setFillColor(MUTED);canvas.setFont('Malgun',8)
    canvas.drawString(M,H-22,'Revealed  /  전체 상세 WBS v1.0')
    canvas.drawRightString(W-M,H-22,'기준 2026.11.12  /  microstone cfd1fe4')
    canvas.setStrokeColor(LINE);canvas.line(M,27,W-M,27)
    canvas.drawString(M,15,'담당·후속 일정·공수는 제안  |  완료 확인은 명시한 기술 검증 범위')
    canvas.drawRightString(W-M,15,str(doc.page));canvas.restoreState()

def build():
    required=[t for t in DATA['tasks'] if t['priority']=='필수']
    complete=[t for t in required if t['status']=='완료 확인']
    pending=[t for t in required if t['status']!='완료 확인']
    hours=sum(t['estimate_hours'] or 0 for t in pending)
    story=[p('선호 기반 프롬프트 자동 생성 도구','small'),p('전체 개발 WBS와 기능 분해','title'),
           p('학기 계획 2026.09.11 - 12.18  /  2026.11.12 확인본','h2'),
           p('요약을 중심으로, 사용자가 확인한 결과 조건을 재사용 지침으로 만들고 새 원문에서 조건 준수와 내용 보존을 따로 검증한다. 코딩의 AI 답변 방식 설정과 React 코드 스타일 비교는 유지한다.'),
           table(['세부 작업','필수 작업','완료 확인 / 잔여 필수','선택·외부 대기'],[[str(len(DATA['tasks'])),str(len(required)),f'{len(complete)} / {len(pending)}',str(len(DATA['tasks'])-len(required))]],[170,170,245,CONTENT-585]),
           Spacer(1,12),p('이 문서에서 구분한 두 구조','h2'),
           p('개발 WBS: 분석·설계·구현·검증·이행 작업을 9개 묶음, 77개 실행 단위로 나눈다. 기능 분해: 8개 대기능, 16개 논리 기능, 54개 세부 기능을 요구사항과 개발 작업에 연결한다.'),
           p('기존 주간보고의 WBS ID를 유지했다. 4주 계획과 9개 큰 항목만 있던 자료를 작업별 산출물·완료 기준·선행 관계·근거로 확장했다. 참고 중간보고서의 기능 3단계, 작업 ID·레벨·요구·선행·날짜 구조를 반영했다.'),
           p('읽는 기준','h2')]
    for note in DATA['assumptions'][:4]:story.append(p(note,'small'))
    story.append(p(f'잔여 필수 {len(pending)}개 작업의 예상 공수는 팀 합산 {hours}시간이다. 이는 추정치이며 실제 기록이 아니다. 공동 담당 시간을 인원수만큼 중복 계산하지 않는다. 완료 항목 수를 프로젝트의 품질 또는 전체 진척률로 해석하지 않는다.','small'))

    story += [PageBreak(),p('1. 전체 일정과 주요 마일스톤','h1'),p('기존: 과거 문서의 학기 계획 틀 / 확인: 산출물을 확인한 주차 / 예정: 이번 상세 WBS의 후속 일정안','small')]
    headers=['ID','작업 묶음','완료/필수']+[f'{i+1}주\n{d[5:].replace("-","/")}' for i,d in enumerate(DATA['weeks'])]
    grid=[]; marks=[]
    for group in DATA['groups']:
        own=[t for t in DATA['tasks'] if t['group']==group['id']]
        req=[t for t in own if t['priority']=='필수']
        row=[group['id'],group['name'],f'{sum(t["status"]=="완료 확인" for t in req)}/{len(req)}']
        for i,week in enumerate(DATA['weeks']):
            a=date.fromisoformat(week);b=a+timedelta(days=6)
            confirmed=any(t['evidence_date'] and a<=date.fromisoformat(t['evidence_date'])<=b for t in own)
            scheduled=any(t['plan_start'] and date.fromisoformat(t['plan_start'])<=b and date.fromisoformat(t['plan_end'])>=a for t in own)
            row.append('확인' if confirmed else '예정' if scheduled else '기존' if i+1 in group['original_plan_weeks'] else '')
        grid.append(row)
    gantt=table(headers,grid,[40,160,58]+[(CONTENT-258)/15]*15)
    gantt.setStyle(TableStyle([('LEFTPADDING',(3,0),(-1,-1),3),('RIGHTPADDING',(3,0),(-1,-1),3)]))
    for r,row in enumerate(grid,1):
        for c,value in enumerate(row[3:],3):
            if value:gantt.setStyle(TableStyle([('BACKGROUND',(c,r),(c,r),colors.HexColor({'확인':'#DDEFE4','예정':'#E7E5FA','기존':'#E9ECF0'}[value]))]))
    story += [gantt,Spacer(1,10),p('11/12는 학기 9주차이며 11/13의 주간보고가 10주차다. 과거 실제 시작·종료일이 없는 항목은 후속 표에서도 확인일만 제시한다. 일부 기존 계획 주차보다 확인 시점이 빠른 것은 계획과 확인 이력을 구분한 결과다.','small')]
    story += [PageBreak(),p('2. 다음 실행 순서와 완료 관문','h1')]
    milestones=[
        ['M0','11/12','요약 v2·회귀·GitHub 검사 통과','3.1.4~5, 4.1.5','완료 확인'],
        ['M1','11/16','한·영 React 지침, 세션 정책, 새 평가 입력 고정','3.1.10, 1.1.5, 4.2.5','일정안'],
        ['M2','11/18','세션 권한 통합 검사와 새 원문·과제 비교','4.1.7, 4.2.6~7','일정안'],
        ['M3','11/20','변경분 회귀·설계·시연 자료 정합성','4.1.8, 5.2.2, 5.1.2','일정안'],
        ['M4','11/27','백업 복원·모바일·시연 결함 정리','5.1.3~5','일정안'],
        ['M5','12/04','기능 범위 고정·릴리스 후보','5.1.9','일정안'],
        ['M6','12/14','최종 발표·시연·질문 대응 준비','5.2.4','일정안'],
        ['M7','12/18','제출본 점검·최종 인계','5.2.5~6','일정안'],
    ]
    story += [table(['관문','목표일','완료 조건','연결 WBS','상태'],milestones,[48,62,370,200,CONTENT-680]),Spacer(1,10),
              p('우선 순서','h2'),p('세션 접근 정책 결정 → 서버 구현 → 교차 계정 검사. 한·영 React 지침 정렬 → 새 평가 원문·과제 고정 → 독립 출력 비교 → 채택 판단. 두 흐름이 끝난 뒤 전체 회귀와 설계서·시연 자료를 갱신한다.'),
              p('최신 요약 v2는 입력·충돌 처리의 기술 검사까지 완료됐다. 새 원문에서 수동 프롬프트 대비 내용 보존을 비교하는 작업 4.2.6은 아직 예정이다. 이전 원문 9개의 결과를 새 v2의 출력 검증으로 옮기지 않는다.','small')]
    near=sorted([t for t in pending if t['plan_end'] and t['plan_end']<='2026-11-20'],key=lambda t:(t['plan_end'],t['id']))
    story += [PageBreak(),p('2.1 11월 20일까지의 상세 실행안','h1'),p('기존 주간보고의 다음 주 계획을 작업 단위로 나눴다. 날짜와 공수는 합의 전 제안이며, 이번에 만든 WBS 자체도 팀 검토 대기로 표시했다.','small'),
              table(['ID','할 일','담당(안)','종료(안)','공수(h)','선행'],[[t['id'],t['name'],t['owner'],t['plan_end'][5:],str(t['estimate_hours']),', '.join(t['predecessors'])] for t in near],[55,320,80,75,65,CONTENT-595])]
    for group_index, group in enumerate(DATA['groups']):
        own=[t for t in DATA['tasks'] if t['group']==group['id']]
        story += [PageBreak() if group_index == 0 else CondPageBreak(180),Spacer(1,12),p(f'3. 상세 WBS  {group["id"]}  {group["name"]}','h1'),
                  p(f'단계: {group["phase"]}  /  하위 작업 {len(own)}개  /  ID는 기존 주간보고의 묶음을 유지한 3단계 작업 번호','caption')]
        rows=[]
        for t in own:
            timing=(f'{t["plan_start"][5:]} - {t["plan_end"][5:]}\n공수 {t["estimate_hours"]}h (안)' if t['plan_start'] else
                    '확인 11/12\n실제 일정 미확인' if t['evidence_date'] else '미정\n선택/외부 조건 필요')
            name=f'<b>{escape(t["name"])}</b><br/>{escape(t["status"])} / {escape(t["priority"])}<br/>담당(안): {escape(t["owner"])}'
            trace=f'{t["requirements"]}\n선행: {", ".join(t["predecessors"]) or "없음"}'
            criteria=f'<b>산출물</b> {escape(t["deliverable"])}<br/><b>완료 기준</b> {escape(t["acceptance"])}<br/><font color="#64748B">근거: {", ".join(t["sources"])}'
            if t['note']:criteria+=f'<br/>{escape(t["note"])}'
            criteria+='</font>'
            rows.append([t['id'],p(name,'cell',True),trace,timing,p(criteria,'cell',True)])
        t=table(['작업 ID','작업·상태·담당','요구사항·선행','일정·공수','산출물·완료 기준·확인 근거'],rows,[55,170,130,100,CONTENT-455])
        for i,task in enumerate(own,1):t.setStyle(TableStyle([('BACKGROUND',(0,i),(0,i),colors.HexColor(STATES[task['status']]))]))
        story.append(t)
    story += [PageBreak(),p('4. 기능의 3단계 분해와 요구 추적','h1'),
              p('업무 기능의 분해이며 개발 작업의 날짜·공수와 중복 집계하지 않는다. 대기능 8개 → 논리 기능 16개 → 세부 기능 54개다. 관련 WBS를 통해 구현·유지·변경 작업을 찾는다.','small')]
    for subsystem in dict.fromkeys(f['subsystem'] for f in DATA['functions']):
        own=[f for f in DATA['functions'] if f['subsystem']==subsystem]
        story += [p(subsystem,'h2'),table(['기능 ID','논리 기능','세부 기능 / 요구 ID','수용 기준','관련 WBS'],
          [[f['id'],f['feature'],f'{f["name"]}\n{f["requirement"]}',f['criterion'],f['wbs']] for f in own],
          [67,132,160,CONTENT-489,130])]
    story += [PageBreak(),p('5. 완료 판단과 유지 방법','h1')]
    rules=[
      ['완료 확인','해당 작업의 산출물과 명시한 기술 검사 근거가 있다. 사람의 효과·모든 환경 지원·배포 완료를 뜻하지 않는다.'],
      ['예정','후속 일정·공수를 제안한 필수 작업이다. 실제 시작·종료일은 아직 기록하지 않는다.'],
      ['검토 대기','초안은 있으나 팀의 연결·범위·담당 검토가 남아 있다.'],
      ['선택 후속','현 필수 완료 조건 밖이다. 수행 조건·자료·참여자·비용을 확보한 뒤 별도로 착수한다.'],
      ['외부 대기','실행 의사가 있어도 로그인 등 외부 조건을 확보하지 못했다. 완료나 실패로 바꾸지 않는다.'],
    ]
    story += [table(['상태','정의'],rules,[110,CONTENT-110]),Spacer(1,12),
      p('완료 증거를 붙일 때','h2'),p('작업 ID에 커밋·검사 로그·문서 판본을 연결한다. 요구가 바뀌면 기존 완료 기록을 덮어쓰기보다 변경 작업을 추가한다. 고정 실험의 과제·첫 응답·점수는 보존한다. 새 지침을 변경한 경우 새 최종 원문·과제로 확인하고 동률·열세도 기록한다.'),
      p('일정과 담당을 바꿀 때','h2'),p('엑셀 상세 WBS의 노란 입력 셀에서 상태·담당·날짜·공수를 수정한다. 기간은 종료일-시작일+1의 달력일이다. 휴일을 추정해 영업일로 변환하지 않는다. 실제 작업일은 확인한 뒤 실제 시작·종료 열에 입력한다.'),
      p('기존 자료와의 관계','h2'),p('주간보고 v0.6과 전체 분석·설계서 v1.0은 당시 기준으로 보존한다. 이번 WBS는 새 관리 기준안이며 과거 보고서를 소급 교체하지 않았다. 운영 13개 코딩 환경 연결은 유지 항목이며 실제 모델 생성 효과까지 전부 검증됐다는 의미가 아니다.')]
    story += [PageBreak(),p('6. 근거 자료','h1'),p('근거 ID는 상세 WBS의 마지막 열과 연결된다. 링크는 확인한 코드 커밋 또는 해당 검사 실행을 가리킨다.','small')]
    for s in DATA['sources']:
        story.append(p(f'<b>{s["id"]}</b>  <a href="{escape(s["url"])}" color="#405C99">{escape(s["title"])}</a>','body',True))
    story += [Spacer(1,10),p('이번 WBS에서 새로 실행한 것은 문서 구조·선행 순환·날짜·집계·파일·가독성 검사다. 위 프로젝트 검증 수치는 기존의 날짜가 있는 실행 증거를 인용했다. 유료 모델 API는 호출하지 않았다.','small')]
    OUT.parent.mkdir(parents=True,exist_ok=True)
    doc=SimpleDocTemplate(str(OUT),pagesize=(W,H),leftMargin=M,rightMargin=M,topMargin=40,bottomMargin=38,
                          title='Revealed 전체 개발 상세 WBS v1.0',author='팀 Revealed',pageCompression=1)
    doc.build(story,onFirstPage=page,onLaterPages=page)
    print(OUT)


if __name__=='__main__':build()

"""Revealed weekly report, matching the supplied course PDF structure."""
from pathlib import Path
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader, PdfWriter

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'output/pdf/Revealed_진행현황_주간보고서_2026-11-05.pdf'
TMP=ROOT/'tmp/weekly_2026_11_05'
TEMPLATE=Path('C:/Users/Laptop_PC/Downloads/AI.SW 융합프로젝트_주간보고서_Template_v0.3 (1).pdf')
W,H=780,540
NAVY='#082452'; GREEN='#185B32'; GRAY='#515151'; MUTED='#626A73'
PALE='#F1F3F5'; TEAL='#168779'
pdfmetrics.registerFont(TTFont('Malgun','C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBold','C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFontFamily('Malgun',normal='Malgun',bold='MalgunBold')
OVERFLOW=[]
buf=BytesIO()
c=canvas.Canvas(buf,pagesize=(W,H))
c.setTitle('Revealed 선호 기반 프롬프트 도구 주간보고서 2026년 11월 5일')
c.setAuthor('윤정우 · 고차원')

def rect(x,y,w,h,fill,stroke=None):
    c.setFillColor(HexColor(fill));c.setStrokeColor(HexColor(stroke or fill))
    c.rect(x,H-y-h,w,h,fill=1,stroke=bool(stroke))

def txt(s,x,y,w,size=13,color='#171717',bold=False,leading=None,maxh=None,align=0):
    style=ParagraphStyle('t',fontName='MalgunBold' if bold else 'Malgun',fontSize=size,
          leading=leading or size*1.43,textColor=HexColor(color),wordWrap='CJK',alignment=align)
    p=Paragraph(s,style);_,h=p.wrap(w,1000)
    if maxh is not None and h>maxh+.2: OVERFLOW.append((s[:65],h,maxh))
    p.drawOn(c,x,H-y-h)
    return h

def header(title,n,sub=''):
    txt(title,34,25,712,21,bold=True,maxh=32)
    rect(34,64,712,3,'#111111')
    if sub:txt(sub,35,77,710,10.3,color=MUTED,maxh=29)
    txt('Revealed  |  AI/SW융합프로젝트  |  2026.11.05',34,519,630,8.2,color=MUTED)
    txt(str(n),718,516,28,10,align=2)

def table(headers,rows,x=34,y=110,widths=None,size=12):
    widths=widths or [712/len(headers)]*len(headers)
    def pp(text,head=False):
        return Paragraph(text,ParagraphStyle('cell',fontName='MalgunBold' if head else 'Malgun',
             fontSize=size,leading=size*1.38,wordWrap='CJK',textColor=white if head else black))
    data=[[pp(s,True) for s in headers]]+[[pp(str(s)) for s in r] for r in rows]
    t=Table(data,colWidths=widths,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),HexColor(GRAY)),
       ('ROWBACKGROUNDS',(0,1),(-1,-1),[white,HexColor('#F4F5F6')]),('VALIGN',(0,0),(-1,-1),'TOP'),
       ('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),
       ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),
       ('LINEBELOW',(0,0),(-1,-1),.4,HexColor('#D5D7DA'))]))
    _,h=t.wrap(sum(widths),1000)
    if y+h>507:OVERFLOW.append(('table',y+h,507))
    t.drawOn(c,x,H-y-h);return h

def weekly(n,title,left,right,issues,requests,sub=''):
    header(title,n,sub)
    top=110; split=390
    for x,w,label,color in [(34,356,'금주 실적  10/30 ~ 11/05','#888888'),(390,356,'차주 계획  11/06 ~ 11/12',GRAY)]:
        rect(x,top,w,30,color);txt(label,x+12,top+4,w-24,13.5,'#FFFFFF',True)
    c.setStrokeColor(HexColor('#C5C5C5'));c.setLineWidth(.65)
    for x in (34,335,390,691,746):c.line(x,H-140,x,H-405)
    for x,items in [(34,left),(390,right)]:
        y=148
        gap=min(76,252/len(items))
        for title,detail,date in items:
            txt('▪ '+title,x+8,y,280,12.7,bold=True,maxh=22)
            txt(detail,x+17,y+22,274,11.4,maxh=gap-25)
            txt(date,x+302,y+3,51,9.3,align=1,maxh=40)
            y+=gap
    for x,title,content in [(34,'주요 이슈 및 의사결정 사항',issues),(390,'프로젝트 요청 사항',requests)]:
        rect(x,405,356,27,'#F0F0F0');txt(title,x+9,409,338,12,bold=True,align=1)
        txt(content,x+8,439,340,11.3,maxh=64)
    rect(34,505,712,1.5,'#B9B9B9')
    c.showPage()

def note(s,y=480):
    txt(s,35,y,710,10.2,color=MUTED,maxh=31)

# 1 Cover: merge the course template below; overlay only the project-specific text.
txt('선호 기반 프롬프트 자동 생성 도구',35,192,463,20,'#FFFFFF',True)
txt('팀 Revealed  ·  윤정우 · 고차원',35,228,465,14,'#FFFFFF')
txt('금주 실적 10/30 ~ 11/05   |   차주 계획 11/06 ~ 11/12',35,380,710,14,bold=True)
txt('선택 기반 코딩 연구를 지침의 저장과 재사용으로 확장',35,412,710,13,color=MUTED)
txt('작성일 2026.11.05  ·  구현·실험 실적 기준 2026.11.04',35,442,710,10.5,color=MUTED)
c.showPage()

# 2 WBS
header('1. 프로젝트 일정 - WBS',2,'현재 단계: 구현 결과 점검과 통합 준비  |  다음 주에는 React 한 환경의 재사용 흐름에 집중')
weeks=['11/03<br/>~11/05','11/06<br/>~11/12','11/13<br/>~11/19','11/20<br/>~11/26','11/27<br/>~12/03']
rows=[
 ['분석','기존 연구·제품 범위 정리','확인','●','','','',''],
 ['연구','React 비교 실험·결과 해석','완료','●','○','','',''],
 ['구현','선호 지침·보관함·재사용','구현','●','○','','',''],
 ['구현','팀 조합·인수인계 기능','구현','●','','○','',''],
 ['통합','연구 브랜치 변경 선별·적용','계획','','○','○','',''],
 ['검증','새 과제의 스타일·기능 평가','계획','','○','○','',''],
 ['안정화','초안 보존·작업 복귀·오류 수정','계획','','○','○','○',''],
 ['발표','시연·근거·최종 보고 정리','계획','','','','○','○']]
    # Dots are an observed/current activity or a proposed future window, not a completion ratio.
table(['단계','작업','상태']+weeks,rows,y=113,widths=[55,206,49]+[80.4]*5,size=10.5)
note('● 금주 확인한 실적   ○ 후속 계획안   |   11/13 이후 일정은 수업 피드백에 따라 조정',474)
note('전체 완료율은 산정하지 않음. 기능 구현, 효과 검증, 브랜치 통합은 별도로 관리.',493)
c.showPage()

# 3 Research progress
weekly(3,'2. 프로젝트 진행현황 - 코딩 실험',[
 ('선택 기반 React 비교 실험','3개 차수에서 무지침 대비 스타일 통과율<br/>+28.89 · +27.78 · +23.33%p 관찰','11/04'),
 ('AI 재서술 단계의 도입 판단','두 차수 모두 추가 이득 기준 미충족<br/>구현은 보존하고 기본 사용은 비활성화','11/03~04'),
 ('평가 도구 보완과 후속 판단','다중 파일 진입점 처리 수정·재채점<br/>4차는 과제 부족으로 확증 실험 미실행','11/04')],[
 ('비교 조건과 판정 기준 고정','React 재사용 평가 범위와 새 과제 선정<br/>스타일·기능·미확인을 구분해 기록','~11/08'),
 ('기존 평가 도구 적용 검토','진입점 처리와 보호 규칙 변경을 선별<br/>현재 브랜치와 충돌·회귀 여부 확인','~11/10'),
 ('독립 과제 평가표 준비','API 없는 점검을 먼저 마친 뒤 실행 범위 결정<br/>실행한 조건만 다음 보고에 반영','~11/12')],
 '모의 프로필 4 × 과제 5 × 3회 = 차수당 60단위.<br/>실사용자 만족도나 전체 코드 품질의 개선 수치가 아님.',
 '고차원: 비교 기준·평가 도구 정리 제안.<br/>교수님: 자동 평가 중심의 다음 검증 범위 검토 요청.',
 '고차원 진행 보고와 연구 브랜치의 완료 기록  |  담당 표기는 다음 주 역할 제안')

# 4 Product
weekly(4,'2. 프로젝트 진행현황 - 마이크로스톤',[
 ('코딩 선호 입력과 지침 조립','설명·주석·구성·출력 4항목 선택<br/>준비 예시 비교 또는 직접 설정','11/03~04'),
 ('보관함과 새 작업 재사용','선호 설정·지침 저장과 재사용<br/>지침과 이번 작업 요청을 함께 복사','11/03~04'),
 ('팀 기준과 인수인계 연결','지원 분류의 개인·팀 기준 비교·조합<br/>작업 맥락·파일·사용 지침 공유','11/03~04'),
 ('선택적 GEPA와 답변 확인','13개 환경 조합에 GEPA 실행 경로 연결<br/>주석·설계 적절성은 자동 점수와 분리','11/04')],[
 ('React 한 흐름을 대표 시연으로 고정','선택 → 지침 → 저장 → 새 과제 재사용<br/>기존 추정과 새 직접 선택을 구별','~11/07'),
 ('화면 이탈 후 초안 보존','상단 이동 시 입력 손실 재현·수정<br/>작성 중 경고 또는 복구 동작 확인','~11/10'),
 ('복사·재사용과 결과 재열람 점검','선택 설정과 저장 지침의 일치 확인<br/>GEPA 작업 복귀·비교 근거 재표시 검토','~11/12')],
 '새 코딩 흐름은 명시적 선택이다.<br/>기존 React 선호 추정과 같다고 설명하지 않음.<br/>13개 환경 연결이 13개 환경의 효과 입증은 아님.',
 '윤정우: 화면·저장·복귀 동선 보완 제안.<br/>이번 주 범위는 코딩과 재사용에 집중하며 AWS 제외.',
 '현재 서비스 브랜치의 구현 실적  |  기존 React 비교 기능은 별도 진입점으로 유지')

# 5 Verification
weekly(5,'2. 프로젝트 진행현황 - 검증과 통합',[
 ('마이크로스톤 회귀 검사 기록','프론트 86개 통과·프로덕션 빌드 통과<br/>Python 1,083개 통과·1개 실패','11/04'),
 ('실패 원인과 재현 항목 정리','실패 1개는 UTF-8 단독 재실행에서 통과<br/>초안 소실·GEPA 복귀 누락 재현','11/04'),
 ('연구와 서비스 브랜치 비교','고차원 연구 결과와 현행 기능 범위 대조<br/>연구 브랜치의 최신 변경은 아직 미통합','11/05')],[
 ('통합 대상과 제외 대상을 기록','평가 도구·버그 수정부터 변경별 검토<br/>재서술 기능은 기본 비활성 유지','~11/08'),
 ('오류 경로 보완 후 회귀 검사','Windows 출력 인코딩을 명시<br/>수정한 환경에서 전체 검사 다시 기록','~11/11'),
 ('통합 시연과 결과표 정리','기능 동작·자동 평가·미확인을 분리<br/>실패 사례와 완료 조건을 함께 보고','~11/12')],
 '전체 Python 검사가 모두 통과했다고 보고하지 않음.<br/>서비스 기능 검사는 AI 품질·사용성 검증과 별개.<br/>연구 코드와 현재 서비스의 점수도 직접 합산하지 않음.',
 '윤정우·고차원 공동: 통합 범위와 완료 기준 합의.<br/>신규 사용자 모집은 다음 주 필수 조건으로 두지 않음.',
 '검사 수치는 11/04 실행 기록  |  11/05에 전체 테스트를 새로 실행한 결과가 아님')

# 6 Continuity
header('[Backup] 기존 주제를 어떻게 이어가는가',6,'수업 주제: 사용자가 고른 코딩 선호를 재사용 가능한 프롬프트로 만드는 도구')
table(['구분','고차원의 기존 코딩 연구','마이크로스톤의 새 코딩 흐름'],[
 ['선호 입력','결과를 반복 비교하고 선택 이력으로 추정','항목별 예시 비교 또는 명시적 설정'],
 ['대상·항목','TypeScript/React<br/>파일 구성·스타일 관리·타입 표기','여러 언어·프레임워크<br/>설명·주석·코드 구성·출력 방식'],
 ['지침 개선','선호 문장 재서술을 별도로 실험<br/>추가 이득 기준 미달로 기본 비활성','선택적 GEPA로 보충 안내 탐색<br/>원본 지침을 고정하고 후보를 비교'],
 ['근거 범위','모의 프로필의 스타일 검사<br/>타입·빌드·고정 동작 시나리오','선택·저장·재사용 구현 검사<br/>새 GEPA는 주로 제한된 정적 평가'],
 ['이어갈 부분','선호 비교·독립 평가·실패 분석','지침 보관·새 과제 재사용·지원 분류 공유']],
 y=111,widths=[84,314,314],size=11.5)
rect(34,430,712,61,'#EDF4F1')
txt('선택 → 개인 지침 생성 → 보관 → 다음 작업에 재사용',48,439,684,15,bold=True)
txt('개발 기반은 마이크로스톤으로 유지하고, 기존 React 연구의 방법과 근거를 연결한다.',48,465,684,11.4)
c.showPage()

# 7 Detailed study
header('[Backup] 코딩 실험의 결과와 한계',7,'고차원 보고 기준  |  프롬프트 없음 A · 규칙 조립 B · AI 재서술 C · 요청 대조 규칙 D')
table(['비교','확인한 수치','해석·상태'],[
 ['B - A 스타일 통과율','1차 +28.89%p / 2차 +27.78%p<br/>3차 +23.33%p','세 차수에서 목표 스타일 준수 증가<br/>공통 지침 효과도 포함'],
 ['C - B 스타일 통과율','1차 -3.89%p / 2차 +1.67%p','두 차수 모두 도입 기준 미충족<br/>3차는 재서술 비교가 아님'],
 ['D - B 기능 통과율','3차 -1.67%p<br/>95% 구간 -10.00 ~ +6.67%p','요청 대조 규칙의 개선 기준 미충족<br/>과제가 쉬워 개선 여지도 작음'],
 ['4차 기능 저하 원인','중간 난이도 과제 2개 확보<br/>계획의 최소 요건 3개에 미달','과제 선정까지만 진행<br/>확증 실험 미실행']],
 y=111,widths=[151,281,280],size=11.7)
txt('판정할 때 남겨야 할 조건',35,390,710,13,bold=True)
txt('• 차수당 독립 과제는 5개. 60단위를 참여자 60명으로 설명하지 않는다.<br/>'
    '• 일부 차수에서는 조립본의 기능 통과율이 더 낮았다. 원인은 아직 분리하지 못했다.<br/>'
    '• 보고된 API 요청은 과제 선정 포함 550회. 실제 청구 금액과 사용자 만족도는 미확인.',
    35,418,710,11.7,maxh=76)
c.showPage()

# 8 Actual screen evidence
header('[Backup] 코딩 지침 생성과 재사용 화면',8,'2026.11.04 로컬 화면  |  준비 예시·예시 계정 사용  |  새 AI 성능 실험을 시연한 화면이 아님')
for x,label,file in [(34,'① 예시를 보고 작성 방식 선택','02-code-comparison.jpg'),
                      (400,'② 선택 요약과 실제 지침 확인','03-my-prompt.jpg')]:
    txt(label,x,116,346,14,bold=True)
    img=ImageReader(str(ROOT/'docs/screenshots/current'/file))
    iw,ih=img.getSize(); scale=min(346/iw,270/ih); dw,dh=iw*scale,ih*scale
    rect(x,151,346,277,'#F1F3F5')
    c.drawImage(img,x+(346-dw)/2,H-151-dh,dw,dh,mask='auto')
txt('지침 저장 후에는 새로운 작업 요청과 함께 복사해 재사용한다.',35,451,710,14,bold=True)
txt('기존 React 비교·팀 기준은 별도 경로다. 새 언어별 지침을 기존 팀 기준에 자동 합치지 않는다.',35,480,710,11,color=MUTED)
c.showPage()

# 9 Acceptance plan
header('[Backup] 다음 주 계획과 완료 기준',9,'11/06 ~ 11/12 계획안  |  다음 주의 핵심은 범위 확장보다 React 재사용 흐름의 점검')
table(['기한','작업·담당 제안','완료를 판단할 자료'],[
 ['11/07','윤정우<br/>대표 시연 경로와 화면 안내 정리','선택 → 저장 → 재사용 1개 흐름의 화면 순서<br/>기존 추정·새 직접 선택을 구별하는 설명'],
 ['11/08','고차원<br/>비교 조건·새 과제·자동 판정 기준 고정','원문·선호·일반 지침의 차이를 적은 평가표<br/>기능·스타일·미확인 기준과 과제 ID'],
 ['11/10','윤정우<br/>초안 소실·복귀 경로 보완','상단 메뉴 이동 전후의 입력 유지·경고 검사<br/>진행 중 작업의 복구 여부 기록'],
 ['11/11','윤정우·고차원<br/>연구 변경의 선별 적용과 회귀 검사','충돌 검토·변경별 회귀 결과<br/>Windows 오류 경로와 실패 원인 기록'],
 ['11/12','윤정우·고차원<br/>확인한 결과로 주간보고 갱신','실행한 조건의 과제별 표·실패 사례·호출 기록<br/>미실행 항목은 계획 상태로 유지']],
 y=112,widths=[64,238,410],size=11.8)
note('API를 쓰는 비교는 범위·호출 상한을 먼저 확정. 사용자 만족도·협업 효과는 완료 기준에 포함하지 않는다.',480)
c.showPage()

# 10 sources & requests
header('[Backup] 확인 근거와 요청 사항',10,'코드·실험 기록·실제 화면을 분리해 확인할 수 있도록 자료를 연결')
links=[
 ('현재 서비스 코드 및 화면 안내','a2f1292 · microstone',
  'https://github.com/a77315829-byte/preference-prompt-tool/tree/a2f12928717c11555c7376d0efdd27e0b0703b51'),
 ('고차원 코딩 연구와 결과','fee9d1c · coding-ai-upgrade',
  'https://github.com/a77315829-byte/preference-prompt-tool/tree/fee9d1c67ae448dfab88cced704463ecaf9e499e'),
 ('3차 실험 계획 및 판정','요청 대조 규칙의 기능 효과',
  'https://github.com/a77315829-byte/preference-prompt-tool/blob/fee9d1c67ae448dfab88cced704463ecaf9e499e/docs/rule_based_function_preregistration.md'),
 ('4차 과제 선정과 확증 미실행','기능 저하 원인 판정은 보류',
  'https://github.com/a77315829-byte/preference-prompt-tool/blob/fee9d1c67ae448dfab88cced704463ecaf9e499e/docs/function_cost_preregistration.md'),
 ('현재 서비스 점검 기록','11/04 회귀·초안 소실·작업 복귀',
  'https://github.com/a77315829-byte/preference-prompt-tool/blob/a2f12928717c11555c7376d0efdd27e0b0703b51/docs/history/2026-11-04_project_review.md')]
for i,(name,desc,url) in enumerate(links):
    y=112+i*48
    txt(name,35,y,350,13,NAVY,True)
    txt(desc,407,y+1,338,11.5,color=MUTED)
    c.linkURL(url,(34,H-y-24,745,H-y+2),relative=0)
    rect(35,y+33,710,.5,'#DDDDDD')
rect(34,368,712,116,'#F3F5F7')
txt('수업에서 검토받을 사항',48,381,684,14,bold=True)
txt('1. 기존 선택 기반 코딩 연구를 중심에 두고, 저장·재사용을 활용 확장으로 설명하는 범위<br/>'
    '2. 사용자 모집 없이 새 과제의 스타일·기능·오류를 함께 확인하는 다음 검증 계획<br/>'
    '3. 기존 연구 코드의 선별 통합과 시연 안정화를 다음 주 우선순위로 두는 일정',
    48,409,684,12,maxh=70)
c.showPage()

# 11 Closing uses the supplied closing page.
txt('Revealed  |  윤정우 · 고차원',35,453,710,15,color='#FFFFFF')
c.showPage()
c.save()
assert not OVERFLOW, OVERFLOW
base=PdfReader(TEMPLATE); overlay=PdfReader(BytesIO(buf.getvalue()));writer=PdfWriter()
for i,p in enumerate(overlay.pages):
    if i==0:
        original=base.pages[0];original.merge_page(p);writer.add_page(original)
    elif i==len(overlay.pages)-1:
        original=base.pages[4];original.merge_page(p);writer.add_page(original)
    else:writer.add_page(p)
writer.add_metadata({'/Title':'Revealed 선호 기반 프롬프트 도구 주간보고서 2026.11.05',
 '/Author':'윤정우 · 고차원','/Subject':'AI/SW융합프로젝트 금주 실적과 차주 계획'})
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open('wb') as f:writer.write(f)
print(OUT, 'pages',len(writer.pages))

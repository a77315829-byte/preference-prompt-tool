"""Course weekly report with implementation evidence and design deliverables."""
from pathlib import Path
from io import BytesIO
from math import atan2, cos, sin, pi
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader, PdfWriter
from build_design import FR, NFR, WBS
from build_uml import Diagram

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'output/pdf/Revealed_진행현황_주간보고서_2026-11-05_보완본.pdf'
TEMPLATE=Path('C:/Users/Laptop_PC/Downloads/AI.SW 융합프로젝트_주간보고서_Template_v0.3 (1).pdf')
W,H=780,540
INK='#17202D';MUTED='#626A73';NAVY='#082452';TEAL='#158C80';PALE='#EFF5F4';GRAY='#515151'
pdfmetrics.registerFont(TTFont('MG','C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MGB','C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFontFamily('MG',normal='MG',bold='MGB')
buf=BytesIO();c=canvas.Canvas(buf,pagesize=(W,H));OVERFLOW=[]

def rect(x,y,w,h,color,stroke=None):
    c.setFillColor(HexColor(color));c.setStrokeColor(HexColor(stroke or color))
    c.rect(x,H-y-h,w,h,fill=1,stroke=bool(stroke))

def txt(s,x,y,w,size=12,color=INK,bold=False,maxh=None,align=0):
    p=Paragraph(str(s),ParagraphStyle('p',fontName='MGB' if bold else 'MG',fontSize=size,
      leading=size*1.42,wordWrap='CJK',textColor=HexColor(color),alignment=align))
    _,h=p.wrap(w,1500)
    if maxh is not None and h>maxh+.5:OVERFLOW.append((c.getPageNumber(),str(s)[:45],round(h,1),maxh))
    p.drawOn(c,x,H-y-h)
    return h

def header(title,sub=''):
    txt(title,34,25,712,21,bold=True,maxh=32);rect(34,64,712,3,'#111111')
    if sub:txt(sub,35,77,710,10.1,MUTED,maxh=29)
    txt('Revealed  |  AI/SW융합프로젝트  |  2026.11.05',34,519,650,8.2,MUTED)
    txt(str(c.getPageNumber()),718,516,28,10,align=2)

def note(s,y=480):txt(s,35,y,710,10.2,MUTED,maxh=31)

def table(head,rows,widths=None,y=112,size=11.2,pad=7):
    widths=widths or [712/len(head)]*len(head)
    def pp(s,h=False):return Paragraph(str(s),ParagraphStyle('cell',fontName='MGB' if h else 'MG',fontSize=size,
      leading=size*1.35,wordWrap='CJK',textColor=white if h else HexColor(INK)))
    t=Table([[pp(s,True) for s in head]]+[[pp(s) for s in r] for r in rows],colWidths=widths)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),HexColor(GRAY)),
      ('ROWBACKGROUNDS',(0,1),(-1,-1),[white,HexColor('#F2F4F5')]),('VALIGN',(0,0),(-1,-1),'TOP'),
      ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
      ('TOPPADDING',(0,0),(-1,-1),pad),('BOTTOMPADDING',(0,0),(-1,-1),pad),
      ('LINEBELOW',(0,0),(-1,-1),.4,HexColor('#D3D8DB'))]))
    _,h=t.wrap(712,1500)
    if y+h>505:OVERFLOW.append((c.getPageNumber(),'table',y+h,505))
    t.drawOn(c,34,H-y-h)
    return y+h

def weekly(title,left,right,issues,requests,sub,right_title='프로젝트 요청 사항'):
    header(title,sub)
    for x,label,color in [(34,'금주 실적  10/30 ~ 11/05','#777777'),(390,'차주 계획  11/06 ~ 11/12',GRAY)]:
        rect(x,110,356,30,color);txt(label,x+12,114,330,13,'#FFFFFF',True)
    c.setStrokeColor(HexColor('#C7CDD0'));c.setLineWidth(.6)
    for x in [34,335,390,691,746]:c.line(x,H-140,x,H-407)
    for x,items in [(34,left),(390,right)]:
        gap=252/len(items)
        for i,(title,body,date) in enumerate(items):
            y=149+i*gap
            txt('▪ '+title,x+9,y,280,12.5,bold=True,maxh=22)
            txt(body,x+17,y+22,273,11.1,maxh=gap-25)
            txt(date,x+302,y+4,51,8.8,align=1,maxh=38)
    for x,title,body in [(34,'주요 이슈 및 의사결정 사항',issues),(390,right_title,requests)]:
        rect(x,407,356,27,'#EEEEEE');txt(title,x+8,411,340,11.7,bold=True,align=1)
        txt(body,x+9,441,338,11.1,maxh=61)
    c.showPage()

def box(x,y,w,h,title,body='',size=11.5,fill=PALE):
    rect(x,y,w,h,fill,'#BAC8CC');txt(title,x+10,y+8,w-20,size,bold=True,maxh=35,align=1)
    if body:txt(body,x+10,y+35,w-20,size-1,maxh=h-41,align=1)

def line(x1,y1,x2,y2,color=MUTED,dash=False):
    c.setStrokeColor(HexColor(color));c.setLineWidth(.9);c.setDash(3,2) if dash else c.setDash()
    c.line(x1,H-y1,x2,H-y2);c.setDash()

def arrow(x1,y1,x2,y2,dash=False):
    line(x1,y1,x2,y2,dash=dash);a=atan2(y2-y1,x2-x1)
    line(x2,y2,x2-6*cos(a-.45),y2-6*sin(a-.45));line(x2,y2,x2-6*cos(a+.45),y2-6*sin(a+.45))

def shot(file,x,y,w,h):
    im=ImageReader(str(ROOT/'docs/screenshots/current'/file));iw,ih=im.getSize();s=min(w/iw,h/ih)
    rect(x,y,w,h,'#F1F3F5');c.drawImage(im,x+(w-iw*s)/2,H-y-(h+ih*s)/2,iw*s,ih*s,mask='auto')

def entity(x,y,w,title,body):
    rect(x,y,w,89,'#FFFFFF','#9AAAB2');rect(x,y,w,24,NAVY)
    txt(title,x+7,y+4,w-14,10.7,'#FFFFFF',True,maxh=18)
    txt(body,x+8,y+30,w-16,9.3,maxh=54)

# 1: cover
txt('선호 기반 프롬프트 자동 생성 도구',35,192,463,20,'#FFFFFF',True)
txt('팀 Revealed  ·  윤정우 · 고차원',35,228,465,14,'#FFFFFF')
txt('이번 주 구현 실적 · 설계 산출물 · 다음 주 실행 계획',35,379,710,15,bold=True)
txt('금주 10/30 ~ 11/05   |   차주 11/06 ~ 11/12',35,412,710,13,MUTED)
txt('구현·실험 기준 11/04  ·  설계 문서화 11/05  ·  AWS 제외',35,443,710,10.5,MUTED)
c.showPage()

# 2: template-like Gantt, observed vs proposed
header('1. 프로젝트 일정 - WBS','분석 → 설계 → 구현 → 통합·검증 → 이행·안정화  |  현재: 구현 결과 정리와 설계 문서화')
cols=[34,75,112,348,395,453,511,569,627,685,746]
rect(34,111,712,37,GRAY)
for x,w,s in [(34,41,'단계'),(75,37,'ID'),(112,236,'작업·산출물'),(348,47,'담당')]:txt(s,x+4,120,w-8,10,'#FFFFFF',True,align=1)
for i,s in enumerate(['10/30<br/>~11/05','11/06<br/>~11/12','11/13<br/>~11/19','11/20<br/>~11/26','11/27<br/>~12/03','12/04<br/>~12/11']):
    txt(s,397+i*58,114,55,9,'#FFFFFF',True,align=1)
for i,(wid,phase,task,owner,evidence,done,plan) in enumerate(WBS):
    y=148+i*22
    rect(34,y,712,22,'#F1F4F5' if i%2 else '#FFFFFF')
    txt(phase,37,y+4,35,8.5,maxh=17);txt(wid,80,y+4,29,9,maxh=17)
    txt(task,117,y+4,224,9.5,maxh=17);txt(owner,349,y+4,44,9,align=1,maxh=17)
    for j in done:
        rect(402+j*58,y+6,43,10,TEAL)
    for j in plan:
        rect(402+j*58,y+6,43,10,NAVY)
    line(34,y+22,746,y+22,'#DCE1E3')
for x in cols[4:]:line(x,148,x,456,'#DAE1E4')
line(453,108,453,461,'#D15E45',True)
rect(35,470,13,8,TEAL);txt('금주 확인 실적',53,465,125,10)
rect(180,470,13,8,NAVY);txt('후속 계획',198,465,110,10)
txt('실적: 11/03~04 구현·실험 / 11/05 문서화',328,465,418,10,MUTED)
note('막대는 해당 주의 활동을 뜻함. 전체 완료율은 산정하지 않으며, 향후 담당·일정은 수업 피드백 후 조정.',490)
c.showPage()

# 3-6: weekly sections, user work first
weekly('2. 프로젝트 진행현황 - 개인 지침·사용 화면',[
 ('코딩 입력 흐름과 예시 선택','환경 → 4항목 선호 → 지침 확인<br/>14개 언어 예시·FastAPI/Spring 전용 예시','11/03~04'),
 ('내 선호 보관함과 재사용','지침·선택 설정 저장, 수정·새 작업 복사<br/>선택 출처와 본문 불일치 안내','11/03~04'),
 ('화면 안내와 실제 자료 정리','선택 후 다음 버튼·보류 항목·취소 처리<br/>요약·코딩·팀 업무 실제 화면 19장 문서화','11/04'),
 ('답변 확인과 선택적 개선','형식 단서·직접 확인 질문 제공<br/>13개 환경의 GEPA 실행 경로 연결','11/04')],[
 ('대표 저장·재사용 흐름 확정','React 환경에서 선택 → 저장 → 재사용<br/>기존 추정 경로와 직접 선택 경로 구별','~11/07'),
 ('초안과 진행 작업 복귀 보완','상단 메뉴 이동 시 입력 손실 해결<br/>GEPA 작업 번호·완료 결과 재열람','~11/10'),
 ('화면·기능 대응 확인','설계 화면 ID별 정상·예외 흐름 점검<br/>저장한 설정과 재사용 지침 일치 확인','~11/12')],
 '새 코딩 흐름은 항목별 명시적 선택.<br/>14개 언어 예시는 언어별 실행 검증이 아니며<br/>GEPA 연결과 실제 개선 효과는 별도로 관리.',
 '윤정우 진행 영역: 화면·지침·보관·재사용.<br/>교수님 검토: 핵심 흐름과 보조 기능의 범위.',
 '윤정우 진행 영역  |  이번 주 기능 개발·화면 정리 실적')

weekly('2. 프로젝트 진행현황 - 팀 공유·업무 연결',[
 ('팀 초대와 개인·팀 기준 비교','비교 전에 팀 생성·초대 링크 제공<br/>지원 분류의 차이·동률·미정 표시','11/03'),
 ('작업용 조합과 변경 이력','항목별 개인/팀 출처 선택·별도 새 저장<br/>재조합·선택 되돌림·직전 항목 연결','11/03'),
 ('인수인계와 참고 파일 첨부','목적·진행·남은 일·지침·자료 저장<br/>지정 계정에 공유·이어받기·완료·버전 기록','11/03~04'),
 ('반복 업무 템플릿과 요청 점검','템플릿 24개: 기존 비교 6 + 새 초안 18<br/>요청 구조 점검·업무 지침 작업 공간 연결','11/03~04')],[
 ('두 계정의 권한 시나리오 점검','공유 전 기록·권한 없는 파일 접근 차단<br/>담당자 변경·버전 충돌·완료 후 처리','~11/09'),
 ('조합의 원본 보존 확인','출처·전후 차이·직전 연결 검토<br/>새 항목 저장과 원본 미변경 점검','~11/11'),
 ('핵심 시연과 보조 기능 구분','코딩 저장·재사용을 본 발표에 배치<br/>팀·인수인계는 활용 확장으로 설명','~11/12')],
 '새 언어별 직접 설정 지침은 React 팀 기준에<br/>자동 조합하지 않음. 다수 선호 집계를<br/>합의 완료·협업 시간 절감으로 주장하지 않음.',
 '윤정우 진행 영역: 팀 조합·이력·인수인계.<br/>두 계정의 기능 점검은 팀 내부에서 수행하며<br/>신규 참여자 모집을 필수 조건으로 두지 않음.',
 '윤정우 진행 영역  |  기존 개인화 지침을 공유·재사용하는 활용 확장')

weekly('2. 프로젝트 진행현황 - 설계·검증·운영 준비',[
 ('설계 산출물 작성','요구사항·UML·ERD·테이블·API 정리<br/>화면 정의·와이어프레임·WBS 작성','11/05'),
 ('회귀 검사와 남은 문제 정리','프론트 86 통과·빌드 통과<br/>Python 1,083 통과·1 실패, 단독 재실행 통과','11/04'),
 ('호스팅 실행 구조 준비','React + API 동일 주소·Docker·영구 저장<br/>로컬 재시작 후 계정·지침·첨부 유지 확인','11/04'),
 ('개발 기록과 수업 자료 정리','기능별 변경 기록·19장 화면·공유 자료<br/>현재 구현과 연구 브랜치의 차이 정리','11/04~05')],[
 ('설계와 구현의 대응 검토','요구사항 ID → 화면 → API → DB 확인<br/>문서 검토 후 GitHub 공유본 갱신','~11/08'),
 ('실패·복귀 경로 보완과 재검사','Windows 인코딩·초안·작업 복귀 개선<br/>같은 환경에서 전체 회귀 결과 기록','~11/11'),
 ('운영 조건과 통합 범위 결정','저장 유지·백업·HTTPS 확인 항목 정리<br/>연구 변경은 필요한 부분부터 선별','~11/12')],
 '실패 항목만 UTF-8 재실행에서 통과.<br/>전체 회귀 통과로 합산하지 않음.<br/>호스팅 준비는 공개 배포 완료가 아님.',
 '윤정우: 문서·운영·복귀 흐름 보완.<br/>공동: 설계 검토와 연구 코드 통합 범위 확인.<br/>새 설계문서는 로컬 작성 상태.',
 '11/05는 문서화 실적  |  테스트 수치는 11/04 기록이며 이번 문서 작성 중 새로 실행한 결과가 아님')

weekly('2. 프로젝트 진행현황 - 기존 코딩 실험 (고차원)',[
 ('선택 조립 지침 효과 (1·2·3차)','스타일 축: +28.89 / +27.78 / +23.33%p<br/>기능: -1.67 / -16.67 / -6.67%p<br/>차이 = B-A (두 지표를 함께 보고)','11/04'),
 ('AI 재서술 단계의 사용 판단','두 차수 추가 이득 기준 미충족<br/>재서술 구현 보존·기본 사용 비활성','11/03~04'),
 ('평가 도구와 후속 과제 점검','다중 파일 진입점 처리 수정·재채점<br/>4차는 적합 과제 부족으로 확증 미실행','11/04')],[
 ('React 비교 조건 고정','스타일·기능·미확인을 따로 기록<br/>최적화에 쓰지 않은 새 과제 확보','~11/08'),
 ('평가 도구와 수정의 선별 통합','현재 서비스와 변경 단위로 대조<br/>독립 평가·보호 규칙·회귀 여부 확인','~11/11'),
 ('실행한 범위의 결과표 작성','과제 ID·모델·검사 조건·실패 기록<br/>미실행 비교는 계획 상태로 유지','~11/12')],
 '모의 프로필 4 × 과제 5 × 3회 = 60단위.<br/>1차 기능 95% 구간: [-13.33, +10.00]%p.<br/>1·2차 기능은 검사 도구 수정 후 재채점.',
 '1차 구간은 0 포함: 차이를 확인 못함.<br/>2·3차 기능 저하 관찰, 원인은 미분리.<br/>실제 사용자 만족도·협업 효과 검증 아님.',
 '실험 A = 지침 없음, B = 선택으로 조립한 지침  |  화면의 예시 A/B와 다른 표기',
 right_title='결과 해석과 검증 범위')

# 7: continuity
header('3. 기존 연구와 이번 구현의 연결','중심 주제 유지: 선택한 선호 → 지침 생성 → 보관 → 새 작업 재사용')
table(['비교 항목','고차원: React 코딩 연구','윤정우: 기능 개발·사용 흐름'],[
 ['질문','선호 지침이 스타일·기능에 미치는 영향','지침을 만들고 보관·공유·재사용하는 방법'],
 ['선호 입력','반복 결과 비교와 선택 이력으로 추정<br/>파일 구성·스타일 관리·타입 표기','준비 예시 또는 직접 설정<br/>설명·주석·구성·출력 방식'],
 ['주요 산출물','비교 조건·자동 평가기·실험 결과','화면·계정별 저장·조합 이력·인수인계'],
 ['개선 경로','선호 문장 재서술의 추가 이득 평가','선택적 GEPA: 원본 고정·보충 안내 탐색'],
 ['현재 근거','모의 프로필의 스타일·기능 검사','구현·회귀·예시 계정 동작 / 효과는 별도 검증'],
 ['다음 연결','평가 도구·실패 분석·보호 규칙','대표 React 흐름·독립 과제·저장 일관성']],
 widths=[90,311,311],size=11.1)
note('기존 연구 결과를 다른 선호 축·다른 언어·팀 생산성의 증거로 그대로 옮기지 않는다.',480)
c.showPage()

# 8: functional requirements
header('[설계] 기능 요구사항','요구사항 식별자와 현재 상태를 함께 관리  |  상세 근거·인수 기준은 별도 설계문서')
table(['ID','기능','요구사항','상태'],[[a,b,d,c] for a,b,d,c,e in FR],
 widths=[54,103,448,107],size=10.3,pad=5)
note('FR05: 지원 분류만 팀 조합. FR08: 기존 비교 6 + 새 초안 18. FR09: 연결 구현과 효과 검증 구별.',490)
c.showPage()

# 9: nonfunctional + design checklist
header('[설계] 비기능 요구사항과 문서 작성 현황','구현 결과를 11/05에 문서화  |  코드와 설계의 대응 검토는 다음 주 진행')
table(['ID·항목','요구사항','상태'],[[a+' '+b,d,e] for a,b,d,e in NFR],widths=[128,384,200],size=10.3,pad=6)
rect(34,422,712,76,PALE)
txt('작성 산출물',46,432,105,11.5,bold=True)
txt('요구사항 · Use Case / Class / Sequence / State · ERD / 13개 테이블 정의<br/>'
    '핵심 API 명세 · 화면 정의 / 와이어프레임 / 스토리보드 · WBS',161,432,572,11.1,maxh=43)
txt('상태: 로컬 작성 완료 → 팀 검토·수업 피드백 → GitHub 공유본 반영',46,478,680,9.8,MUTED,maxh=16)
c.showPage()

# 10: architecture
header('[설계] 시스템 구성도','React 웹 화면 + Python HTTP API + SQLite  |  직접 조립과 실제 AI 호출 경로를 분리')
box(34,124,145,72,'사용자 브라우저','React / Vite 화면')
box(231,124,267,72,'ApiHandler','Python http.server / JSON / 세션 쿠키')
box(550,124,196,72,'SQLite','계정·지침·팀·인수인계')
arrow(179,160,231,160);arrow(498,160,550,160)
box(34,246,212,95,'지침 조립·답변 확인','coding_instructions<br/>coding_answer_review<br/>모델 호출 없이 동작')
box(283,246,214,95,'기존 선택 비교','service / engine / domains<br/>요약·React 경로 유지')
box(534,246,212,95,'선택적 최적화','CodingOptimizationJobs<br/>GEPA / 환경별 정적 검사')
for x in [140,390,640]:
    line(365,196,365,223);line(140,223,640,223);arrow(x,223,x,246)
box(283,398,214,66,'외부 모델 API','실제 모드·명시적 실행 시 호출')
box(534,398,212,66,'응답 캐시 / 작업 상태','파일 캐시 / 작업은 메모리 보관')
arrow(390,341,390,398);line(640,341,640,370);line(640,370,488,370);arrow(488,370,488,398)
arrow(640,341,640,398)
txt('호스팅: hosting_server.py가<br/>화면 빌드와 API를 같은 주소로 제공.<br/>공개 운영·HTTPS는 확인 필요.',35,396,211,11.1,maxh=70)
note('FastAPI는 생성 코드의 대상 환경이다. 이 앱 API 서버를 FastAPI 기반이라고 표기하지 않는다.',485)
c.showPage()

# 11: focused Use Case view; detailed views are in the supplement.
header('[설계] UML - 개인 지침 Use Case','사용 목적별 분리 · 회원 액터 일반화 · 팀 기준·인수인계와 상세 명세는 별첨 UML 2·3·8쪽')
Diagram(c).personal()
c.showPage()

# 12: actual inheritance, dependency and association.
header('[설계] UML - 인증·저장 Class','빈 삼각형: 상속 · 점선: 의존 · 실선 화살표: 연관  |  GEPA 작업 클래스·전체 메서드는 상세 설계문서')
Diagram(c).classes()
c.showPage()

# 13: ERD, core relationships / labels
header('[설계] 데이터베이스 구성 - ERD','관계형 DB 설계도 (UML과 별개)  |  핵심 8개 테이블 / 전체 13개 테이블의 컬럼·DDL은 설계문서')
entity(34,119,210,'sessions','PK token_hash<br/>FK user_id → users.id<br/>expires_at')
entity(285,119,210,'users','PK id / UNIQUE username<br/>password_hash<br/>created_at')
entity(536,119,210,'personal_prompts','PK id / FK owner_id<br/>prompt / revision<br/>provenance_json / coding_profile_json')
line(244,162,285,162);txt('0..*:1',245,143,42,8.3,align=1)
line(495,162,536,162);txt('1:0..*',496,143,40,8.3,align=1)
entity(34,275,210,'teams','PK code / FK created_by (선택)<br/>domain_key / name<br/>created_at')
entity(285,275,210,'team_members','PK (code, member_key)<br/>FK code / FK user_id (선택)<br/>history_json')
entity(536,275,210,'handoffs','PK id / FK owner_id, recipient_id<br/>status / revision / body_json<br/>recipient_from_revision')
line(244,319,285,319);txt('1:0..*',245,301,40,8.3,align=1)
line(390,208,390,275);txt('0..1:0..*',396,235,66,8.5)
line(460,208,460,231);line(460,231,610,231);line(610,231,610,275);txt('owner 1:0..*',485,213,115,8.3)
line(480,208,480,254);line(480,254,690,254);line(690,254,690,275);txt('recipient 0..1:0..*',537,237,165,8.3)
line(317,208,317,230);line(317,230,139,230);line(139,230,139,275);txt('생성 0..1:0..*',45,235,96,8.5)
entity(285,404,210,'handoff_versions','PK (handoff_id, revision)<br/>FK handoff_id / actor_id (선택)<br/>snapshot_json / event')
entity(536,404,210,'handoff_files','PK id / FK handoff_id<br/>name / size / data BLOB<br/>content_type / created_at')
line(566,364,566,383);line(566,383,390,383);line(390,383,390,404)
line(670,364,670,404)
txt('1:0..*',395,386,52,8.6);txt('1:0..*',676,381,52,8.6)
txt('※ 선택 = NULL 허용 FK<br/>actor_id → users 관계선 생략<br/>전체 ERD는 상세 설계문서<br/>JSON 내부 ID는 FK 아님',35,407,215,10.2,MUTED,maxh=85)
c.showPage()

# 14: table definitions summary
header('[설계] 테이블 정의와 저장 규칙','원문 DDL과 전체 컬럼·타입·PK·FK·NULL 선언·기본값을 별도 문서에 수록')
table(['영역 / 테이블','보관하는 자료','중요 규칙'],[
 ['계정<br/>users / sessions','사용자·해시 비밀번호·해시 세션 토큰','계정 삭제 시 세션 CASCADE'],
 ['개인 지침<br/>personal_prompts','지침·선호 설정·출처 스냅샷·revision','원문/새 작업 자동 저장 안 함<br/>재조합은 새 ID로 보관'],
 ['팀 기준<br/>teams / team_members','팀 이름·분류·팀원별 선택 이력','team_members 복합 PK(code,member_key)<br/>명시적으로 합친 선택만 반영'],
 ['인수인계<br/>handoffs / handoff_versions','현재 상태·목적·진행·남은 일·버전 기록','공유 시작 revision 이전 수신자 열람 차단<br/>변경 충돌 시 409'],
 ['첨부<br/>handoff_files','파일 원본 BLOB·크기·MIME','목록 제외 후에도 과거 버전 보존<br/>파일 5MiB / 작업 전체 20MiB'],
 ['업무 작업 공간 / 사용량','workspace_* 4개 / usage','프로젝트·저장 버전·권한·초안 / 하루 한도']],
 widths=[188,254,270],size=11,pad=7)
note('최적화 진행 작업은 DB 테이블이 아니라 프로세스 메모리. 저장한 개선 지침만 personal_prompts에 보관.',485)
c.showPage()

# 15: API
header('[설계] 내부·외부 인터페이스 / API','JSON UTF-8 · 세션 쿠키 · 소유권 / revision 확인  |  명세의 요청·응답·오류는 현행 코드 기준')
table(['경로 (핵심 발췌)','메서드','입력 → 응답'],[
 ['/api/coding-instructions/preview','POST','profile → 200 draft / 모델 호출 없음'],
 ['/api/coding-instructions/review','POST','profile, answer → 200 inspection'],
 ['/api/preferences','GET / POST','목록 200 / title,domainKey,prompt → 저장 201'],
 ['/api/preferences/{id}/update','POST','revision + 지침 필드 → 200 / 충돌 409'],
 ['/api/preferences/{id}/compose-task','POST','팀 snapshot + 항목 선택 → 200 draft'],
 ['/api/handoffs','GET / POST','작업 목록 / 목적·진행·남은 일 → 저장 201'],
 ['/api/handoffs/{id}/share, claim, attach','POST','수신자 지정 / 이어받기 / Base64 첨부'],
 ['/api/coding-instructions/optimizations','GET / POST','실행 가능 범위 200 / 작업 시작 202'],
 ['/api/coding-instructions/optimizations/{id}/save','POST','title, 선택적 직접 판단 → 새 지침 201']],
 widths=[342,78,292],size=10,pad=6)
rect(34,446,712,53,PALE)
txt('외부 연결',45,455,105,11.2,bold=True)
txt('실제 AI 실행 시 서버가 지침·과제를 전송. 단순 조립·답변 확인·첨부는 자동 AI 전송 없음.<br/>호스팅은 준비 단계. 명세는 이번 핵심 변경 범위이며 기존 전체 API의 전수 명세는 별도 확장.',151,455,583,10.3,maxh=37)
c.showPage()

# 16: wireframe + storyboard
header('[설계] 화면 흐름 · 요약 와이어프레임','대표 흐름: 환경 선택 → 선호 결정 → 지침 확인 → 저장·새 작업 재사용')
for i,(title,body) in enumerate([
 ('UI02 개발 환경','언어 선택 버튼<br/>[Python] [TypeScript] …<br/>프레임워크 선택 / 직접 입력<br/><br/>[다음: 선호 고르기]'),
 ('UI03 선호 선택','설명 / 주석 / 구성 / 출력<br/>[예시 A]   [예시 B]<br/>선택 상태 / 판단 보류<br/><br/>[직접 설정] [다음]'),
 ('UI04 지침 확인','선택 요약 + 지침 전문<br/>새 작업 입력 영역<br/>[지침 복사] [작업 함께 복사]<br/><br/>[이름 입력 후 저장]'),
 ('UI05 내 선호 보관함','저장 항목 / 환경 / 출처<br/>지침 본문 / 변경 안내<br/>[새 작업 재사용] [수정]<br/><br/>[지원 분류 팀 비교]')]):
    x=34+i*184
    rect(x,125,160,245,'#FFFFFF','#ADBBC2');rect(x,125,160,36,NAVY)
    txt(title,x+6,135,148,11,'#FFFFFF',True,align=1,maxh=20)
    txt(body,x+10,181,140,10.3,maxh=165)
    if i<3:arrow(x+161,248,x+183,248)
rect(34,390,712,107,PALE)
txt('상태·예외까지 화면 사양에 포함',47,401,685,13,bold=True)
txt('① 처음에는 미선택  ② 보류는 자동 채우지 않음  ③ 환경 변경 시 선택 출처 초기화<br/>'
    '④ 저장·재사용 시 로그인과 버전 확인  ⑤ 직접 설정 지침은 개인용 재사용<br/>'
    '현재 남은 문제: 상단 메뉴 이동 시 초안 소실 / GEPA 진행·완료 작업 재열기 누락',
    47,430,685,11.1,maxh=58)
c.showPage()

# 17-18: actual implementation, four images, captions
def screens(title,items,sub):
    header(title,sub)
    for i,(label,file) in enumerate(items):
        x=34+(i%2)*366;y=112+(i//2)*190
        txt(label,x,y,346,11.5,bold=True,maxh=22);shot(file,x,y+27,346,153)
    note('11/04 격리된 예시 계정의 실제 로컬 화면. 데모·준비 자료를 포함하며 새 AI 효과 실험 화면이 아님.',497)
    c.showPage()
screens('[구현 화면] 선택·지침·보관·새 작업',[
 ('① 코드 예시로 네 가지 선호 선택','02-code-comparison.jpg'),('② 선택 요약과 생성 지침 전문','03-my-prompt.jpg'),
 ('③ 요약·코딩·조합을 함께 보관','12-library-overview.jpg'),('④ 지침과 이번 작업을 함께 복사','04-task-request.jpg')],
 '윤정우 진행 영역  |  단순 프롬프트 생성에서 저장·재사용까지 이어지는 흐름')
screens('[구현 화면] 팀 기준·인수인계·업무 초안',[
 ('① 항목별 개인·팀 기준 조합','11-task-preference-mix.jpg'),('② 작업 목적·진행·남은 일 정리','06-handoff.jpg'),
 ('③ 참고 파일 원본의 열기·다운로드','16-handoff-attachments.jpg'),('④ 반복 업무 템플릿과 요청 점검','13-templates.jpg')],
 '윤정우 진행 영역  |  지원 분류의 조합과 인수인계는 서로 다른 권한·사용 흐름')

# 19: next week acceptance
header('4. 다음 주 계획과 완료 기준','11/06 ~ 11/12  |  담당은 다음 작업 제안 / 사용자 모집 없이 기술적 동작과 독립 과제 중심')
table(['기한·담당','할 일','보고할 산출물·완료 기준'],[
 ['~11/07<br/>윤정우','대표 React 시연 경로 고정','선택 → 지침 → 저장 → 새 작업 재사용<br/>UI02~05 화면·요청·저장값 대응'],
 ['~11/08<br/>공동','설계 검토와 공유본 정리','요구사항 ID·UML·ERD·API·화면 연결<br/>검토 수정사항과 GitHub 공유 경로'],
 ['~11/09<br/>고차원','독립 평가 과제·조건 고정','과제 ID·일반/선호 지침·기능/스타일 판정 기준<br/>최적화 과제와 분리, 미확인 처리 규칙'],
 ['~11/10<br/>윤정우','초안·진행 작업 복귀 보완','상단 이동 전후 입력 유지 또는 경고<br/>GEPA 작업 번호·상태·완료 결과 재열람'],
 ['~11/11<br/>공동','권한·연구 변경·회귀 확인','두 계정의 공유·첨부·revision 시나리오<br/>연구 변경별 적용과 동일 환경 전체 검사'],
 ['~11/12<br/>공동','실행 결과와 주간보고 갱신','실행한 과제별 결과·실패·호출 기록<br/>미실행 비교·미배포는 계획 상태 유지']],
 widths=[103,203,406],size=11.1,pad=7)
note('실제 AI 비교는 범위·호출 상한을 먼저 정함. 만족도·협업 시간 절감은 자동 평가만으로 주장하지 않는다.',488)
c.showPage()

# 20 evidence and document sharing
header('[공유 자료] 설계문서·코드·검증 기록','링크는 확인한 커밋에 고정 (당시 코드·결과 재확인용) / 새 설계문서는 로컬 작성 상태')
links=[
 ('현재 구현 코드·기능 소개','서비스 구현 기준 · commit a2f1292',f'https://github.com/a77315829-byte/preference-prompt-tool/tree/a2f12928717c11555c7376d0efdd27e0b0703b51'),
 ('DB / API 구현 근거','app_db.py / api_server.py',f'https://github.com/a77315829-byte/preference-prompt-tool/blob/a2f12928717c11555c7376d0efdd27e0b0703b51/api_server.py'),
 ('전체 점검과 남은 문제','회귀 수치·초안 손실·작업 복귀',f'https://github.com/a77315829-byte/preference-prompt-tool/blob/a2f12928717c11555c7376d0efdd27e0b0703b51/docs/history/2026-11-04_project_review.md'),
 ('호스팅 준비와 검증 범위','로컬 준비 / 공개 운영은 미확인',f'https://github.com/a77315829-byte/preference-prompt-tool/blob/a2f12928717c11555c7376d0efdd27e0b0703b51/docs/history/2026-11-04_hosting_preparation.md'),
 ('고차원 React 실험·재채점 근거','codex/coding-ai-upgrade · fee9d1c',f'https://github.com/a77315829-byte/preference-prompt-tool/blob/fee9d1c67ae448dfab88cced704463ecaf9e499e/README.md')]
for i,(label,desc,url) in enumerate(links):
    y=115+i*47;txt(label,35,y,355,13,NAVY,True,maxh=23);txt(desc,408,y+2,338,11.1,MUTED,maxh=22)
    c.linkURL(url,(34,H-y-27,746,H-y+2),relative=0);line(35,y+34,745,y+34,'#D9DFE2')
rect(34,365,712,129,PALE)
txt('이번 수업용 설계 산출물',47,377,685,13,bold=True)
txt('docs/weekly_reports/2026-11-05/Revealed_설계문서_2026-11-05.md',47,404,685,10.3,maxh=20)
txt('기능·비기능 요구사항 / WBS / UML 4종 / 전체 ERD·테이블 / 핵심 API / 화면 사양<br/>'
    '새 문서는 로컬 작성 상태이며 원격 업로드 완료로 표기하지 않음.<br/>'
    '수업 검토: 기능 범위·문서 수준·독립 평가 범위·다음 주 우선순위',47,429,685,11,maxh=58)
c.showPage()

# 21 closing
txt('Revealed  |  윤정우 · 고차원',35,453,710,15,'#FFFFFF')
c.showPage();c.save()
assert not OVERFLOW,OVERFLOW
base=PdfReader(TEMPLATE);over=PdfReader(BytesIO(buf.getvalue()));writer=PdfWriter()
for i,p in enumerate(over.pages):
    if i==0:original=base.pages[0];original.merge_page(p);writer.add_page(original)
    elif i==len(over.pages)-1:original=base.pages[4];original.merge_page(p);writer.add_page(original)
    else:writer.add_page(p)
writer.add_metadata({'/Title':'Revealed 주간보고서 - 구현 실적과 설계 산출물','/Author':'윤정우 · 고차원'})
OUT.parent.mkdir(parents=True,exist_ok=True)
with OUT.open('wb') as f:writer.write(f)
print('Report pages:',len(writer.pages))

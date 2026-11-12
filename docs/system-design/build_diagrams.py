"""Editable report diagrams. No API, database, or external image service."""
from pathlib import Path
import math
import shutil
import subprocess
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, white

HERE = Path(__file__).resolve().parent
OUT = HERE / 'diagrams'
OUT.mkdir(exist_ok=True)
pdfmetrics.registerFont(TTFont('Malgun', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBold', 'C:/Windows/Fonts/malgunbd.ttf'))
W, H = 820, 610
INK, LINE, PALE, TEAL = map(HexColor, ['#20314c', '#8392a7', '#eef1fb', '#dff2ed'])
c = None


def text(x, y, value, size=15, bold=False, center=False):
    c.setFillColor(INK)
    c.setFont('MalgunBold' if bold else 'Malgun', size)
    for i, line in enumerate(value.split('\n')):
        if center:
            c.drawCentredString(x, H-y-i*(size+7), line)
        else:
            c.drawString(x, H-y-i*(size+7), line)


def line(a, b, arrow=False, dashed=False, triangle=False):
    c.setStrokeColor(LINE); c.setLineWidth(1.4)
    c.setDash(5, 4) if dashed else c.setDash()
    c.line(a[0], H-a[1], b[0], H-b[1]); c.setDash()
    if arrow or triangle:
        angle = math.atan2(b[1]-a[1], b[0]-a[0]); length=12
        p1=(b[0]-length*math.cos(angle-.42),b[1]-length*math.sin(angle-.42))
        p2=(b[0]-length*math.cos(angle+.42),b[1]-length*math.sin(angle+.42))
        if triangle:
            p=c.beginPath();p.moveTo(b[0],H-b[1]);p.lineTo(p1[0],H-p1[1]);p.lineTo(p2[0],H-p2[1]);p.close()
            c.setFillColor(white);c.drawPath(p,fill=1)
        else:
            c.line(b[0],H-b[1],p1[0],H-p1[1]);c.line(b[0],H-b[1],p2[0],H-p2[1])


def box(x,y,w,h,title,body='',color=PALE):
    c.setStrokeColor(LINE);c.setFillColor(color)
    c.roundRect(x,H-y-h,w,h,9,stroke=1,fill=1)
    text(x+w/2,y+27,title,16,True,True)
    if body: text(x+w/2,y+54,body,13,False,True)


def actor(x,y,label):
    c.setStrokeColor(INK);c.setLineWidth(1.7)
    c.circle(x,H-y,10,stroke=1,fill=0)
    line((x,y+10),(x,y+43));line((x-19,y+25),(x+19,y+25))
    line((x,y+43),(x-17,y+65));line((x,y+43),(x+17,y+65))
    text(x,y+88,label,14,False,True)


def class_box(x,y,w,h,title,body='',color=PALE):
    c.setStrokeColor(LINE);c.setFillColor(color)
    c.rect(x,H-y-h,w,h,stroke=1,fill=1)
    text(x+w/2,y+27,title,16,True,True)
    if body:
        line((x,y+38),(x+w,y+38))
        parts=body.split('\n')
        text(x+w/2,y+59,parts[0],13,False,True)
        if len(parts)>1:
            line((x,y+68),(x+w,y+68))
            text(x+w/2,y+89,parts[1],13,False,True)


def ellipse(x,y,w,h,label):
    c.setStrokeColor(LINE);c.setFillColor(PALE)
    c.ellipse(x,H-y-h,x+w,H-y,stroke=1,fill=1)
    text(x+w/2,y+h/2+5,label,15,False,True)


def begin(slug,title,subtitle):
    global c
    c=canvas.Canvas(str(OUT/f'{slug}.pdf'),pagesize=(W,H))
    c.setTitle(title);text(28,34,title,22,True);text(28,60,subtitle,12)
    return slug


def end(slug):
    text(28,590,'Revealed | 2026-11-12 | 현재 구현의 핵심 관계만 표시',11)
    c.save()
    poppler=shutil.which('pdftoppm')
    if not poppler: raise RuntimeError('Bundled pdftoppm is required')
    subprocess.run([poppler,'-r','150','-png','-singlefile',str(OUT/f'{slug}.pdf'),str(OUT/slug)],check=True)


def usecases():
    s=begin('01-usecases','전체 유즈케이스','액터의 참여 관계와 로그인 사전조건을 구분한다.')
    c.setStrokeColor(LINE);c.rect(153,H-90-454,505,454,stroke=1,fill=0)
    text(405,116,'Revealed 서비스',16,True,True)
    actor(63,158,'방문자');actor(63,424,'회원');actor(750,222,'외부 모델\n서비스')
    line((63,412),(63,263),triangle=True)
    text(75,343,'일반화',11)
    for y,label in [(137,'UC-S 요약 조건 확인'),(204,'UC-C AI 답변 방식 설정'),(271,'UC-R React 스타일 비교')]:
        ellipse(205,y,255,47,label);line((85,191),(205,y+23))
    for y,label in [(353,'UC-P 지침 보관·재사용'),(416,'UC-T 팀 기준·조합'),(479,'UC-H 작업 인수인계')]:
        ellipse(205,y,255,47,label);line((85,457),(205,y+23))
    ellipse(478,353,160,55,'UC-G 선택적 개선')
    for a,b in zip([(85,457),(130,457),(130,561),(674,561),(674,380)],[(130,457),(130,561),(674,561),(674,380),(638,380)]):line(a,b)
    line((730,255),(638,380))
    line((730,255),(460,294));line((730,255),(460,160))
    text(617,197,'실제 후보 생성',11,False,True)
    text(545,450,'저장·공유·개선은\n로그인과 권한 필요\n복사 후 외부 AI 사용은\n서비스 밖의 사용자 작업',12,False,True)
    end(s)


def architecture():
    s=begin('02-architecture','논리 아키텍처','모델 없는 조립과 실제 AI 생성·개선 경로를 구분한다.')
    box(230,90,360,65,'React / Vite','시작 · 비교 · 보관함 · 팀 · 인수인계')
    line((410,155),(410,194),arrow=True);text(430,179,'JSON / 세션 쿠키',12)
    box(230,194,360,65,'ApiHandler / http.server','hosting_server: API + 정적 빌드 제공')
    for x,title,body in [(25,'조건 조립·확인','summary_contracts\ncoding_instructions'),(220,'비교 서비스','service / engine\ndomains / checks'),(415,'개선 작업','CodingOptimizationJobs\nGEPA / 환경별 평가'),(610,'인증·저장소','Auth / Prompt / Team\nHandoff / Workspace')]:
        box(x,320,180,112,title,body);line((410,259),(x+90,320),arrow=True)
    box(25,490,180,60,'모델 호출 없음','검증된 조건 → 지침',TEAL)
    box(277,490,206,60,'외부 모델 API','실제 생성·개선 시 호출',TEAL)
    box(584,490,206,60,'SQLite / 파일 캐시','계정·버전·결과·응답',TEAL)
    line((115,432),(115,490),arrow=True);line((310,432),(335,490),arrow=True)
    line((505,432),(435,490),arrow=True);line((505,432),(640,490),arrow=True)
    line((700,432),(700,490),arrow=True)
    end(s)


def classes():
    s=begin('03-classes','클래스와 사용 의존','실제 클래스만 표시. 점선은 사용 의존, 빈 삼각형은 상속이다.')
    class_box(290,87,240,62,'BaseHTTPRequestHandler')
    class_box(290,190,240,78,'ApiHandler','do_GET() / do_POST()')
    line((410,190),(410,149),triangle=True)
    class_box(18,335,240,100,'AuthService','db: Database\nuser_for() / login()')
    class_box(290,335,240,100,'PersonalPromptStore','_db: DB 조회 callable\ncreate() / update() / get()')
    class_box(562,335,240,100,'HandoffStore','_db: DB 조회 callable\ncreate() / change() / history()')
    for x in (138,410,682):line((410,268),(x,335),arrow=True,dashed=True)
    text(425,298,'API 모듈 전역 객체 사용',12)
    class_box(290,484,240,72,'Database','connect() / migrate()',TEAL)
    line((138,435),(290,510),arrow=True);text(172,474,'db 참조',11)
    line((410,435),(410,484),arrow=True,dashed=True)
    line((682,435),(530,510),arrow=True,dashed=True);text(610,475,'조회 후 사용',11)
    end(s)


def sequence():
    s=begin('04-summary-sequence','요약 조건 확인 시퀀스','명시한 충돌을 해결하기 전에는 새 작업용 지침을 반환하지 않는다.')
    xs=[90,280,495,715]
    for x,title in zip(xs,['사용자','요약 조건 화면','ApiHandler','summary_contracts']):
        box(x-80,95,160,48,title);line((x,143),(x,550),dashed=True)
    events=[(0,1,173,'원문·보존 문장·조건 선택'),(1,2,213,'POST /api/summary-contract'),(2,3,253,'입력·원문·문장 수 확인'),(3,2,293,'needs_resolution'),(2,1,333,'충돌 정보 / prompts={}'),(0,1,380,'해결 방식 선택'),(1,2,420,'같은 요청 + resolution'),(2,3,460,'검증 후 적용 조건 조립'),(3,2,500,'ready / 지침·작업용 요청'),(2,1,540,'원래 조건·적용 조건·지침')]
    for a,b,y,label in events:
        line((xs[a],y),(xs[b],y),arrow=True,dashed=a>b)
        text((xs[a]+xs[b])/2,y-10,label,12,False,True)
    text(407,565,'반환 예시 두 요청을 시간 순서로 표현 · 외부 모델/보관함 호출 없음',12,False,True)
    end(s)


def state():
    s=begin('05-handoff-state','작업 인수인계 상태','변경마다 접근·역할·revision·버전 상한을 먼저 검사한다.')
    text(410,108,'수신 계정 삭제 시: 작성자의 편집·재공유 허용, shared로 복귀',12,False,True)
    c.setFillColor(INK);c.circle(70,H-186,8,fill=1,stroke=0)
    box(130,150,220,85,'draft','작성자의 개인 기록')
    box(470,150,220,85,'shared','지정 수신자에게 공유')
    box(470,374,220,85,'active','수신자가 이어서 맡음')
    box(130,374,220,85,'done','완료 기록')
    line((78,186),(130,186),arrow=True);text(99,169,'저장',11,False,True)
    line((350,192),(470,192),arrow=True);text(410,174,'계정 지정',12,False,True)
    line((580,235),(580,374),arrow=True);text(595,302,'수신자 claim',12)
    line((470,415),(350,415),arrow=True);text(409,398,'완료',12,False,True)
    line((240,459),(240,504));line((240,504),(580,504));line((580,504),(580,459),arrow=True)
    text(410,531,'서버가 허용하는 재진행: done → active',12,False,True)
    text(60,305,'shared에서 수신자 재지정 가능\n이전 수신자의 접근은 유지하지 않음\n링크만으로 열람 권한이 생기지 않음',13)
    end(s)


def data():
    s=begin('06-data','핵심 데이터 관계','논리 관계 일부만 표시. 실제 외래키·전체 16개 테이블은 근거 JSON 참조.')
    box(300,90,220,82,'users','id PK / username')
    box(25,238,220,90,'personal_prompts','owner_id FK\nprompt / revision / profile')
    box(300,238,220,90,'teams','created_by FK nullable\ncode PK / protected')
    box(575,238,220,90,'handoffs','owner_id / recipient_id FK\nstatus / revision')
    for x,label in [(135,'소유'),(410,'생성'),(685,'작성·수신')]:
        line((410,172),(x,238),arrow=True);text((410+x)/2,204,label,12,False,True)
    box(55,418,220,90,'team_members','code + member_key PK\nuser_id FK nullable',TEAL)
    box(300,418,220,90,'coding_team_guides','code PK / FK → teams\nrevision / profile_json',TEAL)
    box(575,418,220,90,'versions / files','handoff_versions\nhandoff_files',TEAL)
    line((410,328),(165,418),arrow=True);line((410,328),(410,418),arrow=True)
    line((685,328),(685,418),arrow=True)
    text(410,553,'화살표: 부모 행에서 관련 행으로 탐색하는 방향 · UML 클래스 소유 관계와 구분',12,False,True)
    end(s)


def navigation():
    s=begin('07-navigation','화면 구성과 주요 이동','완료·미정·오류·데모 여부를 실제 화면 상태와 함께 표시한다.')
    box(290,88,240,62,'시작하기')
    for x,title in [(25,'문서 요약'),(300,'코딩 도움'),(575,'팀 업무 정리')]:
        box(x,216,220,68,title);line((410,150),(x+110,216),arrow=True)
    box(25,354,220,96,'조건 확인·결과','비교 → 보존 문장 선택\n충돌 해결 → 지침',TEAL)
    box(300,330,220,65,'AI 답변 방식 설정','환경 + 4항목',TEAL)
    box(300,424,220,65,'React 스타일 비교','파일·스타일 값·타입',TEAL)
    box(575,354,220,96,'인수인계','작성 → 저장 → 계정 지정\n이어받기 → 완료',TEAL)
    line((135,284),(135,354),arrow=True);line((410,284),(410,330),arrow=True)
    line((520,252),(548,252));line((548,252),(548,456));line((548,456),(520,456),arrow=True)
    line((685,284),(685,354),arrow=True)
    text(410,541,'공통 메뉴: 내 선호 보관함 · 템플릿 · 팀 기준 맞추기',16,True,True)
    end(s)


if __name__=='__main__':
    for draw in [usecases,architecture,classes,sequence,state,data,navigation]:draw()
    print('Rendered 7 diagrams as PDF and PNG.')

"""Code-grounded UML views for the report and its detailed supplement.

Only document files are produced. No application module is imported.
"""
from pathlib import Path
from math import atan2, cos, sin
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor, white

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'output/pdf/Revealed_UML_상세설계_2026-11-05.pdf'
W, H = 780, 540
INK, NAVY, GRAY = '#17202D', '#082452', '#65747D'
for name, file in [('MG','malgun.ttf'),('MGB','malgunbd.ttf')]:
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name, 'C:/Windows/Fonts/'+file))
pdfmetrics.registerFontFamily('MG', normal='MG', bold='MGB')


class Diagram:
    def __init__(self, c):
        self.c = c

    def text(self, s, x, y, w, size=10, bold=False, align=0, maxh=None, color=INK):
        p = Paragraph(s, ParagraphStyle('uml', fontName='MGB' if bold else 'MG',
            fontSize=size, leading=size*1.4, wordWrap='CJK', alignment=align,
            textColor=HexColor(color)))
        _, h = p.wrap(w, 1000)
        if maxh is not None:
            assert h <= maxh+.5, (self.c.getPageNumber(), s[:50], h, maxh)
        p.drawOn(self.c, x, H-y-h)
        return h

    def rect(self, x, y, w, h, fill='#FFFFFF', radius=0):
        self.c.setFillColor(HexColor(fill)); self.c.setStrokeColor(HexColor(GRAY)); self.c.setLineWidth(.8)
        if radius:
            self.c.roundRect(x,H-y-h,w,h,radius,stroke=1,fill=1)
        else:
            self.c.rect(x,H-y-h,w,h,stroke=1,fill=1)

    def line(self, points, dash=False, head=None):
        c=self.c; c.setStrokeColor(HexColor(GRAY));c.setLineWidth(.9)
        c.setDash(4,3) if dash else c.setDash()
        for (x,y),(xx,yy) in zip(points,points[1:]):c.line(x,H-y,xx,H-yy)
        c.setDash()
        if head:
            (x,y),(xx,yy)=points[-2:]; a=atan2(yy-y,xx-x); length=10 if head=='general' else 7
            left=(xx-length*cos(a-.43), yy-length*sin(a-.43))
            right=(xx-length*cos(a+.43), yy-length*sin(a+.43))
            p=c.beginPath();p.moveTo(left[0],H-left[1]);p.lineTo(xx,H-yy);p.lineTo(right[0],H-right[1])
            if head in ('general','filled'):p.close()
            c.setFillColor(white if head=='general' else HexColor(GRAY))
            c.drawPath(p,stroke=1,fill=head in ('general','filled'))

    def actor(self,x,y,label):
        self.c.setStrokeColor(HexColor(INK));self.c.circle(x,H-y,7,stroke=1,fill=0)
        self.line([(x,y+7),(x,y+33)]);self.line([(x-14,y+17),(x+14,y+17)])
        self.line([(x-12,y+49),(x,y+33),(x+12,y+49)])
        self.text(label,x-70,y+55,140,10,align=1,maxh=30)

    def oval(self,x,y,w,h,label):
        self.c.setFillColor(white);self.c.setStrokeColor(HexColor(GRAY));self.c.ellipse(x,H-y-h,x+w,H-y,stroke=1,fill=1)
        self.text(label,x+14,y+(h-14)/2,w-28,10,align=1,maxh=16)

    def klass(self,x,y,w,name,attrs,ops):
        titleh=25; attrh=18*len(attrs)+8 if attrs else 0; oph=18*len(ops)+8 if ops else 0
        self.rect(x,y,w,titleh+attrh+oph)
        self.text(name,x+5,y+5,w-10,10.5,True,1,maxh=18)
        if attrs:
            self.line([(x,y+titleh),(x+w,y+titleh)])
            for i,t in enumerate(attrs):self.text(t,x+7,y+titleh+4+i*18,w-14,8.9,maxh=17)
        if ops:
            self.line([(x,y+titleh+attrh),(x+w,y+titleh+attrh)])
            for i,t in enumerate(ops):self.text(t,x+7,y+titleh+attrh+4+i*18,w-14,9,maxh=17)

    def personal(self):
        self.rect(260,115,310,359,'#F8FAFB')
        self.text('Revealed 웹 서비스 — 개인 지침',273,122,280,11,True)
        self.actor(93,163,'사용자');self.actor(93,348,'회원 사용자')
        self.line([(93,340),(93,239)],head='general')
        labels=['UC01 코딩 지침 만들기','UC02 지침 복사하기','UC03 받은 답변 확인하기',
                'UC04 지침 저장하기','UC05 저장 지침 재사용하기','UC06 GEPA 개선 실행하기']
        ys=[150,201,252,310,361,412]
        for i,(label,y) in enumerate(zip(labels,ys)):
            self.oval(286,y,258,36,label)
            self.line([(107,180 if i<3 else 365),(286,y+18)])
        self.rect(617,407,129,48)
        self.text('«actor»<br/>외부 모델 서비스',622,412,119,9.5,align=1,maxh=36)
        self.line([(544,430),(617,430)])
        self.text('회원은 사용자 기능을 상속한다. UC04~06은 로그인 필요. UC06은 지원 환경·실행 가능 조건을 확인한다.',35,482,710,9.6,maxh=29)

    def team(self):
        self.rect(255,115,340,359,'#F8FAFB')
        self.text('Revealed 웹 서비스 — 팀 기준',270,122,310,11,True)
        self.actor(93,163,'사용자');self.actor(93,348,'회원 사용자')
        self.line([(93,340),(93,239)],head='general')
        labels=['UC07 팀 만들기','UC08 초대로 팀 참여하기','UC09 개인·팀 기준 비교하기',
                'UC10 작업용 지침 조합하기','UC11 저장한 조합 다시 고르기','UC12 선택한 항목 되돌리기']
        for i,(label,y) in enumerate(zip(labels,[150,201,252,310,361,412])):
            self.oval(278,y,294,36,label);self.line([(107,180 if i<2 else 365),(278,y+18)])
        self.text('사전조건',624,139,121,11,True)
        self.text('UC08<br/>선택 완료·명시적 합치기<br/><br/>UC09~10<br/>동일한 지원 분류<br/>팀 접근·기준 확인<br/><br/>UC11~12<br/>출처가 남은 저장본<br/>소유자·버전 확인',624,165,121,10,maxh=265)
        self.text('UC10~12는 원본을 유지한다. 저장을 선택하면 별도 항목으로 보관한다. 새 직접 설정 지침의 팀 조합은 제외한다.',35,482,710,9.6,maxh=29)

    def handoff(self):
        self.rect(240,113,300,364,'#F8FAFB')
        self.text('Revealed 웹 서비스 — 인수인계',252,120,278,11,True)
        self.actor(80,230,'작업 작성자');self.actor(697,230,'지정 수신자')
        labels=['UC13 인수인계 작성하기','UC14 받는 계정 지정하기','UC15 첨부 파일 관리하기',
                'UC16 작업 열람하기','UC17 작업 이어서 맡기','UC18 작업 내용 수정하기',
                'UC19 작업 완료하기','UC20 작업 다시 진행하기','UC21 변경 기록 열람하기']
        for i,label in enumerate(labels):
            y=147+i*36;self.oval(259,y,262,29,label)
            if i in (0,1,2,3,5,8):self.line([(94,247),(259,y+14.5)])
            if i in (2,3,4,5,6,7,8):self.line([(683,247),(521,y+14.5)])
        self.text('공유·편집은 상태·수신자 유무에 따른 권한을 확인한다. 두 액터는 로그인 계정의 작업별 역할이며 상세 조건은 명세를 따른다.',35,483,710,9.6,maxh=29)

    def classes(self):
        self.klass(274,111,232,'BaseHTTPRequestHandler',[],[])
        self.klass(274,178,232,'ApiHandler',[],['+ do_GET()','+ do_POST()'])
        self.line([(390,178),(390,136)],head='general')
        self.klass(34,290,204,'AuthService',['db : Database'],['+ login(username, password, ...)','+ user_for(token) : User | None'])
        self.klass(288,290,204,'PersonalPromptStore',['_db : Database | Callable'],['+ create(owner_id, body, ...) : dict','+ update(owner_id, id, body) : dict'])
        self.klass(542,290,204,'HandoffStore',['_db : Database | Callable'],['+ create(user_id, raw)','+ change(user_id, id, action, raw)'])
        for start,end in [((294,247),(136,290)),((390,247),(390,290)),((486,247),(644,290))]:self.line([start,end],dash=True,head='open')
        self.text('인증',161,263,62,8.5);self.text('저장',397,263,62,8.5);self.text('인수인계',566,263,70,8.5)
        self.klass(288,403,204,'Database',['path : Path'],['+ connect()'])
        self.line([(136,385),(136,454),(288,454)],head='open')
        self.text('0..*',139,394,38,8.5);self.text('1',270,435,14,8.5);self.text('db 직접 참조',170,433,92,8.5)
        self.line([(390,385),(390,403)],dash=True,head='open')
        self.line([(644,385),(644,454),(492,454)],dash=True,head='open')
        self.text('resolver를 통한 사용',523,431,126,8.5)
        self.text('현재 API 연결 기준: AuthService.db는 DB 직접 참조. 두 Store의 _db에는 lambda: DB를 보관하고 db 속성에서 조회한다.<br/>생성자는 Database도 허용하지만 현재 resolver 경로를 의존으로 표시했다. 세 객체가 모두 DB를 직접 보관한다는 뜻은 아니다.',35,486,710,8.6,maxh=27)

    def lifelines(self, items, bottom=482):
        for x,name in items:
            self.rect(x-56,114,112,35)
            self.text(name.replace('store : ','store :<br/>'),x-52,118,104,8.6,align=1,maxh=27)
            self.line([(x,149),(x,bottom)],dash=True)

    def msg(self,x1,x2,y,label,reply=False,size=8.9,offset=18):
        self.line([(x1,y),(x2,y)],dash=reply,head='open' if reply else 'filled')
        self.text(label,min(x1,x2)+6,y-offset,abs(x2-x1)-12,size,maxh=17)

    def self_msg(self,x,y,label,width=176):
        self.line([(x,y),(x+23,y),(x+23,y+12),(x,y+12)],head='filled')
        self.text(label,x+29,y-6,width,8,maxh=15)

    def frame(self,x,y,w,h,label,guard):
        self.rect(x,y,w,h,fill='#FFFFFF')
        self.text(label,x+6,y+3,40,9,True)
        self.line([(x+37,y),(x+37,y+19),(x,y+19)])
        self.text(guard,x+45,y+3,w-53,9,True,maxh=15)

    def sequence_save(self):
        # Nested fragments preserve actual validation order: fields -> begin/count -> cap.
        self.frame(35,197,710,291,'alt','[세션 없음 또는 만료]')
        self.line([(35,232),(745,232)],dash=True)
        self.frame(48,286,684,199,'alt','[필드 오류 또는 설정·지침 불일치]')
        self.line([(48,329),(732,329)],dash=True)
        self.frame(60,379,660,103,'alt','[저장 개수 >= 100]')
        self.line([(60,424),(720,424)],dash=True)
        self.lifelines([(95,'ui : React'),(285,'api : ApiHandler'),(485,'store : PersonalPromptStore'),(685,'conn : SQLite')])
        def m(a,b,y,s,reply=False):self.msg(a,b,y,s,reply,7.9,11)
        m(95,285,165,'POST /api/preferences')
        self.self_msg(285,179,'_current_user() → AUTH.user_for(token)',410)
        m(285,95,225,'401 · 로그인 필요',True)
        self.text('[세션 유효]',82,235,340,8.5,True)
        m(285,485,258,'create(user.id, body)')
        self.self_msg(485,269,'create 내부: 필드·지침 검사',210)
        m(485,285,312,'ValueError',True);m(285,95,324,'400 · 입력·지침 오류',True)
        self.text('[필드·지침 검사 통과]',95,332,350,8.5,True)
        m(485,685,354,'BEGIN IMMEDIATE; SELECT COUNT(*)')
        m(685,485,372,'현재 소유자의 저장 개수',True)
        m(485,685,397,'ROLLBACK · connect 예외 종료')
        m(485,285,405,'ValueError · 보관 상한',True)
        m(285,95,419,'400 · 보관 상한',True)
        self.text('[저장 개수 < 100]',104,427,350,8,True)
        m(485,685,448,'INSERT 후 SELECT')
        m(485,685,461,'COMMIT · connect 정상 종료')
        m(485,285,472,'새 preference',True);m(285,95,480,'201 · 저장 완료',True)
        self.text('검증은 모두 create 내부. 상한 검사만 트랜잭션 안의 개수 조회 뒤 수행한다. COMMIT/ROLLBACK은 Database.connect가 수행.<br/>SQL·검증 단계는 요약 표기이며 별도 새 메서드를 뜻하지 않는다. 외부 모델 호출 없음.',35,490,710,8.5,maxh=26)

    def sequence_handoff(self):
        self.frame(35,268,710,217,'alt','[revision 불일치]')
        self.line([(35,342),(745,342)],dash=True)
        self.text('[revision 일치 · 저장 버전 < 200 · can_claim 참]',82,348,650,9,True)
        self.lifelines([(95,'ui : React'),(285,'api : ApiHandler'),(485,'store : HandoffStore'),(685,'conn : SQLite')])
        self.msg(95,285,179,'1: POST /{id}/claim')
        self.msg(285,485,214,'2: change(user, id, claim, raw)')
        self.msg(485,685,247,'3: BEGIN IMMEDIATE · 조회')
        self.msg(485,685,297,'ROLLBACK · connect 예외 종료',size=8.1,offset=12)
        self.msg(485,285,309,'HandoffConflict',True,size=8.1,offset=12)
        self.msg(285,95,329,'409 · 다시 확인 안내',True)
        self.msg(485,685,380,'UPDATE active · revision + 1',offset=12)
        self.msg(485,685,402,'INSERT handoff_versions',offset=12)
        self.msg(485,685,424,'COMMIT · connect 정상 종료',size=8.1,offset=12)
        self.msg(485,285,448,'handoff',True,offset=12)
        self.msg(285,95,476,'200 · 새 상태 표시',True)
        self.text('UC17: 유효한 세션 전제. 404 접근 불가 / 403 역할·상태 / 400 revision 형식 오류 또는 저장 버전 상한(>= 200).<br/>commit·rollback은 Database.connect 종료 처리. 현재 내용 재조회 등 SQL 일부는 생략했다.',35,489,710,8.6,maxh=27)

    def state(self):
        c=self.c;c.setFillColor(HexColor(INK));c.circle(62,H-165,6,fill=1,stroke=0)
        for x,y,name,desc in [(160,139,'draft','작성자 개인 기록'),(470,139,'shared','지정 수신자 대기'),
                               (470,325,'active','인수 후 진행 중'),(160,325,'done','완료 · 상한 미만 재개')]:
            self.rect(x,y,149,62,radius=10);self.text(name,x+7,y+8,135,12,True,1)
            self.text(desc,x+7,y+34,135,9,align=1)
        self.line([(68,165),(160,165)],head='filled');self.text('create / rev=1',66,143,96,8.5)
        self.line([(309,167),(470,167)],head='filled');self.text('share [can_share]',319,127,143,9,align=1)
        self.text('/ 수신자·공유 버전 기록',313,177,151,8.3,align=1)
        self.line([(544,201),(544,325)],head='filled');self.text('claim [can_claim]',556,250,175,9)
        self.line([(504,325),(504,201)],head='filled')
        self.text('share [can_share]',337,232,157,9,align=2)
        self.text('현재 수신 계정이 없는 경우',337,250,157,8.1,align=2)
        self.text('예: 수신자 계정 삭제',337,265,157,8.1,align=2)
        self.line([(470,350),(309,350)],head='filled');self.text('complete [can_complete]',307,328,164,8.7,align=1)
        self.line([(309,374),(470,374)],head='filled');self.text('reopen [can_reopen]',314,389,151,8.7,align=1)
        self.line([(619,167),(700,167),(700,208),(593,208),(593,201)],head='filled')
        self.text('share [can_share]',627,132,123,8.3)
        self.text('/ 수신자 변경 시<br/>공개 시작 버전 갱신',625,216,122,8.1,maxh=25)
        self.text('상태 안의 내부 전이',35,435,210,10.5,True)
        self.text('draft·shared: update / attach / detach [can_edit]<br/>active: update / attach / detach [can_edit]  ·  done: 편집 불가',35,456,420,9.5,maxh=34)
        self.text('모든 변경: revision 확인 후 성공 시 증가·이력 저장.<br/>revision >= 200이면 complete 외 변경 거절.<br/>complete도 역할·상태 조건을 충족해야 한다.<br/>done은 UML 최종 상태가 아니다.',480,435,266,8.6,maxh=57)

    def spec(self):
        self.text('UC04 지침 저장하기',35,117,710,14,True)
        self.text('회원 사용자가 생성한 지침을 이름과 함께 저장한다. 성공하면 개인 보관함에 새 ID가 생긴다.',35,146,710,11,maxh=32)
        self.text('사전조건  유효한 세션, 완성한 지침과 선택 설정.<br/>기본 흐름  인증 → create 내부 필드·지침 검사 → 트랜잭션 안 개수·상한 확인 → 저장·commit → 201.<br/>대안·실패  세션 무효 401, 설정·본문 불일치 또는 보관 상한 400. 실패 시 새 항목을 만들지 않는다.<br/>사후조건  소유자·지침·환경 설정·revision=1 기록. 새 작업 원문은 자동 저장하지 않는다.',35,186,710,11,maxh=116)
        self.text('UC17 작업 이어서 맡기',35,317,710,14,True)
        self.text('지정 수신자가 shared 상태의 작업을 맡아 active 상태로 바꾼다.',35,346,710,11,maxh=32)
        self.text('사전조건  로그인, 현재 지정 수신자, shared, 최신 revision, 현재 저장 버전 < 200.<br/>기본 흐름  접근·revision·상한·can_claim 확인 → active와 이력 저장 → connect 종료 시 commit → 200.<br/>대안·실패  401 인증 / 404 접근 / 403 역할·상태 / 409 버전 충돌 / 400 버전 형식 오류·상한.<br/>사후조건  수신자 편집 가능. 상태와 이력이 같은 트랜잭션으로 확정된다.',35,385,710,10.5,maxh=90)
        self.text('표기 기준: OMG UML 2.5.1 (9·11·14·17·18장)  https://www.omg.org/spec/UML/2.5.1<br/>구현 근거: api_server.py · auth.py · personal_prompts.py · handoffs.py · app_db.py (a2f1292)',35,481,710,8.8,maxh=29,color=GRAY)


VIEWS = [
 ('personal','UML 유즈케이스 — 개인 지침','현재 구현의 핵심 경로 · 로그인은 회원 전제 · 선은 실행 순서가 아닌 참여 관계'),
 ('team','UML 유즈케이스 — 팀 기준과 조합','지원 분류·저장 출처 조건을 명세에 연결 · 팀 참여와 인수인계 수신 권한은 별개'),
 ('handoff','UML 유즈케이스 — 인수인계','역할은 작업마다 달라짐 · 한 계정이 다른 작업에서는 작성자 또는 수신자가 될 수 있음'),
 ('classes','UML 클래스 — 인증과 저장','실선 빈 삼각형: 상속 · 점선 열린 화살표: 의존 · 실선 열린 화살표: 탐색 가능한 연관'),
 ('sequence_save','UML 시퀀스 — 개인 지침 저장','동기 호출·점선 반환 · alt 조건 분기 · 모델 호출 없는 저장 경로 · 활성 구간은 생략'),
 ('sequence_handoff','UML 시퀀스 — 작업 이어받기','유효한 로그인 전제 · 버전 충돌과 성공 흐름 · 호출명은 읽기 쉽게 축약'),
 ('state','UML 상태 머신 — 인수인계','전이 표기: 사건 [조건] / 처리 · 일반 상태와 최종 상태 구분 · 실제 권한 조건 사용'),
 ('spec','유즈케이스 상세 명세','그림만으로 끝내지 않고 사전조건·기본 흐름·실패·사후조건을 함께 정의'),
]


def build():
    OUT.parent.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(OUT),pagesize=(W,H)); d=Diagram(c)
    c.setTitle('Revealed UML 상세설계'); c.setAuthor('윤정우 · 고차원')
    for i,(method,title,subtitle) in enumerate(VIEWS,1):
        d.text(title,34,25,712,21,True,maxh=32)
        d.line([(34,65),(746,65)])
        d.text(subtitle,35,77,710,10,color=GRAY,maxh=29)
        getattr(d,method)()
        d.text('Revealed | AI/SW융합프로젝트 | 구현 근거 11/04 · 설계 보완 11/06',34,519,680,8,color=GRAY)
        d.text(str(i),718,516,28,10,align=2)
        c.showPage()
    c.save(); print(OUT)


if __name__=='__main__':
    build()

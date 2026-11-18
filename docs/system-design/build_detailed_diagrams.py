"""Fourteen detailed architecture figures; source-derived, no live app/data/API."""
from pathlib import Path
import json
import build_diagrams as d
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.colors import HexColor, white

HERE = Path(__file__).resolve().parent
MINT = HexColor('#e1f2ed')
LILAC = HexColor('#edeafb')
AMBER = HexColor('#fff1d8')
GRAY = HexColor('#f2f5f8')


def route(points, dashed=False, arrow=True):
    for i in range(len(points)-1):
        d.line(points[i], points[i+1], arrow=arrow and i == len(points)-2, dashed=dashed)


def label(x, y, value, width=190, size=13, bold=False, center=True):
    font = 'MalgunBold' if bold else 'Malgun'
    while max(pdfmetrics.stringWidth(s, font, size) for s in value.split('\n')) > width and size > 10:
        size -= .5
    d.text(x, y, value, size, bold, center)


def node(x, y, w, h, title, body='', fill=LILAC, size=15):
    d.c.setStrokeColor(d.LINE); d.c.setFillColor(fill)
    d.c.roundRect(x, d.H-y-h, w, h, 8, stroke=1, fill=1)
    lines = title.split('\n')
    baseline = y+23 if len(lines) > 1 or body else y+h/2+5
    label(x+w/2, baseline, title, w-20, size, True)
    if body:
        label(x+w/2, y+49, body, w-20, 13)


def diamond(cx, cy, w, h, title):
    path=d.c.beginPath();path.moveTo(cx,d.H-cy-h/2)
    path.lineTo(cx+w/2,d.H-cy);path.lineTo(cx,d.H-cy+h/2)
    path.lineTo(cx-w/2,d.H-cy);path.close()
    d.c.setStrokeColor(d.LINE);d.c.setFillColor(AMBER);d.c.drawPath(path,fill=1)
    label(cx,cy+5,title,w-35,13,True)


def dot(x,y,final=False):
    d.c.setFillColor(d.INK);d.c.circle(x,d.H-y,5,fill=1,stroke=0)
    if final:
        d.c.setStrokeColor(d.INK);d.c.circle(x,d.H-y,9,fill=0,stroke=1)


def sequence(slug,title,subtitle,heads,events,foot):
    s=d.begin(slug,title,subtitle)
    xs=([90,290,495,715] if len(heads)==4 else [110,410,710])
    width=160 if len(heads)==4 else 210
    for x,head in zip(xs,heads):
        node(x-width/2,90,width,55,head,fill=GRAY,size=14)
        d.line((x,145),(x,544),dashed=True)
    for a,b,y,caption in events:
        d.line((xs[a],y),(xs[b],y),arrow=True,dashed=a>b)
        label((xs[a]+xs[b])/2,y-10,caption,abs(xs[a]-xs[b])-12,12)
    label(410,564,foot,760,12)
    d.end(s)


def coding_sequence():
    sequence('08-coding-sequence','코딩 네 항목 지침 조립 시퀀스','직접 설정 경로 · 모델 생성과 기존 선호 추정기를 호출하지 않는다.',
        ['사용자','코딩 화면','ApiHandler','지침 조립 함수'],[
            (0,1,180,'환경·네 항목 선택'),
            (1,2,225,'POST preview / profile'),
            (2,3,270,'build_coding_instructions'),
            (3,2,315,'검증한 profile + prompt'),
            (2,1,360,'200 / draft'),
            (1,0,405,'선택 요약·지침 전문'),
            (0,1,450,'새 작업과 복사 / 명시 저장'),
            (1,2,505,'저장은 별도 preferences API'),
        ],'잘못된 값·비교 출처는 400 · 미선택을 숨은 선호로 확정하지 않음')


def save_sequence():
    sequence('09-save-sequence','개인 지침 수정과 revision 시퀀스','인증 계정으로 조회하고 트랜잭션 안에서 현재 버전을 대조한다.',
        ['보관함 화면','ApiHandler','PersonalPromptStore','SQLite'],[
            (0,1,180,'POST update / revision'),
            (1,2,220,'인증된 user.id + 입력'),
            (2,3,260,'BEGIN IMMEDIATE / 현재 행'),
            (3,2,300,'현재 본문·revision'),
            (2,3,340,'일치 시 UPDATE + revision'),
            (3,2,380,'commit / 갱신된 행'),
            (2,1,420,'현재 항목 / 충돌이면 예외'),
            (1,0,465,'200 항목 또는 409 오류'),
            (0,1,515,'409면 입력 보존 후 재조회'),
        ],'revision 불일치 분기에서는 UPDATE하지 않음 · 클라이언트 owner_id를 신뢰하지 않음')


def gepa_sequence():
    sequence('10-gepa-sequence','선택적 GEPA 시작·조회·채택','작업 관리자 내부 워커가 생성·평가하고, API가 계정별 결과를 중개한다.',
        ['개선 화면','ApiHandler','작업 관리자·워커'],[
            (0,1,172,'지원 환경·원본 확인 후 시작'),
            (1,2,207,'start / 사용량·동시 실행 확인'),
            (2,1,242,'job 생성 / 워커 별도 실행'),
            (1,0,277,'202 / job ID'),
            (0,1,312,'GET job / 최근 작업 조회'),
            (1,2,347,'소유자·만료 확인 후 get'),
            (2,1,382,'진행 또는 완료·오류·결과'),
            (1,0,417,'원본·후보·변화·별도 평가'),
            (0,1,452,'사용자가 후보 채택 / save'),
            (1,2,487,'서버 보유 changed 결과 저장'),
            (2,1,522,'새 개인 지침 / 기존 항목 유지'),
            (1,0,545,'201 / 새 보관함 항목'),
        ],'워커는 실제 모델 API를 호출할 수 있음 · 중단 복구는 error이며 자동 재호출하지 않음')


def summary_activity():
    s=d.begin('11-summary-activity','요약 조건 확인 활동 흐름','최초 확인 → 사용자 해결 → 재확인 · 완전 발췌 문장 수의 명시적 충돌을 다룬다.')
    dot(410,94);route([(410,100),(410,118)])
    node(270,118,280,58,'입력·원문 문장 대조','길이·중복·현재 원문 일치')
    node(30,122,165,52,'400 입력 오류',fill=AMBER,size=14)
    route([(270,147),(195,147)]);label(235,132,'실패',65,12)
    route([(410,176),(410,216)])
    diamond(410,251,230,70,'완전 발췌·수량 충돌?')
    node(53,330,230,58,'원래 조건 유지',fill=MINT)
    node(537,324,230,68,'needs_resolution','지침·작업용 요청 비움',fill=AMBER)
    route([(295,251),(168,251),(168,330)]);label(220,237,'아니오',80,12)
    route([(525,251),(652,251),(652,324)]);label(591,237,'예',65,12)
    node(537,417,230,68,'사용자가 해결 선택','선택한 조건만 변경·재확인')
    route([(652,392),(652,417)])
    node(270,510,280,48,'ready · 지침 + 작업용 요청',fill=MINT,size=14)
    route([(168,388),(168,534),(270,534)])
    route([(652,485),(652,534),(550,534)])
    label(410,474,'상한: expand / rephrase / keep_limits\n하한: shorten(가능 시) / rephrase',330,12)
    d.end(s)


def coding_activity():
    s=d.begin('12-coding-activity','코딩 네 항목 선택·확정 흐름','직접 설정이 기본이며 준비 예시 비교는 이해를 돕는 선택 경로다.')
    node(285,94,250,48,'언어·프레임워크 선택')
    route([(410,142),(410,169)]);diamond(410,201,200,64,'예시로 고를까?')
    node(45,263,240,58,'네 항목 직접 선택',fill=MINT)
    node(535,253,240,78,'준비 예시 A/B 선택','최대 8회 · 1회 후 종료 가능')
    route([(310,201),(165,201),(165,263)]);label(220,187,'아니오',70,12)
    route([(510,201),(655,201),(655,253)]);label(590,187,'예',60,12)
    node(535,357,240,66,'선택 신호 구분','한 번·반복·엇갈림·미응답')
    route([(655,331),(655,357)])
    diamond(410,457,230,68,'네 항목 모두 확인?')
    route([(165,321),(165,350),(410,350),(410,423)])
    route([(655,423),(655,457),(525,457)])
    node(40,508,245,48,'미정 항목 직접 확인',fill=AMBER,size=14)
    route([(295,457),(162,457),(162,508)]);label(223,484,'아니오',70,12)
    route([(40,532),(20,532),(20,375),(410,375),(410,423)])
    node(385,515,355,50,'검증한 선택으로 지침 조립·미리 보기',fill=MINT,size=14)
    route([(410,491),(410,515)]);label(430,507,'예',40,11)
    d.end(s)


def team_activity():
    s=d.begin('13-team-activity','개인·팀 기준 조합 활동 흐름','기존 도메인 집계와 새 코딩 명시 기준의 입력 의미를 구분한다.')
    node(250,92,320,52,'로그인 · 개인 지침·팀 기준 읽기')
    route([(410,144),(410,166)])
    diamond(410,200,250,68,'접근권한·같은 분류/환경?')
    node(38,174,165,54,'거절·다시 선택',fill=AMBER,size=14)
    route([(285,200),(203,200)]);label(242,185,'아니오',70,12)
    node(250,269,320,54,'다른 항목마다 개인/팀 선택')
    route([(410,234),(410,269)]);label(432,256,'예',40,12)
    node(250,354,320,59,'본문·출처·snapshot 미리 보기','원래 지침과 당시 값을 유지')
    route([(410,323),(410,354)])
    diamond(410,470,240,66,'저장 직전 버전·선택 동일?')
    route([(410,413),(410,437)])
    node(590,440,200,64,'409 · 다시 확인','입력 보존 후 재조회',fill=AMBER,size=14)
    route([(530,470),(590,470)]);label(560,451,'아니오',65,11)
    route([(690,440),(690,118),(570,118)])
    node(230,535,360,41,'새 작업용 항목 저장 · 원본 유지',fill=MINT,size=14)
    route([(410,503),(410,535)]);label(432,524,'예',40,12)
    d.end(s)


def deployment():
    s=d.begin('14-deployment','배포 구성과 저장 경계','현재 설정 파일의 구성도 · 실제 클라우드 배포·가용성 확인 결과가 아니다.')
    node(270,95,280,55,'사용자 브라우저','React 정적 화면·동일 출처 API')
    node(270,198,280,55,'관리형 HTTPS 프록시','공개 TLS · Host 보존',fill=GRAY)
    route([(410,150),(410,198)]);label(444,178,'HTTPS',90,12)
    d.c.setStrokeColor(d.LINE);d.c.setDash(5,4);d.c.rect(45,d.H-292-190,535,190,fill=0,stroke=1);d.c.setDash()
    label(64,316,'단일 앱 인스턴스 / Docker',400,15,True,False)
    node(77,340,215,65,'hosting_server.py','HostedHandler → ApiHandler',size=14)
    node(332,340,215,65,'frontend/dist','빌드된 HTML·JS·CSS',fill=GRAY,size=14)
    route([(410,253),(410,279),(60,279),(60,331),(184,331),(184,340)])
    route([(292,372),(332,372)]);label(311,356,'정적',65,11)
    label(310,449,'도메인·저장·인증·GEPA 업무 모듈\n환경설정과 서버 키는 공개 정적 경로 밖',470,13)
    node(620,334,175,81,'외부 모델 API','명시적 실제 생성\n또는 GEPA만',fill=AMBER,size=14)
    route([(580,380),(620,380)],dashed=True)
    node(77,510,470,57,'영구 디스크 /var/data','SQLite(첨부 포함) + 응답 캐시 · 비공개',fill=MINT,size=15)
    route([(185,405),(185,510)])
    label(682,516,'로컬 개발은 별도\nVite 5173 → API 8000\n자동 배포는 꺼진 설정',210,12)
    d.end(s)


def wire_shell(slug,title,subtitle):
    s=d.begin(slug,title,subtitle)
    node(28,84,764,47,'Revealed   |   시작하기   보관함   템플릿   팀 기준   계정',fill=GRAY,size=15)
    return s


def summary_wireframe():
    s=wire_shell('15-summary-wireframe','요약 조건 확인 — 논리 와이어프레임','UI-04 · 실제 화면 캡처/픽셀 배치가 아닌 입력·상태·행동 명세다.')
    node(28,153,350,184,'이번 원문','원문 입력 · 초과 입력은 거절\n보존할 완전 문장 최대 8개\n□ 원문 문장 1   □ 원문 문장 2\n선택 순서는 원문 순서로 정규화',fill=white)
    node(401,153,391,184,'요약 조건','분량: 짧게 / 보통 / 길게\n원문 표현: normal / high / fully\n초점(선택)\n[현재 조건 확인]',fill=white)
    node(28,360,764,87,'충돌·해결 영역','needs_resolution: 새 지침 복사 보류\n[분량 확대]  [재서술 허용]  [일부 생략 허용]  → 다시 확인',fill=AMBER)
    node(28,468,764,95,'확인된 결과','원래 조건 / 적용 조건 / 주의사항 / 실제 지침 전문\n[재사용 지침만 복사]  [원문·남길 문장과 함께 복사]',fill=MINT)
    d.end(s)


def coding_wireframe():
    s=wire_shell('16-coding-wireframe','코딩 네 항목 — 논리 와이어프레임','UI-05~07 · 단계의 논리 배치이며 한 화면에 모두 보이는 실제 캡처가 아니다.')
    node(28,151,764,58,'환경 선택 → 선호 선택 → 확인·프롬프트 완성',fill=MINT,size=15)
    node(28,231,240,94,'1. 개발 환경','언어 선택 / 직접 입력\n프레임워크 선택',fill=white)
    node(290,231,502,94,'2. 고르는 방법','[설정만 빠르게 고르기]  [코드 예시로 고르기]\n예시는 선택 항목 · 취소하면 기존 설정 복원',fill=white)
    for x,title,body in [(28,'설명','간결하게 / 단계별'),(223,'주석','필요한 곳 / 상세'),(418,'구성','간결하게 / 역할별'),(613,'출력','전체 / 변경 중심')]:
        node(x,347,179,83,title,body,fill=LILAC,size=14)
    node(28,452,764,110,'3. 확인·결과','미정·엇갈림 직접 확인 → 네 항목 선택 완료\n선택 요약과 실제 지침 전문 · 복사 / 명시 저장 / 별도 개선\n[React 코드 스타일 비교: 다른 세 축 기능]',fill=white)
    d.end(s)


def library_wireframe():
    s=wire_shell('17-library-wireframe','내 선호 보관함 — 논리 와이어프레임','UI-09~11 · 개인 지침·새 작업·조합 출처를 분리한다. 실제 캡처가 아니다.')
    node(28,153,235,369,'내 지침 목록','검색 / 분류\n\n지침 A · revision\n지침 B · revision\n새 작업용 · 출처\n\n빈 목록은 생성 안내',fill=white)
    node(286,153,506,124,'선택 지침 · 사용 / 편집','제목 · 분류 · 메모 · 현재 버전\n실제 지침 전문 · 설정/본문 일치 여부\n저장 / 삭제 / 복사',fill=white)
    node(286,298,506,95,'새 작업에 사용','이번 작업 입력 · 개인/팀/작업용 기준\n복사 또는 실제 실행 · 결과는 원본과 별도',fill=MINT)
    node(286,414,506,108,'출처·재조합·변경 비교','당시 개인/팀 값 · 부모 항목 ID와 버전\n새 조합 / 일부 되돌림 → 다른 이름의 새 항목\n삭제된 부모는 이름으로 추정해 연결하지 않음',fill=white)
    node(28,542,764,31,'409: 수정 입력을 보존한 뒤 최신 항목을 다시 확인',fill=AMBER,size=13)
    d.end(s)


def handoff_wireframe():
    s=wire_shell('18-handoff-wireframe','작업 인수인계 — 논리 와이어프레임','UI-13~14 · 현재 역할·상태·revision이 행동을 결정한다. 실제 캡처가 아니다.')
    node(28,151,764,48,'[새 작업 작성]  [받은 링크 열기]   ·   상태 / 담당자 / revision',fill=MINT,size=14)
    node(28,222,368,170,'작업 본문','제목\n목적 / 진행 상황 / 남은 일\n\n[개인 기록 저장]',fill=white)
    node(418,222,374,170,'자료와 사용 지침','참고 경로·링크 / 사용한 지침\n첨부 목록 / 열기 / 다운로드\n파일 5MiB · 현재 10개\n[저장한 작업에 첨부]',fill=white)
    node(28,414,764,74,'공유·이어받기','[수신 계정 지정] → shared → [이어서 맡기] → active → [완료] → done',fill=LILAC,size=15)
    node(28,509,764,57,'변경 이력·과거 첨부','수신자는 공유 시점 이후 · 파일을 열 때도 현재 접근권한 재검사',fill=white,size=14)
    d.end(s)


def entity(x,y,w,h,name,fields,fill=white):
    d.c.setStrokeColor(d.LINE);d.c.setFillColor(fill);d.c.rect(x,d.H-y-h,w,h,fill=1,stroke=1)
    label(x+w/2,y+23,name,w-12,14,True)
    d.line((x,y+34),(x+w,y+34))
    label(x+10,y+56,fields,w-18,12,False,False)


def identity_data():
    s=d.begin('19-identity-data','계정·팀·개인 지침 데이터 관계','실선 화살표: 자식 FK → 부모 · 점선: 문자열/JSON 논리 연결, SQL FK 아님')
    entity(300,88,220,101,'users','PK id\nusername · password_hash',MINT)
    entity(28,244,225,105,'sessions','PK token_hash\nFK user_id · expires_at')
    entity(298,244,225,105,'teams','PK code · protected\nFK created_by (NULL 허용)')
    entity(568,244,225,105,'personal_prompts','PK id · FK owner_id\nrevision · profile/provenance JSON')
    entity(28,426,225,121,'team_members','PK (code, member_key)\nFK code · FK user_id (NULL)\nhistory_json')
    entity(298,426,225,105,'coding_team_guides','PK/FK code\nrevision · profile/rules JSON')
    entity(568,426,225,105,'usage','PK (day, kind, subject)\ncount · SQL FK 없음',GRAY)
    route([(140,244),(140,210),(345,210),(345,189)])
    route([(410,244),(410,189)])
    route([(680,244),(680,210),(475,210),(475,189)])
    route([(410,426),(410,349)]);label(446,389,'같은 code',100,11)
    route([(253,477),(275,477),(275,325),(298,325)]);label(275,396,'code',50,11)
    route([(28,462),(12,462),(12,136),(300,136)]);label(115,123,'user_id',120,11)
    route([(793,466),(808,466),(808,130),(520,130)],dashed=True)
    label(680,405,'subject는 계정/익명 문자열',230,11)
    label(410,570,'JSON 출처는 당시 스냅샷 · 원본 삭제와 함께 FK로 연쇄 삭제되는 관계가 아님',760,12)
    d.end(s)


def work_data():
    s=d.begin('20-work-data','인수인계·개선·작업 기록 데이터 관계','실선: 자식 FK → 부모 · 점선: 버전 JSON의 첨부 메타데이터 → 파일 ID')
    entity(300,89,220,82,'users','PK id',MINT)
    entity(20,247,230,106,'coding_optimization_jobs','PK id · FK owner_id\nexpires_at · job_json')
    entity(295,230,230,139,'handoffs','PK id\nFK owner_id / recipient_id\nstatus · revision\nrecipient_from_revision')
    entity(570,247,230,106,'coding_work_trials','PK id · FK owner_id\nrevision · record_json')
    entity(73,446,292,105,'handoff_versions','PK (handoff_id, revision)\nFK handoff_id · FK actor_id\nsnapshot_json')
    entity(478,446,292,105,'handoff_files','PK id · FK handoff_id\nname · size · data (BLOB)')
    route([(135,247),(135,207),(345,207),(345,171)])
    route([(410,230),(410,171)])
    route([(685,247),(685,207),(475,207),(475,171)])
    route([(218,446),(218,405),(350,405),(350,369)])
    route([(624,446),(624,405),(470,405),(470,369)])
    route([(73,489),(8,489),(8,129),(300,129)]);label(120,116,'actor_id (NULL 허용)',210,11)
    route([(365,507),(478,507)],dashed=True);label(422,491,'첨부 ID',90,11)
    label(410,572,'계정/작업 삭제 정책은 데이터 사전 참조 · 버전 FK는 현재 열람 권한을 대신하지 않음',770,12)
    d.end(s)


def workspace_data():
    s=d.begin('21-workspace-data','업무 지침 프로젝트 데이터 관계','실선: 자식 FK → 부모 · 저장 버전과 사용자별 초안은 서로 다른 테이블')
    entity(300,92,220,82,'users','PK id',MINT)
    entity(300,235,220,106,'workspace_projects','PK id · FK owner_id\ntitle · updated_at')
    entity(18,435,245,117,'workspace_versions','PK (project_id, version)\nFK project_id\nproject_json · label')
    entity(287,435,245,117,'workspace_members','PK (project_id, user_id)\nFK project_id · FK user_id\nrole: viewer / editor')
    entity(556,435,245,117,'workspace_drafts','PK (project_id, user_id)\nFK project_id · FK user_id\nbase_version · project_json')
    route([(410,235),(410,174)])
    for start,target in [((140,435),(345,341)),((410,435),(410,341)),((680,435),(475,341))]:
        route([start,(start[0],385),(target[0],385),target])
    route([(287,486),(275,486),(275,132),(300,132)])
    route([(801,486),(812,486),(812,132),(520,132)])
    label(183,213,'공유 대상 계정 FK',175,11)
    label(675,213,'초안 작성 계정 FK',175,11)
    label(410,573,'base_version은 작업 사본의 기준 번호이며 workspace_versions로 향하는 SQL FK는 없음',770,12)
    d.end(s)


def validate_table_coverage():
    schema=json.loads((HERE/'source-evidence.json').read_text(encoding='utf-8'))
    drawn={'users','sessions','usage','teams','team_members','coding_team_guides','personal_prompts',
           'handoffs','handoff_versions','handoff_files','coding_optimization_jobs','coding_work_trials',
           'workspace_projects','workspace_versions','workspace_members','workspace_drafts'}
    assert drawn == set(schema['tables']), 'Diagram table coverage differs from source schema.'


if __name__ == '__main__':
    validate_table_coverage()
    drawings=[coding_sequence,save_sequence,gepa_sequence,summary_activity,coding_activity,team_activity,
              deployment,summary_wireframe,coding_wireframe,library_wireframe,handoff_wireframe,
              identity_data,work_data,workspace_data]
    for draw in drawings:
        draw()
    print('Rendered 14 detailed diagrams as PDF + PNG; all 16 tables covered.')

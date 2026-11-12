"""Render all numbered use-case levels and their report-style specifications."""
from pathlib import Path
from xml.sax.saxutils import escape
import json
import math
import shutil
import subprocess
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

HERE=Path(__file__).resolve().parent
D=json.loads((HERE/'usecase-catalog.json').read_text(encoding='utf-8'))
CASES={u['id']:u for u in D['usecases']}
OUT=HERE/'diagrams'
pdfmetrics.registerFont(TTFont('UCM','C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('UCMB','C:/Windows/Fonts/malgunbd.ttf'))
INK='#20314c'; LINE='#8b9aaf'; PALE='#eef2fb'; MINT='#e2f2ec'
INPUT_NOTES=[
 '입력은 사용자명·비밀번호이며 로그인 세션은 쿠키로 전달된다. 비밀번호 원문을 저장하지 않는다. 비밀번호 변경·계정 삭제는 현재 비밀번호를 다시 확인한다. 비교 세션 ID 경로의 별도 권한 경계는 6장·8장을 따른다.',
 '입력은 요약 언어·분류와 현재 원문이다. 실제 후보 생성은 모델 설정·키·한도·캐시가 필요하다. 생성 실패의 데모 전환은 demo_reason=generation_failed로 구별하며 요청 자체 오류와 혼동하지 않는다.',
 '입력은 세션·현재 쌍 ID·응답이다. 이력에는 A/B 조합과 실제 선택값·순서를 남긴다. 되돌리면 남은 이력으로 효용을 다시 계산한다. 최적화 진행 등 허용하지 않는 상태의 변경은 거절한다.',
 '입력은 현재 원문과 후보에 포함된 선택 문장 목록이다. 임의 문자열을 문장 후보처럼 추가할 수 없다. 문장 경계 규칙의 결과를 완벽한 의미 판별로 표현하지 않으며 클릭 순서를 보존 우선순위로 바꾸지 않는다.',
 '입력은 domainKey·profile·sourceText·requiredSentences·resolution이다. 현행 v2는 허용 해결값·원래/적용 조건·분량 경계를 함께 반환한다. 원문 문장이 0개면 축소를 제공하지 않는다. 실제 의미 보존·분량 충족은 새 출력에서 별도 확인한다.',
 '입력은 language·framework와 explanation/comments/structure/output의 네 값이다. 선택 요약과 실제 지침 전문을 따로 보여 준다. 직접 입력 환경의 조립 지원과 준비 예시·실행 평가 지원은 다르다.',
 '입력은 예시 ID·개발 환경·연속 응답 이력이다. 완료 전에는 기존 직접 설정을 덮어쓰지 않는다. 예시 비교의 신호 분류는 기존 비교 엔진의 통계적 신호와 별도이며 과거 기록은 원래 버전 규칙으로 읽는다.',
 '입력은 TypeScript/React 개발 요청과 비교 응답이다. 파일 구성·스타일 관리·타입 작성 세 축의 지침과 이력을 반환한다. 실제 후보 코드의 실행 품질과 스타일 적합성은 따로 확인한다. 기존 새 과제 실험과 언어 차이의 한계는 9장에 기록한다.',
 '입력은 제목·분류·본문·선택 메모/설정이다. 생성 시 revision 1, 수정 시 새 revision을 남긴다. 직접 편집한 본문을 과거 설정과 항상 동일하다고 표시하지 않는다. 보관 개수는 계정당 100개다.',
 '복사는 지침과 새 입력의 결합이다. 선택적 /api/preferences/{id}/run은 LIVE·키·quota를 확인하는 별도 모델 실행이며 실패 시 502 등을 반환한다. 이 동작만으로 입력·답변이나 보관함 원본을 자동 저장하지 않는다.',
 '입력은 팀 이름·종류·기준과 초대 정보다. 닫힌 초대 재개는 같은 링크를 다시 여는 동작이다. 계정 팀은 생성자 삭제 뒤에도 비공개를 유지한다. 30일 미참여 자동 정리는 익명 체험 팀에만 적용한다.',
 '입력은 지원 도메인의 개인 비교 이력과 대상 팀이다. 집계는 이력의 효용을 합쳐 팀 지침을 계산하는 방식이며 조직의 공식 승인이나 강제 규칙이 아니다. 개인 비교만으로 자동 합산하지 않는다.',
 '입력은 팀 개발 환경·네 기본값·필수 규칙·revision이다. coding_profile 계정 팀만 이 경로로 관리한다. 개인 추가 메모와 예시 이력은 팀 기본값에 노출하지 않는다.',
 '입력은 양쪽 기준 ID·버전과 항목별 선택이다. 미리 보기 이후 기준이나 선택이 바뀌면 재조합한다. 저장은 새 개인 항목이며 값·이름·출처·기준 버전을 당시 스냅샷으로 남긴다.',
 '입력은 저장 항목·당시 출처와 되돌릴 항목이다. 새 항목에 직전 ID와 변경 비교를 연결한다. 과거 값이 없는 기록은 추측으로 복원하지 않으며 삭제된 원본과 저장 당시 스냅샷을 구별한다.',
 '입력은 제목·목적·진행·남은 일·자료·사용 지침이다. 지침 연결은 현재 본문 사본이며 원본을 수정하지 않는다. 계정별 임시 초안과 서버 저장 draft를 구분하고 저장 전 파일은 복구된 첨부로 표시하지 않는다.',
 '전이는 작성자의 draft→shared, shared에서 재지정, 수신자의 shared→active→done 및 done→active다. 수신 계정이 삭제되어 recipient_id가 NULL이면 작성자가 복구·재공유할 수 있고 shared로 돌아간다. 버전 열람에는 현재 권한과 공유 시작 revision을 함께 적용한다.',
 '입력은 작업 ID·revision·파일명·바이트다. 파일 원본은 BLOB, 추가·제외는 새 버전으로 남긴다. 현재 제외한 파일도 과거 보존 용량에 포함되며 열기는 요청 버전의 파일 목록과 현재 계정 권한을 모두 확인한다.',
 '입력은 profile·originalPrompt이며 작업 ID로 상태를 조회한다. 모델 개선은 실제 API 비용이 가능하다. 지원 환경·실행 도구가 준비되지 않으면 유료 시작 전에 차단한다. 보관 기록은 계정별 7일 범위다.',
 '입력은 완료 작업·채택 여부·선택적 직접 판단이다. 직접 판단을 자동 점수나 후보 선정에 소급 적용하지 않는다. 과거 v1 점수를 v2로 재계산하여 같은 실험처럼 보고하지 않는다. 채택은 새 개인 항목 저장이다.',
 '입력은 개발 환경·지침 프로필·답변 텍스트다. 주석·선언·파일 등 형식 단서와 직접 확인 질문을 반환한다. 브라우저에서 서버로 전송되지만 모델 호출·외부 AI 전달·코드 실행·자동 저장은 하지 않는다.',
 '입력은 지침·대상 형식·선택적 기존 파일 내용이다. 표시 구역 밖의 보존과 변경 차이를 확인한다. 기존 내용이 있는 Cursor 파일은 전체 자동 병합을 거절하고 새 파일 내려받기·수동 적용을 사용한다.',
 '입력은 고정 과제·도구·모델·맥락·지침 버전과 측정값이다. setup은 준비·요청·응답 대기, edit는 답변 수정·검사를 포함한다. 별도의 세 번째 검사 타이머는 없고 최초 선호 선택 비용도 포함하지 않는다. 실제 기록이 없으면 사람의 효과를 보고하지 않는다.',
 '입력은 템플릿별 요구 또는 작업 공간의 계약·시험 입력·제안이다. 비교 템플릿 6개와 업무 초안 18개의 역할이 다르다. 구조화·시험·제안의 모델 경로에는 비용·한도가 적용된다. 확인된 상태·지침·버전은 실제 업무 성과의 증명이 아니다.',
]

def paragraph(c,s,x,y,w,size=15,bold=False,center=False):
    p=Paragraph(escape(s).replace('\n','<br/>'),ParagraphStyle('p',fontName='UCMB' if bold else 'UCM',fontSize=size,leading=size*1.45,textColor=HexColor(INK),alignment=1 if center else 0,wordWrap='CJK'))
    _,h=p.wrap(w,1000);p.drawOn(c,x,y-h);return h

def edge(c,x1,y1,x2,y2,arrow=False):
    c.setStrokeColor(HexColor(LINE));c.setLineWidth(1.2);c.line(x1,y1,x2,y2)
    if arrow:
        a=math.atan2(y2-y1,x2-x1)
        for b in [-.4,.4]:c.line(x2,y2,x2-10*math.cos(a+b),y2-10*math.sin(a+b))

def actor(c,x,y,name,side_label=False):
    c.setStrokeColor(HexColor(INK));c.circle(x,y+26,8,stroke=1,fill=0)
    edge(c,x,y+18,x,y-12);edge(c,x-17,y+6,x+17,y+6)
    edge(c,x,y-12,x-14,y-30);edge(c,x,y-12,x+14,y-30)
    if side_label:paragraph(c,name,x-165,y+13,130,12,center=True)
    else:paragraph(c,name,x-77,y-38,154,12,center=True)

def oval(c,x,y,w,h,ident,name):
    c.setStrokeColor(HexColor(LINE));c.setFillColor(HexColor(PALE));c.ellipse(x,y,x+w,y+h,stroke=1,fill=1)
    paragraph(c,ident,x+18,y+h-11,w-36,12,True,True)
    paragraph(c,name,x+18,y+h-32,w-36,15,True,True)

def start(slug,title,sub,w=900,h=580):
    c=canvas.Canvas(str(OUT/(slug+'.pdf')),pagesize=(w,h));c.setTitle(title)
    paragraph(c,title,25,h-17,w-50,23,True);paragraph(c,sub,25,h-58,w-50,12)
    return c,w,h

def end(c,slug,w,h):
    paragraph(c,'Revealed | v1.1 | 2026-11-13 | 数字 ID는 문서 추적용이며 UML의 강제 번호 규칙이 아님'.replace('数字','숫자'),25,25,w-50,10)
    c.save()
    poppler=shutil.which('pdftoppm')
    if not poppler:raise RuntimeError('Bundled pdftoppm is required')
    subprocess.run([poppler,'-r','140','-png','-singlefile',str(OUT/(slug+'.pdf')),str(OUT/slug)],check=True,capture_output=True)

def overview():
    slug='01-usecases';c,w,h=start(slug,'전체 유즈케이스 색인','8개 기능 영역 → UC-01~UC-24 → UC-번호-하위번호. 참여 관계는 영역별·개별 그림에서 확인한다.',900,780)
    for i,g in enumerate(D['groups']):
        x=25+(i%2)*440;y=520-(i//2)*158
        c.setStrokeColor(HexColor(LINE));c.setFillColor(HexColor(PALE));c.roundRect(x,y,425,148,8,stroke=1,fill=1)
        paragraph(c,g['name'],x+15,y+136,395,17,True)
        for j,ident in enumerate(g['ids']):paragraph(c,ident+'  '+CASES[ident]['name'],x+15,y+106-j*20,395,11)
    end(c,slug,w,h)

def domain(i,g):
    slug=f'uc-domain-{i:02d}';c,w,h=start(slug,g['name']+' 유즈케이스', '실선은 해당 역할의 참여. 단계 순서·로그인 조건을 include/extend로 표시하지 않는다.',900,570)
    c.setStrokeColor(HexColor(LINE));c.rect(270,67,595,405,stroke=1,fill=0)
    paragraph(c,'Revealed / '+g['name'],285,460,550,14,True)
    names={'계정 관리':'방문자·회원','문서 요약':'사용자','코딩 도움·React 비교':'사용자','개인 지침·재사용':'회원·지침 사용자','팀 기준·조합':'팀장·팀원','작업 인수인계':'작성자·지정 수신자','개선·답변 검토':'회원·답변 사용자','템플릿·업무 작업 공간':'사용자·작업 공간 멤버'}
    actor(c,115,290,names[g['name']])
    n=len(g['ids']);gap=min(77,330/max(n,1))
    for j,ident in enumerate(g['ids']):
        y=365-j*gap if n>1 else 258
        edge(c,135,290,310,y+29);oval(c,310,y,510,60,ident,CASES[ident]['name'])
    paragraph(c,'구체적인 권한은 각 UC의 하위 기능과 사전조건을 따른다.\n영역 묶음 자체가 별도의 UC 또는 공통 실행 순서를 뜻하지 않는다.',35,96,210,11)
    end(c,slug,w,h)

def detail(u):
    slug=u['id'].lower()+'-detail';c,w,h=start(slug,u['id']+'  '+u['name'],'하위 목표별 참여 관계. 이 그림의 연결선은 시간 순서나 필수 호출 관계를 뜻하지 않는다.',900,525)
    c.setStrokeColor(HexColor(LINE));c.rect(290,61,575,365,stroke=1,fill=0)
    paragraph(c,'Revealed / '+u['group'],310,414,530,14,True)
    for i,ch in enumerate(u['children']):
        y=339-i*79
        actor(c,190,y+20,ch['actor'],side_label=True);edge(c,210,y+20,340,y+28)
        oval(c,340,y,475,61,ch['id'],ch['name'])
    end(c,slug,w,h)

def activity(u):
    slug=u['id'].lower()+'-flow';c,w,h=start(slug,u['id']+'  기본 처리 흐름','기본 흐름 번호는 명세와 대응한다. 오른쪽은 이 흐름의 대안·예외 설명이며 추가 기능이 아니다.',900,580)
    c.setFillColor(HexColor(INK));c.circle(260,469,6,stroke=0,fill=1);edge(c,260,463,260,440,True)
    for i,s in enumerate(u['flow']):
        y=368-i*86
        c.setFillColor(HexColor(PALE));c.setStrokeColor(HexColor(LINE));c.roundRect(35,y,450,72,8,stroke=1,fill=1)
        paragraph(c,f'{i+1}. '+s,49,y+61,422,14)
        if i<3:edge(c,260,y,260,y-14,True)
    edge(c,260,110,260,88,True);c.setFillColor(HexColor(INK));c.circle(260,78,5,stroke=0,fill=1);c.circle(260,78,9,stroke=1,fill=0)
    for y,title,body,fill in [(450,'대안 흐름',u['alternate'],MINT),(310,'예외·오류',u['error'],'#fff1dd'),(170,'확인 기준',u['check'],PALE)]:
        paragraph(c,title,535,y,320,16,True);paragraph(c,body,535,y-30,320,14)
    end(c,slug,w,h)

def table(rows):return '\n'.join('| '+' | '.join(row)+' |' for row in [rows[0],['---']*len(rows[0])]+rows[1:])+'\n\n'

def chapter():
    lines=['# 2. 유즈케이스 계층과 상세 명세\n',
      '## 2.1 번호·범위·그림 읽는 법\n',
      '상위 기능은 UC-01~UC-24, 하위 목표는 UC-01-01처럼 숫자만 사용한다. 하위 번호는 부모 안에서 다시 시작하며, UML이 지정한 번호 체계가 아니라 이 프로젝트의 추적 규칙이다. 같은 ID와 이름을 목록·그림·명세·WBS 대응표에서 사용한다. 기존 상위 24개 ID를 유지하므로 과거 요구사항과 검증 기록을 이어서 찾을 수 있다.\n',
      '전체 색인에서 기능 영역을 고르고, 영역별 그림에서 상위 UC를 찾은 뒤, 해당 UC의 하위 그림·명세·기본 흐름을 읽는다. 하위 기능은 79개이며 버튼·검사 함수마다 별도 UC를 추가하지 않았다. 영역·상위 UC로 묶는 것은 문서의 상세화 관계다. UML include는 필수 공통 행동의 포함, extend는 조건부 확장일 때 쓰므로 여기서는 단순 하위 목록에 그 관계를 붙이지 않았다.\n',
      '중간보고서의 기능별 그림과 명세표 구성을 참고하여 개요·액터·사전/사후조건·입력·기본/대안/예외 흐름·검사 기준을 함께 기술한다. 날짜는 문서 수정일, 상태는 현행 구현 기준 검토용이다. 우선순위나 실제 담당자·완료일을 임의 확정하지 않는다. 검사 기준은 앞으로 재확인할 수용 기준이며 새 실행 결과가 아니다.\n',
      '## 2.2 유즈케이스 목록\n']
    def related(u):
        return ', '.join(x['id']+' ('+x['role']+')' for x in u.get('related_wbs',[])) or '-'
    lines.append(table([['ID','유즈케이스 이름','주 구현 WBS','관련 WBS']]+[[u['id'],u['name'],u['wbs'],related(u)] for u in D['usecases']]))
    for i,g in enumerate(D['groups'],1):
        lines.extend([f'## 2.{i+2} {g["name"]} 하위 구성\n',f'![{g["name"]} 참여 관계](../diagrams/uc-domain-{i:02d}.png)\n',
          '이 영역은 '+', '.join(g['ids'])+'로 구성한다. 각 기능의 참여 역할과 처리 결과는 이어지는 개별 명세를 따른다. 공통 UC-03은 요약과 React 비교에서 함께 사용하며 WBS에는 중복 작업으로 합산하지 않는다.\n' if i in (2,3) else '이 영역은 '+', '.join(g['ids'])+'로 구성한다. 그림의 역할 묶음이 모든 하위 동작에 동일 권한을 부여한다는 뜻은 아니다. 개별 명세에서 실제 수행 주체와 권한을 구분한다.\n'])
    lines.extend(['<!-- pagebreak -->\n','## 2.11 WBS와 유즈케이스 연결 원칙\n',
      'PMI는 WBS를 프로젝트 전체 범위를 조직하는 구조로 설명한다. OMG UML의 유즈케이스는 외부 액터와 상호작용하여 가치 있는 결과를 제공하는 시스템 행동을 설명한다. 이 정의에 비추어 두 산출물의 이름이나 개수가 항상 같아야 한다고 해석할 근거는 없다. WBS에는 설계·검증·문서화·운영처럼 사용자 기능 이외의 일도 들어간다. 이는 두 정의를 비교한 본 문서의 적용 판단이며 학교의 별도 양식 규칙을 확인했다는 뜻은 아니다.\n',
      '이 프로젝트에서는 공통 기능명은 일치시키고, 기능 구현 WBS 3.1~3.4에 상위 UC를 연결한다. 주 구현과 공통 사용·보완 예정 관계를 구별한다. 하위 UC는 부모의 연결 범위를 상속하되, 관련 WBS의 보완 대상은 명시한 범위에만 적용한다. 분석 1.2, 설계 2.1~2.3, 회귀 4.2는 전체 UC를 다루는 공통 작업이다. WBS는 기존 5단계·16개 주요 작업을 유지한다.\n',
      table([['WBS','주요 구현 범위','연결 UC']]+[['3.1','문서 요약 기능 구현','UC-02~UC-05'],['3.2','코딩 도움·React 비교 구현','UC-06~UC-08 (공통 UC-03 참조)'],['3.3','계정·지침 저장·재사용 구현','UC-01, UC-09~10, UC-19~24; 세션 정책 보완 대상 UC-02·03'],['3.4','팀 공유·인수인계 구현','UC-11~UC-18']]),
      'UC-02·03의 주 구현은 3.1이다. 3.3은 비교 세션 접근·소유권·만료 정책을 확정하고 구현할 보완 작업이며 현재 계정 격리 완료를 뜻하지 않는다. UC-03은 React 비교의 3.2에서도 공통 사용한다. 요약 v2의 길이 제한·충돌 처리 설명은 반영됐고, 2.1~2.3에는 세션 정책 확정 후 설계·화면·명세 반영이 남아 있다.\n',
      '참고: [PMI WBS Practice Standard 소개](https://www.pmi.org/standards/work-breakdown-structures-third-edition), [OMG UML 2.5.1, 18장 Use Cases](https://www.omg.org/spec/UML/2.5.1). 일정·상태는 보고서형 WBS v3.3과 연결한다.\n'])
    for u in D['usecases']:
        ident=u['id'];actors=' / '.join(dict.fromkeys(ch['actor'] for ch in u['children']))
        lines.extend([f'## {ident} {u["name"]}\n',f'![{ident} 하위 유즈케이스](../diagrams/{ident.lower()}-detail.png)\n',
          table([['명세 항목','내용'],['시스템 / 서브시스템','Revealed / '+u['group']],['UC-ID / 이름',ident+' / '+u['name']],['단계 / 작성일 / 버전','현행 구현 기준 검토용 / 2026-11-13 / v1.2'],['개요',u['goal']],['주요 액터',actors],['사전조건',u['pre']],['사후조건',u['post']],['추적 관계',u['requirements']+' / '+u['screens']+' / 주 구현 WBS '+u['wbs']+(' / 관련 '+related(u) if u.get('related_wbs') else '')]]),
          '### 하위 기능 설명\n',table([['하위 ID','기능 이름','액터·처리 결과']]+[[ch['id'],ch['name'],ch['actor']+' : '+ch['description']] for ch in u['children']]),
          '### 기본·대안·예외 흐름\n',f'![{ident} 기본 처리와 예외 설명](../diagrams/{ident.lower()}-flow.png)\n',
          table([['흐름','설명']]+[[str(i),s] for i,s in enumerate(u['flow'],1)]+[['대안',u['alternate']],['예외',u['error']],['검사 기준',u['check']]]),
          '### 입력·상태·업무 규칙 상세\n',INPUT_NOTES[int(ident.split('-')[1])-1]+'\n'])
    (HERE/'chapters/02-usecases.md').write_text('\n'.join(lines),encoding='utf-8',newline='\n')

def main():
    overview()
    for i,g in enumerate(D['groups'],1):domain(i,g)
    for u in D['usecases']:detail(u);activity(u)
    chapter()
    print('Overview + 8 domain diagrams + 24 child diagrams + 24 activity diagrams; chapter generated.')

if __name__=='__main__':main()

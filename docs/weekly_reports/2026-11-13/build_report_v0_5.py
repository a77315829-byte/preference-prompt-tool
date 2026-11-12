"""Weekly v0.5: completed integration/regression evidence, same course template."""
from pathlib import Path
import hashlib
import json
from pypdf import PdfReader, PdfWriter
import build_report_v0_4 as base

ROOT=base.ROOT
HERE=Path(__file__).resolve().parent
VERSION="0.5"
OUT=ROOT/"output/pdf/Revealed_진행현황_주간보고서_v0.5.pdf"
QA=ROOT/"tmp/weekly_2026_11_13/v0_5"
DATA=json.loads((ROOT/"docs/verification/2026-11-12/results.json").read_text(encoding="utf-8"))
assert DATA["backend"]["failed"]==DATA["frontend"]["failed"]==DATA["integration"]["failed"]==0
BACK=DATA["backend"]["passed"]
FRONT=DATA["frontend"]["passed"]


class ReportPage(base.ReportPage):
    def text(self, value, *args, **kwargs):
        replacements={"최신 전체 재검사 필요":"최신 전체 회귀 통과", "출력 검증·통합 잔여":"출력·두 계정 검증 완료"}
        value=replacements.get(value,value)
        if str(value).startswith("위 H/E 경로는 로컬 저장소 기준."):
            value=("기존 H/E/D 근거는 그대로 보존. 이번 추가 검사 원자료는 docs/verification/2026-11-12/results.json과 results/ 참조.<br/>"
                   "지난주 계획 원본은 v0.3 3쪽. 과거 백업은 현재 13~30쪽이며 최신 통합·회귀 결과는 11~12쪽을 적용.")
        return super().text(value,*args,**kwargs)

    def footer(self, number, backup=False, old_number=None):
        self.rect(0,514,780,26,"#FFFFFF")
        label=(f"과거 백업 | 11/06 v0.3 원문 {old_number}쪽 | 현재 실적·계획·판정은 3~12쪽" if backup
               else "Revealed | AI/SW융합프로젝트 | 2026.11.13 | 10주차 | 실적 확인 11/12까지")
        self.text(label,34,520,620,8,base.MUTED,maxh=13)
        self.text(f"v{VERSION}   {number}",657,518,89,9,base.MUTED,maxh=15,align=2)


# Reuse the verified drawing methods and unchanged scientific-results pages.
base.ReportPage=ReportPage


def cover():
    page=PdfReader(base.TEMPLATE).pages[0]
    p=ReportPage()
    p.text("선호 기반 프롬프트 자동 생성 도구",35,192,463,20,"#FFFFFF",True,maxh=32)
    p.text("팀 Revealed  ·  윤정우 · 고차원",35,228,465,14,"#FFFFFF",maxh=24)
    p.text("2026.11.13 보고  |  10주차  |  v0.5",35,379,710,15,bold=True,maxh=25)
    p.text("금주 11/07 ~ 11/13   |   차주 11/14 ~ 11/20",35,412,710,13,base.MUTED,maxh=22)
    p.text("11/12 추가 검증 반영  ·  두 계정 통합·최신 전체 회귀 완료  ·  본 보고 1~3쪽",35,443,710,10.5,base.MUTED,maxh=18)
    page.merge_page(p.finish());return page


def wbs():
    return base.wbs()


def weekly():
    p=ReportPage();p.header("2. 프로젝트 진행현황","",3)
    for x,label,color in [(34,"금주 실적 (11/07 ~ 11/13)","#808080"),(390,"차주 계획 (11/14 ~ 11/20)",base.GRAY)]:
        p.rect(x,84,356,32,color);p.text(label,x+9,89,338,13,"#FFFFFF",True,maxh=21,align=1)
    for x in [34,335,390,691,746]:p.line(x,116,x,400,"#C7CDD0",.7)
    for x in [34,390,746]:p.line(x,400,x,494,"#C7CDD0",.7)
    left=[
        ("개인 지침·사용 화면","초안·재사용·요약 조건 충돌 처리 보완<br/>권한 회수 뒤 남던 화면 내용 정리 수정","11/09<br/>~11/12"),
        ("팀 공유·업무 연결","두 계정 화면·실제 HTTP 18시나리오 통과<br/>공유·첨부·회수·버전 충돌·원본 보존 확인","11/12"),
        ("설계·검증·운영",f"전체 설계서 97쪽·검증 근거 정리<br/>Python {BACK:,}·프론트 {FRONT}개 통과, 빌드 성공","11/09<br/>~11/12"),
        ("요약·코딩 독립 검증","요약 새 원문 9개·코딩 각 8과제 비교<br/>수동 대비 동률, GEPA 원본 유지","11/10<br/>~11/12"),
    ]
    right=[
        ("입력·지침 경계 보완 (윤정우)","요약 길이 정책·조건 충돌 경로 통일<br/>React 한국어·영어 지침 의미 맞추기","~11/16"),
        ("비교 세션 접근 정책 (공동)","개인 보관함과 다른 세션 접근 범위 정리<br/>민감 원문 처리·소유권 정책과 검사 확정","~11/18"),
        ("변경 지침 재검증 (고차원·공동)","새 원문·과제와 기준을 생성 전 고정<br/>수동과 재비교·유료 API 없이 진행","~11/19"),
        ("최종 시연·문서 정리 (공동)","변경 기능 회귀·설계서·시연 자료 갱신<br/>완료 범위와 공개 배포 여부 별도 정리","~11/20"),
    ]
    for x,items in [(34,left),(390,right)]:
        for i,(title,body,day) in enumerate(items):
            y=124+i*68;p.rect(x+9,y+6,3.5,3.5,"#111111")
            p.text(title,x+19,y,277,11.8,bold=True,maxh=19);p.text(body,x+19,y+22,277,10.6,maxh=33)
            p.text(day,x+304,y+15,48,8.8,maxh=28,align=1)
    for x,title,body in [
        (34,"주요 이슈 및 의사결정 사항","지난주 계획 4묶음: 확인 범위 내 완료.<br/>Windows 링크 검사 1개 건너뜀·API 16개 제외.<br/>수동 대비 우위·사람의 편의성은 미입증."),
        (390,"프로젝트 요청 사항","비교 세션 접근 정책·차주 범위 확인.<br/>공개 배포·실사용자 실험은 완료 아님.<br/>추가 통합·회귀 결과는 11~12쪽 참조."),
    ]:
        p.rect(x,400,356,30,"#EEEEEE");p.text(title,x+8,406,340,11.7,bold=True,maxh=20,align=1)
        p.text(body,x+10,439,336,10.2,maxh=47)
    for y in [400,430,494]:p.line(34,y,746,y,"#C7CDD0",1.5 if y==494 else .7)
    return p.finish()


def backup_index():
    p=ReportPage();p.header("[Backup]","현재 근거는 5~12쪽  |  기존 상세 기록과 그림은 13~30쪽에 보존",4)
    sections=[
        ("5쪽  지난주 계획 대비 완료 여부","v0.4에서 남았던 두 계정 통합·최신 전체 회귀를 추가 검증해 판정 갱신"),
        ("6~7쪽  요약·코딩 독립 출력 검증","이전 평가의 동률·한계 유지. 이번 권한 검사와 프롬프트 성능 평가는 구분"),
        ("8~10쪽  설계서·차주 계획·기존 근거","전체 분석·설계서와 다음 개선의 완료 기준. 과거 설계서는 기준 시점 보존"),
        ("11~12쪽  추가 통합·회귀 검증과 수정","18시나리오, 전체 검사 결과, 발견한 문제·수정·제외한 검사 범위"),
        ("13~30쪽  11/06 보고의 과거 백업","기존 기능·실험·설계 그림·화면은 보존. 현재 판정은 앞의 3~12쪽 적용"),
    ]
    for i,(title,body) in enumerate(sections):
        y=117+i*62;p.rect(36,y+8,4,4,"#111111");p.text(title,51,y,694,14.2,bold=True,maxh=22)
        p.text(body,51,y+27,694,10.8,base.MUTED,maxh=19)
    p.note("이번 추가 검증은 유료 모델 API 0회. 테스트 전용 DB와 합성 계정을 사용하고 기존 사용자 자료는 사용하지 않았다.<br/>"
           "보고 기간·학교 표기·본 보고 3쪽 양식은 v0.4와 동일. v0.4 파일과 기존 실험 결과는 덮어쓰지 않았다.",465)
    return p.finish()


def previous_plan():
    p=ReportPage();p.header("[Backup] 지난주 계획 대비 완료 여부","11/12 추가 통합·전체 회귀 검사 반영  |  네 묶음 모두 아래의 확인 범위에서 완료",5)
    p.table(["지난주 계획·판정","확인한 근거","해석 범위·미포함 사항"],[
        ["저장·재사용<br/>복귀 보완<br/><b>완료</b>","초안·GEPA 결과 보관과 재사용 연결 검사.<br/>이번에는 두 계정 실제 HTTP·브라우저에서<br/>로그아웃 정리·재로그인·저장 내용 복귀 확인.","유료 GEPA 실호출은 미실시.<br/>권한 확인 후 화면 정리를 포함.<br/>사람의 사용 편의성 실험은 아님."],
        ["팀 기능·권한<br/><b>완료</b>","18시나리오 통과. 공유·파일 업/다운로드,<br/>미지정/익명 차단·수신자 변경·버전 충돌,<br/>담당 인계·이전 기록·팀 조합 원본 보존.","두 브라우저 계정+교체 대상·익명<br/>대조. 합성 자료의 로컬 검증.<br/>공개 서버 침투 시험은 아님."],
        ["설계 대응<br/>전체 회귀<br/><b>완료*</b>",f"전체 설계서 97쪽과 구현 대응 정리.<br/>최신 Python {BACK:,}개·프론트 {FRONT}개 통과.<br/>빌드 성공, 기준 소스 342개 해시 기록·대조.","*not-api 전체 검사 기준.<br/>환경 제약 1개 건너뜀, API 16개 제외.<br/>공개 배포는 별도 미완료."],
        ["독립 평가<br/><b>완료</b>","요약 9원문, 코딩 두 기능 각 8과제의<br/>첫 답변·판정·실행 결과 보존.<br/>일반/수동/제품 비교와 실패·동률 기록.","새 평가 준비·실행 완료.<br/>기존 실험 4차 확증과 다름.<br/>선호 발견·사람의 시간은 미측정."],
    ],[136,340,236],heights=[79]*4,size=10.3)
    p.note("v0.4의 ‘일부 완료’ 두 항목을 추가 실행 근거로 갱신. 전 제품·보안·배포의 모든 검사가 끝났다는 뜻은 아니다.<br/>"
           "상세 실행·수정·원자료는 11~12쪽. 프롬프트 평가 수치와 인간 효과의 미검증 범위는 6~7쪽 그대로 유지.")
    return p.finish()


def next_acceptance():
    p=ReportPage();p.header("[Backup] 차주 계획과 완료 기준","11/14~11/20 계획  |  완료한 통합 검사는 보존하고 다음 변경의 경계·검증에 집중",9)
    p.table(["계획·담당·기한","완료로 판단할 근거","범위·실행 원칙"],[
        ["입력·지침 의미 정렬<br/>윤정우 / ~11/16","요약 두 경로의 길이 제한·오류 안내 대조.<br/>한·영 React 3축 지침의 예외·역할 분리 정렬.<br/>경계값·조건 충돌·출력 회귀 통과.","변경 전후 지침과 원인을 기록.<br/>기존 저장본 자동 덮어쓰기 금지."],
        ["비교 세션 접근 정책<br/>공동 / ~11/18","ID 기반 메모리 세션의 접근·민감 원문 정책<br/>확정, 필요한 소유권/수명 검사 설계·반영.<br/>개인 보관함·인수인계 권한 검사 유지.","이번 인수인계 통과를 모든<br/>메모리 세션의 계정 격리로<br/>확대 해석하지 않음."],
        ["변경 지침 재검증<br/>고차원·공동 / ~11/19","변경 경로에 새 자료·수동 지침·평가 기준을<br/>먼저 고정. 첫 답변을 독립 생성·보존.<br/>조건·내용/타입·동작을 나눠 평가.","유료 API 없이 보조 에이전트.<br/>우위가 없으면 동률·저하 보고.<br/>새 표본 수는 실행 전 확정."],
        ["시연·문서 정리<br/>공동 / ~11/20","변경 기능 회귀, 요구·화면·API·DB 대응<br/>및 시연 자료 갱신. 완료 범위·남은 이슈<br/>·공개 배포 여부를 구분해 기록.","이미 통과한 검사도 코드 변경<br/>영향이 있으면 다시 확인.<br/>실사용 효과는 별도 후속 과제."],
    ],[161,328,223],y=115,heights=[80]*4,size=10.2)
    p.note("이번 주 두 계정 통합·최신 전체 회귀는 실행 완료했다. 새 변경 없이 단순 반복 검사 횟수를 성과로 늘리지 않는다.<br/>"
           "유료 모델 실행·공개 배포·실사용자 만족도와 시간 절감은 이번 기술 검증의 완료 범위에 포함하지 않는다.")
    return p.finish()


def integration():
    p=ReportPage();p.header("[Backup] 두 계정 공유·첨부·권한 통합 검증","11/12  |  Chromium 실제 화면 + 프로덕션 빌드 + 로컬 HTTP + 테스트 SQLite  |  18/18 시나리오 통과",11)
    p.table(["검증 묶음","실제 확인한 내용"],[
        ["계정·비공개 원본","쿠키가 분리된 두 브라우저 계정. 미공유 본문·개인 지침은 타 계정 거절, 익명은 로그인 요구."],
        ["첨부·공유·다운로드","화면에서 파일 선택·저장·공유. 수신자 다운로드 바이트 일치와 새 탭 UTF-8 미리 보기 확인."],
        ["권한 회수·이전 기록","교체 대상 계정에 재공유 후 이전 수신자의 본문·기록·첨부 거절. 공유 전 기록도 접근 거절."],
        ["충돌·담당 인계","오래된 창 저장은 409와 초안 보존, 최신 서버 값 유지. 이어받은 수신자만 편집·완료·재개."],
        ["첨부 이력·복귀·팀 기준","현재 첨부 제외 후 허용된 과거 버전은 보존. 로그아웃 초안 정리·재로그인, 팀 초대·조합 출처 보존."],
    ],[151,561],y=115,heights=[43]*5,size=10.6)
    p.text("수정한 문제: 권한이 사라진 작업을 다시 열어 거절받아도 이전 내용이 화면에 남음.",35,375,710,11.7,bold=True,maxh=20)
    p.text("응답 상태를 구분하고 현재 접근 불가를 확인하면 화면·목록·임시 초안을 정리한다.<br/>"
           "없는 과거 기록, 일시 장애, 단순 버전 충돌에서는 유효한 작업과 미저장 내용을 보존한다.<br/>"
           "수정 전 실제 브라우저 재현 → 관련 회귀 10/10 → 수정 빌드의 전체 18시나리오 재실행 순으로 확인.",35,410,710,10.6,maxh=47)
    p.note("두 활성 계정 외에 수신자 교체용 1계정·익명 대조 포함. 팀 기준 조합·초대 권한은 같은 쿠키의 실제 HTTP로 검사.<br/>"
           "로그·실행 코드: docs/verification/2026-11-12/ (12쪽). 이미 받은 파일·클립보드를 회수하는 기능은 아니다.")
    return p.finish()


def regression():
    p=ReportPage();p.header("[Backup] 최신 전체 회귀 검사와 수정 근거","11/12  |  같은 코드·기존 의존성  |  유료 모델 API 0회  |  원자료와 소스 해시 보존",12)
    p.table(["검사","수정 전/관련 검사","최종 결과"],[
        ["Python not-api 전체","정상 연결 환경: 1,353 통과·4 실패",f"{BACK:,} 통과·0 실패·1 건너뜀"],
        ["프론트 전체 / 빌드","초기 120 통과 / 빌드 성공",f"회귀 3개 추가 후 {FRONT} 통과 / 성공"],
        ["계정·팀 통합 시나리오","권한 거절 뒤 화면 잔류 재현","18/18 통과"],
        ["수정 관련 묶음","도메인·조건 처리 122개 / UI 10개","모두 통과 (전체 검사와 중복)"],
    ],[165,299,248],y=116,heights=[40]*4,size=10.7)
    p.text("전체 검사의 4개 실패 원인: 요약 보조 설정을 엔진 도메인 정의로 잘못 수집.",35,326,710,11.5,bold=True,maxh=20)
    p.text("보조 설정 1개만 명시적으로 분리하고 영어·한국어 전용 형식 검사 2개를 추가했다. 나머지 모든 도메인은<br/>"
           "기존 검사를 유지한다. 보조 설정을 오인한 4건이 전용 2건으로 바뀌어 최종 검사 수가 달라졌다.<br/>"
           "설정 파일의 기존 경로·바이트와 고정 실험 결과는 유지했다. 최종 검사 기준 소스 342개의 해시를 기록·대조했다.",35,358,710,10.5,maxh=46)
    p.text("제외·한계: 실제 API 검사 16개 제외. Windows 심볼릭 링크 생성 권한 부족으로 1개 건너뜀.<br/>"
           "기존 500KB 초과 번들 경고는 남아 있다. 초기 격리 환경의 로컬 연결 실패는 제품 결과에서 제외하고 재실행했다.",35,419,710,10.3,maxh=32)
    p.note("원자료: docs/verification/2026-11-12/results.json 및 results/의 backend-final.log·frontend-final.log·browser.json.<br/>"
           "테스트 DB·키·쿠키는 보고서에 포함하지 않음. 공개 배포·실제 모델 출력 품질·사람의 효과는 별도 검증이다.")
    return p.finish()


def sources():
    return base.sources()


def main():
    hashes=base.verify_evidence()
    prior=ROOT/"output/pdf/Revealed_진행현황_주간보고서_v0.4.pdf"
    hashes[str(prior)]=hashlib.sha256(prior.read_bytes()).hexdigest()
    previous=PdfReader(base.PREVIOUS)
    writer=PdfWriter()
    fns=[cover,wbs,weekly,backup_index,previous_plan,base.summary_results,base.coding_results,base.design_results,next_acceptance,sources,integration,regression]
    for fn in fns:writer.add_page(fn())
    for i in range(4,len(previous.pages)):
        page=previous.pages[i];footer=ReportPage();footer.footer(len(writer.pages)+1,True,i+1);page.merge_page(footer.finish());writer.add_page(page)
    for i,title in enumerate(["표지","1. 프로젝트 일정 - WBS","2. 프로젝트 진행현황","Backup","지난주 계획 대조","요약 검증","코딩 검증","설계서","차주 완료 기준","근거","두 계정 통합","최신 전체 회귀"]):writer.add_outline_item(title,i)
    writer.add_outline_item("11/06 과거 백업",12)
    writer.add_metadata({"/Title":"Revealed 주간보고서 v0.5 · 2026-11-13 · 10주차","/Author":"윤정우 · 고차원","/Subject":"두 계정 통합·최신 전체 회귀 결과와 수정 반영"})
    with OUT.open("wb") as stream:writer.write(stream)
    assert len(writer.pages)==30
    for path,digest in hashes.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest
    QA.mkdir(parents=True,exist_ok=True)
    manifest={"version":VERSION,"report_date":"2026-11-13","cutoff":"2026-11-12","pages":30,"main_pages":[1,2,3],"new_verification_pages":[11,12],"historical_backup":[13,30],"output":str(OUT.relative_to(ROOT)),"sha256":hashlib.sha256(OUT.read_bytes()).hexdigest(),"previous_sources_unchanged":True,"visual_review":"pending","metrics":DATA}
    (QA/"build_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    plan=[{"plan":item["plan"],"status":"완료(보고서 5쪽의 확인 범위)","previous_status":item["status"],"new_evidence":"docs/verification/2026-11-12/results.json"} for item in base.PLAN_AUDIT]
    (HERE/"plan_audit_v0_5.json").write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Written {OUT}: {len(writer.pages)} pages; completed execution evidence loaded")


if __name__=="__main__":main()

"""Weekly v0.6: completed GitHub CI and three offline data-check reruns."""
from pathlib import Path
import hashlib
import json
from pypdf import PdfReader, PdfWriter
import build_report_v0_5 as previous

ROOT = previous.ROOT
HERE = Path(__file__).resolve().parent
BASE = previous.base
DrawingPage = previous.ReportPage.__bases__[0]
VERSION = "0.6"
OUT = ROOT / "output/pdf/Revealed_진행현황_주간보고서_v0.6.pdf"
QA = ROOT / "tmp/weekly_2026_11_13/v0_6"
EVIDENCE = ROOT / "docs/verification/2026-11-12/ci/results.json"
CI = json.loads(EVIDENCE.read_text(encoding="utf-8"))
assert all(run["conclusion"] == "success" for run in CI["runs"].values())
assert CI["focused_rerun"]["passed"] == 3 and CI["focused_rerun"]["failed"] == 0


class ReportPage(DrawingPage):
    def text(self, value, *args, **kwargs):
        replacements = {
            "최신 전체 재검사 필요": "로컬·CI 회귀 통과",
            "출력 검증·통합 잔여": "출력·두 계정 검증 완료",
            "2026.11.13 보고  |  10주차  |  v0.5": "2026.11.13 보고  |  10주차  |  v0.6",
            "11/12 추가 검증 반영  ·  두 계정 통합·최신 전체 회귀 완료  ·  본 보고 1~3쪽":
                "11/12 실적  ·  GitHub CI 완료·자료 의존 검사 3개 재확인 반영  ·  본 보고 1~3쪽",
            "전체 설계서 97쪽·검증 근거 정리<br/>Python 1,355·프론트 123개 통과, 빌드 성공":
                "설계서 97쪽·로컬 Python 1,355개 통과<br/>CI 1,353·프론트 123·자료 검사 3개 통과",
            "지난주 계획 4묶음: 확인 범위 내 완료.<br/>Windows 링크 검사 1개 건너뜀·API 16개 제외.<br/>수동 대비 우위·사람의 편의성은 미입증.":
                "지난주 계획 4묶음: 확인 범위 내 완료.<br/>CI 누락 3개 로컬 통과·API 16개 제외.<br/>수동 대비 우위·사람의 편의성은 미입증.",
            "비교 세션 접근 정책·차주 범위 확인.<br/>공개 배포·실사용자 실험은 완료 아님.<br/>추가 통합·회귀 결과는 11~12쪽 참조.":
                "비교 세션 접근 정책·차주 범위 확인.<br/>공개 배포·실사용자 실험은 완료 아님.<br/>통합·회귀·CI 근거는 11~14쪽 참조.",
            "전체 설계서 97쪽과 구현 대응 정리.<br/>최신 Python 1,355개·프론트 123개 통과.<br/>빌드 성공, 기준 소스 342개 해시 기록·대조.":
                "전체 설계서 97쪽·소스 342개 해시 대조.<br/>로컬 1,355·CI 1,353·프론트 123개 통과.<br/>누락 3개 재확인·컨테이너 검사 통과.",
            "*not-api 전체 검사 기준.<br/>환경 제약 1개 건너뜀, API 16개 제외.<br/>공개 배포는 별도 미완료.":
                "*로컬·CI not-api 검사 기준.<br/>차이·재확인은 13~14쪽 참조.<br/>API 16개 제외·공개 배포 미완료.",
            "[Backup] 최신 전체 회귀 검사와 수정 근거": "[Backup] 로컬 전체 회귀 검사와 수정 근거",
            "제외·한계: 실제 API 검사 16개 제외. Windows 심볼릭 링크 생성 권한 부족으로 1개 건너뜀.<br/>기존 500KB 초과 번들 경고는 남아 있다. 초기 격리 환경의 로컬 연결 실패는 제품 결과에서 제외하고 재실행했다.":
                "로컬 한계: 실제 API 검사 16개 제외. Windows 심볼릭 링크 1개 건너뜀 → CI에서 통과(13쪽).<br/>기존 500KB 초과 번들 경고는 유지. 초기 격리 환경의 연결 실패는 집계에서 제외하고 재실행했다.",
        }
        value = replacements.get(value, value)
        if str(value).startswith("위 H/E 경로는 로컬 저장소 기준."):
            value = ("기존 H/E/D 근거는 보존. 통합·회귀는 docs/verification/2026-11-12/, CI·재검증은 하위 ci/ 참조.<br/>"
                     "지난주 계획 원본은 v0.3 3쪽. 과거 백업은 15~32쪽이며 최신 근거는 11~14쪽을 적용.")
        if isinstance(value, str):
            value = value.replace("상세 실행·수정·원자료는 11~12쪽.", "상세 실행·수정·CI 원자료는 11~14쪽.")
        return super().text(value, *args, **kwargs)

    def footer(self, number, backup=False, old_number=None):
        self.rect(0, 514, 780, 26, "#FFFFFF")
        label = (f"과거 백업 | 11/06 v0.3 원문 {old_number}쪽 | 현재 실적·계획·판정은 3~14쪽" if backup
                 else "Revealed | AI/SW융합프로젝트 | 2026.11.13 | 10주차 | 실적 확인 11/12까지")
        self.text(label, 34, 520, 620, 8, BASE.MUTED, maxh=13)
        self.text(f"v{VERSION}   {number}", 657, 518, 89, 9, BASE.MUTED, maxh=15, align=2)


# Reuse existing layout functions without rewriting prior artifacts or evidence.
previous.ReportPage = ReportPage
BASE.ReportPage = ReportPage


def backup_index():
    p = ReportPage()
    p.header("[Backup]", "현재 근거는 5~14쪽  |  기존 상세 기록과 그림은 15~32쪽에 보존", 4)
    sections = [
        ("5쪽  지난주 계획 대비 완료 여부", "네 묶음의 확인 범위와 한계 유지. 로컬·CI·자료 의존 검사 결과 추가"),
        ("6~7쪽  요약·코딩 독립 출력 검증", "이전 비교의 동률·한계 유지. CI 성공을 프롬프트의 성능 향상으로 해석하지 않음"),
        ("8~10쪽  설계서·차주 계획·기존 근거", "전체 분석·설계서와 다음 변경의 완료 기준. 기존 설계서는 기준 시점 보존"),
        ("11~12쪽  두 계정 통합·로컬 전체 회귀", "18시나리오, Python 1,355·프론트 123개 통과 및 발견한 문제의 수정 근거"),
        ("13~14쪽  GitHub CI·건너뛴 검사 3개 재검증", "브랜치·PR·컨테이너 검사 성공. 자료 부재 원인·기존 로컬 통과·별도 재확인"),
        ("15~32쪽  11/06 보고의 과거 백업", "기존 기능·실험·설계 그림·화면 보존. 현재 판정은 앞의 3~14쪽 적용"),
    ]
    for i, (title, body) in enumerate(sections):
        y = 112 + i * 55
        p.rect(36, y + 7, 4, 4, "#111111")
        p.text(title, 51, y, 694, 13.5, bold=True, maxh=22)
        p.text(body, 51, y + 25, 694, 10.6, BASE.MUTED, maxh=19)
    p.note("보고 기간·학교 표기·본 보고 3쪽 양식 유지. v0.5 PDF와 기존 실험 결과는 덮어쓰지 않았다.<br/>"
           "이번 보고서 갱신·재검증의 유료 모델 API 호출은 0회. 3개 재검사는 이전 전체 검사와 중복이며 합산하지 않는다.", 465)
    return p.finish()


def ci_results():
    p = ReportPage()
    p.header("[Backup] GitHub 자동 검사 완료", "11/12 완료  |  검증 코드 c784808  |  브랜치·PR·컨테이너 검사 모두 성공", 13)
    p.table(["자동 검사", "실제 확인 결과", "판정·범위"], [
        ["Tests / 브랜치 push", "Python 1,353 통과·3 건너뜀·16 API 제외<br/>프론트 123 통과·배포 빌드 성공", "성공 / 실패 0<br/>Python 검사 165.80초"],
        ["Tests / PR", "Python 1,353 통과·3 건너뜀·16 API 제외<br/>프론트 123 통과·배포 빌드 성공", "성공 / 실패 0<br/>Python 검사 208.07초"],
        ["Hosted container", "Docker 이미지 빌드·임시 저장소 실행<br/>JS/TS 도구 확인·재시작 후 데이터 유지", "성공 / 모든 단계 통과<br/>공개 서비스 배포는 아님"],
    ], [158, 350, 204], y=115, heights=[56] * 3, size=10.6)
    p.text("로컬과 CI의 검사 수가 다른 이유", 35, 331, 710, 12, bold=True, maxh=21)
    p.text("로컬: 1,355 통과·1 건너뜀. CI: 1,353 통과·3 건너뜀. 두 환경 모두 API 16개는 제외했다.<br/>"
           "CI에는 MACSum·RACE/EvalPlus 자료가 없어 3개가 빠졌고, 로컬에서 빠진 심볼릭 링크 검사는 CI에서 통과했다.<br/>"
           "자료가 있는 로컬에서 그 3개는 이미 통과했으며 이번에도 3/3 통과했다(14쪽). 서로 다른 실행 수를 합산하지 않는다.",
           35, 364, 710, 10.5, maxh=48)
    links = "  |  ".join(f'<link href="{CI["runs"][key]["url"]}" color="#164E8A"><u>{title}</u></link>'
                         for key, title in [("push", "브랜치 검사 원문"), ("pr", "PR 검사 원문"), ("container", "컨테이너 검사 원문")])
    p.text(links, 35, 433, 710, 11, maxh=19)
    p.note("근거: docs/verification/2026-11-12/ci/runs.json·results.json 및 push/pr-test-excerpt.log.<br/>"
           "위 결과는 c784808 코드의 완료 기록이다. 보고서 게시 후 시작되는 자동 검사는 별도 실행이며 미리 성공으로 표시하지 않는다.")
    return p.finish()


def skipped_checks():
    p = ReportPage()
    p.header("[Backup] CI에서 건너뛴 3개 검사 재확인", "11/12 로컬 별도 실행  |  3/3 통과·실패 0·건너뜀 0  |  6.55초  |  네트워크 차단", 14)
    p.table(["검사", "CI에서 빠진 이유", "기존 로컬·이번 재검증"], [
        ["MACSum 평가 수치<br/>재계산·저장값 대조", "MACSum 원문이 CI에 없음.<br/>data/는 GitHub에 올리지 않음.", "이전 로컬 전체 검사 통과 → 이번 통과.<br/>사람 작성 요약의 길이·표현 겹침 측정<br/>결과를 저장한 실험 수치와 대조."],
        ["MACSum 속성 →<br/>가상 선호 구성", "같은 MACSum 원문·속성 필요.<br/>자료가 없으면 명시적으로 건너뜀.", "이전 로컬 전체 검사 통과 → 이번 통과.<br/>속성·참조 요약에서 가상 선호를 만드는<br/>기능 검사. 실제 사람의 선호 추정은 아님."],
        ["RACE·EvalPlus 캐시<br/>무결성·평가 준비", "고정 버전 자료 캐시가 CI에 없음.<br/>검사가 자동 다운로드하지 않음.", "이전 로컬 전체 검사 통과 → 이번 통과.<br/>자료 해시·RACE 함수·542과제 준비 확인.<br/>새 생성 코드의 기능 실행 검증은 아님."],
    ], [173, 230, 309], y=115, heights=[72] * 3, size=10.4)
    p.text("확인 방법과 비용", 35, 380, 710, 12, bold=True, maxh=20)
    p.text("같은 코드의 수집 목록과 로컬·CI의 1,356개 결과 순서를 대조해 건너뛴 검사 이름을 확인했다.<br/>"
           "세 검사만 -vv로 별도 실행하고 XML·개별 통과 로그를 저장했다. .env 로딩·모델 키·실제 생성 설정을 끄고<br/>"
           "소켓 연결을 차단했다. 외부 연결 시도 0회·유료 모델 API 0회. 데이터셋과 사용자 DB는 게시하지 않는다.",
           35, 412, 710, 10.4, maxh=48)
    p.note("근거: ci/comparison.json·collected.json·focused.log·focused.xml·focused-guard.json.<br/>"
           "위 3개는 기존 로컬 1,355개에 포함된다. API 검사 16개는 이번에도 실행하지 않았으며 인간 효과·프롬프트 우위를 증명하지 않는다.")
    return p.finish()


def main():
    hashes = BASE.verify_evidence()
    for version in ["0.4", "0.5"]:
        path = ROOT / f"output/pdf/Revealed_진행현황_주간보고서_v{version}.pdf"
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    hashes[str(EVIDENCE)] = hashlib.sha256(EVIDENCE.read_bytes()).hexdigest()
    writer = PdfWriter()
    pages = [previous.cover, previous.wbs, previous.weekly, backup_index, previous.previous_plan,
             BASE.summary_results, BASE.coding_results, BASE.design_results, previous.next_acceptance,
             previous.sources, previous.integration, previous.regression, ci_results, skipped_checks]
    for fn in pages:
        writer.add_page(fn())
    old = PdfReader(BASE.PREVIOUS)
    for i in range(4, len(old.pages)):
        page = old.pages[i]
        footer = ReportPage()
        footer.footer(len(writer.pages) + 1, True, i + 1)
        page.merge_page(footer.finish())
        writer.add_page(page)
    titles = ["표지", "1. 프로젝트 일정 - WBS", "2. 프로젝트 진행현황", "Backup", "지난주 계획 대조",
              "요약 검증", "코딩 검증", "설계서", "차주 완료 기준", "근거", "두 계정 통합", "로컬 전체 회귀",
              "GitHub CI 완료", "CI에서 건너뛴 검사 재확인"]
    for i, title in enumerate(titles):
        writer.add_outline_item(title, i)
    writer.add_outline_item("11/06 과거 백업", 14)
    writer.add_metadata({"/Title": "Revealed 주간보고서 v0.6 · 2026-11-13 · 10주차",
                         "/Author": "윤정우 · 고차원", "/Subject": "GitHub CI 완료와 데이터 의존 검사 3개 오프라인 재확인"})
    with OUT.open("wb") as stream:
        writer.write(stream)
    assert len(writer.pages) == 32
    assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest for path, digest in hashes.items())
    QA.mkdir(parents=True, exist_ok=True)
    manifest = {"version": VERSION, "report_date": "2026-11-13", "cutoff": "2026-11-12", "pages": 32,
                "main_pages": [1, 2, 3], "new_verification_pages": [13, 14], "historical_backup": [15, 32],
                "output": str(OUT.relative_to(ROOT)), "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest(),
                "previous_sources_unchanged": True, "visual_review": "pending", "ci_evidence": CI}
    (QA / "build_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    plan = json.loads((HERE / "plan_audit_v0_5.json").read_text(encoding="utf-8"))
    for row in plan:
        row["additional_evidence"] = "docs/verification/2026-11-12/ci/results.json"
    (HERE / "plan_audit_v0_6.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Written {OUT}: {len(writer.pages)} pages; previous artifacts unchanged")


if __name__ == "__main__":
    main()

"""Author the dated WBS baseline from published project evidence; no model calls."""
from pathlib import Path
from datetime import date, timedelta
import json
import re

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASE = 'https://github.com/a77315829-byte/preference-prompt-tool/blob/cfd1fe44623b46ca8bf94da059c91e72945de517/'
SOURCES = {
    'S01': ('전체 분석·설계서 v1.0', 'docs/system-design/README.md'),
    'S02': ('주간보고 v0.6의 기존 WBS·차주 계획', 'docs/weekly_reports/2026-11-13/build_report_v0_5.py'),
    'S03': ('요약 길이·충돌 v2 및 최신 회귀', 'docs/verification/2026-11-12-summary-policy/results/validation.json'),
    'S04': ('두 계정 통합 18개 시나리오', 'docs/verification/2026-11-12/results.json'),
    'S05': ('요약 새 원문 9개 비교', 'benchmarks/summary_contract_revision/README.md'),
    'S06': ('AI 답변 방식 새 React 8과제', 'benchmarks/coding_react_current/README.md'),
    'S07': ('React 스타일 새 8과제', 'benchmarks/react_style_current/README.md'),
    'S08': ('실제 GEPA의 오프라인 탐색', 'benchmarks/summary_gepa_offline/README.md'),
    'S09': ('요구사항 및 수용 기준', 'docs/system-design/chapters/01-analysis.md'),
    'S10': ('운영·배포 절차', 'docs/DEPLOYMENT.md'),
    'S11': ('현재 구현·검증 경계', 'CLAUDE.md'),
    'S12': ('학기 15주 일정 기준', 'docs/weekly_reports/2026-11-06/build_report_v0_2.py'),
    'S13': ('과거 4주 WBS·5인 역할 제안', 'docs/PROJECT_PLAN.md'),
    'S14': ('기존 요약 파일럿·분리 평가', 'benchmarks/summary_agent_pilot/README.md'),
    'S15': ('코딩 공개 지표·실험', 'benchmarks/coding_public/README.md'),
    'S16': ('CI 건너뜀 3개 로컬 재검증', 'docs/verification/2026-11-12/ci/results.json'),
    'S17': ('최신 커밋 GitHub Tests 통과', 'https://github.com/a77315829-byte/preference-prompt-tool/actions/runs/43216998372'),
    'S18': ('최신 커밋 컨테이너 검사 통과', 'https://github.com/a77315829-byte/preference-prompt-tool/actions/runs/43216998320'),
}
# Preserve the report's nine work-package IDs. New IDs add level-3 work units.
GROUPS = [
    ('1.1', '분석', '주제·요구 정리', [1,2,3], [9], '공동'),
    ('1.2', '분석', '선호·코딩 실험 기반', list(range(3,9)), [8,9], '고차원'),
    ('2.1', '설계', '전체 분석·설계서', [8,9,10], [8,9], '윤정우'),
    ('3.1', '구현', '개인 지침·재사용', list(range(5,10)), [8,9], '윤정우'),
    ('3.2', '구현', '팀 기준·인수인계', list(range(6,10)), [8,9], '윤정우'),
    ('4.1', '검증', '통합 검사·복귀 보완', [8,9,10,11], [8,9], '공동'),
    ('4.2', '검증', '독립 출력·권한 평가', [10,11,12], [9], '공동'),
    ('5.1', '이행', '운영·시연 안정화', list(range(8,15)), [8,9], '윤정우'),
    ('5.2', '안정화', '최종 결과·발표', [14,15], [], '공동'),
]
tasks = []


def add(group, name, req, deliverable, acceptance, sources='', deps='', owner=None,
        status='완료 확인', start=None, end=None, hours=None, priority='필수', note=''):
    definition = next(g for g in GROUPS if g[0] == group)
    index = 1 + sum(t['group'] == group for t in tasks)
    tasks.append(dict(id=f'{group}.{index}', level=3, group=group, phase=definition[1], name=name,
                      requirements=req, owner=owner or definition[5], status=status, priority=priority,
                      predecessors=deps.split(',') if deps else [], plan_start=start, plan_end=end,
                      estimate_hours=hours, actual_start=None, actual_end=None,
                      evidence_date='2026-11-12' if status == '완료 확인' else None,
                      deliverable=deliverable, acceptance=acceptance,
                      sources=sources.split(',') if sources else [], note=note))


# Analysis: completion refers to the stated artifact/technical criterion, not human effect.
add('1.1','제품 문제·대상 사용자 정의','공통','문제·대상·가설 목록','학생·작은 팀의 반복 지침 작성 문제와 미측정 가설을 구분','S01,S09')
add('1.1','요약 중심 목표와 완료 범위 정리','FR-02,FR-03','목표·범위·제외 항목','조건 준수와 내용 보존을 별도 목표로 두고 코딩 두 경로 유지','S09,S11','1.1.1')
add('1.1','기능·비기능 요구사항 분해','FR-01~16,NFR-01~12','요구사항 목록','요구 ID별 관찰 가능한 수용 조건과 구현 경계 존재','S09','1.1.2')
add('1.1','액터·업무·데이터 경계 분석','NFR-01,NFR-05','권한·원문·지침 구분','방문자·회원·팀장·수신자의 역할과 저장 경계를 명시','S01,S09','1.1.3')
add('1.1','비교 메모리 세션 접근 정책 확정','NFR-01,NFR-05','세션 소유권·만료 정책','익명 체험과 계정 세션의 조회·선택·삭제·원문 보존 범위를 결정','S02','1.1.4',status='예정',start='2026-11-13',end='2026-11-16',hours=3,note='보관함 권한 검증으로 완료 처리하지 않음')
add('1.1','잔여 범위·담당·일정 합의','공통','합의된 상세 WBS','필수 범위와 선택 후속, 담당과 마일스톤을 팀이 확인','S02,S13','1.1.2',status='예정',start='2026-11-13',end='2026-11-13',hours=1,owner='공동')

add('1.2','MACSum 데이터·속성 적용 범위 정리','FR-02,NFR-08','데이터 출처·평가 단위','영어 원문 조건 평가와 한국어 정량 복원율 미산출을 구별','S14,S11')
add('1.2','코딩 공개 지표 활용 범위 조사','FR-04,FR-05','RACE·EvalPlus 검토 기록','정적 지표·기능 테스트·미확인 결과를 구분','S15')
add('1.2','일반·수동·제품 비교 설계','NFR-08','3조건 비교 프로토콜','동일 과제·목표·첫 응답·독립 판정 원칙을 고정','S05,S06,S07','1.1.2')
add('1.2','개선용·선택용·최종 자료 분리','NFR-08','자료 분할·해시','관찰한 최종 자료를 다시 독립 평가로 사용하지 않음','S08,S11','1.2.3')
add('1.2','내용 보존·조건·기능 기준 분리','NFR-08','독립 평가 기준','조건 일치와 핵심 명제, 타입과 실제 동작을 합산하지 않음','S05,S06,S07','1.2.3')
add('1.2','GEPA 유지·채택 기준 검토','FR-13','탐색·선택 결과 기록','비채택 후보의 점수를 최종 선택 결과로 바꾸지 않음','S08','1.2.4')
add('1.2','사람의 편의성·수정 시간 평가','공통','후속 사용자 평가 계획','참여자를 확보한 경우에만 수행하고 미측정을 0으로 쓰지 않음','S09',priority='선택',status='선택 후속',note='현 최종 완료의 필수 조건 아님. 일정·공수 미확정')

add('2.1','유즈케이스 명세·다이어그램','FR-01~16','24개 UC 명세','주·대체·오류 흐름과 액터를 요구사항에 연결','S01','1.1.3')
add('2.1','화면·정보 구조·상태 설계','FR-02~16,NFR-10','화면 흐름·와이어프레임','진입·미정·로딩·오류·완료·복귀 상태를 명세','S01','2.1.1')
add('2.1','모듈·클래스·아키텍처 설계','NFR-07','모듈·클래스 관계도','React·HTTP·서비스·도메인·DB의 책임을 구분','S01','1.1.3')
add('2.1','처리 시퀀스·활동·상태 설계','FR-02,FR-03,FR-10,FR-13','시퀀스·활동·상태도','비교·충돌·저장·개선·인수인계 전이를 설명','S01','2.1.2,2.1.3')
add('2.1','API 입출력·오류·권한 명세','NFR-01,NFR-02','API 목록·계약','요청·응답·권한·사용량·오류를 경로별 연결','S01','2.1.3')
add('2.1','ERD·테이블·제약 설계','NFR-02,NFR-03','ERD·데이터 사전','16테이블의 키·관계·버전·삭제 영향 명세','S01','2.1.3')
add('2.1','운영·검증·추적성 설계','NFR-04~12','운영·검증 장','요구·구현·검사·한계를 연결하고 비용 경계 명시','S01','2.1.5,2.1.6')
add('2.1','전체 설계서 v1.0 편집·검수','공통','97쪽 분석·설계서','표·그림·본문·근거가 읽히는 PDF와 편집 원본 제공','S01','2.1.1,2.1.2,2.1.3,2.1.4,2.1.5,2.1.6,2.1.7')
add('2.1','요약 v2·세션 정책 설계 변경 반영','FR-03,NFR-01','설계서 다음 판본','새 충돌 종류·해결 선택·입력 한도·세션 정책을 명세에 반영','S02,S03','3.1.4,3.1.5,4.1.7',status='예정',start='2026-11-19',end='2026-11-20',hours=4)

add('3.1','계정 생성·로그인·소유권','FR-01','계정 API·화면','계정 격리·로그아웃·인증 회귀 통과','S03,S09','2.1.5,2.1.6')
add('3.1','요약 A/B·보류·되돌리기','FR-02.1~3','비교 화면·세션','현재 쌍만 반영하고 되돌리기 후 결과 상태 일치','S03,S11','2.1.2,2.1.4')
add('3.1','최대 8회·자동 종료·미정 표시','FR-02.3~4','종료 이유·추정 상태','8회를 강제하지 않고 종료 이유와 미정 조건 표시','S03,S11','3.1.2')
add('3.1','요약 시작·조건 확인 길이 정책 통일','FR-02.1,FR-03,NFR-05','공통 정책·문자 수 안내','12,000자 초과를 자르지 않고 거절, 공백·이모지 경계 검사 통과','S03','3.1.2')
add('3.1','발췌 상·하한 충돌과 명시적 해결','FR-03.1~3','조건 확인 v2','문장 부족·상한 초과는 지침 보류, 허용된 조건만 변경','S03','3.1.4')
add('3.1','원문·재사용 지침 분리와 복사','FR-03.4,FR-07.3','지침만/작업 함께 복사','재사용 본문에 원문·선택 문장이 섞이지 않음','S03,S11','3.1.5')
add('3.1','AI 답변 방식 네 항목 설정','FR-04','환경·설명·주석·구성·출력','확인한 네 조건을 모델 없이 지침 전문으로 조립','S06,S11','2.1.2')
add('3.1','코딩 예시 비교·중도 완료·취소','FR-06','직접 설정·예시 전환','최대 8회·중도 종료·엇갈림·취소 복귀가 기존 선택을 보존','S03,S11','3.1.7')
add('3.1','React 코드 스타일 별도 비교','FR-05','3축 비교·결과','구성·스타일 관리·타입 경로가 답변 네 항목과 분리','S07,S03','2.1.2')
add('3.1','한·영 React 지침 의미 정렬','FR-05,NFR-10','양언어 지침 대응표·수정본','예외·역할 분리·타입 의미를 같은 기준으로 설명하고 회귀 통과','S02','3.1.9',status='예정',start='2026-11-13',end='2026-11-16',hours=3)
add('3.1','개인 보관함·수정·새 작업 재사용','FR-07','개인 지침 CRUD·재사용','소유권·revision·원본 보존·새 작업 입력 분리','S03,S04','3.1.1,3.1.6,3.1.7')
add('3.1','초안 복귀·로그아웃·만료 처리','FR-12.1','계정별 임시 초안','24시간 복구·계정 전환·로그아웃 제거 범위 검사','S03,S04','3.1.11')
add('3.1','템플릿·요청문 점검·작업 공간 유지','FR-16','24템플릿·요청문·작업 공간','비교 6개와 업무 초안 18개, 무료·유료 동작 구분','S03,S11','2.1.5')
add('3.1','선택적 GEPA 연결·원본 보존 유지','FR-13,FR-12.2','지원 환경별 개선 경로','명시적 시작·캐시·상한·복구·새 항목 채택 경계 검사','S03,S11','3.1.11',note='운영 13조합의 실제 생성 효과 입증과는 별개')
add('3.1','도구 내보내기·답변·작업 비교 유지','FR-14,FR-15','내보내기·직접 확인 화면','미측정/실패 구분, 작업·시간·조건·기능 근거 별도 기록','S03,S11','3.1.11')

add('3.2','팀 생성·참여·초대 관리','FR-08','팀·초대 API와 화면','회원 팀·익명 체험, 만료·닫기·재개 경계 검사','S03,S04','3.1.1')
add('3.2','팀 기준·필수 규칙 설정','FR-08','팀 기준·필수 항목','팀장 권한과 revision을 검증하고 개인 취향과 구별','S03,S04','3.2.1')
add('3.2','개인·팀 항목별 조합','FR-09','작업용 새 지침','어느 쪽 기준인지 선택하고 원본을 갱신하지 않음','S03,S04','3.2.2,3.1.11')
add('3.2','출처·재조합·선택 되돌림','FR-09,NFR-03','출처 스냅샷·이력 연결','원본 변경·삭제 후 출처 유지, 새 항목으로 재조합','S03,S04','3.2.3')
add('3.2','인수인계 작성·지정 공유','FR-10.1~2','개인 초안·수신자 공유','같은 서버의 지정 계정에만 공개하고 링크 단독 접근 거절','S04','3.1.1')
add('3.2','담당 인계·완료·버전 기록','FR-10.3~4','상태·revision 이력','허용 역할·상태·공유 시작 버전에 맞게 처리','S04','3.2.5')
add('3.2','첨부 업로드·다운로드·제외','FR-11','파일 첨부 기능','크기·개수·전체 용량과 현재/과거 버전 권한 검증','S04','3.2.5')
add('3.2','공유 회수·수신자 변경·화면 정리','FR-10,FR-11,NFR-01','회수 후 서버·화면 처리','이전 대상 접근 차단, 회수 확인 뒤 화면·임시 초안 제거','S04','3.2.6,3.2.7')

add('4.1','Python·프런트 전체 회귀','NFR-12','전체 검사 로그','현재 범위 1,399·129 통과, 건너뜀·API 제외 이유 기록','S03','3.1.5,3.2.8')
add('4.1','실제 브라우저·HTTP·모바일 점검','NFR-10,NFR-11','화면·HTTP 8시나리오','입력·충돌·모바일·코딩 두 진입 확인','S03','3.1.5,3.1.9')
add('4.1','독립 계정 공유·첨부·회수 통합','NFR-01,NFR-02','두 계정 통합 18시나리오','회원·제3자·익명의 공유·첨부·버전·원본 경계 확인','S04','3.2.8')
add('4.1','CI 데이터 의존 건너뜀 로컬 검증','NFR-08','3검사 재검증 기록','캐시·데이터 의존 3개를 유료 호출 없이 로컬 통과','S16','4.1.1')
add('4.1','GitHub·컨테이너 자동 검사','NFR-09,NFR-12','push·PR·컨테이너 검사','cfd1fe4의 세 workflow 통과, 로컬 결과와 배포 상태 구별','S17,S18','4.1.1')
add('4.1','세션 접근 정책 구현','NFR-01,NFR-05','서버 소유권·만료·오류','정한 익명·계정 정책을 API와 안내에 일치시킴','S02','1.1.5',status='예정',start='2026-11-17',end='2026-11-17',hours=5)
add('4.1','세션 ID·원문 접근 통합 검사','NFR-01,NFR-05','교차 계정·만료·익명 검사','타 계정·비인증·만료·선택·조회 경계를 실제 HTTP로 확인','S02','4.1.6',status='예정',start='2026-11-18',end='2026-11-18',hours=3,owner='공동')
add('4.1','변경분 전체 회귀·시연 수용 검사','NFR-10,NFR-12','다음 변경 커밋의 검사 로그','언어 지침·세션 변경 후 회귀·빌드·시연·실패 수정 완료','S02','3.1.10,4.1.7',status='예정',start='2026-11-19',end='2026-11-20',hours=3,owner='공동')

add('4.2','기존 요약 새 9원문 비교','FR-03,NFR-08','일반·수동·제품 결과','고정된 조건과 핵심 내용 보존을 별도로 판정','S05','1.2.5',note='이전 조건 처리 판본의 근거. 최신 v2의 출력 평가 아님')
add('4.2','코딩 답변 방식 새 8과제 비교','FR-04,NFR-08','24첫 응답·타입·동작·조건','조건별 69/69 동작 통과와 수동·제품 8/8 조건 동률 보고','S06','1.2.5,3.1.7')
add('4.2','React 스타일 새 8과제 비교','FR-05,NFR-08','24첫 응답·3축 판정','조건별 56/56 동작 및 타입 통과, 수동·제품 동률 보고','S07','1.2.5,3.1.9')
add('4.2','실제 GEPA 오프라인 탐색 검증','FR-13,NFR-08','탐색·후보 선택·최종 평가','개선/선택/평가 분리, 원본 유지 결과와 한계 공개','S08','1.2.6')
add('4.2','변경 지침용 새 원문·과제 고정','FR-03,FR-05,NFR-08','신규 자료·기준·해시','이전 최종 원문·과제를 제외하고 생성 전에 기준 고정','S02','3.1.5,3.1.10',status='예정',start='2026-11-16',end='2026-11-16',hours=3,owner='고차원')
add('4.2','요약 v2와 수동 지침 새 원문 비교','FR-03,NFR-08','독립 첫 응답·조건·명제 판정','수동/기존/수정 지침의 조건·내용 보존을 분리, 충돌 해결 선택 동일화','S02','4.2.5',status='예정',start='2026-11-17',end='2026-11-18',hours=4,owner='고차원',note='독립 Codex 에이전트 방식 제안. 유료 모델 API 0회')
add('4.2','React 양언어 의미 수정 재비교','FR-05,NFR-08','새 과제 타입·DOM·조건 결과','동일 의미의 목표·새 과제·strict·실제 동작·조건을 별도 확인','S02','4.2.5,3.1.10',status='예정',start='2026-11-17',end='2026-11-18',hours=4,owner='고차원')
add('4.2','독립 재검토·채택 판단·결과 고정','NFR-08','결과표·실패 유형·채택 기록','미확인·동률·열세를 보존하고 결과를 본 재시도를 최종 평가와 구분','S02','4.2.6,4.2.7',status='예정',start='2026-11-19',end='2026-11-19',hours=2,owner='공동')
add('4.2','추가 실사용자 편의성 검증','공통','실사용자 선호·수정 시간','참여자·과제·비용을 확보한 뒤 별도 동의로 수행','S09',status='선택 후속',priority='선택',note='이번 완료 조건과 분리. 에이전트 시간을 사람 시간으로 쓰지 않음')

add('5.1','무료 로컬 실행·배포 이미지 준비','NFR-04,NFR-09','실행 문서·컨테이너','최신 빌드와 API 같은 주소, 모든 LIVE 비활성화 확인','S03,S10','4.1.5')
add('5.1','시연 환경·검증 자료 구성','NFR-05,NFR-10','격리된 데모 계정·샘플','비민감 원문·두 계정·코딩 예제 준비, 유료 실행 없음','S02','4.1.8,4.2.8',status='예정',start='2026-11-20',end='2026-11-20',hours=2)
add('5.1','백업·복원·중단 복구 연습','NFR-06','합성 DB 백업·복원 기록','사용자 DB가 아닌 합성 사본에서 복원 후 지침·첨부·권한 일치','S10','5.1.1',status='예정',start='2026-11-21',end='2026-11-24',hours=3)
add('5.1','모바일·키보드·오류 안내 점검','NFR-10,NFR-11','핵심 화면 점검표','요약·보관함·팀·인수인계의 초점·레이블·복귀·표시 확인','S09','4.1.8',status='예정',start='2026-11-21',end='2026-11-24',hours=3,owner='공동')
add('5.1','시연 오류 수정·동일 사례 재검사','NFR-12','결함 목록·재검사 기록','재현한 중대 오류가 남지 않고 수정 전후 근거 기록','S02','5.1.3,5.1.4',status='예정',start='2026-11-25',end='2026-11-27',hours=4)
add('5.1','공개 배포 범위·운영 여부 결정','NFR-04,NFR-09','배포 결정·설정 목록','공개 범위·자료·유료 모드·운영 담당·비용을 명시적으로 결정','S10','4.1.7',status='예정',start='2026-11-20',end='2026-11-20',hours=1,owner='공동')
add('5.1','공개 환경 배포·도메인·수동 확인','NFR-01,NFR-09','실제 서비스 주소·점검 기록','배포 선택 시 HTTPS·쿠키·영구 저장·재시작을 실제 주소에서 확인','S10','5.1.6',status='선택 후속',priority='선택',note='컨테이너 CI 통과를 공개 배포 완료로 쓰지 않음. 비용 발생 전 확인')
add('5.1','불필요한 과거 Streamlit 배포 정리','NFR-09','이전 배포 중단 확인','계정 로그인 후 대상 확인·삭제, 반복 검사 비활성 상태 유지','S11',status='외부 대기',priority='선택',note='이전 사용자 승인 있음. Streamlit 로그인 미확보, 완료 처리하지 않음')
add('5.1','범위 고정·릴리스 후보 시연','공통','릴리스 후보·시연 체크리스트','기능 추가를 멈추고 필수 시연·검사·문서 연결 완료','S02','5.1.5,5.2.2',status='예정',start='2026-11-28',end='2026-12-04',hours=3,owner='공동')

add('5.2','상세 WBS·요구·검증 추적표 검토','공통','상세 일정·기능 분해·마일스톤','작업 ID·요구·선행·근거·완료 기준의 연결을 검토','S01,S02','1.1.3',status='검토 대기',start='2026-11-12',end='2026-11-13',hours=2,owner='공동')
add('5.2','최신 설계서·주간보고 정합성 갱신','공통','최신 설계·보고 판본','v2 기술 검증과 후속 출력 검증, 완료·미완료를 일치시킴','S02','2.1.9,4.2.8',status='예정',start='2026-11-20',end='2026-11-20',hours=2,owner='윤정우')
add('5.2','최종 검증 결과·한계 정리','NFR-08','결과·자료·재현 링크','수동 대비 우위 미확인, 사람 효과 미측정, 한국어 범위 명시','S02','4.2.8,5.1.9',status='예정',start='2026-12-05',end='2026-12-09',hours=3,owner='고차원')
add('5.2','최종 발표·시연·예상 질문 준비','공통','발표 자료·시연 순서·Q&A','문제·기능·방법·검증·한계를 최신 코드와 일치시킴','S02','5.2.3',status='예정',start='2026-12-10',end='2026-12-14',hours=3,owner='공동')
add('5.2','최종 제출본·소스·실행 안내 점검','공통','제출 묶음·실행 README','새 환경 실행·링크·버전·민감 파일 제외·결과 파일 보존 확인','S02','5.2.4',status='예정',start='2026-12-15',end='2026-12-17',hours=2,owner='윤정우')
add('5.2','최종 시연·제출·인계','공통','제출 확인·최종 버전','확정 범위·실행 방법·남은 제한을 공유하고 제출 확인','S12','5.2.5',status='예정',start='2026-12-18',end='2026-12-18',hours=1,owner='공동',note='기존 15주차 일정의 마지막 보고일 기준 제안')

# Product hierarchy is separate from the delivery-work hierarchy above.
FUNCTION_GROUPS = {
 '01': ('F1','계정·접근','회원 계정','3.1.1'),
 '02': ('F2','문서 요약','예시 비교','3.1.2,3.1.3,3.1.4'),
 '03': ('F2','문서 요약','보존·충돌·지침','3.1.5,3.1.6'),
 '04': ('F3','코딩 도움','AI 답변 방식 설정','3.1.7'),
 '05': ('F3','코딩 도움','React 코드 스타일 비교','3.1.9,3.1.10'),
 '06': ('F3','코딩 도움','선택적 예시 비교','3.1.8'),
 '07': ('F4','개인 지침','보관·수정·재사용','3.1.11'),
 '08': ('F5','팀 기준','팀·초대·기준','3.2.1,3.2.2'),
 '09': ('F5','팀 기준','조합·출처·되돌림','3.2.3,3.2.4'),
 '10': ('F6','업무 인수인계','공유·담당·이력','3.2.5,3.2.6,3.2.8'),
 '11': ('F6','업무 인수인계','첨부·파일 권한','3.2.7'),
 '12': ('F4','개인 지침','초안·개선 작업 복구','3.1.12,3.1.14'),
 '13': ('F7','개선·검증 도구','선택적 GEPA','3.1.14,4.2.4'),
 '14': ('F7','개선·검증 도구','답변 확인 도움','3.1.15'),
 '15': ('F7','개선·검증 도구','내보내기·실제 작업 비교','3.1.15'),
 '16': ('F8','템플릿·작업 공간','초안·요청문·버전','3.1.13'),
}


def main():
    ids = {t['id'] for t in tasks}
    assert len(ids) == len(tasks)
    for t in tasks:
        assert set(t['predecessors']) <= ids, t
        assert set(t['sources']) <= SOURCES.keys(), t
        if t['plan_start']:
            assert t['plan_end'] >= t['plan_start']
        if t['status'] == '완료 확인':
            assert t['sources'] and t['evidence_date']
    visiting, done = set(), set()
    by_id = {t['id']: t for t in tasks}
    def visit(tid):
        assert tid not in visiting, f'Cycle at {tid}'
        if tid in done: return
        visiting.add(tid)
        for predecessor in by_id[tid]['predecessors']: visit(predecessor)
        visiting.remove(tid); done.add(tid)
    for tid in ids: visit(tid)
    functions=[]
    for line in (ROOT/'docs/system-design/chapters/01-analysis.md').read_text(encoding='utf-8').splitlines():
        match=re.match(r'\| (FR-(\d+)\.(\d+)) \| ([^|]+) \| ([^|]+) \|',line)
        if not match: continue
        req, major, sub, name, criterion=match.groups()
        fid, subsystem, feature, work = FUNCTION_GROUPS[major]
        if req == 'FR-03.2': criterion='v2: 보존 문장 상한 초과 또는 가용 완전 문장의 최소 분량 부족 시 지침 생성 보류'
        if req == 'FR-03.3': criterion='v2: 충돌별 가능한 분량 확대·축소·재서술·일부 생략 중 명시한 조건만 변경'
        if req == 'FR-02.1': criterion='v2: 언어·분류·현재 원문 확인. 공백 포함 12,000자 초과 입력 보존·거절'
        functions.append(dict(id=f'{fid}.{int(major)}.{sub}',subsystem=subsystem,feature=feature,name=name.strip(),requirement=req,criterion=criterion.strip(),wbs=work))
    assert len(functions) >= 50
    groups=[dict(id=g[0],phase=g[1],name=g[2],original_plan_weeks=g[3],observed_activity_weeks=g[4],owner=g[5]) for g in GROUPS]
    data=dict(version='1.0',cutoff='2026-11-12',report_date='2026-11-13',head='cfd1fe44623b46ca8bf94da059c91e72945de517',
              semester_start='2026-09-11',final_report='2026-12-18',
              weeks=[(date(2026,9,11)+timedelta(weeks=i)).isoformat() for i in range(15)],
              assumptions=['담당은 최신 주간보고의 윤정우·고차원 기준 배정 제안이며 기여 실적이 아니다.',
                           '앞으로의 시작·종료·공수는 일정안이다. 과거 실제 시작·종료·공수는 확인하지 못해 비워 둔다.',
                           '완료 확인은 해당 수용 기준의 산출물·기술 검사 범위다. 사람의 효과·품질 우위·공개 배포 완료를 뜻하지 않는다.',
                           '기존 15주 간트는 학기 계획 틀이며 실제 작업일이 아니다. 11/12는 9주차, 11/13 보고는 10주차다.',
                           '필수 완료는 알려진 조건의 전달·충돌 처리·재사용·기존 코딩 유지·권한·회귀·새 자료 출력 검증·보고다.',
                           '실사용자 평가·공개 배포·과거 Streamlit 정리는 별도 선택/외부 대기로 관리한다. 유료 API는 사용하지 않는다.'],
              groups=groups,tasks=tasks,functions=functions,
              sources=[dict(id=k,title=v[0],path=None if v[1].startswith('https://') else v[1],
                            url=v[1] if v[1].startswith('https://') else BASE+v[1]) for k,v in SOURCES.items()])
    for source in data['sources']:
        if source['path']: assert (ROOT/source['path']).is_file(), source
    HERE.mkdir(parents=True,exist_ok=True)
    (HERE/'wbs.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'tasks':len(tasks),'functions':len(functions),'status':{s:sum(t['status']==s for t in tasks) for s in sorted({t['status'] for t in tasks})},'planned_required_hours':sum(t['estimate_hours'] or 0 for t in tasks if t['priority']=='필수')},ensure_ascii=False))


if __name__=='__main__': main()

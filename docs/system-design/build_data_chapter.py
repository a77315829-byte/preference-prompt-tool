"""Describe current schema using literal DDL in a disposable memory DB only."""
from pathlib import Path
import ast
import json
import sqlite3

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PURPOSE = {
    'users': '계정 식별과 인증용 해시. 원문 비밀번호나 원문 세션 토큰을 보관하지 않는다.',
    'sessions': '로그인 세션 토큰의 해시와 만료. 비교용 메모리 세션과 다른 자료다.',
    'usage': '날짜·호출 종류·주체별 사용 횟수. subject는 문자열이며 users 외래키가 아니다.',
    'teams': '팀 분류·생성자·이름·초대 만료·비공개 여부. 생성자 삭제와 공개 여부를 분리한다.',
    'team_members': '팀 참여와 기존 비교 이력. member_key는 계정/익명 참여 식별을 구분한다.',
    'coding_team_guides': '새 네 항목 코딩 팀의 명시적 기본값·필수 규칙. 기존 React 이력을 변환하지 않는다.',
    'personal_prompts': '계정별 재사용 지침·메모·출처·코딩 설정 스냅샷. 작업 원문 자동 보관 용도가 아니다.',
    'workspace_projects': '업무 지침 프로젝트의 소유자·제목·시점. 내용은 버전과 초안에 분리한다.',
    'workspace_versions': '명시적으로 저장된 프로젝트 스냅샷. 프로젝트 ID와 버전의 복합키.',
    'workspace_members': '프로젝트 단위 viewer/editor 권한. 팀 참여와 별개다.',
    'workspace_drafts': '사용자별 작업 중 사본. 저장 버전과 다르고 같은 사용자·프로젝트에서 갱신한다.',
    'handoffs': '인수인계 현재 본문·작성자·수신자·상태·revision·공유 시작 revision.',
    'handoff_versions': '인수인계 변경 이벤트와 당시 스냅샷. 현재 접근 권한을 별도로 검사한다.',
    'handoff_files': '첨부 원본과 메타데이터. 버전에는 파일 자체 대신 참조 메타데이터를 둔다.',
    'coding_optimization_jobs': '계정별 개선 작업과 만료. 재시작 후 실행 중 작업은 오류로 복구한다.',
    'coding_work_trials': '사용자가 직접 측정한 작업 비교 기록. 자동 생성·실행 성적이 아니다.',
}
MEANING = {
    'id':'식별자', 'username':'대소문자 구분 없이 고유한 계정명', 'password_hash':'scrypt 파라미터·salt·해시',
    'created_at':'생성 시각', 'updated_at':'최근 수정 시각', 'token_hash':'세션 토큰 SHA-256',
    'user_id':'대상 계정', 'owner_id':'소유 계정', 'expires_at':'만료 시각', 'day':'사용량 집계 날짜',
    'kind':'호출 종류', 'subject':'집계 주체 문자열', 'count':'사용 횟수', 'code':'팀 코드',
    'domain_key':'자료 분류', 'created_by':'생성 계정(삭제 시 NULL)', 'name':'표시 이름',
    'invite_until':'초대 만료 epoch', 'protected':'계정 팀 비공개 구분', 'member_key':'참여 식별 키',
    'history_json':'기존 도메인 비교 이력 JSON', 'joined_at':'참여 시각', 'revision':'현재 변경 버전',
    'profile_json':'팀 기본 프로필 JSON', 'rules_json':'필수 규칙 JSON', 'title':'표시 제목',
    'prompt':'재사용 지침 본문', 'note':'선택 설명', 'provenance_json':'조합 출처 스냅샷 JSON',
    'coding_profile_json':'코딩 설정·본문 해시·선택적 개선/팀 근거 JSON', 'project_id':'프로젝트 식별',
    'version':'저장 버전 번호', 'saved_at':'저장 시각', 'label':'버전 표시 이름',
    'project_json':'프로젝트 전체 스냅샷 JSON', 'role':'viewer/editor 권한', 'added_at':'공유 추가 시각',
    'base_version':'초안이 출발한 저장 버전', 'recipient_id':'지정 수신 계정',
    'recipient_from_revision':'수신자 열람이 시작되는 버전', 'body_json':'현재 인수인계 본문 JSON',
    'status':'draft/shared/active/done', 'handoff_id':'인수인계 식별', 'actor_id':'변경한 계정',
    'event':'변경 행동', 'snapshot_json':'당시 인수인계 스냅샷', 'content_type':'제공할 파일 MIME',
    'size':'파일 바이트 수', 'data':'첨부 원본 바이트', 'job_json':'공개 가능한 작업 상태 JSON',
    'record_json':'과제·타이머·결과·근거 JSON',
}
INTRO = '''# 7. 데이터베이스와 데이터 계약 설계

## 7.1 저장소 선택과 생명주기

현재 앱은 SQLite 한 개를 계정·버전·권한·작업 저장의 기준으로 사용한다. 표준 라이브러리 기반이며 별도 DB 서버를 요구하지 않는다. 요청별 연결을 열고 foreign_keys를 활성화하며, 블록 성공 시 커밋하고 예외 시 롤백한다. WAL 모드와 10초 연결 대기 설정이 있으나 대규모 동시 처리 성능을 측정한 것은 아니다.

영구 저장, 세션성 상태, 캐시를 구별한다. personal_prompts·handoffs는 명시적 저장이고, workspace_drafts는 사용자별 작업 사본이다. 브라우저 코딩/인수인계 초안은 sessionStorage와 메모리의 24시간 복구 상태다. 비교 세션은 서버 메모리의 TTL/상한 대상으로 재시작 후 영구 복구를 보장하지 않는다. 모델 응답 캐시는 같은 요청 재호출을 피하는 목적이다.

아래 스키마는 app_db.py의 MIGRATIONS 리터럴을 읽어 빈 메모리 SQLite에서 실행한 결과다. 실제 사용자 DB를 열지 않았다. 14번까지의 migration으로 생성한 16개 업무 테이블이며 sqlite_sequence는 내부 관리 표라 제외한다. PK·FK·기본값은 실제 DDL 기준이며 JSON 안의 ID는 외래키로 그리지 않는다.

## 7.2 계정·팀·지침 데이터 관계

![계정·팀·지침 데이터 관계](../diagrams/19-identity-data.png)

users는 로그인 세션과 개인 자료의 부모다. teams.created_by는 삭제 시 NULL이 되지만 protected가 비공개 구분을 유지한다. team_members는 code와 member_key를 묶어 식별하며 익명 참여에는 user_id가 없을 수 있다. coding_team_guides는 teams와 같은 code를 PK/FK로 사용한다. 개인 지침의 provenance_json은 저장 당시 스냅샷이므로 원본 자료 삭제와 함께 자동 소실시키지 않는다.

## 7.3 업무·개선 데이터 관계

![인수인계·개선·작업 기록 관계](../diagrams/20-work-data.png)

handoffs는 작성 계정 삭제 시 CASCADE되고 수신 계정 삭제 시 recipient_id가 NULL이 된다. 첨부와 버전은 작업에 종속된다. actor_id는 계정 삭제 후 NULL이 될 수 있다. coding_optimization_jobs와 coding_work_trials는 소유 계정에 종속되며 접근 범위를 user ID로 제한한다. 파일이 과거 버전에 있다는 사실은 현재 접근 권한을 대신하지 않는다.

## 7.4 작업 공간 데이터 관계

![프로젝트·권한·버전·초안 관계](../diagrams/21-workspace-data.png)

workspace_projects는 소유자와 목록 정보만 관리한다. versions는 덧붙이는 저장본, drafts는 사용자별 작업 사본이다. members의 role은 viewer/editor CHECK로 제한한다. 저장본 복원과 초안 갱신은 서로 다른 업무 동작이다. 프로젝트와 사용자를 함께 참조하는 복합키를 두어 다른 프로젝트의 권한·초안이 섞이지 않도록 한다.

## 7.5 물리 데이터 사전

NOT NULL은 DDL에 명시된 제약이고 PK 순번은 복합키 내 순서다. SQLite의 table_info에서 PK와 notnull 표시는 별개이므로 이를 하나의 단순 필수값 플래그로 바꾸지 않는다. TEXT에 JSON을 넣는 열은 업무 모듈이 구조를 검증한다. 시간은 표에 표시된 저장형을 따르며 TEXT 시각과 REAL epoch를 혼용할 때 단위를 확인한다.
'''
OUTRO = '''
## 7.6 JSON 스냅샷 계약

| 저장 영역 | 핵심 내용 | 정합성 규칙 |
|---|---|---|
| coding_profile_json | profile, prompt_sha256, 선택적 optimization·team_context | 본문 해시와 분류로 현재 일치 여부 확인 |
| provenance_json | 선택값·출처·원본 버전·조합 연결 | 원본 수정/삭제 후 당시 기록 보존; 없는 이력 추측 금지 |
| handoffs.body_json | purpose, progress, remaining, prompt, references | 목적·진행·남은 일 필수; 경로/링크는 실행 입력 아님 |
| handoff_versions.snapshot_json | 해당 revision의 본문·상태·파일 메타데이터 | 수신자 공유 시작점·현재 권한과 함께 조회 |
| coding_optimization_jobs.job_json | 상태·단계·결과·오류·원본 | owner/내부 단조시각은 공개 사본에서 제외; 만료 관리 |
| coding_work_trials.record_json | 과제·도구·모델·맥락·arms·prompts·active | 두 단계 setup/edit의 측정 여부와 시간을 분리 |
| workspace_versions.project_json | 계약·지침·시험·제안 등 프로젝트 스냅샷 | 저장 버전은 새로 추가, 초안은 별도 |

JSON 필드를 추가할 때는 기존 NULL/구버전 자료를 읽는 경로를 유지한다. 과거 값이 없으면 새 의미를 추론해 채우지 않는다. 특히 예시 비교 v1~v3와 v4, 점수 v1/v2, 기존 React 팀과 coding_profile 팀을 하나의 기록으로 재해석하지 않는다.

## 7.7 업무 입력의 저장 제한

| 자료 | 제한 | 경계 처리 |
|---|---|---|
| 계정명·비밀번호 | 이름 3~30 영문/숫자/_.-, 비밀번호 8~128 | 입력 오류와 인증 실패를 구별 |
| 개인 지침 | 계정당 100개, 제목 100, 본문 20,000, 메모 1,000자 | 초과 저장 거절 |
| 요약 조건 원문 | 공백 포함 1~12,000 코드 포인트, 초점 300자, 보존 문장 최대 8개 | 비교 시작과 조건 확인 모두 초과 시 자르지 않고 거절 |
| 인수인계 본문 | 제목 100, 목적 3,000, 진행·남은 일 각 6,000, 지침 20,000자 | 필수 입력·길이 검증 |
| 인수인계 참고 | 최대 20개, 각 2,048자 | http(s) 또는 파일 경로, 제어문자 거절 |
| 첨부 | 파일 5MiB, 현재 10개, 작업 누적 20MiB | 제외한 과거 파일도 보존량에 포함 |
| 실제 작업 기록 | 계정당 100개, 과제 10,000, 맥락 3,000자 | 타이머 진행 중 삭제 등 잘못된 상태 거절 |

위 제한은 데이터 정책의 현재 구현값이다. 운영 부하 시험으로 도출한 최적값이 아니다. API의 전체 요청 본문 바이트 상한과 업무별 문자 수 상한은 서로 다른 계층이며 함께 적용된다.

## 7.8 migration과 호환성

PRAGMA user_version에 적용 단계를 기록한다. 이미 적용된 DDL을 수정하지 않고 새 migration을 덧붙인다. migration 1은 계정/세션, 2는 프로젝트/버전, 3은 프로젝트 공유/초안, 4는 사용량/팀, 5는 팀 이름, 6은 보관함, 7은 출처, 8은 코딩 설정, 9는 인수인계, 10은 첨부, 11은 개선 작업 복구, 12는 초대 만료, 13은 비공개 유지, 14는 코딩 팀 기준/실제 작업 기록이다.

과거 DB를 최신 코드로 열기 전에 백업을 남기고 migration을 별도 복사본에서 확인한다. DB 스키마가 전진한 뒤 이전 애플리케이션 코드로 돌아가는 것은 자동 롤백이 아니다. 코드와 데이터 호환성을 검토하고 필요하면 함께 백업 시점으로 복원한다. 이번 문서 작성에서는 사용자 DB에 migration을 실행하지 않았다.

## 7.9 트랜잭션·동시성·정리 정책

개수 상한 확인과 삽입, revision 확인과 변경, 현재 상태와 버전 추가는 분리 실행으로 중간 상태를 남기지 않아야 한다. 일부 업무는 BEGIN IMMEDIATE로 쓰기 경쟁을 직렬화한다. SQLite 잠금·타임아웃이 발생하면 성공으로 응답하지 않고 재조회/재시도 경계를 사용자에게 알린다. 모든 변경의 무한 재시도를 제공하는 것은 아니다.

계정 삭제 시 CASCADE와 SET NULL의 차이를 유지한다. 비공개 팀은 생성자 NULL만으로 공개하지 않는다. 개선 작업은 expires_at을 기준으로 조회·정리하고 실행 중 복구는 오류로 남긴다. 보관량 상한은 백업 크기·누적 첨부와 함께 운영에서 관찰해야 한다. 사용량 subject와 JSON 내부 ID에는 SQL 외래키가 없으므로 별도 정책을 검토한다.

## 7.10 백업·복구 수용 기준

SQLite backup API로 일관된 사본을 만들고 공개 정적 경로 밖의 비공개 저장소에 둔다. 첨부 BLOB도 DB 백업에 포함되며 모델 응답 캐시는 별도 파일이다. 복원 연습에서는 사용자 수 같은 집계뿐 아니라 격리된 예시 계정의 로그인·지침·인수인계·첨부 권한·버전 조회를 확인한다.

백업 주기, 보존 기간, 목표 복구 시간과 허용 손실 시간은 운영 주체가 정해야 하며 아직 실측·합의된 SLA로 제시하지 않는다. 문서에 복구 절차가 있다는 사실과 실제 클라우드 복구 시험을 통과했다는 사실은 다르다.
'''

def main():
    evidence=json.loads((HERE/'source-evidence.json').read_text(encoding='utf-8'))
    module=ast.parse((ROOT/'app_db.py').read_text(encoding='utf-8-sig'))
    ddl=next(ast.literal_eval(n.value) for n in module.body if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id=='MIGRATIONS')
    conn=sqlite3.connect(':memory:')
    for script in ddl: conn.executescript(script)
    parts=[INTRO]
    for name in PURPOSE:
        meta=evidence['tables'][name]
        parts.extend([f'\n### {name}\n\n{PURPOSE[name]}\n', '| 열 | 자료형 | 제약·기본값 | 의미 |', '|---|---|---|---|'])
        for col in meta['columns']:
            constraints=[]
            if col['pk']:constraints.append(f"PK {col['pk']}")
            if col['notnull']:constraints.append('NOT NULL')
            if col['default'] is not None:constraints.append('기본 '+str(col['default']))
            parts.append(f"| {col['name']} | {col['type']} | {'; '.join(constraints) or '명시 제약 없음'} | {MEANING.get(col['name'],'업무 값')} |")
        fk=meta['foreign_keys']
        parts.append('\n외래키: '+('; '.join(f"{v['from']} → {v['table']}.{v['to']} / 삭제 {v['on_delete']}" for v in fk) if fk else '없음.')+'\n')
        indexes=[]
        for row in conn.execute(f'PRAGMA index_list("{name}")'):
            columns=[r[2] for r in conn.execute(f'PRAGMA index_info("{row[1]}")')]
            indexes.append(('고유 ' if row[2] else '')+row[1]+'('+', '.join(columns)+')')
        parts.append('인덱스: '+('; '.join(indexes) if indexes else '별도 인덱스 없음.')+'\n')
    parts.append(OUTRO)
    (HERE/'chapters/07-data-design.md').write_text('\n'.join(parts),encoding='utf-8')
    conn.close()
    print('Wrote 16-table data chapter from memory DDL and frozen schema.')

if __name__=='__main__':main()

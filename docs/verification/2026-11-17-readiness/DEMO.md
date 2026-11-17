# 무료 데모 실행·시연 순서

2026-11-17 작성. 목적은 **원하는 요약 조건을 지침으로 저장하고 다음 작업에 재사용하는 제품 흐름**을 보여 주는 것이다. 데모의 준비 예시는 입력 원문에 대한 실제 모델 생성 결과가 아니다. 기능 동작과 프롬프트 출력 평가를 구별해서 설명한다.

## 새 환경 준비

Git에서 시연할 커밋을 체크아웃한 뒤 저장소 루트에서 Python 3.12와 Node 22를 사용한다. 기존 requirements와 lockfile만 설치한다. Python 설치 방식은 OS에 맞춰 선택한다.

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
npm ci --prefix frontend
npm run build --prefix frontend
.venv/Scripts/python.exe -X utf8 docs/verification/2026-11-17-readiness/offline.py server
```

브라우저에서 `http://127.0.0.1:18769`를 연다. 이 시연 서버는 `tmp/readiness-20261117/demo.db`를 사용하며 평소의 `data/app.db`를 열지 않는다. `.env`를 읽지 않고 모델 live 플래그·키를 제거한다. `VERIFY_RUN_DIR`로 저장소 `tmp/` 아래의 새 폴더를 지정하면 별도의 빈 데모로 시작할 수 있다. `VERIFY_PORT`로 포트를 바꿀 수 있다. 서버를 종료하려면 실행 터미널에서 Ctrl+C를 누른다. 이미 실행 중인 서버의 포트를 강제로 종료하지 않는다.

Linux에서는 `python3.12 -m venv .venv`, `.venv/bin/python`을 사용한다. Linux의 깨끗한 설치·빌드·HTTP·재시작·복원 증거는 GitHub의 **Hosted container** 검사에서 확인한다. 팀원 PC마다 설치가 확인됐다는 뜻은 아니다.

## 5~7분 시연 대본

1. 합성 전용 계정을 하나 새로 만든다. 실제 개인 비밀번호나 사용자 원문을 넣지 않는다.
2. **문서 요약 → 영어 요약**을 선택하고 아래 첫 원문을 넣는다. 예시를 비교하고 자동 종료 시점과 미정 항목을 확인한다. 최대 횟수를 채우는 시연으로 설명하지 않는다.
3. 결과의 **이번 원문의 조건 충돌 확인**에서 `짧게 · 1~2문장`, `완전한 원문 문장만 발췌하기`를 고른 뒤 조건 확인을 누른다. 원문 문장 세 개를 모두 고르고 다시 확인한다. 결과가 차단되는 것을 보여 준다.
4. **분량을 늘려 모두 담기**를 명시적으로 선택하고 다시 확인한다. 조정된 분량과 보존 요청을 읽고 `조건을 확인한 요약 방식`이라는 이름으로 이 영역 안에서 저장한다. 아래의 기본 비교 지침과 구분한다.
5. **저장한 지침 열기 → 새 작업에 쓰기**에서 두 번째 원문을 넣는다. `지침 + 새 작업 복사`와 요청문을 확인한다. 기존 원문과 새 원문이 저장된 지침 본문에 들어가지 않는 점을 설명한다. `이 지침으로 AI 실행`은 무료 데모에서 비활성 상태다.
6. **코딩 도움 → AI 답변 방식 설정**에서 TypeScript/React와 설명·주석·구성·출력을 고르고 확인 후 생성한다. 이어 **React 코드 스타일 비교**는 코드 구성·스타일 관리·타입의 별도 세 축임을 보여 준다.
7. 로그아웃하면 비교 중 원문·결과 접근이 해제됨을 보여 준다. 장기 보관한 지침은 로그인 후 다시 찾을 수 있으며 임시 비교 세션과 다르다.

첫 원문(전부 합성):

```text
The launch moved to Friday. Testing remains unfinished. Funding depends on approval.
```

다음 작업 원문(전부 합성):

```text
The library opens on Monday. Training begins on Tuesday. The team will review progress on Thursday.
```

새 원문에서 남길 문장이나 길이 요구가 달라지면 조건 충돌을 다시 확인해야 한다. 보관함이 새 원문의 내용 보존을 자동으로 증명하지 않는다.

## 백업·복원 리허설

자동 리허설은 `rehearse_storage.py`로 실행한다. 임의 이름의 별도 저장소와 합성 계정을 만들고 온라인 백업→재시작→새 저장소 복원을 확인한다. 원본 DB와 운영 파일을 지우지 않는다. 결과만 공유하고 임시 DB·쿠키 상태 파일은 Git에 올리지 않는다.

직접 조작할 때는 이미 존재하지 않는 출력 폴더를 선택한다. 다음은 위 데모 서버의 예다.

```powershell
.venv/Scripts/python.exe scripts/storage_snapshot.py backup --database tmp/readiness-20261117/demo.db --destination tmp/demo-backup-01
.venv/Scripts/python.exe scripts/storage_snapshot.py verify --snapshot tmp/demo-backup-01
.venv/Scripts/python.exe scripts/storage_snapshot.py restore --snapshot tmp/demo-backup-01 --destination tmp/readiness-20261117/restored-01
```

기존 서버를 Ctrl+C로 종료한 뒤 `VERIFY_DB_PATH`를 복원된 `tmp/readiness-20261117/restored-01/data/app.db`의 절대 경로로 설정하고 같은 서버 명령을 실행한다. `VERIFY_DB_PATH`는 `VERIFY_RUN_DIR` 안에 있어야 한다. 운영에서 응답 캐시를 함께 보존하려면 백업 명령의 `--cache`에 해당 캐시 폴더를 명시한다. 캐시를 빼면 유료 모드에서 기존 응답을 다시 생성할 가능성이 있으므로 운영 복구에서는 별도로 점검한다.

## 실패했을 때

| 상황 | 확인·조치 |
|---|---|
| 포트가 사용 중 | 기존 프로세스를 확인하고 다른 `VERIFY_PORT`로 새 서버 실행 |
| 빌드 파일 없음 | 기존 의존성 설치 후 프론트 빌드; Python 서버만 켜지 않기 |
| 만료·권한 거절 | 다른 계정 자료를 요청하지 말고 해당 계정 로그인 또는 새 비교 시작 |
| 복원 대상 이미 존재 | 새 폴더 선택. 기존 운영 DB 위에 덮어쓰지 않기 |
| 해시/무결성 실패 | 이 백업을 사용하지 않고 보관 중인 다른 검증된 스냅샷 선택 |
| 시연 중 외부 서비스 장애 | 데모 모드를 유지하고 준비된 캡처와 자동 검사 결과 사용 |

스냅샷 해시는 손상 탐지용이며 서명·암호화가 아니다. 백업에는 계정 인증 데이터·첨부가 있으므로 공개 문서 폴더에 두지 않는다. 복원 시 메모리 비교 세션은 돌아오지 않으며 저장된 지침과 인수인계만 재사용한다.

# 인터넷에서 사용하는 Microstone

로컬 PC를 켜 두지 않고 React 화면·Python API·개인 보관함·인수인계를 하나의 HTTPS 주소로 사용하기 위한 배포 설정이다.
2026-11-04 현재 배포 코드를 준비하고 로컬 동작을 확인한 단계다. 서버·도메인은 생성하거나 구입하지 않았다.
비용을 우선해 무료 서버의 영구 저장 가능 여부를 검토하며, 아래 Render 설정은 유료 선택지로만 남겨 둔다.
서비스 이름은 임시로 `microstone`을 사용한다. 화면의 이름과 구입할 도메인은 이후 변경할 수 있다.
도메인 자체에 사용자 자료를 저장하는 것은 아니므로, 같은 서버와 저장소에 새 도메인을 연결할 수 있다.
기존 주소로 공유한 링크는 이전 도메인을 유지하거나 리디렉션해야 계속 사용할 수 있다.

## 준비한 구성

| 항목 | 설정 |
|---|---|
| 배포 브랜치 | `microstone` (`master` 병합 없이 배포 가능) |
| 실행 | Docker: Python 3.12 + 빌드된 React + 기존 Node 22/TypeScript 파서 |
| 공개 주소 | 먼저 Render 기본 HTTPS 주소를 발급받고, 이후 구입한 도메인 연결 |
| 서버 | 싱가포르, 0.5 CPU/512MB, 1개 인스턴스의 시작 구성 |
| 저장 | 1GB 영구 디스크의 `/var/data`에 SQLite와 AI 응답 캐시 보관 |
| 자동 배포 | 꺼짐. 새 버전은 확인한 커밋을 수동 배포 |
| AI 호출 | 초기에는 실제 생성·환경별 GEPA 모두 꺼짐. 지침 조립·보관·팀·인수인계는 사용 가능 |
| 계정 | 새 서버에서 가입·로그인. 로컬 계정·DB·예시 자료는 자동 업로드하지 않음 |

[배포 설정을 Render에서 검토하기](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2Fa77315829-byte%2Fpreference-prompt-tool%2Ftree%2Fmicrostone)

이 링크는 계정의 리소스 생성 검토 화면을 연다. 저장소에 설정을 추가하거나 링크를 여는 것만으로
서버·도메인을 구입했다고 설명하지 않는다. Render 계정 로그인/연결과 유료 리소스 총액 확인이 필요하다.

## 비용 확인

서버·영구 디스크, 도메인 연간 등록/갱신, 실제 AI 사용료는 별개다.
작은 서버는 월 $7, 영구 디스크 1GB는 월 $0.25로 기본 합계 월 $7.25다.
추가 사용량·세금·실제 AI·도메인은 별도이며 생성 화면의 금액을 우선한다.
실제 GEPA를 켠 후 메모리와 응답 시간을 측정해 크기를 다시 결정한다. 시작 구성만으로 모든 동시 사용을 보장하지 않는다.

무료 Render 웹 서버는 재시작·휴면 때 로컬 파일이 사라지고 영구 디스크를 붙일 수 없다.
보관함·파일 첨부를 계속 쓰려는 이번 목적에는 유료 서버와 영구 디스크를 사용한다.

- [서버 요금](https://render.com/pricing)
- [무료 서버의 저장·휴면 제한](https://render.com/docs/free)
- [영구 디스크](https://render.com/docs/disks)
- [도메인 연결과 HTTPS](https://render.com/docs/custom-domains)

## 무료 서버를 선택하는 경우

Render 무료 서버는 15분 동안 요청이 없으면 휴면 상태가 되고, 다시 접속할 때 약 1분이 걸린다.
재시작·휴면·재배포 때 로컬 SQLite와 첨부가 사라지므로 현재 구조 그대로 장기 보관 용도로 사용하지 않는다.

Oracle Cloud Always Free처럼 가상서버와 영구 볼륨을 제공하는 상품은 무료 범위에서 현재 구조를 유지할 후보가 된다.
단, 생성할 서버가 남아 있지 않을 수 있고 사용량이 낮은 인스턴스 회수 조건도 있다. 가입 때 카드 확인이 필요하다.
무료 범위·리전·CPU 아키텍처와 디스크를 확인한 뒤 서버를 선택한다. 무료 가상서버는 서버 업데이트·HTTPS·백업을 직접 관리한다.
현재 Dockerfile은 Node 런타임 라이브러리를 아키텍처별로 복사하도록 작성했으나 ARM 빌드를 검증했다고 주장하지 않는다.

무료 VM에서 같은 이미지를 실행하는 예시는 다음과 같다. 이 명령은 로컬 이미지가 준비된 Linux 서버에서 실행하며,
공개 HTTPS 프록시는 별도 설정한다. 아래 포트는 서버 내부에서만 열어 둔다.

```bash
docker volume create microstone-data
docker run -d --restart unless-stopped --name microstone \
  -p 127.0.0.1:8000:8000 -v microstone-data:/var/data \
  -e PPT_LIVE=0 -e PPT_FASTAPI_GEPA_LIVE=0 -e PPT_SPRING_BOOT_GEPA_LIVE=0 \
  -e PPT_WEB_GEPA_LIVE=0 -e PPT_PYTHON_WEB_GEPA_LIVE=0 microstone:local
```

- [Oracle 무료 자원·유휴 회수 조건](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [Oracle 가입·카드 확인](https://www.oracle.com/cloud/free/faq/)

## 서버 생성 후 확인할 흐름

1. `microstone` 브랜치의 `render.yaml`로 배포할 구성과 비용을 확인한다. `master`나 기존 Streamlit 제출본을 선택하지 않는다.
2. `/api/health`가 정상이고 기본 주소에서 시작 화면과 코드 예시가 열리는지 확인한다.
3. 본인 계정을 만들고 지침 저장·재사용, 인수인계와 첨부 파일 열기를 확인한다.
4. 서버를 재시작한 뒤 같은 계정·보관함·첨부 파일이 유지되는지 확인한다.
5. 원하는 도메인을 등록한 뒤 Render에 추가하고, 등록 업체의 DNS를 안내된 값으로 연결한다. Render가 HTTPS 인증서를 관리한다.
6. 새 도메인에서 로그인·저장·팀 초대·인수인계 링크와 파일 권한을 다시 확인한다.

최초 공개 서버는 빈 DB로 시작한다. 로컬 자료를 옮기려면 기존 DB의 백업·개인 자료 범위·대상 저장소를 확인한 뒤 별도로 이전한다.

## 실제 AI와 GEPA 켜기

API 키는 Render의 비공개 환경변수 설정에 직접 입력한다. 채팅·GitHub·브라우저 프론트 변수에 넣지 않는다.
Docker 빌드에는 로컬 `.env`, DB, 캐시, 보고서와 임시 파일을 포함하지 않는다.

- 실제 요약/생성: `PPT_LIVE=1`
- FastAPI: `PPT_FASTAPI_GEPA_LIVE=1`
- Spring Boot: `PPT_SPRING_BOOT_GEPA_LIVE=1`
- JS/TS React·Express·Vue·Next.js, TS NestJS: `PPT_WEB_GEPA_LIVE=1`
- Flask/Django: `PPT_PYTHON_WEB_GEPA_LIVE=1`

Blueprint에는 환경별 스위치를 명시적으로 `0`으로 두었다. `PPT_LIVE`만 바꿔도 이 스위치는 자동으로 켜지지 않는다.
필요한 환경만 켜고, 모델은 [기존 설정 안내](USER_GUIDE.md)를 따른다.
처음에는 서버 전체 생성 세션 20회/일·계정 5회, 최적화 3회/일·계정 1회, 익명 유료 호출 0회로 설정한다.
이는 요청 횟수 제한이며 결제 금액의 상한이 아니다. 실제 모델 제공자의 사용 예산도 별도로 설정한다.

## 데이터 유지와 백업

- DB: `/var/data/data/app.db`. 첨부 원본도 이 DB에 들어간다.
- 응답 캐시: `/app/cache`가 `/var/data/cache`로 연결된다.
- 디스크를 삭제하거나 다른 디스크로 교체하면 기존 자료가 자동 이전되지 않는다.
- 정기 백업에는 SQLite의 `backup()`을 사용하고, 백업은 공개 웹 경로에 두지 않는다.
- 비교 중인 세션과 저장 전 GEPA 작업은 서버 메모리에 있어 재시작 시 사라질 수 있다. 저장 완료된 보관함·인수인계와 구분한다.

Render Shell에서 DB 백업을 만들 때는 다음처럼 실행한다. 생성한 파일은 공개 경로가 아닌 개인 백업 저장소에 별도로 보관한다.

```python
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

backup_dir = Path('/var/data/backups')
backup_dir.mkdir(exist_ok=True)
backup_path = backup_dir / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.db')
with sqlite3.connect('/var/data/data/app.db') as source:
    with sqlite3.connect(backup_path) as target:
        source.backup(target)
```

## 배포 전 검증

`hosting_server.py`는 빌드 디렉터리만 제공하고 API는 기존 구현에 위임한다.
파일 경로 탈출·숨김 파일·소스 맵을 차단하며 공개 요청의 `X-Forwarded-Host`를 Origin 승인 근거로 사용하지 않는다.
로그인 쿠키는 기본으로 `Secure`다. 로컬 HTTP 검사에서만 `PPT_COOKIE_SECURE=0`을 명시한다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_hosting_server.py tests/test_api_server.py -q
npm run build --prefix frontend
```

`.github/workflows/hosting.yml`은 컨테이너를 빌드하고 격리된 볼륨에서 로그인·저장·첨부·두 데모 분류·재시작 후 보존을 검사한다.
JS/TS 평가에 필요한 Node와 TypeScript 파서도 확인한다. 이 검사는 유료 AI를 호출하거나 실제 클라우드 리소스를 만들지 않는다.

배포 구조 근거: [Docker 배포](https://render.com/docs/docker), [Blueprint 설정](https://render.com/docs/blueprint-spec),
[브랜치 지정 배포 링크](https://render.com/docs/deploy-to-render).

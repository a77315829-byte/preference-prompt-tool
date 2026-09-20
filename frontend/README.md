# React UI

React/Vite 기반의 새 UI 영역입니다. 기존 Python 엔진과 Streamlit 화면은
당분간 유지하고, 이 폴더에서 Toss-inspired 랜딩·카테고리 선택·A/B 비교·
프롬프트 결과 화면을 단계적으로 구현합니다.

## 구조

```text
frontend/
  public/                       정적 파일과 이미지
  src/
    app/                        앱 진입점과 전역 화면 상태
    features/
      landing/                  첫 화면과 스크롤 스토리텔링
      category/                 문서 요약 / 코딩 / AWS / 리뷰 / 이메일 선택
      comparison/               A/B 카드와 선택 전환
      prompt-result/            선호 요약과 최종 프롬프트
    shared/
      components/               여러 기능에서 재사용하는 UI
      styles/                   공통 스타일이 생길 때만 사용
```

디자인 값은 처음부터 별도 토큰 파일로 분리하지 않고 각 화면의 CSS에서
직접 관리합니다. 화면 간에 실제 반복이 생길 때만 공통 스타일을 분리합니다.
## 실행

프론트만 실행해도 API가 없으면 로컬 예시로 계속 진행합니다. 기존 Python
엔진의 코딩·문서 요약·리뷰·이메일·AWS 데모까지 연결하려면 터미널을 두 개 열고 다음처럼 실행합니다.

```bash
# 최초 1회: 저장소 루트에서 프론트 의존성 설치
npm run install:frontend

# 터미널 1: 저장소 루트
.venv/bin/python api_server.py

# 터미널 2: 저장소 루트 (frontend/ 안에서 실행해도 됩니다)
npm run dev
```

브라우저에서 `http://localhost:5173`을 열면 됩니다. `npm run dev`가 인식되지
않는 경우에는 `cd frontend && npm run dev`로 직접 실행할 수 있습니다.

Vite가 `/api` 요청을 `127.0.0.1:8000`으로 전달합니다. API가 켜져 있으면
실제 `service.py`의 `start_session`·`submit_choice` 결과를 사용하고, API가
없으면 브라우저 안의 결정적 데모 데이터로 자동 전환합니다.

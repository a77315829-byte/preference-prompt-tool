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
      category/                 문서 요약 / 코딩 도움 선택
      comparison/               A/B 카드와 선택 전환
      prompt-result/            선호 요약과 최종 프롬프트
    shared/
      components/               여러 기능에서 재사용하는 UI
      styles/                   공통 스타일이 생길 때만 사용
```

디자인 값은 처음부터 별도 토큰 파일로 분리하지 않고 각 화면의 CSS에서
직접 관리합니다. 화면 간에 실제 반복이 생길 때만 공통 스타일을 분리합니다.
화면을 먼저 로컬 데모 데이터로 완성한 뒤, 기존 Python 엔진과 연결하는 API
계층을 붙입니다.

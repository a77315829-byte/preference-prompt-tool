# 코딩 AI 브랜치 병합과 전체 점검 (2026-10-13)

## 병합 (PR #4)

`codex/coding-ai-upgrade`(ui/ux 작업 + 코딩 AI 개선 3커밋)를 master 에 합쳤다. ui/ux 가
master 파일을 병합하지 않고 복사해 넣어서 16개 파일이 충돌했다. 충돌난 모든 파일에서
codex 쪽이 master 변경을 이미 담고 있어 그쪽을 택했고, 파일 전체를 비교해 master 에만
있던 기능(동점·되돌리기·언어 선택·팀·내보내기·GEPA 근거 표시)이 남아 있는지 확인했다.

함께 고친 것:
- CI pytest 작업에 Node 22 + `npm ci --prefix frontend` 를 넣었다.
  `tests/test_coding_ai_quality_stage4.py` 가 `frontend/node_modules/.bin/tsc` 를 불러서
  CI 에서는 늘 실패했다.
- `benchmarks/coding_ai_quality/evaluate_trial.py` 가 실행 결과 JSON 을 stdout 에서만 읽는다.
  jsdom 20 이 Node 21+ 에서 punycode 경고를 stderr 에 내는데, stdout + stderr 를 합쳐
  읽어서 동작 검사가 늘 `error` 였다.

## 전체 점검에서 고친 것 (이 문서와 같은 PR)

1. **AWS 실제 조회가 누구에게나 열려 있었다.** `/api/aws/costs` 는 브라우저가 보낸
   `demoMode: false` 하나로 서버 자격 증명의 Cost Explorer 를 불러 계정 비용을 돌려줬다.
   이제 서버가 `PPT_AWS_LIVE=1` 로 켜고, 로그인한 사람만, 하루 상한
   (`PPT_AWS_QUERIES_PER_DAY` 20 / 사람마다 5) 안에서 조회한다. 막히면 데모 데이터와
   이유(`liveError`)를 주고 화면이 그 문장을 보여 준다.
2. **비교 세션이 메모리에서 지워지지 않았다.** 데모 세션은 상한 없이 만들 수 있다. 새 세션을
   만들 때 12시간이 지난 세션과 500개를 넘는 가장 오래된 세션을 지운다
   (`PPT_SESSION_TTL_HOURS`, `PPT_MAX_SESSIONS`). 최적화가 돌고 있는 세션은 남긴다.
3. **절대 규칙 1 위반.** `engine/generator.py` 가 프롬프트에 `"## A/B 공통 기능 계약"` 이
   있으면 출력 상한을 8,192 로 올렸다 - 엔진이 코딩 프롬프트 문구를 안 것이다. 상한을
   `domains/coding.yaml` 의 `max_output_tokens` 로 옮기고, 엔진은 도메인 값이 있으면 쓰고
   없으면 기본값(2,048)을 쓴다. 엔진 문자열에 도메인·축 이름이 나오지 않는지 보는 검사
   (`tests/test_engine_domain_agnostic.py`)도 더했다 - 이름 수준이라 문구 분기는 못 잡는다.
4. Streamlit 앱에서 코딩 후보가 검사를 끝내 통과하지 못하면 "알 수 없는 오류로 모델 호출이
   실패"로 보였다. `describe_api_error` 가 "코드 검사 실패"로 알린다.
5. `checks/summarization_hybrid.py` 의 분류기·캐시 경로가 실행 위치 기준 상대 경로였다.
   저장소 기준으로 바꿨다.
6. 문서: README 의 팀 프롬프트 설명(한 추정기 합산 · 메모리 저장 · 개인용 문구 → 한 사람
   한 표 · DB 저장 · 팀용 문구), 깨져 보이던 환경변수 표, 서버가 꺼졌을 때의 화면 설명,
   출력 상한 문장, `docs/presentation_guide.md` 의 상한·저장 설명, CLAUDE.md 의 테스트 수와
   코딩 모델.

## 남긴 것

- 코딩 기본 모델(`gpt-6-luna`, 실패 시 `gpt-6.1-sol`)의 청구 비용과 라운드당 대기 시간 측정.
- 새 개발용 의존성(`typescript`, `jsdom`, `@types/react`, `@types/react-dom`) - 실행 검증 전용.
- 연구용 에이전트(`agents/domain_onboarding.py` 등)의 LLM 호출 캐시 (절대 규칙 2). 서비스
  경로는 전부 캐시를 거친다.
- 브랜치 정리: `submission` 은 `submission-final` 태그 위에 10/9 커밋(8f1770a)이 올라가 있어
  Streamlit 공개 배포가 태그와 다른 코드로 돈다. `main` 은 9/21 커밋 하나와 `node_modules`
  가 들어간 정리 안 된 브랜치다. 둘 다 팀이 정한다.

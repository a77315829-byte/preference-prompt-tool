# 2026-11-04 실행 검사 수정이 예전 수치에 미친 영향

32977ae 에서 실행 검사의 진입 파일 고르기를 고쳤다(실행용 `App.tsx`·`index.tsx`·`main.tsx` 껍데기가 다른 후보를
import 하면 후보에서 뺀다). 같은 검사(`evaluate_trial.evaluate_candidate`)로 예전에 낸 수치가 바뀌는지 확인했다.

- 바뀔 수 있는 경우는 예전 코드가 "Missing entry file" 을 내던 출력뿐이다. 저장된 평가 파일(data/, 커밋하지 않음)
  어디에도 그 오류가 없었다. 단계별 평가(`evaluate_trial.evaluate`)는 그 오류를 잡지 않아, 났다면 실행이 멈췄을 것이다.
- 그래도 직접 대조했다: `python -m benchmarks.coding_ai_quality.rescore_saved --reviewed` (API 호출 0회). 단계별 평가 16개
  (stage4~6, 보류 v1~v4, 서비스 경로, 상품 검색·가입·할 일, 비용 고정본, 3단계)와 페르소나 평가 2개, **18개 모두
  typecheck·build·behavior·checks·equivalent(페르소나는 passed) 가 같았다.** 달라진 것은 나중에 추가된 `entry` 필드뿐이다.
- 따라서 `benchmarks/coding_ai_quality/stage*-results.md`, 10월 코딩 검증 문서, README 의 코딩 수치는 정정할 것이 없다.
- 영향을 받은 것은 이 수정 전에 실행한 1·2차 사전등록 비교(`ppc_holdout_behavior`, `ppc2_holdout_behavior`)뿐이고,
  재채점본과 해석 메모를 이미 남겼다(확증 판정은 바꾸지 않는다). 3차(`rc_*`)는 수정 뒤에 실행했다.

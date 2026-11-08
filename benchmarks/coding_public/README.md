# 무료 공개 코딩 검증: RACE + EvalPlus

이 모듈은 기존 서비스·GEPA·`engine/`와 분리되어 있다. 모델 API 클라이언트가 없고
`.env`도 읽지 않는다. 프로젝트 Python 의존성을 추가하지 않는다.
공개 자료 다운로드와 로컬 Docker 실행만 사용한다.

2026-11-09 결과: 준비 예시 **480/480**, HumanEval+ 정답 **164/164**,
MBPP+ NoExtreme 정답은 기본 **378/378**, base+plus **377/378**.
의도적 오답 **542개 모두 실패로 검출**했다.
MBPP/255의 추가 입력 1건은 대용량 결과(길이 77인 조합 1,663,740개)를 요구하며
정답 대조에서도 실패했다. 공식 결과에는 예외 원인이 없어 메모리/시간 영향 가능성만 기록한다.
따라서 **기본 실행은 대조가 모두 통과한 HumanEval**이며 MBPP 확대는 이 실패를 해결한 뒤 한다.
이 수치는 평가기 대조 결과이고 우리 프롬프트 성능이 아니다.
상세 기록: `docs/history/2026-11-09_free_coding_validation.md`,
집계: `benchmarks/coding_public/results/2026-11-09.json`.

## 검증 범위

| 단계 | 실제로 확인하는 것 | 확인하지 못하는 것 |
|---|---|---|
| RACE 정적 함수 | 함수 이름·길이·주석·함수 개수 조건 | 주석의 유용성, 역할 분리의 적절성, 개인 만족도 |
| 준비된 Python 예시 | 24개 선택지의 계산 동등성/수정 결과, 형식 차이 | 모델이 새 과제에서도 선호를 따르는지 |
| EvalPlus 공개 데이터 점검 | 542개 과제의 해시·참조 코드 문법·함수 진입점·입력 수 | 아직 실행하지 않은 코드의 정확도 |
| EvalPlus 정답/오답 대조 | 공식 평가기가 정답을 통과시키고 의도적 오류를 잡는지 | 우리 지침 또는 특정 모델의 성능 |
| 미실행 요청 명세 | 같은 과제에 대한 일반 지침 + 주석/구조 2×2 조합 | 실제 생성 결과, 사용자 선호·수정 시간 |

**이 결과로 8~10회 선택의 충분성이나 개인화 효과를 주장하지 않는다.**
준비 예시는 주문·대여·인쇄 3맥락이지만 계산 구조가 유사하다.
24개 선택지/480개 숫자 입력 검사를 독립적인 사용자 480명이나 다양한 과제 480개로 세지 않는다.

## 재현

프로젝트 루트에서 기존 Python 3.12 환경으로 실행한다.

```powershell
# 최초 1회: 공개 파일만 다운로드하고 SHA-256 확인
./.venv/Scripts/python.exe -m benchmarks.coding_public.run --fetch

# 이후 완전 오프라인: 캐시 해시·문법·RACE·준비 예시·견적 재검사
./.venv/Scripts/python.exe -m benchmarks.coding_public.run
```

원본과 생성 파일은 Git에서 제외한 `data/public-code-benchmarks/`에 둔다.
`prepared/offline-report.json`은 상세 결과이고,
`prepared/requests.NOT_EXECUTED.jsonl`은 **호출하지 않은 요청 계획**이다.
정답 코드·추가 테스트 입력은 모델 요청에 넣지 않는다.
캐시가 없으면 `--fetch` 없이 네트워크로 보충하지 않으며 해시가 다르면 중단한다.

EvalPlus 실행은 다음처럼 별도 진행한다. 이미지를 받는 단계도 모델 API 비용은 없다.
공식 이미지의 압축 다운로드 크기는 약 1.1GB이다.

```powershell
docker pull ganler/evalplus@sha256:26b118098bef281fe8dfe999bf05f1d5b45374b4e6c00161ec0f30592aef4740
./.venv/Scripts/python.exe -m benchmarks.coding_public.evaluate_docker --execute-controls

# 선택: MBPP NoExtreme까지 재현. 현재 MBPP/255 추가 검사 실패로 종료 코드 1을 반환한다.
./.venv/Scripts/python.exe -m benchmarks.coding_public.evaluate_docker --execute-controls --dataset both
```

이 이미지의 발행자 태그는 `v0.3.1`이지만 **실제 설치 패키지는 `0.4.0.dev2`,
Python은 3.11.10**이다. 태그를 패키지 버전으로 보고하지 않는다.
이미지 digest와 실행 중 확인한 실제 버전을 기록한다. 호스트 Python은 3.12를 유지한다.
발행자 코드의 `EVALPLUS_TIMEOUT_PER_TASK` 환경변수 처리는 문자열/숫자 비교 오류가 있어
이 변수를 설정하지 않고 공식 기본값을 사용한다.

또한 이미지에는 HumanEval/32의 성공 기록을 빠뜨리는 버그가 남아 있다.
기본 실행은 저자의 [공식 수정 커밋](https://github.com/evalplus/evalplus/commit/6eb1e199c2e370518e7bf3e8eee6322c2b23c89c)
파일을 읽기 전용으로 연결한다. **원본과 성공 기록 2줄만 다른지 해시로 검증**하며
문제·정답·허용 오차·테스트는 바꾸지 않는다. 이미지 자체와 호스트 패키지는 수정하지 않는다.
`--original-evaluator`로 수정 전 결과를 재현할 수 있다.

기본 실행 데이터는 **HumanEval+ 전체**이고, `--dataset mbpp` 또는 `--dataset both`는
**MBPP+ NoExtreme**을 추가로 사용한다.
이 PC의 Docker 메모리는 약 3.7GiB였고 MBPP+ 전체 및 NoExtreme의 일괄 실행은
3GiB 한도에서 종료 코드 137로 중단됐다. 정답 캐시 하나만 약 0.8GB였으므로
**MBPP 과제를 50개씩 나눠 실행**하고 최종적으로 378개 전체의 누락·중복을 검사해 합친다.
분할 전후의 각 과제 필드와 입력은 그대로 유지하며 배치별 해시를 기록한다.
NoExtreme은 발행자의 공식 변형으로 378개 과제·1,174개 기본 입력은 그대로이고,
추가 입력은 39,841개에서 39,636개로 줄어든다. 7개 과제에서 극단 입력 205개를 제외한다.
따라서 이 실행 결과를 **MBPP+ 전체 입력의 성능으로 표시하면 안 된다**.
과제 지문·정답·다른 필드가 동일한지는 오프라인 대조한다.
`--full-mbpp`는 극단 입력까지 포함하는 별도 실행 옵션이며 더 많은 메모리가 필요할 수 있다.

컨테이너는 네트워크 없음, 읽기 전용 루트, 일반 사용자, CPU 2개·메모리 3GB·프로세스 128개
제한으로 실행한다. 공개 데이터 사본과 이번 실행 결과 폴더만 연결한다.
동시 평가 작업은 1개, BLAS/OMP 스레드는 1개이며 정답 캐시는 RAM 임시 공간 대신 결과 폴더에 둔다.
컨테이너의 `controls.py`는 공식 `evaluate()` 함수를 호출한다. 과제 묶음마다
공식 데이터 로더의 override 경로만 바꾸며 모델/생성 인자는 받지 않는다.
RAM이 작은 PC에서 큰 정답 객체를 프로세스 큐로 복제하지 않도록 **외부 작업 스케줄러는
ThreadPoolExecutor 1개**를 사용한다. 공식 `untrusted_check()`가 각 답안을 별도 프로세스에서
실행하는 동작과 정답 판정은 유지한다. 이 실행 방식 차이는 결과 메타데이터에 기록하며
공식 이미지의 기본 실행 방식 그대로 돌렸다고 표현하지 않는다.
프로젝트 전체, 사용자 DB, `.env`, Docker 소켓은 연결하지 않는다.
전체 실행은 30분 제한이고, 제한을 넘으면 해당 검사 컨테이너만 종료한다.
검사 과정에서 모델·생성 옵션을 전달하지 않는다.

각 실행의 `evalplus-runs/<실행 ID>/`에 다음을 남긴다.

- `execution.json`: 이미지·패키지 버전·데이터 해시·명령
- `execution.log`: 공식 평가기의 원본 로그
- `*_eval_results.json`: 공식 과제별 정답/오답 대조 결과(배치별)
- `summary.json`: 전체 과제 누락 여부와 base / base+plus 집계

정답 대조는 원본 `prompt + canonical_solution`, 오답 대조는 같은 진입점에서 항상
`AssertionError`를 내는 함수다. **둘 다 AI 모델 출력이 아니다.**
샘플이 과제당 정확히 하나이므로 pass@1은 통과 과제의 비율이다.
기본 테스트와 추가 테스트를 모두 통과해야 plus 통과로 센다.
오답 대조의 시간 초과는 정상적인 오류 검출로 인정하지 않는다.

## 자료와 지표의 정확한 의미

- [RACE 공식 저장소](https://github.com/jszheng21/RACE),
  [논문](https://arxiv.org/abs/2407.11470),
  고정 커밋 `3b8ee591abd5febd8ae8ec17c7b9907949c5e1d5`.
  `race/codeeval/metrics_utils.py`의 **정적 함수 7개를 동작 변경 없이 분리**하고 끝 공백만 정리했다.
  원본과 함수 AST를 대조하고 Apache-2.0 라이선스를 `LICENSE-RACE`에 보존한다.
  전체 RACE benchmark 점수나 논문의 correctness/readability/maintainability/efficiency
  종합 점수를 재현했다고 주장하지 않는다. ClassEval·LeetCode·효율 측정은 범위 밖이다.
- [EvalPlus 공식 저장소](https://github.com/evalplus/evalplus),
  [실행 안내](https://github.com/evalplus/evalplus/blob/v0.3.1/docs/cli.md).
  [HumanEval+ v0.1.10](https://github.com/evalplus/humanevalplus_release/releases/tag/v0.1.10) 164개와
  [MBPP+ v0.2.0](https://github.com/evalplus/mbppplus_release/releases/tag/v0.2.0) 378개를 사용한다.
  MBPP는 전체·NoExtreme 원본을 모두 확보하며 실행 결과에는 사용한 변형을 기록한다.
  다운로드 링크와 SHA-256은 `run.py`의 `ASSETS`에 고정했다.
  원본 데이터는 재배포하지 않고 발행자의 공개 배포처에서 내려받는다.

RACE의 `comment_by_line(threshold=0.75)`는 작성자가 정한 주석 비율 조건이다.
한 줄 계산에 주석 하나가 붙은 예시는 이를 통과하지만 그것만으로 주석이 유익하다는 뜻은 아니다.
`comment_by_function`은 docstring 조건이며 모듈 docstring만으로 통과하는 경로도 있다.
우리 예시의 인라인 주석을 docstring과 혼동하지 않는다.
`module_count`는 파일/모듈 개수가 아니라 `FunctionDef` 개수의 정확한 일치 여부다.
1개와 2개 어느 쪽이 더 좋은지 보편적 순위를 부여하지 않는다.
비동기 함수 등은 원본 추출 함수의 범위 한계가 있다.

부분 수정 예시는 원래 함수의 반환문에 먼저 적용한 뒤 검사한다.
준비된 예시의 숫자 검사는 import/exec/eval 없이 정수·덧셈·곱셈·정의된 함수 호출만 처리하는
작은 AST 해석기로 한다. EvalPlus 실행 검사와 구분한다.

공개 MBPP+ 원본의 `Mbpp/793.plus_input`은 빈 배열이 아닌 빈 객체 `{}`다.
이 고정 버전의 예외를 그대로 보존하고 추가 입력이 없는 과제로 명시한다.
Python 3.12가 발견한 원본 문자열 escape 경고도 보고서에 기록하며 원본을 임의 수정하지 않는다.

## 이후 유료 실험 계획 — 아직 실행하지 않음

코드로 조립한 고정 설정을 사용해 주석 2종 × 구조 2종과 일반 지침을 비교한다.
설명은 `brief`, 출력은 `complete`로 고정한다. 이는 **직접 설정 모드의 프롬프트 조립 효과**를
검사하는 계획이며 실제 사용자의 8~10회 선택·선호 추정 과정을 검증하는 실험은 아니다.
16개 전체 설정 조합의 조립 가능 여부는 별도로 오프라인 확인한다.

| 단계 | 과제 수 | 조건 | 생성 호출 수 |
|---|---:|---:|---:|
| 연결 확인용 파일럿 | HumanEval 10 + MBPP 10 | 5 | 100 |
| HumanEval 전체 | 164 | 5 | 820 |
| 두 데이터셋 전체 | 542 | 5 | 2,710 |

파일럿 과제는 task ID에 고정 접두어를 붙인 SHA-256 정렬로 선택한다.
성공률을 보고 골라내지 않는다. 파일럿은 파이프라인 점검이며 효과의 결론용 표본이 아니다.
파일럿으로 지침을 수정하면 해당 과제를 최종 독립 평가에서 빼고 다시 사전 등록해야 한다.

견적은 2026-11-09 확인한 Standard 요금, 캐시 할인 없음, 호출당 출력 1,024토큰 또는
4,096토큰을 가정한다. **입력 토큰 수는 실제 tokenizer 계측이 아니라 UTF-8 바이트 수의
1.1배 + 요청당 128토큰으로 잡은 넉넉한 예산 값**이다. 확정 청구 상한은 아니다.
추론 토큰도 출력 예산 안에 포함해야 하며 재시도·GEPA·도구·세금·환전 수수료는 제외한다.

| 범위 | GPT-6 Luna 예상 / 출력 예산을 다 쓸 때 | GPT-6.1 Sol 예상 / 출력 예산을 다 쓸 때 |
|---|---:|---:|
| 100회 파일럿 | $0.0739 / $0.2275 | $1.4770 / $4.5490 |
| 820회 HumanEval 전체 | $0.6204 / $1.8799 | $12.4080 / $37.5984 |
| 2,710회 전체 | $1.9870 / $6.1495 | $39.7391 / $122.9903 |

근거: [Luna 공식 요금](https://developers.openai.com/api/docs/models/gpt-6-luna)
(입력 $0.10 / 출력 $0.50, 백만 토큰당),
[Sol 공식 요금](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
(입력 $2 / 출력 $10, 백만 토큰당).
재실행 시 보고서의 재계산 값을 우선하고 요금을 다시 확인한다.
**유료 생성 실행기는 이번에 만들지 않았으며, 실행 전 비용과 범위를 사용자에게 제시해야 한다.**

실제 효과를 보려면 조건별 답변을 생성해 기능 정확도와 스타일 조건을 각각 측정하고,
같은 정확도 조건에서 실제 사용자 선호·수정 시간을 따로 비교해야 한다.
8/10회와 더 많은 선택 횟수를 비교하는 사용자 실험도 별도 필요하다.

## 검사

```powershell
$testTemp = Join-Path (Get-Location) ('data/pytest-public-' + [guid]::NewGuid().ToString('N'))
./.venv/Scripts/python.exe -m pytest tests/test_coding_public.py tests/test_coding_elicitation.py -q --basetemp $testTemp
```

데이터가 없는 환경에서는 다운로드가 필요한 통합 테스트 1개만 건너뛴다.
나머지 테스트는 네트워크·Docker·모델 API 없이 실행한다.

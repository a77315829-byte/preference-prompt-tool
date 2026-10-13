# Coding Style Pairs v1 — 코딩 스타일 비교 자극 데이터셋

## 무엇을 만든 것인가

사용자가 같은 기능의 코드 두 개 중 선호하는 것을 고르는 **소규모 합성
비교 데이터셋**입니다. 프로젝트용으로 Codex가 새로 작성했으며 외부 코드
데이터셋을 복사하거나 사용자 응답을 수집해서 만든 자료가 아닙니다.
사람이 검수하기 전 초안이며, 스타일 라벨은 생성 규칙에 따른 라벨입니다.
정답 코드의 우열, 실제 사용자 선호, 개인화 성능을 의미하지 않습니다.

- 원본: `experiments/coding_dataset.py`의 과제와 결정적 변환 규칙
- 배포 파일: [v1.json](v1.json) — 코드 전체, 과제, 스타일 라벨, 비교 쌍 포함
- 외부 데이터 출처: 없음. AI 작성 코드 및 템플릿 변환
- 사용자 선호 라벨: 없음 (`winner: null`). 가상의 참가자·응답·성공률 없음
- 개인정보: 없음
- 대상: TypeScript + React 함수 컴포넌트
- 별도 데이터셋 라이선스: 아직 지정하지 않음. 외부 재배포 전 팀에서 확정

## 규모와 분리

| 용도 | 과제 | 스타일별 코드 | 비교 쌍 |
|---|---|---:|---:|
| 선호 선택 `elicitation` | 카운터, 설명 접기/펼치기, 완료 필터, 체크리스트 | 32 | 48 |
| 미사용 과제 검증 `holdout` | 소개/사용법 화면 선택기, 텍스트 미리보기 | 16 | 24 |
| 합계 | **6개 과제** | **48개** | **72쌍** |

과제마다 3개 이진 축의 모든 조합인 8가지 코드를 만듭니다. 한 축만 다른
쌍은 과제당 12개입니다(축 3개 × 나머지 축의 배경 조합 4개).
72쌍은 독립적인 과제 72개도, 사용자 응답 72개도 아닙니다.
같은 과제의 변형은 반드시 같은 split에 두며 holdout을 선호 추정이나
프롬프트 조정에 쓰면 안 됩니다. holdout 결과를 보고 생성 규칙을 반복
수정한다면 새 과제를 마련해야 합니다. 모든 과제가 작은 useState 컴포넌트라는
공통 템플릿을 사용하므로 이 분리는 넓은 실무 과제에 대한 일반화를 보장하지 않습니다.

## 세 가지 축과 통제 조건

| 축 | 한쪽 | 다른 쪽 |
|---|---|---|
| `code_structure` | `compact`: 한 파일 | `separated`: 화면·로직·스타일 세 파일 |
| `style_management` | `direct`: 스타일 값 직접 작성 | `theme`: 공통 theme에서 값 참조 |
| `type_detail` | `inferred`: 상태·함수의 추론 활용 | `explicit`: 모델·상태·함수 타입 명시 |

비교 쌍마다 축 하나만 바뀌고 나머지 두 축은 같습니다. 기능, 초기 상태,
문구, 상호작용, 접근성 속성, 최종 색상·간격은 유지합니다.
스타일 축을 바꿔도 파일 수가 늘어나지 않도록 theme은 스타일 선언과
같은 파일에 둡니다. CSSProperties는 두 타입 스타일 모두에 사용합니다.
추론 중심은 '타입을 전혀 쓰지 않는 코드'가 아닙니다.
이 초기 과제에는 Props 경계 타입 비교가 없으므로 타입 축 전체를 대표하지 않습니다.

라벨과 생성 규칙을 동일 코드가 관리하므로 라벨 일치만으로 독립적인
정확도 평가를 할 수 없습니다. 팀원이 파일 분리의 자연스러움, 테마
사용의 적절성, 타입 표기, 코드 가독성 등을 별도로 검수해야 합니다.

## 데이터 필드

- `tasks`: 요구사항, split, 컴포넌트명, 초기 상태, 기대 동작 trace
- `variants`: 과제 ID, 스타일 조합 `profile`, 파일명→코드 `files`
- `pairs`: 비교 축 `axis`, variant ID `a`/`b`, 미수집 선호 `winner: null`
- `human_review_status`: `pending` — 자동 검사 통과와 인간 검수는 별개

A/B 방향은 각 과제·축에서 2:2로 균형을 맞췄으며 항상 같은 결과가
나옵니다. 사용자 화면에는 `axis`, `profile`, 내부 ID, '권장' 표시를
노출하지 않아 선택을 유도하지 않도록 합니다. 전체 자료는 개발·검수용이며
사용자 화면에서 72쌍 전체를 노출하는 용도가 아닙니다.

## 실행과 검증

저장소 루트에서, 기존 의존성이 설치된 환경을 사용합니다.

```sh
python -m experiments.coding_dataset
python -m pytest tests/test_coding_dataset.py -q
npm install --prefix benchmarks/coding_style
node benchmarks/coding_style/verify.mjs
```

첫 명령은 동일한 JSON을 표준 출력으로 생성합니다. API나 네트워크를
사용하지 않으며 파일을 덮어쓰지 않습니다.

JS 검사 도구는 이 폴더의 별도 package.json을 사용하며 UI 프로젝트에 의존하지 않습니다.
이미 설치된 도구를 재사용하려면 `node benchmarks/coding_style/verify.mjs /경로/frontend`처럼
esbuild와 react가 설치된 package.json의 디렉터리를 전달할 수 있습니다.
의존성 최초 설치는 네트워크가 필요하지만 데이터 생성과 검사는 API 없이 실행됩니다.

Python 검사는 개수·ID·과제 분리·단일 축 차이·A/B 균형·배포 파일의
재현성, 기존 Estimator와 시스템 프롬프트 연결을 확인합니다. 여기서
사용하는 가상 선택은 테스트 입력일 뿐 연구 데이터에 저장하지 않습니다.

JS 검사는 기존 esbuild로 48개 TS/TSX 코드를 파싱하고 작은 useState
실행기를 통해 버튼/입력 이벤트를 호출합니다. 기대 상태, 초기 표시,
8개 스타일 사이의 화면 트리와 동작 기록 일치를 검사합니다.
**실제 브라우저 렌더링, React 수명주기 전체, TypeScript 의미적 타입 검사,
접근성 검사, 실제 사용자 평가는 별도로 필요합니다.**

## 기존 엔진에 넣는 방법

현재 `service.py`의 코딩 데모는 `demos/coding_dataset.py`를 통해 이 자료를
사용합니다. 선택용 4개 과제만 순환하며 평가용 과제는 노출하지 않습니다.
같은 입력과 선택 이력이면 예시와 순서가 재현됩니다(세션/쌍 ID 제외).
입력은 과제 순서를 정할 뿐 임의의 개발 요청을 구현하지는 않습니다.
실제 API 모드와 다른 도메인의 생성기는 그대로 유지합니다.
아래는 별도 실험에 사용하는 최소 예시입니다. 사용자 기록의 영구 저장은
구현하지 않았습니다. 평가 절차와 기록 양식은 `docs/coding-user-evaluation.md`를 참고합니다.

```python
import json
from pathlib import Path
from engine.domain_loader import load_domain
from engine.estimator import Comparison, Estimator
from optimize.run_gepa import build_seed_prompt

dataset = json.loads(Path("benchmarks/coding_style/v1.json").read_text())
variants = {row["id"]: row for row in dataset["variants"]}
pair = next(row for row in dataset["pairs"] if row["split"] == "elicitation")
a, b = variants[pair["a"]], variants[pair["b"]]
# 요구사항과 a["files"], b["files"]를 보여주고 실제 응답을 받습니다.
# 응답이 없으면 update를 호출하지 않습니다. 자동 승자를 만들지 않습니다.
estimator = Estimator(load_domain("domains/coding.yaml"))
winner = input("선호하는 코드(a/b), 판단하기 어려우면 Enter: ").strip().lower()
if winner in {"a", "b"}:
    estimator.update(Comparison(a["profile"], b["profile"], winner))
    print(build_seed_prompt(load_domain("domains/coding.yaml"), estimator))
```

이는 한 쌍의 입출력 예시입니다. 한 번 선택한 것만으로 세 축의 선호가
확정됐다고 해석하면 안 됩니다.

## 사용자 평가 계획 — 아직 수행하지 않음

1. 팀원이 48개 코드와 요구사항을 검수하고 오류를 수정한 뒤 버전을 고정합니다.
2. 참가자에게 연구 목적과 선택 기록 저장 범위를 알리고 동의를 받습니다.
3. 선호 선택용 과제만으로 각 축을 최소 2번 비교합니다. '비슷함/판단 어려움'도
   허용하고 이를 강제로 a/b로 변환하지 않습니다. 전체 48쌍을 강요하지 않습니다.
4. 같은 선택용 과제에서 나머지 축의 배경 조합을 바꾼 반복 문항으로
   선택이 일관적인지 확인합니다. 위치 순서는 참가자 간 교차 배치합니다.
5. holdout 요구사항에 기본 프롬프트와 개인화 프롬프트를 각각 적용합니다.
   실제 API 실험에서는 모델·버전·생성 설정을 맞추고 출력과 조건을 기록합니다.
   이 합성 코드 두 개를 보여주는 실험과 실제 LLM 생성 효과 검증은 구분합니다.
6. 컴파일·요구사항 충족 여부를 먼저 보고, 생성 조건을 가린 상태에서
   선호/동률/판단 불가를 받습니다. 같은 참가자의 여러 응답을 독립된
   참가자처럼 세지 말고 참가자 수와 응답 수를 따로 보고합니다.
7. 축별 반영률, 기능 성공률, 개인화 선호율, 동률·판단 불가율을 분리합니다.
   API 없이 확인할 수 있는 것은 데이터와 엔진 동작이며 LLM 개선 효과는 아닙니다.

## 발표용 설명

> TypeScript/React 코드의 구조, 스타일 관리, 타입 표기 차이를 비교하기 위해
> 프로젝트용 합성 데이터셋을 제작했습니다. 6개 기능 과제에서 스타일 조합
> 48개와 한 기준씩 달라지는 비교 쌍 72개를 구성했습니다. 사용자의 실제 선호는
> 앞으로 수집하며, 선택에 쓰지 않은 과제로 개인화 효과를 검증할 예정입니다.

이 자료는 기능 검증과 초기 사용자 실험을 위한 **파일럿**입니다.
대규모 벤치마크나 실사용자 선호 데이터셋, 학습 완료 모델로 소개하지 않습니다.

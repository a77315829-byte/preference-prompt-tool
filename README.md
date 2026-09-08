# 선호 기반 프롬프트 자동 생성 도구

사용자가 결과물 두 개 중 마음에 드는 쪽을 8~10회 고르면, 그 선택 이력에서
사용자의 암묵적 선호를 추정하고, 이를 평가 함수로 변환해 자동 프롬프트
최적화기([GEPA](https://arxiv.org/abs/2507.19457))에 전달한다. 최종
산출물은 그 사용자 전용 시스템 프롬프트 텍스트 한 덩어리다.

핵심 전환: 기존 개인화 수단은 "당신이 원하는 것을 서술하세요"에서
출발한다. 본 도구는 "이 둘 중 나은 쪽을 고르세요"에서 출발한다.

**이 프로젝트가 하지 않는 것**
- 언어 모델을 학습하거나 파인튜닝하지 않는다. 상용 API를 부품으로 호출만 한다.
- "범용적으로 좋은 프롬프트"를 목표로 하지 않는다. 개인 적합도가 목표다.

프로젝트의 상세한 설계 결정과 그 이유(무엇을 왜 바꿨는지 포함)는
[`CLAUDE.md`](CLAUDE.md)에 기록되어 있다.

---

## 결과 요약

**선택 기반 개인화는 작동한다. 다만 모든 취향 축이 측정 가능한 것은
아니며, 어떤 축이 그러한지를 실험으로 구분했다.** 아래는 성공(개인화·
수렴·확장성·피드백 효과)과 한계(specificity 축, 에이전트의 축 발견)를
같은 비중으로 보고한다 - 유리한 지표만 골라 보고하지 않는다.

### 성공

#### 1. GEPA 피드백 풍부도 어블레이션 — 가장 인과관계가 깨끗한 결과

`engine/metric_builder.py`가 만드는 축별 자연어 피드백("길이 위반: 6문장
(목표 2문장 이하)...")이 GEPA 성찰에 실제로 도움이 되는지 검증했다
(`experiments/feedback_richness_ablation.py`). **점수 계산 함수는 완전히
동일하게 두고**, GEPA에게 보이는 피드백 텍스트만 rich(축별 위반 내역) vs
terse(점수만)로 바꿔 같은 호출 예산(40회) 안에서 도달하는 검증 점수를
비교했다.

![피드백 풍부도 어블레이션](experiments/results/feedback_richness_ablation.png)

**rich 0.98 vs terse 0.44.** rich는 8회 만에 급격히 수렴해 그 수준을
유지하는 반면, terse는 40회 내내 정체된다. 다른 변수 없이 피드백 형식
하나만 바꿔서 나온 차이라 인과관계가 가장 깨끗하고, "우리는 축을
명시적으로 갖고 있어서 구조화된 피드백을 줄 수 있고, 범용 최적화 도구는
못 하는 부분"이라는 이 프로젝트의 기여 주장에 대한 유일한 직접 증거다.

재현: `python -m experiments.feedback_richness_ablation`

#### 2. 개인화 효과: 비교군 A · B · D

각 조건의 산출물이 페르소나(MACSum 데이터의 실제 속성 조합)의 진짜 선호와
얼마나 일치하는지 두 가지 지표로 채점 (5개 문서 평균).

- **checks_score**: `checks/summarization.py` 기반 - **D의 최적화 목표와
  동일한 함수이므로 D에 유리하게 기울어 있다.** 이 지표 하나만 보고하면
  순환 논증이 된다.
- **independent_score (ROUGE-L)**: 최적화에 전혀 쓰이지 않은 별도
  알고리즘(LCS 기반)으로 MACSum 사람 작성 정답 요약과 직접 비교
  (`experiments/independent_grader.py`).

| 조건 | checks_score (최적화 목표와 동일 계열) | ROUGE-L (독립) |
|---|---|---|
| A - 프롬프트 없이 기본 호출 | 0.600 ± 0.224 | 0.101 ± 0.055 |
| B - 사용자가 직접 쓴 일반적인 지침 | 0.668 ± 0.240 | 0.168 ± 0.060 |
| D - 본 도구 (8회 비교 → 자동 조립된 프롬프트) | 0.996 ± 0.010 | 0.207 ± 0.057 |

![비교군별 결과](experiments/results/baseline_comparison.png)

checks_score는 D의 최적화 목표와 동일 계열의 함수이므로 D에 유리하다.
이를 보완하기 위해 최적화에 전혀 쓰이지 않은 ROUGE-L로 재채점했고,
**절대값은 크게 낮아지지만(0.996 → 0.207) A·B 대비 우위는 유지된다**
(checks 기준 B 대비 +49%p, ROUGE-L 기준 +23%p). 절대값이 낮아지는 걸
감추지 않고 두 지표를 나란히 보고한다 - 이게 0.996만 내세우는 것보다
방어 가능한 주장이다.

재현: `python -m experiments.compare_baselines`

#### 3. 쌍 선택 알고리즘 비교: 무작위 vs 순차 질의 vs 불확실도 기반

실제 API 호출로 생성한 후보를 실제 MACSum 답안지 기준(`checks/`)으로
채점하는 오라클을 오간 선택 루프를 8~10회 돌려, 숨겨진 페르소나의 축별
선호(length, extractiveness)를 얼마나 잘/빨리 복원하는지 비교
(5문서 × 5시드 평균).

![수렴 곡선](experiments/results/convergence.png)

- **무작위**: 10라운드까지도 1.3/2축 정체, 완전복원 32%
- **축 순차 질의**: 1.8/2축, 완전복원 80%
- **불확실도 기반**: 8~9라운드에 2.0/2축 완전 도달, 완전복원 80%

재현: `python -m experiments.run_all` → `python -m experiments.plots`

#### 4. 확장성 검증: 도메인 + 언어

`domains/email.yaml` + `checks/email.py`만 추가하고 `engine/` 코드는 한
줄도 고치지 않고 완전히 다른 도메인(이메일 초안, 축 3개: 길이·격식·구조)이
동작함을 확인했다 (`tests/test_extensibility.py`). `engine/`의 코드에는 도메인
특정 단어가 등장하지 않는다 - 축 이름·값·프롬프트 문구·검사 함수는 전부
`domains/*.yaml`에서 읽는다.

**언어 이식성도 같은 방식으로 검증**: `domains/summarization_ko.yaml` +
`checks/summarization_ko.py`(Kiwi 형태소 분석기로 조사·어미를 제거하고
비교)만 추가해 한국어 요약 도메인도 `engine/` 무수정으로 동작함을 확인
(`tests/test_korean_extensibility.py`). 다만 한국어는 MACSum 같은 사람 주석
답안지가 없어 정량 복원율은 내지 않고, 파이프라인 완주와 검사 함수
스팟 체크로 범위를 제한했다 - short+fully 조합은 원문과 형태소 겹침
94%, long+normal 조합은 40%로 명확히 갈렸다.

---

### 한계 — 모든 축이 측정 가능하지는 않다

#### 5. specificity 축: 다섯 가지 방법 전부 실패

규칙 기반(정규식), 언어학적 도구(spaCy NER), 학습형 분류기(TF-IDF+
로지스틱회귀), 소형 LLM, 대형 LLM - **총 다섯 가지 방법으로 측정을
시도했으나 전부 우연 수준에 머물렀다.** 하나 해보고 포기한 게 아니라
성격이 다른 다섯 접근을 다 시도했다는 게 핵심이다.

| 계층 | 균형정확도 (요약문만) | 균형정확도 (원문 포함) |
|---|---|---|
| 정규식 | 판별력 없음 (6주차) | - |
| spaCy NER | 판별력 없음 (6주차) | - |
| 학습형 분류기 (TF-IDF+로지스틱회귀) | 0.500 (우연) | - |
| 소형 LLM | 0.525 | 0.558 |
| 대형 LLM | 0.464 | 0.514 |

이는 구현 미비가 아니라 **해당 축이 이 데이터에서 표면적으로 판별 가능한
형태로 존재하지 않음을 시사한다.** 다만 라우팅 임계값 스윕 자체는
재사용 가능한 결과를 냈다: 확신도 0.85에서 정확도가 최고점을 찍고, 대형
모델에 전부 맡기면(임계값 1.0) 오히려 정확도가 떨어지며 비용만 5배가 된다.

![하이브리드 라우팅 비용-정확도 곡선](experiments/results/hybrid_routing_curve.png)

재현: `python -m experiments.train_specificity_classifier` →
`python -m experiments.hybrid_routing_eval`

#### 6. 도메인 온보딩 에이전트 (MVP): 안전한 발견은 성공, 사람과는 다른 축을 찾음

사람이 `domains/*.yaml` + `checks/*.py`를 손으로 쓰는 대신, **라벨 없는**
원문+결과물 예시만 보고 에이전트가 축을 제안하고, 검사 코드를 직접 짜서
실제 데이터에 돌려 판별력을 재고, 안 되면 재시도하거나 버리는 루프
(`agents/`). 실행 결과에 따라 재시도할지 포기할지가 갈리고 반복 횟수를
미리 정할 수 없어 워크플로우가 아니라 에이전트다.

**안전장치는 독립적인 성과다.** 에이전트가 코드를 생성·실행하는
시스템에서는 안전장치 설계와 실제 공격 시뮬레이션이 필수인데, 6가지
공격 사례(os 접근, 무한 루프, `__builtins__` 유출, 클래스 계층 우회,
`getattr` 우회, 정상 코드 대조군)로 검증했다. AST 정적 검증(import
전면 금지, 던더 패턴 전체 차단 - 개별 이름 나열 대신 `().__class__.
__base__.__subclasses__()` 류의 우회 경로 자체를 구조적으로 막음) +
별도 프로세스 격리·타임아웃 2단 방어. 처음엔 `__builtins__`를 이름으로
직접 접근하는 우회를 놓쳤다가 던더 패턴 전체 차단으로 막았다.

**MACSum 평가**: 라벨 없이 문서 6개(문서당 결과물 5~7개)를 주자
conciseness·formality·sentence_complexity·focus_on_entities 4개 축을
제안했고, 전부 실제 판별력 기준을 통과해 살아남았다 - specificity 같은
판별 불가능한 축은 제안도 채택도 하지 않았다.

이 축들이 "사람이 고른 축을 다른 이름으로 찾은 것"인지 "정말 다른
것을 찾은 것"인지는 이름 비교만으로는 알 수 없어서, 에이전트가 만든
검사 함수와 사람이 만든 검사 함수(`checks/summarization.py`의 문장 수·
bigram 겹침)를 **같은 텍스트 36개에 돌려 피어슨 상관을 쟀다**
(`agents/correlate_with_human_axes.py`):

| 사람 축 | 가장 가까운 에이전트 축 | 상관계수 |
|---|---|---|
| length (문장 수) | formality | r = -0.45 |
| extractiveness (bigram 겹침) | focus_on_entities | r = 0.26 |

전부 "같은 축"으로 볼 임계값(\|r\| ≥ 0.7)에 크게 못 미친다 - **명명이
다른 게 아니라 정말 다른 축을 찾은 것으로 정량 확인됐다.** length와
가장 가까운 것도 conciseness(직관적 예상)가 아니라 formality였고 그마저
약한 음의 상관이다.

**결론**: "라벨 없이도 실제 판별력 있는 축을 안전하게 찾고 나쁜 축은
스스로 거른다"는 핵심 루프는 작동한다 - 이건 사람이 만든 것과 독립적인
성과다. 다만 사람이 고른 축과 같은 것을 재발견하지는 못했다. 축 분해가
유일하지 않을 수 있다는 뜻으로 읽을 수도 있지만, 상관분석까지 마친
이상 "다른 이름의 성공"이라고 포장하지 않고 "다른 것을 찾았다"로
정직하게 보고한다.

재현: `python -m agents.evaluate_domain_onboarding` →
`python -m agents.correlate_with_human_axes`

### 진행 중 발견한 주요 함정

개발 과정에서 겉보기엔 그럴듯하지만 결과를 왜곡시키는 문제를 몇 차례
발견하고 고쳤다 (자세한 경위는 `CLAUDE.md` 참고).

- **specificity(구체성) 축 제외**: 정규식은 물론 spaCy NER로 측정해도
  MACSum 데이터에서 판별력이 없었다. 코드로 재현 가능하게 잴 수 없는
  축은 애초에 넣지 않는다는 원칙에 따라 제외했다 (4축 → 3축).
- **출력 언어 불일치**: 시스템 프롬프트가 한국어라 축조합에 따라 출력
  언어가 한국어/영어로 들쭉날쭉했다. MACSum 원문·정답이 전부 영어라
  겹침 기반 검사들이 전부 왜곡되고 있었다. 출력 언어를 명시 고정해 해결.
- **페르소나 오라클 재설계**: 처음엔 "정답 요약과의 단어 겹침"으로
  페르소나의 선택을 대행했는데, 원문을 그대로 베낀 후보가 정답 요약과
  우연히 어휘가 더 겹쳐 엉뚱한 축으로 수렴하는 문제가 있었다. 정답
  텍스트 대신 검증된 `checks/` 함수로 실제 축값을 직접 재는 방식으로
  교체하자 5문서 평균 완전복원율이 0~8% → 80%로 뛰었다.

### 발표 서사

> 선택 기반 개인화는 작동한다. 다만 모든 취향 축이 측정 가능한 것은
> 아니며, 우리는 어떤 축이 그러한지를 실험으로 구분했다.

성공(개인화·수렴·이식성·피드백 효과)과 한계(specificity·에이전트의 축
발견)를 나란히 놓고, 한계에서 무엇을 알게 됐는지를 말하는 구성이다.
"우리 도구가 항상 이긴다"가 아니라 "어디까지 되고 어디부터 안 되는지를
직접 측정했다"는 게 이 프로젝트가 실제로 보여줄 수 있는 것이다.

피할 것: 산출물이 "범용적으로 더 좋은 프롬프트"라는 주장 - 목표는 개인
적합도이며, 타인에게 안 맞는 게 정상이다. 그리고 순환 논증으로 보이는
단일 지표(0.996) 단독 보고.

---

## 아키텍처

```
domains/*.yaml      축 정의 · 프롬프트 문구 · 검사함수 이름 (도메인별)
checks/*.py         축별 검사 함수 (도메인 의존)
engine/             도메인을 모르는 코어 - domains/*.yaml만 바꾸면 새 도메인
  domain_loader.py    YAML 로드·검증
  generator.py        축조합 → 프롬프트 조립 → API 호출 → 캐싱
  selector.py         다음에 보여줄 쌍 선택 (무작위/순차/불확실도)
  estimator.py        선택 이력 → 축별 선호 + 확신도 추정 (Bradley-Terry)
  metric_builder.py   추정된 선호 → GEPA용 평가 함수(점수+자연어 피드백) 조립
optimize/run_gepa.py  위 metric을 GEPA의 Evaluator로 감싸 최적화 실행
experiments/         MACSum 페르소나 기반 실험·집계·시각화
agents/              도메인 온보딩 에이전트 (engine/domains/checks와 분리된 별도 패키지)
tests/               각 부품·엔드투엔드 검증 스크립트
scripts/             일회성 탐색 스크립트 (예: MACSum 데이터 훑어보기)
app.py               Streamlit UI (원문 입력 → 8회 비교 → 개인화 프롬프트)
```

`engine/`이 아는 것은 "축이 N개 있고 각 축에 값이 M개 있다"까지다. 실제
검사 로직(문장 수, 어휘 겹침 등)은 전부 `checks/`와 `domains/*.yaml`에
있다 - 이게 확장성 주장의 실체다.

---

## 시작하기

```bash
python -m venv .venv                 # Python 3.12 (3.13/3.14는 패키지 호환성 문제로 비권장)
.venv\Scripts\activate                # Windows
pip install -r requirements.txt

git clone --depth 1 https://github.com/psunlpgroup/MACSum.git data/macsum

cp .env.example .env                  # OPENAI_API_KEY 채워넣기
```

### 웹 UI로 사용해보기

```bash
streamlit run app.py
```

원문을 붙여넣고 8회 비교를 마치면, 그 선호로 GEPA가 최적화한 개인 전용
요약 프롬프트를 보여준다.

### 실험 재현

```bash
python -m experiments.run_all              # 알고리즘 3종 수렴 곡선 데이터
python -m experiments.compare_baselines     # 비교군 A/B/D
python -m experiments.plots                 # 위 결과를 그래프로
```

### 새 도메인 추가하기

`domains/<이름>.yaml`과 `checks/<이름>.py`만 작성하면 된다.
`domains/email.yaml` / `checks/email.py`를 템플릿으로 참고. `engine/`
코드는 건드릴 필요가 없다.

---

## 스택

Python 3.12 · [dspy](https://github.com/stanfordnlp/dspy) ·
[gepa](https://github.com/gepa-ai/gepa) · [litellm](https://github.com/BerriAI/litellm) ·
streamlit · pandas · matplotlib · pyyaml · python-dotenv · pytest

## 참고

- MACSum: Controllable Summarization with Mixed Attributes (Zhang et al., TACL 2023)
- GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning (Agrawal et al., ICLR 2026)

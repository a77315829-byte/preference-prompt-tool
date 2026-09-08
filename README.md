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

### 1. 개인화 효과: 비교군 A · B · D

각 조건의 산출물이 페르소나(MACSum 데이터의 실제 속성 조합)의 진짜 선호와
얼마나 일치하는지 두 가지 지표로 채점 (5개 문서 평균).

- **checks_score**: `checks/summarization.py` 기반 - D의 프롬프트를 최적화할 때
  쓴 것과 같은 계열의 함수. D가 이기는 게 부분적으로 보장돼 있다는 지적을
  받을 수 있어서, 아래 독립 지표를 같이 본다.
- **independent_score (ROUGE-L)**: 최적화에 전혀 관여하지 않은 별도 알고리즘
  (LCS 기반)으로 MACSum 사람 작성 정답 요약과 직접 비교. `experiments/independent_grader.py`.

| 조건 | checks_score | ROUGE-L (독립) |
|---|---|---|
| A - 프롬프트 없이 기본 호출 | 0.600 ± 0.224 | 0.101 ± 0.055 |
| B - 사용자가 직접 쓴 일반적인 지침 | 0.668 ± 0.240 | 0.168 ± 0.060 |
| **D - 본 도구 (8회 비교 → 자동 조립된 프롬프트)** | **0.996 ± 0.010** | **0.207 ± 0.057** |

![비교군별 결과](experiments/results/baseline_comparison.png)

독립 지표에서도 D가 A·B를 앞서지만, 격차는 checks_score만큼 압도적이지
않다 (checks 기준 +49%p vs B, ROUGE-L 기준 +23%p) - 이게 더 정직하고
방어 가능한 수치라고 판단해 낮은 쪽도 그대로 병기한다.

재현: `python -m experiments.compare_baselines`

### 2. 쌍 선택 알고리즘 비교: 무작위 vs 순차 질의 vs 불확실도 기반

실제 API 호출로 생성한 후보를 실제 MACSum 답안지 기준(`checks/`)으로
채점하는 오라클을 오간 선택 루프를 8~10회 돌려, 숨겨진 페르소나의 축별
선호(length, extractiveness)를 얼마나 잘/빨리 복원하는지 비교
(5문서 × 5시드 평균).

![수렴 곡선](experiments/results/convergence.png)

- **무작위**: 10라운드까지도 1.3/2축 정체, 완전복원 32%
- **축 순차 질의**: 1.8/2축, 완전복원 80%
- **불확실도 기반**: 8~9라운드에 2.0/2축 완전 도달, 완전복원 80%

재현: `python -m experiments.run_all` → `python -m experiments.plots`

### 3. 확장성 검증

`domains/email.yaml` + `checks/email.py`만 추가하고 `engine/` 코드는 한
줄도 고치지 않고 완전히 다른 도메인(이메일 초안, 축 3개: 길이·격식·구조)이
동작함을 확인했다 (`test_extensibility.py`). `engine/`의 코드에는 도메인
특정 단어가 등장하지 않는다 - 축 이름·값·프롬프트 문구·검사 함수는 전부
`domains/*.yaml`에서 읽는다.

**언어 이식성도 같은 방식으로 검증**: `domains/summarization_ko.yaml` +
`checks/summarization_ko.py`(Kiwi 형태소 분석기로 조사·어미를 제거하고
비교)만 추가해 한국어 요약 도메인도 `engine/` 무수정으로 동작함을 확인
(`test_korean_extensibility.py`). 다만 한국어는 MACSum 같은 사람 주석
답안지가 없어 정량 복원율은 내지 않고, 파이프라인 완주와 검사 함수
스팟 체크로 범위를 제한했다 - short+fully 조합은 원문과 형태소 겹침
94%, long+normal 조합은 40%로 명확히 갈렸다.

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

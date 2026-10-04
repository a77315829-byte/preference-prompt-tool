# Ollama 실험 검토 후 보완 — 2026-10-04

대상은 master `898fdb9`의 Qwen 2.5 7B 실험과 붙여넣은 실험 기록이다.
기존 30개 사례 CSV·JSON과 관문 JSON은 변경하지 않았다. 새로운 모델 실험도 실행하지 않았다.

## 발표·보고서에서 고친 주장

| 항목 | 검토 후 표현 |
|---|---|
| D 대 공정한 B+ | 18승 12패, ROUGE-L 평균차 +0.0047, 양측 부호검정 p=0.3616. 유의한 우위 미확인 |
| 동등성 | 동등성·비열등성을 검정하지 않았으므로 같은 품질이라고 결론낼 수 없음 |
| D 대 A | 25승 5패, p=0.0003. 부 비교이며 주 비교의 기준 미달을 대체하지 않음 |
| 사용자 노력 | B+는 정답 선호를 코드로 조립한 지침. 시간·수정·부담을 측정한 사람 실험은 아직 없음 |
| 평가 범위 | 길이값별 10개, 추출성 정답은 모두 normal. high·fully 정답 복원과 균형 정확도 미검증 |
| 완전복원 | 기존 CSV에서 6/30=20%를 재계산 가능 |
| 축별 복원·동점 | 길이 25/30, normal 복원 7/30, 동점 86/240은 캐시 진단 보고값. 기존 CSV만으로 검증 불가 |
| 낮은 추출성 복원 원인 | 모델의 지시 준수, bigram 검사, 동점 처리 등이 후보. 원인 분리 실험 전에는 가설 |
| 비용 | 관문 108회 + 본 비교 316회 = 424회, 기록된 API 청구 비용 $0. 전력·장비·시간 미측정 |

실행 전 기준은 역사 기록으로 유지하고 `length_v2_preregistration.md`의 결과 부분에 해석 정정을
남겼다. p≥0.05를 동등성 증거로 쓸 수 없다는 점은 [Lakens의 동등성 검정 설명](https://pubmed.ncbi.nlm.nih.gov/28736600/)과 같다.
ROUGE-L은 참고 요약과의 텍스트 겹침 지표이며 사람 만족도나 사실성 측정은 아니다.

## 코드에서 고친 것

- 두 실험의 기본 출력은 `experiments/results/runs/<UTC 시각·실행 ID>/`이다. `--n 2`를
  돌려도 커밋된 30개 결과를 덮지 않는다. 이 실행 폴더는 Git에서 제외했다.
- `--output-dir`을 명시해도 결과나 실행 설정이 있으면 모델 호출 전에 중단한다.
  교체는 같은 옵션에 `--overwrite`까지 지정했을 때만 가능하다.
- JSON·CSV는 같은 폴더의 임시 파일을 완성한 뒤 교체한다. 저장 실패 시 기존 파일을 보존한다.
  CSV와 JSON 두 파일이 하나의 트랜잭션으로 교체되지는 않으므로 중단 후에는 검증 명령으로 대조한다.
- 실행 설정·상태는 `.run.json`에 남긴다. 본 비교는 모델·도메인·데이터 분할 해시·시드·조건·
  동점 정책을 기록한다. 오류로 끝나도 실패 상태와 수집된 비용/호출 수를 남기고 콜백을 복원한다.
- 후속 CSV는 `learned_length`, `learned_extractiveness`, `oracle_ties`, `oracle_comparisons`를
  저장한다. 요약 JSON은 축별 복원 수와 주 비교의 판정도 기록한다.
- 후속 관문 JSON은 문서 ID와 조건별 개별 출력 비율을 저장한다. 중앙값과 관문을 다시 계산할 수 있다.
- 과거의 동점 A 우선 정책(`legacy-a`)을 기본으로 보존했다. `record-tie`는 명시적으로 켜는
  후속 실험이며 과거 결과를 수정하거나 그 재현으로 표시하지 않는다.

## 기존 결과 검증 — 모델 호출 없음

프로젝트 루트에서 실행한다. 의존성은 기존 `requirements-dev.txt`를 사용하며 새 패키지는 추가하지 않았다.

```powershell
python -m experiments.validate_heldout_results `
  --csv experiments/results/heldout_comparison_summarization_v3_qwen2.5-7b.csv `
  --summary experiments/results/heldout_comparison_summarization_v3_qwen2.5-7b.json `
  --gate experiments/results/length_v3_compliance_qwen2.5-7b.json

python -m pytest tests/test_experiment_result_integrity.py tests/test_heldout_comparison.py -q
```

검증은 조건 누락·중복, 문서 중복, 비정상 수치, 학습률, 지표 평균, 모든 페어드 승·패·동점·
평균차·p값과 관문 판정을 대조한다. 기존 관문은 개별 비율이 없으므로 저장된 중앙값을 기준으로
판정만 검증한다. 검증 통과는 기록 간 일관성을 뜻하며 모델 결과의 재생성이나 연구 결론의 입증은 아니다.

이번 보완 후 `python -m pytest -m "not api" -p no:cacheprovider -q`는 **706 통과,
2 건너뜀, API 대상 16 제외**로 끝났다. 기존 5개 홀드아웃 CSV/JSON 집계, 변조 탐지,
출력 충돌 중단, 짧은 실행의 원본 보존, 축별·동점 기록, 저장 실패와 콜백 복원을 포함한다.
실행 전 5단계 기준이 그대로인지와 기존 결과 파일에 변경이 없는지도 확인했다.

## 다음 실험 실행 — 실행 전 기준을 먼저 고정

아래 명령은 실제 모델을 호출한다. 이번 보완 작업에서 실행하지 않았다.

```powershell
python -m experiments.length_v3_compliance --model ollama/qwen2.5:7b
python -m experiments.heldout_comparison --n 30 --domain domains/summarization_v3.yaml --model ollama/qwen2.5:7b --fair-bplus
```

모두 새 폴더에 저장한다. 출력 위치를 정하려면 `--output-dir experiments/results/runs/my-run`처럼
지정한다. 캐시를 재사용하므로 과거 호출과 같은 조건의 응답이 포함될 수 있다. `model_calls`는
새 실제 호출 수이고 요청된 비교/생성 수와 같지 않을 수 있다. 비용 상한은 페르소나 사이에서
확인하는 기존 방식이므로 페르소나 하나를 처리하는 동안 넘을 수 있다.

동점을 기록하는 후속 비교는 위 본 실험 명령에 `--tie-policy record-tie`를 붙여 별도로 저장한다.
기본 정책과 동점 정책을 같은 사례·모델·시드에서 비교하되, 관찰 후 유리한 정책만 선택하지 않는다.
다음 단계는 (1) 후보의 길이·추출성 지시 준수 분리 측정, (2) 동점 정책 비교, (3) 추출성 정답이
고르게 있는 별도 평가, (4) 품질 기준과 부담 측정을 사전 고정한 사람 실험 순서가 적절하다.
topic이 있는 사례를 추가하면 요약 대상 범위와 길이 분모도 새로 정의해야 한다.

## 앱의 호출을 모두 로컬 모델로 설정할 때

본 비교 실험은 GEPA를 사용하지 않았다. Qwen에서 GEPA·작업 공간 제안의 품질·속도를 검증한
결과도 아니다. API 서버에는 후보 생성, GEPA 성찰/다듬기, 작업 공간 제안의 세 모델 설정이 있다.

Ollama에서 해당 모델을 준비하고 실행한 뒤, 서버를 시작할 PowerShell에서 모두 지정한다.

```powershell
$env:PPT_MODEL = 'ollama/qwen2.5:7b'
$env:PPT_REFLECTION_MODEL = 'ollama/qwen2.5:7b'
$env:PPT_SUGGEST_MODEL = 'ollama/qwen2.5:7b'
$env:PPT_LIVE = '1'
python api_server.py
```

`PPT_MODEL`만 바꾸면 다른 경로는 기본 클라우드 모델을 사용할 수 있다. 서버 시작 뒤 설정을
바꿨다면 다시 시작해야 한다. 이 설정은 API 서버의 세 경로에 해당하며 별도 실험 CLI는 각자의
`--model`/설정을 확인한다. 앱의 v3 요약 도메인 연결과 원문별 목표 길이 재계산은 별도 구현 과제다.

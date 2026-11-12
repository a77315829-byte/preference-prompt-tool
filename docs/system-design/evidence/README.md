# 분석·설계서의 검증 근거

[통합 분석·설계서](../README.md)의 수치를 확인하기 위한 기록이다. 유료 모델 API는 호출하지 않았고 Codex 사용량은 소비됐다. 사람의 선호·만족도·수정 시간은 측정하지 않았다.

## 문서 요약

- [조건 충돌 수정 비교 집계](summary-contract-scores.json): 새 원문 9개에서 수동·현재·수정본 모두 조건 9/9, 핵심 명제 25/27. 두 독립 검토자 일치.
- [조건 충돌 비교 감사](summary-contract-audit.json): 평가 범위·예외·판정 근거.
- [실제 GEPA 선택 결과](summary-gepa-result.json): 개선 6개·후보 선택 6개·최종 9개를 분리한 탐색에서 기존 지침 유지. 최종 생성의 우위나 필수 실행 근거가 아니다.

원문 데이터셋과 다른 프로젝트의 첨부 PDF는 이 문서 공간에 재게시하지 않는다.

## 코딩 답변 방식 4항목

- [전체 방법·결과](coding_react_current/README.md)
- [분리 집계](coding_react_current/results/2026-11-12/scores.json)
- [첫 답변 묶음](coding_react_current/results/2026-11-12/blind_packet.json)
- [타입·동작·조건 감사](coding_react_current/results/2026-11-12/evidence_audit.json)

새 합성 과제 8개×3방식의 첫 답변 24개. 타입·동작은 모두 통과, 네 목표 조건은 일반 0/8·수동 8/8·제품 8/8이었다. 일반 요청에는 선호를 주지 않았다. 수동과 제품의 같은 관측 점수를 통계적 동등성으로 표현하지 않는다.

## React 스타일 3축

- [전체 방법·결과](react_style_current/README.md)
- [분리 집계](react_style_current/results/2026-11-12/scores.json)
- [독립 검토·예외 감사](react_style_current/results/2026-11-12/evidence_audit.json)
- [최종 검사 확인](react_style_current/results/2026-11-12/validation.json)

새 합성 과제 8개×3방식의 첫 응답 24개를 그대로 실행했다. 세 방식 모두 strict 타입 8/8, ReactDOM/JSDOM 동작 56/56을 통과했고 세 목표 조건 모두 일치는 일반 1/8·수동 8/8·제품 8/8이었다. 두 검토자의 축별 72개 판정 쌍 중 1개 차이를 보존했으며 세 축 동시 점수에는 영향이 없다. 4항목 결과와 합산하지 않는다. 영어 최종 지침과 동일한 필수 타입 공통 계약의 한계를 전체 보고서에 명시했다.

## 보존과 재현 범위

`coding_react_current/` 등 실험 디렉터리는 원본 `benchmarks/`의 파일 내용을 유지한 **열람용 스냅샷**이다. 내부 스크립트의 저장소 루트 계산과 기존 해시 경로는 원본 배치를 기준으로 하므로 복사한 폴더에서 바로 실행하는 배포 패키지가 아니다. 실행 재현에는 원래 저장소 배치, 해당 소스 해시, 설치된 의존성이 필요하다.

`publication-manifest.json`은 게시 경로와 원본 경로 및 SHA-256을 연결한다. 실험의 기존 해시 파일은 바꾸지 않는다. 설계서의 `source-evidence.json`에는 현재 로컬 코드와 원격 브랜치의 차이를 명시했다. 이 공간 게시로 앱 코드의 병합·배포가 완료되었다고 해석하지 않는다.

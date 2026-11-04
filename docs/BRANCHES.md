# 브랜치 현황과 정리 제안

2026-11-04 `git fetch origin` 후의 원격 이력과 GitHub PR 상태를 확인했다.
개발 브랜치는 GitHub에서 `microstone`으로 이름이 변경됐으며 로컬 이름·추적 대상도 맞췄다.
이전 이름은 `codex/summary-coding-no-aws`다. 이름 변경 때 PR #12는 닫혔고 그 검토 이력은 보존한다.
아래 목록은 최초 점검의 원격 12개 기준이며, 이후 삭제·이름 변경은 삭제 전에 다시 확인한다.
`origin/HEAD`는 기본 브랜치를 가리키는 별칭이라 개수에 넣지 않는다.

## 정리해도 되는 후보

아래 원격 브랜치의 마지막 커밋은 모두 `origin/master`의 조상이다.
따라서 확인 시점에는 해당 브랜치에만 남은 커밋이 없다.

| 원격 브랜치 | 확인 근거 | 제안 |
|---|---|---|
| `claude/busy-franklin-sew5ji` | master에 병합됨. 최근 PR #10을 포함한 관련 PR 모두 병합 | 삭제 후보 |
| `claude/great-allen-94dzwn` | master에 병합됨, PR #3 병합 | 삭제 후보 |
| `claude/modest-tesla-znfrja` | master에 병합됨, PR #1·#2 병합 | 삭제 후보 |
| `fix/audit-2026-09-27` | 마지막 커밋 `b87da53`이 master에 포함됨 | 삭제 후보 |
| `fix/windows-tests-guide` | master에 병합됨, PR #6 병합 | 삭제 후보 |
| `ui/ux` | 원격 마지막 커밋 `5981c04`까지 master에 포함됨 | 원격과 로컬 모두 삭제 후보 |

로컬 `ui/ux`는 원격보다 4개 커밋 뒤에 있지만, 로컬·원격의 커밋 모두 master에 포함되어 있다.
다른 팀원이 이 이름을 새 작업에 계속 사용하는지는 실제 삭제 직전에 확인한다.

## 유지할 브랜치

| 브랜치 | 이유 |
|---|---|
| `master` | 현재 기본·통합 브랜치 |
| `microstone` | 현재 개발·배포 준비 브랜치. [변경 비교](https://github.com/a77315829-byte/preference-prompt-tool/compare/master...microstone), 이전 PR #12 이력 유지 |
| `codex/coding-ai-upgrade` | [PR #11](https://github.com/a77315829-byte/preference-prompt-tool/pull/11) 열림. master에 없는 커밋 10개와 프롬프트 개선 실험·사전등록·검증 수정이 남아 있음 |
| `submission` | 기존 공개 제출·배포 이력이 연결되어 있음. `submission-final` 태그도 유지 |

`codex/coding-ai-upgrade`는 예전 PR #4에서 한 차례 통합한 이름이지만, 그 뒤 새 작업이 추가됐다.
과거 PR 하나가 병합됐다는 이유로 현재 브랜치를 삭제하면 안 된다.

로컬 `submission`과 `origin/submission`은 서로 1개씩 다른 커밋을 가진다.
두 끝점은 master에 포함되어 있지만 공개 배포가 참조하는 대상을 확인하기 전에는 지우거나 강제로 맞추지 않는다.

## 먼저 보관 여부를 결정할 브랜치

| 브랜치 | 상태 | 제안 |
|---|---|---|
| `aws` | master 및 현재 개발 브랜치에 없는 AWS 작업 커밋 1개(`c750e29`) | AWS 개발을 종료한다면 끝점을 보관 태그로 남긴 뒤 정리할 후보. 지금은 유지 |
| `main` | master와 공통 조상이 없는 독립 이력, 커밋 1개(`299e5de`) | 예전 초기본의 필요성을 확인하고 보관 태그를 만든 뒤 정리할 후보. 기본 브랜치는 master |

## 확인 방법

```powershell
git fetch origin
git branch -vv
git branch -r --merged origin/master
git log --oneline origin/master..origin/codex/coding-ai-upgrade
git rev-list --left-right --count submission...origin/submission
gh pr list --state all --limit 100
```

이 문서는 확인 당시 상태다. 이후 새 커밋이나 PR이 생기면 삭제 후보를 다시 판정한다.

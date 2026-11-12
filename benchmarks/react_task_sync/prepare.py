"""Freeze an actual repository bug into independent agent workspaces; no model calls."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile

from coding_instructions import build_coding_instructions
from coding_work_trials import general_prompt

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tmp" / "react-task-sync-20261109"
TASK = """실제 React 버그를 수정하세요. 코딩 지침 결과/보관함 화면에서 위쪽 작업 요청을 입력·변경해도 아래 '실제 작업 비교'의 '두 조건에 사용할 실제 작업' 입력란에는 최신 내용이 반영되지 않습니다.

완료 조건:
1. 처음 받은 작업 요청이 표시되고, 아직 비교 입력란을 직접 편집하지 않았다면 부모의 최신 작업 요청이 반영되어야 합니다. 빈 문자열로 바뀌는 경우도 포함합니다.
2. 비교 입력란을 사용자가 직접 편집한 뒤에는 부모 요청이 바뀌어도 그 입력을 보존하세요. 사용자가 직접 전부 지운 경우, 편집했다가 이전 원문으로 되돌린 경우도 직접 편집으로 취급합니다.
3. 작업 이름·도구·모델·완료 조건 등 다른 입력은 부모 요청 변경으로 잃지 않아야 합니다.
4. 이미 시작하거나 불러온 비교 기록의 과제·지침·결과는 부모 요청 변경으로 바꾸지 마세요. 확인 후 '새 작업 비교'를 선택하면 최신 부모 요청으로 새 비교를 준비하고, 그 새 비교에서 직접 편집하기 전까지는 다시 최신 요청을 따르세요. 취소 시 기존 기록을 유지하세요.
5. 입력 동기화만으로 저장/AI 호출/비교 생성이 발생하면 안 됩니다. 기존 계정별 기록과 타이머 기능을 유지하세요.

프로젝트 프론트는 실제로 React JSX로 작성되어 있습니다. 이번 범위에서 TypeScript 변환이나 라이브러리 추가는 하지 않습니다.
"""
COMMON = """동일 조건의 독립 버그 수정 실행입니다. 다른 실행이나 정답 패치를 보지 마세요.
지정된 작업 폴더 안의 CLAUDE.md와 파일만 읽고 수정하세요. 원본 저장소, 상위 tmp의 다른 폴더, 평가기, 다른 에이전트의 출력은 읽지 마세요. node_modules는 기존 의존성의 읽기 전용 연결입니다.
프로덕션 수정은 frontend/src/features/coding-instructions/CodingTrialPanel.jsx 및 필요할 경우 같은 폴더의 새 보조 모듈로 제한합니다. 자체 테스트는 추가할 수 있지만 기존 테스트와 package 파일은 바꾸지 마세요. API/백엔드/engine/저장 데이터/환경변수 파일은 수정·조회하지 마세요.
네트워크, 모델 API, 브라우저, 추가 에이전트, 패키지 설치, git commit은 사용하지 마세요. 코드 검토·문법 확인 후 필요한 로컬 테스트만 실행하세요. 기존 테스트는 frontend에서 node --test src/features/coding-instructions/codingWorkflow.test.js 로 실행할 수 있습니다.
최초 도구 호출에서 작업 폴더의 started.json에 실제 UTC ISO 시각을 기록하고 시작하세요. 끝나면 마지막 도구 호출에서 finished.json에 실제 UTC ISO 시각, 수정 파일 목록, 자체 검사 결과를 기록하세요. 시간은 추정하지 마세요. 최대 8분 안에 한 수정안을 제출하고 더 고치지 마세요.
마지막 답변에는 변경과 검사 결과를 적으세요. 평가자는 별도 고정 검사로 기능을 확인합니다.
"""


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    archive = subprocess.check_output(["git", "archive", "--format=zip", commit, "frontend", "CLAUDE.md", "AGENTS.md"], cwd=ROOT)
    profile = {"language": "JavaScript", "framework": "React", "extra": "",
               "preferences": {"explanation": "brief", "comments": "essential", "structure": "compact", "output": "changes"}}
    prompts = {"general": general_prompt(profile, []), "personalized": build_coding_instructions(profile)["prompt"]}
    manifest = {"baseline_commit": commit, "task": TASK, "common_execution": COMMON, "profile": profile,
                "assignment": {"arm_a": "general", "arm_b": "personalized"}, "arms": {},
                "interpretation": "One real React JSX bug, one independent agent per condition; not human editing time or causal evidence.",
                "paid_api_requests": 0}
    for arm, condition in manifest["assignment"].items():
        dest = OUT / arm
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            bundle.extractall(dest)
        payload = prompts[condition] + "\n\n## 과제\n" + TASK + "\n## 실행 규칙\n" + COMMON
        (dest / "TASK.txt").write_text(payload, encoding="utf-8")
        manifest["arms"][arm] = {"condition": condition, "prompt": prompts[condition],
            "payload_sha256": hashlib.sha256(payload.encode()).hexdigest(),
            "component_sha256": hashlib.sha256((dest / "frontend/src/features/coding-instructions/CodingTrialPanel.jsx").read_bytes()).hexdigest()}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"directory": str(OUT), "commit": commit, "same_code": len({v["component_sha256"] for v in manifest["arms"].values()}) == 1}))


if __name__ == "__main__":
    main()

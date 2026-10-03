"""React UI가 사용할 수 있는 최소 JSON API.

기존 ``service.py``를 그대로 감싸기만 합니다. API 키가 없는 로컬 실행에서는
항상 demo_mode=True로 호출하면 되므로, Streamlit 기능과 엔진을 분리한 채
프론트에서도 같은 A/B 비교 루프를 사용할 수 있습니다.
"""

from __future__ import annotations

import base64
import json
import os
import threading
from datetime import date, timedelta
from dataclasses import asdict, replace
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv

from agents.prompt_polish import checklist as polish_checklist
from agents.prompt_polish import polish as polish_prompt

import service
import team
import template_library
from app_db import Database
from auth import AuthError, AuthService, TooManyAttempts, User
from budget import DailyBudget  # noqa: F401 - 테스트가 상한 자리에 끼워 넣는다
from quota import Quota, subject_for
from prompt_workspace import builder as ws_builder
from prompt_workspace import exports as ws_exports
from prompt_workspace import requirements as ws_requirements
from prompt_workspace import questions as ws_questions
from prompt_workspace import runner as ws_runner
from prompt_workspace import suggest as ws_suggest
from prompt_workspace.store import ProjectStore
from prompt_workspace.examples import synthetic_cost as ws_sample
from prompt_workspace.models import new_project, status as ws_status, validate_project

load_dotenv()

ROOT = Path(__file__).resolve().parent
HOST = os.environ.get("PPT_API_HOST", "127.0.0.1")
PORT = int(os.environ.get("PPT_API_PORT", "8000"))
# 후보 생성 모델. 근거는 app.py 의 MODEL 주석(같은 실측).
DEFAULT_MODEL = os.environ.get("PPT_MODEL", "openai/gpt-4o-mini")
# 작업 공간의 개선 추천 모델. 프로젝트 방침대로 후보 생성은 싼 모델, 성찰(무엇을 고칠지)은
# 강한 모델 - GEPA 성찰과 같은 모델을 쓴다. gpt-4o-mini 로는 실패를 고치는 제안이 한 번도
# 나오지 않았다 (CLAUDE.md 2026-10-02 작업 공간 2차).
SUGGEST_MODEL = os.environ.get("PPT_SUGGEST_MODEL") or service.REFLECTION_MODEL

# PPT_LIVE=1 이면 프론트가 보내는 demoMode 와 상관없이 실제 모델로 후보를
# 만든다. 프론트는 아직 demoMode: true 를 고정으로 보내므로, 백엔드만으로
# 실제 생성을 켜고 끌 수 있게 하려는 스위치다. 기본은 꺼짐.
LIVE = os.environ.get("PPT_LIVE") == "1"
# 앱 DB 하나 (app_db.py, SQLite): 사용자 · 세션 · 저장한 작업 공간 프로젝트 · 하루
# 사용량 · 팀. 기본 위치 data/ 는 커밋되지 않는다.
DB = Database(os.environ.get("PPT_DB_PATH") or ROOT / "data" / "app.db")


def _quota(kind: str, total_env: str, total: int, user_env: str, per_user: int) -> Quota:
    """하루 상한 (quota.py). 서버 전체 상한 + 사람마다의 상한. 로그인하지 않은 방문자는
    모두 합쳐 한 사람 몫을 나눠 쓴다(PPT_ANON_<KIND>_PER_DAY 로 바꿀 수 있다).
    DB 에 남으므로 서버를 다시 켜도 초기화되지 않는다."""
    per = int(os.environ.get(user_env, str(per_user)))
    anon_env = user_env.replace("PPT_USER_", "PPT_ANON_")
    return Quota(lambda: DB, kind, total=int(os.environ.get(total_env, str(total))), per_user=per,
                 anon=int(os.environ.get(anon_env, str(per))))


# 실제 생성 세션 상한.
LIVE_SESSIONS = _quota("session", "PPT_LIVE_SESSIONS_PER_DAY", 60, "PPT_USER_SESSIONS_PER_DAY", 20)
# GEPA 최적화 상한. 한 번에 모델 호출이 수십 번이다.
MAX_OPTIMIZATIONS_PER_SESSION = 2
DAILY_OPTIMIZATIONS = _quota("optimize", "PPT_OPTIMIZATIONS_PER_DAY", 30, "PPT_USER_OPTIMIZATIONS_PER_DAY", 5)
OPTIMIZE_RUNS: dict[str, int] = {}
# 최적화 근거(전후 점수 등). 화면에서 "무슨 기준으로 다듬었는지" 보여 준다.
OPTIMIZE_REPORTS: dict[str, dict] = {}
# 팀 모드 (team.py). DB 에 남는다. 로그인한 사람은 자기 아이디로만 참여한다.
TEAMS = team.TeamStore(DB)
# 다른 출처에서 이 API 를 부르도록 허용할 주소 목록 (쉼표로 구분). 기본은
# 비어 있다 - React 화면은 Vite 프록시(/api)로 같은 출처에서 부르므로 CORS
# 헤더가 필요 없다. 예전처럼 "*" 를 주면 PPT_LIVE=1 로 켜 둔 동안 사용자가
# 연 아무 웹페이지나 서버 키로 다듬기·최적화를 호출할 수 있다.
ALLOWED_ORIGINS = frozenset(
    o.strip() for o in os.environ.get("PPT_CORS_ORIGINS", "").split(",") if o.strip()
)
SESSIONS: dict[str, service.SessionState] = {}
SESSIONS_LOCK = threading.Lock()


def _jsonable(value: Any) -> Any:
    """dataclass 내부의 PairView/Candidate를 JSON으로 바꾼다."""
    return asdict(value)


def _state_payload(state: service.SessionState) -> dict[str, Any]:
    payload = _jsonable(state)
    payload["round"] = state.round
    payload["answered"] = state.answered
    if state.done:
        domain, estimator = service.current_estimate(state)
        seed = service.final_prompt(domain, estimator, template_id=state.template_id)
        if state.prompt is None:
            payload["prompt"] = seed
        # GEPA 는 후보가 시드보다 낫지 않으면 시드를 그대로 돌려준다. 그걸
        # "최적화가 적용됐다"고 표시하면 거짓이므로 바뀌었는지를 같이 준다.
        payload["optimize_changed"] = state.optimize_status == "done" and state.prompt != seed
        payload["optimize_report"] = OPTIMIZE_REPORTS.get(state.session_id)
        # 화면에 보이는 프롬프트를 도구별 형식으로. 계산만 하고 모델은 안 부른다.
        payload["exports"] = [asdict(e) for e in service.exports_for(state, payload.get("prompt") or state.prompt)]
    return payload


def _team_payload(code: str) -> dict[str, Any]:
    """팀 결과: 팀원 이름, 축마다 갈린 정도, 합친 선호로 조립한 팀 프롬프트와
    내보내기. 팀원별 원문이나 생성 결과는 담지 않는다."""
    domain_key, members = TEAMS.get(code)
    domain = service.load_domain_for(_domain_path(domain_key))
    estimator, agreements = team.summarize(domain, members)
    prompt = service.final_prompt(domain, estimator)
    labels = domain.final_prompt.axis_labels if domain.final_prompt else {}
    return {
        "code": code,
        "domain_key": domain_key,
        "members": [m.name for m in members],
        # 로그인한 계정으로 참여한 사람 (화면이 이름 옆에 표시한다).
        "signedIn": [m.name for m in members if m.signed_in],
        "agreements": [
            {**asdict(a), "label": labels.get(a.axis) or domain.axis(a.axis).description}
            for a in agreements
        ],
        "prompt": prompt,
        "exports": [asdict(e) for e in service.exports_for_estimate(domain, estimator, prompt, slug_suffix="-team")],
    }


def _domain_path(domain_key: str) -> str:
    allowed = {
        "coding": ROOT / "domains" / "coding.yaml",
        "idle_tracker": ROOT / "domains" / "idle_tracker.yaml",
        "review": ROOT / "domains" / "review.yaml",
        "email": ROOT / "domains" / "email.yaml",
        "summarization": ROOT / "domains" / "summarization.yaml",
        "summarization_ko": ROOT / "domains" / "summarization_ko.yaml",
        "summarization_hybrid": ROOT / "domains" / "summarization_hybrid.yaml",
        "macsum_eval_agent": ROOT / "domains" / "macsum_eval_agent.yaml",
    }
    path = allowed.get(domain_key)
    if path is None:
        raise ValueError(f"지원하지 않는 도메인입니다: {domain_key}")
    return str(path)


def _report_source_text(report: dict[str, Any]) -> str:
    """findings 를 생성기가 실제로 인용할 수 있는 형태로 적는다.

    이전 sourceText는 "찾았으니 확인하세요" 정도의 안내문 한 줄이었다 -
    그 문장만 생성기에 들어가면 실제 금액·리소스ID를 하나도 못 받은
    채로 "요약"을 만드는 셈이라, 출력에 나오는 구체적인 숫자는 전부
    모델이 지어낸 것일 수밖에 없다(사용자에게 보여주는 카드에는 진짜
    데이터가 있는데, 그걸 요약하는 모델만 못 보고 있었다). 개인화(상세도
    ·강조점)와 정확성(금액·리소스ID가 실제와 일치)을 따로 검증하려면
    검증 대상 자체가 먼저 정확해야 한다."""
    period = report.get("period", {})
    lines = [
        f"조회 기간: {period.get('start', '?')} ~ {period.get('end', '?')}",
        f"총 예상 비용: {report.get('totalCost', '?')}",
    ]
    for finding in report.get("findings", []):
        lines.append(
            f"- {finding.get('service', '?')} ({finding.get('resourceId', '?')}): "
            f"{finding.get('cost', '?')} - {finding.get('reason', '')} "
            f"해결: {finding.get('resolution', '')}"
        )
    return "\n".join(lines)


def _demo_aws_cost_report(lookback_days: int = 30) -> dict[str, Any]:
    """API 키 없이도 항상 같은 화면을 보여주는 AWS 비용 점검 결과."""
    end = date.today()
    start = end - timedelta(days=lookback_days)
    report: dict[str, Any] = {
        "mode": "demo",
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "totalCost": "₩16,800",
        "currency": "KRW",
        "findings": [
            {
                "id": "eip",
                "service": "EC2 탄력적 IP",
                "resourceId": "eipalloc-0a12bc34de56f7890",
                "cost": "₩10,000",
                "severity": "high",
                "reason": "연결되지 않은 탄력적 IP가 계속 과금되고 있습니다.",
                "resolution": "AWS 콘솔 > EC2 > 탄력적 IP 메뉴에서 릴리스하세요.",
            },
            {
                "id": "snapshot",
                "service": "EBS 스냅샷",
                "resourceId": "snap-0f1234567890abcd1",
                "cost": "₩6,800",
                "severity": "medium",
                "reason": "오래된 스냅샷이 남아 있어 저장 비용이 발생합니다.",
                "resolution": "AWS 콘솔 > EC2 > 스냅샷에서 필요 없는 항목을 확인 후 삭제하세요.",
            },
        ],
    }
    report["sourceText"] = _report_source_text(report)
    return report


def _aws_cost_report(body: dict[str, Any]) -> dict[str, Any]:
    """Cost Explorer를 선택적으로 조회하고, 실패하면 안전한 데모 결과를 반환한다."""
    try:
        lookback_days = min(max(int(body.get("lookbackDays", 30)), 7), 90)
    except (TypeError, ValueError):
        raise ValueError("lookbackDays는 7~90 사이의 숫자여야 합니다.")
    if bool(body.get("demoMode", True)):
        return _demo_aws_cost_report(lookback_days)

    try:
        import boto3  # type: ignore

        end = date.today()
        start = end - timedelta(days=lookback_days)
        client = boto3.client("ce", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        response = client.get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
        groups: list[dict[str, Any]] = []
        total = 0.0
        for result in response.get("ResultsByTime", []):
            for group in result.get("Groups", []):
                amount = float(group.get("Metrics", {}).get("UnblendedCost", {}).get("Amount", 0) or 0)
                total += amount
                if amount > 0:
                    groups.append({"service": group.get("Keys", ["알 수 없는 서비스"])[0], "amount": amount})
        groups.sort(key=lambda item: item["amount"], reverse=True)
        findings = [
            {
                "id": f"service-{index}",
                "service": item["service"],
                "resourceId": "서비스 단위 비용",
                "cost": f"${item['amount']:.2f}",
                "severity": "high" if index == 0 else "medium",
                "reason": "최근 사용량이 높은 서비스입니다.",
                "resolution": "AWS Cost Explorer에서 세부 리소스와 사용량을 확인하세요.",
            }
            for index, item in enumerate(groups[:4])
        ]
        report = _demo_aws_cost_report(lookback_days)
        report.update({"mode": "aws", "currency": "USD", "totalCost": f"${total:.2f}", "findings": findings})
        report["sourceText"] = _report_source_text(report)
        return report
    except Exception:  # noqa: BLE001 - 자격 증명/SDK/권한 오류를 비밀 없이 처리
        report = _demo_aws_cost_report(lookback_days)
        report["liveError"] = "AWS Cost Explorer를 사용할 수 없어 데모 데이터를 표시합니다."
        return report


# 프롬프트 자체는 비교 세션의 sourceText(과제 원문, 12,000자 한도)보다
# 훨씬 짧아야 정상이다. 큰 값을 받으면 사용자가 원문을 프롬프트 칸에
# 잘못 붙여넣은 것으로 보고 앞에서 거절한다.
MAX_POLISH_PROMPT_CHARS = 4_000
# 프롬프트 다듬기(가져온 프롬프트의 LLM 재작성, /api/polish) 하루 상한. 세션·최적화와 같은
# 방침이고, 재시작하면 0 으로 돌아가므로 결제 쪽 월 상한을 대신하지 않는다.
DAILY_POLISHES = _quota("polish", "PPT_POLISHES_PER_DAY", 60, "PPT_USER_POLISHES_PER_DAY", 20)


def _checklist_payload(items) -> list[dict[str, Any]]:
    return [{"name": r.name, "passed": r.passed, "note": r.note} for r in items]


def _polish_prompt_text(body: dict[str, Any]) -> str:
    prompt = str(body.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("prompt가 필요합니다.")
    if len(prompt) > MAX_POLISH_PROMPT_CHARS:
        raise ValueError(f"prompt는 {MAX_POLISH_PROMPT_CHARS}자 이내여야 합니다.")
    return prompt


def _polish_checklist_only(body: dict[str, Any]) -> dict[str, Any]:
    """타이핑할 때마다 호출해도 되는 무료 경로 - 모델을 부르지 않는다."""
    prompt = _polish_prompt_text(body)
    return {"checklist": _checklist_payload(polish_checklist(prompt))}


def _polish_prompt(body: dict[str, Any]) -> dict[str, Any]:
    """제출 시 한 번만 부르는 경로 - 체크리스트 + LLM 재작성."""
    prompt = _polish_prompt_text(body)
    # 실제 모델 호출이므로 세션 생성과 같은 스위치를 따른다. 꺼져 있으면
    # 무료 점검표(/api/polish/checklist)만 쓸 수 있다.
    if not LIVE:
        raise ValueError("AI 다듬기는 실제 생성 모드에서만 쓸 수 있습니다 (서버를 PPT_LIVE=1 로 켜 주세요). "
                         "위의 구조 점검은 그대로 쓸 수 있습니다.")
    try:
        _take(DAILY_POLISHES, "AI 다듬기")
    except ValueError as exc:
        raise ValueError(f"{exc} 구조 점검은 계속 쓸 수 있습니다.") from None
    # 모델은 서버가 정한다. 요청 본문의 model 을 따르면 누구든 비싼 모델
    # 이름을 보내 서버 키로 호출할 수 있다.
    result = polish_prompt(prompt, model=DEFAULT_MODEL)
    return {
        "checklist": _checklist_payload(result.checklist),
        "suggestions": result.suggestions,
        "revisedPrompt": result.revised_prompt,
    }


# 개발자용 작업 공간 (prompt_workspace/). 서버는 프로젝트를 들고 있지 않는다 -
# 화면이 단계마다 프로젝트 JSON 을 보낸다. 모델을 부르는 것은 '설명 정리'와
# '시험 실행' 둘이고, 하루 상한을 같이 쓴다. 입력 오류로 멈춘 시험은 차감하지
# 않는다 (runner 의 before_call).
DAILY_WORKSPACE_CALLS = _quota("workspace", "PPT_WORKSPACE_CALLS_PER_DAY", 60, "PPT_USER_WORKSPACE_CALLS_PER_DAY", 30)
# 시험 기록은 최근 것만 오간다. 요청 본문 상한(256KB) 안에 머물게.
MAX_WORKSPACE_RUNS = 6

AUTH = AuthService(DB)
# 저장한 프로젝트는 로그인한 사용자 것만 보이고 열린다 (prompt_workspace/store.py).
WORKSPACE_STORE = ProjectStore(DB)
# 가입을 막고 기존 계정만 쓰게 하려면 0. 기본은 열림 (로컬 도구).
ALLOW_SIGNUP = os.environ.get("PPT_ALLOW_SIGNUP", "1") != "0"
# HTTPS 로 배포할 때 1. 로컬 http 에서 켜면 브라우저가 쿠키를 보내지 않는다.
COOKIE_SECURE = os.environ.get("PPT_COOKIE_SECURE") == "1"
SESSION_COOKIE = "ppt_session"


_REQUEST = threading.local()


def _subject() -> str:
    handler = getattr(_REQUEST, "handler", None)
    user = handler._current_user() if handler is not None else None
    return subject_for(user.id if user else None)


def _take(quota, what: str) -> None:
    """한 번 차감한다. 막히면 이유에 맞는 문구로 ValueError (400)."""
    subject = _subject()
    blocked = quota.try_consume(subject)
    if blocked is None:
        return
    if blocked == "total":
        raise ValueError(f"오늘 이 서버에 배정된 {what} 횟수를 모두 썼습니다. 내일 다시 시도해 주세요.")
    if subject == "anon":
        raise ValueError(f"로그인하지 않은 방문자에게 배정된 오늘의 {what} 횟수를 모두 썼습니다. "
                         "로그인하면 개인 몫이 따로 생깁니다.")
    raise ValueError(f"오늘 내 {what} 횟수를 모두 썼습니다. 내일 다시 시도해 주세요.")


def quota_left() -> dict[str, int]:
    """지금 요청한 사람의 오늘 남은 횟수 (/api/auth/me 가 보여 준다)."""
    subject = _subject()
    quotas = {"session": LIVE_SESSIONS, "optimize": DAILY_OPTIMIZATIONS,
              "polish": DAILY_POLISHES, "workspace": DAILY_WORKSPACE_CALLS}
    return {kind: q.left(subject) for kind, q in quotas.items() if hasattr(q, "left")}


def _consume_workspace_call() -> None:
    if not LIVE:
        raise ValueError("AI 호출은 실제 생성 모드에서만 쓸 수 있습니다 (서버를 PPT_LIVE=1 로 켜 주세요).")
    _take(DAILY_WORKSPACE_CALLS, "작업 공간 AI 호출")


def _ws_project(body: dict[str, Any]) -> dict[str, Any]:
    project = validate_project(body.get("project"))
    project["runs"] = project["runs"][-MAX_WORKSPACE_RUNS:]
    return project


def _ws_payload(project: dict[str, Any]) -> dict[str, Any]:
    return {"project": project, "status": ws_status(project)}


def _workspace_sample() -> dict[str, Any]:
    """AI 호출 없이 미리 정리해 둔 샘플. 실제 구조화 결과가 아니다."""
    project = new_project(ws_sample.TITLE, ws_sample.SAMPLE_DESCRIPTION)
    project["requirements"] = ws_sample.sample_requirements()
    project["check_set"] = ws_sample.NAME
    return {**_ws_payload(project), "input": ws_sample.SAMPLE_INPUT, "live": LIVE,
            "notes": ["샘플 요구사항은 미리 정리해 둔 것입니다 (AI 호출 없음). 실제 AWS 데이터가 아닙니다."]}


def _workspace_structure(body: dict[str, Any]) -> dict[str, Any]:
    raw = str(body.get("description", ""))
    example = str(body.get("exampleOutput", ""))
    if not raw.strip():
        raise ValueError("업무 설명을 적어 주세요.")
    _consume_workspace_call()
    result = ws_requirements.structure(raw, example, model=DEFAULT_MODEL)
    project = new_project(str(body.get("title", ""))[:100], raw, example)
    project["requirements"] = result["requirements"]
    return {**_ws_payload(project), "notes": result["notes"], "cached": result["cached"]}


def _workspace_run(body: dict[str, Any]) -> dict[str, Any]:
    project = _ws_project(body)
    record = ws_runner.run(project, body.get("input"), model=DEFAULT_MODEL, live=LIVE,
                           before_call=_consume_workspace_call)
    return {"run": record}


def _workspace_export(body: dict[str, Any]) -> dict[str, Any]:
    project = _ws_project(body)
    data = ws_exports.build_zip(project, body.get("input"), include_data=bool(body.get("includeData", False)))
    return {"filename": "prompt-package.zip", "zipBase64": base64.b64encode(data).decode("ascii")}


def _workspace_resolve(body: dict[str, Any]) -> dict[str, Any]:
    project = ws_questions.resolve(
        _ws_project(body), str(body.get("questionId", "")), str(body.get("answer", "")), str(body.get("target", "")),
    )
    return _ws_payload(project)


def _workspace_store_get(user: User, parts: list[str]) -> dict[str, Any]:
    """GET /api/workspace/projects[/<id>[/versions/<n>]]"""
    if len(parts) == 4:
        return {"projects": WORKSPACE_STORE.list(user.id)}
    if len(parts) == 5:
        return WORKSPACE_STORE.open(user.id, parts[4])
    if len(parts) == 7 and parts[5] == "versions" and parts[6].isdigit():
        return {"project": WORKSPACE_STORE.version(user.id, parts[4], int(parts[6]))}
    raise LookupError("찾을 수 없는 경로입니다.")


def _workspace_store_post(user: User, parts: list[str], body: dict[str, Any]) -> dict[str, Any]:
    """POST /api/workspace/projects (저장) · /<id>/restore · /<id>/delete
    · /<id>/share · /<id>/unshare · /<id>/draft · /<id>/discard-draft"""
    if len(parts) == 4:
        return WORKSPACE_STORE.save(user.id, _ws_project(body), str(body.get("label", "")))
    if len(parts) == 6 and parts[5] == "share":
        return {"members": WORKSPACE_STORE.share(user.id, parts[4], str(body.get("username", "")),
                                                 str(body.get("role", "")))}
    if len(parts) == 6 and parts[5] == "unshare":
        return {"members": WORKSPACE_STORE.unshare(user.id, parts[4], str(body.get("username", "")))}
    if len(parts) == 6 and parts[5] == "draft":
        project = _ws_project(body)
        if project["id"] != parts[4]:
            raise ValueError("자동 저장할 프로젝트 id 가 경로와 다릅니다.")
        return WORKSPACE_STORE.save_draft(user.id, project)
    if len(parts) == 6 and parts[5] == "discard-draft":
        WORKSPACE_STORE.discard_draft(user.id, parts[4])
        return {"discarded": parts[4]}
    if len(parts) == 6 and parts[5] == "restore":
        try:
            version = int(body.get("version"))
        except (TypeError, ValueError):
            raise ValueError("복원할 버전 번호가 필요합니다.")
        return WORKSPACE_STORE.restore(user.id, parts[4], version)
    if len(parts) == 6 and parts[5] == "delete":
        WORKSPACE_STORE.delete(user.id, parts[4])
        return {"deleted": parts[4]}
    raise LookupError("찾을 수 없는 경로입니다.")


def _user_payload(user: User | None) -> dict[str, Any] | None:
    return None if user is None else {"id": user.id, "username": user.username}


def _session_cookie(token: str) -> str:
    cookie = (f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; "
              f"Max-Age={14 * 24 * 3600}")
    return cookie + ("; Secure" if COOKIE_SECURE else "")


def _clear_cookie() -> str:
    return f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0" + ("; Secure" if COOKIE_SECURE else "")


def _workspace_suggest(body: dict[str, Any]) -> dict[str, Any]:
    """개선 방향 추천. 코드 제안은 언제나, AI 제안은 실제 생성 모드에서만 (하루 상한 차감)."""
    project = _ws_project(body)
    if project.get("artifact") is None or ws_status(project)["stage"] != "built":
        raise ValueError("지금 요구사항으로 만든 프롬프트가 있어야 개선 방향을 추천할 수 있습니다.")
    if LIVE:
        _consume_workspace_call()
    return ws_suggest.suggest(project, model=SUGGEST_MODEL, use_ai=LIVE)


def _workspace_trial_suggestions(body: dict[str, Any]) -> dict[str, Any]:
    """제안마다 같은 입력으로 시험해 검사 변화를 센다. 지금 지침 1회 + 제안 수만큼 모델을
    부르므로(캐시된 것도 상한에서는 센다) 남은 횟수가 모자라면 시작하기 전에 거절한다."""
    if not LIVE:
        raise ValueError("제안 시험은 실제 생성 모드에서만 쓸 수 있습니다 (서버를 PPT_LIVE=1 로 켜 주세요).")
    project = _ws_project(body)
    picked = body.get("suggestions")
    if not isinstance(picked, list) or not picked:
        raise ValueError("시험할 제안이 없습니다.")
    testable = [s for s in picked[:ws_suggest.MAX_SUGGESTIONS] if s.get("applicable") and not s.get("touches_rules")]
    needed = 1 + len(testable)
    left = DAILY_WORKSPACE_CALLS.left(_subject())
    if left < needed:
        raise ValueError(f"제안 시험에 AI 호출 {needed}회가 필요한데 오늘 남은 횟수는 {left}회입니다.")
    values = body.get("input")
    return ws_suggest.trial(
        project, picked,
        lambda p: ws_runner.run(p, values, model=DEFAULT_MODEL, live=LIVE, before_call=_consume_workspace_call),
    )


def _workspace_apply_suggestions(body: dict[str, Any]) -> dict[str, Any]:
    """고른 제안을 적용한 지침 후보. 모델을 부르지 않고 프로젝트도 바꾸지 않는다."""
    picked = body.get("suggestions")
    if not isinstance(picked, list) or not picked:
        raise ValueError("적용할 제안을 하나 이상 고르세요.")
    return ws_suggest.apply(_ws_project(body), picked, allow_rule_changes=bool(body.get("allowRuleChanges")))


WORKSPACE_ROUTES = {
    "/api/workspace/suggest": _workspace_suggest,
    "/api/workspace/apply-suggestions": _workspace_apply_suggestions,
    "/api/workspace/trial-suggestions": _workspace_trial_suggestions,
    "/api/workspace/resolve": _workspace_resolve,
    "/api/workspace/status": lambda body: _ws_payload(_ws_project(body)),
    "/api/workspace/structure": _workspace_structure,
    "/api/workspace/confirm": lambda body: _ws_payload(ws_builder.confirm(_ws_project(body))),
    "/api/workspace/build": lambda body: _ws_payload(ws_builder.build(_ws_project(body))),
    "/api/workspace/run": _workspace_run,
    "/api/workspace/export": _workspace_export,
}


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "PreferencePromptAPI/1.0"

    def _send(self, status: int, body: dict[str, Any], cookies: list[str] | None = None) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        # 로그인 응답이 캐시에 남지 않게.
        self.send_header("Cache-Control", "no-store")
        for cookie in cookies or []:
            self.send_header("Set-Cookie", cookie)
        origin = self.headers.get("Origin")
        if origin and origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(encoded)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        # 음수면 rfile.read(-1) 이 연결이 끊길 때까지 기다린다.
        if length < 0:
            raise ValueError("Content-Length가 올바르지 않습니다.")
        if length > 256_000:
            raise ValueError("요청 본문이 너무 큽니다.")
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(data, dict):
            raise ValueError("JSON 객체가 필요합니다.")
        return data

    # --- 로그인 -----------------------------------------------------------------

    def _session_token(self) -> str | None:
        try:
            jar = SimpleCookie(self.headers.get("Cookie", ""))
        except CookieError:
            return None
        morsel = jar.get(SESSION_COOKIE)
        return morsel.value if morsel else None

    def _current_user(self) -> User | None:
        if not hasattr(self, "_user_cache"):
            self._user_cache = AUTH.user_for(self._session_token())
        return self._user_cache

    def _client_address(self) -> str:
        """로그인 실패를 셀 방문자 주소.

        Vite 프록시를 거치면 서버가 보는 주소는 모두 127.0.0.1 이라, 그대로 세면 한 사람의
        실패가 모든 사람의 로그인을 막는다. 직접 연결한 쪽이 이 컴퓨터(루프백)일 때만
        프록시가 붙인 X-Forwarded-For 를 믿고, 그중 **마지막** 주소를 쓴다 - 프록시가 직접
        본 주소이고, 앞부분은 방문자가 헤더에 마음대로 적을 수 있다. 서버를 외부에 열면
        (PPT_API_HOST) 바깥 연결은 루프백이 아니므로 헤더를 무시한다."""
        direct = self.client_address[0]
        if direct in ("127.0.0.1", "::1"):
            forwarded = [a.strip() for a in self.headers.get("X-Forwarded-For", "").split(",") if a.strip()]
            if forwarded:
                return forwarded[-1]
        return direct

    def _cross_site(self) -> bool:
        """다른 사이트에서 온 POST 인가. 쿠키로 로그인한 상태를 다른 사이트가
        이용하지 못하게(CSRF) 막는다. SameSite=Lax 쿠키와 JSON 전용 본문이 1차 방어이고,
        이것은 2차다. Origin 이 없으면(curl·테스트·같은 출처의 일부 요청) 통과시킨다."""
        origin = self.headers.get("Origin")
        if not origin or origin in ALLOWED_ORIGINS:
            return False
        # 앞단 프록시(Vite 개발 서버 등)가 Host 를 바꿨으면 원래 Host 를 X-Forwarded-Host 로
        # 알려 준다. 이 서버는 127.0.0.1 에서만 열리므로 그 헤더를 보낼 수 있는 것은 같은
        # 컴퓨터의 프록시뿐이다 - 외부에 열 때는 이 가정을 다시 봐야 한다.
        hosts = {self.headers.get("Host", "")}
        hosts.update(h.strip() for h in self.headers.get("X-Forwarded-Host", "").split(",") if h.strip())
        return urlparse(origin).netloc not in hosts

    def _auth_route(self, path: str, body: dict[str, Any]) -> None:
        if path == "/api/auth/signup":
            if not ALLOW_SIGNUP:
                self._send(403, {"error": "이 서버는 새 가입을 받지 않습니다."})
                return
            user, token = AUTH.signup(str(body.get("username", "")), str(body.get("password", "")))
            print(f"[auth] 가입 {user.username}", flush=True)
            self._send(200, {"user": _user_payload(user)}, cookies=[_session_cookie(token)])
            return
        if path == "/api/auth/login":
            try:
                user, token = AUTH.login(str(body.get("username", "")), str(body.get("password", "")),
                                         address=self._client_address())
            except TooManyAttempts as exc:
                self._send(429, {"error": str(exc)})
                return
            self._send(200, {"user": _user_payload(user)}, cookies=[_session_cookie(token)])
            return
        if path == "/api/auth/logout":
            AUTH.logout(self._session_token())
            self._send(200, {"user": None}, cookies=[_clear_cookie()])
            return
        if path in ("/api/auth/password", "/api/auth/delete"):
            user = self._current_user()
            if user is None:
                self._send(401, {"error": "로그인이 필요합니다."})
                return
            try:
                if path == "/api/auth/password":
                    token = AUTH.change_password(user, str(body.get("current", "")), str(body.get("new", "")),
                                                 address=self._client_address())
                    self._send(200, {"user": _user_payload(user)}, cookies=[_session_cookie(token)])
                else:
                    AUTH.delete_account(user, str(body.get("password", "")), address=self._client_address())
                    print(f"[auth] 탈퇴 {user.username}", flush=True)
                    self._send(200, {"user": None}, cookies=[_clear_cookie()])
            except TooManyAttempts as exc:
                self._send(429, {"error": str(exc)})
            return
        self._send(404, {"error": "찾을 수 없는 경로입니다."})

    def do_OPTIONS(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._send(204, {})

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        _REQUEST.handler = self
        path = urlparse(self.path).path.rstrip("/")
        if path == "/api/health":
            # live: 화면이 열리자마자 세션을 만들지 말지 정하는 데 쓴다. 실제
            # 생성 모드에서 자동으로 세션을 열면 방문만으로 하루 상한이 준다.
            self._send(200, {"ok": True, "demoAvailable": True, "live": LIVE})
            return
        if path == "/api/auth/me":
            user = self._current_user()
            self._send(200, {
                "user": _user_payload(user),
                "signupOpen": ALLOW_SIGNUP,
                # 탈퇴하면 공유받은 사람에게서도 사라질 내 프로젝트 수 (화면이 미리 알린다).
                "ownedShared": AUTH.owned_shared_count(user) if user else 0,
                # 오늘 남은 AI 횟수 (로그인 안 했으면 익명 공용 몫).
                "quota": quota_left(),
            })
            return
        if len(parts := path.split("/")) == 4 and parts[:3] == ["", "api", "teams"]:
            try:
                self._send(200, {"team": _team_payload(parts[3])})
            except team.TeamError as exc:
                self._send(404, {"error": str(exc)})
            return
        if path == "/api/workspace/sample":
            self._send(200, _workspace_sample())
            return
        if path.startswith("/api/workspace/projects"):
            self._workspace_store(lambda user, parts: _workspace_store_get(user, parts), path)
            return
        if path == "/api/templates":
            self._send(200, {"templates": [asdict(t) for t in template_library.library()]})
            return
        # 최적화 진행률을 폴링하는 경로. /api/sessions/<id>
        parts = path.split("/")
        if len(parts) == 4 and parts[:3] == ["", "api", "sessions"]:
            with SESSIONS_LOCK:
                state = SESSIONS.get(parts[3])
            if state is None:
                self._send(404, {"error": "세션을 찾을 수 없습니다."})
                return
            self._send(200, {"session": _state_payload(state)})
            return
        self._send(404, {"error": "찾을 수 없는 경로입니다."})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        _REQUEST.handler = self
        path = urlparse(self.path).path.rstrip("/")
        if self._cross_site():
            self._send(403, {"error": "다른 사이트에서 보낸 요청은 받지 않습니다."})
            return
        try:
            body = self._read_json()
            if path.startswith("/api/auth/"):
                self._auth_route(path, body)
                return
            if path == "/api/sessions":
                self._start_session(body)
                return
            if path == "/api/aws/costs":
                self._send(200, {"report": _aws_cost_report(body)})
                return
            if path == "/api/polish/checklist":
                self._send(200, _polish_checklist_only(body))
                return
            if path == "/api/polish":
                self._send(200, _polish_prompt(body))
                return
            if path in WORKSPACE_ROUTES:
                self._send(200, WORKSPACE_ROUTES[path](body))
                return
            if path.startswith("/api/workspace/projects"):
                self._workspace_store(lambda user, parts: _workspace_store_post(user, parts, body), path)
                return
            if path.startswith("/api/teams/") and path.endswith("/members"):
                self._join_team(path.split("/")[3], body)
                return
            if path.startswith("/api/sessions/") and path.endswith("/optimize"):
                self._start_optimize(path.split("/")[3])
                return
            if path.startswith("/api/sessions/") and path.endswith("/choices"):
                session_id = path.split("/")[3]
                self._submit_choice(session_id, body)
                return
            self._send(404, {"error": "찾을 수 없는 경로입니다."})
        except service.StaleChoiceError as exc:
            self._send(409, {"error": str(exc)})
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001 - API 응답으로 안전하게 변환
            # 원문은 서버 터미널에만. 공급자 오류 문구에는 키 일부가 들어 있다.
            print(f"[error] {type(exc).__name__}: {exc}", flush=True)
            self._send(500, {"error": service.describe_api_error(exc)})

    def _workspace_store(self, handle, path: str) -> None:
        """저장소 경로 공통 처리. 로그인이 없으면 401, 없는(또는 남의) 프로젝트·버전은
        404, 형식 오류는 400."""
        parts = path.split("/")
        if len(parts) > 3 and parts[3] != "projects":
            self._send(404, {"error": "찾을 수 없는 경로입니다."})
            return
        user = self._current_user()
        if user is None:
            self._send(401, {"error": "로그인이 필요합니다. 저장과 다시 열기는 로그인한 뒤에 쓸 수 있습니다."})
            return
        try:
            self._send(200, handle(user, parts))
        except PermissionError as exc:
            self._send(403, {"error": str(exc)})
        except (KeyError, LookupError):
            self._send(404, {"error": "저장된 프로젝트나 버전을 찾을 수 없습니다."})
        except ValueError as exc:
            self._send(400, {"error": str(exc)})

    def _start_session(self, body: dict[str, Any]) -> None:
        domain_key = str(body.get("domainKey", "coding"))
        source_text = str(body.get("sourceText", "")).strip()
        if not source_text:
            raise ValueError("sourceText가 필요합니다.")
        demo_mode = bool(body.get("demoMode", True))
        if LIVE:
            if LIVE_SESSIONS.try_consume(_subject()) is None:
                demo_mode = False
            else:
                print("[session] 오늘 실제 생성 상한에 도달해 데모로 진행한다", flush=True)
        args = dict(
            source_text=source_text[:12_000],
            domain_key=domain_key,
            domain_path=_domain_path(domain_key),
            # 모델은 서버가 정한다 (요청 본문의 model 은 무시). 브라우저가
            # 고르게 두면 누구든 비싼 모델 이름으로 서버 키를 쓸 수 있다.
            model=DEFAULT_MODEL,
            total_rounds=min(max(int(body.get("totalRounds", service.TOTAL_ROUNDS)), 1), 8),
            # 템플릿 라이브러리의 "내 방식으로 바꾸기". 없는 id·다른 도메인은 400.
            template_id=(str(body["templateId"]) if body.get("templateId") else None),
        )
        try:
            state = service.start_session(demo_mode=demo_mode, **args)
        except Exception as exc:  # noqa: BLE001 - 실제 호출 실패는 데모로 내린다
            if demo_mode:
                raise
            _log_live_failure(exc)
            state = service.start_session(demo_mode=True, **args)
        print(f"[session] {domain_key} mode={'demo' if state.demo_mode else 'live'}", flush=True)
        with SESSIONS_LOCK:
            SESSIONS[state.session_id] = state
        self._send(201, {"session": _state_payload(state)})

    def _submit_choice(self, session_id: str, body: dict[str, Any]) -> None:
        chosen = str(body.get("chosen", ""))
        pair_id = str(body.get("pairId", ""))
        with SESSIONS_LOCK:
            state = SESSIONS.get(session_id)
        if state is None:
            self._send(404, {"error": "세션을 찾을 수 없습니다."})
            return
        try:
            updated = service.submit_choice(state, pair_id, chosen)
        except service.StaleChoiceError:
            raise
        except Exception as exc:  # noqa: BLE001 - 실제 호출 실패는 데모로 내린다
            if state.demo_mode:
                raise
            # 중간에 키가 만료되거나 한도에 걸려도 지금까지의 선택은 살린다.
            _log_live_failure(exc)
            updated = service.submit_choice(replace(state, demo_mode=True), pair_id, chosen)
        with SESSIONS_LOCK:
            SESSIONS[session_id] = updated
        self._send(200, {"session": _state_payload(updated)})

    def _join_team(self, code: str, body: dict[str, Any]) -> None:
        """끝난 세션의 선택 기록을 팀에 더한다. 원문은 넘기지 않는다."""
        with SESSIONS_LOCK:
            state = SESSIONS.get(str(body.get("sessionId", "")))
        if state is None:
            self._send(404, {"error": "세션을 찾을 수 없습니다."})
            return
        if not state.done:
            raise ValueError("선택을 모두 마친 뒤에 팀에 더할 수 있습니다.")
        # 로그인했으면 이름 칸은 무시하고 아이디로 참여한다.
        user = self._current_user()
        TEAMS.add(code, state.domain_key, str(body.get("name", "")), state.history,
                  user_id=user.id if user else None, username=user.username if user else None)
        self._send(200, {"team": _team_payload(code)})

    def _start_optimize(self, session_id: str) -> None:
        """GEPA 최적화를 백그라운드로 시작하고 바로 돌려준다.

        수십 초 걸리므로 요청을 붙잡고 있지 않는다. 진행률과 결과는
        세션 상태(optimize_status/optimize_progress/prompt)에 쓰고, 프론트는
        GET /api/sessions/<id> 로 폴링한다. Streamlit 결과 화면의 긴
        프롬프트가 이 단계의 산출물이다 - 이 경로가 없으면 React 화면은
        축 문구를 이어 붙인 시드 프롬프트에서 끝난다.
        """
        with SESSIONS_LOCK:
            state = SESSIONS.get(session_id)
            if state is None:
                self._send(404, {"error": "세션을 찾을 수 없습니다."})
                return
            if not state.done:
                raise ValueError("선택을 모두 마친 뒤에 최적화할 수 있습니다.")
            if state.demo_mode:
                raise ValueError("데모 모드에서는 최적화할 수 없습니다. 서버를 PPT_LIVE=1 로 켜 주세요.")
            if state.optimize_status == "running":
                self._send(202, {"session": _state_payload(state)})
                return
            if OPTIMIZE_RUNS.get(session_id, 0) >= MAX_OPTIMIZATIONS_PER_SESSION:
                raise ValueError(f"세션당 최적화는 {MAX_OPTIMIZATIONS_PER_SESSION}회까지입니다.")
            _take(DAILY_OPTIMIZATIONS, "최적화")
            OPTIMIZE_RUNS[session_id] = OPTIMIZE_RUNS.get(session_id, 0) + 1
            state.optimize_status = "running"
            state.optimize_progress = 0.0

        def progress(value: float) -> None:
            state.optimize_progress = value

        def work() -> None:
            print(f"[optimize] {state.domain_key} 시작", flush=True)
            try:
                report: dict = {}
                optimized = service.optimize(state, on_progress=progress, report=report)
                OPTIMIZE_REPORTS[state.session_id] = report
                state.prompt = optimized
                state.optimize_status = "done"
                print(f"[optimize] {state.domain_key} 완료 ({len(optimized)}자)", flush=True)
            except Exception as exc:  # noqa: BLE001 - 실패해도 시드 프롬프트는 남는다
                state.optimize_status = "error"
                print(f"[optimize] 실패: {type(exc).__name__}: {exc}", flush=True)

        threading.Thread(target=work, daemon=True).start()
        self._send(202, {"session": _state_payload(state)})

    def log_message(self, format: str, *args: Any) -> None:
        # 기본 access log는 터미널을 지나치게 채우므로 필요한 오류만 앱에서 본다.
        return


def _log_live_failure(exc: Exception) -> None:
    """실제 호출 실패는 서버 터미널에만 남긴다. 응답으로 돌려주면 공급자
    에러 문구(키 일부, 계정 정보)가 브라우저까지 간다."""
    print(f"[live] 실제 생성 실패, 데모로 전환: {type(exc).__name__}: {exc}", flush=True)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), ApiHandler)
    print(f"Preference Prompt API listening on http://{HOST}:{PORT}")
    if LIVE:
        key = "있음" if os.environ.get("OPENAI_API_KEY") else "없음 - 호출이 실패해 데모로 내려간다"
        print(f"mode: live (model={DEFAULT_MODEL}, API 키 {key}, 하루 {LIVE_SESSIONS.limit}세션)")
    else:
        print("mode: demo (규칙 기반 후보. 실제 생성은 PPT_LIVE=1 로 켠다)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPreference Prompt API stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

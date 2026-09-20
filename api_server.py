"""React UI가 사용할 수 있는 최소 JSON API.

기존 ``service.py``를 그대로 감싸기만 합니다. API 키가 없는 로컬 실행에서는
항상 demo_mode=True로 호출하면 되므로, Streamlit 기능과 엔진을 분리한 채
프론트에서도 같은 A/B 비교 루프를 사용할 수 있습니다.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import date, timedelta
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import service
from optimize.run_gepa import build_seed_prompt


ROOT = Path(__file__).resolve().parent
HOST = os.environ.get("PPT_API_HOST", "127.0.0.1")
PORT = int(os.environ.get("PPT_API_PORT", "8000"))
DEFAULT_MODEL = os.environ.get("PPT_MODEL", "openai/gpt-5.6-luna")
SESSIONS: dict[str, service.SessionState] = {}
SESSIONS_LOCK = threading.Lock()


def _jsonable(value: Any) -> Any:
    """dataclass 내부의 PairView/Candidate를 JSON으로 바꾼다."""
    return asdict(value)


def _state_payload(state: service.SessionState) -> dict[str, Any]:
    payload = _jsonable(state)
    payload["round"] = state.round
    payload["answered"] = state.answered
    if state.done and state.prompt is None:
        domain, estimator, _ = service._rebuild(state)
        payload["prompt"] = build_seed_prompt(domain, estimator)
    return payload


def _domain_path(domain_key: str) -> str:
    allowed = {
        "coding": ROOT / "domains" / "coding.yaml",
        "idle_tracker": ROOT / "domains" / "idle_tracker.yaml",
        "review": ROOT / "domains" / "review.yaml",
        "email": ROOT / "domains" / "email.yaml",
        "summarization": ROOT / "domains" / "summarization.yaml",
        "summarization_ko": ROOT / "domains" / "summarization_ko.yaml",
    }
    path = allowed.get(domain_key)
    if path is None:
        raise ValueError(f"지원하지 않는 도메인입니다: {domain_key}")
    return str(path)


def _demo_aws_cost_report(lookback_days: int = 30) -> dict[str, Any]:
    """API 키 없이도 항상 같은 화면을 보여주는 AWS 비용 점검 결과."""
    end = date.today()
    start = end - timedelta(days=lookback_days)
    return {
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
        "sourceText": (
            "AWS 비용 점검 결과입니다. 연결되지 않은 탄력적 IP와 오래된 EBS 스냅샷이 "
            "발견되었습니다. 각 리소스의 비용과 해결 방법을 확인하세요."
        ),
    }


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
        report["sourceText"] = "AWS Cost Explorer 결과를 바탕으로 비용이 높은 서비스를 점검하세요."
        return report
    except Exception:  # noqa: BLE001 - 자격 증명/SDK/권한 오류를 비밀 없이 처리
        report = _demo_aws_cost_report(lookback_days)
        report["liveError"] = "AWS Cost Explorer를 사용할 수 없어 데모 데이터를 표시합니다."
        return report


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "PreferencePromptAPI/1.0"

    def _send(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(encoded)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 256_000:
            raise ValueError("요청 본문이 너무 큽니다.")
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(data, dict):
            raise ValueError("JSON 객체가 필요합니다.")
        return data

    def do_OPTIONS(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        self._send(204, {})

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if urlparse(self.path).path == "/api/health":
            self._send(200, {"ok": True, "demoAvailable": True})
            return
        self._send(404, {"error": "찾을 수 없는 경로입니다."})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = urlparse(self.path).path.rstrip("/")
        try:
            body = self._read_json()
            if path == "/api/sessions":
                self._start_session(body)
                return
            if path == "/api/aws/costs":
                self._send(200, {"report": _aws_cost_report(body)})
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
            self._send(500, {"error": f"세션 처리 중 오류가 발생했습니다: {exc}"})

    def _start_session(self, body: dict[str, Any]) -> None:
        domain_key = str(body.get("domainKey", "coding"))
        source_text = str(body.get("sourceText", "")).strip()
        if not source_text:
            raise ValueError("sourceText가 필요합니다.")
        state = service.start_session(
            source_text[:12_000],
            domain_key,
            _domain_path(domain_key),
            model=str(body.get("model", DEFAULT_MODEL)),
            demo_mode=bool(body.get("demoMode", True)),
            total_rounds=min(max(int(body.get("totalRounds", service.TOTAL_ROUNDS)), 1), 8),
        )
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
        updated = service.submit_choice(state, pair_id, chosen)
        with SESSIONS_LOCK:
            SESSIONS[session_id] = updated
        self._send(200, {"session": _state_payload(updated)})

    def log_message(self, format: str, *args: Any) -> None:
        # 기본 access log는 터미널을 지나치게 채우므로 필요한 오류만 앱에서 본다.
        return


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), ApiHandler)
    print(f"Preference Prompt API listening on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nPreference Prompt API stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

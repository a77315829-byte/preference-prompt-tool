"""Private, user-measured real-work comparisons. No AI calls or code execution."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import time
import uuid

from coding_instructions import build_coding_instructions
from personal_prompts import PromptConflict, expected_revision

ARMS = ("general", "selected")
PHASES = ("setup", "edit")


def text(value, label, maximum, required=True):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError(f"{label}: {'1' if required else '0'}~{maximum}자로 입력해 주세요.")
    return value.strip()


def general_prompt(profile, rules):
    plain = {"language": profile["language"], "framework": profile.get("framework", ""),
             "preferences": {"explanation": "brief", "comments": "essential", "structure": "compact", "output": "complete"}}
    built = build_coding_instructions(plain)["prompt"]
    prompt = built.split("## 직접 고른 내 작성 선호")[0] + "## 항상 지킬 것" + built.split("## 항상 지킬 것")[1]
    if rules:
        prompt += ("\n\n## 이번 작업의 팀 필수 규칙\n"
                   "아래 규칙은 작성 선호보다 우선한다. 요청과 충돌하면 임의로 생략하지 말고 확인하라.\n"
                   + "\n".join("- " + r for r in rules))
    return prompt


def comparison(record):
    arms = record["arms"]
    timed = all(all(arms[a]["timed"][p] for p in PHASES) for a in ARMS) and record["active"] is None
    verified = all(arms[a]["outcome"] in ("pass", "fail") for a in ARMS)
    totals = {a: round(sum(arms[a]["seconds"].values()), 1) if all(arms[a]["timed"].values()) else None for a in ARMS}
    edits = {a: round(arms[a]["seconds"]["edit"], 1) if arms[a]["timed"]["edit"] else None for a in ARMS}
    edits_complete = all(v is not None for v in edits.values()) and record["active"] is None
    return {"timing_complete": timed, "both_checked": verified, "seconds": totals,
            "edit_seconds": edits, "editing_complete": edits_complete,
            "edit_seconds_saved": round(edits["general"] - edits["selected"], 1) if edits_complete else None,
            "seconds_saved": round(totals["general"] - totals["selected"], 1) if timed else None,
            "both_passed": all(arms[a]["outcome"] == "pass" for a in ARMS),
            "accuracy_basis": "사용자가 실행·확인한 결과의 기록. 서버가 코드를 실행하거나 정답을 검증한 점수가 아닙니다."}


class CodingWorkTrials:
    def __init__(self, db, clock=time.time):
        self._db, self.clock = db, clock

    @property
    def db(self):
        return self._db() if callable(self._db) else self._db

    @staticmethod
    def _read(conn, user_id, trial_id):
        row = conn.execute("SELECT * FROM coding_work_trials WHERE id=? AND owner_id=?", (trial_id, user_id)).fetchone()
        if row is None:
            raise LookupError("내 작업 비교 기록을 찾을 수 없습니다.")
        return {**json.loads(row["record_json"]), "id": row["id"], "revision": row["revision"], "updated_at": row["updated_at"]}

    def get(self, user_id, trial_id):
        with self.db.connect() as conn:
            record = self._read(conn, user_id, trial_id)
            return {**record, "comparison": comparison(record), "server_now": self.clock()}

    def list(self, user_id):
        with self.db.connect() as conn:
            rows = conn.execute("SELECT id FROM coding_work_trials WHERE owner_id=? ORDER BY updated_at DESC", (user_id,)).fetchall()
            return [{k: record[k] for k in ("id", "title", "revision", "updated_at", "preference", "active")}
                    | {"comparison": comparison(record)}
                    for row in rows for record in [self._read(conn, user_id, row["id"])]]

    def create(self, user_id, body, draft):
        trial_id = uuid.uuid4().hex
        task = text(body.get("task"), "작업 요청", 10000)
        record = {"title": text(body.get("title"), "작업 이름", 100), "task": task,
                  "model": text(body.get("model"), "모델과 설정", 200),
                  "tool": text(body.get("tool"), "사용 도구", 100),
                  "context": text(body.get("context"), "저장소·버전·완료 조건", 3000),
                  "source": {"profile": draft["profile"], "team_context": draft["team_context"], "snapshot": draft["snapshot"]},
                  "order": list(ARMS) if int(trial_id[-1], 16) % 2 else list(reversed(ARMS)),
                  "active": None, "preference": "unselected", "preference_reason": "", "notes": "",
                  "arms": {a: {"seconds": {p: 0.0 for p in PHASES}, "timed": {p: False for p in PHASES},
                               "outcome": "unverified", "evidence": "", "answer": "",
                               "passed_tests": None, "total_tests": None} for a in ARMS},
                  "prompts": {"general": general_prompt(draft["profile"], (draft["team_context"] or {}).get("rules", [])),
                              "selected": draft["prompt"]},
                  "measurement": "user_timer_and_self_report", "version": 1}
        now = datetime.now(timezone.utc).isoformat()
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT COUNT(*) FROM coding_work_trials WHERE owner_id=?", (user_id,)).fetchone()[0] >= 100:
                raise ValueError("작업 비교는 100개까지 보관할 수 있습니다.")
            conn.execute("INSERT INTO coding_work_trials(id,owner_id,record_json,updated_at) VALUES (?,?,?,?)",
                         (trial_id, user_id, json.dumps(record, ensure_ascii=False), now))
        return self.get(user_id, trial_id)

    def change(self, user_id, trial_id, body, action):
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            record = self._read(conn, user_id, trial_id)
            if expected_revision(body.get("revision")) != record["revision"]:
                raise PromptConflict("다른 창에서 바뀐 기록입니다. 새로 불러온 뒤 계속해 주세요.")
            if action == "delete":
                if record["active"]:
                    raise ValueError("타이머를 멈춘 뒤 삭제해 주세요.")
                conn.execute("DELETE FROM coding_work_trials WHERE id=? AND owner_id=?", (trial_id, user_id))
                return None
            if action == "timer":
                operation = body.get("operation")
                if operation not in ("start", "pause"):
                    raise ValueError("타이머 동작을 확인해 주세요.")
                active = record["active"]
                if operation == "start":
                    arm, phase = body.get("arm"), body.get("phase")
                    if active or arm not in ARMS or phase not in PHASES:
                        raise ValueError("실행 중인 타이머를 먼저 멈추고 비교 항목을 확인해 주세요.")
                    others = conn.execute("SELECT record_json FROM coding_work_trials WHERE owner_id=? AND id<>?",
                                          (user_id, trial_id)).fetchall()
                    if any(json.loads(row[0])["active"] for row in others):
                        raise ValueError("다른 작업 비교의 타이머가 진행 중입니다. 해당 기록을 열어 먼저 멈춰 주세요.")
                    record["active"] = {"arm": arm, "phase": phase, "since": self.clock()}
                elif active:
                    elapsed = self.clock() - active["since"]
                    if not math.isfinite(elapsed) or elapsed < 0:
                        raise ValueError("시계가 변경되었습니다. 기록을 확인해 주세요.")
                    target = record["arms"][active["arm"]]
                    target["seconds"][active["phase"]] += round(elapsed, 3)
                    target["timed"][active["phase"]] = True
                    record["active"] = None
            elif action == "result":
                if record["active"]:
                    raise ValueError("타이머를 멈춘 뒤 확인 결과를 저장해 주세요.")
                arm = body.get("arm")
                if arm not in ARMS or body.get("outcome") not in ("unverified", "pass", "fail", "blocked"):
                    raise ValueError("비교 조건과 기능 확인 결과를 선택해 주세요.")
                evidence = text(body.get("evidence", ""), "확인 명령·결과·근거", 4000, False)
                if body["outcome"] in ("pass", "fail") and not evidence:
                    raise ValueError("통과·실패에는 실행한 검사와 결과 근거를 적어 주세요.")
                passed, total = body.get("passed_tests"), body.get("total_tests")
                if passed is not None or total is not None:
                    if type(passed) is not int or type(total) is not int or not 0 <= passed <= total <= 100000 or total == 0:
                        raise ValueError("통과/전체 테스트 수를 확인해 주세요.")
                    if body["outcome"] == "pass" and passed != total:
                        raise ValueError("일부 테스트 실패를 전체 통과로 기록할 수 없습니다.")
                record["arms"][arm].update(outcome=body["outcome"], evidence=evidence,
                    answer=text(body.get("answer", ""), "보관할 답변", 20000, False), passed_tests=passed, total_tests=total)
            elif action == "preference":
                if body.get("preference") not in (*ARMS, "tie", "unselected"):
                    raise ValueError("더 편했던 답변 또는 비슷함을 선택해 주세요.")
                record.update(preference=body["preference"],
                              preference_reason=text(body.get("reason", ""), "선호 이유", 2000, False))
            else:
                raise ValueError("지원하지 않는 작업입니다.")
            for key in ("id", "revision", "updated_at"):
                record.pop(key, None)
            conn.execute("UPDATE coding_work_trials SET record_json=?,revision=revision+1,updated_at=? WHERE id=? AND owner_id=?",
                         (json.dumps(record, ensure_ascii=False), datetime.now(timezone.utc).isoformat(), trial_id, user_id))
        return self.get(user_id, trial_id)

"""한국어 요약의 사용자별 블라인드 평가. 준비/생성/응답 분석을 분리한다.

모의 응답을 사용자 근거로 만들지 않는다. --generate 없이는 API를 호출하지 않는다.
연구 자료와 응답은 git에서 제외된 data/korean_pilot 아래에 보관한다.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import secrets
from typing import Callable

CONDITIONS = ("direct", "selected")
FACTUALITY = ("not_assessed", "no_error_found", "error_found", "unsure")
SCHEMA_VERSION = 1


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def source_hash(text: str) -> str:
    return digest(" ".join(text.split()))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def nonempty(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}: 비어 있지 않은 문자열이 필요합니다")
    return value.strip()


def validate_protocol(raw: dict) -> dict:
    """같은 원문 재사용·가짜 시간·조건 누락을 생성 전에 거부한다."""
    p = json.loads(json.dumps(raw))
    if p.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("지원하지 않는 protocol 버전")
    if not re.fullmatch(r"P[0-9]{3,6}", p.get("participant_id", "")):
        raise ValueError("participant_id는 P001 같은 임의 ID여야 합니다")
    if type(p.get("is_test")) is not bool:
        raise ValueError("is_test를 true/false로 명시하세요")
    nonempty(p.get("model"), "model")
    if p.get("temperature") != 0 or isinstance(p.get("temperature"), bool):
        raise ValueError("현재 비교는 두 조건 모두 temperature=0으로 고정합니다")
    prompts = p.get("prompts", {})
    if set(prompts) != set(CONDITIONS):
        raise ValueError("direct와 selected 프롬프트가 모두 필요합니다")
    for condition in CONDITIONS:
        prompts[condition] = nonempty(prompts[condition], condition)
    if source_hash(prompts["direct"]) == source_hash(prompts["selected"]):
        raise ValueError("비교할 두 프롬프트가 동일합니다")
    if p.get("selection_rounds") != 8:
        raise ValueError("이 프로토콜은 8회 선택 조건입니다")
    if p.get("collection_order") not in ("direct_first", "selected_first"):
        raise ValueError("지침 수집 순서를 기록하세요")
    for value in p.get("effort_seconds", {}).values():
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            raise ValueError("측정 시간은 0 이상의 유한 수 또는 null이어야 합니다")
    if set(p.get("effort_seconds", {})) != set(CONDITIONS):
        raise ValueError("두 조건의 effort_seconds를 기록하세요. 미측정은 null입니다")
    calibration = p.get("calibration_sources", [])
    if not isinstance(calibration, list) or not calibration:
        raise ValueError("선호 수집에 사용한 원문이 필요합니다")
    seen = {source_hash(nonempty(text, "calibration_source")) for text in calibration}
    documents = p.get("documents", [])
    if not isinstance(documents, list) or not 1 <= len(documents) <= 20:
        raise ValueError("평가 문서는 1~20개여야 합니다 (파일럿 권장 3개)")
    ids = set()
    for doc in documents:
        doc_id = nonempty(doc.get("id"), "document id")
        if doc_id in ids:
            raise ValueError("문서 ID가 중복됐습니다")
        ids.add(doc_id)
        source = nonempty(doc.get("source"), "source")
        if len(source) > 12000:
            raise ValueError("평가 원문은 12,000자 이내로 제한합니다")
        hashed = source_hash(source)
        if hashed in seen:
            raise ValueError("선호 수집 원문과 평가 원문이 겹치거나 평가 원문이 중복됐습니다")
        seen.add(hashed)
        facts = doc.get("must_keep")
        if not isinstance(facts, list) or not facts:
            raise ValueError("생성 전에 보존할 핵심 사실 목록을 정하세요")
        for fact in facts:
            nonempty(fact, "must_keep")
    return p


def plan(raw: dict) -> dict:
    p = validate_protocol(raw)
    return {"participant_id": p["participant_id"], "is_test": p["is_test"],
            "documents": len(p["documents"]), "max_generation_requests": 2 * len(p["documents"]),
            "model": p["model"], "temperature": p["temperature"],
            "note": "캐시 미스 기준 요청 수이며 토큰/금액 상한은 아닙니다. 아직 API를 호출하지 않았습니다."}


def prepare(raw: dict, root: Path, generate: Callable | None = None) -> Path:
    """사용자별 동결된 protocol + 재개 가능한 생성 + 분리된 블라인드 패킷.

    generate는 테스트에서만 대체한다. 실제 호출은 기존 generator 캐시를 사용한다.
    같은 연구 폴더에 대한 동시 실행은 지원하지 않는다.
    """
    p = validate_protocol(raw)
    folder = root / p["participant_id"]
    private_path = folder / "private.json"
    if private_path.exists():
        private = read_json(private_path)
        if private["protocol"] != p:
            raise ValueError("이미 동결된 protocol과 다릅니다. 원본을 덮어쓰지 말고 새 연구 폴더를 사용하세요")
    else:
        n = len(p["documents"])
        first = secrets.choice(CONDITIONS)
        other = next(c for c in CONDITIONS if c != first)
        orientations = [first] * ((n + 1) // 2) + [other] * (n // 2)
        secrets.SystemRandom().shuffle(orientations)
        private = {"schema_version": SCHEMA_VERSION, "study_id": secrets.token_hex(16),
                   "protocol": p, "protocol_hash": digest(p), "cases": []}
        for index, (doc, first) in enumerate(zip(p["documents"], orientations)):
            second = next(c for c in CONDITIONS if c != first)
            private["cases"].append({"case_id": f"case-{index + 1:02}", "document_id": doc["id"],
                                     "mapping": {"A": first, "B": second}, "outputs": {}})
        save_json(private_path, private)
    if generate is None:
        from engine.generator import generate_with_prompt
        generate = generate_with_prompt
    for doc, case in zip(p["documents"], private["cases"]):
        for condition in CONDITIONS:
            if condition in case["outputs"]:
                continue
            try:
                output = generate(p["prompts"][condition], doc["source"], model=p["model"],
                                  temperature=p["temperature"], cache_dir=folder / "cache")
                nonempty(output, "generated output")
            except Exception as exc:
                # SDK의 원문/키가 섞일 수 있는 오류 문자열을 기록하거나 출력하지 않는다.
                raise RuntimeError(f"생성 실패 ({type(exc).__name__}). 완료된 결과는 보존됐으며 동일 명령으로 재개할 수 있습니다.") from None
            case["outputs"][condition] = output
            save_json(private_path, private)
    packet = {"schema_version": SCHEMA_VERSION, "study_id": private["study_id"],
              "is_test": p["is_test"], "cases": []}
    for doc, case in zip(p["documents"], private["cases"]):
        packet["cases"].append({"case_id": case["case_id"], "source": doc["source"],
                                "must_keep": doc["must_keep"],
                                "candidates": {side: case["outputs"][condition]
                                               for side, condition in case["mapping"].items()}})
    packet["packet_hash"] = digest(packet)
    private["packet_hash"] = packet["packet_hash"]
    save_json(private_path, private)
    packet_path = folder / "blind_packet.json"
    save_json(packet_path, packet)
    return packet_path


def validate_packet(packet: dict) -> None:
    """조건 대응표를 포함한 비공개 파일이 평가 화면에 표시되지 않도록 검사한다."""
    if set(packet) != {"schema_version", "study_id", "is_test", "cases", "packet_hash"}:
        raise ValueError("blind_packet.json을 선택하세요. private.json은 평가자에게 전달하지 않습니다")
    if packet["schema_version"] != SCHEMA_VERSION or type(packet["is_test"]) is not bool:
        raise ValueError("패킷 버전 또는 시험 구분이 올바르지 않습니다")
    if packet["packet_hash"] != digest({k: v for k, v in packet.items() if k != "packet_hash"}):
        raise ValueError("패킷이 변경됐습니다")
    if not isinstance(packet["cases"], list) or not packet["cases"]:
        raise ValueError("평가 사례가 없습니다")
    ids = set()
    for case in packet["cases"]:
        if set(case) != {"case_id", "source", "must_keep", "candidates"} or set(case["candidates"]) != {"A", "B"}:
            raise ValueError("평가 사례 형식이 올바르지 않습니다")
        if case["case_id"] in ids:
            raise ValueError("평가 사례가 중복됐습니다")
        ids.add(case["case_id"])
        nonempty(case["source"], "source")
        if not isinstance(case["must_keep"], list) or not case["must_keep"]:
            raise ValueError("핵심 사실 목록이 필요합니다")
        for fact in case["must_keep"]:
            nonempty(fact, "must_keep")
        for text in case["candidates"].values():
            nonempty(text, "candidate")


def validate_answers(packet: dict, answers: list[dict]) -> None:
    validate_packet(packet)
    cases = {c["case_id"]: c for c in packet["cases"]}
    seen = set()
    for answer in answers:
        cid = answer.get("case_id")
        if cid not in cases or cid in seen:
            raise ValueError("알 수 없거나 중복된 평가 사례입니다")
        seen.add(cid)
        if answer.get("preference") not in ("A", "B", "tie", "neither"):
            raise ValueError("모든 문서에서 선호를 선택해 주세요")
        if not isinstance(answer.get("reason", ""), str) or len(answer.get("reason", "")) > 1000:
            raise ValueError("이유는 1000자 이내로 입력해 주세요")
        quality = answer.get("quality", {})
        if set(quality) != {"A", "B"}:
            raise ValueError("A/B 두 결과의 품질 기록이 필요합니다")
        for q in quality.values():
            if q.get("factuality") not in FACTUALITY:
                raise ValueError("사실성 판정 값이 올바르지 않습니다")
            count = q.get("missing_points")
            if count is not None and (type(count) is not int or not 0 <= count <= len(cases[cid]["must_keep"])):
                raise ValueError("누락 수는 핵심 사실 수 이내여야 하며 미평가는 null입니다")
    if seen != set(cases):
        raise ValueError("모든 문서의 응답이 필요합니다. 미응답을 실패로 집계하지 않습니다")


def response_record(packet: dict, answers: list[dict]) -> dict:
    validate_answers(packet, answers)
    return {"schema_version": SCHEMA_VERSION, "study_id": packet["study_id"],
            "packet_hash": packet["packet_hash"], "is_test": packet["is_test"], "answers": answers}


def analyze(private: dict, packet: dict, response: dict) -> dict:
    validate_answers(packet, response.get("answers", []))
    if (response.get("schema_version") != SCHEMA_VERSION
            or response.get("study_id") != private["study_id"]
            or packet["study_id"] != private["study_id"]
            or response.get("packet_hash") != private.get("packet_hash")
            or packet["packet_hash"] != private.get("packet_hash")
            or response.get("is_test") is not private["protocol"]["is_test"]):
        raise ValueError("응답과 동결된 연구 패킷이 일치하지 않습니다")
    counts = Counter({c: 0 for c in (*CONDITIONS, "tie", "neither")})
    quality = {c: {"factuality": Counter(), "missing_points": [], "omission_unassessed": 0} for c in CONDITIONS}
    mappings = {c["case_id"]: c["mapping"] for c in private["cases"]}
    for answer in response["answers"]:
        mapping = mappings[answer["case_id"]]
        winner = answer["preference"]
        counts[mapping[winner] if winner in mapping else winner] += 1
        for side, q in answer["quality"].items():
            bucket = quality[mapping[side]]
            bucket["factuality"][q["factuality"]] += 1
            if q["missing_points"] is None:
                bucket["omission_unassessed"] += 1
            else:
                bucket["missing_points"].append(q["missing_points"])
    return {"schema_version": SCHEMA_VERSION, "participant_id": private["protocol"]["participant_id"],
            "study_id": private["study_id"], "is_test": private["protocol"]["is_test"],
            "model": private["protocol"]["model"], "documents": len(response["answers"]),
            "preference_counts": dict(counts), "quality": quality,
            "effort_seconds": private["protocol"]["effort_seconds"],
            "collection_order": private["protocol"]["collection_order"]}


def summarize(results: list[dict]) -> dict:
    included = [r for r in results if r["is_test"] is False]
    ids = [r["participant_id"] for r in included]
    if len(set(ids)) != len(ids):
        raise ValueError("같은 참여자를 두 번 집계할 수 없습니다")
    if len({r["model"] for r in included}) > 1:
        raise ValueError("모델이 다른 실험은 나누어 집계하세요")
    per_user = []
    for r in included:
        counts = r["preference_counts"]
        per_user.append({"participant_id": r["participant_id"],
                         "documents": r["documents"], "preference_counts": counts,
                         "selected_share_including_ties": counts["selected"] / r["documents"],
                         "effort_seconds": r["effort_seconds"], "quality": r["quality"]})
    return {"participants": len(included), "excluded_test_records": len(results) - len(included),
            "per_participant": per_user,
            "mean_selected_share": (sum(r["selected_share_including_ties"] for r in per_user) / len(per_user) if per_user else None),
            "note": "탐색적 기술 통계입니다. 문서 수를 독립 참여자 수로 세지 않으며 유의성/선호 복원율을 주장하지 않습니다."}


def prepare_demo(root: Path) -> Path:
    """수기 예시의 앞 문장을 보여주는 UI 연습용 패킷. 연구 결과가 아니다."""
    template = Path(__file__).resolve().parents[1] / "docs" / "korean_pilot" / "protocol.example.json"
    p = read_json(template)
    p["is_test"] = True
    p["model"] = "no-api-demo"
    def example_output(prompt, source, **kwargs):
        count = 1 if prompt == p["prompts"]["direct"] else 2
        sentences = re.split(r"(?<=[.!?])\s+", source)
        return " ".join(sentences[:count])
    return prepare(p, root, generate=example_output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("prepare")
    create.add_argument("protocol", type=Path)
    create.add_argument("--root", type=Path, default=Path("data/korean_pilot"))
    create.add_argument("--generate", action="store_true", help="실제 API 생성 허용. 없으면 계획만 출력")
    demo = sub.add_parser("demo", help="API 없는 평가 화면 연습용 자료 만들기")
    demo.add_argument("--root", type=Path, default=Path("data/korean_pilot_demo"))
    review = sub.add_parser("analyze")
    review.add_argument("study_folder", type=Path)
    review.add_argument("ratings", type=Path)
    aggregate = sub.add_parser("summarize")
    aggregate.add_argument("results", type=Path, nargs="+")
    args = parser.parse_args()
    if args.command == "prepare":
        protocol = read_json(args.protocol)
        print(json.dumps(plan(protocol), ensure_ascii=False, indent=2))
        if args.generate:
            from dotenv import load_dotenv
            load_dotenv()
            print(prepare(protocol, args.root))
    elif args.command == "demo":
        print(prepare_demo(args.root))
        print("시험용 패킷입니다. 실제 선호 추정이나 모델 생성 결과가 아니며 집계에서 제외됩니다.")
    elif args.command == "analyze":
        folder = args.study_folder
        result = analyze(read_json(folder / "private.json"), read_json(folder / "blind_packet.json"), read_json(args.ratings))
        save_json(folder / "result.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(summarize([read_json(p) for p in args.results]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

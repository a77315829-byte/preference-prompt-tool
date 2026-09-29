"""연구용 블라인드 평가 화면. 실행: streamlit run pilot_review.py

후보를 생성하거나 API를 호출하지 않는다. 준비된 패킷을 읽고 응답 파일을 내려준다.
공개 app.py와 분리한다. 원문을 다루므로 연구자가 로컬에서 실행하는 것을 기본으로 한다.
"""
from __future__ import annotations

import json

import streamlit as st

from experiments.korean_pilot import FACTUALITY, response_record, validate_packet

PREFERENCE_LABELS = {"A": "A가 더 좋음", "B": "B가 더 좋음", "tie": "비슷함", "neither": "둘 다 원하지 않음"}
FACT_LABELS = {
    "not_assessed": "평가하지 않음",
    "no_error_found": "확인한 범위에서 오류를 찾지 못함",
    "error_found": "사실 오류를 발견함",
    "unsure": "판단하기 어려움",
}
MAX_PACKET_BYTES = 2_000_000


def render_packet(packet: dict) -> None:
    validate_packet(packet)
    if packet["is_test"]:
        st.warning("시험용 자료입니다. 응답은 실사용자 성과 집계에서 제외됩니다.")
    st.caption("각 요약을 원문과 대조하고, 선호와 내용 품질을 따로 평가해 주세요. 방식 이름은 평가 완료 전 공개하지 않습니다.")
    answers = []
    with st.form(f"ratings-{packet['packet_hash']}"):
        for index, case in enumerate(packet["cases"], 1):
            cid = case["case_id"]
            st.subheader(f"문서 {index}")
            with st.expander("원문과 보존할 핵심 사실", expanded=True):
                st.text(case["source"])
                for number, fact in enumerate(case["must_keep"], 1):
                    st.text(f"{number}. {fact}")
            quality = {}
            for col, side in zip(st.columns(2), ("A", "B")):
                with col:
                    st.markdown(f"**요약 {side}**")
                    with st.container(border=True, height=260):
                        st.text(case["candidates"][side])
                    factuality = st.selectbox(
                        f"{side} 사실성", FACTUALITY,
                        format_func=lambda value: FACT_LABELS[value], key=f"{cid}-{side}-fact-{packet['packet_hash']}",
                    )
                    missing = st.selectbox(
                        f"{side} 빠진 핵심 사실 수", [None, *range(len(case["must_keep"]) + 1)],
                        format_func=lambda value: "평가하지 않음" if value is None else str(value),
                        key=f"{cid}-{side}-missing-{packet['packet_hash']}",
                    )
                    quality[side] = {"factuality": factuality, "missing_points": missing}
            preference = st.radio(
                "내가 쓰고 싶은 요약", tuple(PREFERENCE_LABELS), index=None,
                format_func=lambda value: PREFERENCE_LABELS[value], key=f"{cid}-preference-{packet['packet_hash']}",
            )
            reason = st.text_area("선택 이유 또는 오류 위치 (선택)", max_chars=1000, key=f"{cid}-reason-{packet['packet_hash']}")
            answers.append({"case_id": cid, "preference": preference, "quality": quality, "reason": reason})
        confirmed = st.checkbox("평가 결과를 연구 담당자에게 전달하는 데 동의합니다. 응답에 개인정보를 적지 않았습니다.")
        submitted = st.form_submit_button("응답 파일 준비")
    if submitted:
        st.session_state.pop("pilot_response", None)
        if not confirmed:
            st.error("응답 전달 동의를 확인해 주세요.")
        else:
            try:
                st.session_state.pilot_response = response_record(packet, answers)
            except ValueError as exc:
                st.error(str(exc))
    record = st.session_state.get("pilot_response")
    if record and record["packet_hash"] == packet["packet_hash"]:
        st.success("응답 파일을 내려받아 연구 담당자에게 전달해 주세요. 자동 전송하거나 서버 파일로 저장하지 않습니다.")
        st.download_button(
            "응답 JSON 다운로드", json.dumps(record, ensure_ascii=False, indent=2),
            file_name=f"ratings-{packet['study_id']}.json", mime="application/json",
        )


def main() -> None:
    st.set_page_config(page_title="한국어 요약 비교 평가", layout="wide")
    st.title("한국어 요약 비교 평가")
    st.caption("준비된 요약을 읽고 평가하는 화면입니다. 모델 API를 호출하지 않습니다. 업로드한 파일은 이 Streamlit 서버에서 처리합니다.")
    uploaded = st.file_uploader("연구 담당자에게 받은 blind_packet.json", type="json")
    if uploaded is None:
        st.info("private.json은 조건 대응표를 포함하므로 이 화면에 넣거나 평가자에게 전달하지 마세요.")
        return
    if uploaded.size > MAX_PACKET_BYTES:
        st.error("평가 파일은 2MB 이내로 제한합니다.")
        return
    try:
        packet = json.loads(uploaded.getvalue().decode("utf-8-sig"))
        render_packet(packet)
    except (ValueError, KeyError, TypeError, AttributeError):
        st.error("평가 파일 형식이 맞지 않거나 파일이 변경됐습니다. 원본 blind_packet.json을 확인해 주세요.")


if __name__ == "__main__":
    main()
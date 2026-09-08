"""1주차 관통용 스크립트: MACSum 원문 하나에 대해 서로 다른 속성 조합의
사람 작성 요약이 실제로 어떻게 다른지 눈으로 확인한다."""

import json
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "macsum" / "dataset" / "macdoc" / "val.json"


def main() -> None:
    records = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    record = records[0]

    source_text = " ".join(record["source"])

    print("=" * 80)
    print(f"[source] ({record['metadata']['dataset']}, file_id={record['metadata']['file_id']})")
    print(source_text[:500] + " ...")
    print("=" * 80)

    for ref in record["references"]:
        attrs = ref["control_attribute"]
        attrs_str = ", ".join(f"{k}={v}" for k, v in attrs.items() if v)
        print(f"\n--- {attrs_str} ---")
        print(f"title: {ref['title']}")
        print(ref["summary"])


if __name__ == "__main__":
    main()

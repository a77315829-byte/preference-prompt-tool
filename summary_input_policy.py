"""Shared source-size policy for document-summary HTTP entry points."""

SUMMARY_DOMAINS = frozenset({"summarization", "summarization_ko", "summarization_hybrid"})
MAX_SOURCE_CHARS = 12_000
MAX_TOPIC_CHARS = 300


def validate_summary_source(value):
    """Count Unicode code points including surrounding whitespace; never truncate."""
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_SOURCE_CHARS:
        raise ValueError("원문은 1~12,000자로 입력해 주세요. 넘친 내용을 자동으로 자르지 않습니다.")
    return value.strip()


def input_policy():
    return {"max_source_chars": MAX_SOURCE_CHARS, "max_topic_chars": MAX_TOPIC_CHARS,
            "count_unit": "unicode_code_points", "includes_whitespace": True,
            "over_limit": "reject_without_truncation"}

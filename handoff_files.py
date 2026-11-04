"""인수인계 첨부 검증. 파일 이름을 디스크 경로로 사용하거나 파일을 실행하지 않는다."""
import base64
import binascii

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_STORED_BYTES = 20 * 1024 * 1024
MAX_FILES = 10
MAX_UPLOAD_JSON = ((MAX_FILE_BYTES + 2) // 3) * 4 + 4096


def preview_type(data):
    # 클라이언트의 MIME/확장자를 신뢰하지 않는다. HTML/SVG도 텍스트로만 연다.
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "application/octet-stream"
    if any(ord(c) < 32 and c not in "\t\n\r" for c in text):
        return "application/octet-stream"
    return "text/plain; charset=utf-8"


def upload_fields(raw):
    name = raw.get("name")
    if (not isinstance(name, str) or not name.strip() or len(name) > 180
            or name.strip() in (".", "..") or any(c in '/\\:<>"|?*' or ord(c) < 32 or ord(c) == 127 for c in name)):
        raise ValueError("파일 이름을 확인해 주세요. 경로 없이 180자 이내의 이름을 사용합니다.")
    encoded = raw.get("data")
    if not isinstance(encoded, str) or len(encoded) > ((MAX_FILE_BYTES + 2) // 3) * 4:
        raise ValueError("파일은 하나당 5MB까지 첨부할 수 있습니다.")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("파일 내용을 읽지 못했습니다. 다시 선택해 주세요.") from exc
    if not data or len(data) > MAX_FILE_BYTES:
        raise ValueError("빈 파일은 첨부할 수 없으며 파일은 하나당 5MB까지입니다.")
    return name.strip(), data, preview_type(data)

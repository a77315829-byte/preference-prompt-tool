"""Check report facts and render inventory, then prepare visual QA sheets."""
from pathlib import Path
import hashlib
import json
from PIL import Image, ImageOps, ImageDraw
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[3]
QA = ROOT / "tmp/weekly_2026_11_13/v0_6"
OUT = ROOT / "output/pdf/Revealed_진행현황_주간보고서_v0.6.pdf"
data = json.loads((ROOT / "docs/verification/2026-11-12/ci/results.json").read_text(encoding="utf-8"))
reader = PdfReader(OUT)
assert len(reader.pages) == 32
assert all(page.mediabox.width == 780 and page.mediabox.height == 540 for page in reader.pages)
texts = [page.extract_text() for page in reader.pages]
assert "v0.6" in texts[0] and "2026.11.13" in texts[0]
assert "1,355" in texts[2] and "CI 1,353" in texts[2] and "자료 검사 3개 통과" in texts[2]
assert "4묶음" in texts[2] and "네 묶음 모두" in texts[4]
assert "13~14쪽" in texts[3] and "15~32쪽" in texts[3]
assert "로컬·CI 회귀 통과" in texts[1] and "최신 전체 재검사 필요" not in texts[1]
assert "18/18" in texts[10] and "1,355" in texts[11]
assert "1,353" in texts[12] and "3 건너뜀" in texts[12] and "16 API 제외" in texts[12]
assert "165.80초" in texts[12] and "208.07초" in texts[12]
assert data["focused_rerun"]["seconds"] == 6.55
assert "3/3 통과" in texts[13] and "6.55초" in texts[13] and "네트워크 차단" in texts[13]
assert "외부 연결 시도 0회·유료 모델 API 0회" in texts[13]
assert "542과제" in texts[13] and "실행 검증은 아님" in texts[13]
assert "c784808" in texts[12] and "별도 실행" in texts[12]
assert all("현재 실적·계획·판정은 3~14쪽" in text for text in texts[14:])
assert not any("마이크로스톤 구현" in text for text in texts)
uris = [str(annotation.get_object().get("/A", {}).get("/URI", ""))
        for annotation in reader.pages[12].get("/Annots", [])]
assert all(run["url"] in uris for run in data["runs"].values())
prior = ROOT / "output/pdf/Revealed_진행현황_주간보고서_v0.5.pdf"
assert hashlib.sha256(prior.read_bytes()).hexdigest() == "be07f9ec3ab0f7f47f3c1a2a148479e4d545bc9ff66bff3e371bc039c304da6c"
files = sorted(QA.glob("page-*.png"))
assert len(files) == 32
for name, start, end, cols, tw, th in [("current", 0, 14, 2, 620, 450), ("history", 14, 32, 3, 420, 310)]:
    group = files[start:end]
    sheet = Image.new("RGB", (cols * tw, ((len(group) + cols - 1) // cols) * th), "#d9dee4")
    draw = ImageDraw.Draw(sheet)
    for i, path in enumerate(group):
        x, y = (i % cols) * tw, (i // cols) * th
        with Image.open(path) as source:
            preview = ImageOps.contain(source.convert("RGB"), (tw - 12, th - 26))
        sheet.paste(preview, (x + 6, y + 22))
        draw.text((x + 8, y + 5), f"Page {i + start + 1}", fill="black")
    sheet.save(QA / f"contact-{name}.png")
checks = {"pages": 32, "ci_and_rerun_metrics_match": True, "all_pages_rendered": True,
          "ci_links_present": True, "previous_report_unchanged": True,
          "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest()}
(QA / "text_checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
print(json.dumps(checks))

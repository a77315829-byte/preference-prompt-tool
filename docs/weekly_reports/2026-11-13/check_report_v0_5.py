"""PDF text/layout assertions and contact sheets; visual QA follows separately."""
from pathlib import Path
import hashlib
import json
from PIL import Image, ImageOps, ImageDraw
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[3]
QA=ROOT/"tmp/weekly_2026_11_13/v0_5"
OUT=ROOT/"output/pdf/Revealed_진행현황_주간보고서_v0.5.pdf"
data=json.loads((ROOT/"docs/verification/2026-11-12/results.json").read_text(encoding="utf-8"))
reader=PdfReader(OUT)
assert len(reader.pages)==30
texts=[page.extract_text() for page in reader.pages]
assert all(p.mediabox.width==780 and p.mediabox.height==540 for p in reader.pages)
assert "v0.5" in texts[0] and "2026.11.13" in texts[0]
assert f'{data["backend"]["passed"]:,}' in texts[2] and f'{data["frontend"]["passed"]}개' in texts[2]
assert "4묶음" in texts[2] and "네 묶음 모두" in texts[4] and texts[4].count("완료") >= 5
assert "18/18" in texts[10] and "16개 제외" in texts[11] and "1개 건너뜀" in texts[11]
assert "최신 전체 재검사 필요" not in texts[1]
assert not any("마이크로스톤 구현" in text for text in texts)
files=sorted(QA.glob("page-*.png"))
assert len(files)==30
for name,start,end,cols,tw,th in [("current",0,12,2,620,450),("history",12,30,3,420,310)]:
    group=files[start:end]
    sheet=Image.new("RGB",(cols*tw,((len(group)+cols-1)//cols)*th),"#d9dee4")
    draw=ImageDraw.Draw(sheet)
    for i,path in enumerate(group):
        x=(i%cols)*tw;y=(i//cols)*th
        with Image.open(path) as src:preview=ImageOps.contain(src.convert("RGB"),(tw-12,th-26))
        sheet.paste(preview,(x+6,y+22));draw.text((x+8,y+5),f"Page {i+start+1}",fill="black")
    sheet.save(QA/f"contact-{name}.png")
checks={"pages":30,"current_metrics_match_results":True,"all_pages_rendered":True,"sha256":hashlib.sha256(OUT.read_bytes()).hexdigest()}
(QA/"text_checks.json").write_text(json.dumps(checks,indent=2),encoding="utf-8")
print(json.dumps(checks))

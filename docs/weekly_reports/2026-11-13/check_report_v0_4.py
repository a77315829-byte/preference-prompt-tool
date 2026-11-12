"""Check the generated weekly PDF and create sheets for visual inspection."""
from pathlib import Path
import json
import hashlib
from pypdf import PdfReader
from PIL import Image, ImageOps, ImageDraw

ROOT=Path(__file__).resolve().parents[3]
QA=ROOT/"tmp/weekly_2026_11_13/v0_4"
OUT=ROOT/"output/pdf/Revealed_진행현황_주간보고서_v0.4.pdf"
pdf=PdfReader(OUT)
assert len(pdf.pages)==28
texts=[page.extract_text() for page in pdf.pages]
assert all(page.mediabox.width==780 and page.mediabox.height==540 for page in pdf.pages)
assert "2026.11.13" in texts[0] and "10주차" in texts[0] and "v0.4" in texts[0]
assert "11/07 ~ 11/13" in texts[2] and "11/14 ~ 11/20" in texts[2]
assert "2묶음 완료" in texts[2] and "2묶음 일부 완료" in texts[2]
assert texts[5].count("25/27")==6 and "0.7778" in texts[5]
assert texts[6].count("69/69")==3 and texts[6].count("56/56")==3
assert "97쪽" in texts[7] and "90개" in texts[7]
assert not any("마이크로스톤 구현" in text for text in texts)
for i in range(10,28):
    assert f"11/06 v0.3 원문 {i-5}쪽" in texts[i]
files=sorted(QA.glob("page-*.png"))
assert len(files)==28, len(files)
for name,start,end in [("current",0,10),("history",10,28)]:
    group=files[start:end]
    cols=2 if name=="current" else 3
    tw=620 if name=="current" else 420
    th=450 if name=="current" else 310
    sheet=Image.new("RGB",(cols*tw,((len(group)+cols-1)//cols)*th),"#d9dee4")
    draw=ImageDraw.Draw(sheet)
    for i,path in enumerate(group):
        x=(i%cols)*tw
        y=(i//cols)*th
        with Image.open(path) as src:
            preview=ImageOps.contain(src.convert("RGB"),(tw-12,th-26))
        sheet.paste(preview,(x+6,y+22))
        draw.text((x+8,y+5),f"Page {i+start+1}",fill="black")
    sheet.save(QA/f"contact-{name}.png")
checks={"pages":len(pdf.pages),"size_pt":[780,540],"current_numeric_text":True,
        "historical_labels":True,"rendered_pages":len(files),"sha256":hashlib.sha256(OUT.read_bytes()).hexdigest()}
(QA/"text_checks.json").write_text(json.dumps(checks,indent=2),encoding="utf-8")
print(json.dumps(checks,indent=2))

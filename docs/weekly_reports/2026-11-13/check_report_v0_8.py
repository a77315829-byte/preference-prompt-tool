"""Verify four groups, blank fields, unchanged dates/backups, and final rendering."""
from pathlib import Path
import hashlib
import json
import sys
import pdfplumber
from pypdf import PdfReader
from PIL import Image, ImageDraw, ImageOps

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
QA=ROOT/'tmp/weekly_2026_11_13/v0_8'
OUT=ROOT/'output/pdf/Revealed_진행현황_주간보고서_v0.8.pdf'
PREVIOUS=ROOT/'output/pdf/Revealed_진행현황_주간보고서_v0.7.pdf'
manifest=json.loads((QA/'build_manifest.json').read_text(encoding='utf-8'))
old,new=PdfReader(PREVIOUS),PdfReader(OUT)
assert len(old.pages)==len(new.pages)==11
texts=[page.extract_text() for page in new.pages]
assert all(list(p.mediabox)==[0,0,780,540] for p in new.pages)
for i,(a,b) in enumerate(zip(old.pages,new.pages)):
    if i!=2:
        assert a.extract_text().replace('v0.7','v0.8')==texts[i],i+1
    before=[str(ref.get_object().get('/A',{}).get('/URI','')) for ref in a.get('/Annots',[])]
    after=[str(ref.get_object().get('/A',{}).get('/URI','')) for ref in b.get('/Annots',[])]
    assert before==after,i+1
assert 'v0.8' in texts[0] and all('v0.8' in text for text in texts[1:])
for text in [texts[0],texts[2]]:
    assert '11/06 ~ 11/12' in text and '11/13 ~ 11/19' in text
with pdfplumber.open(PREVIOUS) as old_pdf,pdfplumber.open(OUT) as new_pdf:
    page=new_pdf.pages[2]
    assert not (page.crop((34,430,746,494)).extract_text() or '').strip()
    right=(390,84,746,400)
    assert old_pdf.pages[2].crop(right).extract_text()==page.crop(right).extract_text()
    groups=manifest['achievement_groups']
    for i,title in enumerate(groups):
        top=124+i*68
        assert page.crop((50,top,334,top+20)).extract_text().strip()==title
assert '주요 이슈 및 의사결정 사항' in texts[2] and '프로젝트 요청 사항' in texts[2]
assert all(value in texts[2] for value in ['9원문','8과제','18시나리오','1,399','129','수동 대비 동률'])
assert 'GitHub 주소와 분석·설계서 위치' in texts[-1]
assert hashlib.sha256(PREVIOUS.read_bytes()).hexdigest()==manifest['previous_pdf_sha256']
assert hashlib.sha256(OUT.read_bytes()).hexdigest()==manifest['sha256']
images=sorted(QA.glob('page-*.png'))
assert len(images)==11
for start in range(0,len(images),4):
    contact=Image.new('RGB',(1800,1320),'#dfe4e9');draw=ImageDraw.Draw(contact)
    for i,path in enumerate(images[start:start+4]):
        preview=ImageOps.contain(Image.open(path).convert('RGB'),(890,620))
        x=(i%2)*900;y=(i//2)*660
        contact.paste(preview,(x+5,y+25));draw.text((x+12,y+5),f'Page {start+i+1}',fill='black')
    contact.save(QA/f'contact-{start//4+1}.jpg',quality=92)
result={**manifest,'four_groups_verified':True,'blank_fields_verified_by_coordinates':True,
        'next_plan_and_dates_preserved':True,'other_page_text_preserved_except_version':True,
        'all_pdf_links_preserved':True,'all_pages_rendered':True,
        'visual_review':'completed' if '--visual-reviewed' in sys.argv else 'pending'}
(HERE/'validation_v0_8.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:result[k] for k in ['pages','four_groups_verified','blank_fields_verified_by_coordinates','next_plan_and_dates_preserved','visual_review']}))

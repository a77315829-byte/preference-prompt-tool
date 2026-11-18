"""Check dates, evidence, blank template fields, WBS position and rendered pages."""
from pathlib import Path
import hashlib
import json
import sys

import pdfplumber
from PIL import Image, ImageDraw, ImageOps
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
QA=ROOT/'tmp/weekly_2026_11_20/v0_11'
manifest=json.loads((QA/'build_manifest.json').read_text(encoding='utf-8'))
path=ROOT/manifest['output']
pdf=PdfReader(path)
texts=[page.extract_text() for page in pdf.pages]
assert len(texts)==13 and all(list(page.mediabox)==[0,0,780,540] for page in pdf.pages)
assert '2026.11.20' in texts[0] and '11주차' in texts[0]
assert '11/18까지' in texts[0]
for i in (0,2):
    assert '11/13 ~ 11/19' in texts[i] and '11/20 ~ 11/26' in texts[i]
assert all('v0.11' in t for t in texts)
assert all('11/06~11/12' not in t and '11/06 ~ 11/12' not in t for t in texts)
assert all('확인 기준 11/18' in text for text in texts[1:])
assert '1. 프로젝트 일정 - WBS' in texts[1] and '2. 프로젝트 진행현황' in texts[2]
assert all('[Backup]' in text for text in texts[3:])
assert all('11/17' in texts[i] for i in range(4,9))
assert all(v in texts[6] for v in ['6/6','17/18','5/5','0/6','일부 생략','미사용 MACSum 영어 원문 6개'])
assert all(v in texts[7] for v in ['8/8','40/40','일본어 한 단어','미측정'])
assert all(v in texts[8] for v in ['1,440','137','6시나리오','16개 제외','1개 건너뜀','0bbff80','3/3','1,438'])
assert '1,440' not in texts[2] and '통합·회귀 검사' not in texts[2]
assert all(v in texts[9] for v in ['154쪽','16작업','79개','v3.4','진행 중'])
assert all(v in texts[10] for v in ['18쪽','16장','19.4초','합성 계정','Spaces','175쪽','6항목'])
assert '11/20 ~ 11/26' in texts[11]
assert all(v in texts[12] for v in ['GitHub 주소와 분석·설계서 위치','docs/system-design/',
    'docs/wbs/2026-11-18/','docs/final/2026-11-18/','636a766'])
with pdfplumber.open(path) as doc:
    page=doc.pages[2]
    assert not (page.crop((34,430,746,494)).extract_text() or '').strip()
    for i,title in enumerate(manifest['achievement_groups']):
        top=124+i*68
        assert page.crop((50,top,334,top+20)).extract_text().strip()==title
    wbs=json.loads((ROOT/'docs/wbs/2026-11-18/wbs-v3.4.json').read_text(encoding='utf-8'))
    for task in wbs['tasks']: assert task['name'] in texts[1]
    teal=tuple(v/255 for v in (0x15,0x8c,0x80))
    bars=[r for r in doc.pages[1].rects if r['non_stroking_color'] and
          len(r['non_stroking_color'])==3 and all(abs(a-b)<0.001 for a,b in zip(r['non_stroking_color'],teal))
          and 151<=r['top']<455]
    assert len(bars)==len(manifest['highlighted_wbs_ids'])==12
    assert all(abs(r['x0']-(345+9*401/15+5))<0.01 for r in bars)
    boundary_issues=[]
    for i,p in enumerate(doc.pages):
        for char in p.chars:
            if char['x0'] < -0.1 or char['x1'] > 780.1 or char['top'] < -0.1 or char['bottom'] > 540.1:
                boundary_issues.append((i+1,char['text']))
    assert not boundary_issues,boundary_issues[:10]
uris=[str(ref.get_object().get('/A',{}).get('/URI','')) for page in pdf.pages for ref in page.get('/Annots',[])]
assert len(uris)==4 and all(uri.startswith('https://github.com/a77315829-byte/preference-prompt-tool') for uri in uris)
assert all('917e8e4' not in uri for uri in uris)
assert hashlib.sha256(path.read_bytes()).hexdigest()==manifest['sha256']
assert hashlib.sha256((ROOT/manifest['copy']).read_bytes()).hexdigest()==manifest['sha256']
assert hashlib.sha256((ROOT/manifest['additional_copy']).read_bytes()).hexdigest()==manifest['sha256']
old=ROOT/'output/pdf/Revealed_진행현황_주간보고서_v0.10.pdf'
assert hashlib.sha256(old.read_bytes()).hexdigest()==manifest['previous_pdf_sha256']
images=sorted(QA.glob('page-*.png'))
assert len(images)==13
for start in range(0,len(images),4):
    contact=Image.new('RGB',(2000,1440),'#dfe4e9'); draw=ImageDraw.Draw(contact)
    for i,image_path in enumerate(images[start:start+4]):
        preview=ImageOps.contain(Image.open(image_path).convert('RGB'),(990,685))
        x=(i%2)*1000; y=(i//2)*720
        contact.paste(preview,(x+5,y+26)); draw.text((x+12,y+5),f'Page {start+i+1}',fill='black')
    contact.save(QA/f'contact-{start//4+1}.jpg',quality=94)
result={**manifest,'dates_and_cutoff_verified':True,'four_groups_verified':True,
        'blank_fields_verified_by_coordinates':True,'wbs_names_and_activity_column_verified':True,
        'evidence_counts_verified':True,'content_within_page_bounds':True,'links':uris,
        'copy_identical':True,'all_pages_rendered':True,
        'visual_review':'completed' if '--visual-reviewed' in sys.argv else 'pending'}
(HERE/'validation_v0_11.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({key:result[key] for key in ['pages','dates_and_cutoff_verified',
    'blank_fields_verified_by_coordinates','all_pages_rendered','visual_review']}))

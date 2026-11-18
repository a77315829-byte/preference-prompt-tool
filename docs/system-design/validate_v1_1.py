"""Read-only document checks and local QA images; no product database or model calls."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
from pypdf import PdfReader
from PIL import Image,ImageDraw,ImageFont
import openpyxl

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
QA=ROOT/'tmp/system-design-v1.1-final'
QA.mkdir(parents=True,exist_ok=True)
RUNTIME=Path('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1110-778-0_26.1110.778.0_x64__3k8sg7r9htsxt/dependencies')

def contacts(paths,prefix,cols=4,rows=4,thumb=(300,425)):
    font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',16)
    for offset in range(0,len(paths),cols*rows):
        sheet=Image.new('RGB',(cols*thumb[0],rows*(thumb[1]+26)),'#dfe4ed');draw=ImageDraw.Draw(sheet)
        for i,path in enumerate(paths[offset:offset+cols*rows]):
            im=Image.open(path).convert('RGB');im.thumbnail(thumb)
            x=(i%cols)*thumb[0];y=(i//cols)*(thumb[1]+26)
            sheet.paste(im,(x+(thumb[0]-im.width)//2,y));draw.text((x+8,y+thumb[1]+2),path.stem,fill='black',font=font)
        sheet.save(QA/f'{prefix}-{offset//(cols*rows)+1:02d}.jpg',quality=88)

def check():
    catalog=json.loads((HERE/'usecase-catalog.json').read_text(encoding='utf-8'))
    cases=catalog['usecases'];children=[c for u in cases for c in u['children']]
    assert len(cases)==24 and len(children)==79
    ids=[u['id'] for u in cases]+[c['id'] for c in children]
    assert len(set(ids))==len(ids) and all(re.fullmatch(r'UC-\d{2}(?:-\d{2})?',s) for s in ids)
    chapter=(HERE/'chapters/02-usecases.md').read_text(encoding='utf-8')
    refs=[]
    for p in sorted((HERE/'chapters').glob('*.md')):
        for ref in re.findall(r'!\[[^]]*\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
            target=(p.parent/ref).resolve();assert target.exists(),target;refs.append(target)
    assert len(set(refs))==77
    assert len(re.findall(r'^## UC-\d{2} ',chapter,re.M))==24
    for u in cases:
        assert f'## {u["id"]} {u["name"]}' in chapter
        assert (HERE/'diagrams'/f'{u["id"].lower()}-detail.png').exists()
        assert (HERE/'diagrams'/f'{u["id"].lower()}-flow.png').exists()
        diagram=PdfReader(HERE/'diagrams'/f'{u["id"].lower()}-detail.pdf').pages[0].extract_text()
        for child in u['children']:
            assert child['id'] in diagram and child['name'] in diagram
            assert f'| {child["id"]} | {child["name"]} |' in chapter
    pdf=HERE/'Revealed_Analysis_Design_v1.1.pdf';reader=PdfReader(pdf)
    texts=[p.extract_text() for p in reader.pages];joined='\n'.join(texts)
    assert all(ident in joined for ident in ids)
    assert '<!--' not in joined and '\ufffd' not in joined
    empty=[i+1 for i,t in enumerate(texts) if len(t.strip())<70];assert not empty,empty
    wbpath=ROOT/'outputs/wbs-20261112/Revealed_WBS_v3.1_보고서형.xlsx'
    old=openpyxl.load_workbook(ROOT/'outputs/wbs-20261112/Revealed_WBS_v3.0_보고서형.xlsx',data_only=False)
    wb=openpyxl.load_workbook(wbpath,data_only=False)
    assert wb.sheetnames==['WBS','간트차트','UC 연결표']
    for s,area in [('WBS','G8:K28'),('간트차트','A8:R23')]:
        for row in old[s][area]:
            for cell in row:assert wb[s][cell.coordinate].value==cell.value,(s,cell.coordinate)
    mapping=wb['UC 연결표'];known={str(wb['WBS'].cell(i,1).value) for i in range(8,29)}
    for i,u in enumerate(cases,7):
        assert mapping.cell(i,1).value==u['id'] and mapping.cell(i,2).value==u['name']
        assert mapping.cell(i,4).value==u['wbs'] and u['wbs'] in known
    wpdf=ROOT/'output/pdf/Revealed_WBS_v3.1_보고서형.pdf'
    assert len(PdfReader(wpdf).pages)==3
    result=dict(version='1.1',date='2026-11-13',code_basis='cfd1fe4',parent_cases=24,child_cases=79,
        numbered_ids_unique=True,all_child_names_in_diagrams_and_tables=True,referenced_diagrams=77,
        pages=len(texts),all_ids_in_pdf=True,empty_pages=[],wbs_phases=5,wbs_activities=16,wbs_mapping_coverage=24,
        wbs_dates_status_formulas_preserved=True,paid_model_api_calls=0,application_code_changed=False,
        product_regression_rerun=False,visual_review='pending',sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [pdf,wpdf,wbpath]},
        references=['https://www.omg.org/spec/UML/2.5.1 (18.1.3, printed pp.639-641)', 'https://www.pmi.org/standards/work-breakdown-structures-third-edition'])
    (HERE/'validation-v1.1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (QA/'page-text-map.json').write_text(json.dumps([dict(page=i+1,start=t[:180]) for i,t in enumerate(texts)],ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('sha256','references')},ensure_ascii=False))
    if '--render' in sys.argv:
        poppler=RUNTIME/'native/poppler/Library/bin/pdftoppm.exe'
        subprocess.run([str(poppler),'-scale-to','1050','-png',str(pdf),str(QA/'page')],check=True)
        subprocess.run([str(poppler),'-scale-to','1800','-png',str(wpdf),str(QA/'wbs')],check=True)
        contacts(sorted(QA.glob('page-*.png')),'pages')
        contacts(sorted((HERE/'diagrams').glob('uc-*-detail.png')),'details',3,4,(480,300))
        contacts(sorted((HERE/'diagrams').glob('uc-*-flow.png')),'flows',3,4,(480,320))
        contacts(sorted((HERE/'diagrams').glob('uc-domain-*.png')),'domains',2,4,(620,400))
        print('All pages and diagram contact sheets rendered.')

if __name__=='__main__':check()

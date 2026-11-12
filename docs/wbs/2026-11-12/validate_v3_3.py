"""Validate WBS 3.3 and design 1.2 without model calls or application execution."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
from pypdf import PdfReader
from PIL import Image, ImageDraw
from openpyxl import load_workbook

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DESIGN = ROOT / 'docs/system-design'
QA = ROOT / 'tmp/system-design-v1.2-review'
RUNTIME = Path('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1110-778-0_26.1110.778.0_x64__3k8sg7r9htsxt/dependencies')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    QA.mkdir(parents=True, exist_ok=True)
    old, data = read(HERE/'wbs-v3.2.json'), read(HERE/'wbs-v3.3.json')
    catalog = read(DESIGN/'usecase-catalog.json')
    assert data['usecases'] == catalog['usecases']
    previous_catalog = json.loads(subprocess.check_output(['git','show','65978cb:docs/system-design/usecase-catalog.json'],cwd=ROOT).decode('utf-8'))
    for a,b in zip(previous_catalog['usecases'],catalog['usecases']):
        assert a == {k:v for k,v in b.items() if k!='related_wbs'}, a['id']
    assert len(data['tasks']) == 16 and len(data['groups']) == 5
    for a,b in zip(old['tasks'],data['tasks']):
        for key in ('id','name','group','start','end','predecessors','status','progress'):
            assert a[key] == b[key], (a['id'], key)
        assert a['github_first'] == b['repository_first']
    cases = catalog['usecases']
    children = [c for u in cases for c in u['children']]
    ids = [u['id'] for u in cases]+[c['id'] for c in children]
    assert len(cases)==24 and len(children)==79 and len(set(ids))==103
    assert all(re.fullmatch(r'UC-\d{2}(?:-\d{2})?',s) for s in ids)
    chapter = (DESIGN/'chapters/02-usecases.md').read_text(encoding='utf-8')
    for u in cases:
        section = chapter.split(f'## {u["id"]} {u["name"]}\n')[1].split('\n## UC-')[0]
        assert '주 구현 WBS '+u['wbs'] in section
        for link in u['related_wbs']:
            assert link['id']+' ('+link['role']+')' in section
        for child in u['children']:
            assert f'| {child["id"]} | {child["name"]} |' in section
    assert cases[1]['related_wbs'][0]['id']=='3.3'
    assert [x['id'] for x in cases[2]['related_wbs']]==['3.2','3.3']
    paths = [ROOT/'output/pdf/Revealed_WBS_v3.3_보고서형.pdf',
             ROOT/'outputs/wbs-20261112/Revealed_WBS_v3.3_보고서형.xlsx',
             DESIGN/'Revealed_Analysis_Design_v1.2.pdf']
    wb = load_workbook(paths[1]); before=load_workbook(ROOT/'outputs/wbs-20261112/Revealed_WBS_v3.2_보고서형.xlsx')
    cached = load_workbook(paths[1],data_only=True)
    assert wb.sheetnames==before.sheetnames==['WBS','간트차트','UC 연결표']
    formulas=0
    for sheet in before:
        after=wb[sheet.title]
        for row in sheet:
            for cell in row:
                if cell.data_type=='f':
                    assert after[cell.coordinate].value==cell.value
                    formulas+=1
        assert {str(m) for m in sheet.merged_cells.ranges}=={str(m) for m in after.merged_cells.ranges}
        assert sheet.freeze_panes==after.freeze_panes
        assert len(sheet.conditional_formatting)==len(after.conditional_formatting)
        old_dv=[(str(x.sqref),x.type,x.formula1,x.formula2) for x in sheet.data_validations.dataValidation]
        new_dv=[(str(x.sqref),x.type,x.formula1,x.formula2) for x in after.data_validations.dataValidation]
        assert old_dv==new_dv
    for area in ('G8:K28',):
        for row in before['WBS'][area]:
            for cell in row:
                assert wb['WBS'][cell.coordinate].value==cell.value
    assert cached['WBS']['I17'].value==35 and cached['WBS']['J17'].value==1
    assert wb['WBS']['L7'].value=='저장소 최초 추가일'
    assert 'UC-02·03' in wb['WBS']['E19'].value
    mapping=wb['UC 연결표']
    for row,u in enumerate(cases,7):
        assert [mapping.cell(row,c).value for c in (1,2,4)]==[u['id'],u['name'],u['wbs']]
        expected=' / '.join(x['id']+' ('+x['role']+')' for x in u['related_wbs']) or '-'
        assert mapping.cell(row,7).value==expected
    check=read(ROOT/'tmp/wbs-20261112/v3.3-workbook-check.json')
    assert check['inputEditsRecalculated'] and check['inputsRestored'] and 'matched 0 entries' in check['errorScan']
    wpages=PdfReader(paths[0]).pages
    assert len(wpages)==3
    wtext='\n'.join(p.extract_text() for p in wpages)
    assert '저장소 최초 추가일' in wtext and 'GitHub 최초 커밋' not in wtext and '3.3 예정' in wtext
    texts=[p.extract_text() for p in PdfReader(paths[2]).pages]
    joined='\n'.join(texts)
    assert all(i in joined for i in ids)
    assert not any(len(t.strip())<70 or '\ufffd' in t or '<!--' in t for t in texts)
    assert 'WBS v3.3' in joined and '주 구현 WBS' in joined and '보완 예정' in joined
    images=set()
    for chapter_path in (DESIGN/'chapters').glob('*.md'):
        for ref in re.findall(r'!\[[^]]*\]\(([^)]+)\)',chapter_path.read_text(encoding='utf-8')):
            target=(chapter_path.parent/ref).resolve(); assert target.exists(); images.add(target)
    assert len(images)==77
    for file,sha in read(HERE/'validation-v3.2.json')['sha256'].items():
        assert digest(ROOT/file)==sha, 'Previous v3.2 changed: '+file
    old_design=DESIGN/'Revealed_Analysis_Design_v1.1.pdf'
    assert digest(old_design)==read(DESIGN/'validation-v1.1.json')['sha256'][old_design.name]
    shared=dict(date='2026-11-13',code_basis='cfd1fe4',phases=5,activities=16,parent_cases=24,child_cases=79,
        primary_and_related_wbs_consistent=True,dates_status_dependencies_preserved=True,
        documentation_complete_vs_remaining_separated=True,repository_dates_preserved=True,
        formulas_preserved=formulas,formula_errors=0,input_edits_recalculated=True,formula_caches_present=True,
        workbook_native_features_preserved=True,opened_in_microsoft_excel=False,
        paid_model_api_calls=0,application_code_changed=False,product_regression_rerun=False,
        visual_review='completed' if '--visual-reviewed' in sys.argv else 'pending',
        sha256={p.relative_to(ROOT).as_posix():digest(p) for p in paths})
    (HERE/'validation-v3.3.json').write_text(json.dumps(dict(shared,version='3.3',pdf_pages=3,sheets=wb.sheetnames),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (DESIGN/'validation-v1.2.json').write_text(json.dumps(dict(shared,version='1.2',pages=len(texts),referenced_diagrams=77,all_uc_ids_in_pdf=True),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (QA/'page-text-map.json').write_text(json.dumps([dict(page=i+1,start=t[:200]) for i,t in enumerate(texts)],ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(pages=len(texts),wbs_pages=3,formulas_preserved=formulas,all_checks='passed'),ensure_ascii=False))
    if '--render' in sys.argv:
        poppler=RUNTIME/'native/poppler/Library/bin/pdftoppm.exe'
        subprocess.run([str(poppler),'-scale-to','2200','-png',str(paths[0]),str(QA/'wbs')],check=True)
        subprocess.run([str(poppler),'-scale-to','1050','-png',str(paths[2]),str(QA/'page')],check=True)
        pages=sorted(QA.glob('page-*.png'))
        for offset in range(0,len(pages),16):
            canvas=Image.new('RGB',(1200,1804),'#e5e8ee'); draw=ImageDraw.Draw(canvas)
            for i,p in enumerate(pages[offset:offset+16]):
                im=Image.open(p).convert('RGB'); im.thumbnail((300,425))
                x=(i%4)*300; y=(i//4)*451; canvas.paste(im,(x,y)); draw.text((x+5,y+429),p.stem,fill='black')
            canvas.save(QA/f'pages-{offset//16+1:02d}.jpg',quality=88)
        print('Rendered WBS 3 pages and all design pages.')


if __name__=='__main__':
    main()

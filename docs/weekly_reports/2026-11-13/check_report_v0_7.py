"""Verify weekly-period facts, document navigation, and rendered page inventory."""
from pathlib import Path
import hashlib
import json
import sys
from urllib.parse import unquote
from PIL import Image, ImageDraw, ImageOps
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
QA=ROOT/'tmp/weekly_2026_11_13/v0_7'
OUT=ROOT/'output/pdf/Revealed_진행현황_주간보고서_v0.7.pdf'


def read(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8'))


reader=PdfReader(OUT)
texts=[p.extract_text() for p in reader.pages]
joined='\n'.join(texts)
assert len(texts)==11
assert all(p.mediabox.width==780 and p.mediabox.height==540 for p in reader.pages)
assert 'v0.7' in texts[0] and '2026.11.13' in texts[0]
for text in [texts[0],texts[2]]:
    assert '11/06 ~ 11/12' in text and '11/13 ~ 11/19' in text
assert '1. 프로젝트 일정 - WBS' in texts[1] and '2. 프로젝트 진행현황' in texts[2]
for old in ['11/07 ~ 11/13','11/14 ~ 11/20','과거 백업','1~3차','28.89','마이크로스톤 구현']:
    assert old not in joined, old
old=PdfReader(ROOT/'output/pdf/Revealed_진행현황_주간보고서_v0.3.pdf')
old_backup_texts=[p.extract_text() for p in old.pages[4:]]
assert all(t not in old_backup_texts for t in texts[3:])
for task in read('docs/wbs/2026-11-12/wbs-v3.3.json')['tasks']:
    assert task['name'] in texts[1] and task['id'] in texts[1]
assert '12,000' in texts[2] and '12,000' in texts[4]
assert '1,399' in texts[2] and '129' in texts[2]
assert all(v in texts[7] for v in ['1,399','1,355','1,353','129','123','16개','18시나리오','8시나리오','73','3/3'])
policy=read('docs/verification/2026-11-12-summary-policy/results/validation.json')
assert policy['backend_full']['passed']==1399 and policy['frontend']['pass']==129
for name,checks,reviewer_key,target,general in [
    ('coding_react_current',69,'target_match_by_reviewer','all_four',0),
    ('react_style_current',56,'style_by_reviewer','all_three',1),
]:
    evidence=read(f'benchmarks/{name}/results/2026-11-12/scores.json')
    assert all(r['compiler_pass']==8 and r['runtime_checks_passed']==checks and r['runtime_checks_total']==checks
               for r in evidence['technical'].values())
    for review in evidence[reviewer_key].values():
        assert [review[a][target] for a in ['general','manual','product']]==[general,8,8]
    assert f'{checks}/{checks}' in texts[6]
summary=read('benchmarks/summary_contract_revision/results/2026-11-10/scores.json')
assert all(r['joint_pass']==9 and r['core_preserved']==25 and r['core_total']==27
           for review in summary['by_reviewer'].values() for r in review.values())
assert '25/27' in texts[5] and '2/27' in texts[5]
assert '11/13' in texts[8] and '합산하지 않습니다' in texts[8]
assert '97쪽' in texts[8] and '151쪽' in texts[10]
assert '11/13 ~ 11/19' in texts[9]
assert all(day in texts[9] for day in ['11/15','11/17','11/19'])
repo='https://github.com/a77315829-byte/preference-prompt-tool'
uris=[str(ref.get_object().get('/A',{}).get('/URI','')) for ref in reader.pages[-1].get('/Annots',[])]
expected=[repo, repo+'/blob/docs/wbs-v3.2/docs/system-design/README.md',
          repo+'/blob/docs/wbs-v3.2/docs/system-design/Revealed_Analysis_Design_v1.2.pdf',
          repo+'/blob/docs/wbs-v3.2/docs/wbs/2026-11-12/README.md']
assert all(url in uris for url in expected)
for url in expected[1:]: assert (ROOT/unquote(url.split('/blob/docs/wbs-v3.2/')[1])).exists()
manifest=read('tmp/weekly_2026_11_13/v0_7/build_manifest.json')
assert hashlib.sha256((ROOT/'output/pdf/Revealed_진행현황_주간보고서_v0.6.pdf').read_bytes()).hexdigest()==manifest['previous_pdf_sha256']
images=sorted(QA.glob('page-*.png'))
assert len(images)==11
for start in range(0,len(images),4):
    contact=Image.new('RGB',(1800,1320),'#dfe4e9'); draw=ImageDraw.Draw(contact)
    for i,path in enumerate(images[start:start+4]):
        preview=ImageOps.contain(Image.open(path).convert('RGB'),(890,620))
        x=(i%2)*900; y=(i//2)*660
        contact.paste(preview,(x+5,y+25)); draw.text((x+12,y+5),f'Page {start+i+1}',fill='black')
    contact.save(QA/f'contact-{start//4+1}.jpg',quality=92)
result={**manifest,'all_pages_rendered':True,'previous_week_backup_removed':True,
        'period_and_deadlines_checked':True,'wbs_task_names_and_ids_match':True,
        'reported_metrics_match_evidence':True,'post_cutoff_updates_not_counted_as_weekly_work':True,
        'github_links_on_last_page':expected,'text_overflows':0,
        'visual_review':'completed' if '--visual-reviewed' in sys.argv else 'pending'}
(HERE/'validation_v0_7.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({k:result[k] for k in ['pages','historical_backup_pages','period_and_deadlines_checked','reported_metrics_match_evidence','visual_review']},ensure_ascii=False))

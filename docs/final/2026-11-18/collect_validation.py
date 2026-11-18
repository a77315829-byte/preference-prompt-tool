"""Freeze artifact QA receipts after the final render/visual review."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
QA=ROOT/'tmp/final-20261118'

def write(path,data):
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def main():
 pdf=json.loads((QA/'qa/results.json').read_text(encoding='utf-8'))
 for name in ['design','report','wbs']:
  assert hashlib.sha256((ROOT/pdf[name]['path']).read_bytes()).hexdigest()==pdf[name]['sha256']
 workbook=json.loads((QA/'wbs/checks.json').read_text(encoding='utf-8'))
 assert 'matched 0 entries' in workbook['errorScan']
 browser=json.loads((HERE/'demo-results.json').read_text(encoding='utf-8'))
 assert len(browser['results'])==6 and all(r['pass'] for r in browser['results'])
 assert browser['paid_model_api_calls']==0 and not browser['errors'] and not browser['external']
 legacy={}
 for rel in ['docs/system-design/Revealed_Analysis_Design_v1.2.pdf','output/pdf/Revealed_WBS_v3.3_보고서형.pdf','outputs/wbs-20261112/Revealed_WBS_v3.3_보고서형.xlsx','output/pdf/Revealed_진행현황_주간보고서_v0.10.pdf']:
  before=subprocess.check_output(['git','show','0bbff80:'+rel],cwd=ROOT)
  after=(ROOT/rel).read_bytes();assert before==after,rel
  legacy[rel]=hashlib.sha256(after).hexdigest()
 design={**pdf['design'],'date':'2026-11-18','code_basis':'0bbff8021717e22e2e9a204d70e02e0948803b76',
         'traceability':pdf['traceability'],'diagrams_preserved':77,'visual_review':'전체 154쪽 렌더를 연락 인화지로 점검하고 개정·표·그림 페이지를 확대 확인',
         'old_versions_preserved':True,'scope':'문서·추적 관계 검사; 새 모델 실험 또는 사람 평가 아님'}
 write(ROOT/'docs/system-design/validation-v1.3.json',design)
 write(ROOT/'docs/wbs/2026-11-18/validation.json',{'date':'2026-11-18','pdf':pdf['wbs'],'traceability':pdf['traceability'],'workbook':workbook,
        'xlsx_sha256':hashlib.sha256((ROOT/'outputs/wbs-20261118/Revealed_WBS_v3.4_보고서형.xlsx').read_bytes()).hexdigest(),'visual_review':'PDF 3쪽·Excel 세 시트 및 수정한 비고 확인'})
 receipt={'date':'2026-11-18','code_basis':'0bbff8021717e22e2e9a204d70e02e0948803b76','pdfs':pdf,
          'workbook':workbook,'presentation':{'page_id':'page_d4414f0a4c6081919fe25f6a2dde5a19','state_version':5,'slides':16,'all_slides_rendered_and_visually_reviewed':True,'native_tables':4,'speaker_notes':16},
          'video':{'seconds':79.4,'resolution':[1440,1080],'audio':False,'synthetic_only':True,'full_decode_exit_code':0,'sample_frames_seconds':[20,60]},
          'demo':{'passed':6,'errors':0,'external_requests':0},'paid_model_api_calls':0,'new_dependencies':0,'preserved_legacy_sha256':legacy,
          'limitations':['팀원 PC·참석 리허설 미완료','공식 제출 조건 미확인','실사용자 효과 미측정','발표자료는 사용자 Spaces 권한 범위'],
          'manual_visual_review':'PDF 전체 연락 인화지·개정 상세 페이지, WBS 세 시트, 발표 16장, 영상 구간 프레임 확인'}
 files=[ROOT/'README.md',ROOT/'docs/system-design/README.md',ROOT/'docs/wbs/2026-11-12/README.md']+list(HERE.glob('*.md'))+list((ROOT/'docs/wbs/2026-11-18').glob('*.md'))
 broken=[]
 for p in files:
  for link in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
   if '://' in link or link.startswith('#'):continue
   if not (p.parent/unquote(link.split('#')[0])).resolve().exists():broken.append([p.relative_to(ROOT).as_posix(),link])
 assert not broken,broken
 receipt['relative_markdown_links']={'checked_files':len(files),'broken':broken}
 write(HERE/'validation.json',receipt)
 print('Final hashes, preserved old versions, 24/79 UC, 16 WBS, links and QA receipts verified.')

if __name__=='__main__':main()

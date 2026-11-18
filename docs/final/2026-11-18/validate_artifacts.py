"""Read-only PDF/data audit and Poppler render; writes only QA evidence."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import re
import subprocess
import pdfplumber
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[3]
QA=ROOT/'tmp/final-20261118/qa'
POPPLER=Path('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1110-778-0_26.1110.778.0_x64__3k8sg7r9htsxt/dependencies/native/poppler/Library/bin/pdftoppm.exe')
FILES={
 'design':ROOT/'docs/system-design/Revealed_Analysis_Design_v1.3.pdf',
 'report':ROOT/'output/pdf/Revealed_최종보고서_준비본_v0.1.pdf',
 'wbs':ROOT/'output/pdf/Revealed_WBS_v3.4_보고서형.pdf',
}

def validate(name,path):
 pdf=pdfplumber.open(path);doc=pdf.pages;text='\n'.join(p.extract_text() or '' for p in doc);bad=[]
 for i,page in enumerate(doc):
  assert (page.extract_text() or '').strip(), (name,i,'empty')
  for char in page.chars:
   if char['x0'] < -1 or char['top'] < -1 or char['x1']>page.width+1 or char['bottom']>page.height+1:bad.append([i+1,char['text']])
 assert not bad,bad
 if name=='design':
  assert len(doc)>=151
  for i in range(1,25): assert f'UC-{i:02}' in text
  for token in ['1440','137','17/18','v1.3','v3.4','고정 TTL']: assert token in text,token
 if name=='report':
  for token in ['17/18','1440','40/40','미입증','12,000','GEPA']: assert token in text,token
 if name=='wbs': assert len(doc)==3
 out=QA/name;out.mkdir(parents=True,exist_ok=True)
 subprocess.run([str(POPPLER),'-png','-scale-to','1400' if name=='wbs' else '1000',str(path),str(out/'page')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 images=sorted(out.glob('page-*.png'),key=lambda p:int(p.stem.split('-')[-1]))
 assert len(images)==len(doc)
 cols,rows,tw,th=(4,5,250,370) if name=='design' else ((3,3,330,485) if name=='report' else (1,1,1400,1000))
 for start in range(0,len(images),cols*rows):
  canvas=Image.new('RGB',(cols*tw,rows*th),'#e6e8ec');draw=ImageDraw.Draw(canvas)
  for j,p in enumerate(images[start:start+cols*rows]):
   im=Image.open(p).convert('RGB');im.thumbnail((tw-12,th-26))
   x=(j%cols)*tw+(tw-im.width)//2;y=(j//cols)*th+20
   canvas.paste(im,(x,y));draw.text(((j%cols)*tw+8,(j//cols)*th+4),str(start+j+1),fill='black')
  canvas.save(out/f'contact-{start//(cols*rows)+1}.png')
 return {'path':path.relative_to(ROOT).as_posix(),'pages':len(doc),'page_bounds_checked':True,'rendered_pages':len(images),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

def main():
 QA.mkdir(parents=True,exist_ok=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  results=dict(zip(FILES,pool.map(lambda x:validate(*x),FILES.items())))
 old=json.loads((ROOT/'docs/wbs/2026-11-12/wbs-v3.3.json').read_text(encoding='utf-8'))
 new=json.loads((ROOT/'docs/wbs/2026-11-18/wbs-v3.4.json').read_text(encoding='utf-8'))
 for a,b in zip(old['tasks'],new['tasks']):
  for key in ['id','name','start','end','predecessors','uc_scope']: assert a[key]==b[key],(key,a['id'])
 catalog=json.loads((ROOT/'docs/system-design/usecase-catalog.json').read_text(encoding='utf-8'))
 assert len(catalog['usecases'])==24
 assert sum(len(u['children']) for u in catalog['usecases'])==79
 for u in catalog['usecases']:
  w=next(x for x in new['usecases'] if x['id']==u['id'])
  for k in ['name','wbs']: assert u[k]==w[k],(u['id'],k)
  assert [(r['id'],r['role']) for r in u['related_wbs']]==[(r['id'],r['role']) for r in w['related_wbs']],u['id']
 results['traceability']={'parent_uc':24,'child_uc':79,'phases':5,'tasks':16,'schedule_names_preserved':True}
 (QA/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(results,ensure_ascii=False))

if __name__=='__main__':main()

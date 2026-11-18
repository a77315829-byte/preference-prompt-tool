"""Assemble one local delivery folder without overwriting earlier versions."""
from pathlib import Path
import hashlib
import html
import json
import shutil

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'outputs/Revealed_최종제출_준비본_2026-11-18'
FILES=[
 ('전체 분석·설계서 v1.3 · 154쪽','docs/system-design/Revealed_Analysis_Design_v1.3.pdf'),
 ('WBS v3.4 · PDF 3쪽','output/pdf/Revealed_WBS_v3.4_보고서형.pdf'),
 ('WBS v3.4 · Excel 3개 시트','outputs/wbs-20261118/Revealed_WBS_v3.4_보고서형.xlsx'),
 ('최종 보고서 준비본 v0.1 · 18쪽','output/pdf/Revealed_최종보고서_준비본_v0.1.pdf'),
 ('실제 화면 시연 · 1분 19.4초','outputs/final-20261118/Revealed_demo_20261118.webm'),
 ('발표 대본·Q&A','docs/final/2026-11-18/presenter-notes.md'),
 ('직접 시연·실행·복구 안내','docs/verification/2026-11-17-readiness/DEMO.md'),
 ('최신 주간보고서 v0.10 · 기존 판본','output/pdf/Revealed_진행현황_주간보고서_v0.10.pdf'),
]

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 entries=[]
 for title,rel in FILES:
  source=ROOT/rel;target=OUT/source.name
  shutil.copyfile(source,target)
  digest=hashlib.sha256(target.read_bytes()).hexdigest()
  assert digest==hashlib.sha256(source.read_bytes()).hexdigest()
  entries.append({'title':title,'source':rel,'file':source.name,'bytes':source.stat().st_size,'sha256':digest})
 manifest={'date':'2026-11-18','code_basis':'0bbff8021717e22e2e9a204d70e02e0948803b76',
           'status':'준비본; 팀 리허설·공식 제출 요건 확인 필요','paid_model_api_calls':0,
           'presentation':{'page_id':'page_d4414f0a4c6081919fe25f6a2dde5a19','artifact_ref':'artifact_external_1c3c9020-a13a-49f5-be8b-38e187bf12fd','slides':16,'access':'사용자 Spaces; 팀 공유 권한 별도 확인'},
           'files':entries}
 encoded=json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'
 (HERE/'manifest.json').write_text(encoded,encoding='utf-8',newline='\n')
 (OUT/'manifest.json').write_text(encoded,encoding='utf-8',newline='\n')
 rows=''.join(f'<tr><td>{html.escape(e["title"])}</td><td><a href="{html.escape(e["file"])}">열기</a></td></tr>' for e in entries)
 page='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>Revealed 최종 제출 준비본</title>
<style>body{font-family:'Malgun Gothic',sans-serif;color:#20314c;max-width:1000px;margin:60px auto;padding:0 24px;line-height:1.7}h1{font-size:30px}table{border-collapse:collapse;width:100%;margin:24px 0}td{padding:14px;border-bottom:1px solid #dbe1ea}a{color:#40548a}video{width:100%;max-height:620px;background:#f7f9fc}small{color:#556579}</style>
<h1>Revealed 최종 제출 준비본</h1><p>2026-11-18 · 코드 기준 0bbff80</p>
<p>분석·설계서와 WBS를 최신 정책으로 발행하고 최종 보고·발표·시연 자료를 정리했습니다. 팀원 PC 리허설과 공식 제출 요건 확인 후 확정하세요.</p>
<table>'''+rows+'''</table><h2>발표자료</h2><p>Codex의 Spaces에서 <b>Revealed 최종발표 준비본 v0.1 · 2026-11-18</b>을 엽니다. 표지·본문 13장과 보충 3장입니다. 팀원에게 공유할 때 접근 권한을 확인하거나 뷰어에서 PPTX로 내보내세요. 같은 내용과 출처는 위 발표 대본에도 있습니다.</p>
<h2>실제 화면 시연</h2><p>무음 자동 시연 · 합성 자료 · 무료 준비 예시 · 유료 API 0회. 실제 사용자의 편의성 실험이나 실제 모델 생성 영상은 아닙니다.</p><video controls preload="metadata" src="Revealed_demo_20261118.webm"></video>
<p><a href="https://github.com/a77315829-byte/preference-prompt-tool/tree/docs/wbs-v3.2/docs/final/2026-11-18">GitHub 자료 위치</a> · <a href="manifest.json">파일 해시 목록</a></p><small>수동 대비 우위·사람의 시간 절감은 미입증입니다. 기존 주간보고서 기간과 과거 결과는 그대로 유지했습니다.</small></html>'''
 (OUT/'먼저_읽어주세요.html').write_text(page,encoding='utf-8',newline='\n')
 print(json.dumps({'folder':str(OUT),'files':len(entries),'all_copies_hash_match':True},ensure_ascii=False))

if __name__=='__main__':main()

"""Add UC traceability without subdividing the report's sixteen activities."""
from pathlib import Path
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

def main():
    data=json.loads((HERE/'wbs-v3.json').read_text(encoding='utf-8'))
    catalog=json.loads((ROOT/'docs/system-design/usecase-catalog.json').read_text(encoding='utf-8'))
    data.update(version='3.1',date='2026-11-13',status_date='2026-11-12',usecases=catalog['usecases'])
    mapping={'3.1':'UC-02~05','3.2':'UC-06~08','3.3':'UC-01, 09~10, 19~24','3.4':'UC-11~18','4.1':'UC-02~08, 19~21'}
    for t in data['tasks']:
        t['uc_scope']=mapping.get(t['id'],'UC 전체' if t['id'] in ('1.2','2.1','2.2','2.3','4.2','4.3') else '공통')
    data['notes'].append('문서 상세화로 일정 행을 늘리지 않음. 하위 UC는 부모의 구현 WBS를 상속. 공통 UC-03은 3.2에서도 참조.')
    known={t['id'] for t in data['tasks']}
    assert len(data['tasks'])==16 and all(u['wbs'] in known for u in data['usecases'])
    (HERE/'wbs-v3.1.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('WBS 3.1: same 5 phases / 16 activities / dates / status; 24 parent + 79 child UC mappings.')

if __name__=='__main__':main()

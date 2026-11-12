"""Weekly v0.9: replace the test-count achievement with team access improvements."""
import hashlib
import json
from pypdf import PdfWriter
import build_report_v0_8 as previous

ROOT=previous.ROOT
OUT=ROOT/'output/pdf/Revealed_진행현황_주간보고서_v0.9.pdf'
QA=ROOT/'tmp/weekly_2026_11_13/v0_9'
PREVIOUS=ROOT/'output/pdf/Revealed_진행현황_주간보고서_v0.8.pdf'


class ReportPage(previous.ReportPage):
    def text(self,value,*args,**kwargs):
        replacements={
            '2026.11.13 보고  |  10주차  |  v0.7':'2026.11.13 보고  |  10주차  |  v0.9',
            '통합·회귀 검사':'팀 공유·권한 보완',
            '공유·첨부·권한 18시나리오 검증·오류 수정<br/>Python 1,399·프론트 129개 및 빌드 통과':
                '권한 회수 후 남던 화면·초안 오류 수정<br/>두 계정의 공유·첨부·접근 거절 흐름 확인',
        }
        return super().text(replacements.get(value,value),*args,**kwargs)


def main():
    old_hash=hashlib.sha256(PREVIOUS.read_bytes()).hexdigest()
    previous.ReportPage=ReportPage
    base=previous.base
    base.VERSION='0.9'
    base.ReportPage=ReportPage
    writer=PdfWriter()
    for fn in [base.cover,base.wbs,previous.weekly,base.backup_index,base.changes,base.summary_results,
               base.coding_results,base.regression,base.design_results,base.next_plan,base.github]:
        writer.add_page(fn())
    titles=['표지','1. 프로젝트 일정 - WBS','2. 프로젝트 진행현황','Backup','이번 주 수정',
            '요약 검증','코딩 검증','통합·회귀·CI','분석·설계서 작성','다음 계획','GitHub·자료 위치']
    for i,title in enumerate(titles):writer.add_outline_item(title,i)
    writer.add_metadata({'/Title':'Revealed 주간보고서 v0.9 · 실적 11/06~11/12',
                         '/Author':'윤정우 · 고차원','/Subject':'금주 실적에 팀 공유·권한 보완 반영'})
    with OUT.open('wb') as stream:writer.write(stream)
    assert len(writer.pages)==11 and hashlib.sha256(PREVIOUS.read_bytes()).hexdigest()==old_hash
    QA.mkdir(parents=True,exist_ok=True)
    manifest=dict(version='0.9',report_date='2026-11-13',actual_period=['2026-11-06','2026-11-12'],
                  plan_period=['2026-11-13','2026-11-19'],pages=11,main_pages=[1,2,3],backup_pages=[4,11],
                  achievement_groups=['기능 개선','프롬프트 검증','팀 공유·권한 보완','분석·설계서 작성'],
                  historical_backup_pages=0,issue_and_request_fields='blank',previous_pdf_preserved=True,
                  previous_pdf_sha256=old_hash,output=OUT.relative_to(ROOT).as_posix(),
                  sha256=hashlib.sha256(OUT.read_bytes()).hexdigest(),paid_model_api_calls=0,
                  text_overflows=0,visual_review='pending')
    (QA/'build_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(version='0.9',pages=11,previous_pdf_preserved=True)))


if __name__=='__main__':main()

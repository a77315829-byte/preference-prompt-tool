"""Weekly v0.8: four achievement groups; leave issue/request fields empty."""
from pathlib import Path
import hashlib
import json
from pypdf import PdfReader, PdfWriter
import build_report_v0_7 as base

ROOT=base.ROOT
OUT=ROOT/'output/pdf/Revealed_진행현황_주간보고서_v0.8.pdf'
QA=ROOT/'tmp/weekly_2026_11_13/v0_8'
PREVIOUS=ROOT/'output/pdf/Revealed_진행현황_주간보고서_v0.7.pdf'


class ReportPage(base.ReportPage):
    def text(self,value,*args,**kwargs):
        if value=='2026.11.13 보고  |  10주차  |  v0.7':
            value='2026.11.13 보고  |  10주차  |  v0.8'
        return super().text(value,*args,**kwargs)


def weekly():
    p=ReportPage();p.header('2. 프로젝트 진행현황','',3)
    for x,label,color in [(34,'금주 실적 (11/06 ~ 11/12)','#808080'),(390,'차주 계획 (11/13 ~ 11/19)',base.GRAY)]:
        p.rect(x,84,356,32,color)
        p.text(label,x+9,89,338,13,'#FFFFFF',True,maxh=21,align=1)
    for x in [34,335,390,691,746]:p.line(x,116,x,400,'#C7CDD0',.7)
    for x in [34,390,746]:p.line(x,400,x,494,'#C7CDD0',.7)
    left=[
        ('기능 개선','요약 입력 제한·조건 충돌 처리 개선<br/>코딩 두 기능 구분·초안과 결과 복귀 보완','11/09<br/>~11/12'),
        ('프롬프트 검증','요약 9원문·코딩 두 기능 각 8과제 비교<br/>조건과 내용·동작 분리, 수동 대비 동률','11/10<br/>~11/12'),
        ('통합·회귀 검사','공유·첨부·권한 18시나리오 검증·오류 수정<br/>Python 1,399·프론트 129개 및 빌드 통과','11/12'),
        ('분석·설계서 작성','요구사항·유즈케이스·화면·API·DB 정리<br/>처리 흐름과 검증 근거를 전체 문서로 연결','11/12'),
    ]
    right=[
        ('React 지침 의미 정렬 (윤정우)','한국어·영어의 타입 예외·역할 분리 맞추기<br/>동일 조건표와 변경 지침을 고정','~11/15'),
        ('비교 세션 권한 보완 (공동)','접근·소유권·만료 정책 확정 및 구현<br/>두 계정·로그아웃·만료 경계 확인','~11/17'),
        ('변경 지침 재비교 (고차원·공동)','요약 v2 새 원문·React 변경분 새 과제<br/>수동과 조건·내용/타입·동작 분리 평가','~11/19'),
        ('회귀·설계·WBS 동기화 (공동)','수정 코드 전체 검사·빌드·대표 시연<br/>UC 하위 명세와 WBS 연결·근거 갱신','~11/19'),
    ]
    for x,items in [(34,left),(390,right)]:
        for i,(title,body,day) in enumerate(items):
            y=124+i*68
            p.rect(x+9,y+6,3.5,3.5,'#111111')
            p.text(title,x+19,y,277,11.5,bold=True,maxh=19)
            p.text(body,x+19,y+22,277,10.1,maxh=33)
            p.text(day,x+304,y+15,48,8.8,maxh=28,align=1)
    # Keep the template labels and borders; the two fields are intentionally empty.
    for x,title in [(34,'주요 이슈 및 의사결정 사항'),(390,'프로젝트 요청 사항')]:
        p.rect(x,400,356,30,'#EEEEEE')
        p.text(title,x+8,406,340,11.7,bold=True,maxh=20,align=1)
    for y in [400,430,494]:p.line(34,y,746,y,'#C7CDD0',1.5 if y==494 else .7)
    return p.finish()


def main():
    old_hash=hashlib.sha256(PREVIOUS.read_bytes()).hexdigest()
    base.VERSION='0.8'
    base.ReportPage=ReportPage
    writer=PdfWriter()
    pages=[base.cover,base.wbs,weekly,base.backup_index,base.changes,base.summary_results,
           base.coding_results,base.regression,base.design_results,base.next_plan,base.github]
    for fn in pages:writer.add_page(fn())
    titles=['표지','1. 프로젝트 일정 - WBS','2. 프로젝트 진행현황','Backup','이번 주 수정',
            '요약 검증','코딩 검증','통합·회귀·CI','분석·설계서 작성','다음 계획','GitHub·자료 위치']
    for index,title in enumerate(titles):writer.add_outline_item(title,index)
    writer.add_metadata({'/Title':'Revealed 주간보고서 v0.8 · 실적 11/06~11/12',
                         '/Author':'윤정우 · 고차원','/Subject':'금주 실적 네 항목; 주요 이슈와 프로젝트 요청 사항 공란'})
    with OUT.open('wb') as stream:writer.write(stream)
    assert len(writer.pages)==11
    assert hashlib.sha256(PREVIOUS.read_bytes()).hexdigest()==old_hash
    QA.mkdir(parents=True,exist_ok=True)
    manifest=dict(version='0.8',report_date='2026-11-13',actual_period=['2026-11-06','2026-11-12'],
                  plan_period=['2026-11-13','2026-11-19'],pages=11,main_pages=[1,2,3],backup_pages=[4,11],
                  achievement_groups=['기능 개선','프롬프트 검증','통합·회귀 검사','분석·설계서 작성'],
                  historical_backup_pages=0,issue_and_request_fields='blank',
                  previous_pdf_preserved=True,previous_pdf_sha256=old_hash,
                  output=OUT.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(OUT.read_bytes()).hexdigest(),
                  paid_model_api_calls=0,text_overflows=0,visual_review='pending')
    (QA/'build_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(manifest,ensure_ascii=False))


if __name__=='__main__':main()

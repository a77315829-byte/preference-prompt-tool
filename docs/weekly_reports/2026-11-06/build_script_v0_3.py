"""Keep the verified v0.2 Word format; align speech with the restored template."""
from copy import deepcopy
from pathlib import Path
import hashlib

from docx import Document
from docx.oxml.ns import qn

HERE=Path(__file__).resolve().parent
SOURCE=HERE/'Revealed_주간보고_발표대본_v0.2.docx'
OUT=HERE/'Revealed_주간보고_발표대본_v0.3.docx'


def set_text(paragraph,text):
    if paragraph.runs:
        paragraph.runs[0].text=text
        for run in paragraph.runs[1:]:
            run.text=''
    else:
        paragraph.add_run(text)


def main():
    digest=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    doc=Document(SOURCE)
    paras=list(doc.paragraphs)
    assert paras[20].text.startswith('3쪽 15주차 WBS')
    assert paras[28].text=='질문에 따른 백업 안내'
    for p in paras:
        for r in p.runs:
            if 'v0.2' in r.text:
                r.text=r.text.replace('v0.2','v0.3')
    for i in [5,8,11,16]:
        set_text(paras[i],paras[i].text.replace('2쪽','3쪽',1))
    set_text(paras[20],paras[20].text.replace('3쪽','2쪽',1))
    set_text(paras[6],paras[6].text.replace('먼저 첫 번째 행입니다.','3쪽 왼쪽 금주 실적의 첫 번째 항목입니다.'))
    set_text(paras[9],paras[9].text.replace('두 번째 행은','왼쪽 두 번째 항목은'))
    set_text(paras[12],paras[12].text.replace('세 번째 행입니다.','왼쪽 세 번째 항목입니다.'))
    set_text(paras[17],paras[17].text.replace('마지막 행은','왼쪽 마지막 항목은'))
    set_text(paras[15],'금주 실적과 차주 계획')
    set_text(paras[18],
             'B에서 A를 뺀 스타일 축 통과율은 세 차수에서 약 23~29퍼센트포인트 높았습니다. '
             '기능은 2차 16.67, 3차 6.67퍼센트포인트 낮았습니다. '
             '1차 기능 차이는 마이너스 1.67이지만 95퍼센트 구간에 0이 포함돼 차이를 확인하지 못했습니다. '
             '1·2차 기능은 평가 도구 수정 후 재채점한 값이며 정확한 차수별 수치는 백업 8쪽에 있습니다.')
    for p in paras:
        if p.text.startswith('3쪽. 회색은'):
            set_text(p,p.text.replace('3쪽.','2쪽.',1))
        if '현재 금주·차주 기준은 2쪽' in p.text:
            set_text(p,p.text.replace('현재 금주·차주 기준은 2쪽','현재 금주·차주 기준은 3쪽'))
    # Two pages of speech, followed by the question/backup page. Retain actual
    # Word paragraph styles and the original page-break XML, not screenshots.
    order=list(range(0,5))+list(range(20,24))+list(range(5,8))+[14,15]
    order+=list(range(8,14))+list(range(16,20))+list(range(24,len(paras)))
    assert sorted(order)==list(range(len(paras)))
    reordered=[deepcopy(paras[i]._p) for i in order]
    body=doc._element.body
    for node in list(body):
        if node.tag != qn('w:sectPr'):
            body.remove(node)
    for node in reordered:
        body.insert(len(body)-1,node)
    for section in doc.sections:
        for p in section.footer.paragraphs:
            for r in p.runs:
                if 'v0.2' in r.text:
                    r.text=r.text.replace('v0.2','v0.3')
    doc.core_properties.title='Revealed 주간보고 발표 대본 v0.3'
    doc.save(OUT)
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==digest
    print(OUT.name)


if __name__=='__main__':
    main()

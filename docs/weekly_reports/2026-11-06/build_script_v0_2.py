"""Presentation script paired with the three main pages of report v0.2."""
from pathlib import Path
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

HERE = Path(__file__).resolve().parent
OUT = HERE / 'Revealed_주간보고_발표대본_v0.2.docx'
d = Document()
s = d.sections[0]
s.page_width, s.page_height = Cm(21), Cm(29.7)
s.top_margin, s.bottom_margin = Cm(1.9), Cm(1.8)
s.left_margin, s.right_margin = Cm(2.2), Cm(2.2)
for name, size in [('Normal',11), ('Title',22), ('Heading 1',15), ('Heading 2',12)]:
    st=d.styles[name]
    st.font.name='Malgun Gothic'
    st.font.size=Pt(size)
    st.font.color.rgb=RGBColor(0,0,0)
    st.element.get_or_add_rPr()
    if st.element.rPr.rFonts is None:
        st.element.rPr.append(OxmlElement('w:rFonts'))
    st.element.rPr.rFonts.set(qn('w:eastAsia'),'Malgun Gothic')
    st.paragraph_format.space_after=Pt(7)
    st.paragraph_format.line_spacing=1.22
    st.paragraph_format.widow_control=True
    for border in list(st.element.findall('.//'+qn('w:pBdr'))):
        border.getparent().remove(border)
    if name.startswith('Heading'):
        st.paragraph_format.space_before=Pt(11)
        st.paragraph_format.keep_with_next=True

def p(text, style=None):
    return d.add_paragraph(text,style)

def head(text):
    d.add_heading(text,2)

def cue(text):
    para=p(text)
    for r in para.runs:
        r.font.size=Pt(9)
        r.font.color.rgb=RGBColor.from_string('666666')

d.core_properties.title='Revealed 주간보고 발표 대본 v0.2'
d.core_properties.author='윤정우 · 고차원'
p('Revealed 주간보고 발표 대본','Title')
p('AI/SW융합프로젝트  |  윤정우 · 고차원  |  2026년 11월 6일 9주차  |  v0.2')
cue('약 5분 목표. 보고서 1 → 2 → 3쪽으로 발표하며 4쪽 이후는 질문이 있을 때만 연다. 아래 시간은 연습용 배분이다.')
head('1쪽 이번 주 핵심 20초')
p('안녕하세요. Revealed 팀의 윤정우입니다. 이번 주에는 사용자가 선택한 선호로 지침을 만들고, 보관해서 다음 작업에 다시 쓰는 흐름을 연결했습니다. 제가 진행한 기능과 문서 작업, 고차원이 진행한 코딩 실험을 한 페이지에 모아 보고드리겠습니다.')
head('2쪽 개인 지침과 재사용 55초')
p('먼저 첫 번째 행입니다. 개발 환경을 고르고, 설명·주석·코드 구성·출력 방식의 네 가지 선호를 선택한 뒤 지침을 만드는 흐름을 구현했습니다. 예시를 비교하거나 직접 설정할 수 있고, 선택을 보류한 항목은 임의로 채우지 않습니다.')
p('생성한 지침은 내 선호 보관함에 저장하고 새 작업과 함께 복사해 다시 사용할 수 있습니다. 저장 당시의 환경과 선택 출처도 남깁니다. 받은 답변을 확인하는 기능과 13개 환경의 선택적 GEPA 경로도 연결했습니다. 다만 연결 자체를 성능 향상으로 보지는 않습니다. 다음 주에는 React의 대표 저장·재사용 흐름을 고정하고, 메뉴 이동 시 초안과 진행 작업을 다시 여는 문제를 보완하겠습니다.')
head('2쪽 팀 활용과 업무 연결 45초')
p('두 번째 행은 기존 지침을 팀 작업에서 활용하는 기능입니다. 지원하는 분류에서 개인과 팀 기준을 비교하고, 이번 작업에 따를 항목을 골라 새로운 지침으로 저장하도록 했습니다. 선택 출처와 재조합 이력을 남기고 원본은 보존합니다.')
p('인수인계에서는 목적·진행·남은 일·사용한 지침과 참고 파일을 지정한 계정에 전달할 수 있습니다. 업무 템플릿 24개와 요청문 점검도 정리했습니다. 다음 주에는 두 계정으로 공유 권한, 첨부 접근, 수신자 변경, 버전 충돌을 확인하겠습니다. 협업 시간이 줄었다는 효과는 아직 검증하지 않았습니다.')
head('2쪽 문서와 검사 결과 45초')
p('세 번째 행입니다. 요구사항, UML, ERD, 테이블과 API, 화면 정의를 별도 설계문서로 작성하고 팀 검수를 반영했습니다. 주간보고 본문에는 작성 현황만 남겼고, 기존 상세 그림은 백업으로 옮겼습니다.')
p('11월 4일 검사 기록은 프론트 테스트 86개와 빌드 통과, Python 1,083개 통과와 1개 실패입니다. 실패한 항목은 UTF-8 설정으로 단독 재실행했을 때 통과했지만 전체 회귀 통과로 합산하지 않습니다. 호스팅 구조와 저장 유지도 준비했고 오늘 로컬 데모 재기동을 확인했습니다. 다음에는 복귀 문제를 수정한 뒤 같은 환경에서 전체 검사를 다시 확인하겠습니다.')

d.add_page_break()
d.add_heading('실험 결과와 남은 일정',1)
head('2쪽 고차원의 코딩 실험 55초')
p('마지막 행은 고차원의 기존 코딩 실험입니다. A는 지침 없음, B는 선택으로 조립한 지침이며 화면에서 예시를 고르는 A/B와는 다른 조건입니다.')
p('B에서 A를 뺀 스타일 축 통과율은 1차부터 28.89, 27.78, 23.33퍼센트포인트 높았습니다. 기능 통과율 차이는 같은 순서로 마이너스 1.67, 마이너스 16.67, 마이너스 6.67퍼센트포인트였습니다. 1차는 95퍼센트 구간에 0이 포함돼 차이를 확인하지 못했습니다. 1차와 2차 기능 수치는 평가 도구 수정 후 재채점한 값입니다.')
p('스타일 이득과 기능 저하를 함께 보고하고, 저하의 원인은 아직 분리하지 못한 상태로 남겼습니다. 4차 확증은 과제가 부족해 실행하지 못했습니다. 다음 주에는 독립 과제와 기능·스타일·미확인의 판정 기준을 확정하겠습니다. 기존 실험 수치를 새 선호 축이나 사용자 만족도 결과로 그대로 옮기지는 않습니다.')
head('3쪽 15주차 WBS와 현재 위치 65초')
p('WBS는 수업 시작인 9월 11일을 1주차, 12월 18일을 15주차로 잡았습니다. 오늘 11월 6일은 강조된 9주차입니다. 회색 칸은 이번에 정리한 학기 일정안이고 초록 칸은 날짜가 있는 기록으로 확인한 활동입니다. 기록이 없는 과거 주차의 실적이나 전체 완료율은 채우지 않았습니다.')
p('현재는 개인 지침과 팀 활용의 핵심 기능, 3차까지의 실험 결과, 설계문서를 확보한 단계입니다. 다음 주에는 제가 저장·재사용 시연과 초안·작업 복귀를 보완하고, 고차원은 독립 평가 과제와 판정 기준을 준비하는 역할을 제안합니다. 두 계정 권한 점검과 설계·코드 대응은 함께 확인하겠습니다.')
p('이후에는 통합 검사와 독립 평가를 거쳐 운영 점검과 시연을 안정화하고, 14주차와 15주차에 최종 결과와 발표를 정리할 계획입니다. 다음 보고에서는 계획을 나열하는 데 그치지 않고 실행 결과와 남은 실패 항목을 갱신하겠습니다.')
head('3쪽 마무리 15초')
p('이번 주에는 선택한 지침을 실제로 보관하고 재사용하는 흐름을 연결했습니다. 다음 주는 이 흐름의 복귀 문제와 검증을 우선하겠습니다. 자세한 구현·실험 근거와 설계 자료는 백업에 준비했습니다. 감사합니다.')
cue('핵심 발표는 여기서 끝낸다. 모든 백업을 순서대로 넘기지 않는다.')

d.add_page_break()
d.add_heading('질문에 따른 백업 안내',1)
cue('이 페이지는 본 발표 시간에 포함하지 않는다. 새 보고서 v0.2의 쪽 번호를 사용한다.')
qa=[
('이번 주에 무엇을 완료했나요',
 '5~7쪽. 개인 지침의 선택·저장·재사용, 팀 기준 조합·출처·인수인계, 별도 설계문서 작성과 검사 기록 정리입니다. 기능 구현과 효과 검증은 구분하며 초안·작업 복귀 문제와 전체 회귀 재확인은 남아 있습니다.'),
('실험 수치가 유리한 것만 나온 것은 아닌가요',
 '8쪽. 스타일과 기능의 차이를 함께 제시했습니다. 1차 기능은 구간이 0을 포함하며, 2·3차는 기능 저하를 관찰했습니다. 1·2차 기능은 수정한 평가기로 재채점한 값이고 저하 원인은 아직 분리하지 못했습니다.'),
('기존 코딩 실험과 새 화면은 무엇이 다른가요',
 '9쪽. 기존 React 실험은 반복 비교에서 파일 구성·스타일·타입 선호를 추정합니다. 새 흐름은 설명·주석·구성·출력을 항목별로 선택합니다. 선호 지침이라는 주제는 이어가되 기존 효과 수치를 새 흐름에 그대로 적용하지 않습니다.'),
('WBS에서 회색 칸과 초록 칸은 무엇인가요',
 '3쪽. 회색은 현재 재정리한 학기 일정안이고 초록은 날짜가 확인된 활동입니다. 초기부터 이 계획을 따랐거나 1~7주차 활동을 모두 검증했다는 뜻은 아닙니다. 현재 위치는 11월 6일 9주차이며 전체 완료율은 산정하지 않았습니다.'),
('설계문서는 어디에 있나요',
 '별도 Markdown 설계문서와 UML PDF를 공유합니다. 보고서 12~20쪽은 기존 참고 그림을 보존한 백업입니다. 상세 클래스·저장 검증·커밋·버전 상한 검토는 별도 UML에 반영되어 있습니다.'),
('계획과 실제 화면의 근거를 볼 수 있나요',
 '11쪽에 코드·실험 근거 링크, 21~22쪽에 실제 예시 계정의 화면이 있습니다. 10쪽은 11월 5일 작성 당시 상세 계획이며 현재 금주·차주 기준은 2쪽을 따릅니다.'),
('실제 사용자 모집 없이 무엇을 검증하나요',
 '저장·재사용 일치, 계정별 권한, 버전 충돌, 화면 복귀와 독립 과제의 기능·스타일을 확인합니다. 만족도나 협업 시간 절감은 자동 평가만으로 검증했다고 말하지 않습니다.'),
]
for question,answer in qa:
    head(question)
    p(answer)
footer=s.footer.paragraphs[0]
footer.alignment=2
footer.add_run('Revealed v0.2  |  ')
field=OxmlElement('w:fldSimple')
field.set(qn('w:instr'),'PAGE')
footer._p.append(field)
d.save(OUT)
print(OUT.name)

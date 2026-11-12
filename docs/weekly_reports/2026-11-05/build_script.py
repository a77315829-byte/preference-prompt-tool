"""Editable Korean speaking script aligned to the weekly report PDF."""
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

HERE=Path(__file__).resolve().parent
OUT=HERE/'Revealed_주간보고_발표대본_2026-11-05.docx'
d=Document()
s=d.sections[0];s.page_width=Cm(21);s.page_height=Cm(29.7)
s.top_margin=Cm(1.9);s.bottom_margin=Cm(1.8);s.left_margin=Cm(2.2);s.right_margin=Cm(2.2)
for name,size in [('Normal',11),('Title',22),('Heading 1',14),('Heading 2',12)]:
    style=d.styles[name];style.font.name='Malgun Gothic';style.font.size=Pt(size);style.font.color.rgb=RGBColor(0,0,0)
    style.element.get_or_add_rPr().append(OxmlElement('w:rFonts')) if style.element.rPr.rFonts is None else None
    style.element.rPr.rFonts.set(qn('w:eastAsia'),'Malgun Gothic')
    style.paragraph_format.space_after=Pt(7)
    style.paragraph_format.line_spacing=1.22
    if name.startswith('Heading'):
        style.paragraph_format.space_before=Pt(12);style.paragraph_format.keep_with_next=True
    for border in list(style.element.findall('.//'+qn('w:pBdr'))):
        border.getparent().remove(border)
d.styles['Normal'].paragraph_format.widow_control=True
d.core_properties.title='Revealed 주간보고 발표 대본'
d.core_properties.author='윤정우 · 고차원'

def p(text,style=None):return d.add_paragraph(text,style)
def heading(text):return d.add_heading(text,2)
def cue(text):
    x=p(text);x.paragraph_format.space_after=Pt(5)
    for r in x.runs:r.font.size=Pt(9);r.font.color.rgb=RGBColor.from_string('666666')

p('Revealed 주간보고 발표 대본','Title')
p('AI/SW융합프로젝트  |  윤정우 · 고차원  |  2026년 11월 5일')
cue('약 5분 · 보고서 1 → 2 → 3 → 4 → 5 → 6 → 11쪽 순서. 7~10쪽은 질의응답용. 시간은 연습 기준이며 실제 발화 속도에 따라 조정한다.')

heading('보고서 1쪽   인사와 이번 주 방향   20초')
p('안녕하세요. Revealed 팀의 윤정우입니다. 저희는 사용자가 고른 코드 작성 선호를 프롬프트로 만들어 다음 작업에도 재사용하는 도구를 개발하고 있습니다. 이번 주에는 차원이가 진행한 기존 코딩 실험을 정리하고, 마이크로스톤의 저장과 재사용 기능을 이 연구에 어떻게 연결할지 검토했습니다. 이번 보고에는 AWS를 제외했습니다.')

heading('보고서 2쪽   일정과 현재 단계   25초')
p('현재는 기능을 연결한 뒤 검증과 통합을 준비하는 단계입니다. 코딩 비교 실험과 지침 생성, 보관함 기능은 각각 실적을 확보했습니다. 다만 기능 구현이 끝난 것과 효과를 검증한 것은 다르기 때문에 전체 진행률 하나로 표현하지 않았습니다. 다음 주에는 React 한 환경에서 선택부터 저장, 새 작업에 재사용하는 흐름을 집중적으로 점검하겠습니다.')

heading('보고서 3쪽   차원이가 진행한 코딩 실험   60초')
p('차원이는 TypeScript와 React에서 파일 구성, 스타일 관리, 타입 작성 방식이라는 세 선호를 비교했습니다. 조립한 프롬프트는 프롬프트가 없는 조건보다 스타일 검사 통과율이 세 차례에서 약 23에서 29퍼센트포인트 높았습니다.')
p('반면, 조립한 문장을 AI가 다시 쓰게 했을 때의 추가 이득은 두 번 모두 도입 기준을 넘지 못했습니다. 그래서 이 재서술 기능은 구현을 보존하되 기본 사용은 꺼 두었습니다. 기능을 더 넣는 것보다 측정 결과로 사용 여부를 결정했다는 점이 이번 실험의 의미입니다.')
p('또 스타일을 더 지켜도 요청 기능은 덜 지킬 수 있다는 문제가 관찰됐습니다. 원인을 가리려던 네 번째 비교는 알맞은 과제가 부족해 본실험을 진행하지 않았습니다. 이 결과는 모의 프로필과 자동 검사 기준이며, 실제 사용자 만족도를 검증한 결과는 아닙니다.')
cue('강조: 60단위는 사람 60명이 아니다. AI 재서술 비교는 1·2차, 3차는 요청 대조 규칙의 기능 효과 비교다.')

d.add_page_break()
d.add_heading('서비스 확장과 다음 주 우선순위',1)

heading('보고서 4쪽   현재 마이크로스톤에서 한 일   65초')
p('현재 마이크로스톤에서는 사용자가 개발 환경을 고르고, 설명과 주석, 코드 구성, 출력 방식의 네 항목을 선택하면 지침을 조립합니다. 준비된 예시를 보고 고르거나 설정을 직접 선택할 수 있습니다. 결과를 보관함에 저장하고 새 작업 요청과 함께 복사하는 흐름도 연결했습니다.')
p('여기서 기존 연구와 구분할 점이 있습니다. 기존 React 기능은 반복 비교로 선호를 추정하고, 새 코딩 화면은 사용자가 항목별로 원하는 값을 정합니다. 화면에 A와 B가 나온다고 같은 추정 방식인 것은 아닙니다. 기존 React 비교 기능도 별도 진입점으로 유지했습니다.')
p('일부 환경에는 GEPA라는 프롬프트 최적화기를 선택적으로 연결했습니다. 원본 지침을 고정한 채 보충 안내를 탐색합니다. 현재 13개 환경 조합에 실행 경로가 있지만, 주로 제한된 정적 검사에 기반하므로 모든 환경에서 기능이나 성능이 좋아졌다고 보고하지는 않습니다.')

heading('보고서 5쪽   확인한 문제와 통합 계획   45초')
p('검증 기록에서는 프론트 테스트 86개와 빌드가 통과했습니다. Python 검사는 1,083개가 통과하고 한 개가 실패했으며, 실패 항목만 UTF-8 설정으로 다시 실행했을 때 통과했습니다. 전체 검사가 모두 통과한 것으로 합쳐 말하지 않았습니다.')
p('실제 흐름에서는 메뉴 이동 시 작성 중인 초안이 사라지는 문제와, GEPA 실행 중 화면을 나갔다 돌아오면 작업을 다시 찾기 어려운 문제를 확인했습니다. 다음 주에는 이 두 동선을 먼저 보완하고, 차원이의 평가 도구와 버그 수정도 변경별로 검토하겠습니다. 두 브랜치를 이미 통합한 상태는 아닙니다.')

heading('보고서 6쪽   기존 주제를 이어가는 방법   70초')
p('저희가 이어갈 중심은 사용자가 고른 선호를 지침으로 만드는 기존 주제입니다. 마이크로스톤은 이 지침을 보관하고 다음 작업에 다시 쓰는 사용 흐름을 담당합니다. 따라서 기존 실험을 버리거나, 팀 협업 서비스로 주제를 전부 바꾸는 방향으로 설명하지 않겠습니다.')
p('다음 주에는 React 한 환경에서 대표 시연 흐름을 고정하겠습니다. 역할은 윤정우가 화면과 저장·복귀 동선을 보완하고, 고차원이 비교 조건과 평가 도구를 정리하는 안을 제안합니다. 마지막에는 함께 회귀 결과와 새 과제의 평가표를 확인하겠습니다.')
p('평가에서는 코드가 요구한 스타일을 지켰는지, 요청한 기능이 동작하는지, 실행을 확인하지 못했는지를 따로 남기겠습니다. 새로운 참여자 모집 없이도 확인할 수 있는 기술적 범위에 우선 집중하겠습니다. 완료하지 못한 항목은 다음 보고에서도 계획으로 구분하겠습니다.')

heading('보고서 11쪽   마무리   15초')
p('이번 주에는 기존 코딩 실험의 결과와 현재 서비스의 확장 범위를 정리했습니다. 기존 연구를 중심에 두고 지침의 저장과 재사용으로 이어가는 범위가 적절한지, 다음 검증을 어디까지 좁히면 좋을지 의견을 부탁드립니다. 감사합니다.')
cue('표정·호흡을 포함하면 약 5분을 목표로 한다. 시간이 부족하면 4쪽의 GEPA 세부 설명을 줄이고, 6쪽의 다음 주 완료 기준은 남긴다.')

d.add_page_break()
d.add_heading('질의응답 참고',1)
cue('보고서 7~10쪽을 필요할 때만 연다. 다음 답변은 본문 발표 시간에 포함하지 않는다.')

qa=[
('기존 프로젝트에서 주제가 바뀐 것인가요','사용자 선호를 지침으로 만든다는 중심은 유지합니다. 기존 실험은 선호 반영의 근거이고, 마이크로스톤의 저장·재사용은 그 지침을 쓰는 과정의 확장입니다. 팀 인수인계는 보조 활용이며 이번 주 핵심 성능 목표로 두지 않았습니다.'),
('AI 개선은 효과가 없는데 왜 GEPA가 있나요','두 기능의 방식과 실험 조건이 다릅니다. 차원이의 재서술은 선호 문장을 한 차례 다시 쓰는 단계입니다. 현재 GEPA는 원본을 유지하며 여러 보충 안내 후보를 탐색합니다. 연결 여부와 개선 효과는 별개라 GEPA는 선택 기능으로 두고 환경별로 효과를 확인해야 합니다.'),
('코딩 범위가 넓어졌는데 검증은 충분한가요','14개 언어의 준비 예시와 13개 환경 조합의 GEPA 경로가 있습니다. 지원 목록 전체의 품질을 입증한 것은 아닙니다. 다음 주에는 React 한 환경을 먼저 점검하고 다른 환경으로 결론을 확대하지 않겠습니다.'),
('사용자를 모집하지 않고 무엇을 검증하나요','지정 선호의 자동 판정, 독립 과제의 기능 검사, 저장 설정과 재사용 지침의 일치, 화면 복귀와 권한 같은 동작을 확인합니다. 편리함이나 만족도, 협업 시간 절감은 이 결과만으로 주장하지 않습니다.'),
('테스트 1083개 통과면 완료 아닌가요','구현 회귀 검사와 AI 결과 품질은 다른 문제입니다. 실패 항목의 조건도 공개했고, 실제 흐름에서는 초안 손실을 발견했습니다. 숫자만으로 완료를 판단하지 않고 사용 시나리오와 실패 경로를 함께 점검합니다.'),
('친구 보고서의 사용자 파일럿은 코딩인가요','연결된 5~8명·30분 리허설 안내는 한국어 요약 평가입니다. 코딩의 참여자 평가 준비 자료는 별도입니다. 둘을 합쳐 코딩 사용자 검증 완료라고 설명하지 않습니다.'),
('AWS를 제외한 이유는 무엇인가요','이번 수업 보고에서는 선택 기반 코딩 지침과 재사용이라는 한 흐름을 완성하는 데 집중하기 위해 범위를 줄였습니다. 기존 AWS 기록을 코딩의 효과 근거로 사용하지 않습니다.'),
('다음 주에 꼭 보여 줄 것은 무엇인가요','보고서 9쪽의 완료 기준에 맞춰, 선택부터 새 작업 재사용까지 이어지는 시연, 초안과 작업 복귀 점검 결과, 통합한 변경과 회귀 결과, 실행한 범위의 평가표를 보여 드리겠습니다. API 실험을 실행하지 않았다면 그 부분은 준비 상태로 보고하겠습니다.')]
for q,a in qa:
    heading(q)
    p(a)

# Page number is useful for a multi-page speaking script.
f=s.footer.paragraphs[0];f.alignment=2
r=f.add_run();fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');r._r.addnext(fld)
d.save(OUT)
print(OUT)

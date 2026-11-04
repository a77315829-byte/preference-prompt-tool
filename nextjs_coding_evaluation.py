"""App Router GET tasks; no generated imports, Next build, or HTTP server."""
from types import SimpleNamespace

from web_coding_evaluation import evaluate

VERSION = 'nextjs-route-ast-v2'
PREFERENCE_CHECKS = '설명·출력 형식만 자동 점수에 반영합니다. 주석·역할 구성은 실제 답변에서 직접 확인합니다.'
LIMITATION = 'Next.js App Router의 route.ts/js 파일 위치·export GET·URL/nextUrl 쿼리·JSON 응답과 계산식을 제한된 AST로 확인합니다. 실제 파일 생성·모듈 경로 해결·Next.js 빌드·서버·화면·캐싱·타입·보안 검증은 아닙니다. Pages Router·동적 경로·Server Actions는 별도 지원하지 않으며 다른 올바른 표현도 미확인될 수 있습니다.'
OUTPUT_RULE = '전체 파일은 코드 블록 바로 위에 app/.../route.ts 또는 route.js 경로를 쓰고 export GET을 포함합니다. 변경 부분 선호는 기존 맥락에 적용할 export 없는 GET 함수 전체 또는 마지막 return 문입니다. 필요한 import·계산 함수를 함께 제시해도 부분 수정으로 확인합니다.'


def _task(language, label, route, key, left, right, fee, patch):
    typed = language == 'TypeScript'
    suffix = 'ts' if typed else 'js'
    file = 'app' + route + '/route.' + suffix
    original = f'''import {{ NextResponse{', type NextRequest' if typed else ''} }} from 'next/server';
export async function GET(request{': NextRequest' if typed else ''}) {{
  const params = request.nextUrl.searchParams;
  const {left}Raw = params.get('{left}');
  const {right}Raw = params.get('{right}');
  const {left} = Number({left}Raw);
  const {right} = Number({right}Raw);
  if ({left}Raw === null || {right}Raw === null || {left}Raw.trim() === '' || {right}Raw.trim() === '' || !Number.isFinite({left}) || !Number.isFinite({right}) || {left} < 0 || {right} < 0) {{
    return NextResponse.json({{ error: '입력 오류' }}, {{ status: 400 }});
  }}
  return NextResponse.json({{ {key}: {left} * {right} + 100 }});
}}
'''
    request = (f'{language}/Next.js App Router의 기존 프로젝트에서 GET {route}를 구현하세요. '
        f'전체 파일은 코드 블록 바로 위에 ### {file} 제목을 쓰고 ```{suffix} 코드 블록에 export GET을 포함하세요. src/app/... 경로도 허용합니다. '
        f'필수 숫자 쿼리 {left}, {right}를 request.nextUrl.searchParams 또는 new URL(request.url).searchParams로 읽고 Number로 변환하세요. '
        '누락·빈 문자열·공백·비숫자·무한대·음수 입력에는 JSON {error: "입력 오류"}와 400 응답을 반환하세요. '
        f'정상 입력에는 JSON {{{key}: {left} * {right} + {fee}}}와 200 응답을 반환하세요. '
        'next/server에서 import한 NextResponse.json 또는 Web Response.json을 사용할 수 있습니다. '
        '순수 계산 함수 분리도 가능합니다. 서버 시작·새 의존성·네트워크·DB·인증·캐시 설정은 필요하지 않습니다. 고른 답변 방식을 따르고 실행·빌드·타입 검사를 통과했다고 주장하지 마세요.')
    if patch:
        request += f'\n변경 부분 선호면 export를 생략한 GET 함수 전체 또는 마지막 return 문만 제시하세요. 필요한 import와 별도 계산 함수를 함께 제시해도 됩니다. 전체 코드 선호면 경로 제목과 전체 파일을 제시하세요. 기존 {file}:\n```{suffix}\n{original}```'
    return dict(id=f'nextjs-{label}', label=label, input=request, route=route, file=file, key=key,
                left=left, right=right, fee=fee, patch=patch, original=original, entry='GET')


def evaluation_for(language):
    language = 'TypeScript' if language.casefold() == 'typescript' else 'JavaScript'
    def tasks(rows):
        return [_task(language, *row) for row in rows]
    return SimpleNamespace(VERSION=VERSION, LIMITATION=LIMITATION, PREFERENCE_CHECKS=PREFERENCE_CHECKS,
        OUTPUT_RULE=OUTPUT_RULE,
        TRAIN=tasks([('상담 견적','/api/consultations/quote','consultation','hours','hourlyRate',640,False),
                     ('이용료 변경','/api/usage/amount','usage','units','unitRate',2600,True)]),
        VALIDATION=tasks([('회의 비용','/api/meetings/charge','meeting','slots','slotRate',840,False),
                          ('대여료 변경','/api/rentals/fee','rental','days','dailyRate',1500,True)]),
        HOLDOUT=tasks([('작업 견적','/api/work/estimate','work','count','unitPrice',2100,False),
                       ('예약료 변경','/api/bookings/cost','booking','periods','periodRate',490,True)]),
        CHECK_RULES={'syntax':'설치된 TypeScript 파서의 제한된 JS/TS 구문 확인. 타입·빌드 검사는 아님.',
                     'binding':'답변에 제시한 App Router 파일 위치·export GET과 입력 연결 확인. 실제 파일/HTTP 라우팅 검사는 아님.',
                     'validation':'양쪽 입력의 누락·빈 문자열·공백·비숫자·무한대·음수에서 JSON 400 확인.',
                     'calculation':'세 정상 입력의 JSON 키·계산값·200 응답 확인.'},
        evaluate=lambda task,response,profile: evaluate('nextjs',language,task,response,profile,limitation=LIMITATION))

"""Prepared Nest TypeScript controller/module tasks with bounded AST checks."""
from types import SimpleNamespace

from web_coding_evaluation import evaluate

VERSION = 'nestjs-ast-v2'
PREFERENCE_CHECKS = '설명·출력 형식만 자동 점수에 반영합니다. 주석·역할 구성은 실제 답변에서 직접 확인합니다.'
LIMITATION = 'TypeScript의 NestJS Controller/Get/Query·Module 등록·Injectable 서비스의 제한된 생성자 주입·BadRequestException·계산식을 AST로 확인합니다. 생성 코드 import/실행·Nest 빌드·실제 DI 컨테이너·HTTP·ValidationPipe·DB·보안·전체 품질 검증은 아닙니다. 커스텀 provider/pipe/guard·비동기 IO·상속 등 다른 올바른 표현도 미확인될 수 있습니다.'
OUTPUT_RULE = '전체 답변은 Nest import와 Controller·Module 등록을 포함합니다. 서비스를 분리하면 Injectable 서비스·Module providers·생성자 주입도 포함합니다. 변경 부분 선호는 제공된 기존 맥락에 적용할 quote 메서드 전체 또는 마지막 return 문입니다. 필요한 import는 별도 ts 코드 블록으로 제시할 수 있습니다.'


def _task(label, prefix, key, left, right, fee, patch):
    original = f'''import {{ Controller, Get, Query, BadRequestException, Module }} from '@nestjs/common';
@Controller('{prefix}')
export class QuoteController {{
  @Get('quote')
  quote(@Query('{left}') {left}Raw: string | undefined, @Query('{right}') {right}Raw: string | undefined) {{
    const {left} = Number({left}Raw);
    const {right} = Number({right}Raw);
    if ({left}Raw === undefined || {right}Raw === undefined || {left}Raw.trim() === '' || {right}Raw.trim() === '' || !Number.isFinite({left}) || !Number.isFinite({right}) || {left} < 0 || {right} < 0) {{
      throw new BadRequestException('입력 오류');
    }}
    return {{ {key}: {left} * {right} + 100 }};
  }}
}}
@Module({{ controllers: [QuoteController] }})
export class QuoteModule {{}}
'''
    request = (f'TypeScript/NestJS의 기존 프로젝트에 GET /{prefix}/quote를 추가하세요. @Controller와 @Get, '
        f"@Query('{left}'), @Query('{right}')로 원시 문자열을 받는 quote 메서드를 사용하세요. "
        'Number로 숫자를 변환하고 누락·빈 문자열·공백·비숫자·무한대·음수 입력은 BadRequestException("입력 오류")로 거절하세요. '
        f'정상 입력에는 JSON 객체 {{{key}: {left} * {right} + {fee}}}를 반환하세요. '
        '필요한 데코레이터/예외는 @nestjs/common에서 import하고 컨트롤러를 QuoteModule의 controllers에 등록하세요. '
        '계산을 서비스로 나누면 @Injectable 서비스와 Module providers, 타입이 명시된 private/public/readonly 생성자 매개변수 주입을 함께 제시하세요. '
        '순수 계산 함수로 분리해도 됩니다. Controller/Get/Query 데코레이터는 문자열 경로/쿼리 하나만 받도록 하세요. '
        '별도 파이프·DTO·새 패키지·부트스트랩·IO는 필요하지 않습니다. 파일 이름과 ts 코드 블록을 제시하고 고른 답변 방식을 따르세요. 실행·빌드·타입 검사를 통과했다고 주장하지 마세요.')
    if patch:
        request += '\n변경 부분 선호면 @Get과 @Query를 포함한 quote 메서드 전체 또는 마지막 return 문만 제시하세요. 추가 import는 별도 ts 코드 블록에 제시하고, 서비스 등록·주입을 바꾸면 필요한 클래스/모듈 전체를 제시하세요. 전체 코드 선호면 필요한 전체 파일을 제시하세요. 기존 파일:\n```ts\n' + original + '```'
    return dict(id=f'nestjs-{label}', label=label, input=request, route=f'/{prefix}/quote', prefix=prefix,
                key=key, left=left, right=right, fee=fee, patch=patch, original=original, entry='quote')


def evaluation_for():
    def tasks(rows):
        return [_task(*row) for row in rows]
    return SimpleNamespace(VERSION=VERSION, LIMITATION=LIMITATION, PREFERENCE_CHECKS=PREFERENCE_CHECKS, OUTPUT_RULE=OUTPUT_RULE,
        TRAIN=tasks([('배송 견적','shipments','shipment','weight','unitRate',660,False),
                     ('작업 비용 변경','jobs','job','hours','hourlyRate',2800,True)]),
        VALIDATION=tasks([('예약 견적','reservations','reservation','slots','slotRate',860,False),
                          ('장비 비용 변경','devices','device','days','dailyRate',1700,True)]),
        HOLDOUT=tasks([('등록 견적','registrations','registration','count','unitPrice',2300,False),
                       ('출력 비용 변경','prints','printCost','pages','pageRate',530,True)]),
        CHECK_RULES={'syntax':'설치된 TypeScript 파서로 제한된 구문 확인. 빌드·타입 검사는 아님.',
                     'binding':'실제 Nest 데코레이터 import·GET/Query·Module controllers와 사용한 서비스 providers/생성자 연결 확인.',
                     'validation':'양쪽 입력의 누락·빈 값·공백·비숫자·무한대·음수에서 BadRequestException 확인.',
                     'calculation':'세 정상 입력의 반환 객체 키와 계산식 확인.'},
        evaluate=lambda task,response,profile: evaluate('nestjs','TypeScript',task,response,profile,limitation=LIMITATION))

"""Vue 3 script-setup tasks; bounded source/template interpretation only."""
from types import SimpleNamespace

from web_coding_evaluation import evaluate

VERSION = 'vue-ast-v2'
PREFERENCE_CHECKS = '설명·출력 형식만 자동 점수에 반영합니다. 주석·역할 구성은 실제 답변에서 직접 확인합니다.'
LIMITATION = 'Vue 3 script setup·숫자 props·computed·v-if/else·보간을 제한된 AST와 템플릿 구조로 확인합니다. Vue 컴파일·실제 렌더링·반응성·타입·보안·전체 품질 검증은 아닙니다. 지원하지 않는 올바른 표현도 미확인될 수 있습니다.'
OUTPUT_RULE = '전체 코드는 script setup과 template를 포함한 .vue 파일입니다. 기존 코드 변경 과제의 변경 부분 선호는 제공된 맥락에 적용할 script setup 또는 template 전체 블록입니다. 둘 다 바뀌면 각각 별도 코드 블록으로 제시합니다. 필요한 import·계산 함수가 함께 있어도 부분 수정으로 확인합니다.'


def _task(language, label, key, left, right, fee, patch):
    typed = language == 'TypeScript'
    script = '<script setup lang="ts">' if typed else '<script setup>'
    props = f'{{ {left}: number; {right}: number }}' if typed else f'{{ {left}: Number, {right}: Number }}'
    declaration = f'defineProps<{props}>()' if typed else f'defineProps({props})'
    original = f'''{script}
import {{ computed }} from 'vue';
const props = {declaration};
const invalid = computed(() => !Number.isFinite(props.{left}) || !Number.isFinite(props.{right}) || props.{left} < 0 || props.{right} < 0);
const total = computed(() => props.{left} * props.{right} + 100);
</script>
<template>
  <p v-if="invalid">입력 오류</p>
  <output v-else data-testid="{key}">{{{{ total }}}}</output>
</template>
'''
    request = (f'{language}/Vue 3의 기존 프로젝트에서 Calculator.vue를 작성하세요. <script setup' + (' lang="ts"' if typed else '')
        + f'>와 <template>를 사용하세요. defineProps로 숫자 props {left}, {right}를 선언하고 computed를 사용하면 vue에서 import하세요. '
        f'두 props 중 누락·비숫자·무한대·음수 입력이면 v-if/v-else로 "입력 오류"만 표시하고 정상 결과를 숨기세요. '
        f'정상 입력이면 오류를 숨기고 <output data-testid="{key}"> 안에 {left} * {right} + {fee} 계산값만 표시하세요. '
        'computed의 보간 또는 props를 직접 쓰는 보간을 사용할 수 있습니다. 별도 순수 계산 함수로 나눠도 됩니다. '
        '상태 변경·이벤트·네트워크·브라우저 API·새 의존성은 필요하지 않습니다. 파일 이름과 ```vue 코드 블록을 제시하고 고른 답변 방식을 따르세요. 실행·컴파일·타입 검사에 통과했다고 주장하지 마세요.')
    if patch:
        request += '\n변경 부분 선호면 바뀐 <script setup> 또는 <template> 블록 전체만 제시하세요. 둘 다 바뀌면 각각 별도 코드 블록으로 제시하세요. 전체 코드 선호면 .vue 전체 파일을 제시하세요. 필요한 import와 계산 함수를 함께 제시해도 됩니다. 기존 파일:\n```vue\n' + original + '```'
    return dict(id=f'vue-{label}', label=label, input=request, route=f'/{key}/quote', key=key,
                left=left, right=right, fee=fee, patch=patch, original=original, entry='Calculator')


def evaluation_for(language):
    language = 'TypeScript' if language.casefold() == 'typescript' else 'JavaScript'
    def tasks(rows):
        return [_task(language, *row) for row in rows]
    return SimpleNamespace(VERSION=VERSION, LIMITATION=LIMITATION, PREFERENCE_CHECKS=PREFERENCE_CHECKS,
        OUTPUT_RULE=OUTPUT_RULE,
        TRAIN=tasks([('좌석 예약', 'seat', 'seats', 'seatRate', 620, False),
                     ('대여 비용 변경', 'rental', 'days', 'dailyRate', 2400, True)]),
        VALIDATION=tasks([('수업 비용', 'lesson', 'hours', 'hourlyRate', 820, False),
                          ('배송 비용 변경', 'delivery', 'weight', 'unitRate', 1300, True)]),
        HOLDOUT=tasks([('숙박 견적', 'stay', 'nights', 'nightlyRate', 1900, False),
                       ('인쇄 비용 변경', 'printing', 'pages', 'pageRate', 480, True)]),
        CHECK_RULES={'syntax': '제한된 script setup 구문과 템플릿 구조 확인. Vue 컴파일 검사는 아님.',
                     'binding': 'Vue 3 script setup·숫자 defineProps와 템플릿 연결 확인.',
                     'validation': '누락·비숫자·무한대·두 음수 입력에서 오류만 표시되는지 확인.',
                     'calculation': '세 정상 입력에서 오류 없이 지정 output에 계산값만 표시되는지 확인.'},
        evaluate=lambda task, response, profile: evaluate('vue', language, task, response, profile, limitation=LIMITATION))

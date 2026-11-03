"""React/Express prepared tasks, checked through a bounded JS/TS AST interpreter."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
from types import SimpleNamespace

from coding_answer_review import inspect_answer
from coding_evaluation_report import scoring_rules, weighted_score

ROOT = Path(__file__).resolve().parent
VERSION = 'web-ast-v2'
PREFERENCE_CHECKS = '설명·출력 형식만 자동 점수에 반영합니다. 주석·역할 구성은 실제 답변에서 직접 확인합니다.'
LIMITATION = '설치된 TypeScript 파서와 제한된 AST 해석으로 준비 과제의 선언·입력 분기·계산식을 확인합니다. 생성 코드 실행·브라우저 렌더링·Express 서버 실행·TypeScript 타입 검사·보안·전체 품질 검증은 아닙니다.'


def available():
    return bool(shutil.which('node') and (ROOT / 'frontend/node_modules/typescript/lib/typescript.js').is_file())


def _task(mode, language, label, route, key, left, right, fee, patch):
    typed = language == 'TypeScript'
    if mode == 'express':
        entry = 'handleQuote'
        signature = 'req: Request, res: Response' if typed else 'req, res'
        imports = "import express" + (", { type Request, type Response }" if typed else '') + " from 'express';"
        original = f'''{imports}
export const app = express();
export function {entry}({signature}) {{
  const {left} = Number(req.query.{left});
  const {right} = Number(req.query.{right});
  if (!Number.isFinite({left}) || !Number.isFinite({right}) || {left} < 0 || {right} < 0) {{
    return res.status(400).json({{error: '입력 오류'}});
  }}
  return res.json({{{key}: {left} * {right} + 100}});
}}
app.get('{route}', {entry});
'''
        requirement = (f'기존 Express 4+ ESM 프로젝트에 GET {route}를 구현하세요. '
            f'필수 숫자 쿼리 {left}, {right}를 Number로 변환하고 Number.isFinite와 음수 검사를 해 누락·비숫자·음수면 '
            f'HTTP 400과 {{error: "입력 오류"}}를 반환하세요. 성공 시 JSON {{{key}: {left} * {right} + {fee}}}를 반환하세요. '
            f'Express import와 app 생성·경로 등록을 포함하고 {entry} 함수 또는 동등한 화살표 핸들러를 사용하세요. '
            '서버를 시작하는 listen은 넣지 마세요.')
        suffix = 'ts' if typed else 'js'
    else:
        entry = 'Calculator'
        signature = f'{{{left}, {right}}}' + (f': {{{left}: number; {right}: number}}' if typed else '')
        original = f'''import React from 'react';
export function {entry}({signature}) {{
  if (!Number.isFinite({left}) || !Number.isFinite({right}) || {left} < 0 || {right} < 0) {{
    return <p>입력 오류</p>;
  }}
  return <output data-testid="{key}">{{{left} * {right} + 100}}</output>;
}}
'''
        requirement = (f'기존 React 프로젝트에 숫자 props {left}, {right}를 받는 Calculator 컴포넌트를 작성하세요. '
            f'React import를 포함하세요. Number.isFinite와 음수 검사로 잘못된 입력에는 "입력 오류"를 표시하고, '
            f'정상 입력에는 <output data-testid="{key}"> 안에 {left} * {right} + {fee} 계산값만 표시하세요. '
            '이 과제에는 상태·이벤트·브라우저 API가 필요하지 않습니다. 별도 계산 함수로 나누어도 됩니다.')
        suffix = 'tsx' if typed else 'jsx'
    request = f'{language}/{mode.title()}로 작성하세요. {requirement} 고른 답변 방식을 따르고 파일 이름과 ```{suffix} 코드 블록을 제시하세요. 실행·타입 검사에 통과했다고 주장하지 마세요.'
    if patch:
        request += f'\n기존 파일은 아래와 같습니다. 변경 부분 선호면 {entry} 함수 전체 또는 마지막 return 줄만 제시하세요. 전체 코드 선호면 필요한 전체 파일을 제시하세요.\n```{suffix}\n{original}```'
    return dict(id=f'{mode}-{label}', label=label, input=request, route=route, key=key, left=left, right=right,
                fee=fee, patch=patch, original=original, entry=entry)


def evaluation_for(mode, language):
    language = 'TypeScript' if language.casefold() == 'typescript' else 'JavaScript'
    def tasks(rows):
        return [_task(mode, language, *row) for row in rows]
    train = tasks([('구독 비용', '/subscriptions/amount', 'subscription', 'months', 'monthlyRate', 510, False),
                   ('배송 계산 변경', '/parcels/cost', 'parcel', 'weight', 'unitRate', 2300, True)])
    validation = tasks([('작업실 요금', '/studio/fee', 'studio', 'hours', 'hourlyRate', 710, False),
                        ('식수 비용 변경', '/meals/charge', 'meal', 'count', 'unitPrice', 1200, True)])
    holdout = tasks([('보관 요금', '/storage/quote', 'storage', 'days', 'dailyRate', 1600, False),
                     ('이용권 변경', '/passes/price', 'passPrice', 'tickets', 'ticketPrice', 430, True)])
    rules = scoring_rules('fastapi', {'preferences': {'explanation':'brief','comments':'essential','structure':'compact','output':'complete'}})
    rules['checks'] = {'syntax': '설치된 TypeScript 파서의 JS/TS·JSX 구문 구조 확인. 타입·실행 검사는 아님.',
        'binding': 'React import·컴포넌트와 props 연결 확인.' if mode == 'react' else 'Express import·app 생성·GET 경로·핸들러 연결 확인.',
        'validation': '준비된 음수·비숫자·누락 입력에서 오류 표시/응답 분기 확인.',
        'calculation': '세 정상 입력의 제한된 산술식과 출력/반환값 확인.'}
    return SimpleNamespace(VERSION=VERSION, LIMITATION=LIMITATION, PREFERENCE_CHECKS=PREFERENCE_CHECKS,
        TRAIN=train, VALIDATION=validation, HOLDOUT=holdout, CHECK_RULES=rules['checks'],
        evaluate=lambda task, response, profile: evaluate(mode, language, task, response, profile))


def evaluate(mode, language, task, response, profile, *, limitation=LIMITATION):
    checks = dict(syntax=False, binding=False, validation=False, calculation=False)
    preferences = dict(explanation=False, comments=None, structure=None, output=False)
    observations = {}
    if isinstance(response, str) and response.strip() and len(response) <= 24000:
        inspection = inspect_answer(profile, response, task['patch'])
        preferences['explanation'] = inspection['preferences']['explanation']
        observations = inspection['observations']
        fences = r'```(?:vue|jsx?|tsx?|javascript|typescript)\s*\n(.*?)```' if mode == 'vue' else r'```(?:jsx?|tsx?|javascript|typescript)\s*\n(.*?)```'
        codes = re.findall(fences, response, re.S | re.I)
        file_names = []
        if mode == 'nextjs':
            for match in re.finditer(fences, response, re.S | re.I):
                prefix = response[:match.start()].rstrip().splitlines()
                heading = re.sub(r'^\s*#{1,6}\s+', '', prefix[-1] if prefix else '').strip().strip('`* ')
                file_names.append(heading if re.fullmatch(r'(?:src/)?app/[\w/-]+\.(?:ts|js)', heading) else None)
        if available() and 1 <= len(codes) <= 8:
            try:
                process = subprocess.run([shutil.which('node'), str(ROOT / 'scripts/check_web_coding.mjs')],
                    input=json.dumps(dict(task=task, codes=codes, language=language, mode=mode, file_names=file_names), ensure_ascii=False),
                    text=True, encoding='utf-8', capture_output=True, timeout=6, cwd=ROOT)
                data = json.loads(process.stdout) if process.returncode == 0 else {}
                if set(data.get('checks', {})) == set(checks) and all(type(v) is bool for v in data['checks'].values()):
                    checks = data['checks']
                    complete = data.get('complete', data['has_import'])
                    partial = data.get('partial', not data['has_import'])
                    preferences['output'] = partial if task['patch'] and profile['preferences']['output'] == 'changes' else complete
            except (OSError, subprocess.TimeoutExpired, ValueError, KeyError):
                pass
    failed = [key for key, ok in {**checks, **preferences}.items() if ok is False]
    return dict(score=weighted_score(checks, preferences, 'syntax'), checks=checks, preferences=preferences,
        observations=observations, feedback='정적 검사 미확인: ' + ', '.join(failed) + '\n고정 선호: ' + str(profile['preferences'])
        + '\n주석·역할 구성은 직접 확인합니다. 원본 선호를 유지하는 일반 보충 안내만 제안하고 과제 경로·정답 숫자를 복사하지 마세요.\n' + limitation)

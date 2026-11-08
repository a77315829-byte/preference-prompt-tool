"""Bounded repeated comparisons of prepared examples; not a calibrated preference model."""
from __future__ import annotations

from coding_examples import build_coding_examples

AXES = ('explanation', 'comments', 'structure', 'output')


def _variant(value, replacements):
    if isinstance(value, str):
        for before, after in replacements:
            value = value.replace(before, after)
        return value
    if isinstance(value, list):
        return [_variant(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: _variant(item, replacements) for key, item in value.items()}
    return value


def build_coding_elicitation(profile):
    base = build_coding_examples(profile)
    contexts = [
        ('order', '주문 합계', []),
        ('rental', '대여 요금', [('23,000', '21,000'), ('23000', '21000'), ('Order', 'Rental'), ('order', 'rental'), ('상품', '대여'), ('주문', '대여'),
            ('배송비', '보증금'), ('수량', '대여 일수'), ('quantity', 'days'), ('단가', '하루 요금'),
            ('3,000', '1,000'), ('3000', '1000'), ('2,500', '500'), ('2500', '500'), ('23,000', '21,000')]),
        ('print', '인쇄 요금', [('23,000', '20,200'), ('23000', '20200'), ('Order', 'Print'), ('order', 'print'), ('상품', '인쇄'), ('주문', '인쇄'),
            ('배송비', '기본 작업비'), ('수량', '인쇄 부수'), ('quantity', 'copies'), ('단가', '장당 요금'),
            ('3,000', '200'), ('3000', '200'), ('2,500', '100'), ('2500', '100'), ('23,000', '20,200')]),
    ]
    rounds = []
    for context, label, replacements in contexts:
        for pair in base['pairs']:
            item = _variant(pair, replacements)
            item.update(id=f'{context}:{pair["axis"]}', context=label,
                        task=_variant(base['task'], replacements))
            if context == 'rental':
                item['options'].reverse()
            rounds.append(item)
    return {**base, 'version': 3, 'pairs': rounds[:8], 'followups': rounds[8:],
            'source': {**base['source'], 'id': base['source']['id'] + ':repeated-v1',
                       'label': base['source']['label'] + ' · 주문·대여·인쇄 비교'},
            'notice': base['notice'] + ' 기본 8회, 미확정 항목은 최대 2회 더 비교합니다. 반복 선택의 일관성만 확인하며, 취향의 정확도나 코드 품질을 보장하지 않습니다.'}


def summarize_rounds(rounds, bank):
    by_id = {item['id']: item for item in bank['pairs'] + bank['followups']}
    summary = {}
    for axis in AXES:
        rows = [row for row in rounds if by_id[row['id']]['axis'] == axis]
        values = [row['value'] for row in rows if row['value'] is not None]
        consistent = len(values) >= 2 and len(set(values)) == 1
        summary[axis] = {'answered': len(values), 'total': len(rows), 'consistent': consistent,
                         'value': values[0] if consistent else None,
                         'status': 'consistent' if consistent else 'mixed' if len(set(values)) > 1 else 'unresolved'}
    return summary


def validate_elicitation(comparison, profile):
    bank = build_coding_elicitation(profile)
    rows = comparison.get('rounds')
    if not isinstance(rows, list) or not 8 <= len(rows) <= 10:
        raise ValueError('8~10회의 비교 기록을 확인해 주세요.')
    expected = bank['pairs'][:]
    normalized = []
    for index, row in enumerate(rows):
        if index == 8:
            summary = summarize_rounds(normalized, bank)
            unresolved = [axis for axis in AXES if not summary[axis]['consistent']][:2]
            expected += [item for item in bank['followups'] if item['axis'] in unresolved]
        if index >= len(expected) or not isinstance(row, dict) or row.get('id') != expected[index]['id']:
            raise ValueError('비교 순서나 예시가 현재 개발 환경과 다릅니다. 다시 비교해 주세요.')
        value = row.get('value')
        if 'value' not in row or (value is not None and value not in [option['value'] for option in expected[index]['options']]):
            raise ValueError('비교에서 고른 값을 확인해 주세요.')
        normalized.append({'id': row['id'], 'value': value})
    base_summary = summarize_rounds(normalized[:8], bank)
    required = 8 + min(2, sum(not item['consistent'] for item in base_summary.values()))
    if len(rows) != required or comparison.get('example', {}).get('id') != bank['source']['id']:
        raise ValueError('남은 비교를 마치거나 개발 환경을 다시 확인해 주세요.')
    summary = summarize_rounds(normalized, bank)
    for axis in AXES:
        if comparison['choices'][axis] is not None and comparison['choices'][axis] != summary[axis]['value']:
            raise ValueError('미확정 항목은 확인 화면에서 직접 골라 주세요.')
    return {'version': 3, 'choices': dict(comparison['choices']), 'rounds': normalized,
            'example': bank['source'], 'summary': summary}

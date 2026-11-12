"""Predeclared independent technical and target-match aggregates."""
from benchmarks.coding_react_current.run import RUN, ARMS, PROFILES, read, write, verify, seal, validate_review


def aggregate():
    verify()
    packet = read(RUN/'blind_packet.json'); mapping = read(RUN/'blind_mapping.json')
    evaluations = {r['output_id']: read(RUN/f'evaluation/{r["output_id"]}.json') for r in packet}
    reviews = {key: read(RUN/f'review_{key}.json') for key in ('a', 'b')}
    for rows in reviews.values(): validate_review(rows, packet)
    report = {'technical': {}, 'target_match_by_reviewer': {}, 'disagreements': [], 'ambiguity_flags': [], 'execution_claim_flags': []}
    for arm in ARMS:
        ids = [oid for oid, item in mapping.items() if item['arm'] == arm]
        result = {'answers': len(ids), 'delivery_ready': 0, 'compiler_pass': 0, 'clean_type_pass': 0,
                  'type_completed': 0, 'runtime_pass': 0, 'runtime_completed': 0, 'type_runtime_joint': 0,
                  'runtime_checks_passed': 0, 'runtime_checks_total': 0, 'unresolved_or_errors': []}
        for oid in ids:
            item = evaluations[oid]; typed = item.get('types') or {}; runtime = item.get('runtime') or {}
            result['delivery_ready'] += read(RUN/f'materialized/{oid}.json')['status'] == 'ready'
            result['compiler_pass'] += typed.get('compilerPassed') is True
            result['clean_type_pass'] += typed.get('passed') is True
            result['type_completed'] += typed.get('status') == 'completed'
            result['runtime_pass'] += runtime.get('passed') is True
            result['runtime_completed'] += runtime.get('status') == 'completed'
            result['type_runtime_joint'] += typed.get('passed') is True and runtime.get('passed') is True
            result['runtime_checks_passed'] += sum(c['passed'] for c in runtime.get('checks', []))
            result['runtime_checks_total'] += len(runtime.get('checks', []))
            if typed.get('status') != 'completed' or runtime.get('status') != 'completed':
                result['unresolved_or_errors'].append({'output_id': oid, 'status': item.get('status'),
                    'type_status': typed.get('status'), 'runtime_status': runtime.get('status'),
                    'safety_pass': item.get('safety', {}).get('passed')})
        report['technical'][arm] = result
    by_review = {}
    for key, rows in reviews.items():
        by_review[key] = {r['output_id']: r for r in rows}; totals = {}
        for arm in ARMS:
            selected = [r for r in rows if mapping[r['output_id']]['arm'] == arm]
            totals[arm] = {'answers': len(selected), 'dimensions': {axis: sum(r['dimensions'][axis]['match'] for r in selected) for axis in PROFILES['P1']},
                'all_four': sum(all(v['match'] for v in r['dimensions'].values()) for r in selected),
                'type_runtime_all_four_joint': sum(
                    all(v['match'] for v in r['dimensions'].values()) and
                    (evaluations[r['output_id']].get('types') or {}).get('passed') is True and
                    (evaluations[r['output_id']].get('runtime') or {}).get('passed') is True for r in selected)}
        report['target_match_by_reviewer'][key] = totals
    for row in packet:
        oid = row['output_id']; a = by_review['a'][oid]; b = by_review['b'][oid]
        differences = [axis for axis in PROFILES['P1'] if a['dimensions'][axis]['match'] != b['dimensions'][axis]['match']]
        if differences: report['disagreements'].append({'output_id': oid, 'dimensions': differences})
        if a['ambiguities'] or b['ambiguities']: report['ambiguity_flags'].append(oid)
        if a['unsupported_execution_claims'] or b['unsupported_execution_claims']: report['execution_claim_flags'].append(oid)
    report['interpretation'] = 'General target match is spontaneous alignment, not violation of unsupplied preferences. Denominator is eight paired tasks per arm; individual assertions and rubric dimensions are not independent tasks. Missing execution remains unknown, not success. AI review is not human preference evidence.'
    write(RUN/'scores.json', report)
    seal(RUN/'review_seal.json', [RUN/f'review_{k}.json' for k in ('a', 'b')] + [RUN/'scores.json'] + sorted((RUN/'evaluation').glob('*.json')))
    return report


if __name__ == '__main__':
    import json
    print(json.dumps(aggregate(), ensure_ascii=False, indent=2))

"""Strict evidence/provenance audit, separate from the frozen scoring procedure."""
import argparse

from benchmarks.summary_reflection import run


def quotes(value, text, allow_empty=False):
    assert isinstance(value, list), 'Evidence must be a list'
    assert allow_empty or value, 'Evidence must not be empty'
    assert all(isinstance(q, str) and q.strip() and q in text for q in value), 'Nonempty exact evidence required'


def strict_review(rows, packet):
    run.validate_review(rows, packet)
    by_id = {r['output_id']: r for r in packet}
    for row in rows:
        item = by_id[row['output_id']]
        assert type(row['sentence_count']) is int
        assert isinstance(row['issues'], list)
        for fact in row['facts']:
            assert isinstance(fact['reason'], str) and fact['reason'].strip()
            quotes(fact['summary_evidence'], item['summary'], allow_empty=not fact['preserved'])
        for issue in row['issues']:
            quote = issue['summary_quote']
            assert isinstance(quote, str) and quote.strip() and quote in item['summary']
            assert isinstance(issue['reason'], str) and issue['reason'].strip()
            quotes(issue['source_evidence'], item['source'], allow_empty=True)


def audit(stage):
    run.verify(stage)
    folder = run.RUN / stage
    packet = run.read(folder / 'blind_packet.json')
    for key in ('a', 'b'):
        strict_review(run.read(folder / f'review_{key}.json'), packet)
    report = {'stage': stage, 'reviews_validated': len(packet)*2,
              'nonempty_exact_evidence': True, 'reviewer_scores_changed': False,
              'audit_code_sha256': run.sha(__file__),
              'note': 'Format/source-evidence audit only. Exact quotation presence does not prove semantic correctness.'}
    run.write(folder / 'evidence_audit.json', report)
    print(report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['selection', 'final'], required=True)
    audit(parser.parse_args().stage)

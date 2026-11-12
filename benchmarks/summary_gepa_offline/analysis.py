"""Post-search diagnostics; never changes GEPA scores, decisions or outputs."""
from benchmarks.summary_gepa_offline.run import RUN, read, write, verify
from benchmarks.summary_agent_pilot.evaluate import length_pass
from checks.summarization_grounded_v2 import split_sentences


def main():
    verify()
    result=read(RUN/'gepa_result.json')
    records=[read(p) for p in (RUN/'evaluation_cache').glob('*.json')]
    expected={c['id'] for c in read(RUN/'validation/cases.json')}
    diagnostics=[]
    for index,candidate in enumerate(result['candidates']):
        rows=[r for r in records if r['case']['id'] in expected and r['supplement']==candidate['supplement']]
        assert len(rows)==len(expected) and {r['case']['id'] for r in rows}==expected
        raw=sum(r['score'] for r in rows)/len(rows)
        assert abs(raw-result['val_scores'][index])<1e-10
        reviewed=[];disagreements=[]
        for r in rows:
            review=r['review'];profile=r['case']['profile']
            reviewed_length=length_pass(review['sentence_count'],profile['length'])
            reviewed_form=reviewed_length and review['wording_pass']
            coverage=sum(f['preserved'] for f in review['facts'])/3
            reviewed.append(coverage if reviewed_form and not review['issues'] else 0)
            automatic_count=len(split_sentences(r['summary']))
            auto_length=r['automatic']['length']['score']==1
            auto_wording=r['automatic']['extractiveness']['score']==1
            if automatic_count!=review['sentence_count'] or auto_length!=reviewed_length or auto_wording!=review['wording_pass']:
                disagreements.append({'id':r['case']['id'],'automatic_sentence_count':automatic_count,
                    'reviewed_sentence_count':review['sentence_count'],'automatic_length_pass':auto_length,
                    'reviewed_length_pass':reviewed_length,'automatic_wording_pass':auto_wording,
                    'reviewed_wording_pass':review['wording_pass']})
        diagnostics.append({'candidate_index':index,'supplement_words':len(candidate['supplement'].split()),
            'gepa_validation_score':raw,'review_only_diagnostic_score':sum(reviewed)/len(reviewed),
            'facts_preserved':sum(f['preserved'] for r in rows for f in r['review']['facts']),
            'facts_total':len(rows)*3,'factual_issue_outputs':sum(bool(r['review']['issues']) for r in rows),
            'auto_review_disagreements':disagreements})
    report={'candidates':diagnostics,'not_used_for_selection':True,
        'interpretation':'Recomputes diagnostics from the original optimization reviews after the search. No new grading, no changed GEPA winner, no heldout evidence used. These are validation statistics, not final quality.',
        'limitation':'Review-only score is itself AI judgement; removing automatic gates retrospectively is diagnostic, not a new validated metric.'}
    write(RUN/'optimization_diagnostics.json',report)
    print(diagnostics)


if __name__=='__main__':main()

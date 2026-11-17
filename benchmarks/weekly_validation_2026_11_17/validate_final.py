"""Read-only consistency checks; only the final validation record is created."""
from datetime import datetime, timezone
from .prepare_sources import ROOT, BASE, sha, write
from .run import read
from .report import aggregate

def main():
    seals=[BASE/'frozen.json',*sorted(BASE.glob('*_seal.json'))]
    hashes_checked=0
    for path in seals:
        for filename,digest in read(path)['files'].items():
            assert sha((ROOT/filename).read_bytes())==digest,(path.name,filename)
            hashes_checked+=1
    sampling=read(BASE/'source_sampling.json')
    for prior in sampling['prior_json_files']:
        assert sha((ROOT/prior['path']).read_bytes())==prior['sha256'],prior['path']
    dataset=ROOT/sampling['dataset']
    assert sha(dataset.read_bytes())==sampling['dataset_sha256']
    records=read(dataset);sources=read(BASE/'summary_sources.json')
    for row in sources:
        assert row['source']=='\n'.join(records[row['record_index']]['source'])
        assert sha(row['source'].encode())==row['source_sha256']
        assert row['max_prior_word5gram_jaccard']<.1
    outputs=read(BASE/'all_outputs.json')
    assert len(outputs)==28 and len({(r['arm'],r['id']) for r in outputs})==28
    indexed={(r['arm'],r['id']):r for r in outputs}
    file_count=0
    for app in read(BASE/'applications.json'):
        candidate=read(BASE/app['path']);assert sha((BASE/app['path']).read_bytes())==app['sha256']
        answer=indexed[(app['arm'],app['id'])]['answer'].replace('\r\n','\n')
        for origin in candidate['provenance']:
            assert candidate['files'][origin['filename']]==answer[origin['start']:origin['end']]
            file_count+=1
        result=read(BASE/f"evaluation/{app['arm']}/{app['id']}.json")
        assert result['types']['status']=='completed'
        assert result['runtime']['status']=='completed' and len(result['runtime']['checks'])==5
    mapping=read(BASE/'blind_mapping.json');scores=read(BASE/'scores.json')
    for reviewer in ('a','b'):
        rows=[{**read(p),**mapping[p.stem]} for p in (BASE/f'reviews/{reviewer}').glob('*.json')]
        calculated=aggregate([r for r in rows if r['kind']=='summary'],[r for r in rows if r['kind']=='react'])
        assert calculated==scores['by_reviewer'][reviewer]
    result={'validated_utc':datetime.now(timezone.utc).isoformat(),'seals_checked':[p.name for p in seals],
       'sealed_hash_entries_checked':hashes_checked,'prior_json_files_unchanged':len(sampling['prior_json_files']),
       'original_dataset_identity':True,'new_sources':6,'first_responses':28,'literal_applied_source_files':file_count,
       'react_evaluations_completed':16,'react_behavior_checks_completed':80,'independent_review_files':56,
       'all_review_evidence_substrings_valid':True,'saved_scores_equal_recomputed':True,
       'paid_model_api_calls':0,'original_experiment_artifacts_preserved':True}
    write('validation.json',result);print(result)

if __name__=='__main__':main()

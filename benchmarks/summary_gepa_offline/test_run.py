import pytest

from benchmarks.summary_gepa_offline import run
from benchmarks.summary_gepa_offline.diagnostics import lcs_f1


@pytest.mark.parametrize('a,b,expected',[
    ('A b c','a b c',1.0),('A b','x y',0.0),('a a b','a b',.8),('a b','b a',.5),('','a',0.0)])
def test_reference_lcs_definition(a,b,expected):
    assert lcs_f1(a,b)==pytest.approx(expected)


@pytest.mark.parametrize('scores,invalid,expected,aliases,exploratory',[
    ([1.,1.],False,0,{'gepa':'current'},1),
    ([.5,1.],False,1,{},None),
    ([.5,1.],True,0,{'gepa':'current'},None),
])
def test_final_choice_uses_only_validation_and_excludes_invalid(tmp_path,monkeypatch,scores,invalid,expected,aliases,exploratory):
    monkeypatch.setattr(run,'ROOT',tmp_path)
    monkeypatch.setattr(run,'RUN',tmp_path/'run')
    monkeypatch.setattr(run,'verify',lambda:None)
    candidates=[{'supplement':''},{'supplement':'Preserve the central result.'}]
    run.write(run.RUN/'gepa_result.json',{'candidates':candidates,'val_scores':scores,'best_index':1,
              'invalid_candidates':[{'candidate':candidates[1]}] if invalid else []})
    run.write(run.RUN/'final/cases.json',[{'id':'H01','source':'Example source.','base_prompt':'Fixed instruction.'}])
    run.prepare_final()
    plan=run.read(run.RUN/'final_plan.json')
    assert plan['selected_index']==expected
    assert plan['aliases']==aliases and plan['exploratory_index']==exploratory
    assert run.read(run.RUN/'final/inputs/current.json')[0]['prompt']=='Fixed instruction.'
    run.check_seal(run.RUN/'final_input_seal.json')


def test_empty_hash_manifest_rejected(tmp_path):
    path=tmp_path/'empty.json';run.write(path,{})
    with pytest.raises(AssertionError):run.check_seal(path)

from coding_evaluation_report import scoring_rules, weighted_score
from tests.test_spring_boot_optimization import PROFILE, answer
from spring_boot_evaluation import TRAIN, evaluate


def test_v2_excludes_semantic_preferences_from_automatic_score_and_records_evidence():
    profile = {**PROFILE, 'preferences': {
        'explanation': 'steps', 'comments': 'detailed', 'structure': 'modular', 'output': 'changes'}}
    result = evaluate(TRAIN[0], answer(TRAIN[0]), profile)
    assert all(result['checks'].values())
    assert result['preferences'] == {'explanation': False, 'comments': None, 'structure': None, 'output': True}
    assert result['score'] == .825
    assert '개수로 적절함을 판정하지 않음' in result['observations']['comments']
    assert 'PriceController' in result['observations']['structure']
    rules = scoring_rules('spring_boot', profile)
    assert (rules['function_weight'], rules['preference_weight']) == (.65, .35)
    assert '제목의 번호' in rules['preferences']['explanation']
    assert rules['preference_keys'] == ['explanation', 'output']
    assert rules['manual_preferences'] == ['comments', 'structure']
    assert weighted_score({k: False for k in result['checks']}, {k: True for k in profile['preferences']}, 'code_structure') == 0


def test_fastapi_and_spring_reports_explain_different_structure_and_output_rules():
    spring = scoring_rules('spring_boot', PROFILE)
    fastapi = scoring_rules('fastapi', PROFILE)
    assert spring['gate'] == 'code_structure' and fastapi['gate'] == 'syntax'
    assert '클래스' in spring['preferences']['structure']
    assert '함수' in fastapi['preferences']['structure']
    assert 'FastAPI import' in fastapi['preferences']['output']
    assert '컴파일 검사' in spring['checks']['code_structure']

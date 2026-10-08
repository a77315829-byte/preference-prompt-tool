"""합성 선택 시뮬레이션이며 실제 사용자 평가 결과가 아니다."""
from itertools import product
from pathlib import Path
import service
from demos.coding_dataset import generate_coding_pair, load_corpus
from engine.domain_loader import load_domain
from optimize.run_gepa import build_seed_prompt

DOMAIN = str(Path(__file__).resolve().parents[1] / "domains/coding.yaml")


def test_all_eight_profiles_recovered_in_live_session(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No paid API in demo")
    monkeypatch.setattr(service, "generate_all", forbidden)
    domain = load_domain(DOMAIN)
    axes = load_corpus()["axes"]
    for values in product(*axes.values()):
        target = dict(zip(axes, values))
        states = [service.start_session("same input", "coding", DOMAIN, model="unused", demo_mode=True) for _ in range(2)]
        # 현재 UI는 중복 질문을 피하므로 이 도메인은 축마다 한 번씩, 총 3회 묻는다.
        assert states[0].total_rounds == 3
        for _ in range(states[0].total_rounds):
            a, b = states[0].pair.a, states[0].pair.b
            assert a.text == states[1].pair.a.text
            assert b.text == states[1].pair.b.text
            changed = [key for key in axes if a.combo[key] != b.combo[key]]
            assert len(changed) == 1
            winner = "a" if a.combo[changed[0]] == target[changed[0]] else "b"
            states = [service.submit_choice(s, s.pair.pair_id, winner) for s in states]
        for state in states:
            assert state.done
            assert {a.name: a.estimate for a in state.axes} == target
            assert all(a.discriminated >= 1 for a in state.axes)
            _, estimator, _ = service._rebuild(state)
            prompt = build_seed_prompt(domain, estimator)
            for axis in domain.axes:
                assert axis.instruction_for(target[axis.name]) in prompt


def test_holdout_not_exposed_and_no_hidden_axis_labels():
    corpus = load_corpus()
    profile = corpus["variants"][0]["profile"]
    for index in range(20):
        texts = generate_coding_pair("arbitrary", index, profile, profile)
        assert texts[0] == texts[1]
        assert any(t["request"] in texts[0] for t in corpus["tasks"] if t["split"] == "elicitation")
        assert all(t["request"] not in texts[0] for t in corpus["tasks"] if t["split"] == "holdout")
        assert "code_structure" not in texts[0]

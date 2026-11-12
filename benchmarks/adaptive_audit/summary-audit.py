import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

def guard(event, args):
    if event == 'socket.connect':
        raise AssertionError('Network forbidden')
    if event == 'open' and isinstance(args[0], (str, bytes)):
        if pathlib.Path(args[0]).name == '.env':
            raise AssertionError('.env access forbidden')

sys.addaudithook(guard)
import service

counts = {'completed': 0, 'undo_variants': 0, 'reopened_longer': 0}
for domain in ('summarization', 'summarization_ko'):
    initial = service.start_session('첫 번째 문장입니다. 다음 문장도 있습니다. Another sentence. ' * 20,
        domain, str(ROOT / 'domains' / f'{domain}.yaml'), model='forbidden', demo_mode=True)
    pending = [initial]
    while pending:
        state = pending.pop()
        if not state.done:
            for choice in ('a', 'b', 'tie'):
                pending.append(service.submit_choice(state, state.pair.pair_id, choice))
            continue
        counts['completed'] += 1
        assert state.pair is None
        assert state.answered <= state.round_limit <= 8
        assert state.completion_reason in ('round_limit', 'selection_resolved', 'no_more_pairs')
        undone = service.undo_choice(state)
        assert not undone.done and undone.completion_reason is None and undone.prompt is None
        assert undone.total_rounds == initial.total_rounds
        assert undone.answered + 1 == state.answered
        assert undone.pair.a.combo == state.history[-1][0]
        assert undone.pair.b.combo == state.history[-1][1]
        for choice in ('a', 'b', 'tie'):
            changed = service.submit_choice(undone, undone.pair.pair_id, choice)
            counts['undo_variants'] += 1
            if choice == state.history[-1][2]:
                assert changed.done and changed.completion_reason == state.completion_reason
                assert changed.axes == state.axes
            if not changed.done:
                counts['reopened_longer'] += 1
                while not changed.done:
                    changed = service.submit_choice(changed, changed.pair.pair_id, 'a')
                assert changed.answered <= state.round_limit
    print(f'PASS exhaustive {domain}: automatic completion and every last-answer replacement')
print(counts)

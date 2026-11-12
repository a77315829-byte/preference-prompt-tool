import json
import pathlib
import socket
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(AssertionError('Network forbidden'))
from coding_elicitation import build_adaptive_coding_elicitation
from coding_instructions import build_coding_instructions

profile = {'language': 'Python', 'framework': 'FastAPI', 'extra': '', 'preferences': {
    'explanation': 'brief', 'comments': 'essential', 'structure': 'compact', 'output': 'complete'}}
folder = pathlib.Path(__file__).parent
if len(sys.argv) == 1:
    (folder / 'examples.json').write_text(json.dumps(build_adaptive_coding_elicitation(profile), ensure_ascii=False), encoding='utf-8')
else:
    rows = json.loads((folder / 'profiles.json').read_text(encoding='utf-8'))
    for row in rows:
        draft = build_coding_instructions(row['profile'])
        assert draft['profile']['comparison']['summary'] == row['profile']['comparison']['summary'], row['name']
        assert build_coding_instructions(draft['profile']) == draft
    print(f'PASS real backend validates {len(rows)} UI profiles and exact evidence summaries')

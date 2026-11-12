import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

import api_server
from app_db import Database
from auth import AuthService
from coding_optimization_jobs import CodingOptimizationJobs
from team import TeamError, TeamStore

PROFILE = {'language': 'Python', 'framework': 'FastAPI', 'extra': '', 'preferences':
           {'explanation': 'brief', 'comments': 'essential', 'structure': 'compact', 'output': 'complete'}}
HISTORY = [({'code_structure': 'compact'}, {'code_structure': 'separated'}, 'a')]


def test_job_result_survives_new_store_and_is_never_shared_between_owners(tmp_path):
    db = Database(tmp_path / 'app.db')
    user, _ = AuthService(db).signup('alice', 'alice-password-123')
    jobs = CodingOptimizationJobs(db)
    done = threading.Event()
    def run(*_):
        done.set()
        return {'profile': PROFILE, 'changed': False, 'original_prompt': 'original', 'improved_prompt': 'original'}
    job = jobs.start(user.id, PROFILE, run, lambda: None, str)
    assert done.wait(2)
    for _ in range(100):
        if jobs.get(user.id, job['id'])['status'] == 'done': break
        time.sleep(.01)
    restored = CodingOptimizationJobs(db)
    assert restored.get(user.id, job['id'])['result']['original_prompt'] == 'original'
    assert restored.list_for(user.id)[0]['id'] == job['id']
    assert restored.list_for(user.id + 1) == []
    with pytest.raises(LookupError): restored.get(user.id + 1, job['id'])
    with db.connect() as conn:
        conn.execute('UPDATE coding_optimization_jobs SET expires_at = 0')
    with pytest.raises(LookupError): CodingOptimizationJobs(db).get(user.id, job['id'])
    restored.jobs[job['id']]['expires_at'] = 0
    with pytest.raises(LookupError): restored.get(user.id, job['id'])
    assert restored.list_for(user.id) == []


def test_interrupted_job_is_visible_but_never_rerun_automatically(tmp_path):
    db = Database(tmp_path / 'app.db')
    user, _ = AuthService(db).signup('alice', 'alice-password-123')
    jobs = CodingOptimizationJobs(db)
    jobs._persist({'id': 'interrupted', 'owner': user.id, 'started': time.monotonic(), 'profile': PROFILE,
                   'status': 'running', 'result': None, 'error': '', 'saved_id': None})
    restored = CodingOptimizationJobs(db).list_for(user.id)
    assert restored[0]['status'] == 'error'
    assert '재시작' in restored[0]['error']


def test_protected_team_read_join_expiry_close_and_idle_retention(tmp_path, monkeypatch):
    db = Database(tmp_path / 'app.db')
    auth = AuthService(db)
    alice, _ = auth.signup('alice', 'alice-password-123')
    bob, _ = auth.signup('bob', 'bob-password-123')
    now = datetime.now(timezone.utc)
    store = TeamStore(db, lambda: now)
    code = store.create('private team name', 'coding', alice.id)
    monkeypatch.setattr(api_server, 'TEAMS', store)
    for visitor in (None, bob.id):
        payload = api_server._team_payload(code, visitor)
        assert payload['requires_join'] and payload['name'] != 'private team name'
        assert not payload['members'] and not payload['prompts']
        with pytest.raises(TeamError): store.require_read(code, visitor)
    with pytest.raises(TeamError): store.add(code, 'coding', 'anon', HISTORY)
    with pytest.raises(TeamError): store.set_invitation(code, bob.id, False)
    store.set_invitation(code, alice.id, False)
    with pytest.raises(TeamError): store.add(code, 'coding', 'bob', HISTORY, bob.id, 'bob')
    store.set_invitation(code, alice.id, True)
    store.add(code, 'coding', 'bob', HISTORY, bob.id, 'bob')
    store.set_invitation(code, alice.id, False)
    store.require_read(code, bob.id)
    now += timedelta(days=31)
    store.create('another team', 'coding', alice.id)
    assert store.name_for(code) == 'private team name'
    fresh = store.create('expires', 'coding', alice.id)
    now += timedelta(days=8)
    with pytest.raises(TeamError): store.add(fresh, 'coding', 'bob', HISTORY, bob.id, 'bob')
    with db.connect() as conn:
        conn.execute('DELETE FROM users WHERE id = ?', (alice.id,))
    assert store.access(code)['protected']
    with pytest.raises(TeamError): store.require_read(code)
    store.require_read(code, bob.id)

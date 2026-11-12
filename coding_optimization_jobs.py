"""Owner-scoped, bounded background jobs for supported coding GEPA paths."""
from __future__ import annotations

import copy
import json
import threading
import time
import uuid

from coding_gepa import coding_draft
from coding_answer_review import validate_human_review


class CodingOptimizationJobs:
    def __init__(self, db=None):
        self.lock = threading.RLock()
        self.jobs = {}
        self.db = db

    def _persist(self, job):
        if self.db is None:
            return
        db = self.db() if callable(self.db) else self.db
        with db.connect() as conn:
            conn.execute('DELETE FROM coding_optimization_jobs WHERE expires_at < ?', (time.time(),))
            conn.execute('''INSERT OR REPLACE INTO coding_optimization_jobs (id, owner_id, expires_at, job_json)
                SELECT ?, ?, ?, ? WHERE EXISTS (SELECT 1 FROM users WHERE id = ?)''',
                (job['id'], job['owner'], job.setdefault('expires_at', time.time() + 7 * 86400),
                 json.dumps(self._public(job), ensure_ascii=False), job['owner']))

    def _restore(self, owner, job_id):
        if self.db is None:
            return None
        db = self.db() if callable(self.db) else self.db
        with db.connect() as conn:
            row = conn.execute('SELECT job_json, expires_at FROM coding_optimization_jobs WHERE id = ? AND owner_id = ? AND expires_at > ?',
                               (job_id, owner, time.time())).fetchone()
        if row is None:
            return None
        job = {**json.loads(row['job_json']), 'owner': owner, 'started': time.monotonic(), 'expires_at': row['expires_at']}
        if job['status'] == 'running':
            job.update(status='error', stage='서버 재시작으로 중단됨', error='서버가 재시작되어 이 작업은 중단됐어요. 이전 요청을 자동으로 다시 실행하지 않습니다.')
            self._persist(job)
        self.jobs[job_id] = job
        return job

    def list_for(self, owner):
        with self.lock:
            ids = [key for key, job in self.jobs.items() if job['owner'] == owner]
            if self.db is not None:
                db = self.db() if callable(self.db) else self.db
                with db.connect() as conn:
                    ids += [row['id'] for row in conn.execute('SELECT id FROM coding_optimization_jobs WHERE owner_id = ? AND expires_at > ? ORDER BY expires_at DESC LIMIT 20', (owner, time.time()))]
            result = []
            for key in dict.fromkeys(ids):
                try:
                    result.append(self._public(self._owned(owner, key)))
                except LookupError:
                    continue
            return sorted(result, key=lambda job: job.get('created_at', 0), reverse=True)[:20]

    def _owned(self, owner, job_id):
        job = self.jobs.get(job_id)
        if job and job.get('expires_at', float('inf')) <= time.time():
            self.jobs.pop(job_id, None)
            job = None
        if not job or (job['owner'] == owner and job['status'] != 'running' and time.monotonic()-job['started'] > 7200):
            job = self._restore(owner, job_id)
        if not job or job['owner'] != owner or time.monotonic()-job['started'] > 7200:
            raise LookupError('개선 작업을 찾을 수 없어요. 서버를 다시 켰거나 보관 시간이 지난 경우 다시 시작해 주세요.')
        return job

    @staticmethod
    def _public(job):
        return copy.deepcopy({k: v for k, v in job.items() if k not in ('owner', 'started', 'expires_at')})

    def get(self, owner, job_id):
        with self.lock:
            return self._public(self._owned(owner, job_id))

    def start(self, owner, raw_profile, run, consume, describe_error):
        draft = coding_draft(raw_profile)
        with self.lock:
            now = time.monotonic()
            self.jobs = {key: job for key, job in self.jobs.items() if job['status'] == 'running' or now-job['started'] < 7200}
            active = [job for job in self.jobs.values() if job['status'] == 'running']
            for job in active:
                if job['owner'] == owner:
                    if job['profile'] == draft['profile']:
                        return self._public(job)
                    raise ValueError('먼저 진행 중인 개선 작업이 끝날 때까지 기다려 주세요.')
            if len(active) >= 2:
                raise ValueError('현재 다른 개선 작업이 진행 중이에요. 잠시 후 다시 시도해 주세요.')
            if len(self.jobs) >= 100:
                oldest = min((j for j in self.jobs.values() if j['status'] != 'running'), key=lambda j: j['started'])
                self.jobs.pop(oldest['id'])
            consume()
            job = {'id': uuid.uuid4().hex, 'owner': owner, 'started': now, 'profile': draft['profile'],
                   'created_at': time.time(),
                   'status': 'running', 'stage': 'GEPA 평가를 준비하는 중', 'model_calls': 0, 'result': None,
                   'error': '', 'saved_id': None}
            self.jobs[job['id']] = job
            self._persist(job)

        def progress(update):
            with self.lock:
                job.update({k: v for k, v in update.items() if k in ('stage', 'model_calls', 'call_limit')})

        def work():
            try:
                result = run(draft['profile'], progress)
                with self.lock:
                    job.update(status='done', stage='개선 전후를 확인해 주세요', result=result)
                    self._persist(job)
            except Exception as exc:
                with self.lock:
                    job.update(status='error', stage='개선을 마치지 못했어요', error=describe_error(exc))
                    self._persist(job)
        worker = threading.Thread(target=work, daemon=True)
        try:
            worker.start()
        except Exception:
            with self.lock:
                job.update(status='error', error='개선 작업을 시작하지 못했어요. 다시 시도해 주세요.')
                self._persist(job)
            raise
        return self.get(owner, job['id'])

    def save(self, owner, job_id, title, store, human_review=None):
        with self.lock:
            job = self._owned(owner, job_id)
            if job['status'] != 'done' or not job['result'] or not job['result']['changed']:
                raise ValueError('개선 후보가 준비된 뒤에 새 항목으로 저장할 수 있어요.')
            if job['saved_id']:
                return store.get(owner, job['saved_id'])
            result = job['result']
            review = validate_human_review(human_review,
                {task['id'] for task in result['report'].get('holdout_before', {}).get('tasks', [])}, result['changed'])
            item = store.create(owner, {'title': title, 'domainKey': 'coding', 'prompt': result['improved_prompt'],
                'codingProfile': result['profile'], 'note': f"{result['profile']['framework']} · GEPA 개선 후보. 원본 지침과 별도로 저장한 항목입니다."},
                optimization={'method': 'gepa', 'original_prompt': result['original_prompt'], 'guidance': result['guidance'],
                              'report': result['report'], **({'human_review': review} if review else {})})
            job['saved_id'] = item['id']
            self._persist(job)
            return item

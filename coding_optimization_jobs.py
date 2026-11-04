"""Owner-scoped, bounded background jobs for supported coding GEPA paths."""
from __future__ import annotations

import copy
import threading
import time
import uuid

from coding_gepa import coding_draft
from coding_answer_review import validate_human_review


class CodingOptimizationJobs:
    def __init__(self):
        self.lock = threading.RLock()
        self.jobs = {}

    def _owned(self, owner, job_id):
        job = self.jobs.get(job_id)
        if not job or job['owner'] != owner or time.monotonic()-job['started'] > 7200:
            raise LookupError('개선 작업을 찾을 수 없어요. 서버를 다시 켰거나 보관 시간이 지난 경우 다시 시작해 주세요.')
        return job

    @staticmethod
    def _public(job):
        return copy.deepcopy({k: v for k, v in job.items() if k not in ('owner', 'started')})

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
                   'status': 'running', 'stage': 'GEPA 평가를 준비하는 중', 'model_calls': 0, 'result': None,
                   'error': '', 'saved_id': None}
            self.jobs[job['id']] = job

        def progress(update):
            with self.lock:
                job.update({k: v for k, v in update.items() if k in ('stage', 'model_calls', 'call_limit')})

        def work():
            try:
                result = run(draft['profile'], progress)
                with self.lock:
                    job.update(status='done', stage='개선 전후를 확인해 주세요', result=result)
            except Exception as exc:
                with self.lock:
                    job.update(status='error', stage='개선을 마치지 못했어요', error=describe_error(exc))
        worker = threading.Thread(target=work, daemon=True)
        try:
            worker.start()
        except Exception:
            with self.lock:
                job.update(status='error', error='개선 작업을 시작하지 못했어요. 다시 시도해 주세요.')
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
            return item

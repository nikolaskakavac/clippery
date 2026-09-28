import threading
import time
import uuid
import logging
from concurrent.futures import ThreadPoolExecutor
from app.config import JOB_TTL, MAX_DOWNLOAD_SECONDS, MAX_JOBS, JOB_ROOT
from app.services.storage import LocalStorage
from app.services.video_service import extract, ServiceError
from app.services.download_service import process
from app.services.clip_service import create_clip
from app.utils.validation import normalize_url

class JobManager:
    def __init__(self):
        self.storage = LocalStorage()
        self.jobs = {}
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=MAX_JOBS)

    def submit(self, request, clip=False):
        with self.lock:
            if sum(j['state'] not in {'Ready', 'Failed'} for j in self.jobs.values()) >= MAX_JOBS:
                raise ServiceError('Another video is processing. Please wait until it finishes.')
            job_id = uuid.uuid4().hex
            self.jobs[job_id] = {'id': job_id, 'state': 'Preparing', 'progress': 0,
                                 'error': None, 'created': time.time(), 'readers': 0}
            self.pool.submit(self.run, job_id, request, clip)
            return self.public(job_id)

    def public(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return None
            return {k: job[k] for k in ('id', 'state', 'progress', 'error')}

    def update(self, job_id, state, progress):
        with self.lock:
            self.jobs[job_id].update(state=state, progress=progress)

    def run(self, job_id, request, clip):
        try:
            info = extract(request.url)
            url, _ = normalize_url(request.url)
            directory = self.storage.directory(job_id)
            update = lambda state, progress: self.update(job_id, state, progress)
            if clip:
                output = create_clip(url, request.quality, directory, update, request.start, request.end, info['duration'])
            else:
                if info['duration'] > MAX_DOWNLOAD_SECONDS:
                    raise ServiceError('Full downloads are limited to 60 minutes. Use Clip for longer videos.')
                output = process(url, request.quality, directory, update)
            with self.lock:
                self.jobs[job_id].update(path=output, state='Ready', progress=100, created=time.time())
        except Exception as exc:
            logging.getLogger(__name__).exception('Processing job failed: %s', job_id)
            message = str(exc) if isinstance(exc, (ServiceError, ValueError)) else 'Video processing failed. Check that FFmpeg is installed, or try another public video.'
            with self.lock:
                self.jobs[job_id].update(state='Failed', error=message, created=time.time())
            self.storage.remove(job_id)

    def acquire(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or job['state'] != 'Ready' or not job['path'].is_file():
                return None
            job['readers'] += 1
            return job['path']

    def release(self, job_id):
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id]['readers'] -= 1
                self.jobs[job_id]['created'] = time.time() - JOB_TTL
        self.cleanup()

    def cleanup(self):
        with self.lock:
            for job_id, job in list(self.jobs.items()):
                if job['state'] in {'Ready', 'Failed'} and not job['readers'] and time.time() - job['created'] >= JOB_TTL:
                    self.storage.remove(job_id)
                    del self.jobs[job_id]
            # Expire orphan directories left by a process restart.
            if JOB_ROOT.exists():
                for path in JOB_ROOT.iterdir():
                    if path.is_dir() and path.name not in self.jobs and time.time() - path.stat().st_mtime >= JOB_TTL:
                        self.storage.remove(path.name)

manager = JobManager()

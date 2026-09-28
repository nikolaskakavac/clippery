import os
from pathlib import Path

MAX_RESOLUTION = 1080
MAX_DOWNLOAD_SECONDS = 3600
MAX_SOURCE_SECONDS = 10800
MAX_CLIP_SECONDS = 300
MAX_JOBS = 1
JOB_TTL = int(os.getenv('JOB_TTL_SECONDS', '3600'))
JOB_ROOT = Path(os.getenv('JOB_ROOT', './tmp/jobs')).resolve()
FRONTEND_ORIGIN = os.getenv('FRONTEND_ORIGIN', 'http://localhost:3000')

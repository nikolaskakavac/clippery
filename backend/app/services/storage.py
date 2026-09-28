from pathlib import Path
import shutil
from typing import Protocol
from app.config import JOB_ROOT

class Storage(Protocol):
    def directory(self, job_id: str) -> Path: ...
    def remove(self, job_id: str) -> None: ...

class LocalStorage:
    def directory(self, job_id: str) -> Path:
        path = JOB_ROOT / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def remove(self, job_id: str) -> None:
        shutil.rmtree(JOB_ROOT / job_id, ignore_errors=True)

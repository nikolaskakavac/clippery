import tempfile
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from starlette.background import BackgroundTask
from app.services import tiktok_service

router = APIRouter(prefix='/api/quick-download/tiktok')
download_lock = threading.Lock()


class TikTokRequest(BaseModel):
    url: str = Field(max_length=2048)

    @field_validator('url')
    @classmethod
    def validate_url(cls, value):
        return tiktok_service.normalize(value)


@router.post('/info')
def info(request: TikTokRequest):
    return tiktok_service.metadata(request.url)


@router.post('/download')
def download(request: TikTokRequest):
    if not download_lock.acquire(blocking=False):
        raise HTTPException(409, 'Another Quick Download is running. Try again when it finishes.')
    directory = None
    try:
        directory = tempfile.TemporaryDirectory(prefix='clippery-tiktok-')
        path = tiktok_service.download(request.url, Path(directory.name))
        media_type = {'.mp4': 'video/mp4', '.webm': 'video/webm', '.mkv': 'video/x-matroska', '.mov': 'video/quicktime'}[path.suffix]
        return FileResponse(path, media_type=media_type, filename=f'clippery-tiktok{path.suffix}', background=BackgroundTask(directory.cleanup))
    except Exception:
        if directory:
            directory.cleanup()
        raise
    finally:
        download_lock.release()

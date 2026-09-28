from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from app.models.video import VideoRequest, DownloadRequest, ClipRequest
from app.services.video_service import metadata
from app.services.transcript_service import provider
from app.services.jobs import manager

router = APIRouter(prefix='/api/video')

@router.post('/info')
def info(request: VideoRequest):
    return metadata(request.url)

@router.post('/transcript')
def transcript(request: VideoRequest):
    return provider.get(request.url)

@router.post('/download', status_code=202)
def download(request: DownloadRequest):
    return manager.submit(request)

@router.post('/clip', status_code=202)
def clip(request: ClipRequest):
    return manager.submit(request, clip=True)

@router.get('/jobs/{job_id}')
def status(job_id: str):
    job = manager.public(job_id)
    if not job:
        raise HTTPException(404, 'This job expired or does not exist. Create it again.')
    return job

@router.get('/jobs/{job_id}/file')
def file(job_id: str, request: Request):
    if 'range' in request.headers:
        raise HTTPException(416, 'Partial downloads are not supported. Download the complete file.')
    path = manager.acquire(job_id)
    if path is None:
        raise HTTPException(404, 'This file is not ready or has expired.')
    return FileResponse(path, media_type='video/mp4', filename=f'clipper-{job_id[:8]}.mp4',
                        background=BackgroundTask(manager.release, job_id))


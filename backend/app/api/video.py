from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
import logging
import re
import tempfile
import zipfile
from starlette.background import BackgroundTask
from app.models.video import VideoRequest, DownloadRequest, ClipRequest, ArchiveRequest
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

@router.post('/archive')
def archive(request: ArchiveRequest):
    acquired = []
    output = tempfile.TemporaryFile()
    try:
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as bundle:
            for index, item in enumerate(request.clips, 1):
                path = manager.acquire(item.job_id)
                if path is None:
                    raise HTTPException(404, 'A clip is unavailable or expired. Export it again before downloading the ZIP.')
                acquired.append(item.job_id)
                name = re.sub(r'[^\w .()-]', '_', item.name).strip(' .') or 'Clip'
                # A numbered prefix prevents collisions and unsafe reserved filenames.
                stem = f'{index:02d}_{name}'
                bundle.write(path, f'{stem}.mp4')
                if item.srt:
                    bundle.writestr(f'{stem}.srt', item.srt)
        output.seek(0)
    except Exception as exc:
        output.close()
        if isinstance(exc, HTTPException):
            raise
        logging.getLogger(__name__).exception('Could not prepare clip archive')
        raise HTTPException(500, 'Could not prepare the ZIP. Try again.') from exc
    finally:
        for job_id in acquired:
            manager.release(job_id, consume=False)

    def chunks():
        try:
            while chunk := output.read(1024 * 1024):
                yield chunk
        finally:
            output.close()

    return StreamingResponse(chunks(), media_type='application/zip',
                             headers={'Content-Disposition': 'attachment; filename="clippery-clips.zip"'},
                             background=BackgroundTask(output.close))

@router.get('/jobs/{job_id}/file')
def file(job_id: str, request: Request, preview: bool = False, original: bool = False):
    if original and not preview:
        raise HTTPException(400, 'The original clip is available for preview only.')
    if not preview and 'range' in request.headers:
        raise HTTPException(416, 'Partial downloads are not supported. Download the complete file.')
    path = manager.acquire(job_id, original=original)
    if path is None:
        raise HTTPException(404, 'This file is not ready or has expired.')
    name = manager.public(job_id).get('filename') or f'clipper-{job_id[:8]}.mp4'
    return FileResponse(path, media_type='video/mp4', filename=name,
                        content_disposition_type='inline' if preview else 'attachment',
                        background=BackgroundTask(manager.release, job_id, consume=not preview))


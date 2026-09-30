import time

from fastapi.testclient import TestClient
from app.main import app
from app.api import video
from app.services import jobs
from test_services import manager


def ready_file(manager, monkeypatch):
    monkeypatch.setattr(video, 'manager', manager)
    path = manager.storage.directory('preview') / 'clip.mp4'
    path.write_bytes(b'0123456789')
    manager.jobs['preview'] = dict(state='Ready', path=path, readers=0, created=time.time())
    return path


def test_preview_ranges_preserve_file_for_download(manager, monkeypatch):
    path = ready_file(manager, monkeypatch)
    client = TestClient(app)
    for byte_range, expected in [('bytes=0-3', b'0123'), ('bytes=6-9', b'6789')]:
        response = client.get('/api/video/jobs/preview/file?preview=true', headers={'Range': byte_range})
        assert response.status_code == 206
        assert response.content == expected
        assert response.headers['content-disposition'].startswith('inline')
        assert path.exists() and manager.jobs['preview']['readers'] == 0
    response = client.get('/api/video/jobs/preview/file')
    assert response.status_code == 200 and response.content == b'0123456789'
    assert response.headers['content-disposition'].startswith('attachment')
    assert not path.exists()


def test_preview_still_expires_and_download_ranges_still_rejected(manager, monkeypatch):
    path = ready_file(manager, monkeypatch)
    client = TestClient(app)
    assert client.get('/api/video/jobs/preview/file', headers={'Range': 'bytes=0-3'}).status_code == 416
    assert client.get('/api/video/jobs/preview/file?preview=true').status_code == 200
    monkeypatch.setattr(jobs, 'JOB_TTL', -1)
    manager.cleanup()
    assert not path.exists()
    assert client.get('/api/video/jobs/preview/file?preview=true').status_code == 404

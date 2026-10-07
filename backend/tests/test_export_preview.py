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


def test_compare_original_preserves_both_files_and_downloads_processed(manager, monkeypatch):
    processed = ready_file(manager, monkeypatch)
    original = processed.parent / 'original.mp4'
    original.write_bytes(b'original-video')
    manager.jobs['preview'].update(original_path=original, hasOriginal=True)
    client = TestClient(app)
    for query, expected in [('preview=true&original=true', b'orig'), ('preview=true', b'0123')]:
        response = client.get(f'/api/video/jobs/preview/file?{query}', headers={'Range': 'bytes=0-3'})
        assert response.status_code == 206 and response.content == expected
        assert original.exists() and processed.exists()
        assert manager.jobs['preview']['readers'] == 0
    assert 'original_path' not in manager.public('preview')
    assert client.get('/api/video/jobs/preview/file?original=true').status_code == 400
    response = client.get('/api/video/jobs/preview/file')
    assert response.content == b'0123456789'
    assert not original.exists() and not processed.exists()


def test_original_preview_unavailable_without_silence_output(manager, monkeypatch):
    path = ready_file(manager, monkeypatch)
    assert TestClient(app).get('/api/video/jobs/preview/file?preview=true&original=true').status_code == 404
    assert path.exists() and manager.jobs['preview']['readers'] == 0

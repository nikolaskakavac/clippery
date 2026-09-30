import io
import time
import zipfile

from fastapi.testclient import TestClient
from app.main import app
from app.api import video
from test_services import manager


def setup_files(manager, monkeypatch):
    monkeypatch.setattr(video, 'manager', manager)
    for job_id in ('one', 'two'):
        path = manager.storage.directory(job_id) / 'clip.mp4'
        path.write_bytes(job_id.encode())
        manager.jobs[job_id] = dict(state='Ready', path=path, readers=0, created=time.time())


def test_archive_contents_names_subtitles_and_preserved_sources(manager, monkeypatch):
    setup_files(manager, monkeypatch)
    response = TestClient(app).post('/api/video/archive', json={'clips': [
        {'job_id': 'one', 'name': '../same', 'srt': '1\n00:00:00,000 --> 00:00:01,000\nHello\n'},
        {'job_id': 'two', 'name': '../same'}]})
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as bundle:
        assert len(bundle.namelist()) == 3
        assert all('/' not in name and '\\' not in name for name in bundle.namelist())
        assert bundle.read(bundle.namelist()[0]) == b'one'
        assert bundle.read(bundle.namelist()[1]).endswith(b'Hello\n')
        assert bundle.read(bundle.namelist()[2]) == b'two'
    for job in manager.jobs.values():
        assert job['path'].exists() and job['readers'] == 0


def test_missing_archive_clip_releases_earlier_files(manager, monkeypatch):
    setup_files(manager, monkeypatch)
    response = TestClient(app).post('/api/video/archive', json={'clips': [
        {'job_id': 'one', 'name': 'One'}, {'job_id': 'missing', 'name': 'Missing'}]})
    assert response.status_code == 404
    assert manager.jobs['one']['readers'] == 0
    assert manager.jobs['one']['path'].exists()


def test_archive_rejects_empty_or_oversized_batch():
    client = TestClient(app)
    for clips in ([], [{'job_id': 'one', 'name': 'One'}] * 101):
        assert client.post('/api/video/archive', json={'clips': clips}).status_code == 422

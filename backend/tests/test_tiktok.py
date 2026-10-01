from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from yt_dlp import YoutubeDL
from app.main import app
from app.services import tiktok_service as service
from app.api import quick_download

URL = 'https://www.tiktok.com/@creator/video/1234567890123456789'


@pytest.mark.parametrize('url', [URL, URL + '?tracking=1', 'https://vm.tiktok.com/ABC123/', 'https://www.tiktok.com/t/ABC123/'])
def test_tiktok_urls(url):
    assert service.normalize(url).startswith('https://')


@pytest.mark.parametrize('url', ['https://tiktok.com.evil.test/@x/video/123', 'http://localhost/a',
    'https://www.tiktok.com/@creator', 'https://user@www.tiktok.com/@x/video/123',
    'https://www.tiktok.com:8080/@x/video/123', 'https://www.tiktok.com/@x/photo/123',
    'https://youtube.com/watch?v=dQw4w9WgXcQ'])
def test_invalid_urls_rejected(url):
    assert TestClient(app).post('/api/quick-download/tiktok/info', json={'url': url}).status_code == 422


def test_short_link_redirect_is_validated(monkeypatch):
    calls = []
    def head(self, url, **kwargs):
        calls.append(url)
        return service.httpx.Response(302, headers={'location': 'http://127.0.0.1/secret'})
    monkeypatch.setattr(service.httpx.Client, 'head', head)
    with pytest.raises(ValueError):
        service.resolve('https://vm.tiktok.com/ABC123/')
    assert len(calls) == 1


def test_real_format_selection_prefers_high_resolution_separate_streams():
    opts = service.options()
    assert 'extractor_args' not in opts and 'postprocessors' not in opts
    with YoutubeDL(opts) as ydl:
        result = ydl.process_ie_result({'id': '123', 'title': 'Test', 'extractor': 'TikTok', 'formats': [
            {'format_id': 'low', 'url': 'https://example.com/low.mp4', 'height': 360, 'width': 640, 'vcodec': 'h264', 'acodec': 'aac', 'ext': 'mp4'},
            {'format_id': 'high', 'url': 'https://example.com/high.mp4', 'height': 2160, 'width': 3840, 'vcodec': 'h264', 'acodec': 'none', 'ext': 'mp4'},
            {'format_id': 'audio', 'url': 'https://example.com/audio.m4a', 'vcodec': 'none', 'acodec': 'aac', 'ext': 'm4a'},
        ]}, download=False)
    assert result['height'] == 2160
    assert [item['format_id'] for item in result['requested_formats']] == ['high', 'audio']


def test_metadata_optional_fields(monkeypatch):
    monkeypatch.setattr(service, 'extract', lambda _: {'webpage_url': URL})
    response = TestClient(app).post('/api/quick-download/tiktok/info', json={'url': URL})
    assert response.status_code == 200
    assert response.json()['duration'] is None and response.json()['thumbnail'] is None


def test_safe_extraction_failure(monkeypatch):
    monkeypatch.setattr(service, 'resolve', lambda _: URL)
    def fail(*args, **kwargs):
        raise RuntimeError('private upstream secret')
    monkeypatch.setattr(service.YoutubeDL, 'extract_info', fail)
    response = TestClient(app).post('/api/quick-download/tiktok/info', json={'url': URL})
    assert response.status_code == 400 and 'secret' not in response.text


def test_download_delivers_original_bytes_and_cleans_up(monkeypatch):
    paths = []
    def download(url, directory):
        path = directory / 'tiktok.mp4'
        path.write_bytes(b'original video bytes')
        paths.append(path)
        return path
    monkeypatch.setattr(service, 'download', download)
    response = TestClient(app).post('/api/quick-download/tiktok/download', json={'url': URL})
    assert response.content == b'original video bytes'
    assert not paths[0].exists()
    assert not quick_download.download_lock.locked()


def test_download_failure_cleans_up(monkeypatch):
    paths = []
    def fail(url, directory):
        paths.append(directory)
        (directory / 'partial').write_bytes(b'partial')
        raise service.ServiceError(service.ERROR)
    monkeypatch.setattr(service, 'download', fail)
    assert TestClient(app).post('/api/quick-download/tiktok/download', json={'url': URL}).status_code == 400
    assert not paths[0].exists() and not quick_download.download_lock.locked()

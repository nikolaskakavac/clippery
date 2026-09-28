from fastapi.testclient import TestClient
from app.main import app
from app.services import video_service
from app.services.download_service import format_selector

client = TestClient(app)
def test_health(): assert client.get('/health').json() == {'status':'ok'}
def test_bad_url_api():
    response = client.post('/api/video/info', json={'url':'http://localhost:8000/health'})
    assert response.status_code == 422
    assert 'traceback' not in response.text.lower()
def test_normalized_metadata(monkeypatch):
    monkeypatch.setattr(video_service, 'extract', lambda _: {'id':'dQw4w9WgXcQ','title':'Example','channel':'Creator','duration':100,'secret':'never exposed'})
    data = client.post('/api/video/info', json={'url':'https://youtube.com/shorts/dQw4w9WgXcQ'}).json()
    assert data['isShort'] is True
    assert data['durationFormatted'] == '00:01:40'
    assert 'secret' not in data

def test_unknown_job(): assert client.get('/api/video/jobs/unknown/file').status_code == 404

def test_quality_cap():
    assert 'height<=1080' in format_selector('best')
    assert 'height<=720' in format_selector('720')
    assert 'height<=1080' in format_selector('2160')

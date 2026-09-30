from app.services import output_metadata as service, jobs
from app.models.video import ClipRequest
from test_services import manager, finish, URL


def test_metadata_uses_actual_file_and_fractional_fps(tmp_path, monkeypatch):
    path = tmp_path / 'export.mp4'
    path.write_bytes(b'1234567')
    monkeypatch.setattr(service, 'probe', lambda actual: {'streams': [
        {'codec_type': 'audio', 'codec_name': 'aac'},
        {'codec_type': 'video', 'width': 1280, 'height': 720, 'codec_name': 'h264', 'avg_frame_rate': '30000/1001'}]})
    assert service.output_metadata(path) == {'width': 1280, 'height': 720, 'fps': 29.97, 'codec': 'h264', 'sizeBytes': 7}


def test_unknown_frame_rate_is_not_invented(tmp_path, monkeypatch):
    path = tmp_path / 'export.mp4'
    path.write_bytes(b'video')
    monkeypatch.setattr(service, 'probe', lambda _: {'streams': [{'codec_type': 'video', 'avg_frame_rate': '0/0'}]})
    assert service.output_metadata(path)['fps'] is None


def test_job_exposes_output_metadata_only_after_completion(manager, monkeypatch):
    monkeypatch.setattr(jobs, 'extract', lambda _: {'duration': 100})
    def clip(url, quality, directory, *args):
        path = directory / 'clip.mp4'
        path.write_bytes(b'video')
        return path
    monkeypatch.setattr(jobs, 'create_clip', clip)
    metadata = {'width': 1920, 'height': 1080, 'fps': 60, 'codec': 'h264', 'sizeBytes': 5}
    monkeypatch.setattr(jobs, 'output_metadata', lambda _: metadata)
    job = manager.submit(ClipRequest(url=URL, start=0, end=5), clip=True)
    result = finish(manager, job['id'])
    assert result['state'] == 'Ready'
    assert result['output'] == metadata
    assert 'path' not in result


def test_metadata_failure_does_not_fail_export(manager, monkeypatch):
    monkeypatch.setattr(jobs, 'extract', lambda _: {'duration': 100})
    def clip(url, quality, directory, *args):
        path = directory / 'clip.mp4'
        path.write_bytes(b'video')
        return path
    monkeypatch.setattr(jobs, 'create_clip', clip)
    monkeypatch.setattr(jobs, 'output_metadata', lambda _: (_ for _ in ()).throw(ValueError('bad probe')))
    job = manager.submit(ClipRequest(url=URL, start=0, end=5), clip=True)
    result = finish(manager, job['id'])
    assert result['state'] == 'Ready' and result['output'] is None
    assert manager.acquire(job['id']).exists()
    manager.release(job['id'])

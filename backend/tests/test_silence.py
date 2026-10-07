import shutil
import subprocess
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api import video
from app.models.video import ClipRequest, DownloadRequest
from app.services import jobs
from app.services.silence_service import kept_segments, remove_silence
from app.services.download_service import probe
from app.utils.filename import export_filename
from test_services import manager, finish, URL


def test_silence_intervals_preserve_padding_and_frame_boundaries():
    assert kept_segments('silence_start: 1\nsilence_end: 3', 4, 30) == [
        {'start': 0, 'end': 35 / 30}, {'start': 85 / 30, 'end': 4}]
    assert kept_segments('', 4, 30) == [{'start': 0, 'end': 4}]
    assert kept_segments('silence_start: 1', 4, 30)[0]['end'] > 1


@pytest.mark.parametrize('name,expected', [('Hook.mp4', 'Hook.mp4'), ('', 'default.mp4'),
    ('../CON', '_CON.mp4'), ('CON', '_CON.mp4'), ('a/b\r\n', 'a_b__.mp4'), ('moj klip', 'moj klip.mp4')])
def test_export_names_are_safe(name, expected):
    assert export_filename(name, 'default') == expected


def test_silence_is_opt_in_and_custom_filename_delivered(manager, monkeypatch):
    monkeypatch.setattr(video, 'manager', manager)
    monkeypatch.setattr(jobs, 'extract', lambda _: {'duration': 20})
    def clip(url, quality, directory, *args):
        path = directory / 'clipper.mp4'; path.write_bytes(b'original'); return path
    monkeypatch.setattr(jobs, 'create_clip', clip)
    monkeypatch.setattr(jobs, 'output_metadata', lambda _: None)
    monkeypatch.setattr(jobs, 'remove_silence', lambda *args: pytest.fail('Opt-in only'))
    job = manager.submit(ClipRequest(url=URL, start=0, end=5, filename='hook.mp4'), clip=True)
    ready = finish(manager, job['id'])
    assert ready['silence'] is None and ready['clipRange'] == {'start': 0, 'end': 5}
    response = TestClient(app).get(f'/api/video/jobs/{job["id"]}/file')
    assert response.content == b'original'
    assert 'filename="hook.mp4"' in response.headers['content-disposition']


def test_enabled_silence_uses_bounded_clip_and_publishes_map(manager, monkeypatch):
    monkeypatch.setattr(jobs, 'extract', lambda _: {'duration': 100})
    def clip(url, quality, directory, update, start, end, duration):
        assert (start, end) == (10, 15)
        path = directory / 'clipper.mp4'; path.write_bytes(b'bounded'); return path
    monkeypatch.setattr(jobs, 'create_clip', clip)
    monkeypatch.setattr(jobs, 'output_metadata', lambda _: None)
    mapping = {'beforeDuration': 5, 'afterDuration': 3, 'segments': [{'start': 2, 'end': 5}]}
    def cut(path, update):
        assert path.read_bytes() == b'bounded'
        output = path.parent / 'clipper-silence.mp4'
        output.write_bytes(b'processed')
        return output, mapping
    monkeypatch.setattr(jobs, 'remove_silence', cut)
    job = manager.submit(ClipRequest(url=URL, start=10, end=15, remove_silence=True), clip=True)
    result = finish(manager, job['id'])
    assert result['silence'] == mapping and result['hasOriginal'] is True
    original = manager.acquire(job['id'], original=True)
    assert original.read_bytes() == b'bounded'
    manager.release(job['id'], consume=False)
    assert not hasattr(DownloadRequest(url=URL), 'remove_silence')


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='FFmpeg required')
@pytest.mark.parametrize('mode', ['pauses', 'tone', 'silent', 'no-audio'])
def test_real_media_silence_processing(tmp_path, mode):
    source = tmp_path / 'clipper.mp4'
    args = ['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=30']
    if mode != 'no-audio':
        expression = {'pauses': 'if(between(t,1,3),0,0.3*sin(2*PI*440*t))',
                      'tone': '0.3*sin(2*PI*440*t)', 'silent': '0'}[mode]
        args += ['-f', 'lavfi', '-i', f'aevalsrc=exprs={expression}:s=48000']
    args += ['-t', '4', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(source)]
    # Escape expression commas for the lavfi parser, not the shell.
    if mode != 'no-audio':
        args[args.index('-i', args.index('-i') + 1) + 1] = f"aevalsrc=exprs='{expression}':s=48000"
    subprocess.run(args, capture_output=True, check=True, timeout=30)
    output, result = remove_silence(source, lambda *args: None)
    assert source.exists()
    if mode != 'pauses':
        assert output == source
        assert result['beforeDuration'] == result['afterDuration']
    else:
        assert output != source
        assert 2.25 < result['afterDuration'] < 2.6
        data = probe(output)
        v = next(s for s in data['streams'] if s['codec_type'] == 'video')
        a = next(s for s in data['streams'] if s['codec_type'] == 'audio')
        assert (v['width'], v['height'], v['codec_name'], a['codec_name']) == (320, 180, 'h264', 'aac')
        assert Fraction(v['avg_frame_rate']) == 30
        assert abs(float(v['duration']) - float(a['duration'])) < .1
        subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(output), '-f', 'null', '-'], check=True, capture_output=True, timeout=30)

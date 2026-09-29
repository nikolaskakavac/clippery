import shutil
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest
from yt_dlp import YoutubeDL
from app.services import download_service as service


def select(formats, quality='1080'):
    with YoutubeDL({'quiet': True, 'skip_download': True,
                    'format': service.format_selector(quality),
                    'format_sort': ['res', 'vcodec:h264', 'acodec:aac']}) as ydl:
        return ydl.process_ie_result({'id': 'fixture', 'title': 'fixture',
            'formats': [dict(url=f'https://example.com/{f["format_id"]}', **f) for f in formats]}, download=False)


def video(id, height, codec='avc1.640028', audio='none'):
    return dict(format_id=id, height=height, width=height * 16 // 9,
                vcodec=codec, acodec=audio, ext='mp4' if codec.startswith('avc') else 'webm')


AUDIO = dict(format_id='aac', vcodec='none', acodec='mp4a.40.2', ext='m4a')


@pytest.mark.parametrize('quality,height', [('1080', 1080), ('best', 1080), ('720', 720)])
def test_adaptive_video_beats_low_resolution_progressive(quality, height):
    result = select([video('progressive', 360, audio='mp4a.40.2'),
                     video('720', 720), video('1080', 1080), video('2160', 2160), AUDIO], quality)
    assert result['height'] == height
    assert [f['format_id'] for f in result['requested_formats']] == [str(height), 'aac']


def test_resolution_precedes_codec_preference():
    result = select([video('h264-720', 720), video('vp9-1080', 1080, 'vp9'), AUDIO])
    assert result['requested_formats'][0]['format_id'] == 'vp9-1080'


def test_h264_preferred_at_equal_resolution():
    result = select([video('h264', 1080), video('vp9', 1080, 'vp9'), AUDIO])
    assert result['requested_formats'][0]['format_id'] == 'h264'


def test_low_resolution_source_is_not_upscaled():
    result = select([video('low', 360), AUDIO])
    assert result['height'] == 360


def test_progressive_only_source_remains_supported():
    result = select([video('progressive', 480, audio='mp4a.40.2')])
    assert result['format_id'] == 'progressive'


@pytest.mark.parametrize('codec,audio,clip', [('h264', 'aac', True), ('vp9', 'opus', True), ('vp9', 'opus', False)])
def test_editor_encoding_and_remux(monkeypatch, tmp_path, codec, audio, clip):
    monkeypatch.setattr(service, 'probe', lambda _: {'streams': [
        {'codec_type': 'video', 'codec_name': codec, 'pix_fmt': 'yuv420p'},
        {'codec_type': 'audio', 'codec_name': audio}]})
    calls = []
    monkeypatch.setattr(service.subprocess, 'run', lambda args, **kwargs: calls.append(args))
    service.editor_mp4(tmp_path / 'source.mp4', tmp_path / 'output.mp4', lambda *args: None, clip=clip)
    args = calls[0]
    assert '-vf' not in args and '-s' not in args
    if codec == 'h264':
        assert args[args.index('-c:v') + 1] == 'copy'
        assert args[args.index('-c:a') + 1] == 'copy'
        assert '-crf' not in args
    else:
        assert args[args.index('-c:v') + 1] == 'libx264'
        assert args[args.index('-crf') + 1] == ('18' if clip else '20')
        assert args[args.index('-preset') + 1] == ('medium' if clip else 'veryfast')
        assert args[args.index('-c:a') + 1] == 'aac'
        if clip:
            assert args[args.index('-b:a') + 1] == '192k'


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='FFmpeg required')
def test_real_bounded_retry_retains_resolution_and_compatible_codecs(tmp_path, monkeypatch):
    source = tmp_path / 'fixture.mp4'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y',
        '-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=30',
        '-f', 'lavfi', '-i', 'sine=frequency=1000:sample_rate=48000',
        '-t', '4', '-c:v', 'libx264', '-crf', '16', '-g', '90',
        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart', str(source)], check=True, timeout=60)
    attempts = []

    class FixtureYDL(YoutubeDL):
        def download(self, urls):
            attempts.append(self.params['force_keyframes_at_cuts'])
            self.process_ie_result({'id': 'fixture', 'title': 'fixture', 'duration': 4,
                'url': f'http://127.0.0.1:{server.server_port}/fixture.mp4',
                'ext': 'mp4', 'height': 360, 'width': 640,
                'vcodec': 'avc1.64001e', 'acodec': 'mp4a.40.2'}, download=True)

    monkeypatch.setattr(service, 'YoutubeDL', FixtureYDL)
    real_usable = service.usable_section
    # Exercise the precise retry even if this FFmpeg version accepts the first cut.
    monkeypatch.setattr(service, 'usable_section', lambda path, length:
                        len(attempts) > 1 and real_usable(path, length))
    output_dir = tmp_path / 'job'
    output_dir.mkdir()
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(SimpleHTTPRequestHandler, directory=str(tmp_path)))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        output = service.process('fixture', '1080', output_dir, lambda *args: None, section=(0.75, 2.75))
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
    assert attempts == [False, True]
    data = service.probe(output)
    v = next(s for s in data['streams'] if s['codec_type'] == 'video')
    a = next(s for s in data['streams'] if s['codec_type'] == 'audio')
    assert (v['width'], v['height'], v['codec_name'], v['pix_fmt']) == (640, 360, 'h264', 'yuv420p')
    assert a['codec_name'] == 'aac'
    assert abs(float(data['format']['duration']) - 2) <= 0.15

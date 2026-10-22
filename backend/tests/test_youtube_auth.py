import base64
import io
import json
import os
import subprocess
from pathlib import Path

import pytest
from yt_dlp.utils import DownloadError

from app.services import youtube_auth as auth, video_service as video
from app.services import download_service as download, transcript_service as transcript
from app.services.youtube_errors import category

URL = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
COOKIES = '# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tfixture-secret\n'


@pytest.fixture(autouse=True)
def isolation(monkeypatch):
    for name in ('YOUTUBE_COOKIES_BASE64', 'YOUTUBE_COOKIES_FILE', 'RENDER', 'RENDER_SERVICE_ID'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(video.shutil, 'which', lambda _: 'tool')
    monkeypatch.setattr(video.time, 'sleep', lambda _: None)


def configure(monkeypatch, text=COOKIES):
    monkeypatch.setenv('YOUTUBE_COOKIES_BASE64', base64.b64encode(text.encode()).decode())


def test_anonymous_first_even_with_bad_cookie_configuration(monkeypatch):
    monkeypatch.setenv('YOUTUBE_COOKIES_BASE64', 'bad')
    calls = []
    assert video.run_youtube(lambda opts: calls.append(opts) or 42) == 42
    assert len(calls) == 1 and 'cookiefile' not in calls[0]


def test_auth_fallback_and_cleanup(monkeypatch, caplog):
    configure(monkeypatch)
    paths = []
    def operation(opts):
        if 'cookiefile' not in opts:
            raise DownloadError("Sign in to confirm you're not a bot. fixture-secret")
        path = Path(opts['cookiefile'])
        paths.append(path)
        assert 'fixture-secret' in path.read_text()
        if os.name == 'posix':
            assert path.stat().st_mode & 0o777 == 0o600
        return 42
    assert video.run_youtube(operation) == 42
    assert not paths[0].exists() and not paths[0].parent.exists()
    assert 'fixture-secret' not in caplog.text


def test_missing_cookies_does_not_loop():
    calls = []
    def fail(opts):
        calls.append(opts)
        raise DownloadError('Sign in to confirm you are not a bot')
    with pytest.raises(video.ServiceError, match='No YouTube cookies'):
        video.run_youtube(fail)
    assert len(calls) == 1


def test_invalid_configuration_on_auth_failure_is_safe(monkeypatch, caplog):
    monkeypatch.setenv('YOUTUBE_COOKIES_BASE64', 'private-invalid-base64')
    def fail(opts):
        raise DownloadError('LOGIN_REQUIRED: Cookie: SID=private-header https://example.com/?token=private-url')
    with pytest.raises(video.ServiceError, match='invalid Base64') as error:
        video.run_youtube(fail)
    assert 'private-' not in str(error.value) + caplog.text


@pytest.mark.parametrize('order', [('network', 'auth'), ('auth', 'network')])
def test_combined_fallbacks_never_exceed_three_sessions(monkeypatch, order):
    configure(monkeypatch)
    attempts = []
    def operation(opts):
        attempts.append(opts)
        if len(attempts) < 3:
            raise DownloadError('Connection timed out' if order[len(attempts)-1] == 'network' else 'Sign in required')
        assert Path(opts['cookiefile']).exists()
        assert opts['source_address'] == '0.0.0.0'
        return 'ok'
    assert video.run_youtube(operation) == 'ok'
    assert len(attempts) == 3
    assert not Path(attempts[-1]['cookiefile']).exists()


def test_authenticated_failure_cleans_cookie_copy(monkeypatch):
    configure(monkeypatch)
    paths = []
    def fail(opts):
        if opts.get('cookiefile'):
            paths.append(Path(opts['cookiefile']))
        raise DownloadError('Sign in to confirm you are not a bot')
    with pytest.raises(video.ServiceError, match='server may be challenged'):
        video.run_youtube(fail)
    assert len(paths) == 1 and not paths[0].exists()


def test_invalid_base64(monkeypatch):
    monkeypatch.setenv('YOUTUBE_COOKIES_BASE64', 'not-base64')
    with pytest.raises(auth.CookieConfigurationError, match='Base64'):
        with auth.cookie_file():
            pytest.fail('Invalid cookies used')


@pytest.mark.parametrize('text', [
    '{}', '# Netscape HTTP Cookie File\n',
    COOKIES.replace('\t0\t', '\tbad\t'), COOKIES.replace('\tTRUE\t', '\twrong\t', 1),
    COOKIES.replace('.youtube.com', 'youtube.com'), COOKIES.replace('fixture-secret', 'secret\textra'),
    COOKIES.replace('\t0\t', '\t1\t'),
])
def test_invalid_cookie_structure_or_expiration(monkeypatch, text, capsys):
    configure(monkeypatch, text)
    with pytest.raises(auth.CookieConfigurationError):
        auth.validated_cookies()
    assert 'secret' not in capsys.readouterr().err


def test_filters_other_domains_and_preserves_httponly(monkeypatch):
    configure(monkeypatch, COOKIES.replace('.youtube.com', '#HttpOnly_.youtube.com') +
              '.example.com\tTRUE\t/\tTRUE\t0\tSID\tunrelated-secret\n')
    with auth.cookie_file() as path:
        content = Path(path).read_text()
        assert '#HttpOnly_' in content and 'unrelated-secret' not in content


def test_local_cookie_original_not_modified(monkeypatch, tmp_path):
    original = tmp_path / 'cookies.txt'
    original.write_text(COOKIES)
    monkeypatch.setenv('YOUTUBE_COOKIES_FILE', str(original))
    with auth.cookie_file() as path:
        assert Path(path) != original
        Path(path).write_text('mutated by yt-dlp')
        with auth.cookie_file() as second:
            assert second != path
    assert original.read_text() == COOKIES


def test_local_file_missing_and_prohibited_on_render(monkeypatch, tmp_path):
    monkeypatch.setenv('YOUTUBE_COOKIES_FILE', str(tmp_path / 'missing'))
    with pytest.raises(auth.CookieConfigurationError, match='unreadable'):
        auth.validated_cookies()
    monkeypatch.setenv('RENDER', 'true')
    with pytest.raises(auth.CookieConfigurationError, match='Base64|BASE64'):
        auth.validated_cookies()


def test_base64_precedence(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv('YOUTUBE_COOKIES_FILE', 'missing')
    monkeypatch.setenv('RENDER', 'true')
    assert auth.validated_cookies() == COOKIES


def test_network_retry_is_bounded_and_uses_ipv4():
    calls = []
    def fail(opts):
        calls.append(opts)
        raise DownloadError('Connection timed out')
    with pytest.raises(video.ServiceError, match='limited retry'):
        video.run_youtube(fail)
    assert len(calls) == 2
    assert 'source_address' not in calls[0]
    assert calls[1]['source_address'] == '0.0.0.0'


@pytest.mark.parametrize('error,kind,public', [
    ('HTTP Error 429', 'rate_limit', 'rate limiting'),
    ('HTTP Error 403', 'access_denied', 'IP blocking'),
    ('Video unavailable', 'unavailable', 'unavailable'),
    ('n challenge solving failed', 'javascript', 'JavaScript'),
])
def test_failures_are_not_blindly_retried(monkeypatch, error, kind, public):
    configure(monkeypatch)
    calls = []
    def fail(opts):
        calls.append(opts)
        raise DownloadError(error)
    assert category(error) == kind
    with pytest.raises(video.ServiceError, match=public):
        video.run_youtube(fail)
    assert len(calls) == 1


def test_missing_node(monkeypatch):
    monkeypatch.setattr(video.shutil, 'which', lambda _: None)
    with pytest.raises(video.ServiceError, match='runtime is unavailable'):
        video.run_youtube(lambda _: pytest.fail('Must not extract'))


def test_ffmpeg_failure_does_not_log_command_or_retry(caplog):
    def fail(opts):
        raise subprocess.CalledProcessError(1, ['ffmpeg', '-headers', 'secret-header'], stderr='secret-output')
    with pytest.raises(video.ServiceError, match='FFmpeg') as error:
        video.run_youtube(fail)
    assert 'secret-' not in caplog.text + str(error.value)
    assert 'category=ffmpeg' in caplog.text


def test_real_metadata_entry_uses_fallback(monkeypatch):
    configure(monkeypatch)
    calls = []
    class YDL:
        def __init__(self, opts): self.opts = opts; calls.append(opts)
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def extract_info(self, url, download):
            assert url == URL and download is False
            if 'cookiefile' not in self.opts: raise DownloadError('Sign in')
            return {'id': 'dQw4w9WgXcQ', 'duration': 30}
    monkeypatch.setattr(video, 'YoutubeDL', YDL)
    assert video.metadata(URL)['duration'] == 30
    assert len(calls) == 2 and not Path(calls[1]['cookiefile']).exists()


@pytest.mark.parametrize('section', [None, (5, 10)])
def test_download_auth_failure_resolves_new_source_and_keeps_format(monkeypatch, tmp_path, section):
    configure(monkeypatch)
    monkeypatch.setattr(download, 'check_source_provider', lambda: None)
    monkeypatch.setattr(download, 'editor_mp4', lambda src, out, update, **kw: out.write_bytes(b'video'))
    monkeypatch.setattr(download, 'usable_section', lambda *args: True)
    calls = []
    class YDL:
        def __init__(self, opts): self.opts = opts; calls.append(opts)
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def extract_info(self, url, download):
            assert not (tmp_path / 'source.mp4.part').exists()
            return {'id': 'test', 'auth': 'cookiefile' in self.opts,
                    'requested_formats': [{'height': 1080, 'vcodec': 'h264'}]}
        def process_ie_result(self, info, download):
            if not info['auth']:
                (tmp_path / 'source.mp4.part').write_bytes(b'partial')
                raise DownloadError("Sign in to confirm you're not a bot")
            assert Path(self.opts['cookiefile']).exists()
            assert info['requested_formats'][0]['height'] == 1080
            (tmp_path / 'source.mp4').write_bytes(b'high quality')
    monkeypatch.setattr(download, 'YoutubeDL', YDL)
    assert download.process(URL, 'best', tmp_path, lambda *_: None, section).exists()
    assert len(calls) == 2 and calls[0]['format'] == calls[1]['format']
    assert not Path(calls[1]['cookiefile']).exists()
    if section:
        assert list(calls[1]['download_ranges']({}, None))[0] == {'start_time': 5, 'end_time': 10}


def test_transcript_reextracts_and_reads_caption_with_same_cookie_copy(monkeypatch):
    configure(monkeypatch)
    sessions = []
    def extract(url, *, session_options):
        sessions.append(session_options)
        return {'duration': 10, 'subtitles': {'en': [{'ext': 'json3', 'url': 'https://www.youtube.com/api/timedtext'}]}}
    class YDL:
        def __init__(self, opts): self.opts = opts
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def urlopen(self, url):
            if not self.opts.get('cookiefile'): raise DownloadError('Sign in required')
            assert self.opts['cookiefile'] == sessions[-1]['cookiefile']
            assert Path(self.opts['cookiefile']).exists()
            return io.BytesIO(json.dumps({'events': [{'tStartMs': 0, 'dDurationMs': 1000, 'segs': [{'utf8': 'Hi'}]}]}).encode())
    monkeypatch.setattr(transcript, 'extract', extract)
    monkeypatch.setattr(transcript, 'YoutubeDL', YDL)
    assert transcript.provider.get(URL)['segments'][0]['text'] == 'Hi'
    assert len(sessions) == 2 and not Path(sessions[1]['cookiefile']).exists()

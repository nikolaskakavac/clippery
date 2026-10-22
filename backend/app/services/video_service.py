import logging
import os
import re
import shutil
import subprocess
import time
from contextlib import ExitStack
from pathlib import Path
from urllib.error import URLError

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from yt_dlp.networking.exceptions import RequestError
from app.utils.validation import normalize_url
from app.utils.time import format_time
from app.services.youtube_auth import cookie_file, cookies_configured, CookieConfigurationError
from app.services.youtube_errors import category, public_error

logger = logging.getLogger(__name__)
BGUTIL_SERVER_HOME = Path(__file__).resolve().parents[2] / 'vendor' / 'bgutil-ytdlp-pot-provider' / 'server'


class ServiceError(Exception):
    pass


class DiagnosticLog:
    """Never emit arbitrary upstream text: it may contain cookies or signed URLs."""
    def debug(self, message):
        if os.getenv('YTDLP_DIAGNOSTICS', '').lower() not in {'1', 'true'}:
            return
        version = re.match(r'^\[debug\] (yt-dlp version|JS runtimes:) ([a-zA-Z0-9@._+/-]+)', message)
        if version:
            logger.warning('YouTube diagnostic: %s %s', *version.groups())
        elif message.startswith('[debug] [youtube] [pot'):
            # Only fixed event labels escape this adapter, never payloads/commands.
            event = next((label for marker, label in (
                ('Executing command to get POT', 'Invoking token generator (arguments omitted)'),
                ('PO Token Providers:', 'PO token providers registered'),
                ('PO Token Cache', 'PO token cache configured'),
                ('Deno executable not found', 'Optional Deno runtime unavailable; Node is configured'),
                ('failed', 'Token provider failure'), ('Failed', 'Token provider failure'),
                ('Fetching', 'Fetching token'), ('cache', 'Token cache activity'),
            ) if marker in message), 'Token provider activity')
            logger.warning('YouTube diagnostic: %s', event)

    def warning(self, message):
        logger.warning('YouTube upstream warning: category=%s', category(message))

    def error(self, message):
        logger.error('YouTube upstream error: category=%s', category(message))


def options() -> dict:
    diagnostic = os.getenv('YTDLP_DIAGNOSTICS', '').lower() in {'1', 'true'}
    return {'quiet': True, 'no_warnings': False, 'noplaylist': True,
            'verbose': diagnostic, 'logger': DiagnosticLog(),
            'extractor_args': {
                'youtube': {'player_client': ['mweb']},
                'youtubepot-bgutilscript': {'server_home': [str(BGUTIL_SERVER_HOME)]},
            },
            'socket_timeout': 25, 'retries': 2, 'fragment_retries': 2, 'extractor_retries': 1,
            'retry_sleep_functions': {'http': lambda n: min(2 ** n, 8),
                                      'fragment': lambda n: min(2 ** n, 8)},
            'sleep_interval_requests': 1, 'sleep_interval': 5, 'max_sleep_interval': 10,
            'js_runtimes': {'node': {}}, 'geo_bypass': False, 'cachedir': False, 'ignoreconfig': True}


def run_youtube(operation):
    """Anonymous first; at most one cookie fallback and one network retry.

    operation receives session options and must re-resolve signed media URLs on
    a retry. The private cookie copy lives until the complete operation closes.
    """
    if not shutil.which('node'):
        logger.error('YouTube extraction: missing_node_runtime')
        raise ServiceError('YouTube JavaScript runtime is unavailable on the server.')
    with ExitStack() as stack:
        session = options()
        authenticated = False
        network_retried = False
        for attempt in range(3):
            try:
                return operation(dict(session))
            except subprocess.SubprocessError:
                # Never include a subprocess command or stderr: yt-dlp/FFmpeg
                # commands can carry signed URLs and authentication headers.
                logger.error('YouTube media processing failed: category=ffmpeg')
                raise ServiceError(public_error('ffmpeg')) from None
            except (DownloadError, RequestError, URLError, TimeoutError, ConnectionError) as exc:
                kind = category(exc)
                logger.error('YouTube operation failed: category=%s attempt=%s authenticated=%s node_available=%s',
                               kind, attempt + 1, authenticated, bool(shutil.which('node')))
                if kind in {'authentication', 'bot_detection', 'cookies_rejected'} and not authenticated and cookies_configured():
                    try:
                        session['cookiefile'] = stack.enter_context(cookie_file())
                    except CookieConfigurationError as error:
                        logger.error('YouTube cookie configuration invalid')
                        raise ServiceError(str(error)) from None
                    except OSError:
                        logger.error('YouTube temporary credential storage unavailable')
                        raise ServiceError('YouTube authentication could not be initialized on the server.') from None
                    authenticated = True
                    time.sleep(2)
                    continue
                if kind == 'network' and not network_retried and attempt < 2:
                    network_retried = True
                    # One transport fallback, not IP rotation or a proxy.
                    session['source_address'] = '0.0.0.0'
                    time.sleep(2)
                    continue
                raise ServiceError(public_error(kind, authenticated)) from None
        raise ServiceError('YouTube retry limit reached. Please try again later.')


def extract(url: str, *, session_options=None) -> dict:
    canonical, _ = normalize_url(url)
    def read(opts):
        with YoutubeDL(opts) as ydl:
            return validate_info(ydl.extract_info(canonical, download=False))
    return read(session_options) if session_options is not None else run_youtube(read)


def validate_info(info):
    if info and info.get('availability') == 'needs_auth':
        raise DownloadError('Authentication required')
    if not info or info.get('is_live') or not info.get('duration'):
        raise ServiceError('Live streams and videos without a known duration are not supported.')
    if info.get('availability') in {'private', 'premium_only', 'subscriber_only'}:
        raise ServiceError('This video is restricted or requires authentication.')
    return info


def metadata(url: str) -> dict:
    info = extract(url)
    canonical, short = normalize_url(url)
    return {'id': info['id'], 'title': info.get('title', 'Untitled video'),
            'channel': info.get('channel') or info.get('uploader', 'Unknown channel'),
            'thumbnail': f'https://i.ytimg.com/vi/{info["id"]}/hqdefault.jpg',
            'duration': info['duration'], 'durationFormatted': format_time(info['duration']),
            'webpageUrl': canonical, 'isShort': short}


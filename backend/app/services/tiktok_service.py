"""Standalone public TikTok downloader; no YouTube options or job state."""
import logging
import re
from pathlib import Path
from urllib.parse import urlsplit, urljoin

import httpx
from yt_dlp import YoutubeDL
from app.services.video_service import ServiceError

logger = logging.getLogger(__name__)
ERROR = 'TikTok could not provide this video. It may be private, unavailable, or temporarily blocked. Try another public video.'
HOSTS = {'tiktok.com', 'www.tiktok.com', 'm.tiktok.com', 'vm.tiktok.com', 'vt.tiktok.com'}


def normalize(value: str) -> str:
    try:
        parsed = urlsplit(value.strip())
        if parsed.scheme not in {'http', 'https'} or parsed.hostname not in HOSTS or parsed.username or parsed.password or parsed.port not in (None, 80, 443):
            raise ValueError()
        if parsed.hostname in {'vm.tiktok.com', 'vt.tiktok.com'}:
            if re.fullmatch(r'/[A-Za-z0-9]+/?', parsed.path):
                return f'https://{parsed.hostname}{parsed.path}'
        elif re.fullmatch(r'/@[^/\s%]+/video/\d+/?', parsed.path):
            return f'https://www.tiktok.com{parsed.path.rstrip("/")}'
        elif re.fullmatch(r'/t/[A-Za-z0-9]+/?', parsed.path):
            return f'https://www.tiktok.com{parsed.path}'
    except (ValueError, TypeError, AttributeError):
        pass
    raise ValueError('Paste a public TikTok video URL or TikTok share link.')


def resolve(value: str) -> str:
    url = normalize(value)
    # Resolve short links ourselves: never follow an arbitrary redirect target.
    with httpx.Client(follow_redirects=False, timeout=20, trust_env=False) as client:
        for _ in range(5):
            if '/video/' in url:
                return url
            response = client.head(url, headers={'User-Agent': 'facebookexternalhit/1.1'})
            if response.status_code not in {301, 302, 303, 307, 308} or not response.headers.get('location'):
                break
            url = normalize(urljoin(url, response.headers['location']))
    raise ServiceError('Could not resolve this TikTok share link. Paste the full video URL instead.')


def options(directory: Path | None = None) -> dict:
    result = {'quiet': True, 'logger': logger, 'noplaylist': True, 'ignoreconfig': True,
              'cachedir': False, 'geo_bypass': False, 'socket_timeout': 25, 'retries': 2,
              'extractor_retries': 2, 'allowed_extractors': ['TikTok'],
              'format': 'bv*+ba/b', 'format_sort': ['res', 'fps', 'br', 'size'],
              'format_sort_force': True, 'merge_output_format': 'mp4/mkv'}
    if directory:
        result['outtmpl'] = str(directory / 'tiktok.%(ext)s')
    return result


def extract(url: str, directory: Path | None = None) -> dict:
    try:
        canonical = resolve(url)
        with YoutubeDL(options(directory)) as ydl:
            info = ydl.extract_info(canonical, download=False)
            if not info or info.get('_type', 'video') != 'video' or info.get('is_live') or info.get('availability') in {'private', 'premium_only', 'subscriber_only', 'needs_auth'} or not info.get('formats'):
                raise ServiceError(ERROR)
            if directory:
                ydl.process_info(info)
        info['webpage_url'] = canonical
        return info
    except ServiceError:
        raise
    except Exception as exc:
        logger.exception('TikTok extraction/download failed')
        raise ServiceError(ERROR) from exc


def metadata(url: str) -> dict:
    info = extract(url)
    thumbnail = info.get('thumbnail')
    if thumbnail and urlsplit(thumbnail).scheme != 'https':
        thumbnail = None
    return {'url': info['webpage_url'], 'title': info.get('title') or 'TikTok video',
            'creator': info.get('uploader') or info.get('creator') or 'TikTok creator',
            'thumbnail': thumbnail, 'duration': info.get('duration')}


def download(url: str, directory: Path) -> Path:
    extract(url, directory)
    files = [path for path in directory.glob('tiktok.*') if path.suffix in {'.mp4', '.webm', '.mkv', '.mov'}]
    if len(files) != 1:
        raise ServiceError('TikTok did not return a downloadable video. Try again later.')
    return files[0]

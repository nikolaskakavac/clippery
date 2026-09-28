from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from app.utils.validation import normalize_url
from app.utils.time import format_time

class ServiceError(Exception):
    pass

def options() -> dict:
    return {'quiet': True, 'no_warnings': True, 'noplaylist': True,
            'socket_timeout': 25, 'retries': 2, 'extractor_retries': 2,
            'js_runtimes': {'node': {}}, 'geo_bypass': False, 'cachedir': False, 'ignoreconfig': True}

def extract(url: str) -> dict:
    canonical, _ = normalize_url(url)
    try:
        with YoutubeDL(options()) as ydl:
            info = ydl.extract_info(canonical, download=False)
        if not info or info.get('is_live') or not info.get('duration'):
            raise ServiceError('Live streams and videos without a known duration are not supported.')
        if info.get('availability') in {'private', 'premium_only', 'subscriber_only', 'needs_auth'}:
            raise ServiceError('This video is restricted or requires authentication.')
        return info
    except DownloadError:
        raise ServiceError('YouTube could not provide this video. It may be unavailable, restricted, or temporarily blocked. Try again later or use another public video.') from None

def metadata(url: str) -> dict:
    info = extract(url)
    canonical, short = normalize_url(url)
    return {'id': info['id'], 'title': info.get('title', 'Untitled video'),
            'channel': info.get('channel') or info.get('uploader', 'Unknown channel'),
            'thumbnail': f'https://i.ytimg.com/vi/{info["id"]}/hqdefault.jpg',
            'duration': info['duration'], 'durationFormatted': format_time(info['duration']),
            'webpageUrl': canonical, 'isShort': short}


import re
from urllib.parse import urlsplit, parse_qs

HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'www.youtu.be'}

def normalize_url(value: str) -> tuple[str, bool]:
    try:
        parsed = urlsplit(value.strip())
        if parsed.scheme not in {'http', 'https'} or parsed.hostname not in HOSTS:
            raise ValueError('Enter a supported YouTube URL.')
        if parsed.username or parsed.password or parsed.port not in (None, 80, 443):
            raise ValueError('Invalid YouTube URL.')
        query = parse_qs(parsed.query, keep_blank_values=True)
        if 'list' in query:
            raise ValueError('Playlists are not supported. Use a single video link without a list parameter.')
        short = parsed.path.startswith('/shorts/')
        if parsed.hostname in {'youtu.be', 'www.youtu.be'}:
            video_id = parsed.path.removeprefix('/')
        elif short:
            video_id = parsed.path.removeprefix('/shorts/').removesuffix('/')
        elif parsed.path == '/watch':
            video_id = query.get('v', [''])[0]
        else:
            raise ValueError('Use a YouTube watch, Shorts, or youtu.be link.')
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
            raise ValueError('The YouTube video ID is invalid.')
        return f'https://www.youtube.com/watch?v={video_id}', short
    except (TypeError, AttributeError):
        raise ValueError('Enter a valid YouTube URL.') from None


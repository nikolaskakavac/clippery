"""Classify upstream failures without echoing credentials, responses or URLs."""


def category(error):
    text = str(error).lower()
    if any(s in text for s in ('429', 'too many requests', 'rate limit', "this content isn't available, try again later")):
        return 'rate_limit'
    if 'cookie' in text and any(s in text for s in ('expired', 'invalid', 'rotated', 'no longer valid')):
        return 'cookies_rejected'
    if 'not a bot' in text:
        return 'bot_detection'
    if any(s in text for s in ('login_required', 'sign in', 'log in', 'authentication required', 'age-restricted')):
        return 'authentication'
    if any(s in text for s in ('javascript', 'js runtime', 'challenge solving', 'n challenge', 'signature extraction')):
        return 'javascript'
    if any(s in text for s in ('403', 'forbidden', 'ip blocked', 'ip address is blocked')):
        return 'access_denied'
    if any(s in text for s in ('timed out', 'timeout', 'connection reset', 'connection refused', 'network is unreachable', 'temporary failure', '502', '503', '504', 'unable to download api page')):
        return 'network'
    if any(s in text for s in ('ffmpeg', 'ffprobe', 'postprocessing')):
        return 'ffmpeg'
    if any(s in text for s in ('private video', 'video unavailable', 'not available', 'members-only', 'not supported', 'unsupported url')):
        return 'unavailable'
    if 'update yt-dlp' in text or 'outdated' in text:
        return 'outdated_version'
    return 'extraction'


def public_error(kind, authenticated=False):
    if kind in {'authentication', 'bot_detection', 'cookies_rejected'}:
        if authenticated:
            return 'YouTube rejected the configured session. Cookies may be expired or the server may be challenged. Replace cookies; updating yt-dlp or cookies alone may not resolve server IP blocking.'
        return 'YouTube requires authentication or a bot check. No YouTube cookies are configured. Public videos may still be blocked from this server.'
    return {
        'rate_limit': 'YouTube is rate limiting requests. Wait before trying again.',
        'network': 'YouTube could not be reached after a limited retry. Please try again later.',
        'javascript': 'YouTube JavaScript challenge failed. Check the server JavaScript runtime and yt-dlp support.',
        'access_denied': 'YouTube denied this request (403). Server IP blocking is possible; updating yt-dlp or cookies alone may not resolve it.',
        'ffmpeg': 'Video processing failed. Check the server FFmpeg installation or try another source.',
        'unavailable': 'This video is unavailable, private, or restricted.',
        'outdated_version': 'YouTube extraction requires a newer compatible yt-dlp version. Contact the service operator.',
        'extraction': 'YouTube extraction failed. Check the installed yt-dlp version and try again later.',
    }.get(kind, 'YouTube extraction failed.')

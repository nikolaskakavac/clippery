"""Operator-supplied YouTube credentials; never shared with the frontend or TikTok."""
import base64
import binascii
import io
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from yt_dlp.cookies import YoutubeDLCookieJar


class CookieConfigurationError(ValueError):
    pass


MAX_COOKIE_BYTES = 1024 * 1024


def cookies_configured():
    return bool(os.getenv('YOUTUBE_COOKIES_BASE64') or os.getenv('YOUTUBE_COOKIES_FILE'))


def validated_cookies():
    encoded = os.getenv('YOUTUBE_COOKIES_BASE64')
    local = os.getenv('YOUTUBE_COOKIES_FILE')
    if encoded:
        try:
            if len(encoded) > MAX_COOKIE_BYTES * 2:
                raise ValueError()
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise CookieConfigurationError('YouTube cookies configuration has invalid Base64.') from None
    elif local:
        if os.getenv('RENDER', '').lower() == 'true' or os.getenv('RENDER_SERVICE_ID'):
            raise CookieConfigurationError('Use YOUTUBE_COOKIES_BASE64 on Render; local cookie files are disabled there.')
        try:
            with Path(local).open('rb') as handle:
                raw = handle.read(MAX_COOKIE_BYTES + 1)
        except (OSError, ValueError):
            raise CookieConfigurationError('The configured local YouTube cookie file is missing or unreadable.') from None
    else:
        return None
    try:
        if len(raw) > MAX_COOKIE_BYTES:
            raise ValueError()
        text = raw.decode('utf-8-sig').replace('\r\n', '\n')
        if '\x00' in text or text.splitlines()[0] not in {'# Netscape HTTP Cookie File', '# HTTP Cookie File'}:
            raise ValueError()
        rows = []
        for line in text.splitlines()[1:]:
            if not line.strip() or (line.startswith('#') and not line.startswith('#HttpOnly_')):
                continue
            fields = line.removeprefix('#HttpOnly_').split('\t')
            if len(fields) != 7:
                raise ValueError()
            domain, subdomains, path, secure, expiry, name, value = fields
            if subdomains not in {'TRUE', 'FALSE'} or secure not in {'TRUE', 'FALSE'} or not path.startswith('/') or not name:
                raise ValueError()
            if (subdomains == 'TRUE') != domain.startswith('.'):
                raise ValueError()
            if expiry and (not expiry.isdigit() or int(expiry) < 0):
                raise ValueError()
            host = domain.lstrip('.').lower()
            if host == 'youtube.com' or host.endswith('.youtube.com'):
                rows.append(line)
        # Never copy unrelated browser credentials (e.g. email or banking) into yt-dlp.
        filtered = '# Netscape HTTP Cookie File\n' + '\n'.join(rows) + '\n'
        jar = YoutubeDLCookieJar()
        jar.load(io.StringIO(filtered), ignore_discard=True, ignore_expires=True)
        if not rows or not list(jar):
            raise ValueError()
        if not any(cookie.expires is None or cookie.expires == 0 or cookie.expires > time.time() for cookie in jar):
            raise CookieConfigurationError('Configured YouTube cookies have expired. Replace the cookie export.')
        return filtered
    except CookieConfigurationError:
        raise
    except Exception:
        # Cookie parser exceptions can embed complete cookie lines; do not chain them.
        raise CookieConfigurationError('Invalid YouTube cookies. Supply a Netscape-format export containing youtube.com cookies.') from None


@contextmanager
def cookie_file():
    text = validated_cookies()
    if text is None:
        yield None
        return
    # Unique directory per operation avoids concurrent mutation by yt-dlp.save_cookies.
    # TemporaryDirectory and mkstemp are private on POSIX; Windows uses the user's temp ACL.
    with tempfile.TemporaryDirectory(prefix='clippery-auth-') as directory:
        fd, name = tempfile.mkstemp(prefix='youtube-', suffix='.txt', dir=directory)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
                os.chmod(name, 0o600)
                handle.write(text)
            yield name
        finally:
            Path(name).unlink(missing_ok=True)

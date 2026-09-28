import math
import pytest
from app.utils.validation import normalize_url, HOSTS
from app.utils.time import parse_timestamp, format_time, validate_clip

ID = 'dQw4w9WgXcQ'
@pytest.mark.parametrize('url,short', [
    (f'https://www.youtube.com/watch?v={ID}', False),
    (f'https://m.youtube.com/watch?v={ID}&t=20', False),
    (f'https://youtu.be/{ID}?si=abc', False),
    (f'https://www.youtube.com/shorts/{ID}', True),
    (f'https://youtube.com/shorts/{ID}/', True),
])
def test_supported_urls(url, short):
    assert normalize_url(url) == (f'https://www.youtube.com/watch?v={ID}', short)

@pytest.mark.parametrize('url', [
    'https://example.com', 'http://127.0.0.1', 'file:///etc/passwd',
    f'https://youtube.com.evil.org/watch?v={ID}', f'https://youtube.com@evil.org/watch?v={ID}',
    f'https://evil@youtube.com/watch?v={ID}', f'https://youtube.com:999/watch?v={ID}',
    f'https://www.youtube.com/watch?v={ID}&list=abc', 'https://youtube.com/playlist?list=abc',
    'https://youtu.be/../../etc/passwd', 'https://youtube.com/watch?v=bad',
    f'https://youtube.com/watch?v={ID}%0a', f'ftp://youtube.com/watch?v={ID}',
    'https://youtube.com/redirect?q=http://localhost', 'not a url',
])
def test_reject_unsafe_urls(url):
    with pytest.raises(ValueError): normalize_url(url)

@pytest.mark.parametrize('host', sorted(HOSTS))
def test_hosts(host):
    path = f'/{ID}' if 'youtu.be' in host else f'/watch?v={ID}'
    assert normalize_url('https://' + host + path)[0].endswith(ID)

@pytest.mark.parametrize('value,seconds', [('00:00:00', 0), ('01:14:22', 4462), ('00:00:01.250', 1.25), ('100:00:00', 360000)])
def test_timestamps(value, seconds): assert parse_timestamp(value) == seconds

@pytest.mark.parametrize('value', ['-01:00:00', '1:02', '00:60:00', '00:00:60', 'NaN', '00:01:00;rm'])
def test_bad_timestamps(value):
    with pytest.raises(ValueError): parse_timestamp(value)

def test_format_time(): assert format_time(4462.7) == '01:14:22'

@pytest.mark.parametrize('start,end,duration', [(0,300,10800), (100,101,101), (1.25,3.5,10)])
def test_clip_boundaries(start,end,duration): validate_clip(start,end,duration)

@pytest.mark.parametrize('start,end,duration', [(-1,10,100), (10,10,100), (20,10,100), (0,301,1000), (0,10,10801), (0,101,100), (math.nan,10,100), (0,math.inf,100)])
def test_invalid_clips(start,end,duration):
    with pytest.raises(ValueError): validate_clip(start,end,duration)

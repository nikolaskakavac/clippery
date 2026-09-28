import math
import re

def parse_timestamp(value: str) -> float:
    if not re.fullmatch(r'\d{2,}:\d{2}:\d{2}(?:\.\d{1,3})?', value):
        raise ValueError('Use HH:MM:SS timestamps.')
    hours, minutes, seconds = map(float, value.split(':'))
    if minutes >= 60 or seconds >= 60:
        raise ValueError('Minutes and seconds must be below 60.')
    return hours * 3600 + minutes * 60 + seconds

def format_time(value: float) -> str:
    seconds = max(0, int(value))
    return f'{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}'

def validate_clip(start: float, end: float, duration: float) -> None:
    from app.config import MAX_CLIP_SECONDS, MAX_SOURCE_SECONDS
    if not all(math.isfinite(v) for v in (start, end, duration)):
        raise ValueError('Timestamps must be finite.')
    if duration > MAX_SOURCE_SECONDS:
        raise ValueError('Clip sources must be at most 3 hours.')
    if start < 0 or end <= start or end > duration:
        raise ValueError('Clip must start at or after zero and end after start, within the video.')
    if end - start > MAX_CLIP_SECONDS:
        raise ValueError('Clips can be at most 5 minutes.')

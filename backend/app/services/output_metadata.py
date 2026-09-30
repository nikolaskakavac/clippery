from fractions import Fraction
from pathlib import Path

from app.services.download_service import probe


def output_metadata(path: Path) -> dict:
    data = probe(path)
    video = next((stream for stream in data.get('streams', []) if stream.get('codec_type') == 'video'), {})
    fps = None
    try:
        rate = Fraction(str(video.get('avg_frame_rate', '0/0')))
        if rate > 0:
            fps = round(float(rate), 3)
    except (ValueError, ZeroDivisionError, OverflowError):
        pass
    return {'width': video.get('width'), 'height': video.get('height'),
            'fps': fps, 'codec': video.get('codec_name'), 'sizeBytes': path.stat().st_size}

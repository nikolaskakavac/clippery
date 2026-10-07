"""Conservative silence removal on an already bounded clip, never the full source."""
import logging
import math
import re
import subprocess
from fractions import Fraction
from pathlib import Path

from app.services.download_service import probe, log_media
from app.services.video_service import ServiceError

logger = logging.getLogger(__name__)


def kept_segments(log: str, duration: float, fps: float) -> list[dict]:
    intervals = []
    start = None
    for kind, value in re.findall(r'silence_(start|end):\s*(-?\d+(?:\.\d+)?)', log):
        if kind == 'start':
            start = max(0, float(value))
        elif start is not None:
            intervals.append((start, min(duration, float(value))))
            start = None
    if start is not None:
        intervals.append((start, duration))
    kept, cursor = [], 0.0
    for start, end in intervals:
        # Keep 150ms of room around speech and round cuts away from it.
        cut_start = min(duration, math.ceil((start + .15) * fps) / fps)
        cut_end = max(0, math.floor((end - .15) * fps) / fps)
        if end - start < .6 or cut_end <= cut_start or cut_start < cursor:
            continue
        if cut_start > cursor:
            kept.append({'start': cursor, 'end': cut_start})
        cursor = cut_end
    if cursor < duration:
        kept.append({'start': cursor, 'end': duration})
    return kept


def remove_silence(source: Path, update) -> tuple[Path, dict]:
    update('Merging', 95)
    data = probe(source)
    video = next(s for s in data['streams'] if s['codec_type'] == 'video')
    duration = float(video.get('duration') or data['format']['duration'])
    if not math.isfinite(duration) or duration <= 0 or duration > 300.2:
        raise ServiceError('Silence removal is limited to clips of at most 5 minutes.')
    rate = video.get('avg_frame_rate') or video.get('r_frame_rate')
    try:
        fps = float(Fraction(rate))
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError()
    except (ValueError, TypeError, ZeroDivisionError):
        raise ServiceError('Could not determine the clip frame rate for silence removal.') from None
    whole = [{'start': 0, 'end': duration}]
    details = {'beforeDuration': duration, 'afterDuration': duration, 'segments': whole,
               'message': 'No long silences found. Original clip kept.'}
    if not any(s['codec_type'] == 'audio' for s in data['streams']):
        details['message'] = 'No audio track. Original clip kept.'
        return source, details
    try:
        detection = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-i', str(source),
            '-map', '0:a:0', '-af', 'silencedetect=noise=-35dB:d=0.6', '-f', 'null', '-'],
            capture_output=True, text=True, timeout=120, check=True)
        segments = kept_segments(detection.stderr, duration, fps)
        kept = sum(segment['end'] - segment['start'] for segment in segments)
        if len(segments) > 80:
            details['message'] = 'Too many cuts for a safe export. Original clip kept.'
            return source, details
        if kept < .5:
            details['message'] = 'Almost entirely silent. Original clip kept.'
            return source, details
        if duration - kept < .1:
            return source, details
        # Audio/video use identical frame-aligned intervals; one final lossy pass.
        count = len(segments)
        filters = [f'[0:v:0]split={count}' + ''.join(f'[vs{i}]' for i in range(count)),
                   f'[0:a:0]asplit={count}' + ''.join(f'[as{i}]' for i in range(count))]
        for i, segment in enumerate(segments):
            start, end = segment['start'], segment['end']
            filters += [f'[vs{i}]trim=start={start:.9f}:end={end:.9f},setpts=PTS-STARTPTS[v{i}]',
                        f'[as{i}]atrim=start={start:.9f}:end={end:.9f},asetpts=PTS-STARTPTS[a{i}]']
        filters.append(''.join(f'[v{i}][a{i}]' for i in range(count)) + f'concat=n={count}:v=1:a=1[v][a]')
        output = source.parent / 'clipper-silence.mp4'
        subprocess.run(['ffmpeg', '-nostdin', '-y', '-i', str(source), '-filter_complex', ';'.join(filters),
            '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-crf', '16', '-preset', 'medium',
            '-pix_fmt', 'yuv420p', '-r', str(Fraction(rate)), '-fps_mode', 'cfr',
            '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(output)],
            capture_output=True, text=True, timeout=3600, check=True)
        final = probe(output)
        after = float(final['format']['duration'])
        if abs(after - kept) > max(.15, 2 / fps):
            raise ServiceError('Silence removal produced an unexpected duration. Export without removing silence and try again.')
        log_media('silence output', output, final)
        details.update(afterDuration=after, segments=segments, message='Long silences removed. Review the exported preview.')
        return output, details
    except subprocess.SubprocessError as exc:
        logger.error('Silence processing failed: %s; %s', exc, getattr(exc, 'stderr', ''))
        raise ServiceError('Silence removal failed. Try exporting with Remove silence turned off.') from None

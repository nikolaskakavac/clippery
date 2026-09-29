import json
import subprocess
import shutil
import logging
import copy
from pathlib import Path
from yt_dlp import YoutubeDL
from yt_dlp.utils import download_range_func
from app.config import MAX_RESOLUTION
from app.services.video_service import options, ServiceError, BGUTIL_SERVER_HOME

logger = logging.getLogger('uvicorn.error')


class ExtractionLog:
    def __init__(self):
        self.incomplete = False

    def debug(self, message):
        logger.debug(message)

    def warning(self, message):
        if ('missing a URL' in message or 'PO Token which was not provided' in message):
            self.incomplete = True
        logger.warning(message)

    def error(self, message):
        logger.error(message)


def resolve_source(ydl, url, audit):
    for _ in range(3):
        audit.incomplete = False
        info = ydl.extract_info(url, download=False)
        # A genuine progressive-only source is supported. A progressive fallback
        # after YouTube withheld adaptive URLs must not masquerade as Highest.
        if not audit.incomplete or info.get('requested_formats'):
            return info
        logger.warning('Retrying incomplete YouTube format extraction before downloading')
    raise ServiceError('YouTube did not provide the high-quality source streams. Please retry later.')


def check_source_provider():
    """Do not silently export a low-resolution fallback after a broken installation."""
    try:
        result = subprocess.run(['node', str(BGUTIL_SERVER_HOME / 'build' / 'generate_once.js'), '--version'],
                                capture_output=True, text=True, timeout=20, check=True)
        if result.stdout.strip() != '2.0.0':
            raise ValueError('Unexpected bgutil generator version')
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        logger.error('YouTube quality provider check failed: %s %s', exc, getattr(exc, 'stderr', ''))
        raise ServiceError('YouTube quality provider is unavailable. Repair the backend provider installation before exporting.') from None


def log_media(stage, path, data):
    fields = ('codec_type', 'codec_name', 'width', 'height', 'avg_frame_rate', 'r_frame_rate', 'bit_rate', 'pix_fmt')
    logger.info('Media quality %s: %s', stage, json.dumps({
        'file': path.name, 'size': data.get('format', {}).get('size'), 'duration': data.get('format', {}).get('duration'),
        'bit_rate': data.get('format', {}).get('bit_rate'),
        'streams': [{key: stream.get(key) for key in fields} for stream in data['streams']]}))

def clip_video_args(highest):
    # Used for accurate cuts and codec conversion, without scaling or frame-rate conversion.
    return ['-preset', 'medium', '-crf', '16' if highest else '18', '-pix_fmt', 'yuv420p']

def format_selector(quality: str) -> str:
    height = min(int(quality) if quality != 'best' else MAX_RESOLUTION, MAX_RESOLUTION)
    return f'bv[height<={height}]+ba/b[height<={height}]'

def probe(path: Path) -> dict:
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
                            capture_output=True, text=True, timeout=30, check=True)
    return json.loads(result.stdout)

def editor_mp4(source: Path, output: Path, update, *, clip=False, highest=False) -> None:
    update('Merging', 95)
    source_data = probe(source)
    log_media('temporary source', source, source_data)
    streams = source_data['streams']
    video = next((s for s in streams if s['codec_type'] == 'video'), {})
    audio = next((s for s in streams if s['codec_type'] == 'audio'), {})
    copy_video = video.get('codec_name') == 'h264' and video.get('pix_fmt') == 'yuv420p'
    args = ['ffmpeg', '-nostdin', '-y', '-i', str(source), '-map', '0:v:0', '-map', '0:a:0?',
            '-c:v', 'copy' if copy_video else 'libx264']
    if not copy_video:
        args += clip_video_args(highest) if clip else ['-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p']
        if clip:
            args += ['-fps_mode', 'passthrough']
    copy_audio = audio.get('codec_name') == 'aac'
    args += ['-c:a', 'copy' if copy_audio else 'aac']
    if clip and not copy_audio:
        args += ['-b:a', '192k']
    args += ['-movflags', '+faststart', '-avoid_negative_ts', 'make_zero', str(output)]
    subprocess.run(args, capture_output=True, timeout=3600, check=True)
    log_media('final output', output, probe(output))

def usable_section(path: Path, duration: float) -> bool:
    data = probe(path)
    video = next((s for s in data['streams'] if s['codec_type'] == 'video'), {})
    if not video or abs(float(data['format']['duration']) - duration) > 0.15:
        return False
    # Check the beginning, where stream-copy cuts can lack decodable reference frames.
    result = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-t', '1',
                             '-f', 'null', '-'], capture_output=True, timeout=30)
    return result.returncode == 0

def process(url: str, quality: str, directory: Path, update, section=None) -> Path:
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise ServiceError('FFmpeg and ffprobe must be installed on the backend before processing video.')
    check_source_provider()
    seen_formats = set()
    def progress(data):
        info = data.get('info_dict', {})
        key = (attempt, info.get('format_id'))
        if info and key not in seen_formats:
            seen_formats.add(key)
            fields = ('format_id', 'vcodec', 'acodec', 'width', 'height', 'fps', 'tbr', 'vbr', 'abr', 'filesize', 'filesize_approx')
            logger.info('YouTube selected formats: %s', json.dumps({'quality': quality, 'section': section,
                'attempt': attempt, 'streams': [{k: f.get(k) for k in fields} for f in info.get('requested_formats', [info])]}))
        if data['status'] == 'downloading':
            total = data.get('total_bytes') or data.get('total_bytes_estimate')
            update('Downloading', min(90, data.get('downloaded_bytes', 0) / total * 90) if total else None)
        elif data['status'] == 'finished':
            update('Merging', 92)
    opts = {**options(), 'format': format_selector(quality),
            'format_sort': ['res', 'vcodec:h264', 'acodec:aac'],
            'outtmpl': str(directory / 'source.%(ext)s'), 'merge_output_format': 'mp4',
            'progress_hooks': [progress]}
    audit = ExtractionLog()
    opts['logger'] = audit
    source_info = None
    if section:
        opts.update({'download_ranges': download_range_func(None, [section]),
                     'force_keyframes_at_cuts': False})
    for attempt in range(2 if section else 1):
        if attempt:
            # Retry only the bounded section, never the full source. Precise cuts need
            # re-encoding when the requested start is not a usable keyframe boundary.
            opts['force_keyframes_at_cuts'] = True
            opts['external_downloader_args'] = {'ffmpeg_o': [
                '-c:v', 'libx264', *clip_video_args(quality == 'best'),
                '-fps_mode', 'passthrough', '-c:a', 'aac', '-b:a', '192k']}
        with YoutubeDL(opts) as ydl:
            if source_info is None:
                source_info = resolve_source(ydl, url, audit)
                fields = ('format_id', 'vcodec', 'acodec', 'width', 'height', 'fps', 'tbr', 'filesize', 'filesize_approx')
                logger.info('Resolved YouTube source: %s', json.dumps({'quality': quality, 'section': section,
                    'streams': [{k: f.get(k) for k in fields} for f in source_info.get('requested_formats', [source_info])]}))
            # Reuse the resolved source for accurate-cut retries; don't ask YouTube
            # for a new session which may expose a different, lower-quality set.
            ydl.process_ie_result(copy.deepcopy(source_info), download=True)
        sources = [p for p in directory.glob('source.*') if p.suffix in {'.mp4', '.mkv', '.webm'}]
        if len(sources) != 1:
            raise ServiceError('Video processing did not produce a usable file.')
        output = directory / 'clipper.mp4'
        editor_mp4(sources[0], output, update, clip=section is not None, highest=quality == 'best')
        sources[0].unlink(missing_ok=True)
        if not section or usable_section(output, section[1] - section[0]):
            return output
        output.unlink(missing_ok=True)
    raise ServiceError('The source could not produce an accurate, playable clip. Try slightly different timestamps.')


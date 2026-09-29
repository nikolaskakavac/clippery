import json
import subprocess
import shutil
from pathlib import Path
from yt_dlp import YoutubeDL
from yt_dlp.utils import download_range_func
from app.config import MAX_RESOLUTION
from app.services.video_service import options, ServiceError

# Used for accurate section cuts and any clip codec conversion. Never scale up.
CLIP_VIDEO_ARGS = ['-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p']

def format_selector(quality: str) -> str:
    height = min(int(quality) if quality != 'best' else MAX_RESOLUTION, MAX_RESOLUTION)
    return f'bv[height<={height}]+ba/b[height<={height}]'

def probe(path: Path) -> dict:
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
                            capture_output=True, text=True, timeout=30, check=True)
    return json.loads(result.stdout)

def editor_mp4(source: Path, output: Path, update, *, clip=False) -> None:
    update('Merging', 95)
    streams = probe(source)['streams']
    video = next((s for s in streams if s['codec_type'] == 'video'), {})
    audio = next((s for s in streams if s['codec_type'] == 'audio'), {})
    copy_video = video.get('codec_name') == 'h264' and video.get('pix_fmt') == 'yuv420p'
    args = ['ffmpeg', '-nostdin', '-y', '-i', str(source), '-map', '0:v:0', '-map', '0:a:0?',
            '-c:v', 'copy' if copy_video else 'libx264']
    if not copy_video:
        args += CLIP_VIDEO_ARGS if clip else ['-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p']
    copy_audio = audio.get('codec_name') == 'aac'
    args += ['-c:a', 'copy' if copy_audio else 'aac']
    if clip and not copy_audio:
        args += ['-b:a', '192k']
    args += ['-movflags', '+faststart', '-avoid_negative_ts', 'make_zero', str(output)]
    subprocess.run(args, capture_output=True, timeout=3600, check=True)

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
    def progress(data):
        if data['status'] == 'downloading':
            total = data.get('total_bytes') or data.get('total_bytes_estimate')
            update('Downloading', min(90, data.get('downloaded_bytes', 0) / total * 90) if total else None)
        elif data['status'] == 'finished':
            update('Merging', 92)
    opts = {**options(), 'format': format_selector(quality),
            'format_sort': ['res', 'vcodec:h264', 'acodec:aac'],
            'outtmpl': str(directory / 'source.%(ext)s'), 'merge_output_format': 'mp4',
            'progress_hooks': [progress]}
    if section:
        opts.update({'download_ranges': download_range_func(None, [section]),
                     'force_keyframes_at_cuts': False})
    for attempt in range(2 if section else 1):
        if attempt:
            # Retry only the bounded section, never the full source. Precise cuts need
            # re-encoding when the requested start is not a usable keyframe boundary.
            opts['force_keyframes_at_cuts'] = True
            opts['external_downloader_args'] = {'ffmpeg_o': [
                '-c:v', 'libx264', *CLIP_VIDEO_ARGS, '-c:a', 'aac', '-b:a', '192k']}
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
        sources = [p for p in directory.glob('source.*') if p.suffix in {'.mp4', '.mkv', '.webm'}]
        if len(sources) != 1:
            raise ServiceError('Video processing did not produce a usable file.')
        output = directory / 'clipper.mp4'
        editor_mp4(sources[0], output, update, clip=section is not None)
        sources[0].unlink(missing_ok=True)
        if not section or usable_section(output, section[1] - section[0]):
            return output
        output.unlink(missing_ok=True)
    raise ServiceError('The source could not produce an accurate, playable clip. Try slightly different timestamps.')


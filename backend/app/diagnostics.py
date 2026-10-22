"""Run from backend: python -m app.diagnostics [--url URL] [--download]."""
import argparse
import json
import platform
import re
import shutil
import subprocess
import tempfile
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

from app.services.youtube_auth import cookies_configured, cookie_file, CookieConfigurationError


def package_version(name):
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def tool_version(name):
    if not shutil.which(name):
        return None
    try:
        result = subprocess.run([name, '--version' if name == 'node' else '-version'],
                                capture_output=True, text=True, timeout=10, check=True)
        match = re.search(r'\d+\.\d+(?:\.\d+)?', result.stdout.splitlines()[0])
        return match.group(0) if match else 'available'
    except (OSError, subprocess.SubprocessError, IndexError):
        return None


def runtime_report(check_cookies=True):
    node = tool_version('node')
    report = {'python': platform.python_version(), 'yt_dlp': package_version('yt-dlp'),
              'yt_dlp_ejs': package_version('yt-dlp-ejs'),
              'bgutil_plugin': package_version('bgutil-ytdlp-pot-provider'),
              'node': node, 'node_supported': bool(node and node.split('.')[0].isdigit() and int(node.split('.')[0]) >= 22),
              'ffmpeg': tool_version('ffmpeg'), 'ffprobe': tool_version('ffprobe'),
              'cookies_configured': cookies_configured(), 'cookies_parseable': None}
    if check_cookies and report['cookies_configured']:
        try:
            with cookie_file() as path:
                report['cookies_parseable'] = path is not None
        except (CookieConfigurationError, OSError):
            report['cookies_parseable'] = False
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', help='Public YouTube video to test; no network test unless supplied')
    parser.add_argument('--download', action='store_true', help='Also process a temporary 5-second 1080p-max clip')
    parser.add_argument('--check-runtime', action='store_true', help='Exit nonzero for missing runtime requirements')
    parser.add_argument('--skip-cookies', action='store_true', help='Build-time runtime check only')
    args = parser.parse_args()
    if args.download and not args.url:
        parser.error('--download requires --url')
    report = runtime_report(not args.skip_cookies)
    print(json.dumps(report), flush=True)
    if args.check_runtime and not all(report[k] for k in ('yt_dlp', 'yt_dlp_ejs', 'bgutil_plugin', 'node_supported', 'ffmpeg', 'ffprobe')):
        return 1
    if report['cookies_parseable'] is False:
        print('Configured cookies could not be validated; replace the export.', flush=True)
        return 1
    if args.url:
        from app.services.video_service import metadata, ServiceError
        from app.services.download_service import process
        try:
            info = metadata(args.url)
            print(json.dumps({'metadata_ok': True, 'duration': info['duration']}), flush=True)
            if args.download:
                with tempfile.TemporaryDirectory(prefix='clippery-diagnostic-') as directory:
                    output = process(info['webpageUrl'], '1080', Path(directory), lambda *_: None,
                                     section=(0, min(5, info['duration'])))
                    print(json.dumps({'download_ok': output.is_file(), 'bytes': output.stat().st_size}), flush=True)
        except (ServiceError, ValueError):
            print('YouTube test failed. See sanitized category in server logs.', flush=True)
            return 1
        except Exception:
            print('Diagnostic processing failed; no raw response or command printed.', flush=True)
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

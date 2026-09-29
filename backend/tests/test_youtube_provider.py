import logging

import pytest
from yt_dlp.utils import DownloadError

from app.services import video_service


def test_shared_provider_configuration():
    opts = video_service.options()
    assert opts['extractor_args']['youtube']['player_client'] == ['mweb']
    home = video_service.BGUTIL_SERVER_HOME
    assert home.is_absolute()
    assert opts['extractor_args']['youtubepot-bgutilscript']['server_home'] == [str(home)]
    assert opts['js_runtimes'] == {'node': {}}
    assert opts['no_warnings'] is False
    assert opts['logger'] is video_service.logger


def test_extraction_logs_underlying_error_without_exposing_it(monkeypatch, caplog):
    underlying = "LOGIN_REQUIRED: Sign in to confirm you're not a bot"

    class FailingDownloader:
        def __init__(self, options):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def extract_info(self, *args, **kwargs):
            raise DownloadError(underlying)

    monkeypatch.setattr(video_service, 'YoutubeDL', FailingDownloader)
    with caplog.at_level(logging.ERROR), pytest.raises(video_service.ServiceError) as error:
        video_service.extract('https://youtu.be/dQw4w9WgXcQ')
    assert underlying in caplog.text
    assert underlying not in str(error.value)
    assert str(error.value).startswith('YouTube could not provide this video.')

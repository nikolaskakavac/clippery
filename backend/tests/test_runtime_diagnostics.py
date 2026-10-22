import json

from app import diagnostics
from app.services.video_service import DiagnosticLog


def test_runtime_report_only_cookie_booleans(monkeypatch):
    monkeypatch.setenv('YOUTUBE_COOKIES_BASE64', 'private-invalid-export')
    monkeypatch.setattr(diagnostics, 'tool_version', lambda name: '24.14.0' if name == 'node' else '7.0')
    report = diagnostics.runtime_report()
    assert report['cookies_configured'] is True
    assert report['cookies_parseable'] is False
    assert report['node_supported'] is True
    assert 'private-invalid-export' not in json.dumps(report)


def test_unknown_or_old_node_does_not_pass_runtime_check(monkeypatch):
    monkeypatch.setattr(diagnostics, 'tool_version', lambda _: '20.0.0')
    assert diagnostics.runtime_report(False)['node_supported'] is False


def test_credential_payloads_never_logged(monkeypatch, caplog):
    monkeypatch.setenv('YTDLP_DIAGNOSTICS', '1')
    log = DiagnosticLog()
    for message in (
        '[debug] params: bgutil Cookie: SID=secret-cookie',
        '[debug] [youtube] [pot] generated token secret-token',
        '[debug] [youtube] [pot] failed response secret-response',
    ):
        log.debug(message)
    log.warning('HTTP Error 403 Cookie: secret-cookie')
    log.error('LOGIN_REQUIRED https://example.com/?auth=secret-url')
    assert 'secret-' not in caplog.text
    assert 'category=access_denied' in caplog.text
    assert 'category=authentication' in caplog.text

import logging
from app.services.video_service import DiagnosticLog, options


def test_diagnostics_opt_in(monkeypatch):
    monkeypatch.delenv('YTDLP_DIAGNOSTICS', raising=False)
    normal = options()
    assert normal['verbose'] is False
    monkeypatch.setenv('YTDLP_DIAGNOSTICS', '1')
    diagnostic = options()
    assert diagnostic['verbose'] is True
    assert isinstance(diagnostic['logger'], DiagnosticLog)
    assert diagnostic['extractor_args'] == normal['extractor_args']


def test_provider_diagnostics(caplog):
    with caplog.at_level(logging.WARNING):
        log = DiagnosticLog()
        log.debug('[debug] Proxy map: secret-proxy')
        log.debug("[debug] params: {'bgutil': 'private-config'}")
        log.debug('[debug] [youtube] [pot] bgutil available https://example.com/?token=private')
        log.debug('[debug] [youtube] [pot:bgutil:script-node] Executing command to get POT via script: node --context private-visitor')
        log.warning('provider warning')
        log.error('provider error')
    assert 'bgutil available' in caplog.text
    assert 'secret-proxy' not in caplog.text
    assert 'token=private' not in caplog.text
    assert 'provider warning' in caplog.text
    assert 'provider error' in caplog.text

    assert 'private-config' not in caplog.text
    assert 'private-visitor' not in caplog.text
    assert 'Invoking token generator' in caplog.text

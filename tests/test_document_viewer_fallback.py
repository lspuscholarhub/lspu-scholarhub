"""Word documents preview through Google, which cannot always be reached.

When the Google Docs viewer is blocked, firewalled or offline it renders an
empty frame with no error the page can inspect, so the viewer page has to check
it first and show a message (with the download still available) when it fails.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'app' / 'templates' / 'shared' / 'document_viewer.html'


def _body():
    return TEMPLATE.read_text(encoding='utf-8')


def test_word_documents_have_a_fallback_panel_beside_the_google_frame():
    body = _body()
    assert 'id="gviewFrame"' in body and 'id="gviewFallback"' in body
    assert 'id="gviewRetry"' in body
    # the download must stay reachable from the fallback
    fallback = body.split('id="gviewFallback"')[1].split('{% else %}')[0]
    assert '?dl=1' in fallback, 'the fallback must offer the file download'


def test_the_frame_is_checked_before_it_is_trusted():
    body = _body()
    assert 'navigator.onLine' in body, 'offline must be handled without waiting'
    assert 'no-cors' in body, 'the viewer URL must be probed to detect a block'
    assert "'online'" in body and "'offline'" in body, 'the page must recover on reconnect'


def test_hidden_fallbacks_stay_hidden():
    # .docv-fallback is display:flex, which would otherwise beat [hidden]
    body = _body()
    assert '.docv-fallback[hidden]' in body
    assert 'display: none !important' in body.split('.docv-fallback[hidden]')[1][:80]
    assert '.docv-frame[hidden]' in body

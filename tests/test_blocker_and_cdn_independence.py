"""The interface must survive an ad blocker and an unreachable CDN.

Two things took the admin and staff screens down in the field: their components
were named .ad-*, which EasyList (uBlock Origin, AdBlock, AdGuard, Brave) hides
by class name, and Bootstrap, its icons, the webfont and Chart.js all came from
public CDNs that a blocker, a captive portal or an offline demo can make
unreachable. These checks keep both from creeping back.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'app' / 'templates'
STATIC = ROOT / 'app' / 'static'

# Elements these filter lists hide from every site, by class name. A class of
# ours that appears here is invisible for anyone running a blocker.
BLOCKER_HIDDEN = {
    'ad-bar', 'ad-body', 'ad-choices', 'ad-field', 'ad-hint', 'ad-note',
    'ad-panel', 'ad-sep', 'ad-table', 'ad-tile', 'ad-title',
    'ad-banner', 'ad-box', 'ad-container', 'ad-slot', 'ad-unit', 'ad-wrap',
}

VENDORED = [
    'vendor/bootstrap/bootstrap.min.css',
    'vendor/bootstrap/bootstrap.bundle.min.js',
    'vendor/bootstrap-icons/bootstrap-icons.css',
    'vendor/bootstrap-icons/fonts/bootstrap-icons.woff2',
    'vendor/chartjs/chart.umd.min.js',
    'vendor/marked/marked.min.js',
    'vendor/inter/inter.css',
    'vendor/inter/inter-latin-400-normal.woff2',
]


def _templates():
    return sorted(TEMPLATES.rglob('*.html'))


def _stylesheets():
    return sorted((STATIC / 'css').glob('*.css'))


def test_no_template_loads_css_or_js_from_another_site():
    pattern = re.compile(r'<(?:link|script)[^>]+(?:href|src)="https?://', re.I)
    offenders = []
    for path in _templates():
        for match in pattern.finditer(path.read_text(encoding='utf-8')):
            offenders.append(f'{path.relative_to(ROOT)}: {match.group(0)[:80]}')
    assert offenders == [], 'assets must be served by this app: ' + '; '.join(offenders)


def test_vendored_assets_are_present():
    empty = [name for name in VENDORED if not (STATIC / name).is_file()
             or (STATIC / name).stat().st_size == 0]
    assert empty == [], 'missing vendored assets: ' + ', '.join(empty)


def test_no_class_name_is_on_an_ad_blocker_hide_list():
    tokens = set()
    for path in _templates():
        for attr in re.findall(r'class="([^"]*)"', path.read_text(encoding='utf-8')):
            tokens.update(attr.split())
    for path in _stylesheets():
        # strip /* comments */: admin-pages.css documents the blocked names
        css = re.sub(r'/\*.*?\*/', '', path.read_text(encoding='utf-8'), flags=re.S)
        tokens.update(re.findall(r'\.([A-Za-z][\w-]*)', css))

    blocked = sorted(tokens & BLOCKER_HIDDEN)
    assert blocked == [], 'ad blockers hide these classes by name: ' + ', '.join(blocked)

    ad_prefixed = sorted(t for t in tokens if t.startswith('ad-'))
    assert ad_prefixed == [], ('the ad- prefix collides with filter lists; '
                               'use shb- for the board: ' + ', '.join(ad_prefixed))


def test_base_template_guards_the_shell_against_injected_hiding():
    body = (TEMPLATES / 'base.html').read_text(encoding='utf-8')
    assert "'.shb-body'" in body and 'getComputedStyle' in body, \
        'base.html must restore a shell container that an extension hid'

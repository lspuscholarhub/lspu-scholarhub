"""Tests for the dev-script production guard (scripts/dev/_guard.py)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'dev'))

import _guard  # noqa: E402


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('MYSQL_HOST', raising=False)
    monkeypatch.delenv('FLASK_ENV', raising=False)
    monkeypatch.delenv('RAILWAY_ENVIRONMENT', raising=False)
    monkeypatch.delenv('TEST_SMS_NUMBER', raising=False)
    monkeypatch.setattr(sys, 'argv', ['script.py'])


def test_local_database_needs_no_flag(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'mysql+pymysql://root:@localhost/lspu_scholarhub')
    _guard.require_confirmation('seed demo data')  # must not raise


def test_remote_database_is_refused(monkeypatch, capsys):
    monkeypatch.setenv('DATABASE_URL', 'mysql+pymysql://user:s3cr3t-token@db.example.com/prod')
    with pytest.raises(SystemExit) as exc:
        _guard.require_confirmation('seed demo data')
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert 'Refusing' in out
    assert 'db.example.com' in out
    assert 's3cr3t-token' not in out  # never echo credentials


def test_confirmation_flag_allows_remote(monkeypatch, capsys):
    monkeypatch.setenv('DATABASE_URL', 'mysql+pymysql://user:pass@db.example.com/prod')
    monkeypatch.setattr(sys, 'argv', ['script.py', '--confirm-production'])
    _guard.require_confirmation('seed demo data')  # must not raise
    assert 'allowed because --confirm-production' in capsys.readouterr().out


def test_production_environment_blocks_even_localhost(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'mysql+pymysql://root:@localhost/lspu_scholarhub')
    monkeypatch.setenv('FLASK_ENV', 'production')
    with pytest.raises(SystemExit):
        _guard.require_confirmation('print password hashes')


def test_railway_environment_blocks(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'mysql+pymysql://root:@127.0.0.1/lspu_scholarhub')
    monkeypatch.setenv('RAILWAY_ENVIRONMENT', 'production')
    with pytest.raises(SystemExit):
        _guard.require_confirmation('seed demo data')


def test_sms_requires_explicit_flag(monkeypatch, capsys):
    monkeypatch.setenv('TEST_SMS_NUMBER', '+639171234567')
    with pytest.raises(SystemExit) as exc:
        _guard.require_sms_confirmation()
    assert exc.value.code == 1
    assert 'No SMS was sent' in capsys.readouterr().out


def test_sms_requires_recipient(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['script.py', '--send-sms'])
    with pytest.raises(SystemExit) as exc:
        _guard.require_sms_confirmation()
    assert exc.value.code == 1
    assert 'TEST_SMS_NUMBER is missing' in capsys.readouterr().out


def test_sms_flag_and_number_returns_masked(monkeypatch, capsys):
    monkeypatch.setenv('TEST_SMS_NUMBER', '+639171234567')
    monkeypatch.setattr(sys, 'argv', ['script.py', '--send-sms'])
    assert _guard.require_sms_confirmation() == '+639171234567'
    out = capsys.readouterr().out
    assert '***4567' in out
    assert '+639171234567' not in out


def test_sms_scripts_have_no_hardcoded_recipient():
    root = Path(__file__).resolve().parents[1]
    for name in ('test_sms.py', 'check_semaphore.py'):
        text = (root / 'scripts' / 'dev' / name).read_text(encoding='utf-8')
        assert '09683652615' not in text
        assert 'require_sms_confirmation()' in text

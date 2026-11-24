"""Tests for the credentials file of scripts/dev/rotate_known_passwords.py.

The file is the only record of a rotated password, so a rerun must never drop
an earlier account's entry, and applying without a destination must refuse.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'dev'))

import rotate_known_passwords as rotate  # noqa: E402


def test_save_credentials_keeps_earlier_entries(tmp_path):
    output = tmp_path / 'rotated_accounts.txt'
    output.write_text(
        rotate.CREDENTIALS_HEADER + '51\ta@example.com\tstudent\tfirst-pass\n',
        encoding='utf-8')

    rotate.save_credentials(output, [(56, 'b@example.com', 'student', 'second-pass')])

    lines = output.read_text(encoding='utf-8').splitlines()
    assert lines[0].startswith('#')
    assert '51\ta@example.com\tstudent\tfirst-pass' in lines
    assert '56\tb@example.com\tstudent\tsecond-pass' in lines


def test_save_credentials_replaces_same_account_once(tmp_path):
    output = tmp_path / 'rotated_accounts.txt'
    rotate.save_credentials(output, [(7, 'c@example.com', 'student', 'old-pass')])
    rotate.save_credentials(output, [(7, 'c@example.com', 'student', 'new-pass')])

    rows = [line for line in output.read_text(encoding='utf-8').splitlines()
            if line.startswith('7\t')]
    assert rows == ['7\tc@example.com\tstudent\tnew-pass']
    assert not output.with_name(output.name + '.tmp').exists()


def test_apply_without_output_is_refused(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['rotate_known_passwords.py', '--apply'])
    with pytest.raises(SystemExit) as exc:
        rotate.parse_args()
    assert exc.value.code == 2


def test_dry_run_needs_no_output(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['rotate_known_passwords.py'])
    args = rotate.parse_args()
    assert args.apply is False and args.output is None

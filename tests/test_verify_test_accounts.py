"""The test-accounts sheet must agree with the live password hashes.

The sheet drifted once — two student entries kept passwords from an earlier
rotation while the accounts had been restored to their own — so the check that
catches it gets its own tests.
"""
import sys
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'dev'))

import rotate_known_passwords as rotate  # noqa: E402
import verify_test_accounts as verify  # noqa: E402


def _sheet(tmp_path, *rows):
    doc = tmp_path / 'test_accounts.md'
    doc.write_text(
        '# Test accounts\n\nnotes to keep\n\n'
        + rotate.BLOCK_START + '\n'
        + ''.join(rows)
        + rotate.BLOCK_END + '\n',
        encoding='utf-8')
    return doc


def test_read_credentials_reads_only_the_block(tmp_path):
    doc = _sheet(tmp_path, '51\tstudent@lspu.test\tstudent\tpw-one\n',
                 '68\tother@lspu.test\tstudent\tpw-two\n')
    # A stale-looking entry outside the markers must not be read back.
    doc.write_text(doc.read_text(encoding='utf-8')
                   .replace('notes to keep', '51\tbogus@lspu.test\tstudent\tnope'),
                   encoding='utf-8')

    entries = verify.read_credentials(doc)

    assert entries == {51: ('student@lspu.test', 'pw-one'),
                       68: ('other@lspu.test', 'pw-two')}


def test_sheet_without_markers_is_refused(tmp_path):
    doc = tmp_path / 'no-markers.md'
    doc.write_text('just notes\n', encoding='utf-8')

    with pytest.raises(SystemExit):
        verify.read_credentials(doc)


def test_recorded_password_that_still_authenticates_is_ok(tmp_path):
    entries = verify.read_credentials(
        _sheet(tmp_path, '51\tstudent@lspu.test\tstudent\tpw-one\n'))
    accounts = {51: ('student@lspu.test', generate_password_hash('pw-one'))}

    ok, drifted, missing = verify.compare(entries, accounts)

    assert [row[0] for row in ok] == [51]
    assert drifted == [] and missing == []


def test_stale_password_is_reported_as_drifted(tmp_path):
    entries = verify.read_credentials(
        _sheet(tmp_path, '51\tstudent@lspu.test\tstudent\told-rotation\n'))
    accounts = {51: ('student@lspu.test', generate_password_hash('restored-own'))}

    ok, drifted, missing = verify.compare(entries, accounts)

    assert ok == []
    assert [row[0] for row in drifted] == [51]
    assert missing == []


def test_account_that_no_longer_exists_is_reported(tmp_path):
    entries = verify.read_credentials(
        _sheet(tmp_path, '999\tgone@lspu.test\tstudent\tpw-one\n'))

    ok, drifted, missing = verify.compare(entries, {})

    assert ok == [] and drifted == []
    assert [row[0] for row in missing] == [999]

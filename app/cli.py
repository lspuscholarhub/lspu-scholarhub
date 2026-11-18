"""Portal integration commands.

    flask portal-sync status                  readiness + last runs
    flask portal-sync test                    connect and read a record
    flask portal-sync run --dry-run           preview a full sync
    flask portal-sync run                     apply a full sync
    flask portal-sync student 0199-0000       refresh one student
    flask portal-sync archive-legacy          preview the go-live archival
    flask portal-sync archive-legacy --apply  archive legacy accounts

Run these on the server (Railway shell) or locally against a CSV export:

    flask portal-sync run --file portal_students.csv --dry-run
"""
import json
from datetime import datetime

import click

from app import db


def register_cli(app):

    @app.cli.group('portal-sync')
    def portal_sync():
        """LSPU portal integration (read-only student data)."""

    @portal_sync.command('status')
    def status_cmd():
        """Show configuration, student counts and the last sync runs."""
        from app.services.portal import portal_status
        click.echo(json.dumps(portal_status(), indent=2, default=str))

    @portal_sync.command('test')
    @click.option('--file', 'file_path', default=None,
                  help='Read a CSV/JSON export instead of the database.')
    def test_cmd(file_path):
        """Connect to the portal source and read a sample record."""
        from app.services.portal.source import get_portal_source, PortalNotConfigured
        kwargs = {'path': file_path} if file_path else {}
        try:
            source = get_portal_source(**kwargs)
        except PortalNotConfigured as exc:
            click.echo(f'[not configured] {exc}')
            raise SystemExit(2)
        try:
            students = source.fetch_all()
        finally:
            dispose = getattr(source, 'dispose', None)
            if callable(dispose):
                dispose()

        click.echo(f'[ok] source={source.mode} students={len(students)}')
        if not students:
            click.echo('No student records returned — check the view/query.')
            return
        sample = students[0].to_dict()
        # Never echo a whole record: show which fields arrived, not PII.
        present = sorted(k for k, v in sample.items() if v not in (None, {}, []))
        click.echo('Fields present on the first record: ' + ', '.join(present))

    @portal_sync.command('run')
    @click.option('--file', 'file_path', default=None,
                  help='Read a CSV/JSON export instead of the database.')
    @click.option('--student', 'student_ids', multiple=True,
                  help='Only sync these student IDs (repeatable).')
    @click.option('--dry-run', is_flag=True, default=False,
                  help='Report what would change without writing anything.')
    @click.option('--trigger', default='manual', show_default=True,
                  help='Recorded on the run: manual | schedule.')
    def run_cmd(file_path, student_ids, dry_run, trigger):
        """Sync portal students into ScholarHub."""
        from app.services.portal import sync_students

        from app.services.portal.source import PortalNotConfigured
        try:
            stats = sync_students(student_ids=student_ids or None,
                                  trigger=trigger, dry_run=dry_run,
                                  file_path=file_path)
        except PortalNotConfigured as exc:
            click.echo(f'[not configured] {exc}')
            raise SystemExit(2)
        click.echo(json.dumps(stats, indent=2, default=str))
        if stats.get('error'):
            raise SystemExit(1)

    @portal_sync.command('student')
    @click.argument('student_id')
    @click.option('--dry-run', is_flag=True, default=False)
    def student_cmd(student_id, dry_run):
        """Refresh a single student from the portal."""
        from app.services.portal import sync_one
        stats = sync_one(student_id, trigger='manual', dry_run=dry_run)
        click.echo(json.dumps(stats, indent=2, default=str))
        if stats.get('error'):
            raise SystemExit(1)

    @portal_sync.command('archive-legacy')
    @click.option('--apply', is_flag=True, default=False,
                  help='Actually archive. Without it this is a preview.')
    def archive_legacy_cmd(apply):
        """Archive self-registered student accounts at portal cut-over."""
        from app.services.portal import archive_legacy_students
        result = archive_legacy_students(dry_run=not apply)
        click.echo(json.dumps(result, indent=2, default=str))
        if not apply:
            click.echo('Preview only — rerun with --apply to archive.')

"""Recompute every batch's total_scholars / total_male / total_female / total_amount.

    python scripts/recalculate_batch_totals.py            # repair and report
    python scripts/recalculate_batch_totals.py --dry-run  # report only, then roll back

Databases written before the model maintained these columns on every change (or
by scripts that updated applications with raw SQL) can hold totals that disagree
with their approved applications. Run this once after deploying; it prints only
the batches whose row changed, so it is quiet on a database that is already
consistent.
"""
import argparse
import os
import sys

# Running "python scripts/recalculate_batch_totals.py" puts scripts/ (not the
# repo root) on sys.path, so make the app package importable before anything
# below imports it.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _totals(batch):
    return (batch.total_scholars, batch.total_male, batch.total_female,
            float(batch.total_amount or 0))


def recalculate_all_batches(dry_run=False):
    """Recalculate every batch; return [(id, name, before, after)] for changed rows.

    The batch's applications collection is expired first, so the recount reads
    what the database holds rather than whatever a caller happened to load.
    """
    from app import db
    from app.models import ScholarshipBatch

    changed = []
    for batch in ScholarshipBatch.query.order_by(ScholarshipBatch.id).all():
        before = _totals(batch)
        db.session.expire(batch, ['applications'])
        batch.recalculate_totals()
        after = _totals(batch)
        if before != after:
            changed.append((batch.id, batch.batch_name, before, after))

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
    return changed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--dry-run', action='store_true',
                        help='report the batches that would change, then roll back')
    args = parser.parse_args(argv)
    os.environ.setdefault('FLASK_ENV', 'development')

    from app import create_app, db
    import app.models  # noqa: F401  importing the package registers every model
    from app.models import ScholarshipBatch

    application = create_app()
    with application.app_context():
        changed = recalculate_all_batches(dry_run=args.dry_run)
        checked = ScholarshipBatch.query.count()
        url = db.engine.url.render_as_string(hide_password=True)

        print(f'batch totals recount: {url}')
        print(f'  batches checked: {checked}')
        if not changed:
            print('  OK: every batch already matches its approved applications.')
            return 0

        suffix = ' (dry run, rolled back)' if args.dry_run else ''
        print(f'  rows changed: {len(changed)}{suffix}')
        for batch_id, name, before, after in changed:
            print(f'    #{batch_id} {name}: '
                  f'scholars {before[0]} -> {after[0]}, '
                  f'male {before[1]} -> {after[1]}, '
                  f'female {before[2]} -> {after[2]}, '
                  f'amount {before[3]:.2f} -> {after[3]:.2f}')
        return 0


if __name__ == '__main__':
    sys.exit(main())

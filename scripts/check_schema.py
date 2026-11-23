"""Check that a database has every table and column the models map.

    python scripts/check_schema.py --create                      # build an empty DB, then compare
    python scripts/check_schema.py --url mysql+pymysql://...     # inspect an existing database

Exits 1 and lists the drift when the database is behind the models, which is how
a database missing a column the code reads (silently NULL / "no such column")
gets caught instead of showing up as a broken page in production.

Extra tables are reported for information only; the failure condition is a
mapped table or column the database does not have.
"""
import argparse
import os
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--url', help='database URL to inspect (defaults to DATABASE_URL)')
    parser.add_argument('--create', action='store_true',
                        help='create any missing tables first (for a fresh database)')
    args = parser.parse_args(argv)

    if args.url:
        # config reads DATABASE_URL at import time, so this must happen first.
        os.environ['DATABASE_URL'] = args.url
    os.environ.setdefault('FLASK_ENV', 'development')

    from sqlalchemy import inspect as sa_inspect

    from app import create_app, db
    import app.models  # noqa: F401  importing the package registers every model

    application = create_app()
    with application.app_context():
        if args.create:
            db.create_all()

        inspector = sa_inspect(db.engine)
        existing = set(inspector.get_table_names())

        missing = {}
        for table in db.metadata.sorted_tables:
            if table.name not in existing:
                missing[table.name] = ['<whole table missing>']
                continue
            present = {column['name'] for column in inspector.get_columns(table.name)}
            absent = [column.name for column in table.columns if column.name not in present]
            if absent:
                missing[table.name] = absent

        extras = sorted(name for name in existing
                        if name not in db.metadata.tables and not name.startswith('sqlite_'))
        url = db.engine.url.render_as_string(hide_password=True)

    print(f'schema check: {url}')
    print(f'  mapped tables checked: {len(db.metadata.sorted_tables)}')
    if extras:
        print(f'  tables not in the models (ignored): {", ".join(extras)}')
    if not missing:
        print('  OK: every mapped table and column exists in the database.')
        return 0

    print(f'  DRIFT: {sum(len(v) for v in missing.values())} missing item(s)')
    for table, columns in sorted(missing.items()):
        print(f'    {table}: {", ".join(columns)}')
    print('  The database is behind the models; add or run the migration before deploying.')
    return 1


if __name__ == '__main__':
    sys.exit(main())

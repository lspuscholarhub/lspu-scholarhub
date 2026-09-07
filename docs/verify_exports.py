"""Verify all Excel/PDF export endpoints work against the live Railway DB.

READ-ONLY: only calls export/report endpoints that generate files.
Run:  DATABASE_URL='mysql://...' python docs/verify_exports.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db

REPORTS = []


def check(name, resp):
    ct = resp.headers.get('Content-Type', '')
    body = resp.data
    magic = body[:4]
    kind = ('xlsx' if magic.startswith(b'PK')
            else 'pdf' if magic.startswith(b'%PDF')
            else 'html' if magic.startswith(b'<!DOC') or magic.startswith(b'<h') else '?')
    ok = resp.status_code == 200 and kind in ('xlsx', 'pdf') and len(body) > 500
    REPORTS.append((name, resp.status_code, ct.split(';')[0], kind, f"{len(body)/1024:.0f} KB", 'PASS' if ok else 'FAIL'))


def main():
    app = create_app()
    with app.app_context():
        from app.models import User
        from app.models.scholarship_batch import ScholarshipBatch

        staff = User.query.filter_by(user_type='staff', is_active=True).first()
        admin = User.query.filter_by(user_type='admin', is_active=True).first()
        batch = ScholarshipBatch.query.first()
        batch_count = ScholarshipBatch.query.count()
        print(f"DIAGNOSTICS: staff={'yes' if staff else 'no'} admin={'yes' if admin else 'no'} batches={batch_count}")

    client = app.test_client()

    if staff:
        with client.session_transaction() as s:
            s['user_id'], s['user_type'] = staff.id, 'staff'
        check('GET /staff/reports/export', client.get('/staff/reports/export'))
        if batch:
            check(f'GET /staff/batches/{batch.id}/export', client.get(f'/staff/batches/{batch.id}/export'))
        else:
            print('NOTE: no batches in DB — staff batch export untested')
    else:
        print('NOTE: no staff account found')

    client = app.test_client()   # fresh client = fresh session
    if admin:
        with client.session_transaction() as s:
            s['user_id'], s['user_type'] = admin.id, 'admin'
        check('GET /admin/reports/export', client.get('/admin/reports/export'))
        check('GET /admin/audit-log/export', client.get('/admin/audit-log/export'))
        if batch:
            check(f'GET /admin/batches/{batch.id}/export', client.get(f'/admin/batches/{batch.id}/export'))
    else:
        print('NOTE: no admin account found')

    print(f"\n{'ENDPOINT':<36}{'CODE':<6}{'CONTENT-TYPE':<26}{'KIND':<6}{'SIZE':<9}RESULT")
    print('-' * 90)
    fails = 0
    for name, code, ct, kind, size, result in REPORTS:
        print(f"{name:<36}{code:<6}{ct:<26}{kind:<6}{size:<9}{result}")
        if result == 'FAIL':
            fails += 1
    print('-' * 90)
    print('ALL EXPORTS PASS' if fails == 0 else f'{fails} EXPORT(S) FAILED')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()

"""Verify the batch Excel export end-to-end using an isolated in-memory DB.

Creates a synthetic scholarship + period + batch + 2 approved scholars, then
calls the real /staff/batches/<id>/export endpoint and validates the xlsx.
Run:  python docs/verify_batch_export.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from app import create_app, db
from app.models import User, ScholarshipApplication
from app.models.scholarship import Scholarship, ScholarshipStatus, ApplicationStatus
from app.models.scholarship_batch import ScholarshipBatch
from app.models.academic_period import AcademicPeriod


def main():
    app = create_app('testing')
    with app.app_context():
        db.create_all()

        # ── Synthetic data ────────────────────────────────────────────────
        staff = User(username='staff1', email='staff@test.com', first_name='Staff',
                     last_name='Tester', user_type='staff', is_active=True,
                     is_verified=True, gender='Male', password_hash='x')
        db.session.add(staff)

        period = AcademicPeriod(academic_year='2026-2027', semester='1st Semester',
                                is_current=True)
        db.session.add(period)
        db.session.flush()

        sch = Scholarship(title='Test Scholarship Program', status=ScholarshipStatus.ACTIVE,
                          award_amount=10000, description='test',
                          eligibility_criteria='GWA 1.75 or better', benefits='Tuition',
                          created_by=staff.id)
        db.session.add(sch)
        db.session.flush()

        batch = ScholarshipBatch(scholarship_id=sch.id, academic_period_id=period.id,
                                 batch_name='Batch 1', batch_number=1,
                                 amount_per_scholar=10000, status='open')
        db.session.add(batch)
        db.session.flush()

        for i, (fn, ln, gender) in enumerate([('Juan', 'Dela Cruz', 'Male'),
                                              ('Maria', 'Santos', 'Female')]):
            u = User(username=f'stud{i}', email=f'stud{i}@test.com', first_name=fn,
                     last_name=ln, user_type='student', is_active=True, is_verified=True,
                     gender=gender, course='BSIT', year_level='2nd Year', gwa=1.50,
                     password_hash='x')
            db.session.add(u)
            db.session.flush()
            db.session.add(ScholarshipApplication(
                applicant_id=u.id, scholarship_id=sch.id, batch_id=batch.id,
                status=ApplicationStatus.APPROVED, submitted_at=datetime.utcnow()))
        db.session.commit()
        batch_id = batch.id
        staff_id = staff.id

    client = app.test_client()
    with client.session_transaction() as s:
        s['user_id'], s['user_type'] = staff_id, 'staff'

    resp = client.get(f'/staff/batches/{batch_id}/export')
    body = resp.data
    kind = ('xlsx' if body[:2] == b'PK' else
            'pdf' if body[:4] == b'%PDF' else
            'html' if body[:5] == b'<!DOC' else '?')
    ok = resp.status_code == 200 and kind == 'xlsx' and len(body) > 500
    print(f"GET /staff/batches/{batch_id}/export → {resp.status_code} "
          f"kind={kind} size={len(body)/1024:.0f}KB "
          f"content-type={resp.headers.get('Content-Type','').split(';')[0]}")
    print('BATCH EXPORT: PASS' if ok else 'BATCH EXPORT: FAIL')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()

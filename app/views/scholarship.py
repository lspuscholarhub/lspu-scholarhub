import os
import logging
from datetime import datetime
from flask import (Blueprint, render_template, request, flash,
                   redirect, url_for, session, current_app, send_from_directory)
from app import db
from app.models import User, Scholarship, ScholarshipApplication, Notification
from app.models.scholarship import ScholarshipStatus, ApplicationStatus
from app.models.notification import NotificationType, NotificationChannel
from app.models.document import Document
from app.services.document_service import document_service
from app.services.notification_service import notification_service
from app.utils.decorators import login_required, role_required
from app.utils.period_context import get_viewing_period

scholarship_bp = Blueprint('scholarship', __name__)
logger = logging.getLogger(__name__)


# ── Public listing ────────────────────────────────────────────────────────────

@scholarship_bp.route('/')
def list_scholarships():
    """List scholarships — respects is_hidden and allowed_student_ids."""
    q = request.args.get('q', '').strip()

    # Campus filter: students see their campus + university-wide scholarships
    user = User.query.get(session.get('user_id')) if session.get('user_id') else None
    user_campus_id = user.campus_id if user else None
    user_type = session.get('user_type', '')

    query = Scholarship.query
    if q:
        query = query.filter(Scholarship.title.ilike(f'%{q}%'))

    # Campus scoping: students see campus-specific + university-wide
    if user_type == 'student' and user_campus_id:
        from sqlalchemy import or_
        query = query.filter(or_(
            Scholarship.campus_id == user_campus_id,
            Scholarship.campus_id.is_(None)   # university-wide
        ))
    elif user_type in ('staff', 'admin') and user_campus_id:
        # Staff/admin see their campus + university-wide
        from sqlalchemy import or_
        query = query.filter(or_(
            Scholarship.campus_id == user_campus_id,
            Scholarship.campus_id.is_(None)
        ))
    # super_admin sees all (no filter)

    # Period filtering: students see permanent programs + programs for the selected period
    from app.utils.period_context import get_viewing_period, is_viewing_specific_period
    viewing_period = get_viewing_period()
    if user_type == 'student':
        from sqlalchemy import or_
        if is_viewing_specific_period() and viewing_period:
            # Student selected a specific period — show permanent + that period's programs
            query = query.filter(or_(
                Scholarship.academic_period_id.is_(None),
                Scholarship.academic_period_id == viewing_period.id
            ))
        else:
            # Current period — show permanent + current period's programs
            current = AcademicPeriod.get_current()
            if current:
                query = query.filter(or_(
                    Scholarship.academic_period_id.is_(None),
                    Scholarship.academic_period_id == current.id
                ))

    all_scholarships = query.order_by(Scholarship.application_deadline.asc()).all()

    # Filter by visibility for students
    student_id = None
    if user_type == 'student' and user:
        student_id = user.student_id

    if user_type in ('admin', 'super_admin', 'staff', 'admin'):
        scholarships = all_scholarships
    else:
        scholarships = [s for s in all_scholarships if s.is_visible_to(student_id)]

    # Collect the student's application states per scholarship
    applied_ids = set()
    withdrawn_ids = set()
    rejected_ids = set()
    holds_public = False
    active_scholarship_title = None
    if session.get('user_type') == 'student':
        for a in ScholarshipApplication.query.filter_by(applicant_id=session['user_id']).all():
            if a.status == ApplicationStatus.WITHDRAWN:
                withdrawn_ids.add(a.scholarship_id)
            elif a.status == ApplicationStatus.REJECTED:
                rejected_ids.add(a.scholarship_id)
            else:
                applied_ids.add(a.scholarship_id)

        # Public scholarships are exclusive — check for an active one
        # (pending, under review, or approved)
        approved_app = _active_public_application(session['user_id'])
        if approved_app:
            holds_public = True
            active_scholarship_title = approved_app.scholarship.title

    return render_template(
        'scholarship/list.html',
        scholarships=scholarships,
        applied_ids=applied_ids,
        withdrawn_ids=withdrawn_ids,
        rejected_ids=rejected_ids,
        holds_public=holds_public,
        active_scholarship_title=active_scholarship_title,
        q=q,
    )


# ── Public/private scholarship rule ──────────────────────────────────────────

def _active_public_application(user_id, exclude_app_id=None):
    """The student's ACTIVE public scholarship application, if any.

    Rule (per academic period): a student may pursue only ONE public
    (government-funded) scholarship within the same academic period —
    a pending/under-review application or an approved award counts.
    When a new academic period starts, they may apply to a different
    public program again. Private scholarships are combinable — with
    the public one and with each other.
    """
    from app.models.academic_period import AcademicPeriod
    period = get_viewing_period()

    q = (ScholarshipApplication.query
         .join(Scholarship, ScholarshipApplication.scholarship_id == Scholarship.id)
         .filter(
             ScholarshipApplication.applicant_id == user_id,
             ScholarshipApplication.status.in_(
                 [ApplicationStatus.PENDING, ApplicationStatus.UNDER_REVIEW,
                  ApplicationStatus.APPROVED]),
             Scholarship.funding_type == 'public',
         ))
    if exclude_app_id:
        q = q.filter(ScholarshipApplication.id != exclude_app_id)
    apps = q.all()

    if not period:
        # No academic period configured — fall back to legacy behaviour
        return apps[0] if apps else None

    # Only count applications submitted in the current academic period.
    # Approved awards whose period ended do not block a new application.
    start = (period.start_date or None)
    for a in apps:
        ref = a.submitted_at
        if start and ref and ref.date() < start:
            continue
        # An award approved in an EARLIER period doesn't block either
        if a.status == ApplicationStatus.APPROVED and a.approved_at:
            if start and a.approved_at.date() < start:
                continue
            if period.end_date and a.approved_at.date() > period.end_date:
                continue
        return a
    return None


@scholarship_bp.route('/<int:scholarship_id>')
def view_scholarship(scholarship_id):
    """View scholarship details — respects visibility rules."""
    scholarship = Scholarship.query.get_or_404(scholarship_id)

    # Check visibility for students
    if session.get('user_type') == 'student':
        user = User.query.get(session['user_id'])
        if not scholarship.is_visible_to(user.student_id if user else None):
            flash('This scholarship is not available.', 'warning')
            return redirect(url_for('scholarship.list_scholarships'))

    already_applied = False
    can_reapply     = False
    reapply_reason  = None
    holds_public = False
    active_scholarship_title = None
    if session.get('user_type') == 'student':
        existing = ScholarshipApplication.query.filter_by(
            scholarship_id=scholarship_id,
            applicant_id=session['user_id'],
        ).first()
        if existing:
            if existing.status in (ApplicationStatus.WITHDRAWN, ApplicationStatus.REJECTED):
                can_reapply = True      # withdrawn or rejected → allowed to re-apply
                reapply_reason = 'withdrawn' if existing.status == ApplicationStatus.WITHDRAWN else 'rejected'
            else:
                already_applied = True  # active application exists

        # Public scholarships are exclusive — check for an active one
        # (pending, under review, or approved)
        approved_app = _active_public_application(session['user_id'])
        if approved_app:
            holds_public = True
            active_scholarship_title = approved_app.scholarship.title

    days_left = (scholarship.application_deadline - datetime.utcnow()).days if scholarship.application_deadline else None
    fill_pct  = 0
    if scholarship.max_applicants:
        fill_pct = int((scholarship.current_applicants or 0) / scholarship.max_applicants * 100)

    return render_template(
        'scholarship/view.html',
        scholarship=scholarship,
        already_applied=already_applied,
        can_reapply=can_reapply,
        reapply_reason=reapply_reason,
        holds_public=holds_public,
        active_scholarship_title=active_scholarship_title,
        days_left=days_left,
        fill_pct=fill_pct,
    )


# ── Application submission ────────────────────────────────────────────────────

@scholarship_bp.route('/apply/<int:scholarship_id>', methods=['GET', 'POST'])
@role_required('student')
def apply_scholarship(scholarship_id):
    """Submit a scholarship application with document uploads."""
    scholarship = Scholarship.query.get_or_404(scholarship_id)
    user        = User.query.get(session['user_id'])

    # Guard: scholarship must be open
    if not scholarship.is_application_open():
        flash('This scholarship is no longer accepting applications.', 'warning')
        return redirect(url_for('scholarship.view_scholarship', scholarship_id=scholarship_id))

    # Guard: student must be verified
    if not user.is_verified:
        flash('Your account must be verified before you can apply for scholarships. '
              'Please contact the scholarship office or wait for admin verification.', 'warning')
        return redirect(url_for('scholarship.view_scholarship', scholarship_id=scholarship_id))

    # Guard: only ONE public scholarship application may be active at a time
    # (pending, under review, or approved) — private programs are combinable.
    if scholarship.funding_type == 'public':
        active_public = _active_public_application(user.id)
        if active_public:
            st = active_public.status.value.replace('_', ' ')
            flash(f'You already have a public scholarship application '
                  f'("{active_public.scholarship.title}" — {st}). Only one public '
                  'scholarship is allowed at a time — you may still apply to '
                  'private scholarship programs.', 'warning')
            return redirect(url_for('student.my_applications'))

    # Guard: no duplicate ACTIVE application for this scholarship.
    # Withdrawn or rejected applications free the student to apply again.
    existing = ScholarshipApplication.query.filter_by(
        scholarship_id=scholarship_id,
        applicant_id=user.id,
    ).filter(
        ScholarshipApplication.status.in_(
            [ApplicationStatus.PENDING, ApplicationStatus.UNDER_REVIEW,
             ApplicationStatus.APPROVED])
    ).first()
    if existing:
        flash('You have an active application for this scholarship.', 'warning')
        return redirect(url_for('student.my_applications'))

    # Guard: visibility — student must be in the allowed list if scholarship is hidden
    if not scholarship.is_visible_to(user.student_id):
        flash('This scholarship is not available to you.', 'warning')
        return redirect(url_for('scholarship.list_scholarships'))

    if request.method == 'POST':
        form = request.form

        try:
            if not form.get('terms') or not form.get('privacy'):
                flash('You must agree to the terms and privacy policy.', 'error')
                return render_template('scholarship/apply.html',
                                       scholarship=scholarship, user=user,
                                       editing=False, application=None)

            # ── Build application data from user profile ───────────────────────
            gpa = user.gwa or 0
            units = form.get('units_enrolled', '').strip()

            # Persist birthday entered on the form to the user's profile
            bday_raw = (form.get('birthday') or '').strip()
            if bday_raw:
                try:
                    user.date_of_birth = datetime.strptime(bday_raw, '%Y-%m-%d').date()
                except ValueError:
                    pass

            application_data = {
                'first_name':      user.first_name,
                'last_name':       user.last_name,
                'student_id':      user.student_id,
                'email':           user.email,
                'phone':           user.phone_number or '',
                'course':          user.course or '',
                'year_level':      user.year_level or '',
                'gwa':             gpa,
                'units_enrolled':  int(units) if units.isdigit() else None,
                'gender':          user.gender or '',
                'birthday':        user.date_of_birth.isoformat() if user.date_of_birth else '',
                'town':            user.town or '',
                'province':        user.province or '',
            }
            # Update user's units if provided
            if units.isdigit():
                user.units_enrolled = int(units)

            # ── Collect custom form field responses ──────────────────────────
            try:
                if scholarship.custom_form_fields:
                    custom_responses = []
                    for i, field in enumerate(scholarship.custom_form_fields):
                        value = form.get(f'custom_{i}', '').strip()
                        if field.get('required') and not value:
                            flash(f'Please fill in: {field["label"]}', 'error')
                            return render_template('scholarship/apply.html',
                                                   scholarship=scholarship, user=user,
                                                   editing=False, application=None)
                        custom_responses.append({
                            'label': field['label'],
                            'value': value,
                        })
                    application_data['custom_fields'] = custom_responses
            except Exception:
                pass  # custom_form_fields column may not exist yet

            # ── Save application ───────────────────────────────────────────────
            application = ScholarshipApplication(
                scholarship_id=scholarship_id,
                applicant_id=user.id,
                application_data=application_data,
                documents=[],
                status=ApplicationStatus.PENDING,
            )
            db.session.add(application)
            db.session.flush()

            # Update applicant counter
            scholarship.current_applicants = (scholarship.current_applicants or 0) + 1

            db.session.commit()

            # ── Notifications (non-critical — don't crash on failure) ──────────
            try:
                notification_service.send_scholarship_application_received(
                    user.email, user.phone_number or '', user.id, scholarship.title,
                )
            except Exception as e:
                import logging as _log
                _log.getLogger(__name__).warning(f'Notification failed (non-fatal): {e}')

            try:
                from app.services.audit_service import log_action
                log_action('application.submit',
                           f'Student {user.get_full_name()} ({user.student_id}) submitted application '
                           f'#{application.id} for "{scholarship.title}". GWA: {gpa}.',
                           category='application', target_type='application', target_id=application.id)
            except Exception as e:
                import logging as _log
                _log.getLogger(__name__).warning(f'Audit log failed (non-fatal): {e}')

            flash(f'Your application for "{scholarship.title}" has been submitted!', 'success')
            return redirect(url_for('student.my_applications'))

        except Exception as e:
            import logging as _log
            _log.getLogger(__name__).error(f'Application submit error: {e}', exc_info=True)
            db.session.rollback()
            flash(f'An error occurred while submitting your application. Please try again.', 'error')
            return render_template('scholarship/apply.html',
                                   scholarship=scholarship, user=user,
                                   editing=False, application=None)

    # Ensure custom_form_fields is accessible even if column doesn't exist yet
    try:
        _ = scholarship.custom_form_fields
    except Exception:
        scholarship.custom_form_fields = None

    return render_template('scholarship/apply.html', scholarship=scholarship, user=user,
                           editing=False, application=None)


# ── Edit application (before deadline) ───────────────────────────────────────

@scholarship_bp.route('/application/<int:app_id>/edit', methods=['GET', 'POST'])
@role_required('student')
def edit_application(app_id):
    """Allow student to edit a pending application before the deadline."""
    application = ScholarshipApplication.query.get_or_404(app_id)
    user        = User.query.get(session['user_id'])

    if application.applicant_id != session['user_id']:
        flash('Access denied.', 'error')
        return redirect(url_for('student.my_applications'))

    if application.status not in (ApplicationStatus.PENDING, ApplicationStatus.UNDER_REVIEW):
        flash('Only pending or under-review applications can be edited.', 'warning')
        return redirect(url_for('student.my_applications'))

    if not application.scholarship.is_application_open():
        flash('The deadline for this scholarship has passed. No further edits are allowed.', 'warning')
        return redirect(url_for('student.my_applications'))

    if request.method == 'POST':
        form_data = application.application_data or {}

        # Persist birthday to the user's profile
        bday_raw = (request.form.get('birthday') or '').strip()
        if bday_raw:
            try:
                user.date_of_birth = datetime.strptime(bday_raw, '%Y-%m-%d').date()
                form_data['birthday'] = user.date_of_birth.isoformat()
            except ValueError:
                pass

        # Update editable fields (simplified form — no essay, no old document categories)
        for field in ['first_name', 'last_name', 'phone', 'course',
                      'year_level', 'gwa', 'units_enrolled']:
            val = request.form.get(field, '').strip()
            if val:
                if field == 'gwa':
                    try:
                        form_data[field] = float(val)
                    except ValueError:
                        pass
                elif field == 'units_enrolled':
                    try:
                        form_data[field] = int(val)
                    except ValueError:
                        pass
                else:
                    form_data[field] = val

        application.application_data = form_data

        db.session.commit()
        flash('Application updated successfully.', 'success')
        return redirect(url_for('student.my_applications'))

    return render_template('scholarship/apply.html',
                           scholarship=application.scholarship,
                           user=user,
                           application=application,
                           editing=True)


# ── Withdraw application ──────────────────────────────────────────────────────

@scholarship_bp.route('/application/<int:app_id>/withdraw', methods=['POST'])
@role_required('student')
def withdraw_application(app_id):
    application = ScholarshipApplication.query.get_or_404(app_id)
    if application.applicant_id != session['user_id']:
        flash('Access denied.', 'error')
        return redirect(url_for('student.my_applications'))
    if application.status not in (ApplicationStatus.PENDING, ApplicationStatus.UNDER_REVIEW):
        flash('This application cannot be withdrawn.', 'warning')
        return redirect(url_for('student.my_applications'))

    reason = request.form.get('withdraw_reason', '').strip()

    application.status = ApplicationStatus.WITHDRAWN
    # Store the withdrawal reason in review_notes so admin/staff can see it
    if reason:
        application.review_notes = f'[Withdrawn by student] {reason}'
    else:
        application.review_notes = '[Withdrawn by student — no reason provided]'

    application.scholarship.current_applicants = max(
        0, (application.scholarship.current_applicants or 1) - 1
    )
    db.session.commit()

    from app.services.audit_service import log_action
    user = User.query.get(session['user_id'])
    log_action('application.withdraw',
               f'Student {user.get_full_name()} ({user.student_id}) withdrew application '
               f'#{app_id} for "{application.scholarship.title}".'
               + (f' Reason: {reason}' if reason else ' No reason provided.'),
               category='application', target_type='application', target_id=app_id)

    flash('Your application has been withdrawn.', 'info')
    return redirect(url_for('student.my_applications'))


# ── Document download ─────────────────────────────────────────────────────────

@scholarship_bp.route('/document/<int:doc_id>/download')
@login_required
def download_document(doc_id):
    """Serve a document file for download."""
    import os
    from flask import send_file as _send_file
    doc = Document.query.get_or_404(doc_id)

    # Students can only download their own docs; staff/admin can download any
    if session.get('user_type') == 'student' and doc.user_id != session['user_id']:
        flash('Access denied.', 'error')
        return redirect(url_for('student.profile'))

    file_path = doc.file_path
    if not os.path.isabs(file_path):
        file_path = os.path.join(current_app.root_path, '..', file_path)
    file_path = os.path.normpath(file_path)

    if not os.path.exists(file_path):
        flash('File not found on server.', 'error')
        return redirect(url_for('scholarship.list_scholarships'))

    return _send_file(file_path, as_attachment=True,
                      download_name=doc.original_filename)

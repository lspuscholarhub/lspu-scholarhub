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

scholarship_bp = Blueprint('scholarship', __name__)
logger = logging.getLogger(__name__)


# ── Public listing ────────────────────────────────────────────────────────────

@scholarship_bp.route('/')
def list_scholarships():
    """List scholarships — respects is_hidden and allowed_student_ids."""
    q        = request.args.get('q', '').strip()
    status   = request.args.get('status', 'active')
    category = request.args.get('category', '')

    query = Scholarship.query
    if status == 'active':
        query = query.filter_by(status=ScholarshipStatus.ACTIVE)
    elif status == 'all':
        pass
    else:
        try:
            query = query.filter_by(status=ScholarshipStatus(status))
        except ValueError:
            pass

    if q:
        query = query.filter(Scholarship.title.ilike(f'%{q}%'))
    if category:
        query = query.filter(Scholarship.category == category)

    all_scholarships = query.order_by(Scholarship.application_deadline.asc()).all()

    # Filter by visibility for students
    student_id = None
    if session.get('user_type') == 'student':
        user = User.query.get(session['user_id'])
        student_id = user.student_id if user else None

    if session.get('user_type') in ('admin', 'staff'):
        scholarships = all_scholarships
    else:
        scholarships = [s for s in all_scholarships if s.is_visible_to(student_id)]

    # Collect IDs the student already applied to (non-withdrawn)
    applied_ids = set()
    withdrawn_ids = set()
    if session.get('user_type') == 'student':
        for a in ScholarshipApplication.query.filter_by(applicant_id=session['user_id']).all():
            if a.status == ApplicationStatus.WITHDRAWN:
                withdrawn_ids.add(a.scholarship_id)
            else:
                applied_ids.add(a.scholarship_id)

    # Get distinct categories for the filter dropdown
    categories = sorted({s.category for s in Scholarship.query.all() if s.category})

    return render_template(
        'scholarship/list.html',
        scholarships=scholarships,
        applied_ids=applied_ids,
        withdrawn_ids=withdrawn_ids,
        categories=categories,
        q=q,
        status=status,
        category=category,
    )


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
    if session.get('user_type') == 'student':
        existing = ScholarshipApplication.query.filter_by(
            scholarship_id=scholarship_id,
            applicant_id=session['user_id'],
        ).first()
        if existing:
            if existing.status == ApplicationStatus.WITHDRAWN:
                can_reapply = True      # withdrawn → allowed to re-apply
            else:
                already_applied = True  # active application exists

    days_left = (scholarship.application_deadline - datetime.utcnow()).days if scholarship.application_deadline else None
    fill_pct  = 0
    if scholarship.max_applicants:
        fill_pct = int((scholarship.current_applicants or 0) / scholarship.max_applicants * 100)

    return render_template(
        'scholarship/view.html',
        scholarship=scholarship,
        already_applied=already_applied,
        can_reapply=can_reapply,
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

    # Guard: no duplicate active applications (withdrawn = allowed to re-apply)
    existing = ScholarshipApplication.query.filter_by(
        scholarship_id=scholarship_id,
        applicant_id=user.id,
    ).first()
    if existing and existing.status != ApplicationStatus.WITHDRAWN:
        flash('You have already applied for this scholarship.', 'warning')
        return redirect(url_for('student.my_applications'))

    # Guard: visibility — student must be in the allowed list if scholarship is hidden
    if not scholarship.is_visible_to(user.student_id):
        flash('This scholarship is not available to you.', 'warning')
        return redirect(url_for('scholarship.list_scholarships'))

    if request.method == 'POST':
        form = request.form

        if not form.get('terms') or not form.get('privacy'):
            flash('You must agree to the terms and privacy policy.', 'error')
            return render_template('scholarship/apply.html',
                                   scholarship=scholarship, user=user,
                                   editing=False, application=None)

        # ── Upload grades file ────────────────────────────────────────────
        grades_file = request.files.get('grades_file')
        if not grades_file or not grades_file.filename:
            flash('Please upload your Copy of Grades.', 'error')
            return render_template('scholarship/apply.html',
                                   scholarship=scholarship, user=user,
                                   editing=False, application=None)

        grades_result = document_service.save_file(grades_file, user.id, 'grades')
        if not grades_result['success']:
            flash(f'Could not upload grades: {grades_result["message"]}', 'error')
            return render_template('scholarship/apply.html',
                                   scholarship=scholarship, user=user,
                                   editing=False, application=None)

        grades_info = grades_result['file_info']

        # ── Build application data from user profile ───────────────────────
        gpa = user.gwa or 0
        units = form.get('units_enrolled', '').strip()
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
        }
        # Update user's units if provided
        if units.isdigit():
            user.units_enrolled = int(units)

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

        # Save grades document record
        doc = Document(
            user_id=user.id,
            application_id=application.id,
            original_filename=grades_info['original_filename'],
            stored_filename=grades_info['stored_filename'],
            file_path=grades_info['file_path'],
            file_size=grades_info['file_size'],
            category='grades',
            file_type=grades_info['file_type'],
            cloudinary_url=grades_info.get('cloudinary_url'),
            cloudinary_public_id=grades_info.get('cloudinary_public_id'),
        )
        db.session.add(doc)

        # Update applicant counter
        scholarship.current_applicants = (scholarship.current_applicants or 0) + 1

        db.session.commit()

        # ── Notifications ──────────────────────────────────────────────────
        notification_service.send_scholarship_application_received(
            user.email, user.phone_number or '', user.id, scholarship.title,
        )

        from app.services.audit_service import log_action
        log_action('application.submit',
                   f'Student {user.get_full_name()} ({user.student_id}) submitted application '
                   f'#{application.id} for "{scholarship.title}". GWA: {gpa}.',
                   category='application', target_type='application', target_id=application.id)

        flash(f'Your application for "{scholarship.title}" has been submitted!', 'success')
        return redirect(url_for('student.my_applications'))

    return render_template('scholarship/apply.html', scholarship=scholarship, user=user,
                           editing=False, application=None)


# ── Student: my applications ──────────────────────────────────────────────────

@scholarship_bp.route('/my-applications')
@role_required('student')
def my_applications():
    """View the logged-in student's applications."""
    user = User.query.get(session['user_id'])
    apps = (ScholarshipApplication.query
            .filter_by(applicant_id=user.id)
            .order_by(ScholarshipApplication.submitted_at.desc())
            .all())

    total     = len(apps)
    approved  = sum(1 for a in apps if a.status == ApplicationStatus.APPROVED)
    pending   = sum(1 for a in apps if a.status in (ApplicationStatus.PENDING,
                                                     ApplicationStatus.UNDER_REVIEW))
    rejected  = sum(1 for a in apps if a.status == ApplicationStatus.REJECTED)
    total_award = sum(
        float(a.scholarship.award_amount or 0)
        for a in apps if a.status == ApplicationStatus.APPROVED
    )

    return render_template(
        'scholarship/applications.html',
        applications=apps,
        total=total,
        approved=approved,
        pending=pending,
        rejected=rejected,
        total_award=total_award,
    )


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

        # Handle optional grades file replacement
        grades_file = request.files.get('grades_file')
        if grades_file and grades_file.filename:
            result = document_service.save_file(grades_file, user.id, 'grades')
            if result['success']:
                info = result['file_info']
                existing_doc = Document.query.filter_by(
                    application_id=application.id,
                    category='grades'
                ).first()
                if existing_doc:
                    # Delete old file from Cloudinary if applicable
                    if existing_doc.cloudinary_public_id:
                        from app.services.storage_service import delete_file as _del
                        _del(public_id=existing_doc.cloudinary_public_id)
                    elif existing_doc.file_path:
                        document_service.delete_file(existing_doc.file_path)
                    existing_doc.original_filename    = info['original_filename']
                    existing_doc.stored_filename      = info['stored_filename']
                    existing_doc.file_path            = info['file_path']
                    existing_doc.file_size            = info['file_size']
                    existing_doc.file_type            = info['file_type']
                    existing_doc.cloudinary_url       = info.get('cloudinary_url')
                    existing_doc.cloudinary_public_id = info.get('cloudinary_public_id')
                    existing_doc.is_verified          = False
                else:
                    new_doc = Document(
                        user_id=user.id,
                        application_id=application.id,
                        original_filename=info['original_filename'],
                        stored_filename=info['stored_filename'],
                        file_path=info['file_path'],
                        file_size=info['file_size'],
                        category='grades',
                        file_type=info['file_type'],
                        cloudinary_url=info.get('cloudinary_url'),
                        cloudinary_public_id=info.get('cloudinary_public_id'),
                    )
                    db.session.add(new_doc)
            else:
                flash(f'Could not replace grades: {result["message"]}', 'warning')

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
        return redirect(url_for('student.documents'))

    file_path = doc.file_path
    if not os.path.isabs(file_path):
        file_path = os.path.join(current_app.root_path, '..', file_path)
    file_path = os.path.normpath(file_path)

    if not os.path.exists(file_path):
        flash('File not found on server.', 'error')
        return redirect(url_for('scholarship.list_scholarships'))

    return _send_file(file_path, as_attachment=True,
                      download_name=doc.original_filename)

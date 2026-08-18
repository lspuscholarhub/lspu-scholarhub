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

    days_left = (scholarship.application_deadline - datetime.utcnow()).days
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
        # ── Collect form data ──────────────────────────────────────────────
        form = request.form
        required_fields = ['first_name', 'last_name', 'student_id', 'email',
                           'phone', 'course', 'year_level', 'gpa', 'essay']
        missing = [f for f in required_fields if not form.get(f, '').strip()]
        if missing:
            flash(f'Please fill in all required fields: {", ".join(missing)}', 'error')
            return render_template('scholarship/apply.html',
                                   scholarship=scholarship, user=user)

        if not form.get('terms') or not form.get('privacy'):
            flash('You must agree to the terms and privacy policy.', 'error')
            return render_template('scholarship/apply.html',
                                   scholarship=scholarship, user=user)

        try:
            gpa = float(form['gpa'])
            if not (1.00 <= gpa <= 5.00):
                raise ValueError
        except ValueError:
            flash('GWA must be a number between 1.00 and 5.00.', 'error')
            return render_template('scholarship/apply.html',
                                   scholarship=scholarship, user=user)

        # Enforce essay minimum word count
        essay_text = form.get('essay', '').strip()
        word_count = len(essay_text.split())
        if word_count < 300:
            flash(f'Your essay must be at least 300 words (currently {word_count} words).', 'error')
            return render_template('scholarship/apply.html',
                                   scholarship=scholarship, user=user)

        application_data = {
            'first_name':      form['first_name'],
            'last_name':       form['last_name'],
            'student_id':      form['student_id'],
            'email':           form['email'],
            'phone':           form['phone'],
            'course':          form['course'],
            'year_level':      form['year_level'],
            'gpa':             gpa,
            'units_completed': form.get('units_completed', ''),
            'essay':           essay_text,
        }

        # ── Handle file uploads ────────────────────────────────────────────
        saved_docs    = []
        upload_errors = []
        # Store file bytes for CTC detection (transcript specifically)
        transcript_bytes = None
        transcript_ext   = None

        for field_name in ['transcript', 'good_moral', 'birth_cert', 'awards']:
            file = request.files.get(field_name)
            if file and file.filename:
                if field_name == 'transcript':
                    transcript_bytes = file.read()
                    transcript_ext   = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
                    file.seek(0)   # reset stream for document_service
                result = document_service.save_file(file, user.id, field_name)
                if result['success']:
                    saved_docs.append(result['file_info'])
                else:
                    upload_errors.append(f"{field_name}: {result['message']}")

        # transcript and good_moral are required
        uploaded_categories = {d['category'] for d in saved_docs}
        for required_doc in ['transcript', 'good_moral']:
            if required_doc not in uploaded_categories:
                upload_errors.append(f'{required_doc.replace("_", " ").title()} is required.')

        if upload_errors:
            flash('Document errors: ' + '; '.join(upload_errors), 'error')
            return render_template('scholarship/apply.html',
                                   scholarship=scholarship, user=user)

        # ── Save application ───────────────────────────────────────────────
        # Sanitise saved_docs for JSON storage — convert any datetime to ISO string
        json_safe_docs = []
        for d in saved_docs:
            safe = dict(d)
            if hasattr(safe.get('uploaded_at'), 'isoformat'):
                safe['uploaded_at'] = safe['uploaded_at'].isoformat()
            json_safe_docs.append(safe)

        application = ScholarshipApplication(
            scholarship_id=scholarship_id,
            applicant_id=user.id,
            application_data=application_data,
            documents=json_safe_docs,
            status=ApplicationStatus.PENDING,
        )
        db.session.add(application)
        db.session.flush()   # get application.id before committing

        # Persist Document records (run CTC detection on transcript)
        from app.services.ocr_service import detect_ctc_stamp
        for doc_info in saved_docs:
            ctc_result = None
            if doc_info['category'] == 'transcript' and transcript_bytes:
                try:
                    ctc = detect_ctc_stamp(transcript_bytes, transcript_ext or doc_info['file_type'])
                    ctc_result = ctc.get('detected')   # True/False/None
                    logger.info(f"CTC detection on transcript: detected={ctc_result}, "
                                f"confidence={ctc.get('confidence')}, notes={ctc.get('notes')}")
                except Exception as ctc_err:
                    logger.warning(f'CTC detection error: {ctc_err}')

            doc = Document(
                user_id=user.id,
                application_id=application.id,
                original_filename=doc_info['original_filename'],
                stored_filename=doc_info['stored_filename'],
                file_path=doc_info['file_path'],
                file_size=doc_info['file_size'],
                category=doc_info['category'],
                file_type=doc_info['file_type'],
                ctc_detected=ctc_result,
            )
            db.session.add(doc)

        # Update applicant counter on scholarship
        scholarship.current_applicants = (scholarship.current_applicants or 0) + 1

        # Update user profile fields if not already set
        if not user.student_id:
            user.student_id = form['student_id']
        if not user.course:
            user.course = form['course']
        if not user.year_level:
            user.year_level = form['year_level']

        db.session.commit()

        # ── Notifications ──────────────────────────────────────────────────
        notification_service.send_scholarship_application_received(
            user.email,
            user.phone_number or '',
            user.id,
            scholarship.title,
        )

        from app.services.audit_service import log_action
        log_action('application.submit',
                   f'Student {user.get_full_name()} ({user.student_id}) submitted application '
                   f'#{application.id} for "{scholarship.title}". '
                   f'GWA: {application_data.get("gpa", "N/A")}, '
                   f'Course: {application_data.get("course", "N/A")}, '
                   f'Year: {application_data.get("year_level", "N/A")}.',
                   category='application', target_type='application', target_id=application.id)

        flash(f'Your application for "{scholarship.title}" has been submitted successfully!', 'success')
        return redirect(url_for('student.my_applications'))

    return render_template('scholarship/apply.html', scholarship=scholarship, user=user)


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

        # Update editable fields
        for field in ['first_name', 'last_name', 'phone', 'course',
                      'year_level', 'gpa', 'units_completed', 'essay']:
            val = request.form.get(field, '').strip()
            if val:
                form_data[field] = val

        # Validate essay word count
        essay_text = form_data.get('essay', '')
        word_count = len(essay_text.split())
        if word_count < 300:
            flash(f'Essay must be at least 300 words (currently {word_count}).', 'error')
            return render_template('scholarship/apply.html',
                                   scholarship=application.scholarship,
                                   user=user,
                                   application=application,
                                   editing=True)

        application.application_data = form_data

        # Handle optional document replacements
        for field_name in ['transcript', 'good_moral', 'birth_cert', 'awards']:
            file = request.files.get(field_name)
            if file and file.filename:
                result = document_service.save_file(file, user.id, field_name)
                if result['success']:
                    info = result['file_info']
                    # Replace existing doc of same category or add new one
                    existing_doc = Document.query.filter_by(
                        application_id=application.id,
                        category=field_name
                    ).first()
                    if existing_doc:
                        # Delete old file from disk
                        document_service.delete_file(existing_doc.file_path)
                        existing_doc.original_filename = info['original_filename']
                        existing_doc.stored_filename   = info['stored_filename']
                        existing_doc.file_path         = info['file_path']
                        existing_doc.file_size         = info['file_size']
                        existing_doc.file_type         = info['file_type']
                        existing_doc.is_verified       = False  # needs re-verification
                    else:
                        new_doc = Document(
                            user_id=user.id,
                            application_id=application.id,
                            original_filename=info['original_filename'],
                            stored_filename=info['stored_filename'],
                            file_path=info['file_path'],
                            file_size=info['file_size'],
                            category=field_name,
                            file_type=info['file_type'],
                        )
                        db.session.add(new_doc)
                else:
                    flash(f'Could not replace {field_name}: {result["message"]}', 'warning')

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

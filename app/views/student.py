import os
from datetime import datetime
from flask import (Blueprint, render_template, request, flash,
                   redirect, url_for, session, current_app, send_from_directory)
from app import db
from app.models import User, Scholarship, ScholarshipApplication, Notification
from app.models.scholarship import ScholarshipStatus, ApplicationStatus
from app.models.document import Document
from app.services.document_service import document_service
from app.utils.decorators import role_required

student_bp = Blueprint('student', __name__)


# ── Dashboard ─────────────────────────────────────────────────────────────────

@student_bp.route('/dashboard')
@role_required('student')
def dashboard():
    user = User.query.get(session['user_id'])
    apps = user.applications or []

    total_apps     = len(apps)
    approved_count = sum(1 for a in apps if a.status == ApplicationStatus.APPROVED)
    pending_count  = sum(1 for a in apps if a.status in (ApplicationStatus.PENDING,
                                                          ApplicationStatus.UNDER_REVIEW))

    # Available scholarships the student hasn't applied to yet — respect visibility
    applied_ids   = {a.scholarship_id for a in apps}
    all_active = Scholarship.query.filter(
        Scholarship.status == ScholarshipStatus.ACTIVE,
        ~Scholarship.id.in_(applied_ids) if applied_ids else True,
    ).order_by(Scholarship.application_deadline.asc()).all()

    # Filter by visibility for this student
    new_scholarships = [s for s in all_active if s.is_visible_to(user.student_id)][:3]

    # Recent notifications (unread first)
    recent_notifications = (Notification.query
                            .filter_by(recipient_id=user.id)
                            .order_by(Notification.is_read.asc(),
                                      Notification.sent_at.desc())
                            .limit(5).all())

    # Recent applications for the dashboard table
    recent_apps = sorted(apps, key=lambda a: a.submitted_at, reverse=True)[:5]

    return render_template(
        'student/dashboard.html',
        user=user,
        total_apps=total_apps,
        approved_count=approved_count,
        pending_count=pending_count,
        new_scholarships_count=len(new_scholarships),
        new_scholarships=new_scholarships,
        recent_notifications=recent_notifications,
        recent_apps=recent_apps,
    )


# ── My applications ───────────────────────────────────────────────────────────

@student_bp.route('/applications')
@role_required('student')
def my_applications():
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
        'student/applications.html',
        applications=apps,
        total=total,
        approved=approved,
        pending=pending,
        rejected=rejected,
        total_award=total_award,
    )


# ── Apply for scholarship (redirect to scholarship blueprint) ─────────────────

@student_bp.route('/apply/<int:scholarship_id>')
@role_required('student')
def apply_scholarship(scholarship_id):
    return redirect(url_for('scholarship.apply_scholarship',
                            scholarship_id=scholarship_id))


# ── Notifications ─────────────────────────────────────────────────────────────

@student_bp.route('/notifications')
@role_required('student')
def notifications():
    user   = User.query.get(session['user_id'])
    filter_type = request.args.get('filter', 'all')

    query = Notification.query.filter_by(recipient_id=user.id)
    if filter_type == 'unread':
        query = query.filter_by(is_read=False)
    elif filter_type == 'applications':
        from app.models.notification import NotificationType
        query = query.filter(Notification.notification_type.in_([
            NotificationType.APPLICATION_SUBMITTED,
            NotificationType.APPLICATION_APPROVED,
            NotificationType.APPLICATION_REJECTED,
        ]))
    elif filter_type == 'scholarships':
        from app.models.notification import NotificationType
        query = query.filter(Notification.notification_type.in_([
            NotificationType.NEW_SCHOLARSHIP,
            NotificationType.DEADLINE_REMINDER,
        ]))

    notifs      = query.order_by(Notification.sent_at.desc()).all()
    unread_count = Notification.query.filter_by(
        recipient_id=user.id, is_read=False).count()

    return render_template(
        'student/notifications.html',
        notifications=notifs,
        unread_count=unread_count,
        filter_type=filter_type,
    )


@student_bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@role_required('student')
def mark_notification_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.recipient_id != session['user_id']:
        return '', 403
    notif.mark_as_read()
    db.session.commit()
    return redirect(url_for('student.notifications'))


@student_bp.route('/notifications/mark-all-read', methods=['POST'])
@role_required('student')
def mark_all_read():
    from datetime import datetime
    Notification.query.filter_by(
        recipient_id=session['user_id'], is_read=False
    ).update({'is_read': True, 'read_at': datetime.utcnow()})
    db.session.commit()
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('student.notifications'))


# ── Documents ─────────────────────────────────────────────────────────────────

@student_bp.route('/documents')
@role_required('student')
def documents():
    user  = User.query.get(session['user_id'])
    docs  = (Document.query
             .filter_by(user_id=user.id)
             .order_by(Document.uploaded_at.desc())
             .all())

    total_size  = sum(d.file_size or 0 for d in docs)
    verified    = sum(1 for d in docs if d.is_verified)
    pending_v   = sum(1 for d in docs if not d.is_verified)

    return render_template(
        'student/documents.html',
        documents=docs,
        total_size=total_size,
        verified=verified,
        pending_v=pending_v,
    )


@student_bp.route('/documents/upload', methods=['POST'])
@role_required('student')
def upload_document():
    user = User.query.get(session['user_id'])
    file = request.files.get('document_file')
    desc = request.form.get('document_description', '').strip()

    if not file or not file.filename:
        flash('Please select a file to upload.', 'error')
        return redirect(url_for('student.documents'))

    # Use 'general' as the default category since we removed the category picker
    result = document_service.save_file(file, user.id, 'general')
    if not result['success']:
        flash(result['message'], 'error')
        return redirect(url_for('student.documents'))

    info = result['file_info']
    doc  = Document(
        user_id=user.id,
        original_filename=info['original_filename'],
        stored_filename=info['stored_filename'],
        file_path=info['file_path'],
        file_size=info['file_size'],
        category='general',
        file_type=info['file_type'],
        description=desc or info['original_filename'],
    )
    db.session.add(doc)
    db.session.commit()
    flash(f'"{info["original_filename"]}" uploaded successfully.', 'success')
    return redirect(url_for('student.documents'))


@student_bp.route('/documents/<int:doc_id>/delete', methods=['POST'])
@role_required('student')
def delete_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.user_id != session['user_id']:
        flash('Access denied.', 'error')
        return redirect(url_for('student.documents'))

    document_service.delete_file(doc.file_path)
    db.session.delete(doc)
    db.session.commit()
    flash('Document deleted.', 'success')
    return redirect(url_for('student.documents'))


@student_bp.route('/documents/<int:doc_id>/download')
@role_required('student')
def download_document(doc_id):
    import os
    from flask import send_file as _send_file, Response
    doc = Document.query.get_or_404(doc_id)
    if doc.user_id != session['user_id']:
        flash('Access denied.', 'error')
        return redirect(url_for('student.documents'))

    # Cloudinary proxy
    if doc.cloudinary_public_id:
        try:
            import urllib.request as _ur
            from app.services.storage_service import get_signed_url
            res_type  = 'image' if (doc.file_type or '').lower() in ('jpg','jpeg','png') else 'raw'
            signed    = get_signed_url(doc.cloudinary_public_id, resource_type=res_type)
            fetch_url = signed or doc.cloudinary_url
            req = _ur.Request(fetch_url)
            req.add_header('User-Agent', 'LSPU-ScholarHub/1.0')
            with _ur.urlopen(req, timeout=30) as resp:
                file_data = resp.read()
            mime_map = {'pdf':'application/pdf','jpg':'image/jpeg','jpeg':'image/jpeg',
                        'png':'image/png','doc':'application/msword',
                        'docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
            mime = mime_map.get((doc.file_type or '').lower(), 'application/octet-stream')
            return Response(file_data, mimetype=mime,
                            headers={'Content-Disposition': f'attachment; filename="{doc.original_filename}"'})
        except Exception as e:
            flash(f'Could not download file: {e}', 'error')
            return redirect(url_for('student.documents'))

    file_path = doc.file_path
    if not os.path.isabs(file_path):
        file_path = os.path.join(current_app.root_path, '..', file_path)
    file_path = os.path.normpath(file_path)

    if not os.path.exists(file_path):
        flash('File not found on server.', 'error')
        return redirect(url_for('student.documents'))

    return _send_file(file_path, as_attachment=True,
                      download_name=doc.original_filename)


@student_bp.route('/documents/<int:doc_id>/view')
@student_bp.route('/documents/<int:doc_id>/view')
@role_required('student')
def view_document(doc_id):
    """Render a viewer page for any document type."""
    import os
    doc = Document.query.get_or_404(doc_id)
    if doc.user_id != session['user_id']:
        flash('Access denied.', 'error')
        return redirect(url_for('student.documents'))

    file_path = doc.file_path
    if not os.path.isabs(file_path):
        file_path = os.path.join(current_app.root_path, '..', file_path)
    file_path = os.path.normpath(file_path)

    if not os.path.exists(file_path):
        flash('File not found on server.', 'error')
        return redirect(url_for('student.documents'))

    return render_template('student/document_viewer.html',
                           doc=doc,
                           raw_url=url_for('student.serve_document_raw', doc_id=doc.id))


@student_bp.route('/documents/<int:doc_id>/raw')
@role_required('student')
def serve_document_raw(doc_id):
    """Serve the raw file with correct MIME type for inline display."""
    import os
    from flask import send_file as _send_file, Response
    doc = Document.query.get_or_404(doc_id)
    if doc.user_id != session['user_id']:
        flash('Access denied.', 'error')
        return redirect(url_for('student.documents'))

    mime_map = {
        'pdf':  'application/pdf',
        'jpg':  'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
        'doc':  'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }
    mime = mime_map.get((doc.file_type or '').lower(), 'application/octet-stream')
    force_download = request.args.get('dl') == '1'
    disposition    = 'attachment' if force_download else 'inline'

    # Cloudinary proxy
    if doc.cloudinary_public_id:
        try:
            import urllib.request as _ur
            from app.services.storage_service import get_signed_url
            res_type  = 'image' if (doc.file_type or '').lower() in ('jpg','jpeg','png') else 'raw'
            signed    = get_signed_url(doc.cloudinary_public_id, resource_type=res_type)
            fetch_url = signed or doc.cloudinary_url
            req = _ur.Request(fetch_url)
            req.add_header('User-Agent', 'LSPU-ScholarHub/1.0')
            with _ur.urlopen(req, timeout=30) as resp:
                file_data = resp.read()
            return Response(file_data, mimetype=mime,
                            headers={
                                'Content-Disposition': f'{disposition}; filename="{doc.original_filename}"',
                                'Content-Length': str(len(file_data)),
                            })
        except Exception as e:
            flash(f'Could not load file: {e}', 'error')
            return redirect(url_for('student.documents'))

    file_path = doc.file_path
    if not os.path.isabs(file_path):
        file_path = os.path.join(current_app.root_path, '..', file_path)
    file_path = os.path.normpath(file_path)

    if not os.path.exists(file_path):
        flash('File not found.', 'error')
        return redirect(url_for('student.documents'))

    return _send_file(file_path, mimetype=mime, as_attachment=force_download,
                      download_name=doc.original_filename)


# ── Profile ───────────────────────────────────────────────────────────────────

@student_bp.route('/profile')
@role_required('student')
def profile():
    user = User.query.get(session['user_id'])
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('auth.login'))

    apps           = user.applications or []
    total_applications = len(apps)
    pending_count  = sum(1 for a in apps if a.status.value == 'pending')
    approved_count = sum(1 for a in apps if a.status.value == 'approved')
    rejected_count = sum(1 for a in apps if a.status.value == 'rejected')

    return render_template(
        'student/profile.html',
        user=user,
        total_applications=total_applications,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
    )


@student_bp.route('/profile/update', methods=['POST'])
@role_required('student')
def update_profile():
    user = User.query.get(session['user_id'])

    # Handle document upload/replace from profile page
    doc_type = request.form.get('doc_type', '')
    if doc_type in ('cor', 'grades'):
        from app.services.document_service import document_service
        from app.services.storage_service import delete_file as _del_storage
        file = request.files.get(f'{doc_type}_file')
        if file and file.filename:
            result = document_service.save_file(file, user.id, doc_type)
            if result['success']:
                info = result['file_info']
                # Delete old file if exists
                old_path = user.cor_file_path if doc_type == 'cor' else user.grades_file_path
                old_cid  = user.cor_cloudinary_id if doc_type == 'cor' else user.grades_cloudinary_id
                if old_cid:
                    try: _del_storage(public_id=old_cid)
                    except Exception: pass
                elif old_path and not old_path.startswith('http'):
                    try: document_service.delete_file(old_path)
                    except Exception: pass
                # Update user record
                if doc_type == 'cor':
                    user.cor_file_path = info['file_path']
                    user.cor_cloudinary_id = info.get('cloudinary_public_id')
                else:
                    user.grades_file_path = info['file_path']
                    user.grades_cloudinary_id = info.get('cloudinary_public_id')
                db.session.commit()
                label = 'Certificate of Registration' if doc_type == 'cor' else 'Copy of Grades'
                flash(f'{label} uploaded successfully.', 'success')
            else:
                flash(f'Upload failed: {result["message"]}', 'error')
        else:
            flash('Please select a file to upload.', 'error')
        return redirect(url_for('student.profile'))

    # Only update non-readonly fields
    user.first_name   = request.form.get('first_name', user.first_name).strip().title()
    user.last_name    = request.form.get('last_name',  user.last_name).strip().title()
    user.phone_number = request.form.get('phone_number', user.phone_number or '').strip() or None
    user.course       = request.form.get('course',     user.course)
    user.year_level   = request.form.get('year_level', user.year_level)
    # student_id and email are read-only — not updated here

    new_pw = request.form.get('new_password', '').strip()
    if new_pw:
        # Require current password before allowing a change
        current_pw = request.form.get('current_password', '').strip()
        if not current_pw:
            flash('Please enter your current password to set a new one.', 'error')
            return redirect(url_for('student.profile'))
        if not user.check_password(current_pw):
            flash('Current password is incorrect. Password was not changed.', 'error')
            return redirect(url_for('student.profile'))
        if len(new_pw) < 8:
            flash('New password must be at least 8 characters.', 'error')
            return redirect(url_for('student.profile'))
        user.set_password(new_pw)
        # Clear the first-login flag now that they've set a personal password
        session.pop('first_login', None)
        db.session.commit()
        from app.services.audit_service import log_action
        log_action('auth.password_change',
                   f'Student {user.get_full_name()} ({user.student_id}) changed their password.',
                   category='auth', target_type='user', target_id=user.id)
        flash('Password updated successfully. Keep it safe!', 'success')
        return redirect(url_for('student.profile'))

    db.session.commit()
    flash('Profile updated successfully.', 'success')
    return redirect(url_for('student.profile'))


# ── Phone Verification ────────────────────────────────────────────────────────

@student_bp.route('/profile/send-phone-otp', methods=['POST'])
@role_required('student')
def send_phone_otp():
    """Send a 6-digit OTP to the student's phone number to verify it."""
    import random
    from datetime import timedelta
    from app.services.notification_service import notification_service

    user = User.query.get(session['user_id'])
    if not user.phone_number:
        flash('Please save a phone number first.', 'error')
        return redirect(url_for('student.profile'))

    otp = str(random.randint(100000, 999999))
    user.phone_otp = otp
    user.phone_otp_expires = datetime.utcnow() + timedelta(minutes=10)
    user.phone_verified = False
    db.session.commit()

    result = notification_service.send_sms(
        user.phone_number,
        f"LSPU ScholarHub: Your phone verification code is {otp}. Valid for 10 minutes."
    )

    if result.get('success'):
        flash('A 6-digit verification code was sent to your phone number.', 'success')
    else:
        flash(f'Could not send SMS: {result.get("message", "Unknown error")}. '
              'Check that your phone number is correct and try again.', 'error')
    return redirect(url_for('student.profile'))


@student_bp.route('/profile/verify-phone', methods=['POST'])
@role_required('student')
def verify_phone():
    """Verify the OTP entered by the student."""
    from datetime import datetime as dt
    user = User.query.get(session['user_id'])
    entered = request.form.get('otp', '').strip()

    if not user.phone_otp or not user.phone_otp_expires:
        flash('No verification code was sent. Please request one first.', 'error')
        return redirect(url_for('student.profile'))

    if dt.utcnow() > user.phone_otp_expires:
        flash('Verification code has expired. Please request a new one.', 'error')
        return redirect(url_for('student.profile'))

    if entered != user.phone_otp:
        flash('Incorrect verification code. Please try again.', 'error')
        return redirect(url_for('student.profile'))

    user.phone_verified = True
    user.phone_otp = None
    user.phone_otp_expires = None
    db.session.commit()
    flash('Phone number verified successfully!', 'success')
    return redirect(url_for('student.profile'))


# ── GWA Upload ────────────────────────────────────────────────────────────────

@student_bp.route('/upload-gwa', methods=['GET', 'POST'])
@role_required('student')
def upload_gwa():
    """
    Students can upload their Copy of Grades PDF to update their GWA.
    The system extracts the GWA via OCR and saves it to their profile.
    Used when GWA is pending at registration or needs updating each semester.
    """
    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        file = request.files.get('grades_file')
        if not file or not file.filename:
            flash('Please select a PDF file to upload.', 'error')
            return redirect(url_for('student.upload_gwa'))

        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        allowed_exts = {'pdf', 'jpg', 'jpeg', 'png'}
        if ext not in allowed_exts:
            flash('Please upload a PDF or image file (JPG/PNG) of your Copy of Grades.', 'error')
            return redirect(url_for('student.upload_gwa'))

        file_bytes = file.read()
        file.seek(0)

        # Save the file to Cloudinary or local
        from datetime import datetime
        from werkzeug.utils import secure_filename
        from app.services.storage_service import upload_file as _upload
        filename = secure_filename(
            f"grades_{user.student_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{ext}"
        )
        upload_result = _upload(file_bytes, filename, f"registration/{user.id}")
        if upload_result['success']:
            file_path  = upload_result['url']
            grades_cid = upload_result.get('public_id')
        else:
            # Local fallback
            upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'registration')
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, filename)
            with open(file_path, 'wb') as f:
                f.write(file_bytes)
            grades_cid = None

        # Run OCR to extract GWA
        try:
            from app.services.ocr_service import extract_document_data, _normalise_id
            result = extract_document_data(file_bytes, 'pdf')

            extracted_gwa = result.get('gwa')
            doc_student_id = result.get('student_id')

            # Verify the document belongs to this student
            if doc_student_id and doc_student_id != _normalise_id(user.student_id):
                flash(
                    f'The document you uploaded belongs to Student ID {doc_student_id}, '
                    f'but your account is {user.student_id}. '
                    f'Please upload your own Copy of Grades.',
                    'error'
                )
                os.remove(file_path)  # delete the invalid file
                return redirect(url_for('student.upload_gwa'))

            if extracted_gwa:
                # Update user GWA and units
                old_gwa = user.gwa
                user.gwa = round(extracted_gwa, 2)
                user.grades_file_path = file_path
                user.grades_cloudinary_id = grades_cid
                user.grades_updated_at = datetime.utcnow()
                # Auto-populate units_enrolled if extracted
                extracted_units = result.get('units_enrolled')
                if extracted_units:
                    user.units_enrolled = extracted_units

                # Mark which semester these grades are for
                from app.models.academic_period import AcademicPeriod
                current_period = AcademicPeriod.get_current()
                if current_period:
                    user.grades_semester = current_period.display_name
                    # Save to GWA history
                    from app.models.gwa_history import GwaHistory
                    history = GwaHistory(
                        student_id=user.id,
                        gwa=user.gwa,
                        semester=current_period.semester,
                        school_year=current_period.academic_year,
                        recorded_by=user.id,
                        notes='Self-uploaded via Copy of Grades',
                    )
                    db.session.add(history)

                db.session.commit()

                from app.services.audit_service import log_action
                log_action('gwa.student_upload',
                           f'Student {user.get_full_name()} ({user.student_id}) uploaded Copy of Grades. '
                           f'GWA updated from {old_gwa or "None"} to {user.gwa}.',
                           category='gwa', target_type='user', target_id=user.id)

                flash(
                    f'Your GWA has been updated to <strong>{user.gwa}</strong> based on your uploaded document.',
                    'success'
                )
            else:
                # GWA not found in document — save file for manual review
                user.grades_file_path = file_path
                db.session.commit()
                flash(
                    'Your Copy of Grades has been uploaded but the GWA could not be automatically extracted. '
                    'The scholarship office will review it and update your GWA manually.',
                    'warning'
                )

        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f'GWA upload OCR error: {e}')
            # Save file anyway for manual review
            user.grades_file_path = file_path
            db.session.commit()
            flash(
                'Your document has been uploaded. GWA extraction is temporarily unavailable — '
                'the scholarship office will review it manually.',
                'warning'
            )

        return redirect(url_for('student.profile'))

    return render_template('student/upload_gwa.html', user=user)

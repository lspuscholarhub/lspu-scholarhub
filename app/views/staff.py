import os
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, request, flash,
                   redirect, url_for, session, send_file, jsonify, current_app,
                   send_from_directory)
from app import db
from app.models import User, Scholarship, ScholarshipApplication, Notification
from app.models.scholarship import ScholarshipStatus, ApplicationStatus
from app.models.notification import NotificationType, NotificationChannel
from app.services.notification_service import notification_service
from app.utils.decorators import role_required

staff_bp = Blueprint('staff', __name__)

GWA_THRESHOLD = 3.00  # LSPU: above 3.00 = at-risk


# ── Dashboard ─────────────────────────────────────────────────────────────────

@staff_bp.route('/')
@role_required('staff')
def dashboard():
    from app.models import AcademicPeriod, ScholarshipBatch

    to_review = ScholarshipApplication.query.filter(
        ScholarshipApplication.status.in_([ApplicationStatus.PENDING,
                                           ApplicationStatus.UNDER_REVIEW])
    ).count()
    reviewed_today = ScholarshipApplication.query.filter(
        ScholarshipApplication.reviewed_by == session['user_id'],
        db.func.date(ScholarshipApplication.reviewed_at) == datetime.utcnow().date(),
    ).count()
    active_students = User.query.filter_by(user_type='student', is_active=True).count()
    new_users       = User.query.filter(
        User.created_at >= datetime.utcnow() - timedelta(days=30)
    ).count()
    approved_count  = ScholarshipApplication.query.filter_by(status=ApplicationStatus.APPROVED).count()
    at_risk_count   = User.query.filter(
        User.user_type == 'student', User.gwa.isnot(None), User.gwa > GWA_THRESHOLD
    ).count()
    male_students   = User.query.filter_by(user_type='student', gender='Male').count()
    female_students = User.query.filter_by(user_type='student', gender='Female').count()
    total_funds     = db.session.query(
        db.func.coalesce(db.func.sum(ScholarshipBatch.total_amount), 0)
    ).scalar() or 0
    active_batches  = ScholarshipBatch.query.filter_by(status='open').count()
    current_period  = AcademicPeriod.get_current()

    pending_apps = (ScholarshipApplication.query
                    .filter_by(status=ApplicationStatus.PENDING)
                    .order_by(ScholarshipApplication.submitted_at.asc())
                    .limit(5).all())
    recent_activity = (ScholarshipApplication.query
                       .order_by(ScholarshipApplication.submitted_at.desc())
                       .limit(5).all())

    # Top performing students (lowest GWA = best, closest to 1.00)
    top_performers = (User.query
                      .filter(User.user_type == 'student', User.gwa.isnot(None))
                      .order_by(User.gwa.asc())
                      .limit(5).all())

    return render_template(
        'staff/dashboard.html',
        to_review=to_review, reviewed_today=reviewed_today,
        active_students=active_students, approved_count=approved_count,
        at_risk_count=at_risk_count, new_users=new_users,
        male_students=male_students, female_students=female_students,
        total_funds=total_funds, active_batches=active_batches,
        current_period=current_period,
        pending_apps=pending_apps, recent_activity=recent_activity,
        top_performers=top_performers,
    )


# ── Scholarship Management (full CRUD — same as admin) ────────────────────────

@staff_bp.route('/scholarships')
@role_required('staff')
def manage_scholarships():
    scholarships = Scholarship.query.order_by(Scholarship.created_at.desc()).all()
    return render_template('staff/scholarships.html', scholarships=scholarships)


@staff_bp.route('/scholarships/create', methods=['POST'])
@role_required('staff')
def create_scholarship():
    try:
        deadline_str = request.form.get('application_deadline', '').strip()
        deadline = datetime.strptime(deadline_str, '%Y-%m-%d') if deadline_str else None

        # Build custom form fields from submitted data
        field_labels = request.form.getlist('field_label[]')
        field_types = request.form.getlist('field_type[]')
        field_options_raw = request.form.getlist('field_options[]')
        field_required_list = request.form.getlist('field_required[]')
        custom_fields = []
        for i, label in enumerate(field_labels):
            if not label.strip():
                continue
            ftype = field_types[i] if i < len(field_types) else 'text'
            options = None
            if ftype == 'dropdown' and i < len(field_options_raw):
                options = [o.strip() for o in field_options_raw[i].split(',') if o.strip()]
            custom_fields.append({
                'label': label.strip(),
                'type': ftype,
                'required': str(i) in field_required_list if i < len(field_required_list) else True,
                'options': options,
            })

        s = Scholarship(
            title=request.form['title'],
            category=request.form.get('category', 'General'),
            description=request.form.get('description', '').strip() or None,
            eligibility_criteria=request.form.get('eligibility_criteria', '').strip() or None,
            benefits=request.form.get('benefits', '').strip() or None,
            scholarship_type=request.form.get('scholarship_type', 'Financial Assistance'),
            funding_type=request.form.get('funding_type', 'public'),
            award_amount=max(0, float(request.form.get('award_amount') or 0)) or None,
            max_applicants=max(0, int(request.form.get('max_applicants') or 0)) or None,
            application_deadline=deadline,
            status=ScholarshipStatus.ACTIVE,
            created_by=session['user_id'],
            custom_form_fields=custom_fields if custom_fields else None,
        )
        s.is_hidden = bool(request.form.get('is_hidden'))
        s.allowed_student_ids = request.form.get('allowed_student_ids', '').strip() or None
        db.session.add(s)
        db.session.commit()
        from app.services.audit_service import log_action
        log_action('scholarship.create', f'Scholarship "{s.title}" created.',
                   category='scholarship', target_type='scholarship', target_id=s.id)
        flash(f'Scholarship "{s.title}" created.', 'success')

        # ── Optional announcement to all active students ─────────────────────
        if request.form.get('announce_scholarship') == '1':
            announce_title = f"New Scholarship: {s.title}"
            announce_msg = (request.form.get('announce_message') or '').strip() or (
                f'A new scholarship program "{s.title}" is now open for applications! '
                f'Log in to ScholarHub and go to Scholarships to apply.'
            )
            do_sms = request.form.get('announce_sms') == '1'
            do_email = request.form.get('announce_email') == '1'
            try:
                students = User.query.filter_by(user_type='student', is_active=True).all()
                sms_sent = 0
                for user in students:
                    db.session.add(Notification(
                        recipient_id=user.id,
                        title=announce_title,
                        message=announce_msg,
                        notification_type=NotificationType.NEW_SCHOLARSHIP,
                        channel=NotificationChannel.IN_APP,
                    ))
                    if do_email:
                        notification_service.send_email(
                            user.email, announce_title, announce_msg)
                    if do_sms and user.phone_number:
                        result = notification_service.send_sms(
                            user.phone_number, f"{announce_title}: {announce_msg}")
                        if result.get('success'):
                            sms_sent += 1
                db.session.commit()
                log_action('scholarship.announce',
                           f'Announced scholarship "{s.title}" to {len(students)} student(s).',
                           category='scholarship', target_type='scholarship', target_id=s.id)
                flash(f'Announcement sent to {len(students)} student(s)'
                      + (' · Email queued' if do_email else '')
                      + (f' · SMS delivered to {sms_sent}' if do_sms else '') + '.', 'success')
            except Exception as ae:
                db.session.rollback()
                current_app.logger.warning(f'Scholarship announcement failed (non-fatal): {ae}')
                flash('Scholarship created, but the announcement could not be sent.', 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {e}', 'error')
    return redirect(url_for('staff.manage_scholarships'))


@staff_bp.route('/scholarships/<int:sid>/edit', methods=['POST'])
@role_required('staff')
def edit_scholarship(sid):
    s = Scholarship.query.get_or_404(sid)
    try:
        s.title = request.form.get('title', s.title)
        s.category = request.form.get('category', s.category)
        ft = request.form.get('funding_type')
        if ft in ('public', 'private'):
            s.funding_type = ft
        s.description = request.form.get('description', s.description)
        s.eligibility_criteria = request.form.get('eligibility_criteria', s.eligibility_criteria)
        s.benefits = request.form.get('benefits', s.benefits)
        s.award_amount = max(0, float(request.form.get('award_amount') or 0)) or s.award_amount
        if request.form.get('max_applicants'):
            s.max_applicants = max(0, int(request.form['max_applicants'])) or None
        if request.form.get('application_deadline'):
            s.application_deadline = datetime.strptime(request.form['application_deadline'], '%Y-%m-%d')
        if request.form.get('status'):
            s.status = ScholarshipStatus(request.form['status'])
        s.is_hidden = request.form.get('is_hidden') == '1'
        raw_ids = request.form.get('allowed_student_ids', '')
        cleaned = ','.join(i.strip() for i in raw_ids.replace('\n', ',').split(',') if i.strip())
        s.allowed_student_ids = cleaned or None

        # Build custom form fields from submitted data
        field_labels = request.form.getlist('field_label[]')
        field_types = request.form.getlist('field_type[]')
        field_options_raw = request.form.getlist('field_options[]')
        field_required_list = request.form.getlist('field_required[]')
        custom_fields = []
        for i, label in enumerate(field_labels):
            if not label.strip():
                continue
            ftype = field_types[i] if i < len(field_types) else 'text'
            options = None
            if ftype == 'dropdown' and i < len(field_options_raw):
                options = [o.strip() for o in field_options_raw[i].split(',') if o.strip()]
            custom_fields.append({
                'label': label.strip(),
                'type': ftype,
                'required': str(i) in field_required_list if i < len(field_required_list) else True,
                'options': options,
            })
        s.custom_form_fields = custom_fields if custom_fields else None

        db.session.commit()
        from app.services.audit_service import log_action
        log_action('scholarship.edit', f'Scholarship "{s.title}" updated.',
                   category='scholarship', target_type='scholarship', target_id=s.id)
        flash(f'Scholarship "{s.title}" updated.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error: {e}', 'error')
    return redirect(url_for('staff.manage_scholarships'))


@staff_bp.route('/scholarships/<int:sid>/delete', methods=['POST'])
@role_required('staff')
def delete_scholarship(sid):
    s = Scholarship.query.get_or_404(sid)
    pending = ScholarshipApplication.query.filter_by(
        scholarship_id=sid, status=ApplicationStatus.PENDING).count()
    if pending:
        flash(f'Cannot delete: {pending} pending application(s) exist.', 'error')
        return redirect(url_for('staff.manage_scholarships'))
    db.session.delete(s)
    db.session.commit()
    flash('Scholarship deleted.', 'success')
    return redirect(url_for('staff.manage_scholarships'))


@staff_bp.route('/scholarships/<int:sid>/toggle-visibility', methods=['POST'])
@role_required('staff')
def toggle_scholarship_visibility(sid):
    s = Scholarship.query.get_or_404(sid)
    s.is_hidden = not s.is_hidden
    db.session.commit()
    flash(f'"{s.title}" is now {"hidden" if s.is_hidden else "visible"}.', 'success')
    return redirect(url_for('staff.manage_scholarships'))


# ── Application Review (with course + scholarship filters) ────────────────────

@staff_bp.route('/review-applications')
@role_required('staff')
def review_applications():
    # Default to the actionable queue: only applications awaiting a decision.
    # Approved/rejected live under their own filter (their process moves on to
    # batches / monitoring).
    status_filter     = request.args.get('status', 'pending')
    scholarship_filter = request.args.get('scholarship_id', '')
    course_filter     = request.args.get('course', '')
    year_filter       = request.args.get('year', '')
    q                 = request.args.get('q', '').strip()

    query = ScholarshipApplication.query.join(
        User, ScholarshipApplication.applicant_id == User.id)

    if status_filter and status_filter != 'all':
        try:
            if status_filter == 'pending':
                # Pending and Under Review are treated as one state
                query = query.filter(ScholarshipApplication.status.in_(
                    [ApplicationStatus.PENDING, ApplicationStatus.UNDER_REVIEW]))
            else:
                query = query.filter(ScholarshipApplication.status == ApplicationStatus(status_filter))
        except ValueError:
            pass
    if scholarship_filter:
        query = query.filter(ScholarshipApplication.scholarship_id == int(scholarship_filter))
    if course_filter:
        query = query.filter(User.course.ilike(f'%{course_filter}%'))
    if year_filter:
        query = query.filter(User.year_level == year_filter)
    if q:
        query = query.filter(db.or_(
            User.first_name.ilike(f'%{q}%'),
            User.last_name.ilike(f'%{q}%'),
            User.student_id.ilike(f'%{q}%'),
        ))

    # First-come-first-served: oldest applications appear first (paginated)
    page       = request.args.get('page', 1, type=int)
    pagination = (query.order_by(ScholarshipApplication.submitted_at.asc())
                      .paginate(page=page, per_page=20, error_out=False))
    applications = pagination.items
    scholarships = Scholarship.query.order_by(Scholarship.title).all()
    courses = sorted({
        u.course for u in User.query.filter(
            User.user_type == 'student', User.course.isnot(None)).all()
        if u.course
    })

    stats = {
        'total':        ScholarshipApplication.query.count(),
        'pending':      ScholarshipApplication.query.filter(ScholarshipApplication.status.in_(
                            [ApplicationStatus.PENDING, ApplicationStatus.UNDER_REVIEW])).count(),
        'under_review': 0,  # merged into pending
        'approved':     ScholarshipApplication.query.filter_by(status=ApplicationStatus.APPROVED).count(),
        'rejected':     ScholarshipApplication.query.filter_by(status=ApplicationStatus.REJECTED).count(),
    }

    return render_template(
        'staff/review_applications.html',
        applications=applications,
        scholarships=scholarships,
        courses=courses,
        stats=stats,
        pagination=pagination,
        status_filter=status_filter,
        scholarship_filter=scholarship_filter,
        course_filter=course_filter,
        year_filter=year_filter,
        q=q,
    )


@staff_bp.route('/applications/<int:app_id>/review', methods=['POST'])
@role_required('staff')
def review_application(app_id):
    application = ScholarshipApplication.query.get_or_404(app_id)
    action = request.form.get('action')
    notes  = request.form.get('review_notes', '')
    tag    = request.form.get('tag', 'active')

    status_map = {
        'approve':      ApplicationStatus.APPROVED,
        'reject':       ApplicationStatus.REJECTED,
    }
    new_status = status_map.get(action)
    if not new_status:
        flash('Invalid action.', 'error')
        return redirect(url_for('staff.review_applications'))

    # Guard: a student may hold only ONE public scholarship at a time
    if action == 'approve' and application.scholarship.funding_type == 'public':
        held_public = (ScholarshipApplication.query
                       .join(Scholarship, ScholarshipApplication.scholarship_id == Scholarship.id)
                       .filter(
                           ScholarshipApplication.applicant_id == application.applicant_id,
                           ScholarshipApplication.status == ApplicationStatus.APPROVED,
                           Scholarship.funding_type == 'public',
                           ScholarshipApplication.id != application.id,
                       ).first())
        if held_public:
            flash(f'Cannot approve: {application.applicant.get_full_name()} already holds the '
                  f'public scholarship "{held_public.scholarship.title}". Only one public '
                  'scholarship is allowed per student.', 'error')
            return redirect(url_for('staff.review_applications'))

    application.status      = new_status
    application.reviewed_by = session['user_id']
    application.reviewed_at = datetime.utcnow()
    application.review_notes = notes
    application.final_decision_date = datetime.utcnow() if action in ('approve', 'reject') else None

    if action == 'approve':
        application.scholar_status = 'active'
        application.approved_at   = datetime.utcnow()
        application.is_active     = True

        # Auto-assign to batch
        from app.services.batch_service import auto_assign_to_batch
        batch = auto_assign_to_batch(application)
        batch_msg = f' → Assigned to {batch.batch_name}.' if batch else ''
    else:
        batch_msg = ''

    db.session.commit()

    applicant = application.applicant
    notification_service.send_application_status_update(
        applicant.email, applicant.phone_number or '',
        applicant.id, application.scholarship.title, new_status.value, notes,
    )
    from app.services.audit_service import log_action
    log_action(
        f'application.{action}',
        f'Application #{app_id} ({application.scholarship.title}) for '
        f'{applicant.get_full_name()} marked as {new_status.value.replace("_"," ")}.'
        + (f' Notes: {notes}' if notes else ''),
        category='application', target_type='application', target_id=app_id,
    )
    flash(f'Application #{app_id} marked as {new_status.value.replace("_"," ")}.{batch_msg}', 'success')
    return redirect(url_for('staff.review_applications'))


@staff_bp.route('/applications/batch', methods=['POST'])
@role_required('staff')
def batch_review():
    app_ids = request.form.getlist('app_ids')
    action  = request.form.get('action')
    notes   = request.form.get('review_notes', 'Batch processed')
    status_map = {'approve': ApplicationStatus.APPROVED, 'reject': ApplicationStatus.REJECTED}
    new_status = status_map.get(action)
    if not new_status or not app_ids:
        flash('Invalid batch action or no applications selected.', 'error')
        return redirect(url_for('staff.review_applications'))
    processed = 0
    approved_apps = []
    skipped_public = 0
    for app_id in app_ids:
        app = ScholarshipApplication.query.get(int(app_id))
        if app:
            # Guard: skip approving a public scholarship for a student who already holds one
            if (action == 'approve' and app.scholarship.funding_type == 'public'):
                held_public = (ScholarshipApplication.query
                               .join(Scholarship, ScholarshipApplication.scholarship_id == Scholarship.id)
                               .filter(
                                   ScholarshipApplication.applicant_id == app.applicant_id,
                                   ScholarshipApplication.status == ApplicationStatus.APPROVED,
                                   Scholarship.funding_type == 'public',
                                   ScholarshipApplication.id != app.id,
                               ).first())
                if held_public:
                    skipped_public += 1
                    continue
            app.status = new_status
            app.reviewed_by = session['user_id']
            app.reviewed_at = datetime.utcnow()
            app.review_notes = notes
            app.final_decision_date = datetime.utcnow()
            if action == 'approve':
                app.scholar_status = 'active'
                app.approved_at    = datetime.utcnow()
                app.is_active      = True
                approved_apps.append(app)
            processed += 1

    # Auto-assign approved applications to batches
    batch_info = ''
    if approved_apps:
        from app.services.batch_service import auto_assign_multiple
        results = auto_assign_multiple(approved_apps)
        if results:
            batch_info = ' Batches: ' + ', '.join(f'{k} → {v}' for k, v in results.items())

    db.session.commit()

    # Notify each student of their status change (with notes as reason)
    for app_id_str in app_ids:
        try:
            app = ScholarshipApplication.query.get(int(app_id_str))
            if app:
                notification_service.send_application_status_update(
                    app.applicant.email,
                    app.applicant.phone_number or '',
                    app.applicant.id,
                    app.scholarship.title,
                    new_status.value,
                    notes if notes != 'Batch processed' else None,
                )
        except Exception:
            pass

    from app.services.audit_service import log_action
    log_action('application.batch_' + action,
               f'Staff {session.get("username")} batch-{action}d {processed} application(s).',
               category='application')
    flash(f'{processed} application(s) {new_status.value.replace("_"," ")}.{batch_info}'
          + (f' {skipped_public} skipped — student already holds a public scholarship.' if skipped_public else ''),
          'success' if not skipped_public else 'warning')
    return redirect(url_for('staff.review_applications'))


# ── Monitoring & Tracking ─────────────────────────────────────────────────────

@staff_bp.route('/monitoring')
@role_required('staff')
def monitoring():
    """Scholar performance monitoring dashboard."""
    status_filter = request.args.get('scholar_status', '')
    course_filter = request.args.get('course', '')

    # All approved scholars
    query = ScholarshipApplication.query.filter(
        ScholarshipApplication.status == ApplicationStatus.APPROVED
    ).join(User, ScholarshipApplication.applicant_id == User.id)

    if status_filter:
        query = query.filter(ScholarshipApplication.scholar_status == status_filter)
    if course_filter:
        query = query.filter(User.course.ilike(f'%{course_filter}%'))

    scholars = query.order_by(ScholarshipApplication.approved_at.desc()).all()

    # Summary stats
    all_approved = ScholarshipApplication.query.filter_by(status=ApplicationStatus.APPROVED).all()
    stats = {
        'total':       len(all_approved),
        'active':      sum(1 for a in all_approved if a.scholar_status == 'active'),
        'at_risk':     sum(1 for a in all_approved if a.scholar_status == 'at_risk'),
        'probation':   sum(1 for a in all_approved if a.scholar_status == 'probation'),
        'termination': sum(1 for a in all_approved if a.scholar_status == 'termination_warning'),
    }

    # Renewal alerts: approved scholars whose scholarship deadline is within 30 days
    renewal_alerts = []
    for app in all_approved:
        if app.approved_at:
            renewal_due = app.approved_at + timedelta(days=365)
            days_left = (renewal_due - datetime.utcnow()).days
            if 0 <= days_left <= 30:
                renewal_alerts.append({'app': app, 'days_left': days_left, 'due': renewal_due})
    renewal_alerts.sort(key=lambda x: x['days_left'])

    courses = sorted({u.course for u in User.query.filter(
        User.user_type == 'student', User.course.isnot(None)).all() if u.course})

    # M&E form submissions — latest per approved application
    from app.models import MonitoringSubmission
    me_forms = {}
    for s in MonitoringSubmission.query.order_by(MonitoringSubmission.uploaded_at.desc()).all():
        if s.application_id not in me_forms:
            me_forms[s.application_id] = s

    return render_template(
        'staff/monitoring.html',
        scholars=scholars, stats=stats,
        renewal_alerts=renewal_alerts,
        courses=courses,
        status_filter=status_filter,
        course_filter=course_filter,
        me_forms=me_forms,
    )


@staff_bp.route('/monitoring/<int:app_id>/update-status', methods=['POST'])
@role_required('staff')
def update_scholar_status(app_id):
    """Manually update a scholar's performance status."""
    app = ScholarshipApplication.query.get_or_404(app_id)
    new_status = request.form.get('scholar_status', 'active')
    notes      = request.form.get('notes', '').strip()

    valid_statuses = ('active', 'at_risk', 'probation', 'termination_warning')

    if new_status not in valid_statuses:
        flash('Invalid status value.', 'error')
        return redirect(url_for('staff.monitoring'))

    app.scholar_status    = new_status
    app.status_updated_at = datetime.utcnow()
    if notes:
        app.review_notes = (app.review_notes or '') + f'\n[{datetime.utcnow().strftime("%Y-%m-%d")}] {notes}'

    # Send alert notification to student if at-risk or worse
    if new_status in ('at_risk', 'probation', 'termination_warning'):
        student = app.applicant
        label_map = {
            'at_risk':             'At Risk',
            'probation':           'On Probation',
            'termination_warning': 'Termination Warning',
        }
        notification_service.create_in_app_notification(
            student.id,
            f'Scholarship Status Update: {label_map[new_status]}',
            f'Your scholar status for {app.scholarship.title} has been updated to '
            f'{label_map[new_status]}. Please contact the scholarship office.',
            'performance',
        )
        notification_service.send_email(
            student.email,
            f'LSPU ScholarHub — Scholar Status: {label_map[new_status]}',
            f'<h2>⚠️ Scholar Status Update</h2>'
            f'<p>Dear <strong>{student.get_full_name()}</strong>,</p>'
            f'<p>Your scholar status for <strong>{app.scholarship.title}</strong> '
            f'has been updated to <strong>{label_map[new_status]}</strong>.</p>'
            f'<p>Current GWA: <strong>{student.gwa or "Not recorded"}</strong></p>'
            f'{"<p>Note: " + notes + "</p>" if notes else ""}'
            f'<p>Please contact the scholarship office immediately.</p>'
            f'<p>Best regards,<br><strong>LSPU Scholarship Office</strong></p>',
        )

    db.session.commit()
    flash(f'Scholar status updated to {new_status}.', 'success')
    return redirect(url_for('staff.monitoring'))


@staff_bp.route('/monitoring/<int:app_id>/update-gwa', methods=['POST'])
@role_required('staff')
def update_scholar_gwa(app_id):
    """Update a scholar's GWA and auto-update their performance status."""
    app = ScholarshipApplication.query.get_or_404(app_id)
    try:
        gwa = float(request.form.get('gwa', '').strip())
        if not (1.0 <= gwa <= 5.0):
            raise ValueError
    except ValueError:
        flash('GWA must be between 1.00 and 5.00.', 'error')
        return redirect(url_for('staff.monitoring'))

    student = app.applicant
    student.gwa = round(gwa, 2)

    # Auto-determine scholar status from GWA
    if gwa >= 4.00:
        new_status = 'termination_warning'
        new_tag    = 'inactive'
    elif gwa > 3.75:
        new_status = 'probation'
        new_tag    = 'probation'
    elif gwa > 3.00:
        new_status = 'at_risk'
    else:
        new_status = 'active'

    app.scholar_status    = new_status
    app.status_updated_at = datetime.utcnow()
    db.session.commit()

    # Send alert if at-risk or worse
    from app.services.performance_service import performance_service
    alerts = performance_service._check_performance_alerts(student.id, gwa)
    if alerts:
        performance_service._send_performance_notifications(student, app, alerts, gwa)

    flash(f'GWA updated to {gwa} for {student.get_full_name()}. Status: {new_status}.', 'success')
    return redirect(url_for('staff.monitoring'))


@staff_bp.route('/monitoring/<int:app_id>/send-renewal-reminder', methods=['POST'])
@role_required('staff')
def send_renewal_reminder(app_id):
    """Send a renewal reminder to a scholar."""
    app = ScholarshipApplication.query.get_or_404(app_id)
    student = app.applicant
    if app.approved_at:
        renewal_due = app.approved_at + timedelta(days=365)
        days_left   = (renewal_due - datetime.utcnow()).days
    else:
        days_left   = 0
        renewal_due = datetime.utcnow()

    notification_service.send_email(
        student.email,
        'LSPU ScholarHub — Scholarship Renewal Reminder',
        f'<h2>📋 Scholarship Renewal Reminder</h2>'
        f'<p>Dear <strong>{student.get_full_name()}</strong>,</p>'
        f'<p>Your scholarship <strong>{app.scholarship.title}</strong> is due for renewal.</p>'
        f'<p><strong>Renewal Due:</strong> {renewal_due.strftime("%B %d, %Y")}</p>'
        f'<p><strong>Days Remaining:</strong> {max(0, days_left)} days</p>'
        f'<p>Please visit the scholarship office or log in to ScholarHub to submit your renewal documents.</p>'
        f'<p>Best regards,<br><strong>LSPU Scholarship Office</strong></p>',
    )
    notification_service.create_in_app_notification(
        student.id,
        'Scholarship Renewal Reminder',
        f'Your scholarship {app.scholarship.title} renewal is due in {max(0, days_left)} days.',
        'deadline',
    )
    app.renewal_notified_at = datetime.utcnow()
    db.session.commit()
    flash(f'Renewal reminder sent to {student.get_full_name()}.', 'success')
    return redirect(url_for('staff.monitoring'))


# ── Students ──────────────────────────────────────────────────────────────────

@staff_bp.route('/students')
@role_required('staff')
def students():
    """Redirect to the main student directory."""
    return redirect(url_for('staff.student_directory'))


@staff_bp.route('/students/directory')
@role_required('staff')
def student_directory():
    q        = request.args.get('q', '').strip()
    year     = request.args.get('year', '')
    course   = request.args.get('course', '')
    gender   = request.args.get('gender', '')
    sort     = request.args.get('sort', 'name')
    gwa_flag = request.args.get('gwa_flag', '')

    query = User.query.filter_by(user_type='student')
    if q:
        query = query.filter(db.or_(
            User.first_name.ilike(f'%{q}%'), User.last_name.ilike(f'%{q}%'),
            User.student_id.ilike(f'%{q}%'),
        ))
    if year:
        query = query.filter_by(year_level=year)
    if course:
        query = query.filter(User.course.ilike(f'%{course}%'))
    if gender:
        query = query.filter_by(gender=gender)
    if gwa_flag == 'at_risk':
        query = query.filter(User.gwa.isnot(None), User.gwa > GWA_THRESHOLD)

    if sort == 'gwa_asc':
        query = query.order_by(db.case((User.gwa.is_(None), 1), else_=0), User.gwa.asc())
    elif sort == 'gwa_desc':
        query = query.order_by(db.case((User.gwa.is_(None), 1), else_=0), User.gwa.desc())
    else:
        query = query.order_by(User.last_name.asc())

    page = request.args.get('page', 1, type=int)
    students = query.paginate(page=page, per_page=20, error_out=False)
    all_s    = User.query.filter_by(user_type='student').all()
    with_gwa = [s for s in all_s if s.gwa is not None]
    at_risk  = [s for s in with_gwa if s.gwa > GWA_THRESHOLD]
    avg_gwa  = round(sum(s.gwa for s in with_gwa) / len(with_gwa), 2) if with_gwa else None
    courses  = sorted({s.course for s in all_s if s.course})

    return render_template(
        'staff/student_directory.html',
        students=students, q=q, year=year, course=course, gender=gender, sort=sort, gwa_flag=gwa_flag,
        GWA_THRESHOLD=GWA_THRESHOLD,
        total_students=len(all_s), with_gwa_count=len(with_gwa),
        at_risk_count=len(at_risk), avg_gwa=avg_gwa, courses=courses,
    )


@staff_bp.route('/students/<int:uid>')
@role_required('staff')
def student_profile(uid):
    student = User.query.get_or_404(uid)
    if student.user_type != 'student':
        flash('User is not a student.', 'error')
        return redirect(url_for('staff.student_directory'))
    return render_template('staff/student_profile.html', student=student)


# ── Student document verification ─────────────────────────────────────────────

@staff_bp.route('/documents/<int:doc_id>/view')
@role_required('staff')
def view_student_document(doc_id):
    """Render a viewer page for a student document — redirects to raw proxy for Cloudinary files."""
    import os
    from flask import current_app, redirect as _redir
    from app.models.document import Document
    doc = Document.query.get_or_404(doc_id)

    # If stored on Cloudinary, go straight to the raw proxy route
    if doc.cloudinary_public_id or (doc.file_path and (doc.file_path.startswith('http://') or doc.file_path.startswith('https://'))):
        return redirect(url_for('staff.serve_student_document_raw', doc_id=doc.id))

    file_path = doc.file_path
    if not os.path.isabs(file_path):
        file_path = os.path.join(current_app.root_path, '..', file_path)
    if not os.path.exists(os.path.normpath(file_path)):
        flash('File not found.', 'error')
        return redirect(url_for('staff.student_profile', uid=doc.user_id))
    return render_template('shared/document_viewer.html',
                           doc=doc,
                           raw_url=url_for('staff.serve_student_document_raw', doc_id=doc.id),
                           back_url=url_for('staff.student_profile', uid=doc.user_id))


@staff_bp.route('/documents/<int:doc_id>/raw')
@role_required('staff')
def serve_student_document_raw(doc_id):
    """Serve the raw file inline — proxies Cloudinary files through Flask."""
    import os
    from flask import send_file as _sf, current_app, Response
    from app.models.document import Document
    doc = Document.query.get_or_404(doc_id)

    mime_map = {
        'pdf':  'application/pdf',
        'jpg':  'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
        'doc':  'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }
    mime = mime_map.get((doc.file_type or '').lower(), 'application/octet-stream')
    force_download = request.args.get('dl') == '1'
    disposition    = 'attachment' if force_download else 'inline'

    # If stored on Cloudinary — fetch via signed URL and stream through Flask
    if doc.cloudinary_public_id:
        try:
            import urllib.request as _ur
            fetch_url = doc.cloudinary_url
            if not fetch_url:
                from app.services.storage_service import get_signed_url
                res_type  = 'image' if (doc.file_type or '').lower() in ('jpg','jpeg','png') else 'raw'
                fetch_url = get_signed_url(doc.cloudinary_public_id, resource_type=res_type)
            if not fetch_url:
                flash('File URL not available.', 'error')
                return redirect(url_for('staff.student_profile', uid=doc.user_id))
            req = _ur.Request(fetch_url)
            req.add_header('User-Agent', 'LSPU-ScholarHub/1.0')
            with _ur.urlopen(req, timeout=30) as resp:
                file_data = resp.read()
            return Response(
                file_data,
                mimetype=mime,
                headers={
                    'Content-Disposition': f'{disposition}; filename="{doc.original_filename}"',
                    'Content-Length': str(len(file_data)),
                }
            )
        except Exception as e:
            flash(f'Could not load file from cloud storage: {e}', 'error')
            return redirect(url_for('staff.student_profile', uid=doc.user_id))

    # Local file fallback
    path = doc.file_path
    if not os.path.isabs(path):
        path = os.path.join(current_app.root_path, '..', path)
    path = os.path.normpath(path)
    if not os.path.exists(path):
        flash('File not found on server.', 'error')
        return redirect(url_for('staff.student_profile', uid=doc.user_id))
    return _sf(path, mimetype=mime, as_attachment=force_download,
               download_name=doc.original_filename)


@staff_bp.route('/documents/<int:doc_id>/verify', methods=['POST'])
@role_required('staff')
def verify_student_document(doc_id):
    from app.models.document import Document
    doc = Document.query.get_or_404(doc_id)
    doc.is_verified = True
    db.session.commit()
    flash(f'Document "{doc.original_filename}" marked as verified.', 'success')
    return redirect(url_for('staff.student_profile', uid=doc.user_id))


@staff_bp.route('/documents/<int:doc_id>/unverify', methods=['POST'])
@role_required('staff')
def unverify_student_document(doc_id):
    from app.models.document import Document
    doc = Document.query.get_or_404(doc_id)
    doc.is_verified = False
    db.session.commit()
    flash(f'Document "{doc.original_filename}" marked as pending.', 'info')
    return redirect(url_for('staff.student_profile', uid=doc.user_id))


@staff_bp.route('/documents/<int:doc_id>/ctc-override/<int:value>', methods=['POST'])
@role_required('staff')
def override_ctc(doc_id, value):
    """Manually override the AI CTC detection result (1=detected, 0=not detected)."""
    from app.models.document import Document
    doc = Document.query.get_or_404(doc_id)
    doc.ctc_detected = bool(value)
    db.session.commit()
    status = 'present' if value else 'absent'
    flash(f'CTC stamp marked as {status} for "{doc.original_filename}".', 'success')
    app_id = doc.application_id
    if app_id:
        return redirect(url_for('staff.review_applications') + f'#app{app_id}')
    return redirect(url_for('staff.student_profile', uid=doc.user_id))


@staff_bp.route('/students/<int:uid>/update-gwa', methods=['POST'])
@role_required('staff')
def update_gwa(uid):
    student = User.query.get_or_404(uid)
    try:
        gwa_val = float(request.form.get('gwa', '').strip())
        if not (1.0 <= gwa_val <= 5.0):
            raise ValueError
        student.gwa = round(gwa_val, 2)
        # Save units_enrolled if provided
        units_str = request.form.get('units_enrolled', '').strip()
        if units_str:
            try:
                student.units_enrolled = int(units_str)
            except ValueError:
                pass
        db.session.commit()
        from app.services.audit_service import log_action
        from app.models.gwa_history import GwaHistory
        semester    = request.form.get('semester', '1st Semester')
        school_year = request.form.get('school_year', '')
        if not school_year:
            from datetime import datetime as _dt
            y = _dt.utcnow().year
            school_year = f'{y}-{y+1}'
        history = GwaHistory(
            student_id=uid, gwa=student.gwa,
            semester=semester, school_year=school_year,
            recorded_by=session['user_id'],
            notes=request.form.get('gwa_notes', ''),
        )
        db.session.add(history)
        db.session.commit()
        log_action('gwa.update', f'GWA updated to {student.gwa} for {student.get_full_name()} ({student.student_id}).',
                   category='gwa', target_type='user', target_id=uid)
        flash(f'GWA updated to {student.gwa} for {student.get_full_name()}.', 'success')
    except ValueError:
        flash('Invalid GWA. Enter a number between 1.0 and 5.0.', 'error')
    return redirect(url_for('staff.student_profile', uid=uid))


@staff_bp.route('/students/<int:uid>/document/<doc_type>')
@role_required('staff')
def view_reg_document(uid, doc_type):
    import os
    from flask import send_file as _send_file, current_app, Response
    student   = User.query.get_or_404(uid)
    file_path = student.cor_file_path if doc_type == 'cor' else student.grades_file_path

    if not file_path:
        flash('No document uploaded yet. Use the Replace button to upload one.', 'warning')
        return redirect(url_for('staff.student_profile', uid=uid))

    ext = file_path.rsplit('.', 1)[-1].lower() if '.' in file_path else 'pdf'
    mime_map = {'pdf':'application/pdf','jpg':'image/jpeg','jpeg':'image/jpeg','png':'image/png'}
    mime  = mime_map.get(ext, 'application/pdf')
    label = 'COR' if doc_type == 'cor' else 'Grades'
    fname = f"{student.student_id}_{label}.{ext}"

    # Cloudinary URL — proxy through Flask to avoid 401
    if file_path.startswith('http://') or file_path.startswith('https://'):
        try:
            import urllib.request as _ur
            # Detect correct resource type for signed URL
            is_image = ext in ('jpg', 'jpeg', 'png') or '/image/upload/' in file_path
            fetch_url = file_path
            cid = student.cor_cloudinary_id if doc_type == 'cor' else student.grades_cloudinary_id
            if cid:
                from app.services.storage_service import get_signed_url
                signed = get_signed_url(cid, resource_type='image' if is_image else 'raw')
                if signed:
                    fetch_url = signed
            req = _ur.Request(fetch_url)
            req.add_header('User-Agent', 'LSPU-ScholarHub/1.0')
            with _ur.urlopen(req, timeout=30) as resp:
                file_data = resp.read()
            # Use correct mime for images
            if is_image and mime == 'application/pdf':
                mime = 'image/jpeg' if ext in ('jpg','jpeg') else 'image/png'
            return Response(
                file_data,
                mimetype=mime,
                headers={
                    'Content-Disposition': f'inline; filename="{fname}"',
                    'Content-Length': str(len(file_data)),
                }
            )
        except Exception as e:
            flash(f'Could not load file: {e}', 'error')
            return redirect(url_for('staff.student_profile', uid=uid))

    # Local file fallback
    if not os.path.isabs(file_path):
        file_path = os.path.join(current_app.root_path, '..', file_path)
    file_path = os.path.normpath(file_path)
    if not os.path.exists(file_path):
        flash(f'{"COR" if doc_type == "cor" else "Copy of Grades"} file was not found. '
              f'Please use the Replace button to re-upload it.', 'warning')
        return redirect(url_for('staff.student_profile', uid=uid))
    return _send_file(file_path, mimetype=mime, as_attachment=False, download_name=fname)


# ── Reports ───────────────────────────────────────────────────────────────────

@staff_bp.route('/reports')
@role_required('staff')
def reports():
    import json
    total_apps    = ScholarshipApplication.query.count()
    approved      = ScholarshipApplication.query.filter_by(status=ApplicationStatus.APPROVED).count()
    rejected      = ScholarshipApplication.query.filter_by(status=ApplicationStatus.REJECTED).count()
    pending       = ScholarshipApplication.query.filter(
        ScholarshipApplication.status.in_([ApplicationStatus.PENDING, ApplicationStatus.UNDER_REVIEW])
    ).count()
    approval_rate = round(approved / total_apps * 100, 1) if total_apps else 0
    scholarships  = Scholarship.query.all()
    scholarship_stats = []
    for s in scholarships:
        apps = ScholarshipApplication.query.filter_by(scholarship_id=s.id).all()
        scholarship_stats.append({
            'scholarship': s,
            'total':    len(apps),
            'approved': sum(1 for a in apps if a.status == ApplicationStatus.APPROVED),
            'rejected': sum(1 for a in apps if a.status == ApplicationStatus.REJECTED),
            'pending':  sum(1 for a in apps if a.status in (ApplicationStatus.PENDING, ApplicationStatus.UNDER_REVIEW)),
        })

    # GWA distribution
    students_with_gwa = User.query.filter(User.user_type == 'student', User.gwa.isnot(None)).all()
    gwa_buckets = {
        'Excellent (≤1.25)': 0, 'Very Satisfactory (≤1.75)': 0,
        'Satisfactory (≤2.25)': 0, 'Fairly Satisfactory (≤2.75)': 0,
        'Passed (≤3.00)': 0, 'Conditional Failure (≤3.99)': 0, 'Failed (4.00+)': 0,
    }
    for s in students_with_gwa:
        g = s.gwa
        if g <= 1.25:   gwa_buckets['Excellent (≤1.25)'] += 1
        elif g <= 1.75: gwa_buckets['Very Satisfactory (≤1.75)'] += 1
        elif g <= 2.25: gwa_buckets['Satisfactory (≤2.25)'] += 1
        elif g <= 2.75: gwa_buckets['Fairly Satisfactory (≤2.75)'] += 1
        elif g <= 3.00: gwa_buckets['Passed (≤3.00)'] += 1
        elif g < 4.00:  gwa_buckets['Conditional Failure (≤3.99)'] += 1
        else:           gwa_buckets['Failed (4.00+)'] += 1

    gwa_labels   = json.dumps(list(gwa_buckets.keys()))
    gwa_data     = json.dumps(list(gwa_buckets.values()))
    sch_labels   = json.dumps([s['scholarship'].title[:25] for s in scholarship_stats])
    sch_approved = json.dumps([s['approved'] for s in scholarship_stats])
    sch_pending  = json.dumps([s['pending']  for s in scholarship_stats])
    sch_rejected = json.dumps([s['rejected'] for s in scholarship_stats])
    all_approved = ScholarshipApplication.query.filter_by(status=ApplicationStatus.APPROVED).all()
    scholar_status_data = json.dumps([
        sum(1 for a in all_approved if a.scholar_status == 'active'),
        sum(1 for a in all_approved if a.scholar_status == 'at_risk'),
        sum(1 for a in all_approved if a.scholar_status == 'probation'),
        sum(1 for a in all_approved if a.scholar_status == 'termination_warning'),
    ])

    return render_template('staff/reports.html',
                           total_apps=total_apps, approved=approved,
                           rejected=rejected, pending=pending, approval_rate=approval_rate,
                           scholarship_stats=scholarship_stats,
                           gwa_labels=gwa_labels, gwa_data=gwa_data,
                           sch_labels=sch_labels, sch_approved=sch_approved,
                           sch_pending=sch_pending, sch_rejected=sch_rejected,
                           scholar_status_data=scholar_status_data)


@staff_bp.route('/reports/export')
@role_required('staff')
def export_report():
    from app.services.export_service import generate_export
    report_type = request.args.get('type', 'applications')
    fmt         = request.args.get('format', 'pdf')
    filters     = {k: v for k, v in {
        'status': request.args.get('status', ''),
        'scholarship_id': request.args.get('scholarship_id', ''),
        'course': request.args.get('course', ''),
    }.items() if v}
    try:
        buf, mime, filename = generate_export(report_type, fmt, filters)
        return send_file(buf, mimetype=mime, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'Export failed: {e}', 'error')
        return redirect(url_for('staff.reports'))


# ── Notifications ─────────────────────────────────────────────────────────────

@staff_bp.route('/notifications')
@role_required('staff')
def notifications():
    students     = User.query.filter_by(user_type='student', is_active=True).order_by(User.last_name).all()
    courses      = sorted({s.course for s in students if s.course})
    year_levels  = ['1st Year', '2nd Year', '3rd Year', '4th Year']
    scholarships = Scholarship.query.order_by(Scholarship.title).all()
    recent       = Notification.query.order_by(Notification.sent_at.desc()).limit(20).all()
    return render_template('staff/notifications.html', students=students, recent=recent,
                           courses=courses, year_levels=year_levels, scholarships=scholarships)


@staff_bp.route('/notifications/send', methods=['POST'])
@role_required('staff')
def send_notification():
    recipient_type = request.form.get('recipient_type', 'multiple')
    title          = request.form.get('title', '').strip()
    message        = request.form.get('message', '').strip()
    send_email     = request.form.get('send_email') == 'on'
    send_sms       = request.form.get('send_sms') == 'on'

    if not title or not message:
        flash('Title and message are required.', 'error')
        return redirect(url_for('staff.notifications'))

    uids = request.form.getlist('recipient_ids')
    if uids:
        recipients = User.query.filter(User.id.in_([int(u) for u in uids if u.isdigit()])).all()
    else:
        if recipient_type == 'at_risk':
            recipients = User.query.filter_by(user_type='student', is_active=True).filter(
                User.gwa.isnot(None), User.gwa > 3.00).all()
        else:
            recipients = []

    recipients = [u for u in recipients if u]
    sms_sent = 0
    for user in recipients:
        db.session.add(Notification(
            recipient_id=user.id, title=title, message=message,
            notification_type=NotificationType.SYSTEM_ANNOUNCEMENT,
            channel=NotificationChannel.IN_APP,
        ))
        if send_email:
            notification_service.send_email(user.email, title, message)
        if send_sms and user.phone_number:
            result = notification_service.send_sms(user.phone_number, f"{title}: {message}")
            if result.get('success'):
                sms_sent += 1
    db.session.commit()
    msg = f'Notification sent to {len(recipients)} recipient(s).'
    if send_email:
        msg += ' Email queued.'
    if send_sms:
        msg += f' SMS delivered to {sms_sent} verified phone(s).'
    flash(msg, 'success')
    return redirect(url_for('staff.notifications'))


# ── Profile ───────────────────────────────────────────────────────────────────

@staff_bp.route('/profile')
@role_required('staff')
def profile():
    user = User.query.get(session['user_id'])
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('auth.login'))
    return render_template('staff/profile.html', user=user)


@staff_bp.route('/profile/update', methods=['POST'])
@role_required('staff')
def update_profile():
    user = User.query.get(session['user_id'])
    user.first_name   = request.form.get('first_name', user.first_name)
    user.last_name    = request.form.get('last_name', user.last_name)
    user.phone_number = request.form.get('phone_number', user.phone_number)
    new_pw = request.form.get('new_password', '').strip()
    if new_pw:
        current_pw = request.form.get('current_password', '').strip()
        if not current_pw:
            flash('Please enter your current password to set a new one.', 'error')
            return redirect(url_for('staff.profile'))
        if not user.check_password(current_pw):
            flash('Current password is incorrect. Password was not changed.', 'error')
            return redirect(url_for('staff.profile'))
        if len(new_pw) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return redirect(url_for('staff.profile'))
        user.set_password(new_pw)
    db.session.commit()
    from app.services.audit_service import log_action
    pw_note = ' Password was changed.' if new_pw else ''
    log_action('user.profile_update',
               f'Staff {user.username} updated their own profile (name, phone).{pw_note}',
               category='user', target_type='user', target_id=user.id)
    flash('Profile updated.', 'success')
    return redirect(url_for('staff.profile'))


# ── Document helpers ──────────────────────────────────────────────────────────

@staff_bp.route('/document/<int:doc_id>/download')
@role_required('staff')
def download_document(doc_id):
    import os
    from flask import send_file as _send_file, current_app, Response
    from app.models.document import Document
    doc = Document.query.get_or_404(doc_id)

    # Cloudinary proxy
    if doc.cloudinary_public_id or (doc.file_path and (doc.file_path.startswith('http://') or doc.file_path.startswith('https://'))):
        try:
            import urllib.request as _ur
            fetch_url = doc.cloudinary_url or doc.file_path
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
            return redirect(url_for('staff.review_applications'))

    file_path = doc.file_path
    if not os.path.isabs(file_path):
        file_path = os.path.join(current_app.root_path, '..', file_path)
    file_path = os.path.normpath(file_path)
    if not os.path.exists(file_path):
        flash('File not found.', 'error')
        return redirect(url_for('staff.review_applications'))
    return _send_file(file_path, as_attachment=True, download_name=doc.original_filename)


@staff_bp.route('/document/<int:doc_id>/view')
@role_required('staff')
def view_document(doc_id):
    import os
    from flask import send_file as _send_file, current_app, Response
    from app.models.document import Document
    doc = Document.query.get_or_404(doc_id)

    mime_map = {'pdf':'application/pdf','jpg':'image/jpeg','jpeg':'image/jpeg',
                'png':'image/png','doc':'application/msword',
                'docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
    mime = mime_map.get((doc.file_type or '').lower(), 'application/octet-stream')

    # Cloudinary proxy
    if doc.cloudinary_public_id or (doc.file_path and (doc.file_path.startswith('http://') or doc.file_path.startswith('https://'))):
        try:
            import urllib.request as _ur
            fetch_url = doc.cloudinary_url or doc.file_path
            req = _ur.Request(fetch_url)
            req.add_header('User-Agent', 'LSPU-ScholarHub/1.0')
            with _ur.urlopen(req, timeout=30) as resp:
                file_data = resp.read()
            return Response(file_data, mimetype=mime,
                            headers={'Content-Disposition': f'inline; filename="{doc.original_filename}"',
                                     'Content-Length': str(len(file_data))})
        except Exception as e:
            flash(f'Could not load file: {e}', 'error')
            return redirect(url_for('staff.review_applications'))

    file_path = doc.file_path
    if not os.path.isabs(file_path):
        file_path = os.path.join(current_app.root_path, '..', file_path)
    file_path = os.path.normpath(file_path)
    if not os.path.exists(file_path):
        flash('File not found.', 'error')
        return redirect(url_for('staff.review_applications'))
    return _send_file(file_path, mimetype=mime, as_attachment=False,
                      download_name=doc.original_filename)


# ── Bulk Import ───────────────────────────────────────────────────────────────

@staff_bp.route('/import')
@role_required('staff')
def import_page():
    return render_template('staff/import.html')


@staff_bp.route('/import/template')
@role_required('staff')
def download_import_template():
    """Generate and serve a blank Excel import template for staff."""
    import io
    from flask import send_file as _send_file
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = Workbook()
    ws = wb.active
    ws.title = 'Students'
    headers = ['student_id', 'first_name', 'last_name', 'middle_name', 'email',
               'year_level', 'course', 'phone_number', 'gender', 'town', 'province']
    hdr_fill = PatternFill('solid', fgColor='1a3a6b')
    for ci, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=ci, value=h)
        cell.font      = Font(bold=True, color='FFFFFF', name='Calibri')
        cell.fill      = hdr_fill
        cell.alignment = Alignment(horizontal='center')
        ws.column_dimensions[cell.column_letter].width = 24
    ws.append(['0123-1740', 'Juan', 'Dela Cruz', 'Santos', 'juan@student.lspu.edu',
               '3rd Year', 'Bachelor of Science in Information Technology',
               '09123456789', 'Male', 'Santa Cruz', 'Laguna'])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return _send_file(buf,
                      mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                      as_attachment=True,
                      download_name='lspu_scholarhub_import_template.xlsx')


@staff_bp.route('/import/upload', methods=['POST'])
@role_required('staff')
def import_students():
    import io, re
    file = request.files.get('import_file')
    if not file or not file.filename:
        flash('Please select a file.', 'error')
        return redirect(url_for('staff.import_page'))
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ('xlsx', 'xls', 'csv'):
        flash('Only .xlsx, .xls, or .csv files are accepted.', 'error')
        return redirect(url_for('staff.import_page'))
    try:
        import openpyxl, csv as csv_mod
        rows = []
        if ext in ('xlsx', 'xls'):
            wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
            ws = wb.active
            headers = None
            for row in ws.iter_rows(values_only=True):
                if headers is None:
                    headers = [str(c).strip().lower().replace(' ','_') if c else '' for c in row]
                    continue
                rows.append(dict(zip(headers, row)))
        else:
            content = file.read().decode('utf-8-sig')
            reader  = csv_mod.DictReader(io.StringIO(content))
            for row in reader:
                rows.append({k.strip().lower().replace(' ','_'): v for k, v in row.items()})
    except Exception as e:
        flash(f'Could not parse file: {e}', 'error')
        return redirect(url_for('staff.import_page'))
    from app.views.auth import _generate_password, _send_credentials_email
    inserted, skipped, errors = 0, 0, []
    for i, row in enumerate(rows, start=2):
        sid         = str(row.get('student_id','') or '').strip()
        first_name  = str(row.get('first_name','') or '').strip().title()
        last_name   = str(row.get('last_name','') or '').strip().title()
        middle_name = str(row.get('middle_name','') or '').strip().title() or None
        email       = str(row.get('email','') or '').strip().lower()
        year_level  = str(row.get('year_level','') or '').strip()
        course      = str(row.get('course','') or '').strip() or None
        phone       = str(row.get('phone_number','') or '').strip() or None
        gender      = str(row.get('gender','') or '').strip().title() or None
        town        = str(row.get('town','') or '').strip() or None
        province    = str(row.get('province','') or '').strip() or None

        # Validate gender if provided
        if gender and gender not in ('Male', 'Female'):
            gender = None

        if not all([sid, first_name, last_name, email, year_level]):
            errors.append(f'Row {i}: Missing required field(s).'); skipped += 1; continue
        if User.query.filter_by(student_id=sid).first():
            errors.append(f'Row {i}: Student ID "{sid}" exists.'); skipped += 1; continue
        if User.query.filter_by(email=email).first():
            errors.append(f'Row {i}: Email "{email}" exists.'); skipped += 1; continue
        try:
            temp_pw  = _generate_password(10)
            new_user = User(username=sid, email=email,
                            first_name=first_name, last_name=last_name,
                            middle_name=middle_name,
                            student_id=sid, year_level=year_level, course=course,
                            phone_number=phone, gender=gender,
                            town=town, province=province,
                            user_type='student', is_active=True, is_verified=True)
            new_user.set_password(temp_pw)
            db.session.add(new_user)
            db.session.flush()
            _send_credentials_email(new_user, temp_pw)
            inserted += 1
        except Exception as e:
            db.session.rollback(); errors.append(f'Row {i}: {e}'); skipped += 1
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'Commit failed: {e}', 'error')
        return redirect(url_for('staff.import_page'))
    if inserted: flash(f'✓ {inserted} student(s) imported.', 'success')
    if skipped:  flash(f'⚠ {skipped} row(s) skipped.', 'warning')
    return render_template('staff/import.html', import_errors=errors,
                           inserted=inserted, skipped=skipped)


# ── Batch Management (Staff) ──────────────────────────────────────────────────

@staff_bp.route('/batches')
@role_required('staff')
def manage_batches():
    from app.models import AcademicPeriod, ScholarshipBatch
    scholarship_id = request.args.get('scholarship_id', '')
    period_id      = request.args.get('period_id', '')
    current_period = AcademicPeriod.get_current()
    periods        = AcademicPeriod.query.order_by(AcademicPeriod.id.desc()).all()
    scholarships   = Scholarship.query.order_by(Scholarship.title).all()
    query = ScholarshipBatch.query
    if scholarship_id:
        query = query.filter_by(scholarship_id=int(scholarship_id))
    if period_id:
        query = query.filter_by(academic_period_id=int(period_id))
    elif current_period:
        query = query.filter_by(academic_period_id=current_period.id)
    batches = query.order_by(ScholarshipBatch.scholarship_id, ScholarshipBatch.batch_number).all()
    return render_template('staff/batches.html', batches=batches, scholarships=scholarships,
                           periods=periods, current_period=current_period,
                           scholarship_id=scholarship_id, period_id=period_id)


@staff_bp.route('/batches/create', methods=['POST'])
@role_required('staff')
def create_batch():
    from app.models import ScholarshipBatch
    import re as _re
    scholarship_id = request.form.get('scholarship_id', type=int)
    period_id      = request.form.get('academic_period_id', type=int)
    batch_name     = request.form.get('batch_name', '').strip()
    amount         = request.form.get('amount_per_scholar', '').strip()
    if not scholarship_id or not period_id:
        flash('Scholarship and academic period are required.', 'error')
        return redirect(url_for('staff.manage_batches'))
    if not batch_name:
        batch_name, batch_number = ScholarshipBatch.suggest_next_batch_name(scholarship_id, period_id)
    else:
        nums = _re.findall(r'[\d.]+', batch_name)
        batch_number = float(nums[-1]) if nums else 1.0
    try:
        batch = ScholarshipBatch(scholarship_id=scholarship_id, academic_period_id=period_id,
                                 batch_name=batch_name, batch_number=batch_number,
                                 amount_per_scholar=max(0, float(amount)) if amount else None,
                                 created_by=session['user_id'])
        db.session.add(batch); db.session.commit()
        from app.services.audit_service import log_action
        log_action('batch.create', f'Staff {session.get("username")} created "{batch_name}".',
                   category='scholarship', target_type='scholarship', target_id=scholarship_id)
        flash(f'Batch "{batch_name}" created.', 'success')
    except Exception as e:
        db.session.rollback(); flash(f'Error: {e}', 'error')
    return redirect(url_for('staff.manage_batches', scholarship_id=scholarship_id))


@staff_bp.route('/batches/<int:batch_id>/edit', methods=['POST'])
@role_required('staff')
def edit_batch(batch_id):
    from app.models import ScholarshipBatch
    batch = ScholarshipBatch.query.get_or_404(batch_id)
    batch.batch_name = request.form.get('batch_name', batch.batch_name).strip()
    amount = request.form.get('amount_per_scholar', '').strip()
    if amount: batch.amount_per_scholar = max(0, float(amount))
    status = request.form.get('status', '')
    if status in ('open','closed','finalized'): batch.status = status
    batch.notes = request.form.get('notes', batch.notes)
    batch.recalculate_totals()
    db.session.commit()
    flash(f'Batch "{batch.batch_name}" updated.', 'success')
    return redirect(url_for('staff.manage_batches', scholarship_id=batch.scholarship_id))


@staff_bp.route('/batches/<int:batch_id>/assign', methods=['POST'])
@role_required('staff')
def assign_to_batch(batch_id):
    from app.models import ScholarshipBatch
    batch   = ScholarshipBatch.query.get_or_404(batch_id)
    app_ids = request.form.getlist('app_ids')
    if not app_ids:
        flash('No applications selected.', 'error')
        return redirect(url_for('staff.manage_batches', scholarship_id=batch.scholarship_id))
    assigned = 0
    for app_id in app_ids:
        app = ScholarshipApplication.query.get(int(app_id))
        if app and app.status == ApplicationStatus.APPROVED:
            app.batch_id = batch_id
            app.amount_received = batch.amount_per_scholar
            assigned += 1
    batch.recalculate_totals()
    db.session.commit()
    from app.services.audit_service import log_action
    log_action('batch.assign', f'Staff {session.get("username")} assigned {assigned} scholar(s) to "{batch.batch_name}".',
               category='scholarship', target_type='scholarship', target_id=batch.scholarship_id)
    flash(f'{assigned} scholar(s) assigned to "{batch.batch_name}".', 'success')
    return redirect(url_for('staff.manage_batches', scholarship_id=batch.scholarship_id))


@staff_bp.route('/batches/<int:batch_id>/delete', methods=['POST'])
@role_required('staff')
def delete_batch(batch_id):
    from app.models import ScholarshipBatch
    batch = ScholarshipBatch.query.get_or_404(batch_id)
    name, sid = batch.batch_name, batch.scholarship_id
    for app in batch.applications:
        app.batch_id = None; app.seq_number = None
    db.session.delete(batch); db.session.commit()
    flash(f'Batch "{name}" deleted.', 'success')
    return redirect(url_for('staff.manage_batches', scholarship_id=sid))


@staff_bp.route('/batches/suggest-name')
@role_required('staff')
def suggest_batch_name():
    from app.models import ScholarshipBatch
    scholarship_id = request.args.get('scholarship_id', type=int)
    period_id      = request.args.get('period_id', type=int)
    if not scholarship_id or not period_id:
        return jsonify({'name': 'Batch 1', 'number': 1.0})
    name, number = ScholarshipBatch.suggest_next_batch_name(scholarship_id, period_id)
    return jsonify({'name': name, 'number': number})


@staff_bp.route('/batches/<int:batch_id>/export')
@role_required('staff')
def export_batch(batch_id):
    """Export a batch as Excel — same format as admin."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from app.models import ScholarshipBatch
    from flask import send_file as _send_file

    batch = ScholarshipBatch.query.get_or_404(batch_id)
    apps  = [a for a in batch.applications if a.status and a.status.value == 'approved']

    wb = Workbook()
    ws = wb.active
    ws.title = batch.batch_name[:31]

    ws.merge_cells('A1:O1')
    ws['A1'] = 'Republic of the Philippines\nLaguna State Polytechnic University\nSanta Cruz Campus'
    ws['A1'].font = Font(bold=True, size=10)
    ws['A1'].alignment = Alignment(horizontal='center', wrap_text=True)
    ws.row_dimensions[1].height = 40

    ws.merge_cells('A3:O3')
    ws['A3'] = 'SUMMARY OF SCHOLARSHIP AND FINANCIAL ASSISTANCE'
    ws['A3'].font = Font(bold=True, size=11)
    ws['A3'].alignment = Alignment(horizontal='center')

    period_name = batch.academic_period.display_name if batch.academic_period else ''
    ws.merge_cells('A4:O4')
    ws['A4'] = period_name
    ws['A4'].alignment = Alignment(horizontal='center')

    ws.merge_cells('A6:O6')
    ws['A6'] = batch.scholarship.title
    ws['A6'].font = Font(bold=True)

    ws.merge_cells('A7:O7')
    ws['A7'] = batch.batch_name.upper()
    ws['A7'].font = Font(bold=True)

    headers = ['Seq. No.', 'Student ID No.', 'Last Name', 'First Name', 'Middle Name',
               'Program Name', 'Year', 'Total Units Enrolled', 'GWA',
               'Town', 'Province', 'Male', 'Female', 'Amount', 'Remarks']
    hdr_fill = PatternFill('solid', fgColor='1a3a6b')
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'),
                         top=Side(style='thin'), bottom=Side(style='thin'))
    for ci, h in enumerate(headers, start=1):
        cell = ws.cell(row=9, column=ci, value=h)
        cell.font = Font(bold=True, color='FFFFFF', size=9)
        cell.fill = hdr_fill
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = thin_border
    col_widths = [8, 14, 18, 18, 16, 40, 6, 8, 6, 14, 12, 6, 6, 12, 14]
    for ci, w in enumerate(col_widths, start=1):
        ws.column_dimensions[ws.cell(row=9, column=ci).column_letter].width = w

    total_male = total_female = 0
    total_amount = 0
    for seq, app in enumerate(apps, start=1):
        student = app.applicant
        row = seq + 9
        is_male = 1 if student.gender == 'Male' else ''
        is_female = 1 if student.gender == 'Female' else ''
        if student.gender == 'Male': total_male += 1
        if student.gender == 'Female': total_female += 1
        amount = float(app.amount_received or batch.amount_per_scholar or 0)
        total_amount += amount
        data = [seq, student.student_id or '', student.last_name or '', student.first_name or '',
                student.middle_name or '', student.course or '',
                student.year_level.replace(' Year', '') if student.year_level else '',
                student.units_enrolled or '', student.gwa or '',
                student.town or '', student.province or '', is_male, is_female, amount, '']
        for ci, val in enumerate(data, start=1):
            cell = ws.cell(row=row, column=ci, value=val)
            cell.border = thin_border
            cell.font = Font(size=9)

    total_row = len(apps) + 10
    ws.cell(row=total_row, column=1, value='Total').font = Font(bold=True)
    ws.cell(row=total_row, column=12, value=total_male).font = Font(bold=True)
    ws.cell(row=total_row, column=13, value=total_female).font = Font(bold=True)
    ws.cell(row=total_row, column=14, value=total_amount).font = Font(bold=True)
    for ci in range(1, 16):
        ws.cell(row=total_row, column=ci).border = thin_border

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f'{batch.scholarship.title[:20]}_{batch.batch_name}.xlsx'.replace(' ', '_')
    return _send_file(buf, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                      as_attachment=True, download_name=filename)


@staff_bp.route('/batches/<int:batch_id>')
@role_required('staff')
def batch_detail(batch_id):
    """View the list of scholars assigned to a specific batch."""
    from app.models import ScholarshipBatch
    batch = ScholarshipBatch.query.get_or_404(batch_id)
    # Get approved applications in this batch
    applications = [
        a for a in batch.applications
        if a.status and a.status.value == 'approved'
    ]
    # Sort by last name
    applications.sort(key=lambda a: (a.applicant.last_name or '').lower())
    return render_template('staff/batch_detail.html',
                           batch=batch, applications=applications)


# ── Monitoring & Evaluation form submissions ────────────────────────────────

@staff_bp.route('/monitoring/<int:app_id>/me-form')
@role_required('staff')
def view_me_form(app_id):
    """Staff views the scholar's submitted M&E form inline."""
    from app.models import MonitoringSubmission
    from app.services.storage_service import get_signed_url

    subs = (MonitoringSubmission.query
            .filter_by(application_id=app_id)
            .order_by(MonitoringSubmission.uploaded_at.desc()).all())
    if not subs:
        flash('No Monitoring & Evaluation form submitted yet for this scholar.', 'warning')
        return redirect(url_for('staff.monitoring'))
    sub = subs[0]   # latest submission

    if sub.cloudinary_public_id:
        is_image = sub.file_type in ('jpg', 'jpeg', 'png')
        signed = get_signed_url(sub.cloudinary_public_id,
                                resource_type='image' if is_image else 'raw')
        if signed:
            return redirect(signed)
    if sub.local_path and os.path.exists(sub.local_path):
        from flask import send_file
        return send_file(os.path.abspath(sub.local_path), as_attachment=False)
    if sub.file_url and sub.file_url.startswith('http'):
        return redirect(sub.file_url)
    flash('The file could not be found. Please ask the scholar to re-upload.', 'warning')
    return redirect(url_for('staff.monitoring'))

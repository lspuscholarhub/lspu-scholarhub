import os
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, request, flash,
                   redirect, url_for, session, jsonify, send_file, current_app,
                   send_from_directory)
from app import db
from app.models import User, Scholarship, ScholarshipApplication, Notification
from app.models.scholarship import ScholarshipStatus, ApplicationStatus
from app.models.notification import NotificationType, NotificationChannel
from app.services.notification_service import notification_service
from app.utils.decorators import role_required

admin_bp = Blueprint('admin', __name__)


# ── Campus Context (Super Admin) ──────────────────────────────────────

@admin_bp.route('/campus-context/<int:campus_id>')
@role_required('admin', 'staff')
def set_campus_context(campus_id):
    """Set the campus context. campus_id=0 means all allowed campuses."""
    from flask import session as _session
    _me = db.session.get(User, _session.get('user_id'))

    if campus_id == 0:
        _session.pop('campus_context', None)
        _session.pop('campus_context_name', None)
        flash('Showing all campuses.', 'info')
    else:
        from app.models import Campus
        campus = Campus.query.get(campus_id)
        if not campus:
            flash('Invalid campus.', 'error')
            return redirect(url_for('admin.dashboard'))
        # Verify the user is assigned to this campus
        allowed_ids = [c.id for c in _me.assigned_campuses] if _me and _me.assigned_campuses else ([] if _me and not _me.campus_id else [_me.campus_id] if _me else [])
        if _session.get('user_type') == 'super_admin' or campus_id in allowed_ids:
            _session['campus_context'] = campus.id
            _session['campus_context_name'] = campus.name
            flash(f'Switched to {campus.name}.', 'info')
        else:
            flash('You are not assigned to that campus.', 'error')
    return redirect(request.referrer or url_for('admin.dashboard'))


# ── Period Context (all logged-in users) ──────────────────────────────

@admin_bp.route('/period-context/<int:period_id>')
@role_required('admin')
def set_period_context(period_id):
    """Set the viewing period. period_id=0 means current period (default)."""
    from app.models.academic_period import AcademicPeriod
    if period_id == 0:
        session.pop('viewing_period_id', None)
        session.pop('viewing_period_name', None)
        flash('Viewing current period.', 'info')
    else:
        period = AcademicPeriod.query.get(period_id)
        if not period:
            flash('Invalid period.', 'error')
            return redirect(request.referrer or url_for('admin.dashboard'))
        session['viewing_period_id'] = period.id
        session['viewing_period_name'] = period.display_name
        flash(f'Viewing: {period.display_name}', 'info')
    return redirect(request.referrer or url_for('admin.dashboard'))


from app.utils.period_context import get_viewing_period, is_viewing_specific_period


# ── Scholarship campus guard ─────────────────────────────────────────────────

def _scholarship_campus_guard(scholarship):
    """Block campus admins/staff from mutating scholarships outside their campus.
    Super admin (any selector) is always allowed. Returns a redirect response
    when blocked, or None when permitted."""
    if session.get('user_type') == 'super_admin':
        return None
    _me = db.session.get(User, session.get('user_id'))
    my_campus = _me.campus_id if _me else None
    if scholarship.campus_id != my_campus:
        flash('You can only manage scholarship programs for your own campus.', 'error')
        return redirect(url_for('admin.manage_scholarships'))
    return None


# ── Dashboard ─────────────────────────────────────────────────────────────────

@admin_bp.route('/')
@role_required('admin')
def dashboard():
    from app.models import AcademicPeriod, ScholarshipBatch

    # ── Strict campus scoping ──────────────────────────────────────────────
    # Super admin: honor the campus selector (None = all campuses).
    # Campus admin/staff: their assigned campuses (from junction table).
    campus_ctx = None
    my_campus_ids = []  # IDs this user is allowed to see
    if session.get('user_type') == 'super_admin':
        campus_ctx = session.get('campus_context')          # None = all
    else:
        _me = db.session.get(User, session.get('user_id'))
        if _me and _me.assigned_campuses:
            my_campus_ids = [c.id for c in _me.assigned_campuses]
        elif _me:
            my_campus_ids = [_me.campus_id] if _me.campus_id else []
        campus_ctx = my_campus_ids[0] if len(my_campus_ids) == 1 else None

    def _scoped_users(q):
        if campus_ctx:
            return q.filter(User.campus_id == campus_ctx)
        elif my_campus_ids:
            return q.filter(User.campus_id.in_(my_campus_ids))
        return q

    def _scoped_apps(q):
        if campus_ctx:
            return (q.join(User, ScholarshipApplication.applicant_id == User.id)
                     .filter(User.campus_id == campus_ctx))
        elif my_campus_ids:
            return (q.join(User, ScholarshipApplication.applicant_id == User.id)
                     .filter(User.campus_id.in_(my_campus_ids)))
        return q

    def _scoped_sch(q):
        if campus_ctx:
            return q.filter(db.or_(Scholarship.campus_id == campus_ctx,
                                    Scholarship.campus_id.is_(None)))
        elif my_campus_ids:
            return q.filter(db.or_(Scholarship.campus_id.in_(my_campus_ids),
                                    Scholarship.campus_id.is_(None)))
        return q

    # Current academic period (from session switcher or default)
    current_period = get_viewing_period()
    # Only filter by period if user explicitly selected a non-current period
    specific_period = is_viewing_specific_period()
    pid = current_period.id if current_period else None
    # When viewing current period (or no selection), don't filter by period for stats
    effective_pid = pid if specific_period else None

    # Applications — scoped by campus AND period
    _apps_q = _scoped_apps(ScholarshipApplication.query)
    if effective_pid:
        _apps_q = _apps_q.filter(ScholarshipApplication.academic_period_id == effective_pid)
    total_applications  = _apps_q.count()
    pending_review      = _apps_q.filter(
        ScholarshipApplication.status.in_([ApplicationStatus.PENDING,
                                           ApplicationStatus.UNDER_REVIEW])
    ).count()
    approved_count      = _apps_q.filter(ScholarshipApplication.status == ApplicationStatus.APPROVED).count()

    # Student stats — only filter by period when a specific past period is selected
    if specific_period and pid:
        period_student_ids = [r[0] for r in db.session.query(
            ScholarshipApplication.applicant_id
        ).filter(ScholarshipApplication.academic_period_id == pid).distinct().all()]
        if period_student_ids:
            total_students = User.query.filter(User.id.in_(period_student_ids)).count()
            male_students = User.query.filter(User.id.in_(period_student_ids), User.gender == 'Male').count()
            female_students = User.query.filter(User.id.in_(period_student_ids), User.gender == 'Female').count()
            new_users = User.query.filter(User.id.in_(period_student_ids)).count()
            at_risk_count = User.query.filter(
                User.id.in_(period_student_ids), User.gwa.isnot(None), User.gwa > 3.00
            ).count()
            total_users = total_students
        else:
            total_students = 0
            male_students = 0
            female_students = 0
            new_users = 0
            at_risk_count = 0
            total_users = 0
    else:
        total_students = _scoped_users(User.query.filter_by(user_type='student')).count()
        male_students = _scoped_users(User.query.filter_by(user_type='student', gender='Male')).count()
        female_students = _scoped_users(User.query.filter_by(user_type='student', gender='Female')).count()
        new_users = _scoped_users(User.query.filter(
            User.created_at >= datetime.utcnow() - timedelta(days=30)
        )).count()
        at_risk_count = _scoped_users(User.query.filter(
            User.user_type == 'student', User.gwa.isnot(None), User.gwa > 3.00
        )).count()
        total_users = _scoped_users(User.query).count()

    # Active scholarships — scoped by period if set
    _sch_q = Scholarship.query.filter_by(status=ScholarshipStatus.ACTIVE)
    if session.get('user_type') == 'super_admin':
        if campus_ctx:
            _sch_q = _sch_q.filter(db.or_(Scholarship.campus_id == campus_ctx,
                                           Scholarship.campus_id.is_(None)))
    else:
        _me = db.session.get(User, session.get('user_id'))
        if _me:
            _sch_q = _sch_q.filter(Scholarship.campus_id == _me.campus_id)
    active_scholarships = _sch_q.count()

    # Fund summary — scoped by campus AND period
    _funds_q = db.session.query(
        db.func.coalesce(db.func.sum(ScholarshipBatch.total_amount), 0)
    )
    if campus_ctx:
        _funds_q = _funds_q.filter(ScholarshipBatch.campus_id == campus_ctx)
    if effective_pid:
        _funds_q = _funds_q.filter(ScholarshipBatch.academic_period_id == effective_pid)
    total_funds = _funds_q.scalar() or 0

    # Recent activity: last 5 applications — scoped by campus AND period
    recent_apps_q = (ScholarshipApplication.query
                     .join(User, ScholarshipApplication.applicant_id == User.id))
    if campus_ctx:
        recent_apps_q = recent_apps_q.filter(User.campus_id == campus_ctx)
    if effective_pid:
        recent_apps_q = recent_apps_q.filter(ScholarshipApplication.academic_period_id == effective_pid)
    recent_apps = (recent_apps_q
                   .order_by(ScholarshipApplication.submitted_at.desc())
                   .limit(5).all())

    # Active batches — scoped by campus AND period
    active_batches_q = ScholarshipBatch.query.filter_by(status='open')
    if campus_ctx:
        active_batches_q = active_batches_q.filter(ScholarshipBatch.campus_id == campus_ctx)
    if effective_pid:
        active_batches_q = active_batches_q.filter(ScholarshipBatch.academic_period_id == effective_pid)
    active_batches = active_batches_q.count()

    # Top performing students (lowest GWA = best, closest to 1.00)
    top_performers = (_scoped_users(User.query
                      .filter(User.user_type == 'student', User.gwa.isnot(None)))
                      .order_by(User.gwa.asc())
                      .limit(5).all())

    return render_template(
        'admin/dashboard.html',
        total_users=total_users,
        total_students=total_students,
        new_users=new_users,
        active_scholarships=active_scholarships,
        total_applications=total_applications,
        pending_review=pending_review,
        approved_count=approved_count,
        male_students=male_students,
        female_students=female_students,
        total_funds=total_funds,
        current_period=current_period,
        at_risk_count=at_risk_count,
        recent_apps=recent_apps,
        active_batches=active_batches,
        top_performers=top_performers,
    )


# ── Scholarship management ────────────────────────────────────────────────────

@admin_bp.route('/scholarships')
@role_required('admin')
def manage_scholarships():
    # Strict campus scoping (super admin honors campus selector)
    if session.get('user_type') == 'super_admin':
        campus_ctx = session.get('campus_context')          # None = all campuses
    else:
        _me = db.session.get(User, session.get('user_id'))
        campus_ctx = _me.campus_id if _me else None

    query = Scholarship.query
    if session.get('user_type') == 'super_admin':
        # Super admin: selected campus context (None = all). University-wide
        # programs are always visible to them.
        if campus_ctx:
            query = query.filter(db.or_(Scholarship.campus_id == campus_ctx,
                                        Scholarship.campus_id.is_(None)))
    else:
        # Campus admins manage only their own campus's programs;
        # university-wide programs are owned by the super admin.
        query = query.filter(Scholarship.campus_id == campus_ctx)
    scholarships = query.order_by(Scholarship.created_at.desc()).all()

    from app.models import Campus
    all_campuses = Campus.query.filter_by(is_active=True).order_by(Campus.id).all()
    return render_template('admin/scholarships.html', scholarships=scholarships,
                           all_campuses=all_campuses)


@admin_bp.route('/scholarships/create', methods=['POST'])
@role_required('admin')
def create_scholarship():
    try:
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

        # Campus assignment — same rules as staff route:
        # super admin chooses scope; campus admins always create for their own campus.
        if session.get('user_type') == 'super_admin':
            scope = request.form.get('scope', 'campus')
            campus_id_val = int(request.form.get('campus_id') or 0) or None
            if scope == 'university':
                campus_id_val = None   # university-wide
        else:
            _creator = db.session.get(User, session.get('user_id'))
            campus_id_val = _creator.campus_id if _creator else None
            scope = 'campus'

        # Academic period — NULL = permanent, specific ID = period-bound
        period_val = request.form.get('academic_period_id', '').strip()
        academic_period_id_val = int(period_val) if period_val else None

        s = Scholarship(
            title                = request.form['title'],
            category             = request.form.get('category', 'General'),
            scholarship_type     = request.form.get('scholarship_type', 'Financial Assistance'),
            funding_type         = request.form.get('funding_type', 'public'),
            description          = request.form.get('description', '').strip() or None,
            eligibility_criteria = request.form.get('eligibility_criteria', '').strip() or None,
            benefits             = request.form.get('benefits', '').strip() or None,
            award_amount         = max(0, float(request.form.get('award_amount') or 0)) or None,
            max_applicants       = max(0, int(request.form.get('max_applicants') or 0)) or None,
            application_deadline = datetime.strptime(request.form['application_deadline'], '%Y-%m-%d') if request.form.get('application_deadline') else None,
            status               = ScholarshipStatus.ACTIVE,
            created_by           = session['user_id'],
            custom_form_fields   = custom_fields if custom_fields else None,
            campus_id            = campus_id_val,
            scope                = scope,
            academic_period_id   = academic_period_id_val,
        )
        s.is_hidden = bool(request.form.get('is_hidden'))
        s.allowed_student_ids = request.form.get('allowed_student_ids', '').strip() or None
        db.session.add(s)
        db.session.commit()
        from app.services.audit_service import log_action
        log_action('scholarship.create', f'Scholarship "{s.title}" created.',
                   category='scholarship', target_type='scholarship', target_id=s.id)
        flash(f'Scholarship "{s.title}" created successfully.', 'success')

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
                # Announce only to the program's intended audience:
                # campus-specific program → that campus's students; university-wide → everyone.
                _stu_q = User.query.filter_by(user_type='student', is_active=True)
                if campus_id_val:
                    _stu_q = _stu_q.filter(User.campus_id == campus_id_val)
                students = _stu_q.all()
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
        flash(f'Error creating scholarship: {e}', 'error')
    return redirect(url_for('admin.manage_scholarships'))


@admin_bp.route('/scholarships/<int:sid>/edit', methods=['POST'])
@role_required('admin')
def edit_scholarship(sid):
    s = Scholarship.query.get_or_404(sid)
    _err = _scholarship_campus_guard(s)
    if _err:
        return _err
    try:
        s.title                = request.form.get('title', s.title)
        s.category             = request.form.get('category', s.category)
        s.scholarship_type     = request.form.get('scholarship_type', s.scholarship_type)
        ft = request.form.get('funding_type')
        if ft in ('public', 'private'):
            s.funding_type = ft
        s.description          = request.form.get('description', s.description)
        s.eligibility_criteria = request.form.get('eligibility_criteria', s.eligibility_criteria)
        s.benefits             = request.form.get('benefits', s.benefits)
        s.award_amount         = max(0, float(request.form.get('award_amount') or 0)) or s.award_amount
        if request.form.get('max_applicants'):
            s.max_applicants = max(0, int(request.form['max_applicants'])) or None
        if request.form.get('application_deadline'):
            s.application_deadline = datetime.strptime(
                request.form['application_deadline'], '%Y-%m-%d')
        if request.form.get('status'):
            s.status = ScholarshipStatus(request.form['status'])
        # Visibility
        s.is_hidden = request.form.get('is_hidden') == '1'
        # Allowed student IDs — normalise: strip spaces, remove blanks
        raw_ids = request.form.get('allowed_student_ids', '')
        cleaned = ','.join(
            sid.strip() for sid in raw_ids.replace('\n', ',').split(',')
            if sid.strip()
        )
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
        # Academic period
        period_val = request.form.get('academic_period_id', '').strip()
        s.academic_period_id = int(period_val) if period_val else None

        db.session.commit()
        from app.services.audit_service import log_action
        log_action('scholarship.edit', f'Scholarship "{s.title}" updated.',
                   category='scholarship', target_type='scholarship', target_id=s.id)
        flash(f'Scholarship "{s.title}" updated.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating scholarship: {e}', 'error')
    return redirect(url_for('admin.manage_scholarships'))


@admin_bp.route('/scholarships/<int:sid>/toggle-visibility', methods=['POST'])
@role_required('admin')
def toggle_scholarship_visibility(sid):
    """Quick-toggle hidden/visible without opening the full edit modal."""
    s = Scholarship.query.get_or_404(sid)
    _err = _scholarship_campus_guard(s)
    if _err:
        return _err
    s.is_hidden = not s.is_hidden
    db.session.commit()
    state = 'hidden' if s.is_hidden else 'visible (public)'
    from app.services.audit_service import log_action
    log_action('scholarship.visibility',
               f'Admin {session.get("username")} toggled visibility of '
               f'scholarship "{s.title}" (ID #{sid}) — now {state}.',
               category='scholarship', target_type='scholarship', target_id=sid)
    flash(f'"{s.title}" is now {state}.', 'success')
    return redirect(url_for('admin.manage_scholarships'))


@admin_bp.route('/scholarships/<int:sid>/delete', methods=['POST'])
@role_required('admin')
def delete_scholarship(sid):
    s = Scholarship.query.get_or_404(sid)
    _err = _scholarship_campus_guard(s)
    if _err:
        return _err
    pending = ScholarshipApplication.query.filter_by(
        scholarship_id=sid, status=ApplicationStatus.PENDING).count()
    if pending:
        flash(f'Cannot delete: {pending} pending application(s) exist.', 'error')
        return redirect(url_for('admin.manage_scholarships'))
    db.session.delete(s)
    db.session.commit()
    from app.services.audit_service import log_action
    log_action('scholarship.delete',
               f'Admin {session.get("username")} permanently deleted scholarship "{s.title}" '
               f'(ID #{sid}). All associated applications were also removed.',
               category='scholarship', target_type='scholarship', target_id=sid)
    flash('Scholarship deleted.', 'success')
    return redirect(url_for('admin.manage_scholarships'))


# ── Application management & approval workflow ────────────────────────────────

@admin_bp.route('/applications')
@role_required('admin')
def manage_applications():
    # Default to the actionable queue: only applications awaiting a decision.
    status_filter      = request.args.get('status', 'pending')
    scholarship_filter = request.args.get('scholarship_id', '')
    course_filter      = request.args.get('course', '')
    year_filter        = request.args.get('year', '')
    q                  = request.args.get('q', '').strip()

    query = ScholarshipApplication.query.join(
        User, ScholarshipApplication.applicant_id == User.id)

    # Strict campus scoping (super admin honors campus selector)
    campus_ctx = session.get('campus_context') if session.get('user_type') == 'super_admin' else None
    if campus_ctx is None and session.get('user_type') != 'super_admin':
        _me = db.session.get(User, session.get('user_id'))
        campus_ctx = _me.campus_id if _me else None
    if campus_ctx:
        query = query.filter(User.campus_id == campus_ctx)

    # Period filtering
    current_period = get_viewing_period()
    pid = current_period.id if current_period else None
    if pid:
        query = query.filter(ScholarshipApplication.academic_period_id == pid)

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
    _sch_q = Scholarship.query.order_by(Scholarship.title)
    if campus_ctx:
        _sch_q = _sch_q.filter(db.or_(Scholarship.campus_id == campus_ctx,
                                      Scholarship.campus_id.is_(None)))
    scholarships = _sch_q.all()
    courses = sorted({
        u.course for u in User.query.filter(
            User.user_type == 'student', User.course.isnot(None)).all()
        if u.course
    })

    stats = {
        'total':        query.count(),
        'pending':      query.filter(ScholarshipApplication.status.in_(
                            [ApplicationStatus.PENDING, ApplicationStatus.UNDER_REVIEW])).count(),
        'under_review': 0,  # merged into pending
        'approved':     query.filter(ScholarshipApplication.status == ApplicationStatus.APPROVED).count(),
        'rejected':     query.filter(ScholarshipApplication.status == ApplicationStatus.REJECTED).count(),
    }

    return render_template(
        'admin/applications.html',
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


@admin_bp.route('/applications/<int:app_id>/review', methods=['POST'])
@role_required('admin')
def review_application(app_id):
    """Approve or reject a single application."""
    application = ScholarshipApplication.query.get_or_404(app_id)
    action      = request.form.get('action')   # 'approve' | 'reject' | 'under_review'
    notes       = request.form.get('review_notes', '')

    status_map = {
        'approve':      ApplicationStatus.APPROVED,
        'reject':       ApplicationStatus.REJECTED,
    }
    new_status = status_map.get(action)
    if not new_status:
        flash('Invalid action.', 'error')
        return redirect(url_for('admin.manage_applications'))

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
            return redirect(url_for('admin.manage_applications'))

    application.status              = new_status
    application.reviewed_by         = session['user_id']
    application.reviewed_at         = datetime.utcnow()
    application.review_notes        = notes
    application.final_decision_date = datetime.utcnow() if action in ('approve', 'reject') else None

    if action == 'approve':
        application.scholar_status = 'active'
        application.approved_at    = datetime.utcnow()
        application.is_active      = True

        # Auto-assign to batch
        from app.services.batch_service import auto_assign_to_batch
        batch = auto_assign_to_batch(application)

    db.session.commit()

    # Notify applicant
    applicant = application.applicant
    notification_service.send_application_status_update(
        applicant.email,
        applicant.phone_number or '',
        applicant.id,
        application.scholarship.title,
        new_status.value,
        notes,
    )

    # Audit log
    from app.services.audit_service import log_action
    log_action(
        f'application.{action}',
        f'Application #{app_id} ({application.scholarship.title}) for '
        f'{applicant.get_full_name()} marked as {new_status.value.replace("_"," ")}.'
        + (f' Notes: {notes}' if notes else ''),
        category='application', target_type='application', target_id=app_id,
    )

    flash(f'Application #{app_id} has been {new_status.value.replace("_", " ")}.', 'success')
    return redirect(url_for('admin.manage_applications'))


@admin_bp.route('/applications/batch', methods=['POST'])
@role_required('admin')
def batch_review():
    """Batch approve or reject multiple applications."""
    app_ids = request.form.getlist('app_ids')
    action  = request.form.get('action')
    notes   = request.form.get('review_notes', 'Batch processed')

    status_map = {'approve': ApplicationStatus.APPROVED, 'reject': ApplicationStatus.REJECTED}
    new_status = status_map.get(action)
    if not new_status or not app_ids:
        flash('Invalid batch action or no applications selected.', 'error')
        return redirect(url_for('admin.manage_applications'))

    processed = 0
    approved_apps = []
    skipped_public = 0
    for app_id in app_ids:
        app = ScholarshipApplication.query.get(int(app_id))
        if app:
            # Guard: skip approving a public scholarship for a student who already holds one
            if action == 'approve' and app.scholarship.funding_type == 'public':
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
            app.status              = new_status
            app.reviewed_by         = session['user_id']
            app.reviewed_at         = datetime.utcnow()
            app.review_notes        = notes
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
        batch_results = auto_assign_multiple(approved_apps)
        if batch_results:
            batch_info = ' Batches: ' + ', '.join(f'{k} → {v}' for k, v in batch_results.items())

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
            pass   # non-critical — don't block on notification failure

    from app.services.audit_service import log_action
    log_action('application.batch_' + action,
               f'Admin {session.get("username")} batch-{action}d {processed} application(s). '
               f'IDs: {", ".join(app_ids[:10])}{"…" if len(app_ids) > 10 else ""}. '
               f'Notes: {notes}',
               category='application')
    flash(f'{processed} application(s) {new_status.value.replace("_", " ")}.{batch_info}'
          + (f' {skipped_public} skipped — student already holds a public scholarship.' if skipped_public else ''),
          'success' if not skipped_public else 'warning')
    return redirect(url_for('admin.manage_applications'))


# ── Scholar tagging ───────────────────────────────────────────────────────────

@admin_bp.route('/applications/<int:app_id>/tag', methods=['POST'])
@role_required('admin')
def tag_scholar(app_id):
    application = ScholarshipApplication.query.get_or_404(app_id)
    tag = request.form.get('tag')
    if tag not in ('active', 'at_risk', 'probation', 'inactive'):
        flash('Invalid tag.', 'error')
        return redirect(url_for('admin.manage_applications'))
    application.scholar_status = tag
    db.session.commit()
    from app.services.audit_service import log_action
    log_action('application.tag',
               f'Admin {session.get("username")} tagged application #{app_id} '
               f'({application.scholarship.title} — {application.applicant.get_full_name()}) '
               f'as "{tag}".',
               category='application', target_type='application', target_id=app_id)
    flash(f'Scholar tagged as {tag}.', 'success')
    return redirect(url_for('admin.manage_applications'))


# ── Monitoring & Tracking (Admin) ─────────────────────────────────────────────

@admin_bp.route('/monitoring')
@role_required('admin')
def monitoring():
    from datetime import timedelta
    status_filter     = request.args.get('scholar_status', '')
    course_filter     = request.args.get('course', '')

    # Strict campus scoping (super admin honors campus selector)
    campus_ctx = session.get('campus_context') if session.get('user_type') == 'super_admin' else None
    if campus_ctx is None and session.get('user_type') != 'super_admin':
        _me = db.session.get(User, session.get('user_id'))
        campus_ctx = _me.campus_id if _me else None

    current_period = get_viewing_period()
    pid = current_period.id if current_period else None

    query = ScholarshipApplication.query.filter(
        ScholarshipApplication.status == ApplicationStatus.APPROVED
    ).join(User, ScholarshipApplication.applicant_id == User.id)
    if campus_ctx:
        query = query.filter(User.campus_id == campus_ctx)
    if pid:
        query = query.filter(ScholarshipApplication.academic_period_id == pid)

    if status_filter:
        query = query.filter(ScholarshipApplication.scholar_status == status_filter)
    if course_filter:
        query = query.filter(User.course.ilike(f'%{course_filter}%'))

    scholars = query.order_by(ScholarshipApplication.approved_at.desc()).all()

    _all_approved_q = ScholarshipApplication.query.filter_by(status=ApplicationStatus.APPROVED)
    if campus_ctx:
        _all_approved_q = _all_approved_q.join(User, ScholarshipApplication.applicant_id == User.id).filter(User.campus_id == campus_ctx)
    if pid:
        _all_approved_q = _all_approved_q.filter(ScholarshipApplication.academic_period_id == pid)
    all_approved = _all_approved_q.all()
    stats = {
        'total':         len(all_approved),
        'active':        sum(1 for a in all_approved if a.scholar_status == 'active'),
        'at_risk':       sum(1 for a in all_approved if a.scholar_status == 'at_risk'),
        'probation':     sum(1 for a in all_approved if a.scholar_status == 'probation'),
        'termination':   sum(1 for a in all_approved if a.scholar_status == 'termination_warning'),
    }

    renewal_alerts = []
    for app in all_approved:
        if app.approved_at:
            renewal_due = app.approved_at + timedelta(days=365)
            days_left   = (renewal_due - datetime.utcnow()).days
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

    # M&E deadline (per current academic period) for overdue flagging
    from app.models.academic_period import AcademicPeriod
    current_period = get_viewing_period()
    me_deadline = current_period.me_form_deadline if current_period else None
    me_overdue_count = 0
    if me_deadline:
        today = datetime.utcnow().date()
        for a in all_approved:
            if a.id not in me_forms and me_deadline < today:
                me_overdue_count += 1

    return render_template(
        'admin/monitoring.html',
        scholars=scholars, stats=stats,
        renewal_alerts=renewal_alerts, courses=courses,
        status_filter=status_filter,
        course_filter=course_filter,
        me_forms=me_forms,
        me_deadline=me_deadline,
        me_overdue_count=me_overdue_count,
        now_local=datetime.utcnow().date(),
    )


@admin_bp.route('/monitoring/<int:app_id>/update-status', methods=['POST'])
@role_required('admin')
def update_scholar_status(app_id):
    from app.services.notification_service import notification_service as ns
    app = ScholarshipApplication.query.get_or_404(app_id)
    new_status = request.form.get('scholar_status', 'active')
    notes      = request.form.get('notes', '').strip()
    valid_s    = ('active', 'at_risk', 'probation', 'termination_warning')
    if new_status not in valid_s:
        flash('Invalid status.', 'error')
        return redirect(url_for('admin.monitoring'))
    app.scholar_status    = new_status
    app.status_updated_at = datetime.utcnow()
    if notes:
        app.review_notes = (app.review_notes or '') + f'\n[{datetime.utcnow().strftime("%Y-%m-%d")}] {notes}'
    if new_status in ('at_risk', 'probation', 'termination_warning'):
        student   = app.applicant
        label_map = {'at_risk': 'At Risk', 'probation': 'On Probation', 'termination_warning': 'Termination Warning'}
        ns.create_in_app_notification(student.id, f'Scholar Status: {label_map[new_status]}',
            f'Your status for {app.scholarship.title} is now {label_map[new_status]}.', 'performance')
        ns.send_email(student.email, f'LSPU ScholarHub — Scholar Status: {label_map[new_status]}',
            f'<h2>⚠️ Scholar Status Update</h2><p>Dear <strong>{student.get_full_name()}</strong>,</p>'
            f'<p>Your scholar status for <strong>{app.scholarship.title}</strong> is now '
            f'<strong>{label_map[new_status]}</strong>.</p>'
            f'<p>GWA: <strong>{student.gwa or "Not recorded"}</strong></p>'
            f'{"<p>Note: " + notes + "</p>" if notes else ""}'
            f'<p>Please contact the scholarship office.</p>'
            f'<p>Best regards,<br><strong>LSPU Scholarship Office</strong></p>')
    db.session.commit()
    from app.services.audit_service import log_action
    log_action('monitoring.status_update',
               f'Admin {session.get("username")} manually updated scholar status of '
               f'{app.applicant.get_full_name()} ({app.applicant.student_id}) '
               f'for "{app.scholarship.title}" to "{new_status}" (tag: {new_tag}).'
               + (f' Reason: {notes}' if notes else ''),
               category='gwa', target_type='application', target_id=app_id)
    flash(f'Scholar status updated to {new_status}.', 'success')
    return redirect(url_for('admin.monitoring'))


@admin_bp.route('/monitoring/<int:app_id>/update-gwa', methods=['POST'])
@role_required('admin')
def update_scholar_gwa(app_id):
    from app.services.performance_service import performance_service
    app = ScholarshipApplication.query.get_or_404(app_id)
    try:
        gwa = float(request.form.get('gwa', '').strip())
        if not (1.0 <= gwa <= 5.0):
            raise ValueError
    except ValueError:
        flash('GWA must be between 1.00 and 5.00.', 'error')
        return redirect(url_for('admin.monitoring'))
    student = app.applicant
    student.gwa = round(gwa, 2)
    if gwa >= 4.00:   new_status, new_tag = 'termination_warning', 'inactive'
    elif gwa > 3.75:  new_status = 'probation'
    elif gwa > 3.00:  new_status = 'at_risk'
    else:             new_status = 'active'
    app.scholar_status    = new_status
    app.status_updated_at = datetime.utcnow()
    db.session.commit()
    alerts = performance_service._check_performance_alerts(student.id, gwa)
    if alerts:
        performance_service._send_performance_notifications(student, app, alerts, gwa)
    from app.services.audit_service import log_action
    log_action('gwa.update',
               f'Admin {session.get("username")} updated GWA of '
               f'{student.get_full_name()} ({student.student_id}) to {gwa:.2f} '
               f'for scholarship "{app.scholarship.title}". '
               f'Scholar status auto-set to "{new_status}".',
               category='gwa', target_type='user', target_id=student.id)
    flash(f'GWA updated to {gwa} for {student.get_full_name()}. Status: {new_status}.', 'success')
    return redirect(url_for('admin.monitoring'))


@admin_bp.route('/monitoring/<int:app_id>/send-renewal-reminder', methods=['POST'])
@role_required('admin')
def send_renewal_reminder(app_id):
    from datetime import timedelta
    from app.services.notification_service import notification_service as ns
    app = ScholarshipApplication.query.get_or_404(app_id)
    student = app.applicant
    renewal_due = (app.approved_at + timedelta(days=365)) if app.approved_at else datetime.utcnow()
    days_left   = (renewal_due - datetime.utcnow()).days
    ns.send_email(student.email, 'LSPU ScholarHub — Scholarship Renewal Reminder',
        f'<h2>📋 Renewal Reminder</h2><p>Dear <strong>{student.get_full_name()}</strong>,</p>'
        f'<p>Your scholarship <strong>{app.scholarship.title}</strong> renewal is due on '
        f'<strong>{renewal_due.strftime("%B %d, %Y")}</strong> ({max(0,days_left)} days).</p>'
        f'<p>Please visit the scholarship office to submit renewal documents.</p>'
        f'<p>Best regards,<br><strong>LSPU Scholarship Office</strong></p>')
    ns.create_in_app_notification(student.id, 'Scholarship Renewal Reminder',
        f'{app.scholarship.title} renewal due in {max(0,days_left)} days.', 'deadline')
    app.renewal_notified_at = datetime.utcnow()
    db.session.commit()
    from app.services.audit_service import log_action
    log_action('monitoring.renewal_reminder',
               f'Admin {session.get("username")} sent renewal reminder to '
               f'{student.get_full_name()} ({student.student_id}) '
               f'for scholarship "{app.scholarship.title}". '
               f'Renewal due: {renewal_due.strftime("%b %d, %Y")} ({max(0,days_left)} days).',
               category='system', target_type='application', target_id=app_id)
    flash(f'Renewal reminder sent to {student.get_full_name()}.', 'success')
    return redirect(url_for('admin.monitoring'))


# ── User management ───────────────────────────────────────────────────────────

@admin_bp.route('/users')
@role_required('admin')
def manage_users():
    q         = request.args.get('q', '').strip()
    role      = request.args.get('role', '')
    campus_filter = request.args.get('campus', '')
    query     = User.query
    if q:
        query = query.filter(
            db.or_(
                User.username.ilike(f'%{q}%'),
                User.first_name.ilike(f'%{q}%'),
                User.last_name.ilike(f'%{q}%'),
                User.email.ilike(f'%{q}%'),
            )
        )
    if role:
        query = query.filter_by(user_type=role)

    # Campus filtering: super admin honors campus selector, admin/staff see own campus
    user_type = session.get('user_type', '')
    if user_type == 'super_admin':
        campus_ctx = session.get('campus_context')
        if campus_ctx:
            query = query.filter(User.campus_id == campus_ctx)
        elif campus_filter:
            query = query.filter(User.campus_id == int(campus_filter))
    elif user_type in ('admin', 'staff'):
        user = User.query.get(session.get('user_id'))
        if user:
            # Use multi-campus junction table for staff with multiple campuses
            if user.assigned_campuses:
                my_campus_ids = [c.id for c in user.assigned_campuses]
                query = query.filter(User.campus_id.in_(my_campus_ids))
            elif user.campus_id:
                query = query.filter(User.campus_id == user.campus_id)

    users = query.order_by(User.created_at.desc()).all()
    from app.models import Campus
    all_campuses = Campus.query.filter_by(is_active=True).order_by(Campus.id).all()
    return render_template('admin/users.html', users=users, q=q, role=role,
                           current_user_id=session.get('user_id'),
                           all_campuses=all_campuses,
                           campus_filter=campus_filter)


@admin_bp.route('/users/<int:uid>/edit', methods=['POST'])
@role_required('admin')
def edit_user(uid):
    """Edit any user's profile fields."""
    user = User.query.get_or_404(uid)
    user.first_name   = request.form.get('first_name', user.first_name).strip().title()
    user.last_name    = request.form.get('last_name',  user.last_name).strip().title()
    user.email        = request.form.get('email',        user.email).strip()
    user.phone_number = request.form.get('phone_number', user.phone_number or '').strip() or None
    user.student_id   = request.form.get('student_id',   user.student_id or '').strip() or None
    user.course       = request.form.get('course',        user.course or '').strip() or None
    user.year_level   = request.form.get('year_level',    user.year_level or '').strip() or None
    user.address      = request.form.get('address',       user.address or '').strip() or None

    # Role change (with the same safety rules as the quick-change route)
    new_role = request.form.get('role', '').strip()
    if new_role and new_role in ('student', 'staff', 'admin', 'super_admin') and new_role != user.user_type:
        if user.id == session['user_id']:
            flash('You cannot change your own role. Ask another admin to do it.', 'error')
            return redirect(url_for('admin.manage_users'))
        if user.user_type == 'admin' and new_role != 'admin':
            admins_remaining = User.query.filter(
                User.user_type.in_(('admin', 'super_admin')),
                User.id != user.id, User.is_active == True
            ).count()
            if admins_remaining == 0:
                flash('Cannot demote the only active admin. A super admin or '
                      'another admin must remain.', 'error')
                return redirect(url_for('admin.manage_users'))
        old_role = user.user_type
        user.user_type = new_role
        from app.services.audit_service import log_action as _log
        _log('user.role_change',
             f'Admin {session.get("username")} changed role of '
             f'{user.get_full_name()} ({user.username}) from {old_role.upper()} '
             f'to {new_role.upper()} via user edit.',
             category='user', target_type='user', target_id=uid,
             user_id=session.get('user_id'), user_name=session.get('username'),
             user_role='admin')

    new_pw = request.form.get('new_password', '').strip()
    if new_pw:
        from app.services.password_validator import validate_password
        pw_valid, pw_error = validate_password(new_pw)
        if not pw_valid:
            flash(pw_error, 'error')
            return redirect(url_for('admin.manage_users'))
        user.set_password(new_pw)

    # Update campus assignment for staff/admin
    if user.user_type in ('staff', 'admin', 'super_admin'):
        from app.models import UserCampus, Campus
        campus_ids = request.form.getlist('campus_ids')
        if campus_ids:
            new_campuses = []
            for cid in campus_ids:
                try:
                    c = Campus.query.get(int(cid))
                    if c:
                        new_campuses.append(c)
                except (TypeError, ValueError):
                    pass
            if new_campuses:
                # Remove old assignments
                UserCampus.query.filter_by(user_id=user.id).delete()
                # Add new assignments
                for c in new_campuses:
                    db.session.add(UserCampus(user_id=user.id, campus_id=c.id))
                # Update primary campus_id for backward compatibility
                user.campus_id = new_campuses[0].id

    db.session.commit()
    from app.services.audit_service import log_action
    pw_changed = ' Password was also reset.' if request.form.get('new_password', '').strip() else ''
    log_action('user.edit',
               f'Admin edited profile of {user.get_full_name()} ({user.username}, {user.user_type}). '
               f'Fields updated: name, email, phone, student ID, course, year level.{pw_changed}',
               category='user', target_type='user', target_id=uid)
    flash(f'User {user.username} updated successfully.', 'success')
    return redirect(url_for('admin.manage_users'))


@admin_bp.route('/users/<int:uid>/role', methods=['POST'])
@role_required('admin')
def change_user_role(uid):
    """Change a user's role (student / staff / admin)."""
    user = User.query.get_or_404(uid)
    new_role = request.form.get('role', '').strip()

    if new_role not in ('student', 'staff', 'admin', 'super_admin'):
        flash('Invalid role selected.', 'error')
        return redirect(url_for('admin.manage_users'))

    if new_role == user.user_type:
        flash(f'{user.username} is already a {new_role}.', 'info')
        return redirect(url_for('admin.manage_users'))

    # Safety: an admin cannot demote themselves
    if user.id == session['user_id']:
        flash('You cannot change your own role. Ask another admin to do it.', 'error')
        return redirect(url_for('admin.manage_users'))

    # Safety: never remove the last admin
    if user.user_type == 'admin' and new_role != 'admin':
        admins_remaining = User.query.filter(
            User.user_type.in_(('admin', 'super_admin')),
            User.id != user.id, User.is_active == True
        ).count()
        if admins_remaining == 0:
            flash('Cannot demote the only active admin. A super admin or '
                  'another admin must remain.', 'error')
            return redirect(url_for('admin.manage_users'))

    old_role = user.user_type
    user.user_type = new_role
    db.session.commit()

    from app.services.audit_service import log_action
    log_action('user.role_change',
               f'Admin {session.get("username")} changed role of '
               f'{user.get_full_name()} ({user.username}) from {old_role.upper()} '
               f'to {new_role.upper()}.',
               category='user', target_type='user', target_id=uid,
               user_id=session.get('user_id'), user_name=session.get('username'),
               user_role='admin')
    flash(f'{user.get_full_name()} ({user.username}) is now a {new_role}.', 'success')
    return redirect(url_for('admin.manage_users'))


@admin_bp.route('/users/<int:uid>/toggle', methods=['POST'])
@role_required('admin')
def toggle_user(uid):
    user = User.query.get_or_404(uid)
    if user.id == session['user_id']:
        flash('You cannot disable your own account.', 'error')
        return redirect(url_for('admin.manage_users'))
    user.is_active = not user.is_active
    db.session.commit()
    state = 'enabled' if user.is_active else 'disabled'
    from app.services.audit_service import log_action
    log_action('user.toggle',
               f'Admin {session.get("username")} {state} account of '
               f'{user.get_full_name()} ({user.username}, {user.user_type}). '
               f'Account is now {"ACTIVE" if user.is_active else "DISABLED"}.',
               category='user', target_type='user', target_id=uid)
    flash(f'User {user.username} has been {state}.', 'success')
    return redirect(url_for('admin.manage_users'))


@admin_bp.route('/users/<int:uid>/verify', methods=['POST'])
@role_required('admin')
def verify_user(uid):
    user = User.query.get_or_404(uid)
    user.is_verified = True
    db.session.commit()
    if session.get('user_id') == uid:
        session['is_verified'] = True
    from app.services.audit_service import log_action
    log_action('user.verify',
               f'Admin {session.get("username")} manually verified account of '
               f'{user.get_full_name()} ({user.username}, {user.user_type}). '
               f'Student can now apply for scholarships.',
               category='user', target_type='user', target_id=uid)
    flash(f'User {user.username} verified.', 'success')
    return redirect(url_for('admin.manage_users'))


# ── Notifications ─────────────────────────────────────────────────────────────

@admin_bp.route('/notifications')
@role_required('admin')
def manage_notifications():
    # Strict campus scoping (super admin honors campus selector)
    if session.get('user_type') == 'super_admin':
        campus_ctx = session.get('campus_context')          # None = all campuses
    else:
        _me = db.session.get(User, session.get('user_id'))
        campus_ctx = _me.campus_id if _me else None

    _stu_q = User.query.filter_by(user_type='student', is_active=True)
    if campus_ctx:
        _stu_q = _stu_q.filter(User.campus_id == campus_ctx)
    students    = _stu_q.order_by(User.last_name).all()
    courses     = sorted({s.course for s in students if s.course})
    year_levels = ['1st Year', '2nd Year', '3rd Year', '4th Year']
    _sch_q = Scholarship.query.order_by(Scholarship.title)
    if campus_ctx:
        _sch_q = _sch_q.filter(db.or_(Scholarship.campus_id == campus_ctx,
                                      Scholarship.campus_id.is_(None)))
    scholarships = _sch_q.all()
    # Filter recent notifications by campus and period
    recent_q = Notification.query
    if campus_ctx:
        recent_q = recent_q.join(User, Notification.recipient_id == User.id).filter(
            User.campus_id == campus_ctx)
    current_period = get_viewing_period()
    pid = current_period.id if current_period else None
    if pid:
        # Period filtering: only show notifications tagged with this period
        recent_q = recent_q.filter(Notification.academic_period_id == pid)
    recent = recent_q.order_by(Notification.sent_at.desc()).limit(20).all()
    # Check if viewing a past period (for confirmation dialog)
    from app.models.academic_period import AcademicPeriod
    current_period_db = AcademicPeriod.query.filter_by(is_current=True).first()
    viewing_period = get_viewing_period()
    is_past_period = (viewing_period and current_period_db and
                      viewing_period.id != current_period_db.id)
    return render_template('admin/notifications.html',
                           students=students, recent=recent,
                           courses=courses, year_levels=year_levels,
                           scholarships=scholarships,
                           viewing_period=viewing_period,
                           is_past_period=is_past_period)


@admin_bp.route('/notifications/send', methods=['POST'])
@role_required('admin')
def send_notification():
    recipient_type = request.form.get('recipient_type', 'multiple')
    title          = request.form.get('title', '').strip()
    message        = request.form.get('message', '').strip()
    send_email     = request.form.get('send_email') == 'on'
    send_sms       = request.form.get('send_sms') == 'on'

    if not title or not message:
        flash('Title and message are required.', 'error')
        return redirect(url_for('admin.manage_notifications'))

    # ── Optional attachments (up to 3 files, 5MB each) ──────────────────
    import base64 as _b64
    ALLOWED_ATTACHMENT_EXTS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'}
    attachments = []
    for f in request.files.getlist('attachments'):
        if not f or not f.filename:
            continue
        if len(attachments) >= 3:
            flash('Maximum of 3 attachments allowed — extra files were skipped.', 'warning')
            break
        ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
        if ext not in ALLOWED_ATTACHMENT_EXTS:
            flash(f'Attachment "{f.filename}" was skipped — allowed types: PDF, Word, Excel, images.', 'warning')
            continue
        data = f.read()
        if len(data) > 5 * 1024 * 1024:
            flash(f'Attachment "{f.filename}" was skipped — it exceeds the 5MB limit.', 'warning')
            continue
        attachments.append({
            'filename': f.filename,
            'content_base64': _b64.b64encode(data).decode('ascii'),
        })
    if attachments and not send_email:
        flash('Attachments are sent by email only — tick "Also send as email" for students to receive them.', 'warning')

    # All modes submit recipient_ids (checked checkboxes)
    uids = request.form.getlist('recipient_ids')
    if uids:
        recipients = User.query.filter(User.id.in_([int(u) for u in uids if u.isdigit()])).all()
        label = f'{len(recipients)} student(s) via {recipient_type}'
    else:
        if recipient_type == 'at_risk':
            recipients = User.query.filter_by(user_type='student', is_active=True).filter(
                User.gwa.isnot(None), User.gwa > 3.00).all()
            label = 'at-risk students (GWA > 3.00)'
        else:
            recipients = []
            label = 'none'

    sent = 0
    sms_sent = 0
    current_period = get_viewing_period()
    period_id = current_period.id if current_period else None
    for user in recipients:
        db.session.add(Notification(
            recipient_id=user.id,
            title=title,
            message=message,
            notification_type=NotificationType.SYSTEM_ANNOUNCEMENT,
            channel=NotificationChannel.IN_APP,
            academic_period_id=period_id,
        ))
        if send_email:
            notification_service.send_email(user.email, title, message,
                                            attachments=attachments or None)
        if send_sms and user.phone_number:
            result = notification_service.send_sms(user.phone_number, f"{title}: {message}")
            if result.get('success'):
                sms_sent += 1
        sent += 1

    db.session.commit()
    from app.services.audit_service import log_action
    channels = ['in-app']
    if send_email: channels.append('email')
    if send_sms:   channels.append(f'SMS ({sms_sent} delivered)')
    log_action('notification.send',
               f'Admin {session.get("username")} sent "{title}" to {label} ({sent} recipient(s)) '
               f'via {", ".join(channels)}.',
               category='system')
    msg = f'Notification sent to {sent} recipient(s).'
    if send_sms:
        msg += f' SMS delivered to {sms_sent} verified phone(s).'
    flash(msg, 'success')
    return redirect(url_for('admin.manage_notifications'))


# ── Profile ───────────────────────────────────────────────────────────────────

@admin_bp.route('/profile')
@role_required('admin')
def profile():
    user = User.query.get(session['user_id'])
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('auth.login'))
    return render_template('admin/profile.html', user=user)


@admin_bp.route('/profile/update', methods=['POST'])
@role_required('admin')
def update_profile():
    user = User.query.get(session['user_id'])
    user.first_name   = request.form.get('first_name', user.first_name)
    user.last_name    = request.form.get('last_name', user.last_name)
    user.phone_number = request.form.get('phone_number', user.phone_number)
    user.address      = request.form.get('address', user.address)

    new_pw = request.form.get('new_password', '').strip()
    if new_pw:
        current_pw = request.form.get('current_password', '').strip()
        if not current_pw:
            flash('Please enter your current password to set a new one.', 'error')
            return redirect(url_for('admin.profile'))
        if not user.check_password(current_pw):
            flash('Current password is incorrect. Password was not changed.', 'error')
            return redirect(url_for('admin.profile'))
        from app.services.password_validator import validate_password
        pw_valid, pw_error = validate_password(new_pw)
        if not pw_valid:
            flash(pw_error, 'error')
            return redirect(url_for('admin.profile'))
        user.set_password(new_pw)

    db.session.commit()
    from app.services.audit_service import log_action
    pw_note = ' Password was changed.' if new_pw else ''
    log_action('user.profile_update',
               f'Admin {user.username} updated their own profile (name, phone).{pw_note}',
               category='user', target_type='user', target_id=user.id)
    flash('Profile updated successfully.', 'success')
    return redirect(url_for('admin.profile'))


# ── System Settings ─────────────────────────────────────────────────────────

@admin_bp.route('/settings')
@role_required('admin')
def settings():
    """System settings page — manage academic periods and configuration."""
    if session.get('user_type') != 'super_admin':
        flash('Only the Super Admin can manage periods.', 'error')
        return redirect(url_for('admin.dashboard'))
    from app.models import AcademicPeriod, ScholarshipBatch
    periods = AcademicPeriod.query.order_by(AcademicPeriod.id.desc()).all()
    current = get_viewing_period()
    return render_template('admin/settings.html', periods=periods, current=current)


@admin_bp.route('/settings/period/create', methods=['POST'])
@role_required('admin')
def create_academic_period():
    if session.get('user_type') != 'super_admin':
        flash('Only the Super Admin can manage periods.', 'error')
        return redirect(url_for('admin.dashboard'))
    from app.models import AcademicPeriod
    year = request.form.get('academic_year', '').strip()
    sem  = request.form.get('semester', '').strip()
    if not year or not sem:
        flash('Academic year and semester are required.', 'error')
        return redirect(url_for('admin.settings'))
    period = AcademicPeriod(academic_year=year, semester=sem, is_current=True)
    # Unset any existing current period
    AcademicPeriod.query.update({'is_current': False})
    db.session.add(period)
    db.session.commit()
    log_action('settings.period_create',
               f'Admin created academic period: {period.display_name}',
               category='system')
    flash(f'Academic period "{period.display_name}" created and set as current.', 'success')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/settings/period/<int:pid>/set-current', methods=['POST'])
@role_required('admin')
def set_current_period(pid):
    if session.get('user_type') != 'super_admin':
        flash('Only the Super Admin can manage periods.', 'error')
        return redirect(url_for('admin.dashboard'))
    from app.models import AcademicPeriod
    AcademicPeriod.set_current(pid)
    period = AcademicPeriod.query.get(pid)
    log_action('settings.period_set_current',
               f'Admin set current period to {period.display_name}',
               category='system')
    flash(f'Current period set to "{period.display_name}".', 'success')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/settings/period/<int:pid>/delete', methods=['POST'])
@role_required('admin')
def delete_academic_period(pid):
    """Delete an academic period — only if it has no linked data."""
    if session.get('user_type') != 'super_admin':
        flash('Only the Super Admin can manage periods.', 'error')
        return redirect(url_for('admin.dashboard'))
    from app.models import AcademicPeriod, ScholarshipBatch, MonitoringSubmission
    period = AcademicPeriod.query.get(pid)
    if not period:
        flash('Period not found.', 'error')
        return redirect(url_for('admin.settings'))
    if period.is_current:
        flash('Cannot delete the current active period. Set another period as current first.', 'error')
        return redirect(url_for('admin.settings'))
    # Check for linked data
    has_apps = ScholarshipApplication.query.filter_by(academic_period_id=pid).count() > 0
    has_batches = ScholarshipBatch.query.filter_by(academic_period_id=pid).count() > 0
    has_monitoring = MonitoringSubmission.query.filter_by(academic_period_id=pid).count() > 0
    if has_apps or has_batches or has_monitoring:
        flash(f'Cannot delete "{period.display_name}" — it has linked applications, batches, or monitoring records.', 'error')
        return redirect(url_for('admin.settings'))
    name = period.display_name
    db.session.delete(period)
    db.session.commit()
    log_action('settings.period_delete',
               f'Admin deleted academic period: {name}',
               category='system')
    flash(f'Academic period "{name}" deleted.', 'success')
    return redirect(url_for('admin.settings'))


# ── Reports & Export ──────────────────────────────────────────────────────────

@admin_bp.route('/reports')
@role_required('admin')
def reports():
    """Admin reports & analytics page."""
    from app.models.scholarship import ApplicationStatus, ScholarshipStatus
    import json

    # Strict campus scoping (super admin honors campus selector)
    if session.get('user_type') == 'super_admin':
        campus_ctx = session.get('campus_context')          # None = all campuses
    else:
        _me = db.session.get(User, session.get('user_id'))
        campus_ctx = _me.campus_id if _me else None

    current_period = get_viewing_period()
    pid = current_period.id if current_period else None

    def _apps_q():
        """Applications scoped to the campus AND period."""
        q = ScholarshipApplication.query.join(
            User, ScholarshipApplication.applicant_id == User.id)
        if campus_ctx:
            q = q.filter(User.campus_id == campus_ctx)
        if pid:
            q = q.filter(ScholarshipApplication.academic_period_id == pid)
        return q

    def _students_q(extra=None):
        q = User.query.filter(User.user_type == 'student')
        if campus_ctx:
            q = q.filter(User.campus_id == campus_ctx)
        # Period filtering: only students with applications in this period
        if pid:
            period_student_ids = [r[0] for r in db.session.query(
                ScholarshipApplication.applicant_id
            ).filter(ScholarshipApplication.academic_period_id == pid).distinct().all()]
            if period_student_ids:
                q = q.filter(User.id.in_(period_student_ids))
            else:
                # No students in this period — return empty query
                q = q.filter(User.id == -1)
        if extra is not None:
            q = q.filter(extra)
        return q

    total_apps   = _apps_q().count()
    approved     = _apps_q().filter(
        ScholarshipApplication.status == ApplicationStatus.APPROVED).count()
    rejected     = _apps_q().filter(
        ScholarshipApplication.status == ApplicationStatus.REJECTED).count()
    pending      = _apps_q().filter(
        ScholarshipApplication.status.in_([ApplicationStatus.PENDING,
                                           ApplicationStatus.UNDER_REVIEW])
    ).count()
    approval_rate = round(approved / total_apps * 100, 1) if total_apps else 0

    total_students  = _students_q().count()
    total_users     = total_students  # In period context, users = students with apps
    total_staff     = User.query.filter_by(user_type='staff').count()
    active_scholars = _apps_q().filter(
        ScholarshipApplication.status == ApplicationStatus.APPROVED,
        ScholarshipApplication.scholar_status == 'active').count()

    # Strict campus scoping (super admin honors campus selector)
    if session.get('user_type') == 'super_admin':
        campus_ctx = session.get('campus_context')          # None = all campuses
    else:
        _me = db.session.get(User, session.get('user_id'))
        campus_ctx = _me.campus_id if _me else None

    _sch_q = Scholarship.query
    if campus_ctx:
        _sch_q = _sch_q.filter(db.or_(Scholarship.campus_id == campus_ctx,
                                      Scholarship.campus_id.is_(None)))
    scholarships = _sch_q.all()
    scholarship_stats = []
    for s in scholarships:
        apps = _apps_q().filter(ScholarshipApplication.scholarship_id == s.id).all()
        scholarship_stats.append({
            'scholarship': s,
            'total':    len(apps),
            'approved': sum(1 for a in apps if a.status == ApplicationStatus.APPROVED),
            'rejected': sum(1 for a in apps if a.status == ApplicationStatus.REJECTED),
            'pending':  sum(1 for a in apps if a.status in (
                ApplicationStatus.PENDING, ApplicationStatus.UNDER_REVIEW)),
        })

    # ── GWA distribution for chart ────────────────────────────────────────────
    # Bucket students into LSPU grade bands
    students_with_gwa = _students_q(User.gwa.isnot(None)).all()
    gwa_buckets = {
        'Excellent (1.00–1.25)':        0,
        'Very Satisfactory (1.26–1.75)': 0,
        'Satisfactory (1.76–2.25)':      0,
        'Fairly Satisfactory (2.26–2.75)': 0,
        'Passed (2.76–3.00)':            0,
        'Conditional Failure (3.01–3.99)': 0,
        'Failed (4.00+)':                0,
    }
    for s in students_with_gwa:
        g = s.gwa
        if g <= 1.25:   gwa_buckets['Excellent (1.00–1.25)'] += 1
        elif g <= 1.75: gwa_buckets['Very Satisfactory (1.26–1.75)'] += 1
        elif g <= 2.25: gwa_buckets['Satisfactory (1.76–2.25)'] += 1
        elif g <= 2.75: gwa_buckets['Fairly Satisfactory (2.26–2.75)'] += 1
        elif g <= 3.00: gwa_buckets['Passed (2.76–3.00)'] += 1
        elif g < 4.00:  gwa_buckets['Conditional Failure (3.01–3.99)'] += 1
        else:           gwa_buckets['Failed (4.00+)'] += 1

    gwa_labels = json.dumps(list(gwa_buckets.keys()))
    gwa_data   = json.dumps(list(gwa_buckets.values()))

    # ── Per-scholarship applicant counts for bar chart ────────────────────────
    sch_labels = json.dumps([s['scholarship'].title[:25] for s in scholarship_stats])
    sch_approved = json.dumps([s['approved'] for s in scholarship_stats])
    sch_pending  = json.dumps([s['pending']  for s in scholarship_stats])
    sch_rejected = json.dumps([s['rejected'] for s in scholarship_stats])

    # Scholar status breakdown — scoped to visible (campus) scholarships
    _vis_ids = [s.id for s in scholarships]
    _appr_q = ScholarshipApplication.query.filter_by(status=ApplicationStatus.APPROVED)
    if _vis_ids:
        _appr_q = _appr_q.filter(ScholarshipApplication.scholarship_id.in_(_vis_ids))
    else:
        _appr_q = _appr_q.filter(db.false())
    all_approved = _appr_q.all()
    scholar_status_data = json.dumps([
        sum(1 for a in all_approved if a.scholar_status == 'active'),
        sum(1 for a in all_approved if a.scholar_status == 'at_risk'),
        sum(1 for a in all_approved if a.scholar_status == 'probation'),
        sum(1 for a in all_approved if a.scholar_status == 'termination_warning'),
    ])

    return render_template(
        'admin/reports.html',
        total_apps=total_apps,
        approved=approved,
        rejected=rejected,
        pending=pending,
        approval_rate=approval_rate,
        total_users=total_users,
        total_students=total_students,
        total_staff=total_staff,
        active_scholars=active_scholars,
        scholarship_stats=scholarship_stats,
        gwa_labels=gwa_labels,
        gwa_data=gwa_data,
        sch_labels=sch_labels,
        sch_approved=sch_approved,
        sch_pending=sch_pending,
        sch_rejected=sch_rejected,
        scholar_status_data=scholar_status_data,
    )


@admin_bp.route('/reports/export')
@role_required('admin')
def export_report():
    """Export a report in the requested format."""
    from app.services.export_service import generate_export

    report_type = request.args.get('type', 'applications')
    fmt         = request.args.get('format', 'pdf')
    filters     = {
        'status':         request.args.get('status', ''),
        'scholarship_id': request.args.get('scholarship_id', ''),
        'course':         request.args.get('course', ''),
    }
    filters = {k: v for k, v in filters.items() if v}

    try:
        buf, mime, filename = generate_export(report_type, fmt, filters)
        return send_file(buf, mimetype=mime,
                         as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'Export failed: {e}', 'error')
        return redirect(url_for('admin.reports'))


# ── Document download (admin) ─────────────────────────────────────────────────

@admin_bp.route('/document/<int:doc_id>/download')
@role_required('admin')
def download_document(doc_id):
    """Allow admin to download any student document."""
    import os
    from flask import send_file as _send_file, Response
    from app.models.document import Document

    doc = Document.query.get_or_404(doc_id)

    # Cloudinary proxy
    if doc.cloudinary_public_id or (doc.file_path and (doc.file_path.startswith('http://') or doc.file_path.startswith('https://'))):
        try:
            import urllib.request as _ur
            fetch_url = doc.cloudinary_url or doc.file_path
            if doc.cloudinary_public_id:
                from app.services.storage_service import get_signed_url
                res_type = 'image' if (doc.file_type or '').lower() in ('jpg','jpeg','png') else 'raw'
                signed = get_signed_url(doc.cloudinary_public_id, resource_type=res_type)
                if signed:
                    fetch_url = signed
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
            return redirect(url_for('admin.manage_applications'))

    file_path = doc.file_path
    if not os.path.isabs(file_path):
        from flask import current_app
        file_path = os.path.join(current_app.root_path, '..', file_path)
    file_path = os.path.normpath(file_path)

    if not os.path.exists(file_path):
        flash('File not found on server.', 'error')
        return redirect(url_for('admin.manage_applications'))

    return _send_file(file_path, as_attachment=True,
                      download_name=doc.original_filename)


@admin_bp.route('/document/<int:doc_id>/view')
@role_required('admin')
def view_document(doc_id):
    """Allow admin to view/preview a document inline."""
    import os
    from flask import send_file as _send_file, Response
    from app.models.document import Document

    doc = Document.query.get_or_404(doc_id)

    mime_map = {
        'pdf': 'application/pdf',
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }
    mime = mime_map.get((doc.file_type or '').lower(), 'application/octet-stream')

    # Cloudinary proxy
    if doc.cloudinary_public_id or (doc.file_path and (doc.file_path.startswith('http://') or doc.file_path.startswith('https://'))):
        try:
            import urllib.request as _ur
            fetch_url = doc.cloudinary_url or doc.file_path
            if doc.cloudinary_public_id:
                from app.services.storage_service import get_signed_url
                res_type = 'image' if (doc.file_type or '').lower() in ('jpg','jpeg','png') else 'raw'
                signed = get_signed_url(doc.cloudinary_public_id, resource_type=res_type)
                if signed:
                    fetch_url = signed
            req = _ur.Request(fetch_url)
            req.add_header('User-Agent', 'LSPU-ScholarHub/1.0')
            with _ur.urlopen(req, timeout=30) as resp:
                file_data = resp.read()
            return Response(file_data, mimetype=mime,
                            headers={'Content-Disposition': f'inline; filename="{doc.original_filename}"',
                                     'Content-Length': str(len(file_data))})
        except Exception as e:
            flash(f'Could not load file: {e}', 'error')
            return redirect(url_for('admin.manage_applications'))

    file_path = doc.file_path
    if not os.path.isabs(file_path):
        from flask import current_app
        file_path = os.path.join(current_app.root_path, '..', file_path)
    file_path = os.path.normpath(file_path)

    if not os.path.exists(file_path):
        flash('File not found on server.', 'error')
        return redirect(url_for('admin.manage_applications'))

    return _send_file(file_path, mimetype=mime, as_attachment=False,
                      download_name=doc.original_filename)


# ── User Account Management (Admin only) ─────────────────────────────────

def _delete_user_related_rows(uid):
    """Delete rows that reference the user before deleting the account.
    Documents/chat/gwa_history cascade at DB level; these do not."""
    from app.models.notification import Notification
    from app.models.document import Document
    from app.models.chat_history import ChatHistory
    Notification.query.filter_by(recipient_id=uid).delete()
    Document.query.filter_by(user_id=uid).delete()
    ChatHistory.query.filter_by(user_id=uid).delete()


@admin_bp.route('/users/create', methods=['POST'])
@role_required('admin')
def create_user_account():
    """Create a new staff or admin account (from Manage Users)."""
    first_name = request.form.get('first_name', '').strip().title()
    last_name  = request.form.get('last_name',  '').strip().title()
    email      = request.form.get('email',      '').strip().lower()
    username   = request.form.get('username',   '').strip()
    password   = request.form.get('password',   '').strip()
    role       = request.form.get('role', 'staff').strip()

    if role not in ('staff', 'admin'):
        flash('New accounts can be created as staff or admin only. '
              'Students register themselves through the registration page.', 'error')
        return redirect(url_for('admin.manage_users'))
    if not all([first_name, last_name, email, username, password]):
        flash('All fields are required.', 'error')
        return redirect(url_for('admin.manage_users'))
    if len(password) < 8:
        flash('Password must be at least 8 characters.', 'error')
        return redirect(url_for('admin.manage_users'))

    # Campus assignment — staff/admin can be assigned to multiple campuses
    from app.models import Campus, UserCampus
    campus_ids = request.form.getlist('campus_ids')
    if not campus_ids:
        # Fallback to single campus_id for backward compatibility
        single = request.form.get('campus_id', '').strip()
        if single:
            campus_ids = [single]
    campuses = []
    for cid in campus_ids:
        try:
            c = Campus.query.get(int(cid))
            if c:
                campuses.append(c)
        except (TypeError, ValueError):
            pass
    if not campuses:
        flash('Please select at least one campus for this account.', 'error')
        return redirect(url_for('admin.manage_users'))
    if User.query.filter_by(username=username).first():
        flash(f'Username "{username}" is already taken.', 'error')
        return redirect(url_for('admin.manage_users'))
    if User.query.filter_by(email=email).first():
        flash(f'Email "{email}" is already registered.', 'error')
        return redirect(url_for('admin.manage_users'))

    try:
        # Use the first campus as primary campus_id for backward compatibility
        account = User(
            username=username, email=email,
            first_name=first_name, last_name=last_name,
            user_type=role, is_active=True, is_verified=True,
            campus_id=campuses[0].id,
        )
        account.set_password(password)
        db.session.add(account)
        db.session.flush()  # get the id
        # Add all assigned campuses to junction table
        for c in campuses:
            db.session.add(UserCampus(user_id=account.id, campus_id=c.id))
        db.session.commit()
        from app.services.audit_service import log_action
        campus_names = ', '.join(c.name for c in campuses)
        log_action('user.create_account',
                   f'Admin {session.get("username")} created new {role} account: '
                   f'{first_name} {last_name} (username: {username}, email: {email}, '
                   f'campuses: {campus_names}).',
                   category='user', target_type='user', target_id=account.id,
                   user_id=session.get('user_id'), user_name=session.get('username'),
                   user_role='admin')
        flash(f'{role.title()} account "{username}" created successfully '
              f'for {campus_names}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating account: {e}', 'error')
    return redirect(url_for('admin.manage_users'))


@admin_bp.route('/users/create-student', methods=['POST'])
@role_required('admin')
def create_student_account():
    """Create a student account (super admin only)."""
    if session.get('user_type') != 'super_admin':
        flash('Only the Super Admin can create student accounts.', 'error')
        return redirect(url_for('admin.manage_users'))

    first_name = request.form.get('first_name', '').strip().title()
    last_name  = request.form.get('last_name',  '').strip().title()
    email      = request.form.get('email',      '').strip().lower()
    username   = request.form.get('username',   '').strip()
    password   = request.form.get('password',   '').strip()
    campus_id  = request.form.get('campus_id',  '').strip()

    if not all([first_name, last_name, email, username, password, campus_id]):
        flash('All fields are required.', 'error')
        return redirect(url_for('admin.manage_users'))
    if len(password) < 8:
        flash('Password must be at least 8 characters.', 'error')
        return redirect(url_for('admin.manage_users'))

    from app.models import Campus
    campus = Campus.query.get(int(campus_id)) if campus_id.isdigit() else None
    if not campus:
        flash('Please select a valid campus.', 'error')
        return redirect(url_for('admin.manage_users'))
    if User.query.filter_by(username=username).first():
        flash(f'Username "{username}" is already taken.', 'error')
        return redirect(url_for('admin.manage_users'))
    if User.query.filter_by(email=email).first():
        flash(f'Email "{email}" is already registered.', 'error')
        return redirect(url_for('admin.manage_users'))

    try:
        account = User(
            username=username, email=email,
            first_name=first_name, last_name=last_name,
            user_type='student', is_active=True, is_verified=True,
            campus_id=campus.id,
        )
        account.set_password(password)
        db.session.add(account)
        db.session.commit()
        from app.services.audit_service import log_action
        log_action('user.create_student',
                   f'Super admin created student account: '
                   f'{first_name} {last_name} (username: {username}, email: {email}, '
                   f'campus: {campus.name}).',
                   category='user', target_type='user', target_id=account.id,
                   user_id=session.get('user_id'), user_name=session.get('username'),
                   user_role='super_admin')
        flash(f'Student account "{username}" created successfully for {campus.name}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating student account: {e}', 'error')
    return redirect(url_for('admin.manage_users'))


@admin_bp.route('/users/<int:uid>/delete', methods=['POST'])
@role_required('admin')
def delete_user(uid):
    """Permanently delete any staff/admin account (and its records)."""
    user = User.query.get_or_404(uid)

    # Students register through the public flow — removal there means deleting
    # their scholarship history too, which manage_users is not the place for.
    if user.user_type == 'student':
        flash('Student accounts cannot be deleted here. Use the Student Directory.', 'error')
        return redirect(url_for('admin.manage_users'))
    if user.id == session['user_id']:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('admin.manage_users'))
    if user.user_type == 'admin':
        # A super_admin counts as an admin-level guardian of the system
        admins_remaining = User.query.filter(
            User.user_type.in_(('admin', 'super_admin')),
            User.id != user.id, User.is_active == True
        ).count()
        if admins_remaining == 0:
            flash('Cannot delete the only active admin. A super admin or '
                  'another admin must remain to manage the system.', 'error')
            return redirect(url_for('admin.manage_users'))

    uname, uemail = user.username, user.email
    _delete_user_related_rows(uid)
    db.session.delete(user)
    db.session.commit()
    from app.services.audit_service import log_action
    log_action('user.delete_account',
               f'Admin {session.get("username")} permanently deleted {user.user_type} account: '
               f'{uname} (email: {uemail}).',
               category='user', target_type='user', target_id=uid,
               user_id=session.get('user_id'), user_name=session.get('username'),
               user_role='admin')
    flash(f'Account "{uname}" deleted.', 'success')
    return redirect(url_for('admin.manage_users'))


# ── Legacy Staff Management routes — kept as redirects for old links ────────

@admin_bp.route('/staff')
@role_required('admin')
def manage_staff():
    """Legacy staff page — merged into Manage Users; redirects there."""
    return redirect(url_for('admin.manage_users', role='staff'))


@admin_bp.route('/staff/create', methods=['POST'])
@role_required('admin')
def create_staff():
    """Legacy staff-creation endpoint — delegates to the unified account creator."""
    return create_user_account()


@admin_bp.route('/staff/<int:uid>/delete', methods=['POST'])
@role_required('admin')
def delete_staff(uid):
    """Legacy staff-deletion endpoint — delegates to the unified deleter."""
    return delete_user(uid)


# ── Student Directory (Admin) ─────────────────────────────────────────────────

@admin_bp.route('/students')
@role_required('admin')
def student_directory():
    """Central student directory with GWA sorting and filtering."""
    q          = request.args.get('q', '').strip()
    year       = request.args.get('year', '')
    course     = request.args.get('course', '')
    gender     = request.args.get('gender', '')
    sort       = request.args.get('sort', 'name')
    gwa_flag   = request.args.get('gwa_flag', '')
    scholar_filter = request.args.get('scholar', '')
    GWA_THRESHOLD = 3.00

    # Strict campus scoping (super admin honors campus selector)
    campus_ctx = session.get('campus_context') if session.get('user_type') == 'super_admin' else None
    if campus_ctx is None and session.get('user_type') != 'super_admin':
        _me = db.session.get(User, session.get('user_id'))
        campus_ctx = _me.campus_id if _me else None
    current_period = get_viewing_period()
    pid = current_period.id if current_period else None

    # When a period is selected, only show students who have applications in that period
    if pid:
        from sqlalchemy import select as _sel
        period_student_ids = _sel(ScholarshipApplication.applicant_id).where(
            ScholarshipApplication.academic_period_id == pid).distinct()
        query = User.query.filter(User.id.in_(period_student_ids))
    else:
        query = User.query.filter_by(user_type='student')
    if campus_ctx:
        query = query.filter(User.campus_id == campus_ctx)
    if q:
        query = query.filter(db.or_(
            User.first_name.ilike(f'%{q}%'),
            User.last_name.ilike(f'%{q}%'),
            User.student_id.ilike(f'%{q}%'),
            User.email.ilike(f'%{q}%'),
        ))
    if year:
        query = query.filter_by(year_level=year)
    if course:
        query = query.filter(User.course.ilike(f'%{course}%'))
    if gender:
        query = query.filter_by(gender=gender)
    if gwa_flag == 'at_risk':
        query = query.filter(User.gwa.isnot(None), User.gwa > GWA_THRESHOLD)
    if scholar_filter == 'existing':
        query = query.filter(User.is_existing_scholar.is_(True))
    elif scholar_filter == 'none':
        query = query.filter(User.is_existing_scholar.is_(False))

    if sort == 'gwa_asc':
        query = query.order_by(db.case((User.gwa.is_(None), 1), else_=0), User.gwa.asc())
    elif sort == 'gwa_desc':
        query = query.order_by(db.case((User.gwa.is_(None), 1), else_=0), User.gwa.desc())
    else:
        query = query.order_by(User.last_name.asc(), User.first_name.asc())

    page = request.args.get('page', 1, type=int)
    students = query.paginate(page=page, per_page=20, error_out=False)

    # Stats — scoped to the same period
    all_students = query.all()
    with_gwa     = [s for s in all_students if s.gwa is not None]
    at_risk      = [s for s in with_gwa if s.gwa > GWA_THRESHOLD]
    avg_gwa      = round(sum(s.gwa for s in with_gwa) / len(with_gwa), 2) if with_gwa else None
    courses      = sorted({s.course for s in all_students if s.course})
    existing_scholars = sum(1 for s in all_students if s.is_existing_scholar)

    return render_template(
        'admin/students.html',
        students=students,
        q=q, year=year, course=course, gender=gender, sort=sort, gwa_flag=gwa_flag,
        scholar_filter=scholar_filter,
        GWA_THRESHOLD=GWA_THRESHOLD,
        total_students=len(all_students),
        with_gwa_count=len(with_gwa),
        at_risk_count=len(at_risk),
        avg_gwa=avg_gwa,
        courses=courses,
        existing_scholars=existing_scholars,
    )


@admin_bp.route('/students/<int:uid>')
@role_required('admin')
def student_profile(uid):
    """View a single student's full profile with documents and GWA."""
    student = User.query.get_or_404(uid)
    if student.user_type != 'student':
        flash('User is not a student.', 'error')
        return redirect(url_for('admin.student_directory'))
    return render_template('admin/student_profile.html', student=student)


# ── Existing-scholar declaration: add student to a program directly ──────────

@admin_bp.route('/students/<int:uid>/add-existing-scholar', methods=['GET', 'POST'])
@role_required('admin')
def add_existing_scholar(uid):
    """Add a self-declared existing scholar into a scholarship program as a
    pre-approved application (same record a normal approval produces)."""
    student = User.query.get_or_404(uid)
    if student.user_type != 'student':
        flash('User is not a student.', 'error')
        return redirect(url_for('admin.student_directory'))

    if request.method == 'POST':
        from app.services.scholarship_service import add_existing_scholar_to_program
        program_id = request.form.get('scholarship_id', '').strip()
        notes      = request.form.get('notes', '').strip() or None
        if not program_id:
            flash('Please choose a scholarship program.', 'error')
            return redirect(url_for('admin.add_existing_scholar', uid=uid))
        scholarship = Scholarship.query.get(int(program_id))
        if not scholarship:
            flash('Scholarship program not found.', 'error')
            return redirect(url_for('admin.student_profile', uid=uid))

        # Campus guard: campus admins/staff only touch their own campus (or univ-wide)
        if session.get('user_type') != 'super_admin' and student.campus_id:
            _me = db.session.get(User, session.get('user_id'))
            _my_campus = _me.campus_id if _me else None
            if _my_campus and student.campus_id != _my_campus:
                flash('This student belongs to a different campus.', 'error')
                return redirect(url_for('admin.student_directory'))

        application, err = add_existing_scholar_to_program(
            student, scholarship, session.get('user_id'), notes=notes)
        if err:
            flash(err, 'error')
            return redirect(url_for('admin.add_existing_scholar', uid=uid))

        from app.services.audit_service import log_action
        log_action('scholarship.existing_scholar_added',
                   f'{student.get_full_name()} ({student.student_id}) added to '
                   f'"{scholarship.title}" via existing-scholar declaration.',
                   category='scholarship', target_type='application',
                   target_id=application.id)
        flash(f'{student.get_full_name()} has been added to "{scholarship.title}" '
              f'as an approved scholar and notified.', 'success')
        return redirect(url_for('admin.student_profile', uid=uid))

    # GET: programs the office can add this student to (campus-scoped)
    campus_ctx = student.campus_id
    q = Scholarship.query.filter(Scholarship.status == ScholarshipStatus.ACTIVE)
    if campus_ctx:
        q = q.filter(db.or_(Scholarship.campus_id == campus_ctx,
                            Scholarship.campus_id.is_(None)))
    programs = q.order_by(Scholarship.title.asc()).all()
    return render_template('shared/add_existing_scholar.html',
                           student=student, programs=programs,
                           back_url=url_for('admin.student_profile', uid=uid))


# ── Student document verification ─────────────────────────────────────────────

@admin_bp.route('/documents/<int:doc_id>/view')
@role_required('admin')
def view_student_document(doc_id):
    """Render a viewer page for a student document."""
    import os
    from flask import current_app
    from app.models.document import Document
    doc = Document.query.get_or_404(doc_id)

    # If stored on Cloudinary, go through the raw proxy route so the file
    # displays INLINE — redirecting straight to Cloudinary makes the browser
    # download it (Cloudinary serves raw files with Content-Disposition: attachment).
    if doc.cloudinary_public_id or (doc.file_path and (doc.file_path.startswith('http://') or doc.file_path.startswith('https://'))):
        return redirect(url_for('admin.serve_student_document_raw', doc_id=doc.id))

    file_path = doc.file_path
    if not os.path.isabs(file_path):
        file_path = os.path.join(current_app.root_path, '..', file_path)
    if not os.path.exists(os.path.normpath(file_path)):
        flash('File not found.', 'error')
        return redirect(url_for('admin.student_profile', uid=doc.user_id))
    return render_template('shared/document_viewer.html',
                           doc=doc,
                           raw_url=url_for('admin.serve_student_document_raw', doc_id=doc.id),
                           back_url=url_for('admin.student_profile', uid=doc.user_id))


@admin_bp.route('/documents/<int:doc_id>/raw')
@role_required('admin')
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
            # Try stored URL first, then generate signed URL as fallback
            fetch_url = doc.cloudinary_url
            if not fetch_url:
                from app.services.storage_service import get_signed_url
                res_type  = 'image' if (doc.file_type or '').lower() in ('jpg','jpeg','png') else 'raw'
                fetch_url = get_signed_url(doc.cloudinary_public_id, resource_type=res_type)
            if not fetch_url:
                flash('File URL not available.', 'error')
                return redirect(url_for('admin.student_profile', uid=doc.user_id))
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
            return redirect(url_for('admin.student_profile', uid=doc.user_id))

    # Local file fallback
    path = doc.file_path
    if not os.path.isabs(path):
        path = os.path.join(current_app.root_path, '..', path)
    path = os.path.normpath(path)
    if not os.path.exists(path):
        flash('File not found on server.', 'error')
        return redirect(url_for('admin.student_profile', uid=doc.user_id))
    return _sf(path, mimetype=mime, as_attachment=force_download,
               download_name=doc.original_filename)


@admin_bp.route('/documents/<int:doc_id>/verify', methods=['POST'])
@role_required('admin')
def verify_student_document(doc_id):
    from app.models.document import Document
    doc = Document.query.get_or_404(doc_id)
    doc.is_verified = True
    db.session.commit()
    flash(f'Document "{doc.original_filename}" marked as verified.', 'success')
    return redirect(url_for('admin.student_profile', uid=doc.user_id))


@admin_bp.route('/documents/<int:doc_id>/unverify', methods=['POST'])
@role_required('admin')
def unverify_student_document(doc_id):
    from app.models.document import Document
    doc = Document.query.get_or_404(doc_id)
    doc.is_verified = False
    db.session.commit()
    flash(f'Document "{doc.original_filename}" marked as pending.', 'info')
    return redirect(url_for('admin.student_profile', uid=doc.user_id))


@admin_bp.route('/students/<int:uid>/documents/upload', methods=['POST'])
@role_required('admin')
def upload_student_document(uid):
    """Admin uploads a new document for a student."""
    import os
    import uuid
    from datetime import datetime as _dt
    from flask import current_app
    from werkzeug.utils import secure_filename
    from app.models.document import Document

    student = User.query.get_or_404(uid)
    file    = request.files.get('document_file')
    desc    = request.form.get('description', '').strip()
    cat     = request.form.get('category', 'general').strip()

    if not file or not file.filename:
        flash('No file selected.', 'error')
        return redirect(url_for('admin.student_profile', uid=uid))

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    allowed = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'}
    if ext not in allowed:
        flash(f'File type .{ext} not allowed. Use PDF, JPG, PNG, DOC, or DOCX.', 'error')
        return redirect(url_for('admin.student_profile', uid=uid))

    # Server-side 5MB limit (matches what the form promises)
    file.seek(0, os.SEEK_END)
    if file.tell() > 5 * 1024 * 1024:
        flash('File is larger than 5MB. Please upload a smaller file.', 'error')
        return redirect(url_for('admin.student_profile', uid=uid))
    file.seek(0)

    # Read file bytes
    file_bytes = file.read()
    file_size  = len(file_bytes)

    # Build unique filename
    unique_name = secure_filename(
        f"{cat}_{uid}_{_dt.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.{ext}"
    )

    # Save file via Cloudinary or local
    from app.services.storage_service import upload_file as _cloud_upload
    cloud_result = _cloud_upload(file_bytes, unique_name,
                                 f"documents/{uid}", resource_type='auto')
    if cloud_result['success']:
        file_path      = cloud_result['url']
        cloudinary_url = cloud_result['url']
        cloudinary_pid = cloud_result.get('public_id')
    else:
        upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'documents', str(uid))
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, unique_name)
        with open(file_path, 'wb') as f:
            f.write(file_bytes)
        cloudinary_url = None
        cloudinary_pid = None

    doc = Document(
        user_id              = uid,
        original_filename    = file.filename,
        stored_filename      = unique_name,
        file_path            = file_path,
        file_size            = file_size,
        category             = cat,
        file_type            = ext,
        description          = desc or None,
        is_verified          = True,
        cloudinary_url       = cloudinary_url,
        cloudinary_public_id = cloudinary_pid,
    )
    db.session.add(doc)
    db.session.commit()

    from app.services.audit_service import log_action
    log_action('document.upload',
               f'Admin {session.get("username")} uploaded "{file.filename}" '
               f'({cat}) for student {student.get_full_name()} ({student.student_id}).',
               category='document', target_type='user', target_id=uid)
    flash(f'Document "{file.filename}" uploaded successfully.', 'success')
    return redirect(url_for('admin.student_profile', uid=uid))


@admin_bp.route('/documents/<int:doc_id>/delete', methods=['POST'])
@role_required('admin')
def delete_student_document(doc_id):
    """Admin deletes a student document."""
    import os
    from app.models.document import Document

    doc     = Document.query.get_or_404(doc_id)
    uid     = doc.user_id
    fname   = doc.original_filename
    student = User.query.get(uid)

    # Delete physical file
    try:
        if doc.file_path and os.path.exists(doc.file_path):
            os.remove(doc.file_path)
    except Exception:
        pass

    db.session.delete(doc)
    db.session.commit()

    from app.services.audit_service import log_action
    log_action('document.delete',
               f'Admin {session.get("username")} deleted document "{fname}" '
               f'for student {student.get_full_name() if student else uid}.',
               category='document', target_type='user', target_id=uid)
    flash(f'Document "{fname}" deleted.', 'success')
    return redirect(url_for('admin.student_profile', uid=uid))


@admin_bp.route('/students/<int:uid>/documents/replace-reg', methods=['POST'])
@role_required('admin')
def replace_reg_document(uid):
    """Admin replaces a student's registration document (COR or grades)."""
    import os
    import uuid
    from datetime import datetime as _dt
    from flask import current_app
    from werkzeug.utils import secure_filename

    student  = User.query.get_or_404(uid)
    doc_type = request.form.get('doc_type')   # 'cor' or 'grades'
    file     = request.files.get('reg_file')

    if doc_type not in ('cor', 'grades'):
        flash('Invalid document type.', 'error')
        return redirect(url_for('admin.student_profile', uid=uid))

    if not file or not file.filename:
        flash('No file selected.', 'error')
        return redirect(url_for('admin.student_profile', uid=uid))

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ('pdf', 'jpg', 'jpeg', 'png'):
        flash('Only PDF, JPG, or PNG files are accepted.', 'error')
        return redirect(url_for('admin.student_profile', uid=uid))

    # Delete old file
    old_path = student.cor_file_path if doc_type == 'cor' else student.grades_file_path
    old_cid  = student.cor_cloudinary_id if doc_type == 'cor' else student.grades_cloudinary_id
    if old_cid:
        from app.services.storage_service import delete_file as _del
        _del(public_id=old_cid)
    elif old_path and os.path.exists(old_path):
        try:
            os.remove(old_path)
        except Exception:
            pass

    # Read new file bytes
    file_bytes = file.read()

    # Upload to Cloudinary or local
    from app.services.storage_service import upload_file as _cloud_upload
    upload_dir  = os.path.join(current_app.config['UPLOAD_FOLDER'], 'registration')
    os.makedirs(upload_dir, exist_ok=True)
    label       = 'cor' if doc_type == 'cor' else 'grades'
    unique_name = secure_filename(
        f"{label}_{student.student_id}_{_dt.utcnow().strftime('%Y%m%d%H%M%S')}.{ext}"
    )
    cloud_result = _cloud_upload(file_bytes, unique_name,
                                 f"registration/{student.id}", resource_type='auto')
    if cloud_result['success']:
        new_path = cloud_result['url']
        new_cid  = cloud_result.get('public_id')
    else:
        new_path = os.path.join(upload_dir, unique_name)
        with open(new_path, 'wb') as f:
            f.write(file_bytes)
        new_cid = None

    if doc_type == 'cor':
        student.cor_file_path    = new_path
        student.cor_cloudinary_id = new_cid
    else:
        student.grades_file_path    = new_path
        student.grades_cloudinary_id = new_cid

    db.session.commit()

    from app.services.audit_service import log_action
    label_display = 'COR' if doc_type == 'cor' else 'Copy of Grades'
    log_action('document.replace',
               f'Admin {session.get("username")} replaced {label_display} '
               f'for student {student.get_full_name()} ({student.student_id}).',
               category='document', target_type='user', target_id=uid)
    flash(f'{label_display} replaced successfully.', 'success')
    return redirect(url_for('admin.student_profile', uid=uid))


@admin_bp.route('/documents/<int:doc_id>/ctc-override/<int:value>', methods=['POST'])
@role_required('admin')
def override_ctc(doc_id, value):
    """Manually override the AI CTC detection result (1=detected, 0=not detected)."""
    from app.models.document import Document
    doc = Document.query.get_or_404(doc_id)
    doc.ctc_detected = bool(value)
    db.session.commit()
    status = 'present' if value else 'absent'
    flash(f'CTC stamp marked as {status} for "{doc.original_filename}".', 'success')
    # Return to the application review page — get app_id from the doc
    app_id = doc.application_id
    if app_id:
        return redirect(url_for('admin.manage_applications') + f'#app{app_id}')
    return redirect(url_for('admin.student_profile', uid=doc.user_id))


@admin_bp.route('/students/<int:uid>/update-gwa', methods=['POST'])
@role_required('admin')
def update_gwa(uid):
    """Update a student's GWA and units enrolled."""
    student = User.query.get_or_404(uid)
    try:
        gwa_val = float(request.form.get('gwa', '').strip())
        if not (1.0 <= gwa_val <= 5.0):
            flash('GWA must be between 1.0 and 5.0.', 'error')
            return redirect(url_for('admin.student_profile', uid=uid))
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
        # Save history entry
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
        flash('Invalid GWA value. Enter a number between 1.0 and 5.0.', 'error')
    return redirect(url_for('admin.student_profile', uid=uid))


# ── Registration document viewer (admin) ─────────────────────────────────────

@admin_bp.route('/students/<int:uid>/document/<doc_type>')
@role_required('admin')
def view_reg_document(uid, doc_type):
    """View/download a student's registration document (cor or grades)."""
    import os
    from flask import send_file as _send_file, current_app
    student = User.query.get_or_404(uid)

    file_path = student.cor_file_path if doc_type == 'cor' else student.grades_file_path
    if not file_path:
        flash('No document uploaded yet. Use the Replace button to upload one.', 'warning')
        return redirect(url_for('admin.student_profile', uid=uid))

    # If it's a Cloudinary URL, stream it through our Flask route
    # (avoids Cloudinary 401 for raw files)
    if file_path and (file_path.startswith('http://') or file_path.startswith('https://')):
        try:
            import urllib.request
            from flask import Response

            # Determine resource type from URL or extension
            ext = file_path.rsplit('.', 1)[-1].lower() if '.' in file_path else 'pdf'
            # Cloudinary image URLs contain /image/upload/
            is_image = ext in ('jpg', 'jpeg', 'png') or '/image/upload/' in file_path
            res_type = 'image' if is_image else 'raw'

            fetch_url = file_path
            cid = student.cor_cloudinary_id if doc_type == 'cor' else student.grades_cloudinary_id
            if cid:
                from app.services.storage_service import get_signed_url
                signed = get_signed_url(cid, resource_type=res_type)
                if signed:
                    fetch_url = signed

            req = urllib.request.Request(fetch_url)
            req.add_header('User-Agent', 'LSPU-ScholarHub/1.0')
            with urllib.request.urlopen(req, timeout=30) as resp:
                file_data = resp.read()

            mime_map = {
                'pdf': 'application/pdf',
                'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
            }
            mime  = mime_map.get(ext, 'image/jpeg' if is_image else 'application/pdf')
            label = 'COR' if doc_type == 'cor' else 'Grades'
            fname = f"{student.student_id}_{label}.{ext}"
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
            return redirect(url_for('admin.student_profile', uid=uid))

    if not os.path.isabs(file_path):
        file_path = os.path.join(current_app.root_path, '..', file_path)
    file_path = os.path.normpath(file_path)

    if not os.path.exists(file_path):
        label_display = 'COR' if doc_type == 'cor' else 'Copy of Grades'
        flash(
            f'{label_display} file was not found on the server. '
            f'Please use the Replace button to re-upload the file.',
            'warning'
        )
        return redirect(url_for('admin.student_profile', uid=uid))

    ext = file_path.rsplit('.', 1)[-1].lower()
    mime_map = {
        'pdf': 'application/pdf',
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }
    mime = mime_map.get(ext, 'application/octet-stream')
    label = 'COR' if doc_type == 'cor' else 'Grades'
    filename = f"{student.student_id}_{label}.{ext}"
    return _send_file(file_path, mimetype=mime, as_attachment=False,
                      download_name=filename)


# ── Excel / CSV Bulk Import ───────────────────────────────────────────────────

@admin_bp.route('/import')
@role_required('admin')
def import_page():
    """Excel/CSV bulk import page."""
    return render_template('admin/import.html')


@admin_bp.route('/import/upload', methods=['POST'])
@role_required('admin')
def import_students():
    """
    Parse uploaded Excel/CSV and bulk-register students.
    Expected columns (case-insensitive):
      student_id, first_name, last_name, email, year_level
    Optional: course, phone_number
    """
    import io
    import re

    file = request.files.get('import_file')
    if not file or not file.filename:
        flash('Please select a file to upload.', 'error')
        return redirect(url_for('admin.import_page'))

    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ('xlsx', 'xls', 'csv'):
        flash('Only .xlsx, .xls, or .csv files are accepted.', 'error')
        return redirect(url_for('admin.import_page'))

    try:
        import openpyxl
        import csv as csv_mod

        rows = []
        if ext in ('xlsx', 'xls'):
            wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
            ws = wb.active
            headers = None
            for row in ws.iter_rows(values_only=True):
                if headers is None:
                    headers = [str(c).strip().lower().replace(' ', '_')
                               if c else '' for c in row]
                    continue
                rows.append(dict(zip(headers, row)))
        else:
            content = file.read().decode('utf-8-sig')
            reader  = csv_mod.DictReader(io.StringIO(content))
            for row in reader:
                rows.append({k.strip().lower().replace(' ', '_'): v
                             for k, v in row.items()})

    except Exception as e:
        flash(f'Could not parse file: {e}', 'error')
        return redirect(url_for('admin.import_page'))

    # ── Process rows ──────────────────────────────────────────────────────────
    from app.views.auth import _generate_password, _send_credentials_email

    inserted = 0
    skipped  = 0
    errors   = []

    REQUIRED = {'student_id', 'first_name', 'last_name', 'email', 'year_level'}

    for i, row in enumerate(rows, start=2):   # row 2 = first data row
        # Normalise keys
        sid        = str(row.get('student_id', '') or '').strip()
        first_name = str(row.get('first_name', '') or '').strip().title()
        last_name  = str(row.get('last_name',  '') or '').strip().title()
        email      = str(row.get('email',      '') or '').strip().lower()
        year_level = str(row.get('year_level', '') or '').strip()
        course     = str(row.get('course',     '') or '').strip() or None
        phone      = str(row.get('phone_number','') or '').strip() or None

        # Validate required fields
        if not all([sid, first_name, last_name, email, year_level]):
            errors.append(f'Row {i}: Missing required field(s) — skipped.')
            skipped += 1
            continue

        # Validate email format
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            errors.append(f'Row {i}: Invalid email "{email}" — skipped.')
            skipped += 1
            continue

        # Check duplicates
        if User.query.filter_by(student_id=sid).first():
            errors.append(f'Row {i}: Student ID "{sid}" already exists — skipped.')
            skipped += 1
            continue
        if User.query.filter_by(email=email).first():
            errors.append(f'Row {i}: Email "{email}" already exists — skipped.')
            skipped += 1
            continue

        # Create user
        try:
            temp_pw = _generate_password(10)
            new_user = User(
                username=sid,
                email=email,
                first_name=first_name,
                last_name=last_name,
                student_id=sid,
                year_level=year_level,
                course=course,
                phone_number=phone,
                user_type='student',
                is_active=True,
                is_verified=True,
            )
            new_user.set_password(temp_pw)
            db.session.add(new_user)
            db.session.flush()   # get ID before commit

            # Send credentials email
            _send_credentials_email(new_user, temp_pw)
            inserted += 1

        except Exception as e:
            db.session.rollback()
            errors.append(f'Row {i}: DB error — {e}')
            skipped += 1
            continue

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'Database commit failed: {e}', 'error')
        return redirect(url_for('admin.import_page'))

    # Summary flash
    if inserted:
        flash(f'✓ {inserted} student(s) imported successfully. '
              f'Credentials emailed to each student.', 'success')
    if skipped:
        flash(f'⚠ {skipped} row(s) skipped. See details below.', 'warning')

    return render_template('admin/import.html',
                           import_errors=errors,
                           inserted=inserted,
                           skipped=skipped)


# ── Import template download ──────────────────────────────────────────────────

@admin_bp.route('/import/template')
@role_required('admin')
def download_import_template():
    """Generate and serve a blank Excel import template."""
    import io
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

    # Sample row
    ws.append(['0123-1740', 'Juan', 'Dela Cruz', 'Santos',
               'juan@student.lspu.edu', '3rd Year',
               'Bachelor of Science in Information Technology',
               '09123456789', 'Male', 'Santa Cruz', 'Laguna'])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return send_file(
        buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='lspu_scholarhub_import_template.xlsx',
    )


# ── Audit Log ─────────────────────────────────────────────────────────────────

@admin_bp.route('/audit-log')
@role_required('admin')
def audit_log():
    """View the system audit trail."""
    from app.models.audit_log import AuditLog

    category = request.args.get('category', '')
    role     = request.args.get('role', '')
    q        = request.args.get('q', '').strip()
    page     = request.args.get('page', 1, type=int)
    per_page = 50

    # Campus scoping for admin/staff
    campus_ctx = session.get('campus_context') if session.get('user_type') == 'super_admin' else None
    if campus_ctx is None and session.get('user_type') != 'super_admin':
        _me = db.session.get(User, session.get('user_id'))
        campus_ctx = _me.campus_id if _me else None

    query = AuditLog.query
    if campus_ctx:
        query = query.join(User, AuditLog.user_id == User.id, isouter=True).filter(
            db.or_(User.campus_id == campus_ctx, User.campus_id.is_(None)))
    if category:
        query = query.filter_by(category=category)
    if role:
        query = query.filter_by(user_role=role)
    if q:
        query = query.filter(
            db.or_(
                AuditLog.user_name.ilike(f'%{q}%'),
                AuditLog.description.ilike(f'%{q}%'),
                AuditLog.action.ilike(f'%{q}%'),
            )
        )

    logs       = query.order_by(AuditLog.timestamp.desc()).paginate(
                     page=page, per_page=per_page, error_out=False)
    categories = ['auth', 'application', 'scholarship', 'user', 'gwa', 'document', 'system']
    roles      = ['super_admin', 'admin', 'staff', 'student']

    return render_template(
        'admin/audit_log.html',
        logs=logs,
        categories=categories,
        roles=roles,
        category=category,
        role=role,
        q=q,
    )


@admin_bp.route('/audit-log/export')
@role_required('admin')
def export_audit_log():
    """Export the audit log as PDF or Excel, respecting current filters."""
    import io
    from datetime import datetime as _dt
    from app.models.audit_log import AuditLog

    fmt      = request.args.get('format', 'xlsx')
    category = request.args.get('category', '')
    role     = request.args.get('role', '')
    q        = request.args.get('q', '').strip()

    query = AuditLog.query
    if category:
        query = query.filter_by(category=category)
    if role:
        query = query.filter_by(user_role=role)
    if q:
        query = query.filter(
            db.or_(
                AuditLog.user_name.ilike(f'%{q}%'),
                AuditLog.description.ilike(f'%{q}%'),
                AuditLog.action.ilike(f'%{q}%'),
            )
        )
    logs = query.order_by(AuditLog.timestamp.desc()).all()
    generated = _dt.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    filename_base = f'audit_log_{_dt.utcnow().strftime("%Y%m%d_%H%M%S")}'

    # ── Excel export ──────────────────────────────────────────────────────────
    if fmt == 'xlsx':
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, PatternFill
        wb = Workbook()
        ws = wb.active
        ws.title = 'Audit Log'

        # Title row
        ws.merge_cells('A1:G1')
        ws['A1'] = f'LSPU ScholarHub — Audit Log Export  ({generated})'
        ws['A1'].font = Font(bold=True, size=13, color='FFFFFF')
        ws['A1'].fill = PatternFill('solid', fgColor='1a3a6b')
        ws['A1'].alignment = Alignment(horizontal='center')
        ws.row_dimensions[1].height = 22

        # Header row
        headers = ['Timestamp', 'User', 'Role', 'Category', 'Action', 'Description', 'IP Address']
        hdr_fill = PatternFill('solid', fgColor='2c5282')
        for ci, h in enumerate(headers, start=1):
            cell = ws.cell(row=2, column=ci, value=h)
            cell.font      = Font(bold=True, color='FFFFFF', name='Calibri', size=10)
            cell.fill      = hdr_fill
            cell.alignment = Alignment(horizontal='center', vertical='center')

        col_widths = [22, 18, 10, 14, 28, 70, 14]
        for ci, w in enumerate(col_widths, start=1):
            ws.column_dimensions[ws.cell(row=2, column=ci).column_letter].width = w

        # Data rows
        for ri, log in enumerate(logs, start=3):
            ws.cell(row=ri, column=1, value=log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else '')
            ws.cell(row=ri, column=2, value=log.user_name or '')
            ws.cell(row=ri, column=3, value=(log.user_role or '').title())
            ws.cell(row=ri, column=4, value=(log.category or '').title())
            ws.cell(row=ri, column=5, value=log.action or '')
            ws.cell(row=ri, column=6, value=log.description or '')
            ws.cell(row=ri, column=7, value=log.ip_address or '')
            # Alternate row shading
            if ri % 2 == 0:
                fill = PatternFill('solid', fgColor='EBF0FA')
                for ci in range(1, 8):
                    ws.cell(row=ri, column=ci).fill = fill

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return send_file(buf,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True,
                         download_name=f'{filename_base}.xlsx')

    # ── PDF export ────────────────────────────────────────────────────────────
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    navy   = colors.HexColor('#1a3a6b')
    light  = colors.HexColor('#EBF0FA')

    title_style = ParagraphStyle('title', parent=styles['Title'],
                                 fontSize=14, textColor=navy, spaceAfter=4)
    sub_style   = ParagraphStyle('sub', parent=styles['Normal'],
                                 fontSize=8, textColor=colors.grey, spaceAfter=8)
    cell_style  = ParagraphStyle('cell', parent=styles['Normal'], fontSize=7, leading=9)

    elements = [
        Paragraph('LSPU ScholarHub — Audit Log', title_style),
        Paragraph(f'Generated: {generated}  |  Total entries: {len(logs)}'
                  + (f'  |  Filter: category={category}' if category else '')
                  + (f', search="{q}"' if q else ''), sub_style),
        Spacer(1, 0.3*cm),
    ]

    col_widths_pdf = [3.8*cm, 2.8*cm, 1.6*cm, 2.2*cm, 4.0*cm, 11.0*cm, 2.2*cm]
    table_data = [['Timestamp', 'User', 'Role', 'Category', 'Action', 'Description', 'IP']]

    for log in logs:
        table_data.append([
            Paragraph(log.timestamp.strftime('%Y-%m-%d\n%H:%M:%S') if log.timestamp else '', cell_style),
            Paragraph(log.user_name or '', cell_style),
            Paragraph((log.user_role or '').title(), cell_style),
            Paragraph((log.category or '').title(), cell_style),
            Paragraph(log.action or '', cell_style),
            Paragraph((log.description or '')[:200], cell_style),
            Paragraph(log.ip_address or '', cell_style),
        ])

    tbl = Table(table_data, colWidths=col_widths_pdf, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (-1,0), navy),
        ('TEXTCOLOR',   (0,0), (-1,0), colors.white),
        ('FONTNAME',    (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',    (0,0), (-1,0), 8),
        ('ALIGN',       (0,0), (-1,0), 'CENTER'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, light]),
        ('FONTSIZE',    (0,1), (-1,-1), 7),
        ('VALIGN',      (0,0), (-1,-1), 'TOP'),
        ('GRID',        (0,0), (-1,-1), 0.3, colors.HexColor('#CBD5E0')),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING',(0,0), (-1,-1), 4),
        ('TOPPADDING',  (0,0), (-1,-1), 3),
        ('BOTTOMPADDING',(0,0),(-1,-1), 3),
    ]))
    elements.append(tbl)
    doc.build(elements)
    buf.seek(0)
    return send_file(buf, mimetype='application/pdf',
                     as_attachment=True,
                     download_name=f'{filename_base}.pdf')


# ── Scheduled Reminders (manual trigger) ─────────────────────────────────────

@admin_bp.route('/reminders/run', methods=['POST'])
@role_required('admin')
def run_reminders():
    """
    Manually trigger all pending reminders:
    1. Deadline reminders — scholarships closing within 7 days
    2. Renewal reminders  — scholars whose 1-year renewal is within 30 days
    3. Performance alerts — approved scholars with GWA > 3.00 who haven't been notified
    """
    from datetime import timedelta
    from app.services.notification_service import notification_service
    from app.services.audit_service import log_action

    sent_deadline = sent_renewal = sent_performance = 0

    # ── 1. Deadline reminders ─────────────────────────────────────────────────
    deadline_window = datetime.utcnow() + timedelta(days=7)
    closing_soon = Scholarship.query.filter(
        Scholarship.status == ScholarshipStatus.ACTIVE,
        Scholarship.application_deadline <= deadline_window,
        Scholarship.application_deadline >= datetime.utcnow(),
    ).all()

    for s in closing_soon:
        # Notify students who have pending applications for this scholarship
        pending_apps = ScholarshipApplication.query.filter_by(
            scholarship_id=s.id,
            status=ApplicationStatus.PENDING,
        ).all()
        days_left = (s.application_deadline - datetime.utcnow()).days
        for app in pending_apps:
            student = app.applicant
            notification_service.create_in_app_notification(
                student.id,
                f'Deadline Reminder: {s.title}',
                f'The application deadline for {s.title} is in {days_left} day(s) '
                f'({s.application_deadline.strftime("%b %d, %Y")}). Make sure your application is complete.',
                'deadline',
            )
            sent_deadline += 1

    # ── 2. Renewal reminders ──────────────────────────────────────────────────
    all_approved = ScholarshipApplication.query.filter_by(
        status=ApplicationStatus.APPROVED).all()
    for app in all_approved:
        if not app.approved_at:
            continue
        renewal_due = app.approved_at + timedelta(days=365)
        days_left   = (renewal_due - datetime.utcnow()).days
        if 0 <= days_left <= 30:
            # Only send if not already notified in the last 7 days
            if (app.renewal_notified_at and
                    (datetime.utcnow() - app.renewal_notified_at).days < 7):
                continue
            student = app.applicant
            notification_service.send_email(
                student.email,
                'LSPU ScholarHub — Scholarship Renewal Reminder',
                f'<h2>📋 Renewal Reminder</h2>'
                f'<p>Dear <strong>{student.get_full_name()}</strong>,</p>'
                f'<p>Your scholarship <strong>{app.scholarship.title}</strong> '
                f'renewal is due in <strong>{days_left} day(s)</strong> '
                f'({renewal_due.strftime("%B %d, %Y")}).</p>'
                f'<p>Please visit the scholarship office to submit renewal documents.</p>'
                f'<p>Best regards,<br><strong>LSPU Scholarship Office</strong></p>',
            )
            notification_service.create_in_app_notification(
                student.id,
                'Scholarship Renewal Reminder',
                f'{app.scholarship.title} renewal due in {days_left} days.',
                'deadline',
            )
            app.renewal_notified_at = datetime.utcnow()
            sent_renewal += 1

    # ── 3. Performance alerts ─────────────────────────────────────────────────
    at_risk_scholars = [
        a for a in all_approved
        if a.applicant.gwa and a.applicant.gwa > 3.00
        and a.scholar_status in ('active', None, '')
    ]
    for app in at_risk_scholars:
        student    = app.applicant
        new_status = ('termination_warning' if student.gwa >= 4.00
                      else 'probation' if student.gwa > 3.75
                      else 'at_risk')
        app.scholar_status    = new_status
        app.status_updated_at = datetime.utcnow()
        notification_service.create_in_app_notification(
            student.id,
            '⚠️ Performance Alert',
            f'Your GWA ({student.gwa}) requires attention. '
            f'Please contact the scholarship office.',
            'performance',
        )
        sent_performance += 1

    # ── 4. GWA pending reminders ──────────────────────────────────────────────
    # Notify approved scholars who have no GWA recorded yet
    sent_gwa_reminder = 0
    pending_gwa_scholars = [
        a for a in all_approved
        if a.applicant.gwa is None and a.is_active
    ]
    for app in pending_gwa_scholars:
        student = app.applicant
        notification_service.create_in_app_notification(
            student.id,
            '📋 GWA Upload Reminder',
            f'Your GWA for {app.scholarship.title} has not been recorded yet. '
            f'Please upload your Copy of Grades under My Profile → Upload Grades.',
            'deadline',
        )
        notification_service.send_email(
            student.email,
            'LSPU ScholarHub — Please Upload Your Copy of Grades',
            f'<h2>📋 GWA Upload Reminder</h2>'
            f'<p>Dear <strong>{student.get_full_name()}</strong>,</p>'
            f'<p>Your GWA for scholarship <strong>{app.scholarship.title}</strong> '
            f'has not been recorded yet.</p>'
            f'<p>Please log in to ScholarHub and upload your official Copy of Grades (PDF) '
            f'under <strong>My Profile → Upload Copy of Grades</strong>.</p>'
            f'<p>This is required to maintain your scholarship status.</p>'
            f'<p>Best regards,<br><strong>LSPU Scholarship Office</strong></p>',
        )
        sent_gwa_reminder += 1

    db.session.commit()

    log_action('system.reminders',
               f'Manual reminders run: {sent_deadline} deadline, '
               f'{sent_renewal} renewal, {sent_performance} performance, '
               f'{sent_gwa_reminder} GWA pending alerts sent.',
               category='system')

    flash(
        f'Reminders sent — '
        f'{sent_deadline} deadline alert(s), '
        f'{sent_renewal} renewal reminder(s), '
        f'{sent_performance} performance alert(s), '
        f'{sent_gwa_reminder} GWA pending reminder(s).',
        'success'
    )
    return redirect(url_for('admin.audit_log'))


# ── Batch Management ──────────────────────────────────────────────────────────

@admin_bp.route('/batches')
@role_required('admin')
def manage_batches():
    """View and manage scholarship batches."""
    from app.models import AcademicPeriod, ScholarshipBatch

    scholarship_id = request.args.get('scholarship_id', '', type=str)
    period_id      = request.args.get('period_id', '', type=str)

    current_period = get_viewing_period()
    periods        = AcademicPeriod.query.order_by(AcademicPeriod.id.desc()).all()

    # Strict campus scoping (super admin honors campus selector)
    campus_ctx = session.get('campus_context') if session.get('user_type') == 'super_admin' else None
    if campus_ctx is None and session.get('user_type') != 'super_admin':
        _me = db.session.get(User, session.get('user_id'))
        campus_ctx = _me.campus_id if _me else None

    _sch_q = Scholarship.query.order_by(Scholarship.title)
    if campus_ctx:
        _sch_q = _sch_q.filter(db.or_(Scholarship.campus_id == campus_ctx,
                                      Scholarship.campus_id.is_(None)))
    scholarships   = _sch_q.all()

    query = ScholarshipBatch.query
    if campus_ctx:
        query = query.filter(ScholarshipBatch.campus_id == campus_ctx)
    if scholarship_id:
        query = query.filter_by(scholarship_id=int(scholarship_id))
    if period_id:
        query = query.filter_by(academic_period_id=int(period_id))
    elif current_period:
        query = query.filter_by(academic_period_id=current_period.id)

    batches = query.order_by(ScholarshipBatch.scholarship_id, ScholarshipBatch.batch_number).all()

    return render_template(
        'admin/batches.html',
        batches=batches,
        scholarships=scholarships,
        periods=periods,
        current_period=current_period,
        scholarship_id=scholarship_id,
        period_id=period_id,
    )


@admin_bp.route('/batches/create', methods=['POST'])
@role_required('admin')
def create_batch():
    """Create a new batch for a scholarship."""
    from app.models import AcademicPeriod, ScholarshipBatch

    scholarship_id = request.form.get('scholarship_id', type=int)
    period_id      = request.form.get('academic_period_id', type=int)
    batch_name     = request.form.get('batch_name', '').strip()
    amount         = request.form.get('amount_per_scholar', '').strip()

    if not scholarship_id or not period_id:
        flash('Scholarship and academic period are required.', 'error')
        return redirect(url_for('admin.manage_batches'))

    _s = db.session.get(Scholarship, scholarship_id)
    if not _s:
        flash('Scholarship program not found.', 'error')
        return redirect(url_for('admin.manage_batches'))
    _err = _scholarship_campus_guard(_s)
    if _err:
        return _err

    # Auto-suggest name if not provided
    if not batch_name:
        batch_name, batch_number = ScholarshipBatch.suggest_next_batch_name(scholarship_id, period_id)
    else:
        # Parse batch number from name (e.g. "Batch 1.1" → 1.1)
        import re
        nums = re.findall(r'[\d.]+', batch_name)
        batch_number = float(nums[-1]) if nums else 1.0

    try:
        batch = ScholarshipBatch(
            scholarship_id=scholarship_id,
            academic_period_id=period_id,
            batch_name=batch_name,
            batch_number=batch_number,
            amount_per_scholar=max(0, float(amount)) if amount else None,
            created_by=session['user_id'],
        )
        db.session.add(batch)
        db.session.commit()

        from app.services.audit_service import log_action
        s = Scholarship.query.get(scholarship_id)
        log_action('batch.create',
                   f'Admin {session.get("username")} created "{batch_name}" for '
                   f'"{s.title}" (amount: ₱{amount or "TBD"}/scholar).',
                   category='scholarship', target_type='scholarship', target_id=scholarship_id)

        flash(f'Batch "{batch_name}" created successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating batch: {e}', 'error')

    return redirect(url_for('admin.manage_batches', scholarship_id=scholarship_id))


@admin_bp.route('/batches/<int:batch_id>/edit', methods=['POST'])
@role_required('admin')
def edit_batch(batch_id):
    """Edit batch name, amount, or status."""
    from app.models import ScholarshipBatch

    batch = ScholarshipBatch.query.get_or_404(batch_id)
    batch.batch_name = request.form.get('batch_name', batch.batch_name).strip()
    amount = request.form.get('amount_per_scholar', '').strip()
    if amount:
        batch.amount_per_scholar = max(0, float(amount))
    status = request.form.get('status', '')
    if status in ('open', 'closed', 'finalized'):
        batch.status = status
    batch.notes = request.form.get('notes', batch.notes)

    # Recalculate totals
    batch.recalculate_totals()
    db.session.commit()

    flash(f'Batch "{batch.batch_name}" updated.', 'success')
    return redirect(url_for('admin.manage_batches', scholarship_id=batch.scholarship_id))


@admin_bp.route('/batches/<int:batch_id>/assign', methods=['POST'])
@role_required('admin')
def assign_to_batch(batch_id):
    """Assign approved applications to a batch."""
    from app.models import ScholarshipBatch

    batch   = ScholarshipBatch.query.get_or_404(batch_id)
    app_ids = request.form.getlist('app_ids')

    if not app_ids:
        flash('No applications selected.', 'error')
        return redirect(url_for('admin.manage_batches', scholarship_id=batch.scholarship_id))

    assigned = 0
    for app_id in app_ids:
        app = ScholarshipApplication.query.get(int(app_id))
        if app and app.status == ApplicationStatus.APPROVED:
            app.batch_id = batch_id
            app.amount_received = batch.amount_per_scholar
            assigned += 1

    # Recalculate batch totals
    batch.recalculate_totals()
    db.session.commit()

    from app.services.audit_service import log_action
    log_action('batch.assign',
               f'Admin {session.get("username")} assigned {assigned} scholar(s) to '
               f'"{batch.batch_name}" ({batch.scholarship.title}).',
               category='scholarship', target_type='scholarship', target_id=batch.scholarship_id)

    flash(f'{assigned} scholar(s) assigned to "{batch.batch_name}".', 'success')
    return redirect(url_for('admin.manage_batches', scholarship_id=batch.scholarship_id))


@admin_bp.route('/batches/<int:batch_id>/delete', methods=['POST'])
@role_required('admin')
def delete_batch(batch_id):
    """Delete a batch (unassigns all applications from it)."""
    from app.models import ScholarshipBatch

    batch = ScholarshipBatch.query.get_or_404(batch_id)
    name  = batch.batch_name
    sid   = batch.scholarship_id

    # Unassign all applications
    for app in batch.applications:
        app.batch_id = None
        app.seq_number = None

    db.session.delete(batch)
    db.session.commit()

    from app.services.audit_service import log_action
    log_action('batch.delete',
               f'Admin {session.get("username")} deleted batch "{name}".',
               category='scholarship', target_type='scholarship', target_id=sid)

    flash(f'Batch "{name}" deleted.', 'success')
    return redirect(url_for('admin.manage_batches', scholarship_id=sid))


@admin_bp.route('/batches/suggest-name')
@role_required('admin')
def suggest_batch_name():
    """AJAX endpoint: suggest the next batch name for a scholarship+period."""
    from app.models import ScholarshipBatch

    scholarship_id = request.args.get('scholarship_id', type=int)
    period_id      = request.args.get('period_id', type=int)

    if not scholarship_id or not period_id:
        return jsonify({'name': 'Batch 1', 'number': 1.0})

    name, number = ScholarshipBatch.suggest_next_batch_name(scholarship_id, period_id)
    return jsonify({'name': name, 'number': number})


@admin_bp.route('/batches/<int:batch_id>/export')
@role_required('admin')
def export_batch(batch_id):
    """Export a batch as Excel in the same format as the LSPU summary report."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from app.models import ScholarshipBatch

    batch = ScholarshipBatch.query.get_or_404(batch_id)
    apps  = [a for a in batch.applications if a.status and a.status.value == 'approved']

    wb = Workbook()
    ws = wb.active
    ws.title = batch.batch_name[:31]  # Excel sheet name max 31 chars

    # Title rows
    ws.merge_cells('A1:O1')
    ws['A1'] = 'Republic of the Philippines\nLaguna State Polytechnic University\nProvince of Laguna\nSanta Cruz Campus'
    ws['A1'].font = Font(bold=True, size=10)
    ws['A1'].alignment = Alignment(horizontal='center', wrap_text=True)
    ws.row_dimensions[1].height = 50

    ws.merge_cells('A3:O3')
    ws['A3'] = 'SUMMARY OF SCHOLARSHIP AND FINANCIAL ASSISTANCE'
    ws['A3'].font = Font(bold=True, size=11)
    ws['A3'].alignment = Alignment(horizontal='center')

    ws.merge_cells('A4:O4')
    period_name = batch.academic_period.display_name if batch.academic_period else ''
    ws['A4'] = period_name
    ws['A4'].alignment = Alignment(horizontal='center')

    ws.merge_cells('A6:O6')
    ws['A6'] = f'{batch.scholarship.title}'
    ws['A6'].font = Font(bold=True, size=10)

    ws.merge_cells('A7:O7')
    ws['A7'] = batch.batch_name.upper()
    ws['A7'].font = Font(bold=True)

    # Headers (row 9) — matching the Excel reference
    headers = ['Seq. No.', 'Student ID No.', 'Last Name', 'First Name', 'Middle Name',
               'Program Name', 'Year', 'Total Units Enrolled', 'GWA',
               'Town', 'Province', 'Male', 'Female', 'Amount', 'Remarks']

    hdr_fill = PatternFill('solid', fgColor='1a3a6b')
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    for ci, h in enumerate(headers, start=1):
        cell = ws.cell(row=9, column=ci, value=h)
        cell.font      = Font(bold=True, color='FFFFFF', size=9)
        cell.fill      = hdr_fill
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border    = thin_border

    # Column widths
    col_widths = [8, 14, 18, 18, 16, 40, 6, 8, 6, 14, 12, 6, 6, 12, 14]
    for ci, w in enumerate(col_widths, start=1):
        ws.column_dimensions[ws.cell(row=9, column=ci).column_letter].width = w

    # Data rows
    total_male = total_female = 0
    total_amount = 0

    for seq, app in enumerate(apps, start=1):
        student = app.applicant
        row = seq + 9  # data starts at row 10

        is_male   = 1 if student.gender == 'Male' else ''
        is_female = 1 if student.gender == 'Female' else ''
        if student.gender == 'Male':   total_male += 1
        if student.gender == 'Female': total_female += 1
        amount = float(app.amount_received or batch.amount_per_scholar or 0)
        total_amount += amount

        data = [
            seq,
            student.student_id or '',
            student.last_name or '',
            student.first_name or '',
            student.middle_name or '',
            student.course or '',
            student.year_level.replace(' Year', '') if student.year_level else '',
            student.units_enrolled or '',
            student.gwa or '',
            student.town or '',
            student.province or '',
            is_male,
            is_female,
            amount,
            '',
        ]
        for ci, val in enumerate(data, start=1):
            cell = ws.cell(row=row, column=ci, value=val)
            cell.border = thin_border
            cell.font   = Font(size=9)

    # Total row
    total_row = len(apps) + 10
    ws.cell(row=total_row, column=1, value='Total').font = Font(bold=True, size=9)
    ws.cell(row=total_row, column=12, value=total_male).font = Font(bold=True, size=9)
    ws.cell(row=total_row, column=13, value=total_female).font = Font(bold=True, size=9)
    ws.cell(row=total_row, column=14, value=total_amount).font = Font(bold=True, size=9)
    for ci in range(1, 16):
        ws.cell(row=total_row, column=ci).border = thin_border

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = f'{batch.scholarship.title[:20]}_{batch.batch_name}_{period_name[:20]}.xlsx'.replace(' ', '_')
    return send_file(buf,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=filename)


@admin_bp.route('/batches/<int:batch_id>')
@role_required('admin')
def batch_detail(batch_id):
    """View the list of scholars assigned to a specific batch."""
    from app.models import ScholarshipBatch
    batch = ScholarshipBatch.query.get_or_404(batch_id)
    applications = [
        a for a in batch.applications
        if a.status and a.status.value == 'approved'
    ]
    applications.sort(key=lambda a: (a.applicant.last_name or '').lower())
    return render_template('admin/batch_detail.html',
                           batch=batch, applications=applications)


# ── Temporary email test route (admin only) ───────────────────────────────────

@admin_bp.route('/test-email')
@role_required('admin')
def test_email():
    """Test email configuration — visit /admin/test-email to check."""
    import os
    from flask import jsonify
    from app.services.notification_service import notification_service

    admin_user = User.query.filter_by(user_type='admin').first()
    test_to = admin_user.email if admin_user else 'test@example.com'

    result = notification_service.send_email(
        test_to,
        'LSPU ScholarHub — Test Email',
        '<h2>Test email works!</h2><p>Email configuration is correct.</p>',
    )

    return jsonify({
        'sent_to':      test_to,
        'result':       result,
        'BREVO_API_KEY': 'SET' if os.environ.get('BREVO_API_KEY') else 'NOT SET',
        'MAIL_SERVER':   os.environ.get('MAIL_SERVER', 'NOT SET'),
        'MAIL_USERNAME': os.environ.get('MAIL_USERNAME', 'NOT SET'),
    })


# ── Monitoring & Evaluation form submissions ────────────────────────────────

@admin_bp.route('/monitoring/<int:app_id>/me-form')
@role_required('admin')
def view_me_form(app_id):
    """Admin views the scholar's submitted M&E form inline."""
    from app.models import MonitoringSubmission
    from app.services.storage_service import get_signed_url

    subs = (MonitoringSubmission.query
            .filter_by(application_id=app_id)
            .order_by(MonitoringSubmission.uploaded_at.desc()).all())
    if not subs:
        flash('No Monitoring & Evaluation form submitted yet for this scholar.', 'warning')
        return redirect(url_for('admin.monitoring'))
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
    return redirect(url_for('admin.monitoring'))


@admin_bp.route('/settings/me-deadline', methods=['POST'])
@role_required('admin')
def set_me_deadline():
    """Set/clear the M&E form submission deadline for the current period."""
    if session.get('user_type') != 'super_admin':
        flash('Only the Super Admin can manage periods.', 'error')
        return redirect(url_for('admin.dashboard'))
    from app.models import AcademicPeriod
    period = get_viewing_period()
    if not period:
        flash('Create a current academic period first.', 'warning')
        return redirect(url_for('admin.settings'))

    if request.form.get('clear'):
        period.me_form_deadline = None
        db.session.commit()
        from app.services.audit_service import log_action
        log_action('settings.me_deadline_clear', 'Cleared M&E form deadline')
        flash('M&E form deadline cleared.', 'success')
        return redirect(url_for('admin.settings'))

    raw = request.form.get('me_form_deadline', '').strip()
    if not raw:
        flash('Please choose a date.', 'warning')
        return redirect(url_for('admin.settings'))
    try:
        period.me_form_deadline = datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date.', 'error')
        return redirect(url_for('admin.settings'))
    db.session.commit()
    from app.services.audit_service import log_action
    log_action('settings.me_deadline_set', f'M&E form deadline set to {raw}')
    flash('M&E form deadline saved.', 'success')
    return redirect(url_for('admin.settings'))

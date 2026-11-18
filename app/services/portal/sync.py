"""Portal → ScholarHub student synchronisation.

The portal owns *who a student is* (identity, course, year level, campus, GWA,
units, enrollment status).  ScholarHub owns *what they applied for*.  This
module is the only place portal data is written into ScholarHub, so every
change can be dry-run, audited and replayed.

Decisions this implements (agreed with the scholarship office):

* Student accounts are matched by **student ID**, never by email — an email
  change in the portal must not create a second person.
* A self-registered account is *upgraded in place* to ``data_source='portal'``
  on the first sync, so its applications and uploaded documents are kept.
* GWA is the portal's per-semester GWA.  Each sync also appends to
  ``gwa_history`` so the trend survives even when the snapshot changes.
* Graduated / dropped-out students are applied through
  ``student_status_service`` so their active scholarships are closed exactly
  like a manual status change.
* Nothing is ever deleted.  The one-time cut-over archives legacy accounts
  (``is_archived``) without touching their history.
* Idempotent: a second run over unchanged portal data writes nothing.
* One bad record never aborts a run; it is counted as failed with the student
  ID only (no PII in the error text).

Freshness: run it often (webhook, schedule) or let ``refresh_on_login`` catch
a student up when their cached copy is older than PORTAL_FRESHNESS_MINUTES.
"""
from __future__ import annotations

import logging
import os
import re
import secrets
from datetime import date, datetime, timedelta
from typing import Iterable, Optional

from app import db

log = logging.getLogger(__name__)

# Identity / academic fields the portal owns. Scholarship-side fields
# (student_status is special-cased, is_existing_scholar, documents, ...) are
# never touched by a sync.
PORTAL_OWNED_FIELDS = (
    'first_name', 'last_name', 'middle_name',
    'phone_number', 'gender', 'date_of_birth',
    'town', 'province', 'address',
    'course', 'year_level', 'campus_id',
    'gwa', 'units_enrolled',
)

DETAIL_LIMIT = 200


# ── Helpers ─────────────────────────────────────────────────────────────────

def _truthy(value) -> bool:
    return str(value or '').strip().lower() in ('1', 'true', 'yes', 'on')


def is_enabled() -> bool:
    """True when the portal integration is switched on for this deployment."""
    return _truthy(os.environ.get('PORTAL_ENABLED'))


def freshness_minutes() -> int:
    try:
        return max(1, int(os.environ.get('PORTAL_FRESHNESS_MINUTES', '60')))
    except (TypeError, ValueError):
        return 60


def _norm_word(value: str) -> str:
    txt = str(value or '').lower()
    txt = txt.replace('sta.', 'santa ').replace('sta ', 'santa ')
    txt = txt.replace('city', ' ').replace('campus', ' ')
    return re.sub(r'[^a-z]', '', txt)


def resolve_campus_id(*names) -> Optional[int]:
    """Map a portal campus name/code onto a ScholarHub Campus row."""
    candidates = [n for n in names if n]
    if not candidates:
        return None
    from app.models import Campus

    campuses = Campus.query.all()
    normalised = [(_norm_word(c.name), _norm_word(c.short_name or ''), c.id)
                  for c in campuses]

    for raw in candidates:
        target = _norm_word(raw)
        if not target:
            continue
        for name_norm, short_norm, cid in normalised:
            if target == name_norm or (short_norm and target == short_norm):
                return cid
    for raw in candidates:
        target = _norm_word(raw)
        if not target:
            continue
        for name_norm, short_norm, cid in normalised:
            if name_norm and (target in name_norm or name_norm in target):
                return cid
    return None


def normalise_year_level(value) -> Optional[str]:
    txt = str(value or '').strip()
    if not txt:
        return None
    low = txt.lower()
    if 'irreg' in low:
        return 'Irregular'
    if 'grad' in low:
        return 'Graduate'
    match = re.search(r'([1-6])', low)
    if match:
        num = int(match.group(1))
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(num, 'th')
        return f'{num}{suffix} Year'
    return txt.title()


def normalise_status(value) -> Optional[str]:
    txt = str(value or '').strip().lower()
    if not txt:
        return None
    if 'grad' in txt:
        return 'graduated'
    if any(word in txt for word in ('drop', 'awol', 'inactive', 'loa',
                                    'leave', 'not enrolled', 'unenrolled')):
        return 'dropped_out'
    return 'active'


def _semester_label(record) -> Optional[str]:
    semester = (record.semester or '').strip()
    school_year = (record.school_year or '').strip()
    if not semester:
        return None
    return f'{semester} {school_year}'.strip()


def _match_user(student_id: str):
    """Find the ScholarHub user for a portal student ID (exact, then compact)."""
    from app.models import User

    sid = str(student_id or '').strip()
    if not sid:
        return None

    user = (User.query.filter_by(portal_student_id=sid).first()
            or User.query.filter_by(student_id=sid).first()
            or User.query.filter_by(username=sid).first())
    if user is not None:
        return user

    compact = re.sub(r'[^A-Za-z0-9]', '', sid)
    if compact and compact != sid:
        user = (User.query.filter_by(student_id=compact).first()
                or User.query.filter_by(username=compact).first())
        if user is not None:
            return user
        # MySQL REPLACE covers the usual "0199-0000" / "01990000" split.
        try:
            user = User.query.filter(
                db.func.replace(User.student_id, '-', '') == compact
            ).first()
        except Exception:
            user = None
    return user


def _safe_email(record, student_id: str, current_user=None) -> Optional[str]:
    """Pick a portal email that does not collide with a different account."""
    from app.models import User

    email = (record.email or '').strip().lower()
    if not email:
        return None
    holder = User.query.filter_by(email=email).first()
    if holder is None or (current_user is not None and holder.id == current_user.id):
        return email
    log.warning('Portal email for %s is already used by another ScholarHub '
                'account; keeping the existing email.', student_id)
    return None


# ── Writing one record ──────────────────────────────────────────────────────

def _apply_record(record, dry_run: bool = False):
    """Create or update one student. Returns (action, changed_field_names)."""
    from app.models import User

    sid = str(record.student_id).strip()
    user = _match_user(sid)
    created = False

    if user is None:
        action = 'created'
        if dry_run:
            return action, ['new account']

        email = _safe_email(record, sid) or f'{re.sub(r"[^a-z0-9]", "", sid.lower())}@portal.lspu.edu.ph'
        if User.query.filter_by(username=sid).first():
            return 'skipped', ['username already taken']
        if User.query.filter_by(email=email).first():
            return 'skipped', ['email already taken']

        campus_id = resolve_campus_id(record.campus, record.campus_short)
        user = User(
            username=sid,
            email=email,
            first_name=(record.first_name or 'Student').title(),
            last_name=(record.last_name or sid).title(),
            middle_name=(record.middle_name.title() if record.middle_name else None),
            phone_number=record.phone_number,
            gender=(record.gender.title() if record.gender in ('Male', 'Female') else None),
            date_of_birth=record.date_of_birth,
            town=record.town,
            province=record.province,
            address=record.address,
            student_id=sid,
            course=record.course,
            year_level=normalise_year_level(record.year_level),
            campus_id=campus_id,
            gwa=record.gwa,
            units_enrolled=record.units_enrolled,
            user_type='student',
            is_active=True,
            is_verified=True,          # identity comes from the registrar, not a PDF
            ocr_verified=True,
            student_status=normalise_status(record.student_status) or 'active',
            data_source='portal',
            portal_student_id=sid,
            portal_synced_at=datetime.utcnow(),
        )
        # No usable password: these accounts sign in through portal SSO, or the
        # office issues a temporary password through the normal reset flow.
        user.set_password(secrets.token_urlsafe(32))
        db.session.add(user)
        db.session.flush()          # id needed for the GWA history row below
        created = True
    else:
        action = 'updated'

    changed = []
    if not created:
        values = {
            'first_name': record.first_name.title() if record.first_name else None,
            'last_name': record.last_name.title() if record.last_name else None,
            'middle_name': record.middle_name.title() if record.middle_name else None,
            'phone_number': record.phone_number,
            'gender': (record.gender.title()
                       if str(record.gender or '').title() in ('Male', 'Female') else None),
            'date_of_birth': record.date_of_birth,
            'town': record.town,
            'province': record.province,
            'address': record.address,
            'course': record.course,
            'year_level': normalise_year_level(record.year_level),
            'campus_id': resolve_campus_id(record.campus, record.campus_short),
            'gwa': record.gwa,
            'units_enrolled': record.units_enrolled,
        }
        email = _safe_email(record, sid, current_user=user)
        if email and email != user.email:
            values['email'] = email

        for field_name in PORTAL_OWNED_FIELDS + ('email',):
            if field_name not in values:
                continue
            new_value = values[field_name]
            if new_value is None:
                continue      # never blank out data ScholarHub already has
            if getattr(user, field_name) != new_value:
                setattr(user, field_name, new_value)
                changed.append(field_name)

        if user.portal_student_id != sid:
            user.portal_student_id = sid
            changed.append('portal_student_id')
        if user.data_source != 'portal':
            user.data_source = 'portal'
            changed.append('data_source')
        if user.is_archived:
            user.is_archived = False
            user.is_active = True
            changed.append('reactivated')
        user.portal_synced_at = datetime.utcnow()
        if changed:
            action = 'updated'
        else:
            action = 'unchanged'

    if dry_run:
        return action, changed

    # Per-semester GWA history: keep the trend, not only the latest value.
    if record.gwa is not None:
        _record_gwa_history(user, record)

    # Lifecycle status goes through the single write-point that also closes
    # active scholarships for graduates / drop-outs.
    status = normalise_status(record.student_status)
    if status and (user.student_status or 'active') != status:
        from app.services.student_status_service import set_student_status
        ok, err = set_student_status(user, status)   # commits
        if ok:
            changed.append('student_status')
        elif err:
            log.warning('Could not set status for %s: %s', sid, err)
    else:
        db.session.commit()

    return action, changed


def _record_gwa_history(user, record):
    """Upsert one GwaHistory row for the portal's semester GWA."""
    from app.models import GwaHistory

    semester = (record.semester or 'Current Semester').strip()[:30]
    school_year = (record.school_year or '').strip()[:20] or '—'

    row = GwaHistory.query.filter_by(
        student_id=user.id, semester=semester, school_year=school_year).first()
    if row is None:
        row = GwaHistory(student_id=user.id, semester=semester,
                         school_year=school_year, gwa=record.gwa,
                         notes='LSPU portal sync')
        db.session.add(row)
    elif abs((row.gwa or 0) - record.gwa) > 0.0001:
        row.gwa = record.gwa
        row.notes = 'LSPU portal sync (corrected)'


# ── Running a sync ──────────────────────────────────────────────────────────

def _new_run(trigger: str, mode: str) -> Optional['PortalSyncRun']:
    from app.models.portal_sync import PortalSyncRun

    if trigger == 'login' and not _truthy(os.environ.get('PORTAL_LOG_LOGIN_RUNS')):
        return None      # login refreshes are frequent; don't fill the table

    run = PortalSyncRun(trigger=trigger, mode=mode, status='running')
    db.session.add(run)
    db.session.commit()
    return run


def sync_students(student_ids: Optional[Iterable[str]] = None,
                  trigger: str = 'manual',
                  dry_run: bool = False,
                  source=None,
                  file_path: Optional[str] = None) -> dict:
    """Sync every portal student (or just ``student_ids``) into ScholarHub.

    Returns a stats dict; when ``dry_run`` nothing is written.
    """
    from app.services.portal.source import get_portal_source

    ids = [str(i).strip() for i in (student_ids or []) if str(i).strip()]
    if source is None:
        kwargs = {}
        if file_path:
            kwargs['path'] = file_path
        source = get_portal_source(**kwargs)

    run = None if dry_run else _new_run(trigger, source.mode)

    stats = {'seen': 0, 'created': 0, 'updated': 0, 'unchanged': 0,
             'skipped': 0, 'failed': 0}
    details = []
    error = None

    try:
        records = source.fetch_many(ids) if ids else source.fetch_all()
        if ids and len(records) != len(ids):
            missing = set(ids) - {r.student_id for r in records}
            if missing:
                log.info('Portal has no record for: %s', ', '.join(sorted(missing)))

        for record in records:
            stats['seen'] += 1
            try:
                action, changed = _apply_record(record, dry_run=dry_run)
                stats[action] = stats.get(action, 0) + 1
                if len(details) < DETAIL_LIMIT:
                    details.append({'student_id': str(record.student_id),
                                    'action': action, 'fields': changed})
            except Exception as exc:
                db.session.rollback()
                stats['failed'] += 1
                log.exception('Portal sync failed for %s', record.student_id)
                if len(details) < DETAIL_LIMIT:
                    details.append({'student_id': str(record.student_id),
                                    'action': 'failed',
                                    'error': type(exc).__name__})
    except Exception as exc:
        db.session.rollback()
        error = f'{type(exc).__name__}: {exc}'
        log.exception('Portal sync aborted')
    finally:
        dispose = getattr(source, 'dispose', None)
        if callable(dispose):
            try:
                dispose()
            except Exception:
                pass

    if run is not None:
        run.finished_at = datetime.utcnow()
        run.seen = stats['seen']
        run.created = stats['created']
        run.updated = stats['updated']
        run.unchanged = stats['unchanged']
        run.skipped = stats['skipped']
        run.failed = stats['failed']
        run.error = error
        run.set_details(details)
        if error:
            run.status = 'failed'
        elif stats['failed']:
            run.status = 'partial'
        else:
            run.status = 'success'
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    result = dict(stats)
    result.update({'dry_run': dry_run, 'trigger': trigger,
                   'run_id': run.id if run is not None else None,
                   'error': error})
    return result


def sync_one(student_id: str, trigger: str = 'manual', dry_run: bool = False) -> dict:
    return sync_students([student_id], trigger=trigger, dry_run=dry_run)


# ── Login hook ──────────────────────────────────────────────────────────────

def refresh_on_login(user) -> Optional[dict]:
    """Refresh one student at login when their copy is older than the window.

    Best-effort: never raises, never blocks a login for longer than one query.
    """
    if not is_enabled():
        return None
    if getattr(user, 'user_type', None) != 'student':
        return None
    if getattr(user, 'is_archived', False):
        return None

    synced_at = getattr(user, 'portal_synced_at', None)
    if synced_at and (datetime.utcnow() - synced_at) < timedelta(minutes=freshness_minutes()):
        return None

    student_id = getattr(user, 'student_id', None) or getattr(user, 'portal_student_id', None)
    if not student_id:
        return None

    try:
        return sync_one(student_id, trigger='login')
    except Exception:
        log.exception('Portal refresh on login failed for %s', student_id)
        return None


# ── Registration hook ───────────────────────────────────────────────────────

def lookup_for_registration(student_id: str):
    """Portal record for a student ID, or None.

    Used so a student the portal already knows skips the COR/grades OCR flow.
    Any portal failure returns None, which keeps the existing document flow as
    the fallback — registration must never depend on portal uptime.
    """
    if not is_enabled():
        return None
    sid = str(student_id or '').strip()
    if not sid:
        return None
    try:
        from app.services.portal.source import get_portal_source
        source = get_portal_source()
        try:
            return source.fetch_one(sid)
        finally:
            dispose = getattr(source, 'dispose', None)
            if callable(dispose):
                dispose()
    except Exception as exc:
        log.warning('Portal lookup unavailable for registration (%s).', type(exc).__name__)
        return None


# ── One-time cut-over ───────────────────────────────────────────────────────

def archive_legacy_students(dry_run: bool = True, actor_id: Optional[int] = None) -> dict:
    """Archive self-registered student accounts at go-live.

    They are deactivated, not deleted: applications, awards and documents stay
    for audit, and the next portal sync can revive any account the portal also
    knows (matched by student ID).
    """
    from app.models import User

    query = User.query.filter(
        User.user_type == 'student',
        User.is_archived.is_(False),
        db.or_(User.portal_student_id.is_(None), User.data_source != 'portal'),
    )
    pending = query.all()
    result = {'candidates': len(pending), 'archived': 0, 'dry_run': dry_run}

    if dry_run:
        result['preview'] = [{'student_id': u.student_id or u.username,
                              'name': u.get_full_name()} for u in pending[:50]]
        return result

    for user in pending:
        user.is_archived = True
        user.is_active = False
    db.session.commit()
    result['archived'] = len(pending)

    try:
        from app.services.audit_service import log_action
        log_action('portal.legacy_archive',
                   f'Archived {len(pending)} self-registered student account(s) '
                   f'at portal cut-over. Applications and documents retained.',
                   category='user', user_id=actor_id)
    except Exception:
        pass
    return result


# ── Readiness snapshot ──────────────────────────────────────────────────────

def portal_status() -> dict:
    """Everything the office/ICTS needs to see whether the link is healthy."""
    from app.models import User
    from app.models.portal_sync import PortalSyncRun

    status = {
        'enabled': is_enabled(),
        'freshness_minutes': freshness_minutes(),
        'source': (os.environ.get('PORTAL_SOURCE') or '').lower() or None,
        'configured': False,
        'configuration_error': None,
        'recent_runs': [],
        'last_run': None,
        'counts': {},
    }

    try:
        from app.services.portal.source import get_portal_source
        source = get_portal_source()
        status['source'] = source.mode
        status['configured'] = True
        dispose = getattr(source, 'dispose', None)
        if callable(dispose):
            dispose()
    except Exception as exc:
        status['configuration_error'] = str(exc)

    try:
        status['counts'] = {
            'students': User.query.filter_by(user_type='student').count(),
            'from_portal': User.query.filter_by(user_type='student',
                                                data_source='portal').count(),
            'self_registered': User.query.filter_by(user_type='student',
                                                    data_source='self_registered').count(),
            'archived': User.query.filter_by(user_type='student',
                                             is_archived=True).count(),
            'missing_portal_id': User.query.filter(
                User.user_type == 'student',
                User.portal_student_id.is_(None)).count(),
        }
    except Exception as exc:
        status['counts_error'] = str(exc)

    try:
        runs = (PortalSyncRun.query.order_by(PortalSyncRun.id.desc()).limit(5).all())
        status['recent_runs'] = [r.to_dict() for r in runs]
        status['last_run'] = runs[0].to_dict() if runs else None
    except Exception:
        pass

    return status

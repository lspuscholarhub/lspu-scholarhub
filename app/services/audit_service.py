"""
Audit Service — thin wrapper that writes AuditLog rows.
Call log_action() from any view after a significant operation.
"""
import logging
from flask import request, session
from app import db
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def log_action(action: str, description: str, category: str = 'general',
               target_type: str = None, target_id: int = None,
               user_id: int = None, user_name: str = None, user_role: str = None):
    """
    Write one audit log entry.

    Parameters
    ----------
    action      : short machine-readable key  e.g. 'application.approve'
    description : human-readable sentence     e.g. 'Approved application #12 for DOST Scholarship'
    category    : auth | application | scholarship | user | gwa | document | system
    target_type : optional — 'application' | 'scholarship' | 'user' | 'document'
    target_id   : optional — PK of the affected record
    user_id / user_name / user_role : override session values (useful in background tasks)
    """
    try:
        uid   = user_id   or session.get('user_id')
        uname = user_name or session.get('username', 'system')
        urole = user_role or session.get('user_type', 'system')

        try:
            ip = request.remote_addr
        except RuntimeError:
            ip = None   # outside request context

        entry = AuditLog(
            user_id     = uid,
            user_name   = uname,
            user_role   = urole,
            action      = action,
            category    = category,
            description = description,
            target_type = target_type,
            target_id   = target_id,
            ip_address  = ip,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as e:
        logger.warning(f'Audit log failed (non-fatal): {e}')
        try:
            db.session.rollback()
        except Exception:
            pass

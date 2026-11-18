"""LSPU portal integration (read-only student data).

ScholarHub reads student identity and academic data from the university
portal's read-only replica (or a SQL export while that access is arranged) and
keeps owning scholarship records itself.

    from app.services.portal import (
        is_enabled, sync_students, refresh_on_login,
        lookup_for_registration, portal_status,
    )

See docs/PORTAL_INTEGRATION.md for the ICTS handover specification.
"""
from app.services.portal.source import (
    PortalConfigError,
    PortalNotConfigured,
    PortalStudent,
    PortalSource,
    SqlPortalSource,
    FilePortalSource,
    get_portal_source,
)
from app.services.portal.sync import (
    archive_legacy_students,
    freshness_minutes,
    is_enabled,
    lookup_for_registration,
    portal_status,
    refresh_on_login,
    resolve_campus_id,
    sync_one,
    sync_students,
)

__all__ = [
    'PortalConfigError', 'PortalNotConfigured', 'PortalStudent', 'PortalSource',
    'SqlPortalSource', 'FilePortalSource', 'get_portal_source',
    'archive_legacy_students', 'freshness_minutes', 'is_enabled',
    'lookup_for_registration', 'portal_status', 'refresh_on_login',
    'resolve_campus_id', 'sync_one', 'sync_students',
]

"""Read-only adapters that read student records from the LSPU student portal.

ScholarHub never writes to the portal.  Two adapters implement the same tiny
interface so the rest of the app does not care which one ICTS ends up giving
us:

    SqlPortalSource   a SELECT-only view on the ICTS replica / direct SQL
                      login.  The connection is opened read-only and the
                      query is refused unless it is a single SELECT/WITH.
    FilePortalSource  a CSV / JSON export of the same view.  This is the
                      interim path (ICTS can export today) and the way the
                      sync is tested locally.

Both return ``PortalStudent`` objects, so ``sync.py`` only sees normalised
values.

Configuration (all optional until ICTS delivers access):

    PORTAL_ENABLED=true
    PORTAL_SOURCE=sql|file          (default: sql if PORTAL_DSN is set)
    PORTAL_DSN=mysql+pymysql://ro_user:...@host/lspu_portal
    PORTAL_STUDENTS_VIEW=portal_students
    PORTAL_STUDENT_QUERY="SELECT ... FROM ..."   (overrides the view)
    PORTAL_ID_COLUMN=student_id
    PORTAL_EXPORT_FILE=path/to/portal_students.csv

Credentials belong in the host's environment variables, never in the repo.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Iterable, Optional

log = logging.getLogger(__name__)


class PortalNotConfigured(RuntimeError):
    """Raised when portal access has not been set up yet (the normal state)."""


class PortalConfigError(RuntimeError):
    """Raised when portal access is misconfigured or unsafe."""


# ── Normalised record ────────────────────────────────────────────────────────

@dataclass
class PortalStudent:
    """One student as the portal knows them.

    ``student_id`` is the join key with ScholarHub.  Everything else is
    optional so a partial view still syncs what it has.
    """
    student_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    town: Optional[str] = None
    province: Optional[str] = None
    address: Optional[str] = None
    course: Optional[str] = None
    year_level: Optional[str] = None
    campus: Optional[str] = None
    campus_short: Optional[str] = None
    gwa: Optional[float] = None
    units_enrolled: Optional[int] = None
    student_status: Optional[str] = None
    semester: Optional[str] = None
    school_year: Optional[str] = None
    extra: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


# ── Column normalisation ────────────────────────────────────────────────────
# Portal table/view column names are unknown until ICTS publishes the schema,
# so a generous alias table maps common names onto the canonical fields.

_ALIASES = {
    'student_id':      ('student_id', 'studentid', 'student_no', 'student_number',
                        'student_no_', 'stud_id', 'id_no', 'id_number', 'studentidno',
                        'studid'),
    'first_name':      ('first_name', 'firstname', 'given_name', 'fname', 'givenname'),
    'last_name':       ('last_name', 'lastname', 'surname', 'family_name', 'lname'),
    'middle_name':     ('middle_name', 'middlename', 'middle_initial', 'mi', 'mname'),
    'email':           ('email', 'email_address', 'emailaddress', 'lspu_email',
                        'school_email', 'institutional_email'),
    'phone_number':    ('phone_number', 'phone', 'mobile', 'mobile_number',
                        'contact_number', 'cp_number'),
    'gender':          ('gender', 'sex'),
    'date_of_birth':   ('date_of_birth', 'birthdate', 'birthday', 'dob', 'bday'),
    'town':            ('town', 'municipality', 'city', 'city_municipality'),
    'province':        ('province', 'prov'),
    'address':         ('address', 'home_address', 'complete_address',
                        'permanent_address'),
    'course':          ('course', 'program', 'degree_program', 'program_name',
                        'curriculum', 'degree'),
    'year_level':      ('year_level', 'yearlevel', 'year', 'level', 'yr_level'),
    'campus':          ('campus', 'campus_name', 'branch', 'school_campus'),
    'campus_short':    ('campus_short', 'campus_code', 'campus_short_name',
                        'campus_abbr'),
    'gwa':             ('gwa', 'general_weighted_average', 'weighted_average',
                        'semestral_gwa', 'sem_gwa', 'average'),
    'units_enrolled':  ('units_enrolled', 'total_units', 'units', 'enrolled_units',
                        'total_units_enrolled'),
    'student_status':  ('student_status', 'enrollment_status', 'enrolment_status',
                        'academic_status', 'status'),
    'semester':        ('semester', 'term', 'sem', 'current_semester'),
    'school_year':     ('school_year', 'sy', 'academic_year', 'ay',
                        'schoolyear'),
}

_HEADER_TO_FIELD = {}
for _f, _names in _ALIASES.items():
    for _n in _names:
        _HEADER_TO_FIELD[_n] = _f


def _canonical_header(name) -> str:
    txt = str(name or '').strip().lower()
    txt = re.sub(r'[^a-z0-9]+', '_', txt).strip('_')
    return txt


def _field_for_header(name) -> Optional[str]:
    return _HEADER_TO_FIELD.get(_canonical_header(name))


# ── Value cleaning ──────────────────────────────────────────────────────────

def _clean(value) -> Optional[str]:
    if value is None:
        return None
    txt = str(value).strip()
    if not txt or txt.lower() in ('none', 'null', 'n/a', 'na', '-'):
        return None
    return txt


def _parse_float(value) -> Optional[float]:
    txt = _clean(value)
    if txt is None:
        return None
    try:
        num = float(txt.replace(',', ''))
    except (TypeError, ValueError):
        return None
    # GWA is on the LSPU 1.00–5.00 scale; anything else is a parsing mistake.
    if num <= 0 or num > 5:
        return None
    return round(num, 3)


def _parse_int(value) -> Optional[int]:
    txt = _clean(value)
    if txt is None:
        return None
    try:
        return int(float(txt.replace(',', '')))
    except (TypeError, ValueError):
        return None


def _parse_date(value) -> Optional[date]:
    txt = _clean(value)
    if txt is None:
        return None
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y', '%d/%m/%Y',
                '%Y/%m/%d', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(txt[:19], fmt).date()
        except ValueError:
            continue
    return None


def _row_to_student(mapping: dict) -> Optional[PortalStudent]:
    """Turn any column-named mapping into a PortalStudent (None if no ID)."""
    values = {}
    extra = {}
    for key, raw in mapping.items():
        field_name = _field_for_header(key)
        if field_name:
            values[field_name] = raw
        else:
            extra[_canonical_header(key)] = raw

    student_id = _clean(values.get('student_id'))
    if not student_id:
        return None

    return PortalStudent(
        student_id=student_id,
        first_name=_clean(values.get('first_name')),
        last_name=_clean(values.get('last_name')),
        middle_name=_clean(values.get('middle_name')),
        email=(_clean(values.get('email')) or '').lower() or None,
        phone_number=_clean(values.get('phone_number')),
        gender=_clean(values.get('gender')),
        date_of_birth=_parse_date(values.get('date_of_birth')),
        town=_clean(values.get('town')),
        province=_clean(values.get('province')),
        address=_clean(values.get('address')),
        course=_clean(values.get('course')),
        year_level=_clean(values.get('year_level')),
        campus=_clean(values.get('campus')),
        campus_short=_clean(values.get('campus_short')),
        gwa=_parse_float(values.get('gwa')),
        units_enrolled=_parse_int(values.get('units_enrolled')),
        student_status=_clean(values.get('student_status')),
        semester=_clean(values.get('semester')),
        school_year=_clean(values.get('school_year')),
        extra=extra,
    )


# ── Sources ─────────────────────────────────────────────────────────────────

class PortalSource:
    """Interface shared by the SQL and file adapters."""
    mode = 'unknown'

    def fetch_all(self) -> list[PortalStudent]:
        raise NotImplementedError

    def fetch_one(self, student_id: str) -> Optional[PortalStudent]:
        raise NotImplementedError

    def fetch_many(self, student_ids: Iterable[str]) -> list[PortalStudent]:
        wanted = [s for s in (str(i).strip() for i in student_ids) if s]
        found = []
        for sid in wanted:
            rec = self.fetch_one(sid)
            if rec is not None:
                found.append(rec)
        return found


_SELECT_ONLY = re.compile(r'^\s*(select|with)\b', re.IGNORECASE)
_IDENTIFIER = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


class SqlPortalSource(PortalSource):
    """SELECT-only access to the ICTS replica / direct SQL login.

    Safety rules, in order:
      1. Only one SELECT/WITH statement is accepted (no semicolons, no DML).
      2. The database session is put in READ ONLY mode on connect, so even a
         compromised query string cannot write.
      3. The engine is small (2 connections) and disposed with each source,
         so the sync cannot exhaust the portal's connection limit.
    """
    mode = 'sql'

    def __init__(self, dsn: Optional[str] = None,
                 query: Optional[str] = None,
                 view: Optional[str] = None,
                 id_column: Optional[str] = None):
        self.dsn = dsn or os.environ.get('PORTAL_DSN')
        if not self.dsn:
            raise PortalNotConfigured('PORTAL_DSN is not set.')

        self.view = view or os.environ.get('PORTAL_STUDENTS_VIEW', 'portal_students')
        if not _IDENTIFIER.match(self.view):
            raise PortalConfigError('PORTAL_STUDENTS_VIEW must be a plain identifier.')

        self.query = (query or os.environ.get('PORTAL_STUDENT_QUERY')
                      or f'SELECT * FROM {self.view}')
        self._validate_query(self.query)

        self.id_column = id_column or os.environ.get('PORTAL_ID_COLUMN', 'student_id')
        if not _IDENTIFIER.match(self.id_column):
            raise PortalConfigError('PORTAL_ID_COLUMN must be a plain identifier.')

        self._engine = None

    @staticmethod
    def _validate_query(query: str):
        stripped = query.strip().rstrip(';').strip()
        if not _SELECT_ONLY.match(stripped) or ';' in stripped:
            raise PortalConfigError(
                'The portal query must be a single SELECT/WITH statement; '
                'ScholarHub never writes to the portal database.'
            )

    def _engine_for(self):
        if self._engine is not None:
            return self._engine

        from sqlalchemy import create_engine, event

        engine = create_engine(
            self.dsn,
            pool_pre_ping=True,
            pool_recycle=280,
            pool_size=2,
            max_overflow=0,
            future=True,
        )

        @event.listens_for(engine, 'connect')
        def _read_only_session(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute('SET SESSION TRANSACTION READ ONLY')
            except Exception:
                # Older MySQL / MariaDB: the grants on the read-only user are
                # the real guarantee; this is defence in depth.
                pass
            try:
                cursor.execute('SET SESSION MAX_EXECUTION_TIME=30000')
            except Exception:
                pass
            finally:
                try:
                    cursor.close()
                except Exception:
                    pass

        self._engine = engine
        return engine

    def _rows(self, sql: str, params: Optional[dict] = None):
        from sqlalchemy import text
        self._validate_query(sql)
        engine = self._engine_for()
        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            return [dict(row) for row in result.mappings().all()]

    def fetch_all(self):
        rows = self._rows(self.query)
        return [s for s in (_row_to_student(r) for r in rows) if s is not None]

    def fetch_one(self, student_id: str):
        base = self.query.strip().rstrip(';').strip()
        sql = (f'SELECT * FROM ({base}) AS portal_row '
               f'WHERE portal_row.{self.id_column} = :sid')
        rows = self._rows(sql, {'sid': student_id})
        if not rows:
            # Tolerate the common "0199-0000" vs "01990000" difference.
            compact = re.sub(r'[^A-Za-z0-9]', '', str(student_id))
            if compact and compact != str(student_id):
                rows = self._rows(sql, {'sid': compact})
        if not rows:
            return None
        return _row_to_student(rows[0])

    def dispose(self):
        if self._engine is not None:
            try:
                self._engine.dispose()
            finally:
                self._engine = None


class FilePortalSource(PortalSource):
    """Reads a CSV / JSON / JSONL export of the portal student view."""
    mode = 'file'

    def __init__(self, path: Optional[str] = None):
        self.path = path or os.environ.get('PORTAL_EXPORT_FILE')
        if not self.path:
            raise PortalNotConfigured('PORTAL_EXPORT_FILE is not set.')
        if not os.path.exists(self.path):
            raise PortalNotConfigured(f'Portal export not found: {self.path}')
        self._cache = None

    def fetch_all(self):
        if self._cache is None:
            self._cache = self._load()
        return list(self._cache)

    def fetch_one(self, student_id: str):
        sid = str(student_id or '').strip()
        if not sid:
            return None
        compact = re.sub(r'[^A-Za-z0-9]', '', sid).lower()
        for record in self.fetch_all():
            rid = str(record.student_id)
            if rid == sid or re.sub(r'[^A-Za-z0-9]', '', rid).lower() == compact:
                return record
        return None

    def _load(self):
        ext = os.path.splitext(self.path)[1].lower()
        if ext == '.json':
            with open(self.path, 'r', encoding='utf-8-sig') as fh:
                payload = json.load(fh)
            rows = payload.get('students', payload) if isinstance(payload, dict) else payload
        elif ext in ('.jsonl', '.ndjson'):
            rows = []
            with open(self.path, 'r', encoding='utf-8-sig') as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
        else:
            with open(self.path, 'r', encoding='utf-8-sig', newline='') as fh:
                rows = list(csv.DictReader(fh))

        students = []
        for row in rows:
            rec = _row_to_student(row)
            if rec is not None:
                students.append(rec)
        log.info('Portal export %s: %d student record(s).', self.path, len(students))
        return students


def get_portal_source(source: Optional[str] = None, **kwargs) -> PortalSource:
    """Build the adapter named by PORTAL_SOURCE (or inferred from the env)."""
    kind = (source or os.environ.get('PORTAL_SOURCE') or '').strip().lower()
    if not kind:
        # An explicit export path (CLI --file) always means the file adapter,
        # even when a replica DSN is configured for the deployment.
        if kwargs.get('path') or os.environ.get('PORTAL_EXPORT_FILE'):
            kind = 'file'
        elif os.environ.get('PORTAL_DSN'):
            kind = 'sql'

    if kind == 'sql':
        return SqlPortalSource(**kwargs)
    if kind == 'file':
        return FilePortalSource(**kwargs)

    raise PortalNotConfigured(
        'No portal source configured. Set PORTAL_DSN (read-only replica) or '
        'PORTAL_EXPORT_FILE (CSV/JSON export) and PORTAL_SOURCE accordingly.'
    )

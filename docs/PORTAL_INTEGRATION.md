# LSPU Portal Integration — ICTS Handover Specification

Status: **integration seam implemented, waiting for portal access from ICTS**
Audience: LSPU ICTS / portal vendor, SFAO, and whoever maintains ScholarHub.

ScholarHub is the scholarship system. The LSPU student portal is the record of
who a student is and what their academic standing is. This document describes
the link between the two, what ICTS needs to provide, and what was deliberately
left on the ScholarHub side.

---

## 1. Agreed operating model

| Question | Decision | Where it lives in the code |
|---|---|---|
| Portal access | Read-only: replica database or a `SELECT`-only SQL login. | `app/services/portal/source.py` (`SqlPortalSource`); CSV/JSON export while waiting (`FilePortalSource`) |
| Student sign-in | Portal SSO once ICTS delivers it; ScholarHub passwords until then. | `app/views/auth.py` `login()` (unchanged); SSO seam documented in §9 |
| Staff / campus admin / super admin | Local ScholarHub accounts created by SFAO / super admin. | `app/views/admin.py`, `create_staff_accounts.py` |
| Self-registration + COR/grades OCR | Skipped for students the portal knows; kept as the fallback for unknown students. | Portal branch at the top of `register()`; legacy document gate untouched below it |
| Source of truth | Portal owns identity + academic data. ScholarHub owns applications, awards, documents, monitoring. | `PORTAL_OWNED_FIELDS` in `app/services/portal/sync.py` |
| GWA | One per-semester GWA value from the portal. | `User.gwa` + `GwaHistory` row per semester |
| Freshness | Near-real-time when the portal can push; otherwise login refresh + scheduled sync. | `/api/portal/sync` webhook, `refresh_on_login()`, `flask portal-sync run` |
| Mid-semester changes | A student's current portal data is what an application uses; no automatic re-review of past awards. | Sync updates the profile only |
| One process | One fixed university-wide pipeline. Campuses set dates and eligibility cutoffs, never extra steps. | `ApplicationStatus` enum is the single pipeline (§7) |
| Final award authority | Campus decides; the university office views and audits, does not veto. | Campus-scoped review in `app/views/staff.py` / `admin.py` |
| Existing accounts | Archived at cut-over, then revived by the first sync if the portal also knows them. | `flask portal-sync archive-legacy` |

---

## 2. Architecture

```
   LSPU student portal (registrar data)
            │
            │  read-only replica  ── or ──  SELECT-only SQL login
            │  (or a CSV/JSON export while access is arranged)
            ▼
   app/services/portal/source.py      SqlPortalSource | FilePortalSource
            │   PortalStudent (normalised record)
            ▼
   app/services/portal/sync.py        matching + write rules + audit
            │
            ├── users            identity, course, year, campus, GWA, units, status
            ├── gwa_history      one row per semester GWA
            ├── portal_sync_runs one row per sync (who changed what, when)
            └── audit_log        status changes, archival
```

ScholarHub writes **nothing** back to the portal. Scholarship applications,
batches, monitoring, documents, notifications and reports stay entirely in
ScholarHub's own database.

### Entry points

| Trigger | Path |
|---|---|
| Manual / scheduled | `flask portal-sync run` (or `--file export.csv`) |
| Portal push | `POST /api/portal/sync` (HMAC-signed) |
| Student login | `refresh_on_login()` when the cached copy is older than `PORTAL_FRESHNESS_MINUTES` |
| Registration | `lookup_for_registration()` — decides whether OCR is needed |

---

## 3. What ICTS needs to provide

### 3.1 Preferred: read-only replica

A MySQL/MariaDB (or PostgreSQL) replica of the student records, reachable from
ScholarHub's host, with a dedicated user:

```sql
CREATE USER 'scholarhub_ro'@'%' IDENTIFIED BY '<long random password>';
GRANT SELECT ON lspu_portal.portal_students TO 'scholarhub_ro'@'%';
-- no INSERT / UPDATE / DELETE / DDL
```

The adapter additionally puts every session in `READ ONLY` mode
(`SET SESSION TRANSACTION READ ONLY`) and refuses any statement that is not a
single `SELECT`/`WITH`, so a mistake cannot write to the portal even if the
grants were wrong. Use a *replica*, not the production primary, so a slow
scholarship report can never affect enrollment transactions.

### 3.2 Acceptable: direct SQL with a `SELECT`-only login

Same grants as above. ScholarHub opens at most **two** connections per sync and
disposes them afterwards; sync of the full student population is expected to be
a few thousand rows.

### 3.3 Interim: CSV/JSON export

Until database access exists, ICTS (or the registrar) can export the same view:

```
flask portal-sync run --file portal_students.csv --dry-run
flask portal-sync run --file portal_students.csv
```

CSV/JSON headers are matched through an alias table, so `Student No`,
`student_number`, `STUDENT_ID` all map to the same field (see §5).

### 3.4 The view ScholarHub reads

One row per student (current enrollment), name it `portal_students` or point
`PORTAL_STUDENT_QUERY` at your own query. Minimum useful columns:

| Portal column | Meaning | Required |
|---|---|---|
| `student_id` | Student number, e.g. `0199-0000` | **yes** |
| `first_name`, `last_name`, `middle_name` | Legal name | yes |
| `email` | Institutional email (used for OTP + notifications) | yes |
| `course` | Degree program | yes |
| `year_level` | 1–5 / Irregular / Graduate | yes |
| `campus` | Campus name | yes |
| `gwa` | **Per-semester** GWA on the 1.00–5.00 scale | yes |
| `semester`, `school_year` | Which term that GWA belongs to | yes |
| `units_enrolled` | Total units for the term | yes |
| `student_status` | active / graduated / dropped | yes |
| `phone_number`, `gender`, `date_of_birth`, `town`, `province`, `address` | Profile data | optional |
| anything else | Copied into `PortalStudent.extra` for future scholarship criteria | optional |

Notes:

- ScholarHub keeps students who are *not* in the current enrollment snapshot;
  a missing row is never treated as a drop-out. Lifecycle changes must come
  through `student_status`.
- GWA must be the term GWA the registrar already computes, not an average of
  ScholarHub-side grades.
- If the portal later exposes program-specific data (income bracket, household
  size, PWD status, …), add the column and it will be carried in `extra`
  without a code change.

### 3.5 Optional: change webhook

```
POST /api/portal/sync
X-Portal-Timestamp: 1734567890
X-Portal-Signature: sha256=<hex HMAC-SHA256 of "<timestamp>.<raw body>">
Content-Type: application/json

{"student_ids": ["0199-0000", "0199-0001"]}
```

- Secret: `PORTAL_WEBHOOK_SECRET` on ScholarHub, shared out-of-band.
- Timestamps older than 5 minutes are rejected; requests are capped at 200 IDs.
- The payload carries **only IDs** — ScholarHub re-reads the record from its own
  read-only source, so a forged body cannot inject data.
- Any scheduler can call the same endpoint (a cron job that posts recently
  changed IDs is enough).

---

## 4. Configuration

Set these as environment variables on the host (never in the repository):

| Variable | Default | Meaning |
|---|---|---|
| `PORTAL_ENABLED` | `false` | Master switch. Everything below is inert while false. |
| `PORTAL_SOURCE` | inferred | `sql` or `file` |
| `PORTAL_DSN` | — | SQLAlchemy URL for the read-only replica |
| `PORTAL_STUDENTS_VIEW` | `portal_students` | Table/view name |
| `PORTAL_STUDENT_QUERY` | `SELECT * FROM <view>` | Custom SELECT (must be one statement) |
| `PORTAL_ID_COLUMN` | `student_id` | Join column in the view |
| `PORTAL_EXPORT_FILE` | — | CSV/JSON path for the interim source |
| `PORTAL_FRESHNESS_MINUTES` | `60` | Login refresh window |
| `PORTAL_WEBHOOK_SECRET` | — | Enables `/api/portal/sync` |
| `PORTAL_LOG_LOGIN_RUNS` | `false` | Record login refreshes in `portal_sync_runs` |

### Go-live sequence

1. **Connect** — set `PORTAL_DSN` + `PORTAL_ENABLED=true`, restart.
2. **Inspect** — `flask portal-sync status` then `flask portal-sync test`.
   `test` prints which fields arrived, never personal data.
3. **Shadow** — `flask portal-sync run --dry-run` and read the counts. Repeat
   until `created` / `updated` match expectations.
4. **First sync** — `flask portal-sync run`. Existing self-registered accounts
   are matched by student ID and upgraded in place, so their applications stay.
5. **Archive the rest** — `flask portal-sync archive-legacy` (preview), then
   `--apply`. Accounts are deactivated, not deleted; history is intact and the
   next sync can revive anyone the portal knows.
6. **Webhook (optional)** — set `PORTAL_WEBHOOK_SECRET` and have ICTS post
   changed IDs. Without a webhook, add `flask portal-sync run` to a nightly
   schedule; logins also refresh stale students.
7. **SSO (later)** — see §9.

Rollback at any step: set `PORTAL_ENABLED=false`. Portal-sourced data already
written stays as normal profile data; nothing else depends on the link.

---

## 5. Field mapping

| Portal | ScholarHub | Rule |
|---|---|---|
| `student_id` | `users.student_id` / `users.portal_student_id` | Join key; never changed by email |
| `first_name`, `last_name`, `middle_name` | same columns | Portal value wins when non-empty |
| `email` | `users.email` | Portal value wins **unless** another account already holds it (then it is skipped and logged) |
| `course` | `users.course` | Portal value wins |
| `year_level` | `users.year_level` | Normalised to `1st Year … 5th Year`, `Irregular`, `Graduate` |
| `campus` | `users.campus_id` | Matched to a `campuses` row by name or short code (`SC`, `SN`, `SBC`, `LB`) |
| `gwa` | `users.gwa` + `gwa_history` | One history row per `semester` + `school_year` |
| `semester`, `school_year` | `users.grades_semester`, `gwa_history` | Display label, e.g. `1st Semester 2026-2027` |
| `units_enrolled` | `users.units_enrolled` | Portal value wins |
| `student_status` | `users.student_status` via `student_status_service` | Graduated/dropped closes active scholarships exactly like a manual change |
| `phone_number`, `gender`, `dob`, `town`, `province`, `address` | same columns | Portal value wins when present |
| everything else | `PortalStudent.extra` | Preserved for future criteria; not written to a column |

Sync rules:

- A `NULL`/blank portal value never erases an existing ScholarHub value.
- The sync is idempotent: a second run over unchanged data reports `unchanged`.
- Records are committed one by one; a bad row is counted as `failed` with only
  the student ID (no personal data) and the rest of the run continues.
- Nothing is deleted.

---

## 6. Student experience

- **Registration:** portal-known student → enter student ID (and email if the
  portal has none) → OTP → account. No COR/grades PDF, no OCR. Unknown student
  → the existing self-registration + document verification flow.
- **Login:** ScholarHub password today; portal SSO later. Accounts created by
  the sync have no usable password — the office issues a temporary password
  through the normal reset flow until SSO is live.
- **Profile:** read-only academic fields (course, year level, campus, GWA,
  units) come from the portal. Contact details can still be edited where the
  portal has no value.
- **Applying / renewing:** the application reads the student's current portal
  data at submission time; documents already on record stay viewable.

---

## 7. The single scholarship process

`ApplicationStatus` is the whole pipeline and is shared by every campus:

```
pending → under_review → approved | rejected        (withdrawn at any point)
```

What a campus may set (its own choices, no new steps):

- scholarship dates and deadlines (`Scholarship.application_deadline`,
  academic period dates),
- scholarship scope, slots, award amount, funding type,
- eligibility cutoffs in the criteria text and the numeric filters used during
  review (minimum GWA, minimum units, income ceiling).

What no campus may change:

- the sequence of stages,
- who can award (the campus scholarship committee / campus admin),
- whether the university office can see the record (always can; it audits and
  reports, it does not veto a campus award).

This is the "one process" the office asked for: one pipeline, one audit trail,
one set of reports — with campus-level dates and thresholds.

---

## 8. Security and privacy

- Portal access is read-only at three levels: database grants, session
  `READ ONLY`, and query validation (single `SELECT`/`WITH` only).
- Credentials live only in host environment variables; `.env` is not tracked and
  `.env.example` contains placeholders only.
- Sync logs record student IDs and field *names*, not field values.
- `PortalStudent.extra` and sync details are stored server-side only; nothing
  from the portal is exposed to another student.
- Only student-owned data is shown to that student; staff see their campus;
  the university office sees aggregates and audits.
- Personal data handling is subject to the Data Privacy Act (RA 10173): the
  replica user should be limited to the columns ScholarHub actually needs, and
  access should be reviewed by ICTS annually.

---

## 9. SSO later

Nothing in the portal link requires SSO, and nothing blocks it. When ICTS can
issue a portal login for ScholarHub:

1. Add an OIDC/SAML callback route in `app/views/auth.py`.
2. Verify the assertion, then look the student up by `student_id`
   (`User.portal_student_id`), creating the account through the same sync rules
   if it is missing.
3. Set `session['user_id']` exactly as `login()` does today, so roles, campus
   context and inactivity timeout behave identically.
4. Keep the password form as a fallback for staff accounts and for students the
   portal cannot authenticate.

The account model already separates identity (`portal_student_id`,
`data_source`) from authentication (`password_hash`), so this is additive.

---

## 10. Operations

```bash
flask portal-sync status                  # config, counts, last 5 runs
flask portal-sync test                    # connect + which fields arrived
flask portal-sync run --dry-run           # preview a full sync
flask portal-sync run                     # apply
flask portal-sync student 0199-0000       # refresh one student
flask portal-sync archive-legacy          # preview cut-over archival
flask portal-sync archive-legacy --apply  # archive legacy accounts
```

Failure behaviour, by design:

| Failure | Effect |
|---|---|
| Portal unreachable | Sync run marked `failed`; app keeps working on last-known data; login refresh is skipped |
| One bad record | Counted `failed`, run continues, other students still sync |
| Portal query returns no rows | Nothing changes (never mass-archives) |
| Email collision | Email is skipped for that student, rest of record still syncs |
| Webhook signature wrong / stale | `401`, no sync attempted |

Monitoring: `flask portal-sync status` shows the last runs and student counts;
`portal_sync_runs` keeps the history (trigger, mode, counts, error).

---

## 11. Open items for the ICTS meeting

1. Replica or direct SQL, and which host/port ScholarHub may reach.
2. Exact view/table name and column names for the fields in §3.4.
3. Whether GWA can be supplied per semester (and for which terms history is
   available).
4. Refresh interval of the replica — this sets the real freshness ceiling.
5. Whether a change webhook can be emitted, or whether a nightly pull is the
   only option.
6. Campus names/codes as the portal spells them (for campus matching).
7. SSO protocol and timeline, if any.
8. Who owns the read-only account and its rotation.

Until items 1–2 are answered, the integration runs against a CSV export and
remains switched off in production (`PORTAL_ENABLED=false`).

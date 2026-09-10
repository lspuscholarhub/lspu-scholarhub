# Paper 3 — Database Schema of LSPU ScholarHub

> Thesis use: Chapter 3 (Methodology) — Database Design; ERD narrative for
> the appendix. The full SQL dump lives in `database/lspu_scholarhub_dump.sql`.

---

## 1. Design Overview

- **DBMS:** MySQL 8, InnoDB (ACID transactions)
- **Access:** SQLAlchemy ORM 2.0 (Flask-SQLAlchemy), PyMySQL driver
- **Entities:** 12 model classes mapping 1:1 to tables
- **Design signature:** every domain table carries `campus_id` (nullable)
  to support the multi-campus university-wide deployment; `NULL`
  represents "university-wide / not campus-bound".

---

## 2. Entity Inventory

| # | Entity | Table purpose | Key relationships |
|---|---|---|---|
| 1 | **User** | All accounts (students, staff, admins) — identity, credentials, contact, academic info (student_id, course, year_level, GWA, units_enrolled), document paths, campus | belongs to Campus; has Applications, Documents, Notifications, ChatHistory, MonitoringSubmissions |
| 2 | **Campus** | The 4 LSPU campuses (Santa Cruz main, Siniloan, San Pablo City, Los Baños) with short codes | has many Users, Scholarships, Batches, Applications |
| 3 | **Scholarship** | Scholarship programs — title, description, funding type (public/private), award amount, slots (`max_applicants`), current fill count, eligibility criteria, benefits, deadline, status, scope (`campus_id` NULL = university-wide), `is_hidden` + `allowed_student_ids` (targeted visibility), custom form fields (JSON) | belongs to Campus; has Applications, Batches |
| 4 | **ScholarshipApplication** | A student's application to one program — pre-filled profile snapshot, custom answers (JSON), status (pending → under review → approved/rejected), review notes, timestamps | belongs to User, Scholarship; optionally to Batch |
| 5 | **ScholarshipBatch** | Groups of approved scholars per program per semester, with approval workflow state | belongs to Scholarship, Campus; has many Applications |
| 6 | **MonitoringSubmission** | Monitoring & Evaluation form per scholar per academic period — file path + Cloudinary public id, submission/review state | belongs to User (scholar), references Scholarship, AcademicPeriod |
| 7 | **AcademicPeriod** | Semesters/terms (1st/2nd/Inter-Semester), incl. the M&E form deadline per period | referenced by MonitoringSubmissions, Batches |
| 8 | **Document** | Registration document metadata (COR, Copy of Grades) — local + Cloudinary paths, verification state | belongs to User |
| 9 | **Notification** | In-app notification rows (title, message, type, read flag) + delivery log for email/SMS fanout | belongs to User |
| 10 | **ChatHistory** | Persistent AI assistant messages per user (role, content) | belongs to User |
| 11 | **AuditLog** | Administrative action trail (actor, action, target, timestamp, details) | references User (actor) |
| 12 | **OTP / verification tokens** | One-time PINs for email verification and password resets (hashed, expiring) | belongs to User |

---

## 3. Core Relationships (ERD narrative)

```
Campus ──1:N── User
Campus ──1:N── Scholarship
Campus ──1:N── ScholarshipBatch

User ──1:N── ScholarshipApplication ──N:1── Scholarship
User ──1:N── Document
User ──1:N── Notification
User ──1:N── ChatHistory
User ──1:N── MonitoringSubmission ──N:1── AcademicPeriod
User ──1:N── AuditLog (as actor)

Scholarship ──1:N── ScholarshipApplication
Scholarship ──1:N── ScholarshipBatch
ScholarshipBatch ──1:N── ScholarshipApplication (approved scholars grouped)

ScholarshipApplication ──N:1── ScholarshipBatch (optional until batching)
```

### Status enumerations

- **User.user_type:** `student` | `staff` | `admin` | `super_admin`
- **Scholarship.status:** `active` | `inactive` | `closed` (enum)
- **Application status flow:** `pending` → `under_review` → `approved` / `rejected`
  (display layer merges *pending/under review* as "Pending/Review" for students)
- **Batch workflow:** draft → finalized/approved

---

## 4. Integrity & Concurrency Rules

| Concern | Rule enforced |
|---|---|
| One public program per student | Application layer rejects a second *public* scholarship application; private programs may be combined |
| Slot capacity | `current_applicants` incremented on approval; `max_applicants` is non-negative (`CHECK`-style validation in forms + model) |
| Deadline handling | `application_deadline` nullable — NULL means open until manually closed |
| Hidden programs | `is_hidden` + `allowed_student_ids` (comma-separated IDs) — enforced by a single shared `is_visible_to()` helper used by list page, chatbot, and detail access |
| Campus scoping | `campus_id IS NULL` ⇒ university-wide; otherwise restricted to that campus |
| File lifecycle | Replaced documents delete the old Cloudinary object (resource-type-aware) to prevent orphaned storage |

---

## 5. Schema Sources of Truth

1. **Models** — `app/models/*.py` (authoritative, used by Alembic migrations)
2. **Dump** — `database/lspu_scholarhub_dump.sql` (full schema + data snapshot)
3. **Migrations** — applied programmatically at startup for additive changes
   (e.g., the multi-campus columns, M&E deadline), documented in
   `app/__init__.py`

For the thesis ERD figure, export the diagram from
`database/lspu_scholarhub_dump.sql` with MySQL Workbench
(Database → Reverse Engineer) or dbdiagram.io, then label the four campus
rows and the university-wide NULL pattern.

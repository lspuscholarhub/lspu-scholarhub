# Paper 2 — System Architecture of LSPU ScholarHub

> Thesis use: Chapter 3 (Methodology) — Architectural Design / System Design.

---

## 1. Architectural Pattern

LSPU ScholarHub follows the **three-tier architecture** with a
**Model–View–Controller (MVC)** organization inside the application tier:

| Tier | Implementation |
|---|---|
| **Presentation tier** | Jinja2 templates + Bootstrap 5 rendered to the browser (47 templates, one shared `base.html` with role-aware navbar/footer) |
| **Application tier** | Flask application on Gunicorn (Python), organized as MVC |
| **Data tier** | MySQL 8 (Railway-managed) accessed through SQLAlchemy ORM; Cloudinary for document binaries |

### MVC mapping

| MVC component | Location | Contents |
|---|---|---|
| **Model** | `app/models/` | 12 SQLAlchemy entity classes |
| **View** | `app/templates/` | Jinja2 templates organized per role (`student/`, `staff/`, `admin/`, `auth/`, `scholarship/`, `chatbot/`) |
| **Controller** | `app/views/` | Flask Blueprints — one module per role plus shared controllers |
| **Service layer** | `app/services/` | Business logic decoupled from controllers (OCR, chatbot, notifications, storage, batching, exports, campus context, audit, performance) |
| **Utilities** | `app/utils/` | Decorators (`role_required`), shared helpers |

---

## 2. Module Map

```
app/
├── __init__.py          # Application factory (create_app), extensions, migrations
├── models/              # M — 12 entities (User, Campus, Scholarship, ...)
├── views/               # C — Blueprints per role
│   ├── auth.py          #   registration, OTP, login, password reset
│   ├── main.py          #   landing page, guest pages
│   ├── scholarship.py   #   public/student scholarship list & detail, apply
│   ├── student.py       #   dashboard, applications, documents, M&E form
│   ├── staff.py         #   review, batching, monitoring, scholarships CRUD
│   ├── admin.py         #   user mgmt, settings, reports, monitoring, audit
│   ├── chatbot.py       #   AI assistant endpoints (rate-limited)
│   └── ...
├── services/            # Business logic layer
│   ├── ocr_service.py           # pypdf extraction → Gemini verification
│   ├── chatbot_service.py       # Gemini chatbot + visibility-scoped context
│   ├── notification_service.py  # Brevo email, Semaphore/Twilio SMS, in-app
│   ├── storage_service.py       # Cloudinary upload/delete (resource-aware)
│   ├── batch_service.py         # scholar batching workflow
│   ├── export_service.py        # Excel/PDF/DOCX exports
│   ├── campus_context.py        # multi-campus scoping helpers
│   ├── audit_service.py         # action logging
│   ├── performance_service.py   # query optimization / caching
│   └── scholarship_service.py   # eligibility & statistics
├── templates/           # V — Jinja2 per-role templates
├── static/              # CSS, JS, images, uploaded local fallbacks
└── utils/
    └── decorators.py    # @role_required, login requirements
```

---

## 3. Request Flow (example: student applies for a scholarship)

```
Browser
  │ POST /scholarship/<id>/apply  (CSRF token, session cookie)
  ▼
Gunicorn worker ──▶ Flask routing (scholarship blueprint)
  │                    1. @role_required('student') — authorization check
  │                    2. Flask-WTF CSRF validation
  │                    3. Flask-Limiter rate-limit check
  ▼
Controller (app/views/scholarship.py)
  │   a. Load Scholarship via SQLAlchemy (campus + visibility scoped)
  │   b. Verify eligibility (public/private rule, one-public-program rule)
  │   c. Build application record from pre-filled profile + custom form fields
  ▼
Service layer
  │   notification_service ─▶ Brevo (email) + Semaphore (SMS) + in-app row
  │   audit_service ─▶ action log row
  ▼
Model layer ─▶ MySQL (INSERT application, UPDATE current_applicants)
  ▼
Redirect ─▶ My Applications page with flash confirmation
```

---

## 4. Multi-Campus Scoping Architecture

The system was upscaled from campus-wide to **university-wide** using a
campus foreign key on every domain entity plus a session-scoped campus
context:

- `campuses` table: Santa Cruz (Main), Siniloan, San Pablo City, Los Baños
- `campus_id` FK on: users, scholarships, applications, batches,
  notifications, documents, monitoring submissions
- **Scholarship scope:** campus-specific (`campus_id` set) or
  **university-wide** (`campus_id = NULL` → visible to all campuses)
- **Role-based scoping:**
  - *Super Admin* — all campuses; selectable campus context in navbar
  - *Admin* — one campus only
  - *Staff* — one campus only
  - *Student* — sees own-campus + university-wide programs
- `campus_context.py` centralizes the filter logic so every query is
  automatically scoped — no view constructs campus filters by hand.

---

## 5. Security Architecture

| Layer | Mechanism |
|---|---|
| Authentication | Session-based (Flask-Login), bcrypt/Werkzeug password hashing, session regeneration on login (fixation defense) |
| Password policy | Min 8 chars with uppercase, lowercase, and digit (`password_validator.py`) |
| Authorization | `@role_required` decorator per route; 5 roles (guest, student, staff, admin, super_admin) |
| OTP verification | Email OTP required before account activation |
| CSRF | Flask-WTF token on every POST form |
| Rate limiting | Flask-Limiter on login, OTP resend, chatbot endpoints |
| Document authenticity | OCR cross-verification: student ID, name, year level, and birthdate from uploaded COR/Grades must match registration input; PDF-only accepted at registration |
| Visibility control | `is_hidden` + `allowed_student_ids` on scholarships; enforced consistently on the list page AND the AI assistant (single shared visibility helper) |
| Audit trail | `audit_service` records admin/staff actions |
| Secrets | Environment variables only (12-factor); nothing hard-coded in the repo |

---

## 6. Deployment Topology

```
GitHub (main branch)
   │  push → auto-build
   ▼
Railway project
├── service: web
│     gunicorn run:app --workers 3 --threads 8
│     bind 0.0.0.0:$PORT, timeout 120s, graceful 30s
│     env: GEMINI_API_KEY, CLOUDINARY_*, BREVO_API_KEY,
│         SEMAPHORE_API_KEY, TWILIO_*, DATABASE_URL, ...
└── service: MySQL 8 + persistent volume (mysql-volume)
        DATABASE_URL supplied to web service

External SaaS:
├── Cloudinary — document CDN storage
├── Google Gemini API — OCR verification + chatbot
├── Brevo API — transactional email
└── Semaphore / Twilio — SMS
```

**Scalability notes.** The Gunicorn configuration (3 workers × 8 threads)
provides 24 concurrent handlers per instance; the worker count is a
single-line change on Railway and can be raised for peak enrollment
periods. MySQL connection pooling via SQLAlchemy, rate limiting on
expensive endpoints (OCR upload, chatbot), and CDN-served static files
keep per-request cost low.

# Paper 1 — Technology Stack of LSPU ScholarHub

> Thesis use: Chapter 3 (Methodology) — Software Requirements / Tools & Technologies.
> All versions are pinned from `requirements.txt` and verified against the running system.

---

## 1. Overview

LSPU ScholarHub is a **web-based scholarship management system** built as a
server-rendered web application following the Model–View–Controller (MVC)
pattern. It is developed in **Python** using the **Flask** micro-framework,
stores data in a **MySQL** relational database, and is deployed to
**Railway** with document files stored on **Cloudinary**.

The system integrates two AI capabilities powered by **Google Gemini**:

1. **OCR document intelligence** — reads student PDFs (Certificate of
   Registration, Copy of Grades) to extract and verify identity data
   (student ID, name, year level, birthdate, GWA, units enrolled).
2. **Conversational assistant** — the "ScholarHub Assistant" chatbot that
   answers scholarship questions for guests and students using live
   database context.

---

## 2. Layer-by-Layer Stack

### 2.1 Presentation Layer (Client Side)

| Technology | Version | Role | Justification |
|---|---|---|---|
| **HTML5** | — | Page structure | Standard for web UIs |
| **CSS3** | — | Custom styling | Layered over Bootstrap for the LSPU identity |
| **Bootstrap** | 5.1.3 | Responsive layout framework | Mobile-first grid, mature components; ensures the system works on phones where most students browse |
| **Bootstrap Icons** | 1.11.0 | Icon set | Consistent lightweight iconography |
| **JavaScript (Vanilla ES6+)** | — | Client interactivity | No heavy SPA framework needed — the app is server-rendered; JS handles forms, modals, chat UI, and Chart.js wiring |
| **Chart.js** | (CDN) | Data visualization | Powers the statistical graphs on staff/admin reports (application trends, campus breakdowns) |
| **Jinja2 templating** | 3.1.6 | Server-side templating | Role-aware single navbar/base layout (`base.html`) renders per role: Guest, Student, Staff, Admin, Super Admin |

### 2.2 Application Layer (Server Side)

| Technology | Version | Role | Justification |
|---|---|---|---|
| **Python** | 3.14 | Core language | Team proficiency, readable syntax, extensive library ecosystem |
| **Flask** | 2.3.3 | Web micro-framework | Lightweight, explicit, ideal for an MVC capstone system; avoids magic conventions of larger frameworks |
| **Werkzeug** | 2.3.7 | WSGI utilities, password hashing | Industry-standard `generate_password_hash` / `check_password_hash` for credential storage |
| **Jinja2** | 3.1.6 | Template engine | Sandboxed autoescaping protects against XSS in templates |
| **Blueprints** | (Flask built-in) | Modular routing | Codebase split into `auth`, `student`, `staff`, `admin`, `scholarship`, `chatbot`, `main` blueprints — one module per user role |
| **Flask-Login** | 0.6.3 | Session management | Handles login state, session protection |
| **Flask-WTF / WTForms** | 1.1.1 / 3.2.1 | CSRF protection & forms | Every POST form carries a CSRF token |
| **Flask-Limiter** | 4.1.1 | Rate limiting | Brute-force protection on login, OTP, and chatbot endpoints |
| **Flask-Mail** | 0.9.1 | SMTP fallback | Backup email channel |

### 2.3 Data Layer

| Technology | Version | Role | Justification |
|---|---|---|---|
| **MySQL** | 8.x (Railway managed) | Relational database | ACID transactions for application/batch workflows; the university ICT environment already standardizes on MySQL |
| **SQLAlchemy** | 2.0.49 | ORM | Type-safe query construction, relationship management across 12 entities |
| **Flask-SQLAlchemy** | 3.0.5 | Flask-ORM integration | Session scoping per request |
| **PyMySQL** | 1.1.0 | MySQL driver | Pure-Python driver — no native build dependencies, deploys cleanly on Railway |
| **Flask-Migrate / Alembic** | 4.0.5 / 1.18.4 | Schema migrations | Versioned schema evolution (used during the multi-campus upscale) |

### 2.4 AI / Intelligence Layer

| Technology | Version | Role | Justification |
|---|---|---|---|
| **Google Gemini (google-genai SDK)** | 2.3.0 | Two AI functions: document OCR verification & the ScholarHub chatbot | Multimodal model reads scanned PDFs/images of COR and Grades; verification rules (ID match, name match, year level, birthdate, GWA extraction) run in `app/services/ocr_service.py`. The chatbot uses Gemini with a live system-prompt built from database state |
| **pypdf** | 6.11.0 | Native PDF text extraction | Fast first-pass extraction before falling back to Gemini vision — reduces API cost and latency |
| **difflib (stdlib)** | — | Fuzzy name matching | Tolerates OCR noise when comparing document names against registration input |

### 2.5 File Storage & Notification Services

| Service | Library/Version | Role | Justification |
|---|---|---|---|
| **Cloudinary** | cloudinary 1.44.0 | Document file storage (PDFs/images) | Cloud CDN storage with signed URLs; keeps binary files out of the app server and database; resource-type-aware deletion implemented |
| **Brevo (Sendinblue) API** | requests | Transactional email | OTP delivery, application status notifications, announcements — REST API preferred over raw SMTP for deliverability |
| **Semaphore SMS API** | requests | PH SMS gateway (primary SMS) | Local Philippine gateway — cheaper and more reliable for 09XX mobile numbers |
| **Twilio** | twilio 9.10.5 | SMS fallback gateway | Automatic failover when Semaphore is unavailable |

### 2.6 DevOps / Deployment

| Technology | Version | Role | Justification |
|---|---|---|---|
| **Gunicorn** | 21.2.0 | Production WSGI server | 3 workers × 8 threads = 24 concurrent request handlers per dyno; handles the target load of hundreds of simultaneous users |
| **Railway** | — | Cloud hosting (app + MySQL) | PaaS with GitHub auto-deploy: every push to `main` builds and releases; managed MySQL with persistent volume |
| **Git / GitHub** | — | Version control | Repository: `lspuscholarhub/lspu-scholarhub`; push-to-deploy pipeline |
| **python-dotenv** | 1.0.0 | Environment config | 12-factor configuration; secrets never committed |
| **pytest / coverage** | 7.4.2 / 7.13.5 | Testing | Unit/integration test runs (see `docs/TESTING_POLICY.md`) |
| **flake8 / black** | 6.1.0 / 23.9.1 | Code quality | Style enforcement |

### 2.7 Report Generation

| Library | Version | Role |
|---|---|---|
| **openpyxl** | 3.1.2 | Excel (.xlsx) exports of batches and reports |
| **reportlab** | 4.1.0 | PDF generation |
| **python-docx** | 1.1.0 | DOCX document generation |

---

## 3. Stack Summary Diagram (text form)

```
┌─────────────────────────────────────────────────────────────┐
│ CLIENT                                                       │
│  HTML5 · CSS3 · Bootstrap 5.1.3 · JS ES6 · Chart.js          │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTPS
┌──────────────────────▼──────────────────────────────────────┐
│ RAILWAY — Flask 2.3.3 on Gunicorn (3w × 8t)                  │
│  Blueprints: main · auth · student · staff · admin ·         │
│              scholarship · chatbot                            │
│  Services:  ocr (Gemini) · chatbot (Gemini) · notification · │
│             storage (Cloudinary) · batch · export · campus    │
│  Security:  Flask-Login · Flask-WTF (CSRF) · Flask-Limiter   │
└───────┬───────────────────┬───────────────────┬─────────────┘
        │ SQL (PyMySQL)     │ REST              │ REST
┌───────▼───────┐  ┌────────▼────────┐  ┌───────▼─────────────┐
│ MySQL 8       │  │ Cloudinary      │  │ Gemini API (Google) │
│ (Railway)     │  │ document files  │  │ OCR + chatbot       │
└───────────────┘  └─────────────────┘  └─────────────────────┘
        │
        │ REST  ┌──────────────────────────┐
        └──────▶│ Brevo (email)            │
                │ Semaphore (SMS, primary) │
                │ Twilio (SMS, fallback)   │
                └──────────────────────────┘
```

---

## 4. Hardware Requirements (minimum for deployment host)

Railway abstracts hardware, but for documentation purposes the equivalent
specification is:

- **App instance:** ≥ 0.5 vCPU / 512 MB RAM (Gunicorn, 3 workers × 8 threads)
- **Database:** managed MySQL 8 with persistent volume (`mysql-volume`)
- **Client:** any modern browser (Chrome, Edge, Firefox) on desktop or mobile;
  Bootstrap 5 responsive breakpoints cover 320 px–1920 px screens

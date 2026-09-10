# Paper 4 — Functionalities & Workflow of LSPU ScholarHub

> Thesis use: Chapter 1 (Objectives & Scope) and Chapter 2 (comparison with
> related systems). Describes every role's capabilities and the end-to-end
> scholarship lifecycle as implemented.

---

## 1. Roles

| Role | Scope | Purpose |
|---|---|---|
| **Guest** (no account) | Public | Browse landing page, open scholarships, AI assistant |
| **Student** | Own campus + university-wide programs | Register with document verification, apply, track, comply |
| **Staff** | One campus | Review applications, batch scholars, monitor compliance, manage programs |
| **Admin** | One campus | Everything staff can do + user management + settings + reports for their campus |
| **Super Admin** | All campuses (switchable context) | Full system oversight across the university |

---

## 2. End-to-End Scholarship Lifecycle

```
┌──────────────┐   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐   ┌──────────────┐
│ 1. REGISTER   │▶──│ 2. PROGRAM     │▶──│ 3. REVIEW      │▶──│ 4. BATCHING    │▶──│ 5. MONITORING │
│ doc-verified  │   │ CREATION       │   │ & DECISION     │   │ & AWARDING     │   │ & RENEWAL     │
└──────────────┘   └───────────────┘   └───────────────┘   └───────────────┘   └──────────────┘
```

### Stage 1 — Registration (document-verified)

1. Student fills the registration form: identity, contact, birthday,
   course, **year level** (1st–5th, plus *Irregular* and *Graduate* options
   ready for future policy), **campus**, and uploads **PDF only**:
   Certificate of Registration (COR) + Copy of Grades.
2. **OCR verification pipeline** (`ocr_service.py`):
   - pypdf extracts native PDF text; Gemini vision fallback for scans;
   - extracts: student ID, full name, year level (numeric or word form),
     birthdate, GWA, units enrolled, course;
   - cross-checks student ID, name, **year level**, and **birthdate**
     against the form values — mismatch blocks registration with a
     specific, actionable error message.
3. Email OTP verification activates the account; a temporary password is
   issued. GWA and units are stored from the Copy of Grades.

### Stage 2 — Program discovery & application

1. Admin/Staff create scholarship programs with: award amount, slots
   (min 0), eligibility criteria, benefits, **scope** (campus-specific or
   university-wide), **custom form fields** (replacing paper/Google-Forms
   intake), and optional targeted visibility (`is_hidden` +
   `allowed_student_ids` for programs that must not be publicly listed).
   An optional announcement (email + SMS + in-app) can be broadcast on
   creation.
2. Students see only programs they are allowed to see — own campus +
   university-wide, non-hidden (or invited-hidden), and open (active,
   not past deadline, slots available).
3. Applying is a **pre-filled experience**: identity, course, year level,
   GWA, and units come from the verified profile; the student only
   answers the program's custom questions. **No essay, no document
   re-upload at apply time.**
4. Eligibility rules enforced server-side: a student may hold **one
   public program** at a time; **private programs** may be combined with
   the public one and with each other; approved scholars of one program
   can still be awarded others per the public/private rule.

### Stage 3 — Review & decision

1. Staff review applications in a queue (campus-scoped): profile snapshot,
   custom answers, GWA, eligibility summary.
2. Actions: move to *Under Review*, **Approve** (with notes) or
   **Reject** (with reason). Every change fires in-app + email + SMS
   notifications to the student automatically.
3. Students can edit or withdraw while *pending*; a resubmit flow covers
   corrections after rejection.

### Stage 4 — Batching & awarding

1. Approved applicants are grouped into a **batch named after the
   scholarship program** — created in one action (no manual per-student
   entry), campus-scoped.
2. Batches are viewable with each scholar's full information and are
   exportable to Excel for the scholarship office records.

### Stage 5 — Monitoring & compliance

1. Approved scholars download the official **Monitoring & Evaluation
   form** (LSPU-SFA-SF-006) from *My Scholarship*, have instructors sign
   it, and upload a photo/scan (PDF or image, ≤ 5 MB). Re-uploads replace
   the previous submission for the semester.
2. Staff/Admin see per-scholar M&E compliance in the Monitoring &
   Tracking table (submitted/not-submitted, viewable file).
3. The M&E deadline per academic period is configurable in System
   Settings; the student page shows color-coded deadline banners.
4. Students keep their documents current: they can replace their COR and
   Copy of Grades (re-verified by the same OCR pipeline), which updates
   GWA/units automatically.
5. Renewal follows the same lifecycle from Stage 2 next period.

---

## 3. Feature Inventory by Role

### Student
- Dashboard: application counters, approved-scholar banner, GWA card,
  document reminder, recent applications
- Scholarships list (campus + visibility scoped) with detail pages and
  pre-filled apply flow
- My Applications: status tracking (Pending/Review → Approved/Rejected),
  edit/withdraw while pending, per-application history
- My Scholarship (approved scholars): program details, benefits, batch,
  M&E form download/upload with deadline banners
- My Documents: replace COR/Grades (PDF, OCR re-verified, ≤ 5 MB)
- My Profile: identity, contact, year level (incl. 5th/Irregular/Graduate),
  course, campus (read-only), password change with policy enforcement
- Notifications: in-app with unread badge, backed by email + SMS
- AI Assistant: Gemini chatbot with live, visibility-scoped scholarship data

### Staff (campus-scoped)
- Review queue with approve/reject/under-review + notes
- Scholarship program CRUD with custom form fields, scope, announcement
- One-click batching by program; batch viewer; Excel export
- Monitoring & tracking incl. M&E compliance column
- Reports with Chart.js visualizations

### Admin (campus-scoped) — superset of staff
- User management (single Manage Users page: students, staff, admins,
  role changes, campus assignment)
- Campus-wide settings (M&E deadline), reports, audit log view
- All staff capabilities

### Super Admin (university scope)
- Campus context switcher (All / per-campus) in the navbar
- Sees and manages everything across all 4 campuses
- University-wide program creation (scope toggle)

### Guest
- Landing page, public scholarship browsing, AI Assistant (non-hidden
  programs only), registration/login

---

## 4. Cross-Cutting Functionalities

- **Notifications:** every workflow event fans out to in-app, Brevo email,
  and Semaphore/Twilio SMS
- **AI OCR verification:** registration and document replacement share the
  same extraction + cross-validation pipeline
- **AI chatbot:** rule-based fast paths + Gemini fallback; role- and
  visibility-aware; rate-limited; persistent history for logged-in users
- **Audit trail:** administrative actions logged for accountability
- **Multi-campus data isolation:** enforced at query level via
  `campus_context` helpers, not per-view hand-written filters
- **Exports:** Excel (batches/reports), PDF/DOCX generation available
- **Security:** CSRF everywhere, rate limiting, password policy, session
  fixation defense, OTP verification, file-type/size validation,
  visibility controls

---

## 5. What the System Replaced (for Chapter 2 comparison)

| Before (manual) | After (ScholarHub) |
|---|---|
| Paper application forms / Google Forms per program | One pre-filled digital application with per-program custom fields |
| Manual checking of COR/Grades authenticity | Automated OCR + Gemini verification at registration |
| Manual scholar batching by staff | One-click program-named batches |
| Bulletin-board / group-chat announcements | Targeted email + SMS + in-app broadcasts |
| Paper M&E form collection | Digital download/upload with deadline tracking and compliance table |
| Physical record keeping | Central MySQL database with exports and audit trail |
| One-campus scope | University-wide, 4 campuses, with campus and university-wide program scopes |

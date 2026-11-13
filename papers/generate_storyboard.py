"""Generate the LSPU ScholarHub User Storyboard DOCX.

Reads screenshots from papers/storyboard_images/ named:
  G1..G4      (Guest)
  S1..S10     (Student)
  ST1..ST9    (Staff)
  A1..A9      (Admin)
  SA1..SA8    (Super Admin)
Any missing image is skipped with a note. Run:  python papers/generate_storyboard.py
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

HERE = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(HERE, 'storyboard_images')
OUT = os.path.join(HERE, 'LSPU_ScholarHub_Storyboard.docx')

# (filename, figure title, what the page does, user action that leads to NEXT screen)
SCREENS = {
    'GUEST': [
        ('G1', 'Landing Page',
         'The public entry point of the system. It presents the Scholarship Office information, an overview of available scholarship programs, and navigation options for logging in or registering.',
         'The guest clicks Register to create an account.'),
        ('G2', 'Browse Scholarships',
         'Allows visitors to view all publicly available scholarship programs, including descriptions, benefits, and eligibility criteria, before creating an account.',
         'The guest clicks Login to access an existing account.'),
        ('G3', 'Registration Page',
         'Enables new students to create an account by uploading their Certificate of Registration (COR) and Report of Grades (ROG). OCR automatically extracts the name, student number, course, year level, units, and GWA, and verifies them against the uploaded files.',
         'After successful registration, the student is redirected to the login page.'),
        ('G4', 'Login Page',
         'Provides secure authentication for all users. Each user is redirected to the dashboard appropriate to their role after logging in.',
         'The user enters their credentials and logs in.'),
    ],
    'STUDENT': [
        ('S1', 'Student Dashboard',
         "Displays the student's overview: total applications, pending/under-review count, approved scholarships, and a reminder to keep their COR and grades up to date.",
         'The student clicks Browse Scholarships in the navigation bar.'),
        ('S2', 'Browse Scholarships',
         'Shows scholarship programs available to the student based on campus and academic period, with an Apply button for open programs. The system enforces the one-public-program rule.',
         'The student clicks Apply on a scholarship program.'),
        ('S3', 'Scholarship Application Form',
         'The application form with student details pre-filled from the profile (birthday, course, GWA, units). The student verifies the information and submits the application.',
         'After submission the student opens My Applications.'),
        ('S4', 'My Applications',
         'Lists all submitted applications with status tracking (Submitted, Under Review, Approved, Rejected) and the scholar tag per application.',
         'The student clicks an application to view its details.'),
        ('S5', 'Application Details',
         'Shows a single application with a visual progress tracker and review notes from the Scholarship Office. Editing is locked once the application is under review.',
         'The student returns to the dashboard and opens My Scholarship.'),
        ('S6', 'My Scholarship',
         'Displays the details of approved scholarship program(s): program name, benefits, award amount, batch assignment, and scholar status.',
         'The student opens Notifications from the navigation bar.'),
        ('S7', 'Notifications',
         'Shows announcements and notifications sent by staff and administrators, filtered by academic period, including title, message, and optional attachments.',
         'The student opens My Profile.'),
        ('S8', 'My Profile',
         "Displays the student's information. Email and phone number are editable; the name, student number, campus, course, and year level are locked and require Scholarship Office assistance.",
         'The student opens the Documents page.'),
        ('S9', 'Documents (COR / ROG)',
         'Allows the student to upload or replace their Certificate of Registration and Report of Grades (PDF only, 5 MB limit). OCR re-validates the student details on upload.',
         'The student opens the AI Chatbot.'),
        ('S10', 'AI Chatbot',
         'An AI-powered assistant that answers scholarship-related questions based on actual system data such as programs, eligibility, and application status.',
         'The student logs out or continues using the system.'),
    ],
    'STAFF': [
        ('ST1', 'Staff Dashboard',
         'Shows campus-level statistics: total applications, pending review, approved scholars, and recent activity, scoped to the selected campus and academic period.',
         'The staff opens Manage Scholarships.'),
        ('ST2', 'Manage Scholarships',
         'Lists scholarship programs with create, edit, close, and visibility controls. Programs with applicants cannot be edited.',
         'The staff clicks Add New Program.'),
        ('ST3', 'Create Scholarship Program',
         'The form for creating a scholarship program: name, description, benefits, funding type (public/private), campus, academic period, maximum applicants, and custom application fields.',
         'The staff saves and opens Review Applications.'),
        ('ST4', 'Review Applications',
         'Displays submitted applications with student details, GWA, and documents. Staff can approve or reject applications with notes.',
         'Approved students are batched; the staff opens Batches.'),
        ('ST5', 'Batch Students',
         'Allows staff to group approved applicants into batches per scholarship program and export batch lists to Excel.',
         'The staff opens the Student Directory.'),
        ('ST6', 'Student Directory',
         'A searchable, filterable list of registered students with their profiles, documents, and application status.',
         'The staff opens Announcements.'),
        ('ST7', 'Send Announcement',
         'The announcement composer with recipient selection (all students, by scholarship, by batch, or individual) and optional file attachment, sent via email and SMS.',
         'The staff opens Reports.'),
        ('ST8', 'Reports',
         'Analytics and charts on applications, approvals, GWA distribution, and scholarship statistics for the selected period and campus.',
         'The staff opens Monitor Scholars.'),
        ('ST9', 'Monitor Scholars',
         'Tracks active scholars, their status, and Monitoring and Evaluation form submissions which staff can view and verify.',
         'End of staff flow.'),
    ],
    'ADMIN': [
        ('A1', 'Admin Dashboard',
         'Campus overview with statistics and an academic period selector that scopes every page to the chosen period.',
         'The admin opens Manage Users.'),
        ('A2', 'Manage Users',
         'User account management in one place: creating accounts, changing roles, assigning campuses, and deactivating users.',
         'The admin opens Manage Scholarships.'),
        ('A3', 'Manage Scholarships',
         'The same scholarship management as staff, scoped to the admin campus: create, edit, close, and delete programs.',
         'The admin opens Manage Campuses.'),
        ('A4', 'Manage Campuses',
         'Campus configuration for the university: campus names, codes, and status used across registration and data scoping.',
         'The admin opens Academic Periods.'),
        ('A5', 'Manage Academic Periods',
         'Creating, editing, and deleting academic periods (e.g., 1st Semester AY 2026-2027) and setting the current period.',
         'The admin opens the Audit Log.'),
        ('A6', 'Audit Log',
         'A filterable activity trail (search, category, and role filters) of every significant action performed in the system, with Excel/PDF export.',
         'The admin opens Reports.'),
        ('A7', 'Reports',
         'Campus analytics: applications, approvals, GWA distribution, and scholarship statistics scoped by period and campus.',
         'The admin opens the Student Directory.'),
        ('A8', 'Student Directory',
         'Searchable student records with profiles, documents, application status, and scholar information.',
         'The admin opens Announcements.'),
        ('A9', 'Send Announcement',
         'The announcement composer with period-aware recipient lists and optional attachments, delivered by email and SMS.',
         'End of admin flow.'),
    ],
    'SUPER ADMIN': [
        ('SA1', 'Super Admin Dashboard',
         'University-wide statistics with a campus selector; the selected campus scopes all data shown.',
         'The super admin opens Manage Users.'),
        ('SA2', 'Manage Users',
         'System-wide account management across all campuses: creating users, assigning roles (super admin, admin, staff, student), and multi-campus assignments.',
         'The super admin opens Manage Campuses.'),
        ('SA3', 'Manage Campuses',
         'All campus records for the university, with codes and configuration used by registration, staff assignment, and data scoping.',
         'The super admin opens Academic Periods.'),
        ('SA4', 'Manage Academic Periods',
         'University-wide academic period management: create, edit, delete, and set the current period that scopes system data.',
         'The super admin opens the Audit Log.'),
        ('SA5', 'Audit Log',
         'The complete audit trail of every campus and user, with category, role, and search filters and export options.',
         'The super admin opens Reports.'),
        ('SA6', 'Reports',
         'University-wide analytics with per-campus or aggregated views across all campuses and periods.',
         'The super admin uses the campus selector.'),
        ('SA7', 'Campus Selector',
         'The header dropdown that switches the campus context; every page then reflects the chosen campus and period.',
         'End of super admin flow.'),
    ],
}

ROLE_ORDER = ['GUEST', 'STUDENT', 'STAFF', 'ADMIN', 'SUPER ADMIN']

NAVY = RGBColor(0x1F, 0x3A, 0x5F)
GRAY = RGBColor(0x59, 0x59, 0x59)


def add_caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(10)
    r.font.color.rgb = NAVY
    return p


def add_role_heading(doc, role, count):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f'{role.title()} User Storyboard')
    r.bold = True
    r.font.size = Pt(16)
    r.font.color.rgb = NAVY
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rs = sub.add_run(f'The following figures present the screens available to the {role.lower()} role ({count} screens).')
    rs.italic = True
    rs.font.size = Pt(10)
    rs.font.color.rgb = GRAY


def main():
    doc = Document()

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rt = title.add_run('LSPU ScholarHub\nUser Storyboard')
    rt.bold = True
    rt.font.size = Pt(22)
    rt.font.color.rgb = NAVY
    intro = doc.add_paragraph()
    intro.alignment = WD_ALIGN_PARAGRAPH.CENTER
    ri = intro.add_run(
        'The storyboard presents the sequence of screens for each user role, '
        'describing the purpose of every page and the action that leads to the next screen.'
    )
    ri.italic = True
    ri.font.size = Pt(10)
    ri.font.color.rgb = GRAY
    doc.add_paragraph()

    fig_no = 0
    included, missing = [], []

    for role in ROLE_ORDER:
        present = [(fn, t, d, a) for fn, t, d, a in SCREENS[role]
                   if os.path.exists(os.path.join(IMG_DIR, f'{fn}.png')) or
                      os.path.exists(os.path.join(IMG_DIR, f'{fn}.jpg')) or
                      os.path.exists(os.path.join(IMG_DIR, f'{fn}.jpeg'))]
        if not present:
            continue
        add_role_heading(doc, role, len(present))
        doc.add_paragraph()
        for i, (fn, t, d, action) in enumerate(present):
            img = next(f'{fn}.{ext}' for ext in ('png', 'jpg', 'jpeg')
                       if os.path.exists(os.path.join(IMG_DIR, f'{fn}.{ext}')))
            fig_no += 1
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture(os.path.join(IMG_DIR, img), width=Inches(5.5))
            add_caption(doc, f'Figure {fig_no}. {t}')
            desc = doc.add_paragraph()
            rd = desc.add_run(d)
            rd.font.size = Pt(10.5)
            if i < len(present) - 1:
                act = doc.add_paragraph()
                act.alignment = WD_ALIGN_PARAGRAPH.CENTER
                ra = act.add_run(f'\u2193  User Action: {action}')
                ra.italic = True
                ra.font.size = Pt(9.5)
                ra.font.color.rgb = GRAY
            doc.add_paragraph()
        included.extend(f'{role}:{fn}' for fn, *_ in present)

    for fn, t, *_ in sum((SCREENS[r] for r in ROLE_ORDER), []):
        if not any(fn in x for x in included):
            missing.append(fn)

    doc.save(OUT)
    print(f'Storyboard saved: {OUT}')
    print(f'Included {len(included)} screens: {", ".join(included) if included else "none yet"}')
    if missing:
        print(f'Missing ({len(missing)}): {", ".join(missing)}')


if __name__ == '__main__':
    os.makedirs(IMG_DIR, exist_ok=True)
    main()

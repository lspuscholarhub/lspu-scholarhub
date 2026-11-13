"""Generate Proposed Process Flow for LSPU ScholarHub — matches reference APPENDICES format.

Format: two-column table (Responsibility | Description) with ↓ flow arrows,
alternating Actor and System steps, ending with an outcome row (—).
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
import os

doc = Document()

for section in doc.sections:
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)

style = doc.styles['Normal']
style.font.name = 'Times New Roman'
style.font.size = Pt(12)

DOWN_ARROW = '↓'
OUTCOME = '—'


def add_heading(text, size=14, center=False):
    p = doc.add_paragraph()
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(size)
    run.font.name = 'Times New Roman'
    return p


def add_figure_caption(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(11)
    run.font.name = 'Times New Roman'
    return p


def add_process_flow(doc, steps):
    """steps: list of (responsibility, description) — responsibility '—' marks outcome."""
    table = doc.add_table(rows=0, cols=2)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Header row
    header = table.add_row()
    for i, text in enumerate(['Responsibility', 'Description']):
        cell = header.cells[i]
        cell.text = ''
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(11)
        run.font.name = 'Times New Roman'

    for resp, desc in steps:
        row = table.add_row()
        c0, c1 = row.cells

        # Arrow + responsibility
        p0 = c0.paragraphs[0]
        p0.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p0.add_run(DOWN_ARROW + '\n')
        run.font.size = Pt(11)
        run.font.name = 'Times New Roman'
        run = p0.add_run(resp)
        run.bold = resp not in (OUTCOME,)
        run.font.size = Pt(11)
        run.font.name = 'Times New Roman'

        # Description
        p1 = c1.paragraphs[0]
        run = p1.add_run(desc)
        run.font.size = Pt(11)
        run.font.name = 'Times New Roman'

        c0.width = Cm(4.0)
        c1.width = Cm(10.0)

    return table


# ═════════════════════════════════════════════════════════════════════════════
# PROPOSED PROCESS FLOWS
# ═════════════════════════════════════════════════════════════════════════════
add_heading('PROPOSED PROCESS FLOW', 16, center=True)
doc.add_paragraph()

# ── Figure 1. Student Registration ──────────────────────────────────────────
add_figure_caption('Figure 1. Student Registration Process Flow')
add_process_flow(doc, [
    ('Guest', 'Guest clicks Register and opens the registration page.'),
    ('System', 'System displays the registration form with document upload fields.'),
    ('Guest', 'Guest uploads Certificate of Registration (COR) and Report of Grades (ROG) in PDF format.'),
    ('System', 'System validates file type and size (PDF only, 5 MB limit).'),
    ('System', 'System extracts student details via OCR (name, student ID, course, year level, units, GWA) and auto-fills the form.'),
    ('Guest', 'Guest verifies the extracted details and completes birthday, email, and password.'),
    ('System', 'System validates that the entered details match the uploaded documents, checks for duplicate accounts, and creates the account.'),
    (OUTCOME, 'Student account created; student is redirected to the login page.'),
])
doc.add_paragraph()

# ── Figure 2. Scholarship Application ───────────────────────────────────────
add_figure_caption('Figure 2. Scholarship Application Process Flow')
add_process_flow(doc, [
    ('Student', 'Student logs in and opens the scholarship programs page.'),
    ('System', 'System displays open scholarship programs for the student\'s campus and current academic period.'),
    ('Student', 'Student selects a program and opens the application form.'),
    ('System', 'System pre-fills student details (birthday, course, year level, GWA, units) from the student profile.'),
    ('Student', 'Student verifies the information and submits the application.'),
    ('System', 'System checks eligibility (no duplicate application, one public program rule) and saves the application.'),
    ('System', 'System sends a confirmation notification to the student.'),
    (OUTCOME, 'Application submitted and queued for review.'),
])
doc.add_paragraph()

# ── Figure 3. Application Review and Approval ───────────────────────────────
add_figure_caption('Figure 3. Application Review and Approval Process Flow')
add_process_flow(doc, [
    ('Staff / Admin', 'Staff opens the Review Applications module.'),
    ('System', 'System displays pending applications filtered by campus and academic period.'),
    ('Staff', 'Staff opens an application and examines the student details and documents.'),
    ('Staff', 'Staff approves or rejects the application and records review notes.'),
    ('System', 'System validates the decision, updates the application status, and increments the program\'s approved count.'),
    ('System', 'System notifies the student of the decision via in-app notification and email.'),
    (OUTCOME, 'Application approved or rejected; student informed.'),
])
doc.add_paragraph()

# ── Figure 4. Batching of Approved Scholars ─────────────────────────────────
add_figure_caption('Figure 4. Batching of Approved Scholars Process Flow')
add_process_flow(doc, [
    ('Staff / Admin', 'Staff opens the Batches module.'),
    ('System', 'System displays existing batches and approved students awaiting batch assignment for the selected period.'),
    ('Staff', 'Staff creates a batch and selects the scholarship program; the system groups approved students by program automatically.'),
    ('System', 'System validates the batch, links it to the campus and academic period, and assigns the selected scholars.'),
    ('System', 'System notifies the batched scholars.'),
    (OUTCOME, 'Scholars organized into batches ready for fund disbursement.'),
])
doc.add_paragraph()

# ── Figure 5. Scholar Monitoring and Evaluation ─────────────────────────────
add_figure_caption('Figure 5. Scholar Monitoring and Evaluation Process Flow')
add_process_flow(doc, [
    ('Student', 'Student downloads the Monitoring and Evaluation form from the system.'),
    ('Student', 'Student completes the form and uploads a photo or PDF of the accomplished form.'),
    ('System', 'System validates the file and stores it under the student\'s scholarship record.'),
    ('Staff / Admin', 'Staff opens the Monitor Scholars module to review scholar compliance, GWA, and submitted M&E forms.'),
    ('System', 'System displays scholar status and at-risk indicators based on the latest grades on file.'),
    ('Staff', 'Staff marks scholars as compliant or at risk and follows up as needed.'),
    (OUTCOME, 'Scholar compliance monitored and recorded for the period.'),
])
doc.add_paragraph()

# ── Figure 6. Announcement Management ───────────────────────────────────────
add_figure_caption('Figure 6. Announcement Management Process Flow')
add_process_flow(doc, [
    ('Staff / Admin', 'Staff opens the Announcements page.'),
    ('System', 'System displays recent announcements filtered by campus and academic period.'),
    ('Staff', 'Staff clicks Send Announcement and selects recipients (individual students, by scholarship, or by batch).'),
    ('Staff', 'Staff writes the title and message and optionally attaches files.'),
    ('System', 'System warns if the currently viewed period is not the active period before sending.'),
    ('System', 'System delivers the announcement via in-app notification and email (and SMS when enabled), tagging it with the current academic period.'),
    (OUTCOME, 'Announcement delivered; recipients notified.'),
])
doc.add_paragraph()

# ── Figure 7. Document Update / Replacement ─────────────────────────────────
add_figure_caption('Figure 7. Student Document Update Process Flow')
add_process_flow(doc, [
    ('Student', 'Student opens the Documents page.'),
    ('System', 'System displays the current Certificate of Registration and Report of Grades on file.'),
    ('Student', 'Student uploads a replacement document (PDF only).'),
    ('System', 'System validates the file type and size, then re-extracts the student details via OCR.'),
    ('System', 'System verifies the extracted details match the account and replaces the stored file.'),
    (OUTCOME, 'Student records updated with the latest documents.'),
])
doc.add_paragraph()

# ── Figure 8. Academic Period and Campus Management ─────────────────────────
add_figure_caption('Figure 8. Academic Period and Campus Management Process Flow')
add_process_flow(doc, [
    ('Super Admin', 'Super Admin opens the Periods (Settings) page.'),
    ('System', 'System displays all academic periods and campuses.'),
    ('Super Admin', 'Super Admin creates, edits, or deletes an academic period and sets the current active period.'),
    ('System', 'System validates the period and applies it as the default data context for all users.'),
    ('Admin / Super Admin', 'Admin switches the campus selector to manage campus-scoped data.'),
    ('System', 'System filters dashboards, applications, reports, and announcements by the selected campus and period.'),
    (OUTCOME, 'System data scoped correctly per campus and academic period.'),
])
doc.add_paragraph()

# ── Figure 9. User and Role Management ──────────────────────────────────────
add_figure_caption('Figure 9. User and Role Management Process Flow')
add_process_flow(doc, [
    ('Admin / Super Admin', 'Admin opens the Manage Users page.'),
    ('System', 'System displays user accounts filtered by campus (all campuses for Super Admin).'),
    ('Admin', 'Admin creates a user, changes a role, or assigns a staff member to one or more campuses.'),
    ('System', 'System validates the changes, updates the account, and records the action in the audit log.'),
    (OUTCOME, 'User accounts and roles updated with a full audit trail.'),
])
doc.add_paragraph()

# ── Figure 10. Scholarship Program Management ───────────────────────────────
add_figure_caption('Figure 10. Scholarship Program Management Process Flow')
add_process_flow(doc, [
    ('Staff / Admin', 'Staff opens the Manage Scholarships page.'),
    ('System', 'System displays scholarship programs with period badges (Permanent or period-specific).'),
    ('Staff', 'Staff creates a new program (title, benefits, award, requirements, campus, academic period) or edits an existing one.'),
    ('System', 'System blocks editing when a program already has applicants and saves the program otherwise.'),
    ('System', 'System publishes the program to students of the assigned campus and period.'),
    (OUTCOME, 'Scholarship program created or updated and visible to eligible students.'),
])

# Save
output_path = os.path.join(os.path.dirname(__file__), 'LSPU_ScholarHub_Proposed_Process_Flow.docx')
doc.save(output_path)
print(f'DOCX saved: {output_path}')

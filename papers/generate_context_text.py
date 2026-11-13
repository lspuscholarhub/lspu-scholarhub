"""Generate System Context Diagram (text-based) for LSPU ScholarHub — DOCX format."""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from docx import Document
from docx.shared import Pt, Cm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os

doc = Document()

# Page margins
for section in doc.sections:
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)

# Default font
style = doc.styles['Normal']
font = style.font
font.name = 'Times New Roman'
font.size = Pt(12)
pf = style.paragraph_format
pf.space_after = Pt(6)
pf.line_spacing = 1.15

# ── Helper: Add heading with underline style ────────────────────────────────
def add_heading_styled(doc, text, level=1):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(14) if level == 1 else Pt(12)
    run.font.name = 'Times New Roman'
    return p

def add_body(doc, text, first_indent=True):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if first_indent:
        p.paragraph_format.first_line_indent = Cm(1.27)
    run = p.add_run(text)
    run.font.size = Pt(12)
    run.font.name = 'Times New Roman'
    return p

def add_body_mixed(doc, segments, first_indent=True):
    """segments: list of (text, bold) tuples"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if first_indent:
        p.paragraph_format.first_line_indent = Cm(1.27)
    for text, bold in segments:
        run = p.add_run(text)
        run.font.size = Pt(12)
        run.font.name = 'Times New Roman'
        run.bold = bold
    return p

# ── Title ────────────────────────────────────────────────────────────────────
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = title.add_run('SYSTEM CONTEXT DIAGRAM')
run.bold = True
run.font.size = Pt(16)
run.font.name = 'Times New Roman'
run.underline = True

doc.add_paragraph()

# ── Body Text ────────────────────────────────────────────────────────────────
add_body_mixed(doc, [
    ('Five main groups of users interact with LSPU ScholarHub: the ', False),
    ('Super Administrator', True),
    (', ', False),
    ('Administrators', True),
    (' (Campus Admins), ', False),
    ('Staff Members', True),
    (' (Scholarship Office personnel), ', False),
    ('Students/Scholars', True),
    (', and ', False),
    ('Guests', True),
    (' (unauthenticated visitors). All users are required to register and create secure accounts, governed by Role-Based Access Control (RBAC) and session-based authentication, before accessing the features of the system. Registered users can then perform specific functions based on their assigned roles within the platform.', False),
])

add_body_mixed(doc, [
    ('The ', False),
    ('Super Administrator', True),
    (' holds system-wide authority across all campuses of Laguna State Polytechnic University. This role manages all user accounts (including role assignments), configures academic periods, oversees campus management, controls system-wide settings, and has unrestricted access to the complete audit log and analytics. The Super Administrator can switch between campus views to monitor data across the entire university.', False),
])

add_body_mixed(doc, [
    ('Administrators', True),
    (' (Campus Admins) manage their respective campus operations. They create and manage scholarship programs, review and approve or reject student applications, batch approved scholars, monitor active scholars, send announcements to students, generate campus-specific reports, and manage users within their assigned campus. Administrators also handle academic period configuration and maintain the student directory.', False),
])

add_body_mixed(doc, [
    ('Staff Members', True),
    (' (Scholarship Office personnel) perform day-to-day scholarship management tasks. They create and edit scholarship programs, process incoming applications by reviewing student submissions and documents, group approved students into batches for fund disbursement, monitor scholar compliance and academic standing, compose and send announcements (with optional email/SMS delivery and file attachments), import student data via CSV/Excel uploads, and generate detailed reports filtered by campus and academic period.', False),
])

add_body_mixed(doc, [
    ('Students/Scholars', True),
    (' interact with the system through a web-based interface to browse available scholarship programs, submit applications with required information, track their application status through a visual progress indicator (Submitted → Under Review → Approved/Rejected), manage their profile and uploaded documents (Certificate of Registration and Report of Grades), view their approved scholarship details, receive notifications and announcements, download and upload Monitoring and Evaluation forms when required, and interact with an AI-powered chatbot for scholarship-related inquiries.', False),
])

add_body_mixed(doc, [
    ('Guests', True),
    (' (unauthenticated visitors) can access the public-facing features of the system, including browsing available scholarship programs and their eligibility criteria, viewing general system information, and interacting with the AI chatbot. Guests may also register for a student account by uploading their academic documents, which are automatically processed using Optical Character Recognition (OCR) to pre-fill registration details.', False),
])

add_body(doc,
    'On the backend, LSPU ScholarHub integrates with several external services to deliver its core functionality. '
    'Email notifications are dispatched through the Resend API, while SMS alerts are sent via an external SMS gateway. '
    'Document processing and AI-powered chatbot responses are powered by the Google Gemini API, which extracts student '
    'information from uploaded Certificate of Registration and Report of Grades files. All system data—including user '
    'accounts, scholarship programs, applications, batches, notifications, and audit logs—is stored in a MySQL database '
    'hosted on the Railway cloud platform. Uploaded files such as student documents, monitoring forms, and announcement '
    'attachments are securely stored and retrieved through Cloudinary cloud storage. The system enforces campus-based '
    'and academic period-based data isolation, ensuring that each user sees only the data relevant to their assigned '
    'campus and selected academic period.',
)

doc.add_paragraph()

# ── Table: User Roles Summary ────────────────────────────────────────────────
h = doc.add_paragraph()
run = h.add_run('Table A-1. User Roles and Responsibilities')
run.bold = True
run.font.size = Pt(10)
run.font.name = 'Times New Roman'
h.alignment = WD_ALIGN_PARAGRAPH.CENTER

table = doc.add_table(rows=1, cols=3)
table.style = 'Light Grid Accent 1'
table.alignment = WD_TABLE_ALIGNMENT.CENTER

headers = ['User Role', 'Access Level', 'Key Responsibilities']
for i, header in enumerate(headers):
    cell = table.rows[0].cells[i]
    cell.text = ''
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(header)
    run.bold = True
    run.font.size = Pt(10)
    run.font.name = 'Times New Roman'

roles = [
    ('Super Admin', 'System-wide',
     'Manage all users, roles, campuses, academic periods, system settings. '
     'View complete audit log and university-wide analytics.'),
    ('Admin (Campus Admin)', 'Campus-scoped',
     'Manage scholarship programs, review applications, batch scholars, '
     'send announcements, manage campus users, view campus reports.'),
    ('Staff (Scholarship Office)', 'Campus-scoped',
     'Create/edit scholarships, review applications, batch approved students, '
     'monitor scholars, import students, send announcements, view reports.'),
    ('Student / Scholar', 'Personal data',
     'Apply for scholarships, manage profile/documents, view application status, '
     'view notifications, download/upload M&E forms, use AI chatbot.'),
    ('Guest', 'Public only',
     'Browse scholarship programs, view system info, use AI chatbot, register account.'),
]

for role, access, resp in roles:
    row = table.add_row()
    cells = row.cells
    
    p = cells[0].paragraphs[0]
    run = p.add_run(role)
    run.font.size = Pt(10)
    run.font.name = 'Times New Roman'
    run.bold = True
    
    p = cells[1].paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(access)
    run.font.size = Pt(10)
    run.font.name = 'Times New Roman'
    
    p = cells[2].paragraphs[0]
    run = p.add_run(resp)
    run.font.size = Pt(10)
    run.font.name = 'Times New Roman'

for row in table.rows:
    row.cells[0].width = Cm(3.5)
    row.cells[1].width = Cm(2.5)
    row.cells[2].width = Cm(10.0)

doc.add_paragraph()

# ── Table: External Systems ──────────────────────────────────────────────────
h2 = doc.add_paragraph()
run = h2.add_run('Table A-2. External Systems and Services')
run.bold = True
run.font.size = Pt(10)
run.font.name = 'Times New Roman'
h2.alignment = WD_ALIGN_PARAGRAPH.CENTER

table2 = doc.add_table(rows=1, cols=3)
table2.style = 'Light Grid Accent 1'
table2.alignment = WD_TABLE_ALIGNMENT.CENTER

for i, header in enumerate(['External System', 'Purpose', 'Integration']):
    cell = table2.rows[0].cells[i]
    cell.text = ''
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(header)
    run.bold = True
    run.font.size = Pt(10)
    run.font.name = 'Times New Roman'

ext_systems = [
    ('MySQL Database (Railway)', 'Primary data storage for all system entities',
     'SQLAlchemy ORM, hosted on Railway cloud platform'),
    ('Cloudinary', 'Cloud file storage for uploaded documents and attachments',
     'REST API for upload/retrieve'),
    ('Resend API', 'Email notification delivery (announcements, status updates)',
     'REST API integration'),
    ('SMS Gateway', 'SMS notification delivery for critical alerts',
     'API integration'),
    ('Google Gemini API', 'OCR document processing and AI chatbot responses',
     'REST API integration'),
]

for name, purpose, integration in ext_systems:
    row = table2.add_row()
    cells = row.cells
    
    p = cells[0].paragraphs[0]
    run = p.add_run(name)
    run.font.size = Pt(10)
    run.font.name = 'Times New Roman'
    run.bold = True
    
    p = cells[1].paragraphs[0]
    run = p.add_run(purpose)
    run.font.size = Pt(10)
    run.font.name = 'Times New Roman'
    
    p = cells[2].paragraphs[0]
    run = p.add_run(integration)
    run.font.size = Pt(10)
    run.font.name = 'Times New Roman'

for row in table2.rows:
    row.cells[0].width = Cm(3.5)
    row.cells[1].width = Cm(6.5)
    row.cells[2].width = Cm(6.0)

# Save
output_path = os.path.join(os.path.dirname(__file__), 'LSPU_ScholarHub_Context_Description.docx')
doc.save(output_path)
print(f"DOCX saved: {output_path}")

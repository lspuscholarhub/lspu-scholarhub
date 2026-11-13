"""Generate Use Case Diagram for LSPU ScholarHub and save as DOCX."""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
import os

# ── Use Case Data ────────────────────────────────────────────────────────────
actors = {
    'Guest': {
        'color': '#6c757d',
        'use_cases': [
            'View Scholarship\nPrograms',
            'Register\nAccount',
            'Login',
            'Use AI\nChatbot',
        ]
    },
    'Student': {
        'color': '#0d6efd',
        'use_cases': [
            'Login',
            'View Dashboard',
            'Browse & Apply\nfor Scholarships',
            'View My\nApplications',
            'Edit Application',
            'View My\nScholarship',
            'View Notifications',
            'Update Profile',
            'Upload/Replace\nDocuments',
            'Download & Upload\nM&E Form',
            'Use AI Chatbot',
            'Logout',
        ]
    },
    'Staff': {
        'color': '#198754',
        'use_cases': [
            'Login',
            'View Dashboard',
            'Manage\nScholarships',
            'Review\nApplications',
            'Batch Approved\nStudents',
            'Monitor\nScholars',
            'View Student\nDirectory',
            'Send\nAnnouncements',
            'View Reports',
            'Import\nStudents',
            'Logout',
        ]
    },
    'Admin': {
        'color': '#dc3545',
        'use_cases': [
            'Login',
            'View Dashboard',
            'Manage\nScholarships',
            'Review\nApplications',
            'Batch Approved\nStudents',
            'Monitor\nScholars',
            'View Student\nDirectory',
            'Send\nAnnouncements',
            'View Reports',
            'Manage Users',
            'Manage\nCampuses',
            'Manage Academic\nPeriods',
            'View Audit Log',
            'Logout',
        ]
    },
    'Super Admin': {
        'color': '#6f42c1',
        'use_cases': [
            'Login',
            'View Dashboard\n(Campus Selector)',
            'Manage All\nCampuses',
            'Manage Users\n& Roles',
            'Manage Academic\nPeriods',
            'View System-wide\nReports',
            'View Audit Log',
            'Manage System\nSettings',
            'Logout',
        ]
    }
}

# ── Helper: Draw stick figure ───────────────────────────────────────────────
def draw_stick_figure(ax, x, y, color='#333', scale=1.0, label=None):
    """Draw a stick figure actor."""
    s = scale
    # Head
    head = plt.Circle((x, y + 0.35*s), 0.08*s, fill=False, edgecolor=color, linewidth=1.8)
    ax.add_patch(head)
    # Body
    ax.plot([x, x], [y + 0.27*s, y + 0.05*s], color=color, linewidth=1.8)
    # Arms
    ax.plot([x - 0.12*s, x + 0.12*s], [y + 0.22*s, y + 0.22*s], color=color, linewidth=1.8)
    # Legs
    ax.plot([x - 0.1*s, x, x + 0.1*s], [y - 0.08*s, y + 0.05*s, y - 0.08*s], color=color, linewidth=1.8)
    # Label
    if label:
        ax.text(x, y - 0.18*s, label, ha='center', va='top', fontsize=8, fontweight='bold', color=color)

# ── Helper: Draw use case oval ──────────────────────────────────────────────
def draw_usecase(ax, x, y, text, w=0.38, h=0.18, color='#dee2e6', ec='#666'):
    """Draw a use case oval with text."""
    ellipse = mpatches.Ellipse((x, y), w, h, facecolor=color, edgecolor=ec, linewidth=1.2, alpha=0.92)
    ax.add_patch(ellipse)
    ax.text(x, y, text, ha='center', va='center', fontsize=5.5, color='#222',
            fontfamily='sans-serif', linespacing=1.15)

# ── Helper: Draw system boundary ────────────────────────────────────────────
def draw_boundary(ax, x, y, w, h, label, color='#495057'):
    """Draw system boundary rectangle."""
    rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02",
                          facecolor='none', edgecolor=color, linewidth=1.5, linestyle='--')
    ax.add_patch(rect)
    ax.text(x + w/2, y + h + 0.03, label, ha='center', va='bottom', fontsize=9,
            fontweight='bold', color=color, fontfamily='sans-serif')

# ── Main Diagram ────────────────────────────────────────────────────────────
fig, ax = plt.subplots(1, 1, figsize=(16, 11), dpi=200)
ax.set_xlim(-0.5, 4.0)
ax.set_ylim(-0.3, 3.2)
ax.set_aspect('equal')
ax.axis('off')

# System boundary
draw_boundary(ax, 1.0, -0.15, 1.9, 3.1, 'LSPU ScholarHub — System Boundary')

# ── Layout: 5 actor columns ─────────────────────────────────────────────────
actor_positions = {
    'Guest':      0.15,
    'Student':    0.85,
    'Staff':      1.55,
    'Admin':      2.25,
    'Super Admin': 2.95,
}

uc_y_start = 2.7
uc_y_spacing = 0.26

for actor_name, info in actors.items():
    ax_x = actor_positions[actor_name]
    color = info['color']
    
    # Draw actor stick figure at top
    fig_y = 2.95
    draw_stick_figure(ax, ax_x, fig_y, color=color, scale=0.8, label=actor_name)
    
    # Draw use cases
    for i, uc in enumerate(info['use_cases']):
        uc_y = fig_y - 0.35 - i * 0.28
        # Stagger slightly left/right for readability
        uc_x = ax_x + 0.05 if i % 2 == 0 else ax_x - 0.05
        
        # Color the oval based on actor
        draw_usecase(ax, uc_x, uc_y, uc, w=0.42, h=0.18, color=color + '18', ec=color)
        
        # Draw connecting line from actor to use case
        ax.plot([ax_x, uc_x], [fig_y - 0.22, uc_y + 0.09],
                color=color, linewidth=0.6, alpha=0.4, linestyle='-')

# ── Relationships ────────────────────────────────────────────────────────────
# Student "Login" is the same as Guest "Login" — use <<include>>
# Student → "View Dashboard" includes login
# Use dashed arrows for include/extend relationships

def draw_include(ax, x1, y1, x2, y2, label='<<include>>', color='#888'):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=0.8, linestyle='dashed'))
    mx, my = (x1+x2)/2, (y1+y2)/2
    ax.text(mx, my + 0.03, label, ha='center', va='bottom', fontsize=4.5, color=color, style='italic')

# Title
ax.text(2.0, 3.15, 'USE CASE DIAGRAM — LSPU ScholarHub', ha='center', va='bottom',
        fontsize=13, fontweight='bold', color='#212529', fontfamily='sans-serif')

# Legend
legend_x, legend_y = 0.0, -0.22
for i, (name, info) in enumerate(actors.items()):
    ax.add_patch(plt.Rectangle((legend_x + i*0.82, legend_y), 0.06, 0.06, 
                                facecolor=info['color'], alpha=0.7))
    ax.text(legend_x + i*0.82 + 0.09, legend_y + 0.03, name, fontsize=6, va='center', color='#333')

plt.tight_layout(pad=0.3)
diagram_path = os.path.join(os.path.dirname(__file__), 'usecase_diagram.png')
plt.savefig(diagram_path, dpi=200, bbox_inches='tight', facecolor='white')
plt.close()
print(f"Diagram saved: {diagram_path}")

# ── DOCX ─────────────────────────────────────────────────────────────────────
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

# Title
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = title.add_run('USE CASE DIAGRAM')
run.bold = True
run.font.size = Pt(16)
run.font.name = 'Times New Roman'

# Subtitle
sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = sub.add_run('LSPU ScholarHub — Scholarship Management System')
run.font.size = Pt(12)
run.font.name = 'Times New Roman'
run.italic = True

doc.add_paragraph()

# Insert diagram
if os.path.exists(diagram_path):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(diagram_path, width=Inches(6.2))
    
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = cap.add_run('Figure A-1. Use Case Diagram of LSPU ScholarHub')
    run.bold = True
    run.font.size = Pt(10)
    run.font.name = 'Times New Roman'

doc.add_paragraph()

# ── Use Case Descriptions ────────────────────────────────────────────────────
h = doc.add_paragraph()
run = h.add_run('USE CASE DESCRIPTIONS')
run.bold = True
run.font.size = Pt(14)
run.font.name = 'Times New Roman'

use_case_table = [
    # (ID, Use Case, Actor, Description)
    ('UC-01', 'View Scholarship Programs', 'Guest',
     'The guest browses available scholarship programs displayed on the public scholarship listing page. Programs show title, description, benefits, eligibility criteria, and status (Open/Closed).'),
    ('UC-02', 'Register Account', 'Guest',
     'The guest creates a new student account by uploading a Certificate of Registration (COR) and Report of Grades (ROG) as PDF files. The system uses OCR to auto-fill student details (name, ID, course, year level, GWA, units). The guest sets email, password, birthday, and year level.'),
    ('UC-03', 'Login', 'Guest, Student, Staff, Admin, Super Admin',
     'The user authenticates using their email and password. The system validates credentials and redirects to the appropriate dashboard based on role.'),
    ('UC-04', 'Use AI Chatbot', 'Guest, Student',
     'The user interacts with an AI-powered chatbot to ask questions about scholarship programs, eligibility, requirements, and application status. The chatbot responds based on system data.'),
    ('UC-05', 'View Dashboard', 'Student, Staff, Admin, Super Admin',
     'The user views a summary dashboard showing key metrics. Students see application status and scholarship info. Staff/Admin see campus-specific statistics. Super Admin can switch between campuses.'),
    ('UC-06', 'Browse & Apply for Scholarships', 'Student',
     'The student browses available scholarship programs, selects one to apply, fills out the application form with required information, and submits. The system checks for duplicate applications and enforces the one-public-program rule.'),
    ('UC-07', 'View My Applications', 'Student',
     'The student views a list of their submitted applications with status tracking (Submitted → Under Review → Approved/Rejected). Each application shows a progress indicator.'),
    ('UC-08', 'Edit Application', 'Student',
     'The student edits their application details before it is reviewed. Once the application status changes to "Under Review" or beyond, editing is locked.'),
    ('UC-09', 'View My Scholarship', 'Student',
     'The student views details of their approved scholarship program(s), including program name, benefits, award amount, batch assignment, and scholar status.'),
    ('UC-10', 'View Notifications', 'Student, Staff, Admin',
     'The user views announcements and notifications filtered by their campus and academic period. Unread count is displayed in the navigation bar.'),
    ('UC-11', 'Update Profile', 'Student',
     'The student updates editable profile fields (email, phone number). Fields like name, student ID, course, campus, and year level are locked and require scholarship office intervention.'),
    ('UC-12', 'Upload/Replace Documents', 'Student',
     'The student uploads or replaces their Certificate of Registration (COR) and Report of Grades (ROG) documents. Only PDF files are accepted. The system re-validates student details via OCR upon upload.'),
    ('UC-13', 'Download & Upload M&E Form', 'Student',
     'The student downloads the Monitoring and Evaluation form (if required by the scholarship program), fills it out, and uploads a photo/PDF of the completed form.'),
    ('UC-14', 'Manage Scholarships', 'Staff, Admin',
     'The staff/admin creates, edits, closes, deletes, and toggles visibility of scholarship programs. Programs can be linked to specific academic periods or marked as permanent. Editing is blocked if the program has existing applicants.'),
    ('UC-15', 'Review Applications', 'Staff, Admin',
     'The staff/admin reviews pending scholarship applications. Actions include Approve, Reject, or Request Revision. Review notes are recorded for each decision.'),
    ('UC-16', 'Batch Approved Students', 'Staff, Admin',
     'The staff/admin groups approved students into batches for each scholarship program. Batches are linked to academic periods and campuses.'),
    ('UC-17', 'Monitor Scholars', 'Staff, Admin',
     'The staff/admin monitors active scholars, their compliance status, GWA, and at-risk indicators. The monitoring page is filtered by campus and academic period.'),
    ('UC-18', 'View Student Directory', 'Staff, Admin',
     'The staff/admin views a searchable directory of all registered students with their details (name, ID, course, year level, campus, GWA). Filtered by campus and period.'),
    ('UC-19', 'Send Announcements', 'Staff, Admin',
     'The staff/admin composes and sends announcements to selected students, scholarship groups, or batches. Announcements can include email/SMS delivery and optional file attachments. Period-scoped.'),
    ('UC-20', 'View Reports', 'Staff, Admin',
     'The staff/admin views analytics and reports including application statistics, scholarship distribution, GWA breakdowns, and demographic data. Filtered by campus and academic period.'),
    ('UC-21', 'Import Students', 'Staff',
     'The staff imports student data via CSV/Excel upload. Imported students are assigned to the staff\'s campus. OCR validation is performed on uploaded documents.'),
    ('UC-22', 'Manage Users', 'Admin, Super Admin',
     'The admin/super admin creates, edits, and manages user accounts. Role changes (Student ↔ Staff ↔ Admin) are supported. Multi-campus assignment is available for staff.'),
    ('UC-23', 'Manage Campuses', 'Admin, Super Admin',
     'The admin manages campus listings. Super Admin can manage all campuses system-wide.'),
    ('UC-24', 'Manage Academic Periods', 'Admin, Super Admin',
     'The admin/super admin creates, edits, and deletes academic periods (e.g., "1st Semester AY 2026-2027"). Setting a period as "current" determines the default view.'),
    ('UC-25', 'View Audit Log', 'Admin, Super Admin',
     'The admin views a chronological log of all system actions (logins, application changes, user modifications, etc.) with filters by category, role, and search. Exportable to Excel/PDF.'),
    ('UC-26', 'Manage System Settings', 'Super Admin',
     'The super admin manages system-wide settings including notification templates, system announcements, and global configuration.'),
    ('UC-27', 'Logout', 'All Users',
     'The user ends their session and is redirected to the login page.'),
]

# Create table
table = doc.add_table(rows=1, cols=4)
table.style = 'Light Grid Accent 1'
table.alignment = WD_TABLE_ALIGNMENT.CENTER

# Header
headers = ['ID', 'Use Case', 'Actor(s)', 'Description']
for i, header in enumerate(headers):
    cell = table.rows[0].cells[i]
    cell.text = ''
    p = cell.paragraphs[0]
    run = p.add_run(header)
    run.bold = True
    run.font.size = Pt(10)
    run.font.name = 'Times New Roman'

# Data rows
for uc_id, uc_name, actor, desc in use_case_table:
    row = table.add_row()
    cells = row.cells
    
    # ID
    p = cells[0].paragraphs[0]
    run = p.add_run(uc_id)
    run.font.size = Pt(9)
    run.font.name = 'Times New Roman'
    
    # Use Case
    p = cells[1].paragraphs[0]
    run = p.add_run(uc_name)
    run.font.size = Pt(9)
    run.font.name = 'Times New Roman'
    run.bold = True
    
    # Actor
    p = cells[2].paragraphs[0]
    run = p.add_run(actor)
    run.font.size = Pt(9)
    run.font.name = 'Times New Roman'
    
    # Description
    p = cells[3].paragraphs[0]
    run = p.add_run(desc)
    run.font.size = Pt(9)
    run.font.name = 'Times New Roman'

# Set column widths
for row in table.rows:
    row.cells[0].width = Cm(1.5)
    row.cells[1].width = Cm(3.5)
    row.cells[2].width = Cm(3.0)
    row.cells[3].width = Cm(8.0)

doc.add_paragraph()

# ── Actor Descriptions ──────────────────────────────────────────────────────
h2 = doc.add_paragraph()
run = h2.add_run('ACTOR DESCRIPTIONS')
run.bold = True
run.font.size = Pt(14)
run.font.name = 'Times New Roman'

actor_table = [
    ('Guest', 'An unauthenticated visitor who can browse scholarship programs, view system information, and register for an account.'),
    ('Student / Scholar', 'A registered student who can apply for scholarships, manage their profile and documents, view application status, and receive notifications. Limited to one active public scholarship program.'),
    ('Staff', 'A scholarship office staff member who manages scholarship programs, reviews applications, batches approved students, monitors scholars, and sends announcements. Assigned to one or more campuses.'),
    ('Admin', 'A campus administrator with full management capabilities including user management, campus management, academic period management, and system-wide reporting.'),
    ('Super Admin', 'The system-wide administrator with unrestricted access across all campuses. Can manage all users, campuses, academic periods, system settings, and view the complete audit log.'),
]

table2 = doc.add_table(rows=1, cols=2)
table2.style = 'Light Grid Accent 1'
table2.alignment = WD_TABLE_ALIGNMENT.CENTER

headers2 = ['Actor', 'Description']
for i, header in enumerate(headers2):
    cell = table2.rows[0].cells[i]
    cell.text = ''
    p = cell.paragraphs[0]
    run = p.add_run(header)
    run.bold = True
    run.font.size = Pt(10)
    run.font.name = 'Times New Roman'

for actor_name, desc in actor_table:
    row = table2.add_row()
    cells = row.cells
    
    p = cells[0].paragraphs[0]
    run = p.add_run(actor_name)
    run.font.size = Pt(10)
    run.font.name = 'Times New Roman'
    run.bold = True
    
    p = cells[1].paragraphs[0]
    run = p.add_run(desc)
    run.font.size = Pt(10)
    run.font.name = 'Times New Roman'

for row in table2.rows:
    row.cells[0].width = Cm(3.5)
    row.cells[1].width = Cm(12.5)

# Save
output_path = os.path.join(os.path.dirname(__file__), 'LSPU_ScholarHub_UseCase_Diagram.docx')
doc.save(output_path)
print(f"DOCX saved: {output_path}")
print(f"\nDiagram: {diagram_path}")

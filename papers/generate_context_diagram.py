"""Generate System Context Diagram for LSPU ScholarHub and save as DOCX."""
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

# ── Data ─────────────────────────────────────────────────────────────────────
external_entities = [
    # (name, x, y, color, shape)
    ('Student / Scholar',   0.5, 2.0, '#0d6efd', 'rect'),
    ('Staff\n(Scholarship Office)', 1.5, 3.2, '#198754', 'rect'),
    ('Admin\n(Campus Admin)', 2.5, 3.2, '#dc3545', 'rect'),
    ('Super Admin',         3.5, 2.0, '#6f42c1', 'rect'),
    ('Email Service\n(Resend API)', 0.5, 0.5, '#fd7e14', 'db'),
    ('SMS Service',         1.5, 0.0, '#fd7e14', 'db'),
    ('AI / OCR Service\n(Gemini API)', 2.5, 0.0, '#fd7e14', 'db'),
    ('MySQL Database\n(Railway)',      3.5, 0.5, '#20c997', 'cylinder'),
    ('Cloud Storage\n(Cloudinary)',    4.3, 1.5, '#20c997', 'cylinder'),
]

data_flows = [
    # (from_entity_idx, to_entity_idx, label, color)
    (0, 'sys', 'Apply for Scholarship\nUpload Documents', '#0d6efd'),
    ('sys', 0, 'Application Status\nNotifications\nScholarship Info', '#0d6efd'),
    (1, 'sys', 'Manage Scholarships\nReview Applications\nSend Announcements', '#198754'),
    ('sys', 1, 'Application List\nReports\nStudent Directory', '#198754'),
    (2, 'sys', 'Manage Users\nManage Campuses\nManage Periods', '#dc3545'),
    ('sys', 2, 'System Reports\nAudit Log\nUser List', '#dc3545'),
    (3, 'sys', 'System Settings\nCampus Selector\nAll Reports', '#6f42c1'),
    ('sys', 3, 'System Status\nAudit Log\nFull Access Data', '#6f42c1'),
    ('sys', 4, 'Send Email\n(Notification)', '#fd7e14'),
    (4, 'sys', 'Delivery Status', '#fd7e14'),
    ('sys', 5, 'Send SMS\n(Notification)', '#fd7e14'),
    ('sys', 6, 'OCR Document\nAI Chatbot Query', '#fd7e14'),
    (6, 'sys', 'Extracted Data\nAI Response', '#fd7e14'),
    ('sys', 7, 'Read/Write\nData', '#20c997'),
    ('sys', 8, 'Store/Retrieve\nFiles', '#20c997'),
]

# ── Main Diagram ────────────────────────────────────────────────────────────
fig, ax = plt.subplots(1, 1, figsize=(16, 10), dpi=200)
ax.set_xlim(-0.2, 5.0)
ax.set_ylim(-0.6, 3.8)
ax.set_aspect('equal')
ax.axis('off')

# ── System Box (center) ─────────────────────────────────────────────────────
sys_x, sys_y, sys_w, sys_h = 1.3, 1.2, 2.4, 1.5
rect = FancyBboxPatch((sys_x, sys_y), sys_w, sys_h,
                       boxstyle="round,pad=0.05",
                       facecolor='#e7f1ff', edgecolor='#0d6efd', linewidth=2.5)
ax.add_patch(rect)
ax.text(sys_x + sys_w/2, sys_y + sys_h/2 + 0.12, 'LSPU ScholarHub',
        ha='center', va='center', fontsize=14, fontweight='bold', color='#0d6efd',
        fontfamily='sans-serif')
ax.text(sys_x + sys_w/2, sys_y + sys_h/2 - 0.12, 'Scholarship Management\nSystem',
        ha='center', va='center', fontsize=9, color='#495057',
        fontfamily='sans-serif', linespacing=1.3)

# ── External Entities ────────────────────────────────────────────────────────
entity_boxes = {}  # idx -> (cx, cy, w, h)

for i, (name, ex, ey, color, shape) in enumerate(external_entities):
    w, h = 0.85, 0.45
    cx, cy = ex, ey
    
    if shape == 'cylinder':
        # Database/cloud cylinder
        ellipse_top = mpatches.Ellipse((cx, cy + h/2), w, 0.15, facecolor=color, edgecolor=color, alpha=0.3)
        ellipse_bot = mpatches.Ellipse((cx, cy - h/2), w, 0.15, facecolor=color, edgecolor=color, alpha=0.3)
        rect_body = plt.Rectangle((cx - w/2, cy - h/2), w, h, facecolor=color, edgecolor=color, alpha=0.15)
        ax.add_patch(rect_body)
        ax.add_patch(ellipse_top)
        ax.add_patch(ellipse_bot)
        ax.add_patch(plt.Rectangle((cx - w/2, cy - h/2), w, h, facecolor='none', edgecolor=color, linewidth=1.5))
    else:
        # Rounded rectangle
        box = FancyBboxPatch((cx - w/2, cy - h/2), w, h,
                             boxstyle="round,pad=0.03",
                             facecolor=color + '15', edgecolor=color, linewidth=1.5)
        ax.add_patch(box)
    
    ax.text(cx, cy, name, ha='center', va='center', fontsize=7.5, fontweight='bold',
            color=color, fontfamily='sans-serif', linespacing=1.2)
    entity_boxes[i] = (cx, cy, w, h)

# ── Data Flows ───────────────────────────────────────────────────────────────
sys_center = (sys_x + sys_w/2, sys_y + sys_h/2)

for from_ent, to_ent, label, color in data_flows:
    # Get positions
    if from_ent == 'sys':
        fx, fy = sys_center
    else:
        fx, fy = entity_boxes[from_ent][0], entity_boxes[from_ent][1]
    
    if to_ent == 'sys':
        tx, ty = sys_center
    else:
        tx, ty = entity_boxes[to_ent][0], entity_boxes[to_ent][1]
    
    # Offset to avoid overlapping the system box
    dx = tx - fx
    dy = ty - fy
    dist = (dx**2 + dy**2) ** 0.5
    
    if dist < 0.01:
        continue
    
    # Shorten the arrow to not overlap system box or entity box
    shorten = 0.3
    nx, ny = dx/dist, dy/dist
    
    if from_ent == 'sys':
        sx, sy = fx + nx*shorten, fy + ny*shorten
    else:
        sx, sy = fx + nx*0.5, fy + ny*0.28
    
    if to_ent == 'sys':
        ex_, ey_ = tx - nx*shorten, ty - ny*shorten
    else:
        ex_, ey_ = tx - nx*0.5, ty - ny*0.28
    
    # Draw arrow
    ax.annotate('', xy=(ex_, ey_), xytext=(sx, sy),
                arrowprops=dict(arrowstyle='->', color=color, lw=1.0, alpha=0.6,
                               connectionstyle='arc3,rad=0.1'))
    
    # Label (offset to the side)
    mx, my = (sx + ex_)/2, (sy + ey_)/2
    # Perpendicular offset
    perp_x, perp_y = -ny * 0.12, nx * 0.12
    ax.text(mx + perp_x, my + perp_y, label, ha='center', va='center',
            fontsize=4.5, color=color, fontfamily='sans-serif',
            linespacing=1.1, alpha=0.8,
            bbox=dict(boxstyle='round,pad=0.15', facecolor='white', edgecolor='none', alpha=0.8))

# Title
ax.text(2.3, 3.65, 'SYSTEM CONTEXT DIAGRAM — LSPU ScholarHub', ha='center', va='bottom',
        fontsize=13, fontweight='bold', color='#212529', fontfamily='sans-serif')

# Legend
legend_items = [
    ('User Roles', '#0d6efd'),
    ('External Services', '#fd7e14'),
    ('Data Stores', '#20c997'),
]
for i, (label, color) in enumerate(legend_items):
    lx = 0.0 + i * 1.6
    ly = -0.5
    ax.add_patch(plt.Rectangle((lx, ly), 0.08, 0.08, facecolor=color, alpha=0.7))
    ax.text(lx + 0.12, ly + 0.04, label, fontsize=7, va='center', color='#333')

plt.tight_layout(pad=0.3)
diagram_path = os.path.join(os.path.dirname(__file__), 'context_diagram.png')
plt.savefig(diagram_path, dpi=200, bbox_inches='tight', facecolor='white')
plt.close()
print(f"Diagram saved: {diagram_path}")

# ── DOCX ─────────────────────────────────────────────────────────────────────
doc = Document()

for section in doc.sections:
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)

style = doc.styles['Normal']
font = style.font
font.name = 'Times New Roman'
font.size = Pt(12)

# Title
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = title.add_run('SYSTEM CONTEXT DIAGRAM')
run.bold = True
run.font.size = Pt(16)
run.font.name = 'Times New Roman'

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
    run = cap.add_run('Figure A-2. System Context Diagram of LSPU ScholarHub')
    run.bold = True
    run.font.size = Pt(10)
    run.font.name = 'Times New Roman'

doc.add_paragraph()

# ── Description ──────────────────────────────────────────────────────────────
h = doc.add_paragraph()
run = h.add_run('SYSTEM CONTEXT DESCRIPTION')
run.bold = True
run.font.size = Pt(14)
run.font.name = 'Times New Roman'

p = doc.add_paragraph()
p.paragraph_format.first_line_indent = Cm(1.27)
run = p.add_run(
    'The System Context Diagram illustrates the boundaries of the LSPU ScholarHub system '
    'and its interactions with external entities. The system operates as a centralized '
    'web-based platform deployed on Railway (cloud hosting) and connects to several external '
    'services for email delivery, SMS notifications, AI-powered document processing, and '
    'cloud file storage.'
)
run.font.size = Pt(12)
run.font.name = 'Times New Roman'

doc.add_paragraph()

# ── External Entities Table ──────────────────────────────────────────────────
h2 = doc.add_paragraph()
run = h2.add_run('EXTERNAL ENTITIES')
run.bold = True
run.font.size = Pt(14)
run.font.name = 'Times New Roman'

entity_data = [
    ('Student / Scholar', 'User', 
     'Registers an account, applies for scholarships, manages profile and documents, '
     'views application status, receives notifications, and interacts with the AI chatbot.'),
    ('Staff (Scholarship Office)', 'User',
     'Manages scholarship programs, reviews applications, batches approved students, '
     'monitors scholars, sends announcements, and generates reports. Assigned to one or more campuses.'),
    ('Admin (Campus Admin)', 'User',
     'Manages users, campuses, and academic periods. Has full management access within their campus. '
     'Views system reports and audit logs.'),
    ('Super Admin', 'User',
     'System-wide administrator with unrestricted access across all campuses. Manages system settings, '
     'all users, all campuses, and views the complete audit log.'),
    ('Email Service (Resend API)', 'External Service',
     'Sends email notifications to students and staff including application updates, '
     'announcements, and system alerts. Integrated via Resend API.'),
    ('SMS Service', 'External Service',
     'Sends SMS notifications to students for critical alerts such as application status changes.'),
    ('AI / OCR Service (Gemini API)', 'External Service',
     'Processes uploaded documents (COR, ROG) using OCR to extract student details. '
     'Powers the AI chatbot for answering scholarship-related queries.'),
    ('MySQL Database (Railway)', 'Data Store',
     'Stores all system data including user accounts, scholarship programs, applications, '
     'batches, notifications, and audit logs. Hosted on Railway cloud platform.'),
    ('Cloud Storage (Cloudinary)', 'Data Store',
     'Stores uploaded files including student documents (COR, ROG), monitoring forms, '
     'and announcement attachments. Provides secure file retrieval via URL.'),
]

table = doc.add_table(rows=1, cols=3)
table.style = 'Light Grid Accent 1'
table.alignment = WD_TABLE_ALIGNMENT.CENTER

for i, header in enumerate(['Entity', 'Type', 'Description']):
    cell = table.rows[0].cells[i]
    cell.text = ''
    p = cell.paragraphs[0]
    run = p.add_run(header)
    run.bold = True
    run.font.size = Pt(10)
    run.font.name = 'Times New Roman'

for name, etype, desc in entity_data:
    row = table.add_row()
    cells = row.cells
    
    p = cells[0].paragraphs[0]
    run = p.add_run(name)
    run.font.size = Pt(9)
    run.font.name = 'Times New Roman'
    run.bold = True
    
    p = cells[1].paragraphs[0]
    run = p.add_run(etype)
    run.font.size = Pt(9)
    run.font.name = 'Times New Roman'
    
    p = cells[2].paragraphs[0]
    run = p.add_run(desc)
    run.font.size = Pt(9)
    run.font.name = 'Times New Roman'

for row in table.rows:
    row.cells[0].width = Cm(3.5)
    row.cells[1].width = Cm(2.5)
    row.cells[2].width = Cm(10.0)

doc.add_paragraph()

# ── Data Flow Descriptions ──────────────────────────────────────────────────
h3 = doc.add_paragraph()
run = h3.add_run('DATA FLOW DESCRIPTIONS')
run.bold = True
run.font.size = Pt(14)
run.font.name = 'Times New Roman'

flow_data = [
    ('Student → System', 'Application submission, document uploads (COR/ROG), profile updates, '
     'M&E form uploads, chatbot queries.'),
    ('System → Student', 'Application status updates, scholarship information, notifications, '
     'AI chatbot responses, downloadable forms.'),
    ('Staff → System', 'Scholarship program management, application review decisions, '
     'batch creation, announcement composition, report generation.'),
    ('System → Staff', 'Application lists, student directories, monitoring data, '
     'reports and analytics, audit trail.'),
    ('Admin → System', 'User management, campus configuration, academic period management.'),
    ('System → Admin', 'System reports, audit logs, user lists, campus summaries.'),
    ('Super Admin → System', 'System settings, campus selection, global configuration.'),
    ('System → Super Admin', 'System-wide status, complete audit log, all campus data.'),
    ('System → Email Service', 'Notification content, recipient addresses, attachment URLs.'),
    ('Email Service → System', 'Delivery confirmation, bounce status.'),
    ('System → SMS Service', 'SMS message content, recipient phone numbers.'),
    ('System → AI/OCR Service', 'Document images for OCR processing, chatbot queries.'),
    ('AI/OCR → System', 'Extracted text data (student ID, name, GWA, course), AI responses.'),
    ('System → Database', 'CRUD operations on all data entities.'),
    ('System → Cloud Storage', 'File upload (documents, forms, attachments).'),
    ('Cloud Storage → System', 'File URLs for retrieval and display.'),
]

table2 = doc.add_table(rows=1, cols=2)
table2.style = 'Light Grid Accent 1'
table2.alignment = WD_TABLE_ALIGNMENT.CENTER

for i, header in enumerate(['Data Flow', 'Description']):
    cell = table2.rows[0].cells[i]
    cell.text = ''
    p = cell.paragraphs[0]
    run = p.add_run(header)
    run.bold = True
    run.font.size = Pt(10)
    run.font.name = 'Times New Roman'

for flow, desc in flow_data:
    row = table2.add_row()
    cells = row.cells
    
    p = cells[0].paragraphs[0]
    run = p.add_run(flow)
    run.font.size = Pt(9)
    run.font.name = 'Times New Roman'
    run.bold = True
    
    p = cells[1].paragraphs[0]
    run = p.add_run(desc)
    run.font.size = Pt(9)
    run.font.name = 'Times New Roman'

for row in table2.rows:
    row.cells[0].width = Cm(4.0)
    row.cells[1].width = Cm(12.0)

# Save
output_path = os.path.join(os.path.dirname(__file__), 'LSPU_ScholarHub_Context_Diagram.docx')
doc.save(output_path)
print(f"DOCX saved: {output_path}")

"""Generate Proposed Process Flow WITH FLOWCHART SYMBOLS for LSPU ScholarHub.

Matches the reference appendices format:
- 3-column table: [Process Flow symbol] | Responsibility | Description
- Flowchart symbols drawn as PNGs: oval (Start/End), parallelogram (I/O),
  rectangle (Process), diamond (Decision)
- Symbol column forms a vertical chain like a real flowchart
- Includes a symbol legend table
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.path import Path
import matplotlib.patches as mpatches_pkg

from docx import Document
from docx.shared import Pt, Cm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

HERE = os.path.dirname(os.path.abspath(__file__))
SYM_DIR = os.path.join(HERE, 'flowchart_symbols')
os.makedirs(SYM_DIR, exist_ok=True)

# ═════════════════════════════════════════════════════════════════════════════
# 1. Draw flowchart symbols as PNGs
# ═════════════════════════════════════════════════════════════════════════════
EC, FC, LW = '#333333', '#FFFFFF', 2.0


def _save(fig, name):
    path = os.path.join(SYM_DIR, name)
    fig.savefig(path, dpi=300, bbox_inches='tight', pad_inches=0.02,
                facecolor='white', transparent=False)
    plt.close(fig)
    return path


def sym_oval(label='START'):
    """Terminator: rounded oval."""
    fig, ax = plt.subplots(figsize=(2.0, 0.75))
    ax.set_xlim(0, 2); ax.set_ylim(0, 0.75); ax.axis('off'); ax.set_aspect('equal')
    e = mpatches.FancyBboxPatch((0.12, 0.15), 1.76, 0.45,
                                boxstyle='round,pad=0.02,rounding_size=0.22',
                                facecolor=FC, edgecolor=EC, linewidth=LW)
    ax.add_patch(e)
    ax.text(1.0, 0.375, label, ha='center', va='center', fontsize=10,
            fontweight='bold', color=EC)
    return _save(fig, 'oval.png')


def sym_rect(label='PROCESS'):
    """Process: rectangle."""
    fig, ax = plt.subplots(figsize=(2.0, 0.75))
    ax.set_xlim(0, 2); ax.set_ylim(0, 0.75); ax.axis('off'); ax.set_aspect('equal')
    r = mpatches.Rectangle((0.15, 0.12), 1.7, 0.51, facecolor=FC, edgecolor=EC, linewidth=LW)
    ax.add_patch(r)
    ax.text(1.0, 0.375, label, ha='center', va='center', fontsize=9,
            fontweight='bold', color=EC)
    return _save(fig, 'rect.png')


def sym_para(label='INPUT'):
    """Input/Output: parallelogram."""
    fig, ax = plt.subplots(figsize=(2.0, 0.75))
    ax.set_xlim(0, 2); ax.set_ylim(0, 0.75); ax.axis('off'); ax.set_aspect('equal')
    pts = [(0.32, 0.12), (1.85, 0.12), (1.68, 0.63), (0.15, 0.63)]
    p = mpatches.Polygon(pts, closed=True, facecolor=FC, edgecolor=EC, linewidth=LW)
    ax.add_patch(p)
    ax.text(1.0, 0.375, label, ha='center', va='center', fontsize=9,
            fontweight='bold', color=EC)
    return _save(fig, 'para.png')


def sym_diamond(label='DECIDE'):
    """Decision: diamond."""
    fig, ax = plt.subplots(figsize=(2.0, 1.1))
    ax.set_xlim(0, 2); ax.set_ylim(0, 1.1); ax.axis('off'); ax.set_aspect('equal')
    pts = [(1.0, 0.06), (1.9, 0.55), (1.0, 1.04), (0.1, 0.55)]
    d = mpatches.Polygon(pts, closed=True, facecolor=FC, edgecolor=EC, linewidth=LW)
    ax.add_patch(d)
    ax.text(1.0, 0.55, label, ha='center', va='center', fontsize=8,
            fontweight='bold', color=EC)
    return _save(fig, 'diamond.png')


def sym_arrow_down():
    """Small downward connector arrow."""
    fig, ax = plt.subplots(figsize=(0.5, 0.45))
    ax.set_xlim(0, 0.5); ax.set_ylim(0, 0.45); ax.axis('off'); ax.set_aspect('equal')
    ax.annotate('', xy=(0.25, 0.05), xytext=(0.25, 0.42),
                arrowprops=dict(arrowstyle='-|>', color=EC, lw=2.0))
    return _save(fig, 'arrow.png')


SYM = {
    'oval': sym_oval(),
    'rect': sym_rect(),
    'para': sym_para(),
    'diamond': sym_diamond(),
    'arrow': sym_arrow_down(),
}

# ═════════════════════════════════════════════════════════════════════════════
# 2. Process flow data — (symbol, responsibility, description)
#    symbols: 'oval' start/end, 'rect' process, 'para' input/output,
#             'diamond' decision
# ═════════════════════════════════════════════════════════════════════════════
FLOWS = [
    ('Figure 1. Student Registration Process Flow', [
        ('oval',    'Guest / System',      'START — Guest opens the registration page.'),
        ('para',    'Guest',               'Guest uploads Certificate of Registration (COR) and Report of Grades (ROG) in PDF format.'),
        ('diamond', 'System',              'System validates file type and size (PDF only, 5 MB limit). Invalid files are rejected.'),
        ('rect',    'System',              'System extracts student details via OCR (name, student ID, course, year level, units, GWA) and auto-fills the form.'),
        ('para',    'Guest',               'Guest verifies the extracted details and completes birthday, email, and password.'),
        ('diamond', 'System',              'System verifies details match the uploaded files and checks for duplicate accounts.'),
        ('rect',    'System',              'System creates the student account.'),
        ('oval',    'System',              'END — Account created; student is redirected to the login page.'),
    ]),
    ('Figure 2. Scholarship Application Process Flow', [
        ('oval',    'Student / System',    'START — Student logs in and opens the scholarship programs page.'),
        ('rect',    'System',              'System displays open programs for the student\u2019s campus and current academic period.'),
        ('rect',    'Student',             'Student selects a program and opens the application form.'),
        ('para',    'System',              'System pre-fills student details (birthday, course, year level, GWA, units) from the profile.'),
        ('diamond', 'System',              'System checks eligibility: no duplicate application and one public program rule.'),
        ('rect',    'System',              'System saves the application and queues it for review.'),
        ('oval',    'System',              'END — Application submitted; confirmation notification sent to the student.'),
    ]),
    ('Figure 3. Application Review and Approval Process Flow', [
        ('oval',    'Staff / System',      'START — Staff opens the Review Applications module.'),
        ('rect',    'System',              'System displays pending applications filtered by campus and academic period.'),
        ('rect',    'Staff',               'Staff examines the student details and documents.'),
        ('diamond', 'Staff',               'Staff decides: approve or reject the application.'),
        ('rect',    'System',              'System updates the application status and increments the program\u2019s approved count.'),
        ('rect',    'System',              'System notifies the student via in-app notification and email.'),
        ('oval',    'System',              'END — Application approved or rejected; student informed.'),
    ]),
    ('Figure 4. Batching of Approved Scholars Process Flow', [
        ('oval',    'Staff / System',      'START — Staff opens the Batches module.'),
        ('rect',    'System',              'System displays existing batches and approved students awaiting assignment for the period.'),
        ('rect',    'Staff',               'Staff creates a batch and selects the scholarship program.'),
        ('rect',    'System',              'System groups approved students by program and assigns them to the batch.'),
        ('rect',    'System',              'System links the batch to the campus and academic period, then notifies the batched scholars.'),
        ('oval',    'System',              'END — Scholars organized into batches ready for fund disbursement.'),
    ]),
    ('Figure 5. Scholar Monitoring and Evaluation Process Flow', [
        ('oval',    'Student / System',    'START — Student opens the scholarship page.'),
        ('para',    'Student',             'Student downloads the Monitoring and Evaluation form.'),
        ('para',    'Student',             'Student uploads a photo or PDF of the accomplished form.'),
        ('rect',    'System',              'System validates the file and stores it under the student\u2019s scholarship record.'),
        ('rect',    'Staff',               'Staff reviews scholar compliance, GWA, and submitted M&E forms.'),
        ('diamond', 'Staff',               'Staff evaluates: compliant or at risk?'),
        ('oval',    'Staff / System',      'END — Scholar compliance monitored and recorded for the period.'),
    ]),
    ('Figure 6. Announcement Management Process Flow', [
        ('oval',    'Staff / System',      'START — Staff opens the Announcements page.'),
        ('rect',    'Staff',               'Staff clicks Send Announcement and selects recipients (students, by scholarship, or by batch).'),
        ('para',    'Staff',               'Staff writes the title and message and optionally attaches files.'),
        ('diamond', 'System',              'System checks: is the viewed period the active period? If not, a confirmation warning appears.'),
        ('rect',    'System',              'System delivers the announcement via in-app notification and email (and SMS when enabled), tagged with the academic period.'),
        ('oval',    'System',              'END — Announcement delivered; recipients notified.'),
    ]),
    ('Figure 7. Student Document Update Process Flow', [
        ('oval',    'Student / System',    'START — Student opens the Documents page.'),
        ('rect',    'System',              'System displays the current COR and ROG on file.'),
        ('para',    'Student',             'Student uploads a replacement document (PDF only).'),
        ('diamond', 'System',              'System validates the file and re-extracts the student details via OCR. Details must match the account.'),
        ('rect',    'System',              'System replaces the stored file.'),
        ('oval',    'System',              'END — Student records updated with the latest documents.'),
    ]),
    ('Figure 8. Academic Period and Campus Management Process Flow', [
        ('oval',    'Super Admin / System', 'START — Super Admin opens the Periods page.'),
        ('rect',    'System',               'System displays all academic periods and campuses.'),
        ('rect',    'Super Admin',          'Super Admin creates, edits, or deletes an academic period and sets the current active period.'),
        ('rect',    'System',               'System applies the period as the default data context for all users.'),
        ('rect',    'Admin / Super Admin',  'Admin switches the campus selector to manage campus-scoped data.'),
        ('rect',    'System',               'System filters dashboards, applications, reports, and announcements by campus and period.'),
        ('oval',    'System',               'END — System data scoped correctly per campus and academic period.'),
    ]),
    ('Figure 9. User and Role Management Process Flow', [
        ('oval',    'Admin / System',      'START — Admin opens the Manage Users page.'),
        ('rect',    'System',              'System displays user accounts filtered by campus (all campuses for Super Admin).'),
        ('rect',    'Admin',               'Admin creates a user, changes a role, or assigns a staff member to one or more campuses.'),
        ('rect',    'System',              'System validates the changes, updates the account, and records the action in the audit log.'),
        ('oval',    'System',              'END — User accounts and roles updated with a full audit trail.'),
    ]),
    ('Figure 10. Scholarship Program Management Process Flow', [
        ('oval',    'Staff / System',      'START — Staff opens the Manage Scholarships page.'),
        ('rect',    'System',              'System displays scholarship programs with period badges (Permanent or period-specific).'),
        ('rect',    'Staff',               'Staff creates a new program or edits an existing one.'),
        ('diamond', 'System',              'System checks: does the program already have applicants? Editing is blocked if yes.'),
        ('rect',    'System',              'System saves and publishes the program to students of the assigned campus and period.'),
        ('oval',    'System',              'END — Scholarship program created or updated and visible to eligible students.'),
    ]),
]

# ═════════════════════════════════════════════════════════════════════════════
# 3. Build DOCX
# ═════════════════════════════════════════════════════════════════════════════
doc = Document()
for section in doc.sections:
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)

style = doc.styles['Normal']
style.font.name = 'Times New Roman'
style.font.size = Pt(12)


def add_heading(text, size=16, center=True):
    p = doc.add_paragraph()
    if center:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(size)
    run.font.name = 'Times New Roman'
    return p


def add_caption(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(11)
    run.font.name = 'Times New Roman'
    return p


def add_flow_table(steps):
    """3-column table: [symbol img] | Responsibility | Description."""
    table = doc.add_table(rows=0, cols=3)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    header = table.add_row()
    for i, text in enumerate(['Process Flow', 'Responsibility', 'Description']):
        cell = header.cells[i]
        cell.text = ''
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(11)
        run.font.name = 'Times New Roman'

    n = len(steps)
    for idx, (sym, resp, desc) in enumerate(steps):
        row = table.add_row()
        c_sym, c_resp, c_desc = row.cells

        # ── Symbol column: image + connector arrow below (except last) ──
        p = c_sym.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        width = Inches(1.05) if sym != 'diamond' else Inches(1.15)
        run.add_picture(SYM[sym], width=width)

        if idx < n - 1:
            p2 = c_sym.add_paragraph()
            p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p2.paragraph_format.space_before = Pt(0)
            p2.paragraph_format.space_after = Pt(0)
            r2 = p2.add_run()
            r2.add_picture(SYM['arrow'], height=Inches(0.28))

        # ── Responsibility ──
        p = c_resp.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(resp)
        run.font.size = Pt(11)
        run.font.name = 'Times New Roman'

        # ── Description ──
        p = c_desc.paragraphs[0]
        run = p.add_run(desc)
        run.font.size = Pt(11)
        run.font.name = 'Times New Roman'

        c_sym.width = Cm(3.6)
        c_resp.width = Cm(3.6)
        c_desc.width = Cm(8.8)

    return table


# ── Title ──
add_heading('PROPOSED PROCESS FLOW')
doc.add_paragraph()

# ── All flows ──
for caption, steps in FLOWS:
    add_caption(caption)
    add_flow_table(steps)
    doc.add_paragraph()

# ── Symbol legend ──
add_caption('Flowchart Symbols Used')
legend_rows = [
    ('oval',    'Terminator (Start / End)', 'Marks the beginning and end of the process.'),
    ('rect',    'Process', 'A processing step performed by a user or the system.'),
    ('para',    'Input / Output', 'Data entered into or produced by the system (uploads, forms, notifications).'),
    ('diamond', 'Decision', 'A point where the flow branches based on a condition or validation.'),
]
lt = doc.add_table(rows=1, cols=3)
lt.style = 'Table Grid'
lt.alignment = WD_TABLE_ALIGNMENT.CENTER
for i, text in enumerate(['Symbol', 'Name', 'Meaning']):
    cell = lt.rows[0].cells[i]
    cell.text = ''
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(11)
    run.font.name = 'Times New Roman'

for sym, name, meaning in legend_rows:
    row = lt.add_row()
    p = row.cells[0].paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run()
    w = Inches(1.0) if sym != 'diamond' else Inches(1.1)
    r.add_picture(SYM[sym], width=w)
    p2 = row.cells[1].paragraphs[0]
    run = p2.add_run(name)
    run.font.size = Pt(11)
    run.font.name = 'Times New Roman'
    p3 = row.cells[2].paragraphs[0]
    run = p3.add_run(meaning)
    run.font.size = Pt(11)
    run.font.name = 'Times New Roman'
    row.cells[0].width = Cm(3.6)
    row.cells[1].width = Cm(4.0)
    row.cells[2].width = Cm(8.4)

output_path = os.path.join(HERE, 'LSPU_ScholarHub_Process_Flow_Flowchart.docx')
doc.save(output_path)
print(f'DOCX saved: {output_path}')

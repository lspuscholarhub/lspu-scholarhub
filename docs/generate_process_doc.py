"""Generate LSPU ScholarHub process documentation (DOCX with flowcharts).

Outputs:
  <project root>/LSPU-ScholarHub-Process-Documentation.docx
  docs/flowcharts/*.png  (flowchart images, reusable in slides/papers)

Run:  python docs/generate_process_doc.py
"""
import os
import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon, FancyArrowPatch

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(BASE, 'docs', 'flowcharts')
os.makedirs(IMG_DIR, exist_ok=True)
DOCX_PATH = os.path.join(BASE, 'LSPU-ScholarHub-Process-Documentation.docx')

NAVY_RGB = RGBColor(0x1F, 0x4E, 0x79)
GRAY_RGB = RGBColor(0x59, 0x59, 0x59)

# --------------------------------------------------------------------------
# Flowchart drawing helpers
# --------------------------------------------------------------------------
STYLE = {
    'start':    ('#2C3E50', '#2C3E50'),
    'process':  ('#EAF2F8', '#1F618D'),
    'decision': ('#FEF9E7', '#B7950B'),
    'bad':      ('#FDEDEC', '#C0392B'),
    'good':     ('#E9F7EF', '#1E8449'),
}
ARROW = '#5D6D7E'


def canvas(w, h, title):
    fig, ax = plt.subplots(figsize=(8.6 * w / 100.0, 8.6 * h / 100.0))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis('off')
    ax.text(w / 2.0, h - 2.5, title, ha='center', va='center',
            fontsize=13, fontweight='bold', color='#1F4E79')
    return fig, ax


def box(ax, cx, cy, w, h, text, kind='process', fs=9):
    fill, edge = STYLE[kind]
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                                boxstyle='round,pad=0.6,rounding_size=2',
                                linewidth=1.6, edgecolor=edge, facecolor=fill))
    ax.text(cx, cy, text, ha='center', va='center', fontsize=fs, color='#1B2631')


def oval(ax, cx, cy, w, h, text, fs=9):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                                boxstyle='round,pad=0.6,rounding_size=100',
                                linewidth=1.6, edgecolor='#1B2631',
                                facecolor='#2C3E50'))
    ax.text(cx, cy, text, ha='center', va='center', fontsize=fs,
            color='white', fontweight='bold')


def diamond(ax, cx, cy, w, h, text, fs=9):
    fill, edge = STYLE['decision']
    pts = [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)]
    ax.add_patch(Polygon(pts, closed=True, facecolor=fill, edgecolor=edge, linewidth=1.6))
    ax.text(cx, cy, text, ha='center', va='center', fontsize=fs, color='#1B2631')


def _label(ax, text, x, y, rotation=0):
    color = {'yes': '#1E8449', 'no': '#C0392B'}.get(text.lower(), '#34495E')
    ax.text(x, y, text, fontsize=8.5, style='italic', color=color,
            ha='center', va='center', rotation=rotation,
            bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none'))


def arrow(ax, x1, y1, x2, y2, label=None, lx=None, ly=None):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle='-|>',
                                 mutation_scale=14, color=ARROW, lw=1.5,
                                 shrinkA=1, shrinkB=1))
    if label:
        _label(ax, label, lx if lx is not None else (x1 + x2) / 2,
               ly if ly is not None else (y1 + y2) / 2)


def elbow(ax, pts, label=None, li=0, lx=None, ly=None, dashed=False, rot=0):
    ls = '--' if dashed else '-'
    for i in range(len(pts) - 2):
        ax.plot([pts[i][0], pts[i + 1][0]], [pts[i][1], pts[i + 1][1]],
                color=ARROW, lw=1.5, linestyle=ls, solid_capstyle='round')
    ax.add_patch(FancyArrowPatch(pts[-2], pts[-1], arrowstyle='-|>',
                                 mutation_scale=14, color=ARROW, lw=1.5,
                                 linestyle=ls, shrinkA=1, shrinkB=1))
    if label:
        (x1, y1), (x2, y2) = pts[li], pts[li + 1]
        _label(ax, label, lx if lx is not None else (x1 + x2) / 2,
               ly if ly is not None else (y1 + y2) / 2, rotation=rot)


def save(fig, name):
    path = os.path.join(IMG_DIR, name)
    fig.savefig(path, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return path


# --------------------------------------------------------------------------
# Figure 1 — End-to-end system workflow
# --------------------------------------------------------------------------
def fig1():
    fig, ax = canvas(110, 140, 'LSPU ScholarHub — End-to-End System Workflow')
    cx, bw = 38, 44

    oval(ax, cx, 130, 40, 7, 'Student visits ScholarHub')
    box(ax, cx, 118.5, bw, 9, 'Register account\nand verify via OTP')
    box(ax, cx, 106.5, bw, 9, 'Upload COR and Copy of Grades\n(GWA is read automatically)')
    box(ax, cx, 95, bw, 8, 'Browse open scholarship programs')
    box(ax, cx, 84, bw, 9, 'Submit application\n(auto-filled profile + custom form)')
    box(ax, cx, 73, bw, 7, 'Application status: PENDING')
    box(ax, cx, 62.5, bw, 9, 'Staff / Admin review\ndocuments, GWA, custom answers')
    diamond(ax, cx, 44, 26, 14, 'Approved?')
    box(ax, 88, 44, 36, 10, 'Status: REJECTED\nstudent is notified', kind='bad')
    box(ax, cx, 28.5, bw, 10, "Auto-batched under the program's batch\n(current academic period)")
    oval(ax, cx, 14, 46, 8, 'Scholar monitored every term\n(see Scholar Monitoring)')

    arrow(ax, cx, 126.5, cx, 123)
    arrow(ax, cx, 114, cx, 111)
    arrow(ax, cx, 102, cx, 99)
    arrow(ax, cx, 91, cx, 88.5)
    arrow(ax, cx, 79.5, cx, 76.5)
    arrow(ax, cx, 69.5, cx, 67)
    arrow(ax, cx, 58, cx, 51)
    arrow(ax, 51, 44, 70, 44, label='no', lx=57, ly=46.5)
    elbow(ax, [(88, 49), (88, 95), (60, 95)], label='may reapply', li=0, lx=88, ly=72)
    arrow(ax, cx, 37, cx, 33.5, label='yes', lx=41, ly=35.5)
    arrow(ax, cx, 23.5, cx, 18)
    return save(fig, 'fig1_end_to_end.png')


# --------------------------------------------------------------------------
# Figure 2 — Student application process
# --------------------------------------------------------------------------
def fig2():
    fig, ax = canvas(110, 112, 'Student Application Process')
    cx = 38

    oval(ax, cx, 101, 34, 7, 'Student is logged in')
    box(ax, cx, 91, 40, 8, 'Go to Scholarships')
    diamond(ax, cx, 76.5, 30, 14, 'Already an active\nscholar?')
    box(ax, 88, 76.5, 38, 10, 'Blocked — one scholarship\nat a time', kind='bad')
    diamond(ax, cx, 55.5, 36, 18, 'Program open? (active status,\nbefore deadline, slots left)')
    box(ax, 88, 55.5, 36, 10, 'Applications closed —\nchoose another program', kind='bad')
    box(ax, cx, 37.5, 44, 10, 'Open the application form —\nprofile details auto-filled')
    box(ax, cx, 25.5, 40, 9, "Answer the program's\ncustom questions")
    box(ax, cx, 15.5, 40, 7, 'Review and submit')
    box(ax, cx, 6, 44, 8, 'Status: PENDING — confirmation sent\nvia email / SMS / in-app')
    box(ax, 88, 25.5, 38, 10, 'Track in My Applications —\nedit or withdraw while pending')

    arrow(ax, cx, 97.5, cx, 95)
    arrow(ax, cx, 87, cx, 83.5)
    arrow(ax, 53, 76.5, 69, 76.5, label='yes', lx=57, ly=79)
    arrow(ax, cx, 69.5, cx, 64.5)
    arrow(ax, 56, 55.5, 70, 55.5, label='no', lx=60, ly=58)
    arrow(ax, cx, 46.5, cx, 42.5, label='yes', lx=41, ly=44.5)
    arrow(ax, cx, 32.5, cx, 30)
    arrow(ax, cx, 21, cx, 19)
    arrow(ax, cx, 12, cx, 10)
    elbow(ax, [(60, 6), (88, 6), (88, 20.5)])
    return save(fig, 'fig2_student_application.png')


# --------------------------------------------------------------------------
# Figure 3 — Staff review, approval and auto-batching
# --------------------------------------------------------------------------
def fig3():
    fig, ax = canvas(110, 104, 'Staff Review, Approval and Auto-Batching')
    cx = 38

    oval(ax, cx, 94, 42, 7, 'New application is submitted')
    box(ax, cx, 83.5, 44, 10, 'Staff opens Review Applications\n(filters: program, status, GWA)')
    box(ax, cx, 70.5, 44, 10, 'Open applicant: documents, GWA,\nCTC status, custom answers')
    diamond(ax, cx, 53.5, 24, 13, 'Qualifies?')
    box(ax, 88, 53.5, 36, 10, 'Reject with reason —\nstudent is notified', kind='bad')
    box(ax, cx, 35, 44, 10, 'Approve — single applicant\nor batch-select')
    box(ax, cx, 21.5, 46, 10, "System finds or creates the batch named\nafter the program (current academic period)")
    box(ax, cx, 8, 44, 8, 'Scholar added to batch;\napproval notification sent')
    box(ax, 88, 21.5, 38, 10, 'View, manage, and export\nbatches and scholars')

    arrow(ax, cx, 90.5, cx, 88.5)
    arrow(ax, cx, 78.5, cx, 75.5)
    arrow(ax, cx, 65.5, cx, 60)
    arrow(ax, 50, 53.5, 70, 53.5, label='no', lx=54, ly=56)
    arrow(ax, cx, 47, cx, 40, label='yes', lx=41, ly=44)
    arrow(ax, cx, 30, cx, 26.5)
    arrow(ax, cx, 16.5, cx, 12)
    elbow(ax, [(61, 21.5), (69, 21.5)])
    return save(fig, 'fig3_staff_review_batching.png')


# --------------------------------------------------------------------------
# Figure 4 — Scholar monitoring cycle
# --------------------------------------------------------------------------
def fig4():
    fig, ax = canvas(110, 106, 'Scholar Monitoring Cycle (Every Term)')
    cx = 40

    oval(ax, cx, 96, 30, 7, 'New term begins')
    box(ax, cx, 86.5, 34, 7, 'Staff opens Monitoring')
    box(ax, cx, 76.5, 36, 7, "Update each scholar's GWA")
    diamond(ax, cx, 59, 34, 16, 'GWA meets the\nprogram requirement?')
    box(ax, 20, 41.5, 30, 10, 'Good Standing —\nscholar retained', kind='good')
    oval(ax, 20, 28.5, 34, 7, 'Retained until program\nends / graduation')
    box(ax, 80, 46.5, 40, 10, 'At Risk — student is notified\n(must improve next term)', kind='decision')
    box(ax, 80, 32.5, 40, 10, 'Still low: Probation →\nTermination warning', kind='bad')
    oval(ax, 80, 19.5, 42, 8, 'Scholarship terminated —\nrecords kept')

    arrow(ax, cx, 92.5, cx, 90)
    arrow(ax, cx, 83, cx, 80)
    arrow(ax, cx, 73, cx, 67)
    elbow(ax, [(23, 59), (20, 59), (20, 46.5)], label='yes', lx=22, ly=62)
    arrow(ax, 20, 36.5, 20, 32.5)
    elbow(ax, [(3, 28.5), (3, 86.5), (23, 86.5)], label='next term', li=0,
          lx=2.0, ly=57, dashed=True, rot=90)
    elbow(ax, [(57, 59), (80, 59), (80, 51.5)], label='no', li=0, lx=62, ly=62)
    arrow(ax, 80, 41.5, 80, 37.5)
    arrow(ax, 80, 27.5, 80, 23.5)
    return save(fig, 'fig4_monitoring.png')


# --------------------------------------------------------------------------
# DOCX helpers
# --------------------------------------------------------------------------
def shade(cell, color):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:fill'), color)
    tc_pr.append(shd)


def add_table(doc, headers, rows):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = 'Table Grid'
    hdr = t.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = ''
        run = hdr[i].paragraphs[0].add_run(h)
        run.bold = True
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        run.font.size = Pt(10.5)
        shade(hdr[i], '1F4E79')
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ''
            run = cells[i].paragraphs[0].add_run(val)
            run.font.size = Pt(10)
    return t


def add_pic(doc, path, width_in, caption):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(path, width=Inches(width_in))
    c = doc.add_paragraph()
    c.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = c.add_run(caption)
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = GRAY_RGB


def step(doc, num, title, body):
    p = doc.add_paragraph()
    r = p.add_run(f'{num}. {title} — ')
    r.bold = True
    r.font.color.rgb = NAVY_RGB
    p.add_run(body)


def bullets(doc, items):
    for it in items:
        doc.add_paragraph(it, style='List Bullet')


# --------------------------------------------------------------------------
# Build the document
# --------------------------------------------------------------------------
def build_doc(figs):
    doc = Document()
    doc.core_properties.title = 'LSPU ScholarHub — Process Documentation'
    doc.core_properties.author = 'LSPU ScholarHub'

    for name in ('Title', 'Heading 1', 'Heading 2'):
        doc.styles[name].font.color.rgb = NAVY_RGB
    doc.styles['Normal'].font.name = 'Calibri'

    # Footer
    footer_p = doc.sections[0].footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fr = footer_p.add_run('LSPU ScholarHub — AI-Enabled Scholarship Management and Monitoring System')
    fr.font.size = Pt(8.5)
    fr.font.color.rgb = GRAY_RGB

    # ---- Cover ----
    for _ in range(6):
        doc.add_paragraph()
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tr = t.add_run('LSPU ScholarHub')
    tr.font.size = Pt(34)
    tr.bold = True
    tr.font.color.rgb = NAVY_RGB

    s = doc.add_paragraph()
    s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sr = s.add_run('AI-Enabled Scholarship Management and Monitoring System')
    sr.font.size = Pt(14)
    sr.font.color.rgb = GRAY_RGB

    s2 = doc.add_paragraph()
    s2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    s2r = s2.add_run('Process Documentation — Workflows and Flowcharts')
    s2r.font.size = Pt(13)
    s2r.bold = True

    doc.add_paragraph()
    s3 = doc.add_paragraph()
    s3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    s3r = s3.add_run('Laguna State Polytechnic University — Scholarship Office\n'
                     + datetime.date.today().strftime('%B %d, %Y'))
    s3r.font.size = Pt(11)
    s3r.font.color.rgb = GRAY_RGB
    doc.add_page_break()

    # ---- Contents ----
    doc.add_heading('Contents', level=1)
    bullets(doc, [
        '1. System Overview',
        '2. User Roles',
        '3. End-to-End Workflow (Figure 1)',
        '4. Student Journey (Figure 2)',
        '5. Staff Review, Approval and Auto-Batching (Figure 3)',
        '6. Scholar Monitoring (Figure 4)',
        '7. Admin Functions',
        '8. Application Status Lifecycle',
        '9. Key Business Rules',
        '10. Notifications and Support',
    ])
    doc.add_page_break()

    # ---- 1. Overview ----
    doc.add_heading('1. System Overview', level=1)
    doc.add_paragraph(
        'LSPU ScholarHub digitizes the complete scholarship lifecycle of the Laguna State '
        'Polytechnic University Scholarship Office. It replaces manual form distribution '
        '(e.g., Google Forms and paper submissions) with an online system that:')
    bullets(doc, [
        'publishes scholarship programs, each with its own custom application form;',
        'collects student applications with profile data filled in automatically;',
        'lets staff and admins review, approve, or reject applicants;',
        'automatically organizes approved scholars into batches named after their scholarship program for the current academic period;',
        'monitors the General Weighted Average (GWA) of every scholar each term and flags those who need attention;',
        'notifies students through email, SMS, and in-app notifications at every important step.',
    ])
    doc.add_paragraph(
        'An integrated AI assistant answers common scholarship questions, and documents '
        '(Certificate of Registration and Copy of Grades) are stored securely online. '
        'The GWA is read automatically from the uploaded grades, removing manual encoding.')

    # ---- 2. Roles ----
    doc.add_heading('2. User Roles', level=1)
    add_table(doc, ['Role', 'Main Responsibilities'], [
        ['Guest', 'Views the landing page, browses open scholarship programs, reads how the '
                  'system works, contacts the office, and registers as a student.'],
        ['Student', 'Registers (verified by one-time PIN), uploads COR and Copy of Grades, '
                    'applies to scholarship programs, tracks application status, edits or '
                    'withdraws pending applications, receives notifications, and chats with '
                    'the AI assistant.'],
        ['Staff', 'Creates scholarship programs with custom application forms, reviews '
                  'applications, approves or rejects applicants, manages batches, monitors '
                  'scholar GWA, sends announcements, and generates reports and exports.'],
        ['Admin', 'Has all staff capabilities plus user and staff account management, system '
                  'settings, academic periods, and full audit logs.'],
    ])
    doc.add_paragraph()

    # ---- 3. End-to-end ----
    doc.add_heading('3. End-to-End Workflow', level=1)
    doc.add_paragraph(
        'The diagram below shows the complete journey of a student from first visit to '
        'becoming a monitored scholar.')
    add_pic(doc, figs[0], 6.1, 'Figure 1. End-to-end system workflow.')
    step(doc, 1, 'Account creation', 'the student registers with a school email and confirms identity using a one-time PIN (OTP).')
    step(doc, 2, 'Document submission', 'the student uploads the Certificate of Registration and Copy of Grades; the system reads the GWA automatically.')
    step(doc, 3, 'Application', 'the student browses open programs and applies — profile details are pre-filled and each program asks its own custom questions.')
    step(doc, 4, 'Review', 'staff or admin evaluate the application (documents, GWA, and custom answers).')
    step(doc, 5, 'Decision', 'the applicant is approved or rejected; the student is notified through email, SMS, or in-app alert.')
    step(doc, 6, 'Batching', 'approved scholars are automatically placed in the batch named after their scholarship program under the current academic period.')
    step(doc, 7, 'Monitoring', 'every term, staff verify each scholar\u2019s GWA; scholars are classified as Good Standing, At Risk, Probation, or Termination Warning.')
    step(doc, 8, 'Reporting', 'staff and admin generate reports and export batch lists to Excel.')
    doc.add_page_break()

    # ---- 4. Student ----
    doc.add_heading('4. Student Journey', level=1)
    doc.add_paragraph(
        'Guests can browse open scholarship programs without an account, but applying '
        'requires registration. The figure below shows the application process.')
    add_pic(doc, figs[1], 6.1, 'Figure 2. Student application process.')
    step(doc, 1, 'Register', 'sign up with a school email and verify through the OTP sent to the account.')
    step(doc, 2, 'Upload documents', 'in My Documents, upload the COR and the latest Copy of Grades (PDF or image). Replacing a file updates it everywhere in the system.')
    step(doc, 3, 'Browse', 'open programs show their award, deadline (if any), and remaining slots.')
    step(doc, 4, 'Apply', 'the application form is pre-filled with profile details (name, course, year level, GWA, birthday, etc.); the student answers only the program\u2019s custom questions.')
    step(doc, 5, 'Submit and track', 'the application becomes PENDING; the student can edit or withdraw it while it is pending, and receives notifications on every status change.')
    doc.add_paragraph()
    doc.add_paragraph(
        'Restrictions enforced by the system: a student who is already an approved scholar '
        'cannot apply to another program (one scholarship at a time), and applications are '
        'accepted only while the program is active, before its deadline (if set), and while '
        'slots remain.')

    # ---- 5. Staff ----
    doc.add_heading('5. Staff Review, Approval and Auto-Batching', level=1)
    doc.add_paragraph(
        'Previously, staff manually grouped scholars into batches — slow and error-prone. '
        'In the system, approval itself performs the batching: each approved scholar is '
        'automatically placed in the batch named after the scholarship program they applied to.')
    add_pic(doc, figs[2], 6.1, 'Figure 3. Staff review, approval and auto-batching.')
    step(doc, 1, 'Review queue', 'staff open Review Applications and filter by program, status, or GWA.')
    step(doc, 2, 'Evaluate', 'each applicant record shows the uploaded documents, GWA, CTC status, and answers to the program\u2019s custom questions.')
    step(doc, 3, 'Decide', 'staff approve a single applicant or batch-select several at once; rejections include a reason sent to the student.')
    step(doc, 4, 'Automatic batching', 'the system finds or creates the batch for that program under the current academic period and assigns the scholar to it.')
    step(doc, 5, 'Manage batches', 'staff view every batch, see each scholar\u2019s details, and export the list to Excel.')
    doc.add_page_break()

    # ---- 6. Monitoring ----
    doc.add_heading('6. Scholar Monitoring', level=1)
    doc.add_paragraph(
        'Scholarship retention depends on academic performance. Every term, staff check '
        'each scholar\u2019s GWA in the Monitoring page. The system classifies scholars as follows:')
    add_table(doc, ['Status', 'Meaning'], [
        ['Good Standing', 'GWA meets the program requirement; the scholar is retained.'],
        ['At Risk', 'GWA falls below the requirement; the student is notified and must improve next term.'],
        ['Probation', 'The GWA remains low after an At Risk term; final warning period.'],
        ['Termination Warning', 'Requirements remain unmet; the scholarship is ended and the record is kept.'],
    ])
    doc.add_paragraph()
    doc.add_paragraph(
        'Students are alerted through SMS, email, and in-app notifications, and renewal '
        'reminders are sent when documents or grades need updating.')
    add_pic(doc, figs[3], 6.0, 'Figure 4. Scholar monitoring cycle per term.')

    # ---- 7. Admin ----
    doc.add_heading('7. Admin Functions', level=1)
    bullets(doc, [
        'User management — enable/disable accounts, verify students, reset access.',
        'Staff management — create and remove staff accounts.',
        'Scholarship management — full control over programs, custom forms, and visibility.',
        'Applications oversight — the same review tools as staff.',
        'Batches — view any batch and its scholars, with exports.',
        'Students directory — searchable list with GWA sorting and at-risk filters.',
        'Monitoring and announcements — system-wide messaging.',
        'Reports — charts, approval rates, and per-program statistics.',
        'Audit logs — a trail of every significant action for accountability.',
        'System settings — academic periods and system configuration.',
    ])

    # ---- 8. Status lifecycle ----
    doc.add_heading('8. Application Status Lifecycle', level=1)
    add_table(doc, ['Status', 'Set by', 'Meaning'], [
        ['Pending', 'System', 'Application submitted; waiting for the office to review.'],
        ['Under Review', 'Staff / Admin', 'The application is being evaluated.'],
        ['Approved', 'Staff / Admin', 'Applicant qualified; automatically placed in the program\u2019s batch and notified.'],
        ['Rejected', 'Staff / Admin', 'Did not meet requirements; the reason is sent to the student, who may apply to other open programs.'],
        ['Withdrawn', 'Student', 'The student cancelled a pending application.'],
    ])
    doc.add_paragraph()

    # ---- 9. Rules ----
    doc.add_heading('9. Key Business Rules', level=1)
    step(doc, 1, 'One scholarship at a time', 'a student holding an approved scholarship cannot apply to another program until it ends or is withdrawn.')
    step(doc, 2, 'Open programs only', 'applications are accepted while the program is active, before its deadline (if set), and while slots remain.')
    step(doc, 3, 'Required documents', 'Certificate of Registration and the latest Copy of Grades, as PDF or image; students may replace their files anytime from My Documents.')
    step(doc, 4, 'Automatic GWA', 'the GWA is read from the uploaded grades and drives both eligibility and monitoring.')
    step(doc, 5, 'Auto-batching', 'approval automatically assigns the scholar to the batch named after the program for the current academic period; the period is created automatically if missing.')
    step(doc, 6, 'Custom application forms', 'each scholarship program defines its own additional questions; common profile fields are filled in automatically.')
    step(doc, 7, 'Triple-channel notifications', 'every important event reaches the student through email, SMS (when configured), and in-app alerts.')
    step(doc, 8, 'Audit trail', 'significant actions across all roles are recorded for accountability.')

    # ---- 10. Support ----
    doc.add_heading('10. Notifications and Support', level=1)
    doc.add_paragraph(
        'Students are kept informed at every step — application received, decision released, '
        'batch assignment, GWA alerts, and renewal reminders. For questions and concerns, '
        'the Scholarship Office can be reached through the Contact page or directly:')
    bullets(doc, [
        'Email: lspu.scholarhub@gmail.com',
        'Phone: 0968-365-2615 (Mon\u2013Fri, 8:00 AM\u20135:00 PM)',
        'Office: Student Affairs Building, 2nd Floor, LSPU Sta. Cruz',
        'AI Assistant: available inside the system for common questions.',
    ])

    doc.save(DOCX_PATH)
    return DOCX_PATH


if __name__ == '__main__':
    figures = [fig1(), fig2(), fig3(), fig4()]
    out = build_doc(figures)
    size_kb = os.path.getsize(out) / 1024.0
    print(f'Generated: {out} ({size_kb:.0f} KB)')
    for f in figures:
        print(f'  figure: {f}')

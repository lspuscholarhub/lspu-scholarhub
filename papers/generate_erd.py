"""
Generate the ERD diagram image (Chen-style, clean and simple) for the
thesis and embed it in a DOCX document.

Outputs:
  papers/erd_diagram.png                       — the diagram itself
  papers/LSPU_ScholarHub_ERD.docx              — DOCX with the figure

Run:  python papers/generate_erd.py
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT_PNG = Path(__file__).parent / 'erd_diagram.png'
OUT_DOCX = Path(__file__).parent / 'LSPU_ScholarHub_ERD.docx'

# ── Entities: (name, [key attributes]) ────────────────────────────────────────
ENTITIES = {
    'USERS':        ['id (PK)', 'username', 'email', 'user_type', 'campus_id (FK)'],
    'CAMPUS':       ['id (PK)', 'name', 'short_name'],
    'SCHOLARSHIP':  ['id (PK)', 'title', 'funding_type', 'campus_id (FK)',
                     'award_amount', 'deadline', 'status'],
    'APPLICATION':  ['id (PK)', 'scholarship_id (FK)', 'applicant_id (FK)',
                     'status', 'submitted_at'],
    'BATCH':        ['id (PK)', 'scholarship_id (FK)', 'campus_id (FK)',
                     'batch_name', 'status'],
    'DOCUMENT':     ['id (PK)', 'user_id (FK)', 'doc_type', 'file_url'],
    'NOTIFICATION': ['id (PK)', 'recipient_id (FK)', 'title', 'channel'],
    'MONITORING':   ['id (PK)', 'user_id (FK)', 'application_id (FK)',
                     'period_id (FK)', 'file_url'],
    'PERIOD':       ['id (PK)', 'academic_year', 'semester', 'me_deadline'],
    'CHAT_HISTORY': ['id (PK)', 'user_id (FK)', 'role', 'content'],
    'AUDIT_LOG':    ['id (PK)', 'user_id (FK)', 'action', 'created_at'],
}

# ── Relationships: (entityA, entityB, label, cardinality) ────────────────────
RELATIONS = [
    ('CAMPUS', 'USERS',        'has',        '1:N'),
    ('CAMPUS', 'SCHOLARSHIP',  'hosts',      '1:N'),
    ('CAMPUS', 'BATCH',        'groups',     '1:N'),
    ('USERS',  'APPLICATION',  'submits',    '1:N'),
    ('SCHOLARSHIP', 'APPLICATION', 'receives', '1:N'),
    ('SCHOLARSHIP', 'BATCH',   'awards',     '1:N'),
    ('USERS',  'DOCUMENT',     'uploads',    '1:N'),
    ('USERS',  'NOTIFICATION', 'receives',   '1:N'),
    ('USERS',  'MONITORING',   'complies',   '1:N'),
    ('USERS',  'CHAT_HISTORY', 'chats',      '1:N'),
    ('USERS',  'AUDIT_LOG',    'performs',   '1:N'),
    ('PERIOD', 'MONITORING',   'covers',     '1:N'),
]

# ── Layout (x, y) per entity, grid coordinates ───────────────────────────────
POS = {
    'CAMPUS':       (0.0, 4.0),
    'USERS':        (0.0, 2.4),
    'SCHOLARSHIP':  (2.2, 4.0),
    'APPLICATION':  (2.2, 2.4),
    'BATCH':        (2.2, 5.4),
    'DOCUMENT':     (0.0, 0.8),
    'NOTIFICATION': (2.2, 0.8),
    'MONITORING':   (4.4, 2.4),
    'PERIOD':       (4.4, 4.0),
    'CHAT_HISTORY': (4.4, 0.8),
    'AUDIT_LOG':    (0.0, -0.9),
}
W, H = 2.0, 1.0   # entity box size


def draw_entity(ax, name, attrs, x, y):
    box = FancyBboxPatch((x, y), W, H, boxstyle='square,pad=0.02',
                         fc='white', ec='black', lw=1.2, zorder=3)
    ax.add_patch(box)
    # Header
    ax.text(x + W/2, y + H - 0.14, name, ha='center', va='center',
            fontsize=8.5, fontweight='bold', family='monospace', zorder=4)
    ax.plot([x, x+W], [y + H - 0.28, y + H - 0.28], color='black', lw=1.0, zorder=4)
    # Attributes (max 5 shown)
    for i, a in enumerate(attrs[:5]):
        ax.text(x + 0.07, y + H - 0.42 - i*0.15, a, ha='left', va='center',
                fontsize=6.0, family='monospace', zorder=4)


def draw_relation(ax, a, b, label, card):
    ax_, ay = POS[a]; bx, by = POS[b]
    x1, y1 = ax_ + W/2, ay + H/2
    x2, y2 = bx + W/2, by + H/2
    arr = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle='-', color='black',
                          lw=0.9, zorder=1, shrinkA=42, shrinkB=42)
    ax.add_patch(arr)
    mx, my = (x1+x2)/2, (y1+y2)/2
    ax.text(mx, my + 0.05, label, ha='center', va='bottom', fontsize=6.0,
            style='italic', family='monospace', zorder=2,
            bbox=dict(fc='white', ec='none', pad=0.5))
    ax.text(mx, my - 0.10, card, ha='center', va='top', fontsize=5.5,
            family='monospace', zorder=2,
            bbox=dict(fc='white', ec='none', pad=0.5))


def build_png():
    fig, ax = plt.subplots(figsize=(11.5, 8.2), dpi=150)
    ax.set_xlim(-0.6, 6.8)
    ax.set_ylim(-1.6, 6.4)
    ax.axis('off')

    for name, (x, y) in POS.items():
        draw_entity(ax, name, ENTITIES[name], x, y)
    for a, b, label, card in RELATIONS:
        draw_relation(ax, a, b, label, card)

    ax.set_title('LSPU ScholarHub — Entity Relationship Diagram',
                 fontsize=11, fontweight='bold', pad=14)
    plt.tight_layout()
    plt.savefig(OUT_PNG, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f'PNG saved: {OUT_PNG}')


def build_docx():
    from docx import Document
    from docx.shared import Inches, Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    doc.styles['Normal'].font.name = 'Times New Roman'
    doc.styles['Normal'].font.size = Pt(12)

    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = h.add_run('Figure X. Entity Relationship Diagram of LSPU ScholarHub')
    r.bold = True
    r.font.size = Pt(13)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_picture(str(OUT_PNG), width=Inches(6.4))

    # Caption
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cr = cap.add_run('Figure 1. Entity Relationship Diagram of the LSPU ScholarHub Database')
    cr.italic = True
    cr.font.size = Pt(11)

    # Short narrative
    doc.add_paragraph()
    intro = doc.add_paragraph()
    intro.add_run(
        'The LSPU ScholarHub database consists of eleven (11) entities centered '
        'on USERS, which anchors student, staff, and administrator accounts. '
        'CAMPUS scopes every major entity for the university-wide, '
        'multi-campus deployment. SCHOLARSHIP programs receive APPLICATIONS '
        'submitted by students, and approved applications are grouped into '
        'BATCHES per academic PERIOD. Students upload registration DOCUMENTS '
        'and Monitoring & Evaluation (MONITORING) submissions, and receive '
        'NOTIFICATIONS. CHAT_HISTORY stores AI assistant conversations, and '
        'AUDIT_LOG records administrative actions for accountability.'
    )
    for run in intro.runs:
        run.font.size = Pt(12)
    intro.paragraph_format.line_spacing = 1.5
    intro.paragraph_format.first_line_indent = Inches(0.5)

    doc.save(OUT_DOCX)
    print(f'DOCX saved: {OUT_DOCX}')


if __name__ == '__main__':
    build_png()
    build_docx()

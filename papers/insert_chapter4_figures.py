"""Insert approved screenshots into Chapter 4 (Section 4.2.5) of the thesis docx.

- Figure 9 (Admin/SFAO Web): 6 desktop screenshots stacked, sub-labeled (a)-(f)
- Figure 10 (Student Mobile): 4 panels (a)-(d), phone shots side-by-side in borderless tables
- Removes only the two [IMAGE PLACEHOLDER] paragraphs for Figures 9 and 10
- Leaves the Figure 8 placeholder, all text, and captions untouched
- Saves to a NEW file so the original stays safe

Run:  python papers/insert_chapter4_figures.py
"""
import io, os, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

SRC = r'C:\Users\kirit\Downloads\ScholarHub Chapter 4-5.docx'
OUT = r'C:\Users\kirit\Downloads\ScholarHub Chapter 4-5 (with figures).docx'
IMG = r'C:\Users\kirit\Downloads\Chapter4_Figures'

FIG9 = [
    ('fig9a_dashboard.png',       '(a) Web dashboard overview'),
    ('fig9b_review_queue.png',    '(b) Application review queue'),
    ('fig9c_review_modal.png',    '(c) Application review and decision modal'),
    ('fig9d_student_profile.png', '(d) Student profile with OCR-parsed documents'),
    ('fig9e_monitoring.png',      '(e) Scholar monitoring and tracking'),
    ('fig9f_announcements.png',   '(f) Announcement composer with multi-channel delivery'),
]

# Figure 10: pairs of images per row (phone shots are tall+narrow)
FIG10_ROWS = [
    [('fig10a_dashboard_top.png', '(a) Student dashboard'),
     ('fig10a_dashboard_bottom.png', '')],
    [('fig10b_applications.png', '(b) My Applications with status tracking'),
     ('fig10d_ai_assistant.png', '(d) AI chatbot assistant')],
    [('fig10c_documents_profile.png', ''),
     ('fig10c_documents_cor.png', '(c) Document upload and replacement')],
    [('fig10c_documents_cog.png', ''),
     None],
]


def set_cell_no_borders(cell):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement('w:tcBorders')
    for edge in ('top', 'left', 'bottom', 'right'):
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:val'), 'nil')
        borders.append(el)
    tcPr.append(borders)


def add_sub_label(paragraph, text):
    """Append ' (x) label' in smaller italic text to a centered paragraph."""
    run = paragraph.add_run(f' {text}')
    run.italic = True
    run.font.size = Pt(9)


def main():
    doc = Document(SRC)
    paras = doc.paragraphs

    # ── Locate anchors ────────────────────────────────────────────────────
    ph9_idx = ph10_idx = None
    cap9_idx = cap10_idx = None
    for i, p in enumerate(paras):
        t = p.text.strip()
        if t.startswith('[IMAGE PLACEHOLDER'):
            if ph9_idx is None:
                ph9_idx = i
            else:
                ph10_idx = i
        if t.startswith('Figure 9.'):
            cap9_idx = i
        if t.startswith('Figure 10.'):
            cap10_idx = i

    assert ph9_idx and cap9_idx, 'Figure 9 placeholder/caption not found'
    assert ph10_idx and cap10_idx, 'Figure 10 placeholder/caption not found'
    print(f'Figure 9: placeholder @ {ph9_idx}, caption @ {cap9_idx}')
    print(f'Figure 10: placeholder @ {ph10_idx}, caption @ {cap10_idx}')

    # ── Insert Figure 9 (6 stacked shots) at the placeholder position ────
    ph9 = paras[ph9_idx]
    for img, label in FIG9:
        path = os.path.join(IMG, img)
        # Image paragraph
        p_img = ph9.insert_paragraph_before()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p_img.add_run()
        run.add_picture(path, width=Inches(5.8))
        # Sub-label paragraph
        p_lab = ph9.insert_paragraph_before()
        p_lab.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p_lab.add_run(label)
        r.italic = True
        r.font.size = Pt(9)
    # Remove the placeholder paragraph itself
    ph9._element.getparent().remove(ph9._element)
    print('Figure 9: 6 screenshots inserted')

    # ── Re-locate Figure 10 anchors (indices shifted) ─────────────────────
    paras = doc.paragraphs
    ph10 = cap10 = None
    for p in paras:
        t = p.text.strip()
        if t.startswith('[IMAGE PLACEHOLDER') and ph10 is None:
            ph10 = p
        if t.startswith('Figure 10.'):
            cap10 = p
    assert ph10 is not None and cap10 is not None

    # ── Insert Figure 10 (side-by-side phone shots in borderless tables) ─
    anchor = ph10._element
    for row in FIG10_ROWS:
        row = [c for c in row if c]          # drop None cells
        if not row:
            continue
        tbl = doc.add_table(rows=1, cols=len(row))
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        for cell, (img, label) in zip(tbl.rows[0].cells, row):
            set_cell_no_borders(cell)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run()
            run.add_picture(os.path.join(IMG, img), width=Inches(2.5))
            if label:
                pl = cell.add_paragraph()
                pl.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r = pl.add_run(label)
                r.italic = True
                r.font.size = Pt(9)
        # Move the table to just before the placeholder anchor
        anchor.addprevious(tbl._tbl)
        spacer = OxmlElement('w:p')
        anchor.addprevious(spacer)
    # Remove the placeholder paragraph
    ph10._element.getparent().remove(ph10._element)
    print('Figure 10: 4 panels (7 images) inserted')

    doc.save(OUT)
    print(f'Saved: {OUT}')


if __name__ == '__main__':
    main()

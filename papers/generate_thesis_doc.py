"""
Generate the thesis-submission DOCX from the papers/ markdown files.

Output: papers/LSPU_ScholarHub_Thesis_Documentation.docx

Formatting (Philippine thesis conventions):
  - Times New Roman 12 pt body, 1.5 line spacing
  - 1.5" left margin (binding), 1" top/bottom/right
  - Page numbers in the footer (none on the title page)
  - Auto table of contents (Word: right-click -> Update Field, or F9)

Run:  python papers/generate_thesis_doc.py
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

PAPERS_DIR = Path(__file__).parent
PAPERS = ['TECH_STACK.md', 'SYSTEM_ARCHITECTURE.md', 'DATABASE_SCHEMA.md',
          'FUNCTIONALITIES.md']
OUTPUT = PAPERS_DIR / 'LSPU_ScholarHub_Thesis_Documentation.docx'

# Glyphs that may be missing from Times New Roman / Courier New on Windows
SANITIZE = {'₱': 'Php ', '▶': '>', '⇒': '=>'}

INLINE_RE = re.compile(r'(\*\*.+?\*\*|`[^`]+`|\[[^\]]+\]\([^)]*\)|\*[^*\s][^*]*\*)')


def clean(text):
    for k, v in SANITIZE.items():
        text = text.replace(k, v)
    return text


def add_inline(par, text, force_italic=False, bold_all=False):
    """Render markdown inline formatting (**bold**, `code`, *italic*, links)."""
    text = clean(text)
    for tok in INLINE_RE.split(text):
        if not tok:
            continue
        if tok.startswith('**') and tok.endswith('**') and len(tok) > 4:
            r = par.add_run(tok[2:-2]); r.bold = True
        elif tok.startswith('`') and tok.endswith('`') and len(tok) > 2:
            r = par.add_run(tok[1:-1]); r.font.name = 'Courier New'; r.font.size = Pt(10)
        elif tok.startswith('[') and '](' in tok:
            m = re.match(r'\[([^\]]+)\]\(([^)]*)\)', tok)
            r = par.add_run(m.group(1) if m else tok); r.italic = True
        elif tok.startswith('*') and tok.endswith('*') and len(tok) > 2:
            r = par.add_run(tok[1:-1]); r.italic = True
        else:
            r = par.add_run(tok)
        if force_italic:
            r.italic = True
        if bold_all:
            r.bold = True


def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear'); shd.set(qn('w:color'), 'auto'); shd.set(qn('w:fill'), fill)
    tcPr.append(shd)


def add_toc_field(par):
    run = par.add_run()
    fld = OxmlElement('w:fldChar'); fld.set(qn('w:fldCharType'), 'begin')
    instr = OxmlElement('w:instrText'); instr.set(qn('xml:space'), 'preserve')
    instr.text = 'TOC \\o "1-3" \\h \\z \\u'
    sep = OxmlElement('w:fldChar'); sep.set(qn('w:fldCharType'), 'separate')
    holder = OxmlElement('w:t')
    holder.text = ('Right-click here and choose "Update Field" (or press F9) '
                   'to build the table of contents.')
    end = OxmlElement('w:fldChar'); end.set(qn('w:fldCharType'), 'end')
    for el in (fld, instr, sep, holder, end):
        run._r.append(el)


def add_page_number(par):
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = par.add_run()
    f1 = OxmlElement('w:fldChar'); f1.set(qn('w:fldCharType'), 'begin')
    it = OxmlElement('w:instrText'); it.set(qn('xml:space'), 'preserve'); it.text = 'PAGE'
    f2 = OxmlElement('w:fldChar'); f2.set(qn('w:fldCharType'), 'end')
    for el in (f1, it, f2):
        run._r.append(el)


def render_markdown(doc, md_text):
    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()

        # Fenced code block -> Courier, single-spaced, scaled to fit
        if s.startswith('```'):
            block, i = [], i + 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                block.append(lines[i].rstrip()); i += 1
            i += 1
            maxlen = max((len(l) for l in block), default=0)
            size = 8 if maxlen <= 90 else 7.5 if maxlen <= 100 else 6.5
            for l in block:
                p = doc.add_paragraph()
                p.paragraph_format.line_spacing = 1.0
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)
                r = p.add_run(l if l else ' ')
                r.font.name = 'Courier New'; r.font.size = Pt(size)
            continue

        if not s or s == '---':
            i += 1; continue

        if s.startswith('### '):
            doc.add_heading(clean(s[4:]), level=3); i += 1; continue
        if s.startswith('## '):
            doc.add_heading(clean(s[3:]), level=2); i += 1; continue
        if s.startswith('# '):
            doc.add_heading(clean(s[2:]), level=1); i += 1; continue

        if s.startswith('> '):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.3)
            add_inline(p, s[2:], force_italic=True); i += 1; continue

        if s.startswith('|'):
            tbl_lines = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                tbl_lines.append(lines[i].strip()); i += 1
            rows = []
            for tl in tbl_lines:
                if re.match(r'^\|[\s:\-|]+\|$', tl):
                    continue
                rows.append([c.strip() for c in tl.strip('|').split('|')])
            if rows:
                ncols = max(len(r) for r in rows)
                t = doc.add_table(rows=len(rows), cols=ncols)
                t.style = 'Table Grid'; t.alignment = WD_TABLE_ALIGNMENT.CENTER
                t.autofit = True
                for ri, row in enumerate(rows):
                    for ci in range(ncols):
                        cell = t.cell(ri, ci)
                        par = cell.paragraphs[0]
                        par.paragraph_format.line_spacing = 1.0
                        par.paragraph_format.space_before = Pt(1)
                        par.paragraph_format.space_after = Pt(1)
                        add_inline(par, row[ci] if ci < len(row) else '',
                                   bold_all=(ri == 0))
                        for r in par.runs:
                            r.font.size = Pt(10.5)
                        if ri == 0:
                            shade(cell, 'D9D9D9')
                doc.add_paragraph()  # breathing room after the table
            continue

        if s.startswith('- '):
            buf = [s[2:]]
            while (i + 1 < len(lines) and lines[i + 1].strip()
                   and lines[i + 1].startswith(('  ', '\t'))):
                i += 1; buf.append(lines[i].strip())
            p = doc.add_paragraph(style='List Bullet')
            add_inline(p, ' '.join(buf)); i += 1; continue

        m = re.match(r'^(\d+)\.\s+(.*)$', s)
        if m:
            buf = [m.group(2)]
            while (i + 1 < len(lines) and lines[i + 1].strip()
                   and lines[i + 1].startswith(('  ', '\t'))
                   and not lines[i + 1].strip().startswith('|')):
                i += 1; buf.append(lines[i].strip())
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.35)
            p.paragraph_format.first_line_indent = Inches(-0.2)
            p.add_run(m.group(1) + '. ')
            add_inline(p, ' '.join(buf)); i += 1; continue

        # Plain paragraph — merge wrapped continuation lines so inline
        # formatting (e.g. **bold**) spanning a source line break still works
        buf = [s]
        while (i + 1 < len(lines)):
            nxt = lines[i + 1].strip()
            if (not nxt or nxt.startswith(('#', '>', '|', '-', '```'))
                    or re.match(r'^\d+\.\s+', nxt)):
                break
            buf.append(nxt); i += 1
        p = doc.add_paragraph()
        add_inline(p, ' '.join(buf)); i += 1


def build():
    doc = Document()

    cp = doc.core_properties
    cp.title = 'LSPU ScholarHub — Thesis Documentation'
    cp.author = 'LSPU ScholarHub Development Team'
    cp.subject = 'Web-Based Scholarship Management System for LSPU'

    # ── Base styles ────────────────────────────────────────────────────────
    normal = doc.styles['Normal']
    normal.font.name = 'Times New Roman'; normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(6)

    for nm, sz, sb in [('Heading 1', 16, 0), ('Heading 2', 14, 14), ('Heading 3', 12, 10)]:
        st = doc.styles[nm]
        st.font.name = 'Times New Roman'; st.font.size = Pt(sz); st.font.bold = True
        st.font.color.rgb = RGBColor(0, 0, 0)
        st.paragraph_format.space_before = Pt(sb)
        st.paragraph_format.space_after = Pt(6)
        st.paragraph_format.line_spacing = 1.15
        st.paragraph_format.keep_with_next = True
    doc.styles['Heading 1'].paragraph_format.page_break_before = True

    # ── Page setup ─────────────────────────────────────────────────────────
    sec = doc.sections[0]
    sec.left_margin = Inches(1.5)   # binding edge
    sec.right_margin = Inches(1)
    sec.top_margin = Inches(1)
    sec.bottom_margin = Inches(1)
    sec.different_first_page_header_footer = True   # no page number on title page
    add_page_number(sec.footer.paragraphs[0])

    # ── Title page ─────────────────────────────────────────────────────────
    def centered(text, size, bold=False, space_after=6, italic=False, caps=False):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(space_after)
        r = p.add_run(text.upper() if caps else text)
        r.bold = bold; r.italic = italic; r.font.size = Pt(size)
        return p

    centered('Laguna State Polytechnic University', 14, bold=True, space_after=2)
    centered('Scholarship Office', 12, italic=True, space_after=48)
    centered('LSPU ScholarHub', 24, bold=True, space_after=6)
    centered('A Web-Based Scholarship Management System', 16, space_after=4)
    centered('for Laguna State Polytechnic University', 16, space_after=48)
    centered('TECHNICAL DOCUMENTATION', 14, bold=True, caps=True, space_after=8)
    centered('Technology Stack · System Architecture · Database Schema · Functionalities',
             12, italic=True, space_after=72)
    centered('Prepared by: ________________________________', 12, space_after=48)
    centered('September 2026', 12)
    doc.add_page_break()

    # ── Table of contents ──────────────────────────────────────────────────
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run('TABLE OF CONTENTS'); r.bold = True; r.font.size = Pt(14)
    add_toc_field(doc.add_paragraph())

    # ── Preface ────────────────────────────────────────────────────────────
    doc.add_heading('About This Document', level=1)
    intro = [
        'This document consolidates the technical documentation papers of the '
        'LSPU ScholarHub system — a web-based scholarship management system for '
        'Laguna State Polytechnic University (LSPU). It is organized into four '
        'parts, each of which was prepared for direct adaptation into the '
        'corresponding thesis chapters:',
    ]
    for t in intro:
        p = doc.add_paragraph(); add_inline(p, t)
    for item in [
        '**Part I — Technology Stack.** Languages, frameworks, libraries (with '
        'exact pinned versions), cloud services, and the justification for each '
        'choice. (Chapter 3 — Software Requirements)',
        '**Part II — System Architecture.** Three-tier MVC design, module map, '
        'request flow, multi-campus scoping, security architecture, and '
        'deployment topology. (Chapter 3 — System Design)',
        '**Part III — Database Schema.** The twelve entities, their '
        'relationships, and the integrity rules of the system. '
        '(Chapter 3 — Database Design / Appendix)',
        '**Part IV — Functionalities & Workflow.** Role-by-role feature '
        'inventory, the five-stage scholarship lifecycle, and a comparison of '
        'the manual process the system replaced. (Chapters 1–2)',
    ]:
        p = doc.add_paragraph(style='List Bullet'); add_inline(p, item)
    p = doc.add_paragraph()
    add_inline(p, 'All version numbers reflect the deployed system as of '
                  'September 2026 and match the pinned dependencies in the '
                  'project\'s `requirements.txt`. Supporting artifacts — '
                  'flowchart figures, the full database dump, and the process '
                  'workflow document — accompany this document in the project '
                  'repository under `docs/` and `database/`.')

    # ── The four papers ────────────────────────────────────────────────────
    for name in PAPERS:
        path = PAPERS_DIR / name
        render_markdown(doc, path.read_text(encoding='utf-8'))

    doc.save(OUTPUT)
    print(f'Created: {OUTPUT}')
    print(f'Size   : {OUTPUT.stat().st_size / 1024:.1f} KB')


if __name__ == '__main__':
    build()

"""
Annual Report Service — multi-year (up to 6 AY) comparison + written report.

Pulls REAL data only (no seeds, no placeholders). Years with no recorded
applications are shown as empty and the narrative says so honestly.

Comparison basis: academic year (both semesters combined per AY).
Metrics per year: applications, approved, rejected, pending, approval rate,
active scholars, graduated / dropped out, average applicant GWA.
"""

import io
from datetime import datetime

from app import db
from app.models import User, ScholarshipApplication, AcademicPeriod
from app.models.scholarship import ApplicationStatus


MAX_YEARS = 6

# Metric descriptors shared by table + chart + export
METRICS = [
    ('apps',          'Applications',    'int'),
    ('approved',      'Approved',        'int'),
    ('rejected',      'Rejected',        'int'),
    ('pending',       'Pending',         'int'),
    ('approval_rate', 'Approval Rate',   'pct'),
    ('active',        'Active Scholars', 'int'),
    ('graduated',     'Graduated',       'int'),
    ('dropped',       'Dropped Out',     'int'),
    ('avg_gwa',       'Avg. GWA',        'gwa'),
]


# ─────────────────────────────────────────────────────────────────────────────
# Data assembly
# ─────────────────────────────────────────────────────────────────────────────

def _campus_ctx():
    """Resolve campus scope the same way views do (super admin honors selector)."""
    from flask import session
    if session.get('user_type') == 'super_admin':
        return session.get('campus_context')  # None = all campuses
    me = db.session.get(User, session.get('user_id'))
    return me.campus_id if me else None


def _group_years():
    """Group all academic periods by academic_year, ordered oldest→newest.

    Returns [(year_label, [period_id, ...]), ...] capped at the most recent
    MAX_YEARS distinct years.
    """
    periods = AcademicPeriod.query.all()
    groups = {}
    for p in periods:
        groups.setdefault(p.academic_year, []).append(p.id)

    def _ay_key(label):
        try:
            return int(str(label).split('-')[0])
        except (ValueError, TypeError):
            return 0

    ordered = sorted(groups.items(), key=lambda kv: _ay_key(kv[0]))
    return ordered[-MAX_YEARS:]


_FMT_BY_KEY = {k: f for k, _l, f in METRICS}


def _delta_info(vals, fmt):
    """Latest-year vs prior-year delta for the comparison table.
    Returns {'text': str|None, 'good': bool|None}.
    """
    if len(vals) < 2 or vals[-1] is None or vals[-2] is None:
        return {'text': None, 'good': None}
    d = vals[-1] - vals[-2]
    if d == 0:
        return {'text': '0', 'good': None}
    sign = '+' if d > 0 else '\u2212'
    a = abs(d)
    if fmt == 'pct':
        text = f'{sign}{a:.1f} pp'
    elif fmt == 'gwa':
        text = f'{sign}{a:.2f}'
    else:
        text = f'{sign}{int(a) if a == int(a) else a}'
    good = (d < 0) if fmt == 'gwa' else (d > 0)
    return {'text': text, 'good': good}


def build_yearly_comparison(campus_ctx=None):
    """Return the per-year comparison dataset for up to 6 academic years.

    Structure: {
      'years':     ['2021-2022', ...],           # oldest → newest
      'rows':      {metric_key: [values aligned with years]},
      'metrics':   [(key, label, fmt), ...],
    }
    """
    campus_ctx = campus_ctx if campus_ctx is not None else _campus_ctx()
    year_groups = _group_years()

    rows = {k: [] for k, _lbl, _f in METRICS}
    years = []
    for year_label, period_ids in year_groups:
        q = (ScholarshipApplication.query
             .join(User, ScholarshipApplication.applicant_id == User.id)
             .filter(ScholarshipApplication.academic_period_id.in_(period_ids)))
        if campus_ctx:
            q = q.filter(User.campus_id == campus_ctx)
        apps = q.all()

        n = len(apps)
        appr = sum(1 for a in apps if a.status == ApplicationStatus.APPROVED)
        rej = sum(1 for a in apps if a.status == ApplicationStatus.REJECTED)
        pend = sum(1 for a in apps if a.status in (
            ApplicationStatus.PENDING, ApplicationStatus.UNDER_REVIEW))
        active = sum(1 for a in apps if a.status == ApplicationStatus.APPROVED
                     and a.scholar_status == 'active')

        # Graduated / dropped among this year's approved applicants
        grad = drop = 0
        if appr:
            ids = {a.applicant_id for a in apps
                   if a.status == ApplicationStatus.APPROVED}
            smap = dict(db.session.query(User.id, User.student_status)
                        .filter(User.id.in_(ids)).all())
            grad = sum(1 for u in ids if smap.get(u) == 'graduated')
            drop = sum(1 for u in ids if smap.get(u) == 'dropped_out')

        # Average GWA of applicants that year
        gwas = [a.applicant.gwa for a in apps
                if a.applicant is not None and a.applicant.gwa is not None]
        avg_gwa = round(sum(gwas) / len(gwas), 2) if gwas else None

        rows['apps'].append(n)
        rows['approved'].append(appr)
        rows['rejected'].append(rej)
        rows['pending'].append(pend)
        rows['approval_rate'].append(round(appr / n * 100, 1) if n else None)
        rows['active'].append(active)
        rows['graduated'].append(grad)
        rows['dropped'].append(drop)
        rows['avg_gwa'].append(avg_gwa)
        years.append(year_label)

    deltas = {k: _delta_info(rows[k], _FMT_BY_KEY[k]) for k, _l, _f in METRICS}
    return {'years': years, 'rows': rows, 'metrics': METRICS, 'deltas': deltas}


def build_scope_label(campus_ctx):
    """Human-readable scope for headers/downloads."""
    if not campus_ctx:
        return 'All Campuses'
    from app.models import Campus
    c = db.session.get(Campus, campus_ctx)
    return f'Campus: {c.name}' if c else 'Selected Campus'


# ─────────────────────────────────────────────────────────────────────────────
# Written report
# ─────────────────────────────────────────────────────────────────────────────

def _delta_str(cur, prev, fmt='int', higher_is_better=True):
    """Human phrase for change vs previous year. None-safe."""
    if cur is None or prev is None:
        return None
    d = cur - prev
    if d == 0:
        return 'steady'
    if fmt == 'pct':
        dd = f"{abs(d):.1f} pp"
    elif fmt == 'gwa':
        dd = f"{abs(d):.2f} points"
    else:
        dd = f"{abs(d)}"
    word = 'up' if d > 0 else 'down'
    tone = ''
    if higher_is_better is not None:
        improved = (d > 0) == higher_is_better
        tone = ' (improvement)' if improved else ' (decline)'
    return f"{word} {dd}{tone}"


def _paragraphs(comp):
    """Generate the written report as a list of (heading, [paragraph, ...])."""
    years = comp['years']
    rows = comp['rows']
    n = len(years)
    latest = years[-1] if years else None
    cur = {k: rows[k][-1] if rows[k] else None for k, _l, _f in METRICS}
    prev = {k: rows[k][-2] if n > 1 and len(rows[k]) > 1 else None
            for k, _l, _f in METRICS}
    has_any = any(rows['apps'])

    sections = []

    # ── Overview ──
    ov = []
    if not has_any:
        ov.append(
            "No scholarship applications have been recorded in the selected "
            "scope for any of the covered academic years. This report will "
            "populate automatically as applications are received.")
    else:
        first_idx = next(i for i, v in enumerate(rows['apps']) if v)
        covered = n - first_idx
        ov.append(
            f"This report covers {covered} academic year(s) with recorded "
            f"activity ({years[first_idx]} to {latest}) within a comparison "
            f"window of up to {MAX_YEARS} academic years.")
        if n == 1:
            if cur['approval_rate'] is not None:
                ov.append(
                    f"For AY {latest}, the office processed {cur['apps']} "
                    f"application(s): {cur['approved']} approved, "
                    f"{cur['rejected']} rejected, and {cur['pending']} "
                    f"awaiting review, for an approval rate of "
                    f"{cur['approval_rate']:.1f}%.")
            else:
                ov.append(
                    f"For AY {latest}, the office processed {cur['apps']} "
                    f"application(s).")
        else:
            ov.append(
                f"For AY {latest}, the office processed {cur['apps']} "
                f"application(s): {cur['approved']} approved, "
                f"{cur['rejected']} rejected, and {cur['pending']} awaiting "
                f"review.")
        if n > 1 and prev['apps']:
            d = _delta_str(cur['apps'], prev['apps'])
            if d:
                ov.append(
                    f"Compared with AY {years[-2]}, applications were {d} "
                    f"({prev['apps']} → {cur['apps']}).")
        if (n > 1 and prev['apps'] and cur['approval_rate'] is not None
                and prev['approval_rate'] is not None):
            d = _delta_str(cur['approval_rate'], prev['approval_rate'], 'pct')
            if d:
                ov.append(
                    f"The approval rate was {d} "
                    f"({prev['approval_rate']:.1f}% → "
                    f"{cur['approval_rate']:.1f}%).")
    sections.append(('Overview', ov))

    # ── Program Performance ──
    pp = []
    if not has_any:
        pp.append("No application activity on record in this scope.")
    elif n == 1:
        pp.append(
            f"Only AY {latest} has recorded data so far. Year-over-year "
            f"commentary becomes available once a second academic year has "
            f"applications on record.")
        if cur['graduated'] or cur['dropped']:
            pp.append(
                f"Among approved scholars in AY {latest}, {cur['graduated']} "
                f"have since graduated and {cur['dropped']} dropped out.")
        if cur['avg_gwa'] is not None:
            pp.append(f"The average GWA of applicants in AY {latest} was "
                      f"{cur['avg_gwa']:.2f}.")
    else:
        if (cur['approved'] is not None and prev['approved'] is not None
                and prev['apps']):
            d = _delta_str(cur['approved'], prev['approved'])
            if d:
                pp.append(f"Approved scholars were {d} year-over-year "
                          f"({prev['approved']} → {cur['approved']}).")
        if cur['graduated'] or cur['dropped']:
            pp.append(
                f"Among approved scholars in AY {latest}, {cur['graduated']} "
                f"have since graduated and {cur['dropped']} dropped out.")
        if cur['avg_gwa'] is not None:
            pp.append(f"The average GWA of applicants in AY {latest} was "
                      f"{cur['avg_gwa']:.2f}.")
        if cur['avg_gwa'] is not None and prev['avg_gwa'] is not None:
            d = _delta_str(cur['avg_gwa'], prev['avg_gwa'], 'gwa',
                           higher_is_better=False)
            if d:
                pp.append(f"Average GWA was {d} versus the prior year "
                          f"({prev['avg_gwa']:.2f} → {cur['avg_gwa']:.2f}) — "
                          f"for GWA, lower is better.")
        if not pp:
            pp.append("Not enough variation in the data for additional "
                      "year-over-year commentary.")
    sections.append(('Program Performance', pp))

    # ── Trends ──
    tr = []
    if not has_any:
        tr.append("No trends to report yet — no recorded applications in "
                  "this scope.")
    elif n == 1:
        tr.append(
            "Trend analysis requires at least two academic years with data; "
            f"currently only AY {latest} has records.")
    else:
        nonempty = [i for i in range(n) if rows['apps'][i]]
        if len(nonempty) > 1:
            peak_i = max(nonempty, key=lambda i: rows['apps'][i])
            low_i = min(nonempty, key=lambda i: rows['apps'][i])
            tr.append(
                f"Application volume peaked in AY {years[peak_i]} "
                f"({rows['apps'][peak_i]} applications) and was lowest in "
                f"AY {years[low_i]} ({rows['apps'][low_i]}).")
        elif nonempty:
            tr.append(
                f"AY {years[nonempty[0]]} is currently the only academic "
                f"year with recorded applications "
                f"({rows['apps'][nonempty[0]]}).")
        if cur['active'] is not None:
            tr.append(
                f"As of AY {latest}, {cur['active']} approved scholar(s) "
                f"remain active.")
            if prev['active'] is not None and prev['apps']:
                d = _delta_str(cur['active'], prev['active'])
                if d:
                    tr.append(
                        f"The active-scholar base was {d} versus the prior "
                        f"year ({prev['active']} → {cur['active']}).")
        if not tr:
            tr.append("Trend commentary will appear as more years of data "
                      "accumulate.")
    sections.append(('Trends', tr))

    # ── Retention & Completion ──
    rt = []
    if has_any and (any(rows['graduated']) or any(rows['dropped'])):
        if n > 1:
            rt.append(
                f"Graduated: {prev['graduated']} → {cur['graduated']}; "
                f"dropped out: {prev['dropped']} → {cur['dropped']} "
                f"(prior year → current).")
        else:
            rt.append(
                f"Among approved scholars in AY {latest}: {cur['graduated']} "
                f"graduated and {cur['dropped']} dropped out.")
        rt.append(
            "These figures reflect the current status flags of approved "
            "applicants.")
    else:
        rt.append(
            "Graduation and dropout tracking begins once approved scholars "
            "are marked as Graduated or Dropped Out in the student directory.")
    sections.append(('Retention & Completion', rt))

    # ── Data Coverage ──
    dc = []
    if n == 0:
        dc.append("No academic periods are configured yet. Add them under "
                  "Admin → Settings → Academic Periods.")
    else:
        empty = [y for y, a in zip(years, rows['apps']) if not a]
        if empty:
            dc.append(
                f"Academic years with no recorded applications in this "
                f"scope: {', '.join(empty)}. These years show as zero in "
                f"the comparison table and charts.")
        else:
            dc.append("All covered academic years have recorded applications.")
        dc.append(f"Comparison window (oldest first): {', '.join(years)}.")
    sections.append(('Data Coverage', dc))

    return sections


def build_written_report(comp):
    """Return {'sections': [(heading, [paragraphs])]} for template + export."""
    return {'sections': _paragraphs(comp)}


# ─────────────────────────────────────────────────────────────────────────────
# Exports (PDF / DOCX) — written report + comparison table
# ─────────────────────────────────────────────────────────────────────────────

def _pdf(comp, written, title, subtitle):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                    Paragraph, HRFlowable)
    from reportlab.lib.enums import TA_CENTER

    LSPU_BLUE = colors.HexColor('#1a3a6b')
    LSPU_GOLD = colors.HexColor('#f5a623')
    LSPU_LIGHT = colors.HexColor('#e8f0fe')

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm)

    styles = getSampleStyleSheet()
    st_title = ParagraphStyle('ARTitle', parent=styles['Title'], fontSize=15,
                              textColor=LSPU_BLUE, alignment=TA_CENTER,
                              spaceAfter=2)
    st_sub = ParagraphStyle('ARSub', parent=styles['Normal'], fontSize=9,
                            textColor=colors.grey, alignment=TA_CENTER,
                            spaceAfter=10)
    st_h = ParagraphStyle('ARH', parent=styles['Normal'], fontSize=11.5,
                          textColor=LSPU_BLUE, fontName='Helvetica-Bold',
                          spaceBefore=12, spaceAfter=4)
    st_h2 = ParagraphStyle('ARH2', parent=styles['Normal'], fontSize=10,
                           fontName='Helvetica-Bold', spaceBefore=8, spaceAfter=2)
    st_p = ParagraphStyle('ARP', parent=styles['Normal'], fontSize=9.5,
                          leading=13)

    story = []
    story.append(Paragraph('LSPU ScholarHub', st_title))
    story.append(Paragraph(title, ParagraphStyle(
        'ART2', parent=styles['Normal'], fontSize=11, textColor=LSPU_BLUE,
        alignment=TA_CENTER, spaceAfter=2)))
    story.append(Paragraph(
        f'{subtitle}<br/>Generated: {datetime.now().strftime("%B %d, %Y")}',
        st_sub))
    story.append(HRFlowable(width='100%', thickness=1.5, color=LSPU_GOLD,
                            spaceAfter=10))

    # ── Written narrative ──
    story.append(Paragraph('Written Report', st_h))
    for heading, paras in written['sections']:
        story.append(Paragraph(heading, st_h2))
        for p in paras:
            story.append(Paragraph(p, st_p))

    # ── Comparison table ──
    story.append(Paragraph('Multi-Year Comparison', st_h))
    years = comp['years']
    data = [['Metric'] + [f'AY {y}' for y in years]]
    for key, label, fmt in comp['metrics']:
        cells = [label]
        for v in comp['rows'][key]:
            if v is None:
                cells.append('—')
            elif fmt == 'pct':
                cells.append(f'{v:.1f}%')
            elif fmt == 'gwa':
                cells.append(f'{v:.2f}')
            else:
                cells.append(str(v))
        data.append(cells)

    tbl = Table(data, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, 0), LSPU_BLUE),
        ('TEXTCOLOR',   (0, 0), (-1, 0), colors.white),
        ('FONTNAME',    (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, -1), 8),
        ('ALIGN',       (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',  (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LSPU_LIGHT]),
        ('GRID',        (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('LINEBELOW',   (0, 0), (-1, 0), 1.5, LSPU_GOLD),
    ]))
    story.append(tbl)

    doc.build(story)
    buf.seek(0)
    return buf


def _docx(comp, written, title, subtitle):
    from docx import Document as DocxDocument
    from docx.shared import Pt, Cm, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    doc = DocxDocument()
    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)

    h1 = doc.add_heading('LSPU ScholarHub', level=1)
    h1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    h1.runs[0].font.color.rgb = RGBColor(0x1a, 0x3a, 0x6b)

    h2 = doc.add_heading(title, level=2)
    h2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    h2.runs[0].font.color.rgb = RGBColor(0x1a, 0x3a, 0x6b)

    meta = doc.add_paragraph(
        f'{subtitle} · Generated: {datetime.now().strftime("%B %d, %Y")}')
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.runs[0].font.size = Pt(9)
    meta.runs[0].font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    doc.add_paragraph()

    doc.add_heading('Written Report', level=3)
    for heading, paras in written['sections']:
        doc.add_heading(heading, level=4)
        for p in paras:
            doc.add_paragraph(p)

    doc.add_heading('Multi-Year Comparison', level=3)
    headers = ['Metric'] + [f'AY {y}' for y in comp['years']]
    tbl = doc.add_table(rows=1, cols=len(headers))
    tbl.style = 'Table Grid'
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER

    for i, h in enumerate(headers):
        cell = tbl.rows[0].cells[i]
        cell.text = h
        run = cell.paragraphs[0].runs[0]
        run.font.bold = True
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        tcPr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), '1a3a6b')
        tcPr.append(shd)

    for key, label, fmt in comp['metrics']:
        cells = tbl.add_row().cells
        cells[0].text = label
        cells[0].paragraphs[0].runs[0].font.size = Pt(8)
        for ci, v in enumerate(comp['rows'][key], start=1):
            if v is None:
                txt = '—'
            elif fmt == 'pct':
                txt = f'{v:.1f}%'
            elif fmt == 'gwa':
                txt = f'{v:.2f}'
            else:
                txt = str(v)
            cells[ci].text = txt
            for r in cells[ci].paragraphs[0].runs:
                r.font.size = Pt(8)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def export_written_report(fmt='pdf', comp=None, written=None,
                          scope_label='All Campuses'):
    """Build the downloadable annual report. fmt: 'pdf' | 'docx'."""
    comp = comp or build_yearly_comparison()
    written = written or build_written_report(comp)

    title = 'Annual Scholarship Report'
    subtitle = f'Scope: {scope_label} · Up to {MAX_YEARS}-Year Comparison'

    if fmt == 'pdf':
        buf = _pdf(comp, written, title, subtitle)
        mime = 'application/pdf'
    elif fmt == 'docx':
        buf = _docx(comp, written, title, subtitle)
        mime = ('application/vnd.openxmlformats-officedocument'
                '.wordprocessingml.document')
    else:
        raise ValueError(f'Unsupported annual report format: {fmt}')

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'lspu_scholarhub_annual_report_{timestamp}.{fmt}'
    return buf, mime, filename

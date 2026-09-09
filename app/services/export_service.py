"""
Export Service for LSPU ScholarHub
Generates PDF, Excel (XLSX), CSV, and DOCX reports.

Supported report types
----------------------
  applications  – full application list with status
  scholarships  – scholarship programme summary
  students      – student roster
  approved      – approved scholars only
"""

import io
import csv
from datetime import datetime

# ── PDF ───────────────────────────────────────────────────────────────────────
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                Paragraph, Spacer, HRFlowable)
from reportlab.lib.enums import TA_CENTER

# ── Excel ─────────────────────────────────────────────────────────────────────
from openpyxl import Workbook
from openpyxl.styles import (Font, PatternFill, Alignment, Border, Side)
from openpyxl.utils import get_column_letter

# ── DOCX ──────────────────────────────────────────────────────────────────────
from docx import Document as DocxDocument
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

LSPU_BLUE  = colors.HexColor('#1a3a6b')
LSPU_GOLD  = colors.HexColor('#f5a623')
LSPU_LIGHT = colors.HexColor('#e8f0fe')

REPORT_TITLES = {
    'applications': 'Scholarship Applications Report',
    'scholarships': 'Scholarship Programmes Report',
    'students':     'Student Roster Report',
    'approved':     'Approved Scholars Report',
}


def _now_str():
    return datetime.now().strftime('%B %d, %Y %I:%M %p')


def _safe(val, default='—'):
    if val is None:
        return default
    return str(val)


# ─────────────────────────────────────────────────────────────────────────────
# Data builders  (return list-of-dicts regardless of report type)
# ─────────────────────────────────────────────────────────────────────────────

def _build_applications_data(filters=None):
    from app.models import ScholarshipApplication, User, Scholarship
    from app.models.scholarship import ApplicationStatus

    query = ScholarshipApplication.query
    if filters:
        status = filters.get('status')
        scholarship_id = filters.get('scholarship_id')
        if status:
            try:
                query = query.filter_by(status=ApplicationStatus(status))
            except ValueError:
                pass
        if scholarship_id:
            query = query.filter_by(scholarship_id=int(scholarship_id))

    apps = query.order_by(ScholarshipApplication.submitted_at.desc()).all()

    rows = []
    for a in apps:
        ad = a.application_data or {}
        rows.append({
            'ID':           str(a.id),
            'Applicant':    a.applicant.get_full_name(),
            'Student ID':   _safe(a.applicant.student_id),
            'Email':        a.applicant.email,
            'Course':       _safe(ad.get('course') or a.applicant.course),
            'Year':         _safe(ad.get('year_level') or a.applicant.year_level),
            'GPA':          _safe(ad.get('gpa')),
            'Scholarship':  a.scholarship.title,
            'Status':       a.status.value.replace('_', ' ').title(),
            'Scholar Status': _safe(a.scholar_status).replace('_', ' ').title(),
            'Submitted':    a.submitted_at.strftime('%Y-%m-%d'),
            'Reviewed':     a.reviewed_at.strftime('%Y-%m-%d') if a.reviewed_at else '—',
            'Notes':        _safe(a.review_notes),
        })
    return rows


def _build_scholarships_data(filters=None):
    from app.models import Scholarship, ScholarshipApplication
    from app.models.scholarship import ScholarshipStatus, ApplicationStatus

    scholarships = Scholarship.query.order_by(
        Scholarship.application_deadline.asc()).all()

    rows = []
    for s in scholarships:
        apps = ScholarshipApplication.query.filter_by(scholarship_id=s.id).all()
        rows.append({
            'ID':            str(s.id),
            'Title':         s.title,
            'Award (₱)':     f'{float(s.award_amount):,.2f}' if s.award_amount else '—',
            'Max Slots':     _safe(s.max_applicants),
            'Applicants':    str(s.current_applicants or 0),
            'Approved':      str(sum(1 for a in apps if a.status == ApplicationStatus.APPROVED)),
            'Pending':       str(sum(1 for a in apps if a.status == ApplicationStatus.PENDING)),
            'Rejected':      str(sum(1 for a in apps if a.status == ApplicationStatus.REJECTED)),
            'Deadline':      s.application_deadline.strftime('%Y-%m-%d') if s.application_deadline else '—',
            'Status':        s.status.value.title(),
        })
    return rows


def _build_students_data(filters=None):
    from app.models import User, ScholarshipApplication
    from app.models.scholarship import ApplicationStatus

    query = User.query.filter_by(user_type='student')
    if filters:
        course = filters.get('course')
        if course:
            query = query.filter(User.course.ilike(f'%{course}%'))

    students = query.order_by(User.last_name.asc()).all()

    rows = []
    for s in students:
        apps = s.applications or []
        approved = sum(1 for a in apps if a.status == ApplicationStatus.APPROVED)
        rows.append({
            'Name':          s.get_full_name(),
            'Username':      s.username,
            'Student ID':    _safe(s.student_id),
            'Email':         s.email,
            'Phone':         _safe(s.phone_number),
            'Course':        _safe(s.course),
            'Year Level':    _safe(s.year_level),
            'Applications':  str(len(apps)),
            'Approved':      str(approved),
            'Active':        'Yes' if s.is_active else 'No',
            'Verified':      'Yes' if s.is_verified else 'No',
            'Registered':    s.created_at.strftime('%Y-%m-%d'),
        })
    return rows


def _build_approved_data(filters=None):
    from app.models import ScholarshipApplication
    from app.models.scholarship import ApplicationStatus

    apps = ScholarshipApplication.query.filter_by(
        status=ApplicationStatus.APPROVED
    ).order_by(ScholarshipApplication.final_decision_date.desc()).all()

    rows = []
    for a in apps:
        ad = a.application_data or {}
        rows.append({
            'Scholar':       a.applicant.get_full_name(),
            'Student ID':    _safe(a.applicant.student_id),
            'Email':         a.applicant.email,
            'Course':        _safe(ad.get('course') or a.applicant.course),
            'Year':          _safe(ad.get('year_level') or a.applicant.year_level),
            'GPA':           _safe(ad.get('gpa')),
            'Scholarship':   a.scholarship.title,
            'Award (₱)':     f'{float(a.scholarship.award_amount):,.2f}' if a.scholarship.award_amount else '—',
            'Scholar Status': _safe(a.scholar_status).replace('_', ' ').title(),
            'Approved On':   a.final_decision_date.strftime('%Y-%m-%d') if a.final_decision_date else '—',
            'Reviewer Notes':_safe(a.review_notes),
        })
    return rows


DATA_BUILDERS = {
    'applications': _build_applications_data,
    'scholarships': _build_scholarships_data,
    'students':     _build_students_data,
    'approved':     _build_approved_data,
}


# ─────────────────────────────────────────────────────────────────────────────
# PDF
# ─────────────────────────────────────────────────────────────────────────────

def export_pdf(report_type, filters=None):
    """Return a BytesIO containing a styled PDF report."""
    rows = DATA_BUILDERS[report_type](filters)
    title = REPORT_TITLES[report_type]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=2 * cm,    bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Title'],
        fontSize=16,
        textColor=LSPU_BLUE,
        spaceAfter=4,
        alignment=TA_CENTER,
    )
    sub_style = ParagraphStyle(
        'SubTitle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
        alignment=TA_CENTER,
        spaceAfter=12,
    )
    cell_style = ParagraphStyle(
        'Cell',
        parent=styles['Normal'],
        fontSize=7.5,
        leading=10,
    )

    story = []

    # Header
    story.append(Paragraph('LSPU ScholarHub', title_style))
    story.append(Paragraph(title, ParagraphStyle(
        'Sub', parent=styles['Normal'], fontSize=12,
        textColor=LSPU_BLUE, alignment=TA_CENTER, spaceAfter=2)))
    story.append(Paragraph(f'Generated: {_now_str()}', sub_style))
    story.append(HRFlowable(width='100%', thickness=1.5,
                             color=LSPU_GOLD, spaceAfter=10))

    if not rows:
        story.append(Paragraph('No data available for this report.',
                                styles['Normal']))
        doc.build(story)
        buf.seek(0)
        return buf

    # Build table
    headers = list(rows[0].keys())
    table_data = [[Paragraph(h, ParagraphStyle(
        'Hdr', parent=styles['Normal'], fontSize=8,
        textColor=colors.white, fontName='Helvetica-Bold',
        alignment=TA_CENTER)) for h in headers]]

    for row in rows:
        table_data.append([
            Paragraph(_safe(row.get(h)), cell_style) for h in headers
        ])

    col_count = len(headers)
    page_w = landscape(A4)[0] - 3 * cm
    col_w = page_w / col_count

    tbl = Table(table_data, colWidths=[col_w] * col_count, repeatRows=1)
    tbl.setStyle(TableStyle([
        # Header row
        ('BACKGROUND',  (0, 0), (-1, 0),  LSPU_BLUE),
        ('TEXTCOLOR',   (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, 0),  8),
        ('ALIGN',       (0, 0), (-1, 0),  'CENTER'),
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',  (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',(0,0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',(0, 0), (-1, -1), 4),
        # Alternating rows
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LSPU_LIGHT]),
        # Grid
        ('GRID',        (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
        ('LINEBELOW',   (0, 0), (-1, 0),  1.5, LSPU_GOLD),
    ]))

    story.append(tbl)

    # Footer summary
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        f'Total records: {len(rows)}',
        ParagraphStyle('Footer', parent=styles['Normal'],
                       fontSize=8, textColor=colors.grey)))

    doc.build(story)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────────────────────────────────
# Excel (XLSX)
# ─────────────────────────────────────────────────────────────────────────────

def export_excel(report_type, filters=None):
    """Return a BytesIO containing a styled .xlsx workbook."""
    rows = DATA_BUILDERS[report_type](filters)
    title = REPORT_TITLES[report_type]

    wb = Workbook()
    ws = wb.active
    ws.title = report_type.title()

    # Colour palette
    hdr_fill  = PatternFill('solid', fgColor='1a3a6b')
    alt_fill  = PatternFill('solid', fgColor='e8f0fe')
    gold_fill = PatternFill('solid', fgColor='f5a623')
    thin_border = Border(
        left=Side(style='thin', color='cccccc'),
        right=Side(style='thin', color='cccccc'),
        top=Side(style='thin', color='cccccc'),
        bottom=Side(style='thin', color='cccccc'),
    )

    # ── Title rows ──
    ws.merge_cells('A1:Z1')
    ws['A1'] = 'LSPU ScholarHub'
    ws['A1'].font      = Font(name='Calibri', bold=True, size=16, color='1a3a6b')
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 28

    ws.merge_cells('A2:Z2')
    ws['A2'] = title
    ws['A2'].font      = Font(name='Calibri', bold=True, size=13, color='1a3a6b')
    ws['A2'].alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[2].height = 22

    ws.merge_cells('A3:Z3')
    ws['A3'] = f'Generated: {_now_str()}'
    ws['A3'].font      = Font(name='Calibri', italic=True, size=9, color='888888')
    ws['A3'].alignment = Alignment(horizontal='center')
    ws.row_dimensions[3].height = 16

    # Gold separator row
    ws.row_dimensions[4].height = 4
    for col in range(1, 30):
        ws.cell(row=4, column=col).fill = gold_fill

    if not rows:
        ws['A5'] = 'No data available.'
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    headers = list(rows[0].keys())

    # ── Header row ──
    HDR_ROW = 5
    for ci, h in enumerate(headers, start=1):
        cell = ws.cell(row=HDR_ROW, column=ci, value=h)
        cell.font      = Font(name='Calibri', bold=True, size=10, color='FFFFFF')
        cell.fill      = hdr_fill
        cell.alignment = Alignment(horizontal='center', vertical='center',
                                   wrap_text=True)
        cell.border    = thin_border
    ws.row_dimensions[HDR_ROW].height = 20

    # ── Data rows ──
    for ri, row in enumerate(rows, start=HDR_ROW + 1):
        fill = alt_fill if ri % 2 == 0 else PatternFill('solid', fgColor='FFFFFF')
        for ci, h in enumerate(headers, start=1):
            cell = ws.cell(row=ri, column=ci, value=_safe(row.get(h)))
            cell.font      = Font(name='Calibri', size=9)
            cell.fill      = fill
            cell.alignment = Alignment(vertical='center', wrap_text=True)
            cell.border    = thin_border
        ws.row_dimensions[ri].height = 16

    # ── Auto column width ──
    for ci, h in enumerate(headers, start=1):
        col_letter = get_column_letter(ci)
        max_len = max(
            len(h),
            max((len(_safe(r.get(h))) for r in rows), default=0)
        )
        ws.column_dimensions[col_letter].width = min(max_len + 4, 40)

    # Freeze header
    ws.freeze_panes = ws.cell(row=HDR_ROW + 1, column=1)

    # ── Summary sheet ──
    ws2 = wb.create_sheet('Summary')
    ws2['A1'] = 'Report Summary'
    ws2['A1'].font = Font(bold=True, size=12, color='1a3a6b')
    ws2['A2'] = f'Report Type: {title}'
    ws2['A3'] = f'Total Records: {len(rows)}'
    ws2['A4'] = f'Generated: {_now_str()}'

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────────────────────────────────
# CSV
# ─────────────────────────────────────────────────────────────────────────────

def export_csv(report_type, filters=None):
    """Return a BytesIO containing a UTF-8 CSV."""
    rows = DATA_BUILDERS[report_type](filters)

    buf = io.StringIO()
    if not rows:
        buf.write('No data available.\n')
        out = io.BytesIO(buf.getvalue().encode('utf-8-sig'))
        out.seek(0)
        return out

    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()),
                            lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)

    # utf-8-sig adds BOM so Excel opens it correctly
    out = io.BytesIO(buf.getvalue().encode('utf-8-sig'))
    out.seek(0)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# DOCX
# ─────────────────────────────────────────────────────────────────────────────

def export_docx(report_type, filters=None):
    """Return a BytesIO containing a styled .docx report."""
    rows = DATA_BUILDERS[report_type](filters)
    title = REPORT_TITLES[report_type]

    doc = DocxDocument()

    # Page margins
    for section in doc.sections:
        section.top_margin    = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin   = Cm(2)
        section.right_margin  = Cm(2)

    # ── Header ──
    h1 = doc.add_heading('LSPU ScholarHub', level=1)
    h1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    h1.runs[0].font.color.rgb = RGBColor(0x1a, 0x3a, 0x6b)

    h2 = doc.add_heading(title, level=2)
    h2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    h2.runs[0].font.color.rgb = RGBColor(0x1a, 0x3a, 0x6b)

    meta = doc.add_paragraph(f'Generated: {_now_str()}')
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.runs[0].font.size = Pt(9)
    meta.runs[0].font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    doc.add_paragraph()  # spacer

    if not rows:
        doc.add_paragraph('No data available for this report.')
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf

    headers = list(rows[0].keys())

    # ── Table ──
    tbl = doc.add_table(rows=1, cols=len(headers))
    tbl.style = 'Table Grid'
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Header row
    hdr_cells = tbl.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = h
        run = hdr_cells[i].paragraphs[0].runs[0]
        run.font.bold  = True
        run.font.size  = Pt(8)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        # Blue background via XML shading
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        tc = hdr_cells[i]._tc
        tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), '1a3a6b')
        tcPr.append(shd)

    # Data rows
    for ri, row in enumerate(rows):
        cells = tbl.add_row().cells
        fill_color = 'e8f0fe' if ri % 2 == 0 else 'FFFFFF'
        for ci, h in enumerate(headers):
            cells[ci].text = _safe(row.get(h))
            run = cells[ci].paragraphs[0].runs[0]
            run.font.size = Pt(8)
            from docx.oxml.ns import qn
            from docx.oxml import OxmlElement
            tc = cells[ci]._tc
            tcPr = tc.get_or_add_tcPr()
            shd = OxmlElement('w:shd')
            shd.set(qn('w:val'), 'clear')
            shd.set(qn('w:color'), 'auto')
            shd.set(qn('w:fill'), fill_color)
            tcPr.append(shd)

    # ── Footer ──
    doc.add_paragraph()
    footer_p = doc.add_paragraph(f'Total records: {len(rows)}')
    footer_p.runs[0].font.size = Pt(8)
    footer_p.runs[0].font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────────────────────────────────
# Public dispatcher
# ─────────────────────────────────────────────────────────────────────────────

MIME_TYPES = {
    'pdf':  'application/pdf',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'csv':  'text/csv',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}

EXPORTERS = {
    'pdf':  export_pdf,
    'xlsx': export_excel,
    'csv':  export_csv,
    'docx': export_docx,
}


def generate_export(report_type, fmt, filters=None):
    """
    Main entry point.

    Parameters
    ----------
    report_type : str  – 'applications' | 'scholarships' | 'students' | 'approved'
    fmt         : str  – 'pdf' | 'xlsx' | 'csv' | 'docx'
    filters     : dict – optional query filters

    Returns
    -------
    (BytesIO, mime_type, filename)
    """
    if report_type not in DATA_BUILDERS:
        raise ValueError(f'Unknown report type: {report_type}')
    if fmt not in EXPORTERS:
        raise ValueError(f'Unknown export format: {fmt}')

    buf       = EXPORTERS[fmt](report_type, filters)
    mime      = MIME_TYPES[fmt]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename  = f'lspu_scholarhub_{report_type}_{timestamp}.{fmt}'

    return buf, mime, filename

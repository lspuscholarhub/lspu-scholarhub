"""
OCR / Document Parsing Service — LSPU ScholarHub
=================================================

IMPORTANT SECURITY RULES:
  1. Only PDF files are accepted for registration documents.
     Images (JPG/PNG) cannot be reliably read and allow fake documents to slip through.
  2. When Gemini quota is exceeded AND native PDF extraction cannot find the student ID,
     registration is BLOCKED — not allowed through with a warning.
  3. Documents belonging to an already-registered student are always blocked.

Strategy:
  Pass 1 — pypdf native text extraction (fast, accurate for LSPU digital PDFs)
  Pass 2 — Gemini AI text analysis (fallback when native extraction is incomplete)
           Uses google.genai (new SDK — replaces deprecated google.generativeai)
"""

import re
import io
import os
import json
import base64
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

# Cached working Gemini model name (probed once per process, then reused)
_resolved_ocr_model = None

# ── Constants ─────────────────────────────────────────────────────────────────

NAME_MATCH_THRESHOLD   = 0.80
COURSE_MATCH_THRESHOLD = 0.70   # raised from 0.60 for tighter security

# Common LSPU course name mappings — maps abbreviated/short names to full official names
# Used when the COR prints a shortened version vs the full name selected in the form
COURSE_ALIASES = {
    # Abbreviations → full names (matching new exact course names)
    'bsit':   'bachelor of science in information technology',
    'bscs':   'bachelor of science in computer science',
    'bsce':   'bachelor of science in civil engineering',
    'bsee':   'bachelor of science in electrical engineering',
    'bsme':   'bachelor of science in mechanical engineering',
    'bsece':  'bachelor of science in electronics engineering',
    'bscoe':  'bachelor of science in computer engineering',
    'beed':   'bachelor of elementary education',
    'bsed':   'bachelor of secondary education',
    'bped':   'bachelor of physical education',
    'btvted': 'bachelor of technical-vocational teacher education',
    'btle':   'bachelor of technology and livelihood education',
    'bsa':    'bachelor of science in accountancy',
    'bse':    'bachelor of science in entrepreneurship',
    'bsoa':   'bachelor of science in office administration',
    'bsba':   'bachelor of science in business administration major in financial management',
    'bsmath': 'bachelor of science in mathematics',
    'bsbio':  'bachelor of science in biology',
    'bschem': 'bachelor of science in chemistry',
    'bspsych':'bachelor of science in psychology',
    'bsn':    'bachelor of science in nursing',
    'bshm':   'bachelor of science in hospitality management',
    'bstm':   'bachelor of science in tourism management',
    'bpa':    'bachelor of public administration',
    'bsfm':   'bachelor of science in financial management',
    'ab':     'bachelor of arts in broadcasting',
    'bscje':  'bachelor of science in criminal justice education',
    # Short "BS" forms that appear on CORs
    'bs information technology':           'bachelor of science in information technology',
    'bs computer science':                 'bachelor of science in computer science',
    'bs civil engineering':                'bachelor of science in civil engineering',
    'bs electrical engineering':           'bachelor of science in electrical engineering',
    'bs mechanical engineering':           'bachelor of science in mechanical engineering',
    'bs electronics engineering':          'bachelor of science in electronics engineering',
    'bs computer engineering':             'bachelor of science in computer engineering',
    'bs accountancy':                      'bachelor of science in accountancy',
    'bs entrepreneurship':                 'bachelor of science in entrepreneurship',
    'bs office administration':            'bachelor of science in office administration',
    'bs mathematics':                      'bachelor of science in mathematics',
    'bs biology':                          'bachelor of science in biology',
    'bs chemistry':                        'bachelor of science in chemistry',
    'bs psychology':                       'bachelor of science in psychology',
    'bs nursing':                          'bachelor of science in nursing',
    'bs hospitality management':           'bachelor of science in hospitality management',
    'bs tourism management':               'bachelor of science in tourism management',
    'bs financial management':             'bachelor of science in financial management',
    'bs criminal justice':                 'bachelor of science in criminal justice education',
    'bs criminal justice education':       'bachelor of science in criminal justice education',
    'bs business administration':          'bachelor of science in business administration major in financial management',
    'bs business administration major in marketing': 'bachelor of science in business administration major in marketing',
    'bs business administration major in financial management': 'bachelor of science in business administration major in financial management',
    # Industrial Technology short forms
    'bs industrial technology':                         'bachelor of science in industrial technology',
    'bsit food processing':                             'bachelor of science in industrial technology – food processing',
    'bsit automotive':                                  'bachelor of science in industrial technology – automotive',
    'bsit drafting':                                    'bachelor of science in industrial technology – drafting',
    'bsit electrical':                                  'bachelor of science in industrial technology – electrical',
    'bsit electronics':                                 'bachelor of science in industrial technology – electronics',
    'bsit hvac':                                        'bachelor of science in industrial technology – heating, ventilation, and air conditioning',
    'bsit heating ventilation':                         'bachelor of science in industrial technology – heating, ventilation, and air conditioning',
    # Education short forms
    'bsed english':                        'bachelor of secondary education major in english',
    'bsed filipino':                       'bachelor of secondary education major in filipino',
    'bsed social science':                 'bachelor of secondary education major in social science',
    'bsed mathematics':                    'bachelor of secondary education major in mathematics',
    'bsed math':                           'bachelor of secondary education major in mathematics',
    'bsed science':                        'bachelor of secondary education major in science',
    'bachelor of secondary education major in english':       'bachelor of secondary education major in english',
    'bachelor of secondary education major in filipino':      'bachelor of secondary education major in filipino',
    'bachelor of secondary education major in social science':'bachelor of secondary education major in social science',
    'bachelor of secondary education major in mathematics':   'bachelor of secondary education major in mathematics',
    'bachelor of secondary education major in science':       'bachelor of secondary education major in science',
}
GWA_PATTERN = re.compile(
    r'(?:GWA|General\s+Weighted\s+Average|GENERAL\s+WEIGHTED\s+AVERAGE'
    r'|Weighted\s+Average|WEIGHTED\s+AVERAGE)'
    r'[\s:=]*([1-5]\.\d{1,2})',
    re.IGNORECASE
)
STUDENT_ID_PATTERN = re.compile(r'\b(\d{4}[-\s]?\d{4})\b')

COR_ID_PATTERN   = re.compile(
    r'Student\s+No\.\s*[:\-]?\s*(\d{4}[-\s]?\d{4})', re.IGNORECASE)
COR_NAME_PATTERN = re.compile(
    r'Student\s+Name\s*[:\-]?\s*([A-Za-z][A-Za-z\s,.\-]{3,60}?)(?:\s{2,}|Student\s+No)',
    re.IGNORECASE)

GRADES_ID_PATTERN   = re.compile(
    r'Student\s+ID\s*[:\-]?\s*(\d{4}[-\s]?\d{4})', re.IGNORECASE)
GRADES_NAME_PATTERN = re.compile(
    r'Name\s*[:\-]\s*([A-Za-z][A-Za-z\s,.\-]{3,60}?)(?:\n|Student\s+ID)',
    re.IGNORECASE)


# ── Normalisation helpers ─────────────────────────────────────────────────────

def _normalise_id(raw: str) -> str:
    cleaned = re.sub(r'[\s]+', '-', raw.strip())
    digits  = re.sub(r'\D', '', cleaned)
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:]}"
    return cleaned.upper()


def _normalise_name(raw: str) -> str:
    cleaned = re.sub(r'[,.]', ' ', raw)
    tokens  = [t.lower() for t in cleaned.split() if t]
    return ' '.join(sorted(tokens))


def _name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalise_name(a), _normalise_name(b)).ratio()


def _course_similarity(doc_course: str, form_course: str) -> float:
    """
    Compare course names with abbreviation expansion.
    Returns the highest reliable similarity score.

    Logic:
    - Abbreviation expansion (BSIT → bs information technology) gets full weight
    - Base string similarity is only trusted when keyword similarity also agrees
    - This prevents "BS Civil Engineering" matching "BS Electrical Engineering"
      just because they share the word "Engineering"
    """
    doc_lower  = doc_course.lower().strip()
    form_lower = form_course.lower().strip()

    # Exact match
    if doc_lower == form_lower:
        return 1.0

    # Try expanding abbreviations
    doc_expanded  = COURSE_ALIASES.get(doc_lower, doc_lower)
    form_expanded = COURSE_ALIASES.get(form_lower, form_lower)

    # Similarity after expansion — only use if at least one side was actually abbreviated
    doc_was_expanded  = (doc_expanded  != doc_lower)
    form_was_expanded = (form_expanded != form_lower)

    exp_sim      = SequenceMatcher(None, doc_expanded, form_lower).ratio()  if doc_was_expanded  else 0
    form_exp_sim = SequenceMatcher(None, doc_lower, form_expanded).ratio()  if form_was_expanded else 0
    both_exp_sim = SequenceMatcher(None, doc_expanded, form_expanded).ratio() if (doc_was_expanded or form_was_expanded) else 0

    # Keyword match — only MEANINGFUL words (skip generic words)
    STOP_WORDS = {'bs', 'of', 'in', 'the', 'and', 'bachelor', 'science', 'arts',
                  'technology', 'engineering'}  # 'engineering' alone is not specific enough
    form_words = [w for w in form_lower.split() if len(w) > 3 and w not in STOP_WORDS]
    doc_words  = [w for w in doc_lower.split()  if len(w) > 3 and w not in STOP_WORDS]

    if form_words and doc_words:
        shared = sum(1 for w in form_words if any(w in dw or dw in w for dw in doc_words))
        keyword_sim = shared / max(len(form_words), len(doc_words))
    else:
        keyword_sim = 0

    # Base string similarity — only use it if keyword similarity also agrees
    # This prevents "BS Civil Engineering" ≈ "BS Electrical Engineering" (0.80 base, 0.0 keyword)
    base_sim = SequenceMatcher(None, doc_lower, form_lower).ratio()
    if keyword_sim < 0.5:
        base_sim = base_sim * 0.5   # penalise base sim when keywords don't agree

    return max(base_sim, exp_sim, form_exp_sim, both_exp_sim, keyword_sim)


# ── Pass 1: pypdf native text extraction ─────────────────────────────────────

def _extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract all text from a PDF using pypdf (pure Python)."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        pages  = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return '\n'.join(pages)
    except Exception as e:
        logger.warning(f'pypdf extraction failed: {e}')
        return ''


def _parse_text(text: str, doc_type: str = 'auto') -> dict:
    """Search extracted text for Student ID, Name, GWA, and Course."""
    result = {'student_id': None, 'name': None, 'gwa': None,
              'course': None, 'units_enrolled': None, 'year_level': None,
              'date_of_birth': None, 'place_of_birth': None}

    is_cor    = 'Student No.' in text or 'CERTIFICATE OF REGISTRATION' in text.upper()
    is_grades = 'Student ID:' in text or 'REPORT OF GRADES' in text.upper() or 'GWA:' in text
    result['detected_type'] = 'cor' if is_cor else ('grades' if is_grades else 'unknown')

    # Student ID
    if is_cor:
        m = COR_ID_PATTERN.search(text)
        if m:
            result['student_id'] = _normalise_id(m.group(1))
    elif is_grades:
        m = GRADES_ID_PATTERN.search(text)
        if m:
            result['student_id'] = _normalise_id(m.group(1))
    if not result['student_id']:
        m = STUDENT_ID_PATTERN.search(text)
        if m:
            result['student_id'] = _normalise_id(m.group(1))

    # Student Name
    if is_cor:
        m = COR_NAME_PATTERN.search(text)
        if m:
            result['name'] = m.group(1).strip()
    elif is_grades:
        m = GRADES_NAME_PATTERN.search(text)
        if m:
            result['name'] = m.group(1).strip()
    if not result['name']:
        for pat in [
            r'(?:Student\s+Name|Name of Student)\s*[:\-]?\s*([A-Za-z][A-Za-z\s,.\-]{4,60}?)(?=\s{2,}|\n|\b[A-Z][A-Za-z]+\s*:|$)',
            r'Name\s*[:\-]\s*([A-Za-z][A-Za-z\s,.\-]{4,60}?)(?=\s{2,}|\n|\b[A-Z][A-Za-z]+\s*:|$)',
        ]:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                candidate = m.group(1).strip()
                if len(candidate) >= 5 and 'STUDENT' not in candidate.upper():
                    result['name'] = candidate
                    break

    # GWA
    gwa_exact = re.search(r'\bGWA\s*[:\-]\s*([1-5]\.\d{1,2})', text, re.IGNORECASE)
    if gwa_exact:
        try:
            result['gwa'] = float(gwa_exact.group(1))
        except ValueError:
            pass
    if result['gwa'] is None:
        gwa_long = GWA_PATTERN.search(text)
        if gwa_long:
            try:
                result['gwa'] = float(gwa_long.group(1))
            except ValueError:
                pass

    # Course — try multiple patterns to handle COR and Grades formats
    course_patterns = [
        # COR: "Course : Bachelor of Science in Information Technology   Year Level"
        r'Course\s*[:\-]\s*([A-Za-z][A-Za-z\s]+?)(?:\s{2,}|Year\s+Level|\n|$)',
        # Grades: "Program: Bachelor of Science in Information Technology"
        r'Program\s*[:\-]\s*([A-Za-z][A-Za-z\s]+?)(?:\s{2,}|\n|$)',
        # Abbreviated: "BSIT" or "BS Information Technology" on its own line
        r'\b(BS\s+[A-Za-z][A-Za-z\s]{3,50}|Bachelor\s+of\s+[A-Za-z][A-Za-z\s]{3,50})\b',
    ]
    for pat in course_patterns:
        course_m = re.search(pat, text, re.IGNORECASE)
        if course_m:
            candidate = course_m.group(1).strip()
            # Filter out noise
            if (len(candidate) >= 4
                    and 'STUDENT' not in candidate.upper()
                    and 'YEAR' not in candidate.upper()
                    and 'LEVEL' not in candidate.upper()):
                result['course'] = candidate
                break

    # Units enrolled — native PDFs (Gemini already extracts this for scans)
    units_patterns = [
        r'(?:Total\s+)?Units?\s+Enrolled\s*[:\-]?\s*(\d{1,3})',
        r'Total\s+Units\s*[:\-]?\s*(\d{1,3})',
        r'Units?\s*[:\-]\s*(\d{1,3})',
    ]
    for pat in units_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                val = int(m.group(1))
                if 1 <= val <= 99:   # sane semester load
                    result['units_enrolled'] = val
                    break
            except ValueError:
                pass

    # Year Level — found on CORs (e.g. "Year Level : 2", "Year Level 3",
    # "Course: BSIT   Year Level: 4", or "2nd Year" / "4th Year",
    # or text-based: "Year Level : Fourth Year")
    year_map = {'1': '1st Year', '2': '2nd Year', '3': '3rd Year', '4': '4th Year', '5': '5th Year'}
    year_text_map = {
        'first': '1st Year', 'second': '2nd Year', 'third': '3rd Year',
        'fourth': '4th Year', 'fifth': '5th Year'
    }
    year_patterns = [
        # Text-based: "Year Level : Fourth Year"
        r'Year\s+Level\s*[:\-]?\s*(First|Second|Third|Fourth|Fifth)\s+Year',
        # Numeric: "Year Level : 2"
        r'Year\s+Level\s*[:\-]?\s*(\d)',
        r'Year\s*[:\-]\s*(\d)',
        r'Yr\.?\s*Level\s*[:\-]?\s*(\d)',
        r'Grade\s+Year\s*[:\-]?\s*(\d)',
        r'\b(\d)(?:st|nd|rd|th)\s+Year\b',
    ]
    for pat in year_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            value = m.group(1)
            if value.isdigit():
                if value in year_map:
                    result['year_level'] = year_map[value]
            elif value.lower() in year_text_map:
                result['year_level'] = year_text_map[value.lower()]
            break

    # Date of Birth — found on Report of Grades (e.g. "Date of Birth: 10/16/2004")
    dob_patterns = [
        r'Date\s+of\s+Birth\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'Birthday\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'Birth\s+Date\s*[:\-]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
    ]
    for pat in dob_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result['date_of_birth'] = m.group(1)
            break

    # Place of Birth — found on Report of Grades
    pob_patterns = [
        r'Place\s+of\s+Birth\s*[:\-]?\s*(.+?)(?:\n|$)',
        r'Birthplace\s*[:\-]?\s*(.+?)(?:\n|$)',
    ]
    for pat in pob_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            result['place_of_birth'] = m.group(1).strip()
            break

    return result


# ── Pass 2: Gemini AI (google.genai — new SDK) ────────────────────────────────

# ── Pass 2: Gemini AI Vision (google.genai — new SDK) ─────────────────────────

GEMINI_INSTRUCTION = (
    'This is an official document from Laguna State Polytechnic University (LSPU), '
    'Santa Cruz Campus, Philippines. It may be a PDF, a screenshot, or a photo of the document.\n\n'
    'DOCUMENT TYPE 1 — CERTIFICATE OF REGISTRATION (COR):\n'
    '  Layout: Student Name : [name]   Student No. : [XXXX-XXXX]\n'
    '          Course : [full program name]   Year Level : [year]\n\n'
    'DOCUMENT TYPE 2 — REPORT OF GRADES:\n'
    '  Layout: Name: [name]\n'
    '          Student ID: [XXXX-XXXX]\n'
    '          Course: [full program name]\n'
    '          Date of Birth: [MM/DD/YYYY]\n'
    '          Place of Birth: [city/municipality]\n'
    '          GWA: [number]\n'
    '          Total Units / Units Enrolled: [number]\n\n'
    'Extract ALL values you can find. The course/program is REQUIRED.\n'
    'Also extract the academic year and semester if visible '
    '(e.g. "Second Semester AY 2025-2026").\n\n'
    'Return ONLY valid JSON:\n'
    '{\n'
    '  "student_id": "XXXX-XXXX format or null",\n'
    '  "name": "Full student name exactly as printed or null",\n'
    '  "gwa": 2.00 or null,\n'
    '  "units_enrolled": 21 or null,\n'
    '  "course": "Full course/program name or null",\n'
    '  "year_level": "e.g. 4th Year or null",\n'
    '  "date_of_birth": "MM/DD/YYYY format or null",\n'
    '  "place_of_birth": "city/municipality or null",\n'
    '  "semester": "e.g. 2nd Semester or null",\n'
    '  "academic_year": "e.g. 2025-2026 or null"\n'
    '}\n'
    'No explanation. JSON only.'
)


def _extract_via_gemini(file_bytes: bytes, file_ext: str, raw_text: str = '') -> dict:
    """
    Use Gemini to extract Student ID, Name, GWA, Course from documents.
    Supports:
      - PDF: sends extracted text as a text prompt
      - Images (JPG/PNG): sends the image directly for vision analysis (like Google Lens)

    Uses the new google.genai SDK.
    """
    result = {'student_id': None, 'name': None, 'gwa': None, 'course': None,
              'semester': None, 'academic_year': None}

    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not api_key:
        logger.warning('GEMINI_API_KEY not set — skipping Gemini OCR.')
        return result

    try:
        from google import genai
        from google.genai import types
        import time

        client = genai.Client(api_key=api_key)

        # Use model name from env; if unset/retired, probe known-good candidates.
        # gemini-1.5-flash was RETIRED by Google (404s) — the old hardcoded default
        # silently killed the AI fallback. gemini-flash-latest always tracks the
        # current stable Flash model.
        global _resolved_ocr_model
        _ocr_model = os.environ.get('GEMINI_MODEL', '').strip()
        if not _ocr_model or 'gemini-1.5' in _ocr_model:
            if _resolved_ocr_model:
                _ocr_model = _resolved_ocr_model   # cached from a previous call
            else:
                _ocr_model = None
                for candidate in ('gemini-flash-latest', 'gemini-2.5-flash-lite',
                                  'gemini-2.0-flash'):
                    try:
                        test = client.models.generate_content(model=candidate, contents='hi')
                        if test.text:
                            _ocr_model = candidate
                            break
                    except Exception:
                        continue
                if not _ocr_model:
                    _ocr_model = 'gemini-flash-latest'  # last resort — will raise below
                _resolved_ocr_model = _ocr_model
            logger.info(f'Gemini OCR using model: {_ocr_model}')

        # Retry logic: if we get a 429 with a short retry delay, wait and try once more
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                if file_ext in ('jpg', 'jpeg', 'png'):
                    mime_type = 'image/jpeg' if file_ext in ('jpg', 'jpeg') else 'image/png'
                    response = client.models.generate_content(
                        model=_ocr_model,
                        contents=[
                            GEMINI_INSTRUCTION,
                            types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                        ],
                    )
                else:
                    context = raw_text[:5000] if raw_text else 'No text could be extracted.'
                    full_prompt = (
                        f"The following is text extracted from an official LSPU document:\n\n"
                        f"{context}\n\n"
                        f"{GEMINI_INSTRUCTION}"
                    )
                    response = client.models.generate_content(
                        model=_ocr_model,
                        contents=full_prompt,
                    )
                break  # success — exit retry loop

            except Exception as retry_err:
                err_msg = str(retry_err)
                if '429' in err_msg and attempt < max_attempts - 1:
                    # Check if the error suggests a short retry (under 30s)
                    import re as _re
                    delay_match = _re.search(r'retry.*?(\d+)', err_msg.lower())
                    wait_time = int(delay_match.group(1)) if delay_match else 21
                    if wait_time <= 30:
                        logger.info(f'Gemini rate limited. Waiting {wait_time}s before retry...')
                        time.sleep(wait_time)
                        continue
                raise  # re-raise if not retryable or max attempts reached

        raw = response.text.strip()
        start = raw.find('{')
        end   = raw.rfind('}') + 1
        if start != -1 and end > start:
            data = json.loads(raw[start:end])
            sid = data.get('student_id')
            if sid and str(sid).lower() != 'null':
                result['student_id'] = _normalise_id(str(sid))
            name = data.get('name')
            if name and str(name).lower() != 'null':
                result['name'] = str(name).strip()
            gwa = data.get('gwa')
            if gwa and str(gwa).lower() != 'null':
                try:
                    result['gwa'] = float(gwa)
                except (ValueError, TypeError):
                    pass
            course = data.get('course')
            if course and str(course).lower() != 'null':
                result['course'] = str(course).strip()
            semester = data.get('semester')
            if semester and str(semester).lower() != 'null':
                result['semester'] = str(semester).strip()
            academic_year = data.get('academic_year')
            if academic_year and str(academic_year).lower() != 'null':
                result['academic_year'] = str(academic_year).strip()
            units = data.get('units_enrolled')
            if units and str(units).lower() != 'null':
                try:
                    result['units_enrolled'] = int(float(units))
                except (ValueError, TypeError):
                    pass

    except Exception as e:
        logger.warning(f'Gemini OCR failed: {e}')
        err_str = str(e).lower()
        if '429' in str(e) or 'quota' in err_str or 'rate' in err_str:
            raise   # propagate quota errors upward

    return result


# ── Main extraction function ──────────────────────────────────────────────────

def extract_document_data(file_bytes: bytes, file_ext: str) -> dict:
    """
    Extract Student ID, Name, GWA, Course from a document.
    Supports:
      - PDF: native text extraction first, then Gemini fallback
      - Images (JPG/PNG): sent directly to Gemini Vision (like Google Lens)
        Works with screenshots, photos of documents, scanned images.

    Returns dict with keys: student_id, name, gwa, units_enrolled, course, raw_text, method, semester, academic_year, date_of_birth, place_of_birth
    """
    result = {
        'student_id':    None,
        'name':          None,
        'gwa':           None,
        'units_enrolled': None,
        'course':        None,
        'year_level':    None,
        'raw_text':      '',
        'method':        'failed',
        'semester':      None,
        'academic_year': None,
        'date_of_birth': None,
        'place_of_birth': None,
    }

    allowed_exts = ('pdf', 'jpg', 'jpeg', 'png')
    if file_ext not in allowed_exts:
        logger.warning(f'Unsupported file type "{file_ext}".')
        result['method'] = 'rejected_unsupported'
        return result

    # ── For images: go straight to Gemini Vision ──────────────────────────────
    if file_ext in ('jpg', 'jpeg', 'png'):
        logger.info(f'Running Gemini Vision analysis for .{file_ext} image.')
        try:
            gemini = _extract_via_gemini(file_bytes, file_ext)
            for key in ('student_id', 'name', 'gwa', 'units_enrolled', 'course', 'year_level', 'semester', 'academic_year', 'date_of_birth', 'place_of_birth'):
                if gemini.get(key):
                    result[key] = gemini[key]
            result['method'] = (
                'gemini_vision' if (result['student_id'] or result['name']) else 'failed'
            )
        except Exception as e:
            logger.warning(f'Gemini Vision unavailable: {e}')
            result['method'] = 'quota_exceeded'
        return result

    # ── For PDFs: native extraction first, then Gemini fallback ───────────────
    raw_text = _extract_text_from_pdf(file_bytes)
    result['raw_text'] = raw_text

    if raw_text.strip():
        parsed = _parse_text(raw_text)
        result.update(parsed)
        result['method'] = 'pdf_native'

        if result['student_id'] and result['name']:
            logger.info('Document parsed via native PDF text.')
            return result

    # Gemini fallback for PDFs
    logger.info(f'Running Gemini analysis for .{file_ext} document.')
    try:
        gemini = _extract_via_gemini(file_bytes, file_ext, raw_text)
        for key in ('student_id', 'name', 'gwa', 'units_enrolled', 'course', 'year_level', 'semester', 'academic_year', 'date_of_birth', 'place_of_birth'):
            if gemini.get(key):
                result[key] = gemini[key]
        result['method'] = (
            'gemini' if (result['student_id'] or result['name']) else 'failed'
        )
    except Exception as e:
        logger.warning(f'Gemini unavailable: {e}')
        result['method'] = 'quota_exceeded'

    return result


# ── Triple-match verification ─────────────────────────────────────────────────

def verify_documents(
    form_student_id: str,
    form_first_name: str,
    form_last_name:  str,
    cor_bytes:       bytes,
    cor_ext:         str,
    grades_bytes:    bytes | None = None,
    grades_ext:      str  | None = None,
    form_course:     str  | None = None,
    form_middle_name: str | None = None,
) -> dict:
    """
    Run the triple-match gatekeeper.

    SECURITY POLICY:
    - Unsupported file types → BLOCKED (method = 'rejected_unsupported')
    - Quota exceeded AND no native data found → BLOCKED (method = 'quota_exceeded')
    - Document belongs to existing account → BLOCKED
    - ID/name mismatch → BLOCKED
    - Random/forged PDF with no readable student data → BLOCKED (no hard data = no proof)
    - Readable ID+name but course not found → WARNING only (staff review)
    """
    errors   = []
    warnings = []
    # Build name variants — the document may show either "First Last" or "First Middle Last"
    form_name_short = f"{form_first_name} {form_last_name}".strip()
    if form_middle_name:
        form_name_full = f"{form_first_name} {form_middle_name} {form_last_name}".strip()
    else:
        form_name_full = form_name_short
    # Use the longer variant as primary; fall back to shorter if it matches better
    form_name = form_name_full

    def _best_name_sim(doc_name: str) -> float:
        """Return the best similarity score across all name variants."""
        s1 = _name_similarity(form_name_full, doc_name)
        s2 = _name_similarity(form_name_short, doc_name)
        return max(s1, s2)

    norm_form_id = _normalise_id(form_student_id)

    # ── Extract COR ───────────────────────────────────────────────────────────
    logger.info('Extracting data from COR…')
    cor_data = extract_document_data(cor_bytes, cor_ext)

    # Hard block: wrong document type uploaded as COR
    if cor_data.get('detected_type') == 'grades':
        errors.append(
            'The file uploaded as your Certificate of Registration appears to be '
            'a Copy of Grades instead. Please download your COR PDF from the '
            'LSPU student portal and upload it here.'
        )
        return {'passed': False, 'errors': errors, 'warnings': warnings,
                'cor_data': cor_data, 'grades_data': None, 'gwa': None}

    # Hard block: unsupported file type
    if cor_data['method'] == 'rejected_unsupported':
        errors.append(
            'Your Certificate of Registration (COR) must be a PDF file. '
            'Please upload your official COR PDF from the LSPU portal.'
        )
        return {'passed': False, 'errors': errors, 'warnings': warnings,
                'cor_data': cor_data, 'grades_data': None, 'gwa': None}

    # Hard block: readable PDF but NO student data at all — nothing proves ownership.
    # This rejects random PDFs (e.g. any document renamed to .pdf) at registration time.
    # Checked BEFORE the quota/failed blocks so the user gets the accurate reason.
    if not cor_data['student_id'] and not cor_data['name']:
        errors.append(
            'Your Certificate of Registration (COR) could not be verified — '
            'no Student ID or name was found in the document. '
            'Please upload the official digital COR PDF from the LSPU portal. '
            'Photos or printouts saved as PDF cannot be verified.'
        )
        return {'passed': False, 'errors': errors, 'warnings': warnings,
                'cor_data': cor_data, 'grades_data': None, 'gwa': None}

    # Hard block: Gemini quota exceeded AND no native data — cannot verify
    if cor_data['method'] == 'quota_exceeded' and not cor_data['student_id']:
        errors.append(
            'Document verification is temporarily unavailable (AI service quota exceeded). '
            'This usually resets within a few minutes. Please try again shortly. '
            'If this persists, try uploading a PDF version of your document instead of an image — '
            'PDFs can be verified without the AI service.'
        )
        return {'passed': False, 'errors': errors, 'warnings': warnings,
                'cor_data': cor_data, 'grades_data': None, 'gwa': None}

    # Hard block: completely failed to read the document
    if cor_data['method'] == 'failed' and not cor_data['student_id']:
        errors.append(
            'Your Certificate of Registration (COR) could not be read. '
            'Please make sure you are uploading a valid, text-based PDF from the LSPU portal. '
            'Scanned images saved as PDF may not work — use the original digital PDF.'
        )
        return {'passed': False, 'errors': errors, 'warnings': warnings,
                'cor_data': cor_data, 'grades_data': None, 'gwa': None}

    # Security: check if COR belongs to an already-registered student
    if cor_data['student_id']:
        try:
            from app.models import User
            existing = User.query.filter_by(student_id=cor_data['student_id']).first()
            if existing:
                errors.append(
                    f'The Certificate of Registration (COR) you uploaded belongs to a '
                    f'student who is already registered in the system '
                    f'(Student ID: {cor_data["student_id"]}). '
                    f'You must upload your own official COR. '
                    f'If this is your document, please log in to your existing account.'
                )
                return {'passed': False, 'errors': errors, 'warnings': warnings,
                        'cor_data': cor_data, 'grades_data': None, 'gwa': None}
        except Exception as e:
            logger.warning(f'Could not check existing student ID: {e}')

    # COR: Student ID match
    if cor_data['student_id']:
        if cor_data['student_id'] != norm_form_id:
            errors.append(
                f'Student ID mismatch on your COR: '
                f'the document shows "{cor_data["student_id"]}" '
                f'but you entered "{norm_form_id}". '
                f'Please make sure your Student ID matches your COR exactly.'
            )
    else:
        # ID missing but name was found — still verifiable via name; warn only.
        warnings.append(
            'Could not locate a Student ID on your COR. '
            'Staff will manually verify this document.'
        )

    # COR: Name match
    if cor_data['name']:
        sim = _best_name_sim(cor_data['name'])
        if sim < NAME_MATCH_THRESHOLD:
            errors.append(
                f'Name mismatch on your COR: '
                f'the document shows "{cor_data["name"]}" '
                f'but you entered "{form_name}". '
                f'Please make sure your name matches your COR exactly.'
            )
    else:
        warnings.append(
            'Could not locate your name on the COR. '
            'Staff will manually verify this document.'
        )

    # COR: Course match — required field, hard block on mismatch or missing
    if form_course:
        if cor_data.get('course'):
            course_sim = _course_similarity(cor_data['course'], form_course)
            if course_sim < COURSE_MATCH_THRESHOLD:
                errors.append(
                    f'Course mismatch on your COR: '
                    f'the document shows "{cor_data["course"]}" '
                    f'but you selected "{form_course}". '
                    f'Please make sure your course matches your COR exactly.'
                )
        elif cor_data['student_id'] or cor_data['name']:
            # Document was readable (we got ID/name) but course wasn't found — block
            errors.append(
                f'Your course/program could not be verified from your COR. '
                f'The system could not find "{form_course}" in your document. '
                f'Please make sure you are uploading the correct COR for your course.'
            )

    # ── Extract Copy of Grades (if provided) ─────────────────────────────────
    grades_data   = None
    extracted_gwa = None

    if grades_bytes and grades_ext:
        logger.info('Extracting data from Copy of Grades…')
        grades_data = extract_document_data(grades_bytes, grades_ext)

        # Hard block: wrong document type uploaded as Grades
        if grades_data.get('detected_type') == 'cor':
            errors.append(
                'The file uploaded as your Copy of Grades appears to be a '
                'Certificate of Registration instead. Please download your '
                'grades PDF from the LSPU student portal and upload it here.'
            )
            return {'passed': False, 'errors': errors, 'warnings': warnings,
                    'cor_data': cor_data, 'grades_data': grades_data, 'gwa': None}

        # Hard block: unsupported file type
        if grades_data['method'] == 'rejected_unsupported':
            errors.append(
                'Your Copy of Grades must be a PDF file. '
                'Please upload your official grades PDF from the LSPU portal.'
            )
            return {'passed': False, 'errors': errors, 'warnings': warnings,
                    'cor_data': cor_data, 'grades_data': grades_data, 'gwa': None}

        # Hard block: quota exceeded with no data
        if grades_data['method'] == 'quota_exceeded' and not grades_data['student_id']:
            errors.append(
                'Document verification is temporarily unavailable. '
                'Please try again in a few minutes.'
            )
            return {'passed': False, 'errors': errors, 'warnings': warnings,
                    'cor_data': cor_data, 'grades_data': grades_data, 'gwa': None}

        if grades_data['method'] not in ('failed', 'quota_exceeded'):
            # Security: check if grades belong to existing account
            if grades_data['student_id']:
                try:
                    from app.models import User
                    existing = User.query.filter_by(
                        student_id=grades_data['student_id']).first()
                    if existing and grades_data['student_id'] != norm_form_id:
                        errors.append(
                            f'The Copy of Grades you uploaded belongs to a student '
                            f'who is already registered in the system '
                            f'(Student ID: {grades_data["student_id"]}). '
                            f'You must upload your own official grades document.'
                        )
                        return {'passed': False, 'errors': errors, 'warnings': warnings,
                                'cor_data': cor_data, 'grades_data': grades_data, 'gwa': None}
                except Exception as e:
                    logger.warning(f'Could not check grades student ID: {e}')

            # Grades: Student ID match
            if grades_data['student_id']:
                if grades_data['student_id'] != norm_form_id:
                    errors.append(
                        f'Student ID mismatch on your Copy of Grades: '
                        f'the document shows "{grades_data["student_id"]}" '
                        f'but you entered "{norm_form_id}".'
                    )
            else:
                warnings.append(
                    'Could not locate a Student ID on your Copy of Grades. '
                    'Staff will manually verify this document.'
                )

            # Grades: Name match
            if grades_data['name']:
                sim = _best_name_sim(grades_data['name'])
                if sim < NAME_MATCH_THRESHOLD:
                    errors.append(
                        f'Name mismatch on your Copy of Grades: '
                        f'the document shows "{grades_data["name"]}" '
                        f'but you entered "{form_name}".'
                    )
            else:
                warnings.append(
                    'Could not locate your name on the Copy of Grades. '
                    'Staff will manually verify this document.'
                )

            # Grades: Course match — required, hard block on mismatch or missing
            if form_course:
                if grades_data.get('course'):
                    course_sim = _course_similarity(grades_data['course'], form_course)
                    if course_sim < COURSE_MATCH_THRESHOLD:
                        errors.append(
                            f'Course mismatch on your Copy of Grades: '
                            f'the document shows "{grades_data["course"]}" '
                            f'but you selected "{form_course}". '
                            f'Please make sure your course matches your grades document.'
                        )
                elif grades_data['student_id'] or grades_data['name']:
                    # Document was readable but course wasn't found — block
                    errors.append(
                        f'Your course/program could not be verified from your Copy of Grades. '
                        f'The system could not find "{form_course}" in your document. '
                        f'Please make sure you are uploading the correct grades document for your course.'
                    )

            # Extract GWA
            extracted_gwa = grades_data.get('gwa')
            if extracted_gwa is None:
                warnings.append(
                    'GWA could not be automatically extracted from your grades document. '
                    'Staff will enter it manually after reviewing your document.'
                )
        else:
            warnings.append(
                'Your Copy of Grades could not be automatically verified. '
                'Staff will review it manually.'
            )

    return {
        'passed':      len(errors) == 0,
        'errors':      errors,
        'warnings':    warnings,
        'cor_data':    cor_data,
        'grades_data': grades_data,
        'gwa':         extracted_gwa,
    }


# ── Document ownership gate (replacement uploads) ────────────────────────────

def verify_document_owner(file_bytes: bytes, file_ext: str,
                          expected_id: str, expected_first: str,
                          expected_last: str, expected_middle: str | None = None) -> dict:
    """
    Ownership gate for document replacement uploads (My Documents).
    Same security policy as registration: the document must be readable and
    must belong to the expected student — random or borrowed documents are
    rejected. Returns {'passed': bool, 'error': str|None, 'data': extract dict}.
    """
    data = extract_document_data(file_bytes, file_ext)

    def _fail(msg):
        return {'passed': False, 'error': msg, 'data': data}

    # Build the expected name variants (same logic as verify_documents)
    form_short = f"{expected_first} {expected_last}".strip()
    if expected_middle:
        form_full = f"{expected_first} {expected_middle} {expected_last}".strip()
    else:
        form_full = form_short

    def _best_name_sim(doc_name: str) -> float:
        return max(_name_similarity(form_full, doc_name),
                   _name_similarity(form_short, doc_name))

    if data['method'] == 'rejected_unsupported':
        return _fail('This document must be a PDF file. '
                     'Download the official PDF from the LSPU student portal.')

    if data['method'] in ('failed', 'quota_exceeded') and not data['student_id'] and not data['name']:
        return _fail('This document could not be verified — no Student ID or name was found. '
                     'Upload the official digital PDF from the LSPU portal '
                     '(photos or printouts saved as PDF cannot be verified). '
                     'If the AI service is busy, please try again in a few minutes.')

    if not data['student_id'] and not data['name']:
        return _fail('This document could not be verified — no Student ID or name was found in it. '
                     'Please upload the official digital PDF from the LSPU portal.')

    norm_expected = _normalise_id(expected_id)

    if data['student_id'] and data['student_id'] != norm_expected:
        return _fail(f'This document belongs to Student ID {data["student_id"]}, '
                     f'but your account is {norm_expected}. '
                     f'Please upload your own official document.')

    if data['name']:
        sim = _best_name_sim(data['name'])
        if sim < NAME_MATCH_THRESHOLD:
            return _fail(f'The name on this document ("{data["name"]}") does not match '
                         f'your account name ("{form_full}"). '
                         f'Please upload your own official document.')

    # ID matched, or name matched with no ID printed — ownership established
    return {'passed': True, 'error': None, 'data': data}


# ── CTC Stamp Detection ───────────────────────────────────────────────────────

def detect_ctc_stamp(file_bytes: bytes, file_ext: str) -> dict:
    """
    Use Gemini Vision to detect if a document has a Certified True Copy (CTC) stamp.

    A CTC stamp is a physical rubber stamp or embossed seal typically containing:
    - The text "CERTIFIED TRUE COPY" or "CERTIFIED CORRECT COPY"
    - An official seal, dry seal, or ink stamp from a registrar/certifying officer
    - A signature from the certifying official

    Returns:
        {
            'detected': True/False/None,   # None = could not determine (AI unavailable)
            'confidence': 'high'/'low'/'unknown',
            'notes': 'Human-readable explanation',
        }
    """
    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not api_key:
        return {'detected': None, 'confidence': 'unknown',
                'notes': 'AI not configured — manual check required.'}

    model_name = os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash').strip()
    # Guard against invalid legacy model names
    if 'preview' in model_name and model_name not in ('gemini-1.5-pro-preview', 'gemini-1.5-flash-preview'):
        model_name = 'gemini-1.5-flash'

    prompt = (
        "Examine this document carefully. It should be an official school document "
        "(Certificate of Registration or Copy of Grades) from a Philippine university.\n\n"
        "Your task: determine if this document has a CERTIFIED TRUE COPY (CTC) mark.\n\n"
        "A CTC mark may appear as:\n"
        "- A rubber stamp saying 'CERTIFIED TRUE COPY' or 'CERTIFIED CORRECT COPY'\n"
        "- An embossed dry seal from the university registrar\n"
        "- Official ink stamp with signature of the certifying officer\n"
        "- Any text or mark indicating official certification\n\n"
        "Look at ALL parts of the document including corners and margins.\n\n"
        "Respond with ONLY valid JSON:\n"
        "{\n"
        '  "ctc_found": true or false,\n'
        '  "confidence": "high" or "low",\n'
        '  "evidence": "Brief description of what you found (e.g. rubber stamp in bottom-right corner) or null"\n'
        "}\n"
        "No other text. JSON only."
    )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        if file_ext in ('jpg', 'jpeg', 'png'):
            mime = 'image/jpeg' if file_ext in ('jpg', 'jpeg') else 'image/png'
            contents = [prompt, types.Part.from_bytes(data=file_bytes, mime_type=mime)]
        else:
            # For PDFs, convert first page to text and ask Gemini to look for CTC indicators
            raw_text = _extract_text_from_pdf(file_bytes)
            ctc_indicators = ['certified true copy', 'certified correct copy', 'ctc',
                              'certify', 'certified', 'registrar', 'true copy']
            text_lower = raw_text.lower()
            has_text_indicator = any(ind in text_lower for ind in ctc_indicators)
            if has_text_indicator:
                return {
                    'detected': True,
                    'confidence': 'high',
                    'notes': 'CTC text found in document content.'
                }
            # Send to Gemini with the extracted text
            contents = [
                f"The following text was extracted from a PDF document:\n\n{raw_text[:4000]}\n\n{prompt}"
            ]

        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=200)
        )

        raw = response.text.strip()
        start = raw.find('{')
        end   = raw.rfind('}') + 1
        if start != -1 and end > start:
            data = json.loads(raw[start:end])
            ctc_found  = data.get('ctc_found', False)
            confidence = data.get('confidence', 'low')
            evidence   = data.get('evidence') or ''
            return {
                'detected':   bool(ctc_found),
                'confidence': confidence,
                'notes':      evidence if evidence else ('CTC detected.' if ctc_found else 'No CTC stamp detected.'),
            }

    except Exception as e:
        logger.warning(f'CTC detection failed: {e}')

    return {
        'detected':   None,
        'confidence': 'unknown',
        'notes':      'CTC detection unavailable — manual check required.',
    }

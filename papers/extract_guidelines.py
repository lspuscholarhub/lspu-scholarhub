"""One-shot: extract text from the scanned TES/TDP guideline PDFs via Gemini.

Gemini natively reads PDFs (including scanned ones) — send the whole file
in one call. Free-tier quota is PER MODEL, so if the main model is exhausted
we fall through the same candidates the OCR service uses.
Usage:  python papers/extract_guidelines.py [tes|tdp|all]
"""
import io
import os
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_KEY = os.environ.get('GEMINI_API_KEY', '').strip()
if not API_KEY:
    for line in open('.env', encoding='utf-8'):
        if line.startswith('GEMINI_API_KEY='):
            API_KEY = line.split('=', 1)[1].strip()
            break
if not API_KEY:
    print('FATAL: no GEMINI_API_KEY')
    sys.exit(1)

from google import genai
from google.genai import types

client = genai.Client(api_key=API_KEY)

MODELS = ['gemini-3.5-flash-lite', 'gemini-3.5-flash', 'gemini-2.0-flash']

DOWNLOADS = r'C:/Users/kirit/Downloads'
PROJECT = os.path.dirname(os.path.abspath(__file__))

JOBS = {
    'tes': ('2026 Revised TES Guidelines.pdf', 'tes_guidelines_text.txt'),
    'tdp': ('2026 Revised TDP Guidelines (1).pdf', 'tdp_guidelines_text.txt'),
}

PROMPT = ('This is an official scholarship guideline document. Transcribe ALL of its text '
          'exactly as written, preserving headings, numbered sections, lists and tables. '
          'Plain text output only, no commentary.')

which = sys.argv[1].lower() if len(sys.argv) > 1 else 'all'
targets = list(JOBS) if which == 'all' else [which]

for key in targets:
    pdf_name, out_name = JOBS[key]
    pdf_path = os.path.join(DOWNLOADS, pdf_name)
    out_path = os.path.join(PROJECT, out_name)
    pdf_bytes = open(pdf_path, 'rb').read()
    print(f'=== {pdf_name}: {len(pdf_bytes)/1024:.0f} KB ===', flush=True)

    text = ''
    for model in MODELS:
        try:
            t0 = time.time()
            resp = client.models.generate_content(
                model=model,
                contents=[PROMPT, types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf')])
            text = resp.text or ''
            print(f'  {model}: {len(text)} chars in {time.time()-t0:.0f}s', flush=True)
            if text.strip():
                break
        except Exception as e:
            msg = str(e)[:100].replace('\n', ' ')
            print(f'  {model} failed: {msg}', flush=True)
            time.sleep(2)

    open(out_path, 'w', encoding='utf-8').write(text)
    print(f'  saved {out_path}: {len(text)} chars\n', flush=True)

print('DONE')

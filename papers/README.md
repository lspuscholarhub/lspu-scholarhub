# LSPU ScholarHub — Thesis Documentation Papers

This folder contains the technical documentation papers for the LSPU ScholarHub
capstone/thesis project. Each paper is written to be adapted directly into
thesis chapters (Chapter 1–3 material, system design, and appendices).

| # | Document | Contents | Typical Thesis Use |
|---|----------|----------|--------------------|
| 1 | [TECH_STACK.md](TECH_STACK.md) | Complete technology stack: languages, frameworks, libraries (with exact versions), cloud services, and justification for each choice | Chapter 3 — Methodology / Software & Hardware Requirements |
| 2 | [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | Three-tier architecture, MVC structure, module map, request/data flow, security layers, deployment topology | Chapter 3 — System Design / Architectural Design |
| 3 | [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) | All 12 entities, their fields, relationships, and the multi-campus scoping design | Chapter 3 — Database Design / Appendix — ERD narrative |
| 4 | [FUNCTIONALITIES.md](FUNCTIONALITIES.md) | Full feature inventory per role (Super Admin, Admin, Staff, Student, Guest) and the end-to-end workflow | Chapter 1 — Objectives & Scope / Chapter 2 — Related systems comparison |

## Thesis-Submission DOCX

Run to build **`LSPU_ScholarHub_Thesis_Documentation.docx`** from the four
papers above (Times New Roman 12, 1.5 spacing, 1.5" binding margin, title
page, auto table of contents, footer page numbers):

```
python papers/generate_thesis_doc.py
```

The script is idempotent — regenerate anytime the papers change.
After opening the DOCX in Word, right-click the table of contents and
choose **Update Field** (or press F9) to populate it.

Related material already in the repository:

- `docs/flowcharts/` — generated flowchart images (end-to-end, student
  application, staff review/batching, monitoring) usable as thesis figures.
- `docs/generate_process_doc.py` — script that builds the process workflow
  DOCX (produces the workflow/flowchart document).
- `database/lspu_scholarhub_dump.sql` — full database dump (schema + seed),
  usable for the appendix and for restoring a demo database.

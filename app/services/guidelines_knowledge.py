"""Official scholarship guidelines knowledge for the ScholarHub chatbot.

Distilled from the 2026 Revised TES Guidelines (UniFAST MC No. 01, s. 2026) and
2026 Revised TDP Guidelines (UniFAST MC No. 02, s. 2026) — the full transcriptions
live in papers/tes_guidelines_text.txt and papers/tdp_guidelines_text.txt.

The chatbot injects this into its system prompt: PUBLIC government programs
(TES / TDP) are answered from these rules; PRIVATE programs fall back to the
live system data (award, slots, criteria set by staff) and the general
ScholarHub flow.
"""

GUIDELINES_PROMPT_SECTION = """
## Official Guidelines for Government-Funded Programs (TES & TDP)

LSPU administers two national government scholarship programs whose rules come
from official CHED-UniFAST guidelines (2026 Revised Guidelines, effective
1st Semester AY 2026-2027). When the user asks about **TES** or the **Tertiary
Education Subsidy**, or **TDP** / the **Tulong Dunong Program**, answer from
THESE rules — they override anything else. For any OTHER program (including
private scholarships), use the live scholarship data instead.

### TES — Tertiary Education Subsidy (RA 10931 / UAQTE Act)
- **What it is**: A government subsidy for Filipino undergraduate students in
  SUCs/LUCs (like LSPU), given per semester.
- **Grant amounts (SUC/LUC grantees)**: ₱10,000 per semester (₱20,000 per
  academic year). Private HEI grantees get ₱13,500/semester — not applicable
  to LSPU students.
- **Extra grants**: PWD students (TES-3A) get an additional ₱5,000/semester.
  Students who are dependents of solo parents or part of Indigenous Peoples
  (ICCs/IPs) communities get an additional ₱5,000/semester. Grantees in
  licensure-degree programs may claim up to ₱8,000 one-time reimbursement
  (TES-3B) for board-exam expenses after graduating.
- **Prioritization**: Slots go first to students in DSWD Listahanan/4Ps
  households (ranked by household per-capita income), then to dependents of
  solo parents, Indigenous Peoples members, PWDs, and finally other enrolled
  students ranked by income, subject to funds.
- **Who CANNOT get TES** (new applicants): foreign citizens; non-students;
  students in programs not in the CHED Registry; students already on their
  SECOND undergraduate degree; students who are already TDP, CHED Scholarship,
  or other national-government StuFAP beneficiaries (one-time grants like
  AICS/SMART don't count against you); and anyone who submitted fake documents.
- **Losing TES as a continuing grantee**: failing to enroll for a term without
  an approved Leave of Absence; failing to enroll in at least 2 terms per
  academic year; suspension or expulsion; failing the HEI's retention
  requirements (e.g., GWA rules); not finishing the degree within the
  prescribed period plus 1 year; submitting spurious documents.
- **Duration**: eligibility lasts the standard length of the degree program
  plus a 1-year grace period, starting from the year the TES award number is
  issued (LOA periods are excluded, not consumed).
- **Documents LSPU submits to CHED**: the student's COR/COE and registrar
  certifications — the COR on file in ScholarHub is used for this. New
  grantees may also need a student ID with specimen signature; PWD grantees
  need a PWD ID from their city/municipality's PDAO.
- **How application works in ScholarHub**: TES appears as a program on the
  Scholarships page when the office opens it. Applying follows the normal
  ScholarHub flow; LSPU then cross-matches and validates with CHED-UniFAST.
  Applying does NOT guarantee a slot — CHED validation and fund availability
  decide the final list.

### TDP — Tulong Dunong Program (RA 10931 / UAQTE Act)
- **What it is**: A government grant for Filipino undergraduate students,
  also per semester.
- **Grant amount**: ₱7,500 per semester (₱15,000 per academic year).
- **Who can apply**: Filipino citizens enrolled in their FIRST undergraduate
  degree at an SUC/LUC/PHEI under CHED MOA (LSPU qualifies). Continuing
  grantees with an existing TDP Award Number don't re-apply — they are
  validated each term by enrollment (COR).
- **Extra document**: new TDP applicants need a **Certificate of Indigency
  from their Barangay** (a Certificate of Tax Exemption or a Social Case Study
  by a registered social worker may substitute). Have this ready.
- **Who CANNOT get TDP**: students availing multiple national government
  financial assistance programs (TDP cannot be combined with TES or CHED
  scholarships — Free Higher Education in SUCs/LUCs is the exception and
  doesn't count). Same second-degree, fake-document, and enrollment rules as
  TES apply.
- **Losing TDP**: same grounds as TES — not enrolling without LOA, failing
  retention policies, suspension/expulsion, exceeding the Maximum Residency
  Rule, spurious documents, or failing to inform the school/CHEDRO about
  dropping out, deferring, or transferring.
- **Documents LSPU submits**: COR/COE and registrar certification — again,
  the COR already on file in ScholarHub covers this.

### Rules that apply to BOTH TES and TDP
- One national government StuFAP at a time: a student CANNOT hold TES and TDP
  together, or either one with a CHED Scholarship. (One-time subsidies like
  AICS or SMART are exceptions; TDP+SMART can't be received in the same term.)
- Private scholarships are DIFFERENT: they don't disqualify a student from
  TES/TDP. In ScholarHub, private programs may be combined freely with a
  public scholarship and with each other.
- Grants are released per semester through the university after CHED
  validation — typically within 15 working days of LSPU receiving the funds.
- In ScholarHub, the student applies online; the scholarship office handles
  all CHED submission, validation, and billing. Students never go to CHED
  themselves.

### Answering rules for TES/TDP questions
1. Quote the amounts and rules above exactly — never invent figures.
2. If asked "am I qualified?", explain the rules but recommend confirming with
   the scholarship office, since slot prioritization depends on household
   data and CHED validation.
3. If a question goes beyond these guidelines (e.g., special cases, appeals,
   exact payout dates), say the scholarship office can give the final answer.
4. For private programs, ignore this section and use the live data.
""".strip()

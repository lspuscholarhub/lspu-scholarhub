"""Generate Data Dictionary for LSPU ScholarHub.

Matches the reference appendices format:
- One table per database entity
- 4 columns: Field | Data Type | Constraints | Description
- Table captions like "Table N. The table below displays the data dictionary of <Entity>."
Schemas mirror app/models/*.py (the actual running system).
"""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
import os

doc = Document()

for section in doc.sections:
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)

style = doc.styles['Normal']
style.font.name = 'Times New Roman'
style.font.size = Pt(12)

TABLE_NUM = 0


def add_title(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(16)
    run.font.name = 'Times New Roman'


def add_dict_table(entity_name, fields):
    """fields: list of (field, data_type, constraints, description)."""
    global TABLE_NUM
    TABLE_NUM += 1

    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = cap.add_run(f'Table {TABLE_NUM}. The table below displays the data dictionary of {entity_name}.')
    run.font.size = Pt(12)
    run.font.name = 'Times New Roman'

    table = doc.add_table(rows=1, cols=4)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    for i, header in enumerate(['Field', 'Data Type', 'Constraints', 'Description']):
        cell = table.rows[0].cells[i]
        cell.text = ''
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(header)
        run.bold = True
        run.font.size = Pt(10)
        run.font.name = 'Times New Roman'

    for field, dtype, constraints, desc in fields:
        row = table.add_row()
        for i, value in enumerate((field, dtype, constraints, desc)):
            p = row.cells[i].paragraphs[0]
            run = p.add_run(value)
            run.font.size = Pt(10)
            run.font.name = 'Times New Roman'
            if i == 0:
                run.bold = True

    for row in table.rows:
        row.cells[0].width = Cm(4.0)
        row.cells[1].width = Cm(3.0)
        row.cells[2].width = Cm(3.5)
        row.cells[3].width = Cm(5.5)

    doc.add_paragraph()


# ═════════════════════════════════════════════════════════════════════════════
add_title('DATA DICTIONARY')
doc.add_paragraph()

# ── 1. Users ─────────────────────────────────────────────────────────────────
add_dict_table('User Information', [
    ('id', 'int', 'Not Null, Primary Key, Auto-Increment', 'Unique identifier for each user account.'),
    ('username', 'varchar(80)', 'Not Null, Unique', 'Unique username used for account identification.'),
    ('email', 'varchar(120)', 'Not Null, Unique', 'Official email address used for login and email notifications.'),
    ('password_hash', 'varchar(255)', 'Not Null', 'Encrypted hash of the user password.'),
    ('first_name', 'varchar(50)', 'Not Null', 'Given name of the user.'),
    ('last_name', 'varchar(50)', 'Not Null', 'Family name of the user.'),
    ('middle_name', 'varchar(50)', 'Null', 'Middle name of the user (optional).'),
    ('phone_number', 'varchar(20)', 'Null', 'Mobile number used for SMS notifications.'),
    ('gender', 'enum(Male, Female)', 'Null', 'Gender of the user used for demographic reports.'),
    ('town', 'varchar(100)', 'Null', 'Town or municipality of residence.'),
    ('province', 'varchar(100)', 'Null', 'Province of residence.'),
    ('date_of_birth', 'date', 'Null', 'Birthday of the student, validated against uploaded documents.'),
    ('address', 'text', 'Null', 'Complete residential address of the user.'),
    ('student_id', 'varchar(30)', 'Unique', 'LSPU student identification number (students only).'),
    ('course', 'varchar(100)', 'Null', 'Degree program the student is enrolled in.'),
    ('year_level', 'varchar(20)', 'Null', 'Current year level (1st Year to 5th Year, Irregular, Graduate).'),
    ('cor_file_path', 'varchar(500)', 'Null', 'File path or URL of the Certificate of Registration (COR).'),
    ('grades_file_path', 'varchar(500)', 'Null', 'File path or URL of the Report of Grades (ROG).'),
    ('cor_cloudinary_id', 'varchar(255)', 'Null', 'Cloudinary public ID of the COR file for secure retrieval and deletion.'),
    ('grades_cloudinary_id', 'varchar(255)', 'Null', 'Cloudinary public ID of the ROG file for secure retrieval and deletion.'),
    ('grades_semester', 'varchar(50)', 'Null', 'Semester the uploaded grades belong to.'),
    ('grades_updated_at', 'datetime', 'Null', 'Date and time the grades were last uploaded or replaced.'),
    ('ocr_verified', 'boolean', 'Null', 'Result of OCR validation: True if passed, False if failed, Null if pending.'),
    ('ocr_result', 'text', 'Null', 'Raw OCR mismatch details when validation fails.'),
    ('gwa', 'float', 'Null', 'General Weighted Average recorded from the uploaded grades.'),
    ('units_enrolled', 'int', 'Null', 'Total academic units enrolled for the current semester.'),
    ('is_existing_scholar', 'boolean', 'Not Null, Default: false', 'Flag indicating the student declared being a scholar of another program at registration.'),
    ('existing_scholarship_name', 'varchar(150)', 'Null', 'Name of the scholarship program the student currently holds.'),
    ('campus_id', 'int', 'Foreign Key (campuses.id)', 'Campus the user belongs to; Null for university-level accounts.'),
    ('user_type', 'enum(student, staff, admin, super_admin)', 'Not Null, Default: student', 'System role that determines access permissions (RBAC).'),
    ('is_active', 'boolean', 'Not Null, Default: true', 'Flag indicating whether the account is currently active.'),
    ('is_verified', 'boolean', 'Not Null, Default: false', 'Flag indicating whether the account has passed document verification.'),
    ('password_reset_token', 'varchar(100)', 'Unique', 'Token used for password reset requests.'),
    ('password_reset_expires', 'datetime', 'Null', 'Expiration time of the password reset token.'),
    ('phone_verified', 'boolean', 'Not Null, Default: false', 'Flag indicating whether the phone number was verified via OTP.'),
    ('phone_otp', 'varchar(10)', 'Null', 'One-time PIN sent for phone verification.'),
    ('phone_otp_expires', 'datetime', 'Null', 'Expiration time of the phone verification OTP.'),
    ('created_at', 'datetime', 'Not Null', 'Date and time the account was created.'),
    ('updated_at', 'datetime', 'Not Null', 'Date and time the profile was last updated.'),
    ('last_login', 'datetime', 'Null', 'Date and time of the most recent login.'),
])

# ── 2. Campuses ──────────────────────────────────────────────────────────────
add_dict_table('Campus Information', [
    ('id', 'int', 'Not Null, Primary Key, Auto-Increment', 'Unique identifier for each campus.'),
    ('name', 'varchar(100)', 'Not Null, Unique', 'Official name of the LSPU campus (e.g., Santa Cruz Campus).'),
    ('short_name', 'varchar(30)', 'Null', 'Abbreviated campus name used in badges and labels.'),
    ('is_active', 'boolean', 'Default: true', 'Flag indicating whether the campus is currently operating in the system.'),
    ('created_at', 'datetime', 'Not Null', 'Date and time the campus record was created.'),
])

# ── 3. User-Campus Assignment ────────────────────────────────────────────────
add_dict_table('User Campus Assignment', [
    ('id', 'int', 'Not Null, Primary Key, Auto-Increment', 'Unique identifier for each assignment record.'),
    ('user_id', 'int', 'Not Null, Foreign Key (users.id)', 'Staff or admin user assigned to a campus.'),
    ('campus_id', 'int', 'Not Null, Foreign Key (campuses.id)', 'Campus assigned to the user. Allows one person to manage multiple campuses.'),
])

# ── 4. Academic Periods ──────────────────────────────────────────────────────
add_dict_table('Academic Period', [
    ('id', 'int', 'Not Null, Primary Key, Auto-Increment', 'Unique identifier for each academic period.'),
    ('academic_year', 'varchar(20)', 'Not Null', 'Academic year covered (e.g., 2026-2027).'),
    ('semester', 'varchar(30)', 'Not Null', 'Semester within the academic year (1st Semester, 2nd Semester, Inter-Semester).'),
    ('is_current', 'boolean', 'Default: false', 'Flag marking the active period used as the default data context.'),
    ('start_date', 'date', 'Null', 'Start date of the academic period.'),
    ('end_date', 'date', 'Null', 'End date of the academic period.'),
    ('me_form_deadline', 'date', 'Null', 'Deadline for scholars to submit their Monitoring and Evaluation form.'),
    ('created_at', 'datetime', 'Not Null', 'Date and time the period record was created.'),
])

# ── 5. Scholarships ──────────────────────────────────────────────────────────
add_dict_table('Scholarship Program', [
    ('id', 'int', 'Not Null, Primary Key, Auto-Increment', 'Unique identifier for each scholarship program.'),
    ('title', 'varchar(200)', 'Not Null', 'Official name of the scholarship program.'),
    ('category', 'varchar(50)', 'Default: General', 'Classification category of the program.'),
    ('scholarship_type', 'enum(Financial Assistance, Merit Scholarship, Grant, Other)', 'Null', 'Type of scholarship being offered.'),
    ('funding_type', 'enum(public, private)', 'Not Null, Default: public', 'Funding source. Students may hold multiple private scholarships but only one public scholarship.'),
    ('description', 'text', 'Not Null', 'Detailed description of the scholarship program.'),
    ('eligibility_criteria', 'text', 'Not Null', 'Qualification requirements a student must meet to apply.'),
    ('benefits', 'text', 'Not Null', 'Benefits granted to approved scholars.'),
    ('application_deadline', 'datetime', 'Null', 'Cut-off date and time for accepting applications.'),
    ('award_amount', 'decimal(10,2)', 'Null', 'Monetary value awarded per scholar.'),
    ('max_applicants', 'int', 'Null, Minimum: 0', 'Maximum number of applicants the program can accept.'),
    ('current_applicants', 'int', 'Default: 0', 'Running count of submitted applications.'),
    ('status', 'enum(ACTIVE, CLOSED)', 'Not Null, Default: ACTIVE', 'Indicates whether the program is open or closed for applications.'),
    ('created_by', 'int', 'Not Null, Foreign Key (users.id)', 'Staff or admin who created the program.'),
    ('is_hidden', 'boolean', 'Not Null, Default: false', 'Flag controlling visibility of the program to students.'),
    ('allowed_student_ids', 'text', 'Null', 'List of specific students allowed to view a private/targeted program.'),
    ('custom_form_fields', 'json', 'Null', 'Custom application form fields defined by the scholarship office.'),
    ('campus_id', 'int', 'Foreign Key (campuses.id)', 'Campus the program belongs to; Null for university-wide programs.'),
    ('scope', 'enum(campus, university)', 'Not Null, Default: campus', 'Coverage scope of the program.'),
    ('academic_period_id', 'int', 'Foreign Key (academic_periods.id)', 'Period the program is bound to; Null means the program is permanent.'),
    ('created_at', 'datetime', 'Not Null', 'Date and time the program was created.'),
    ('updated_at', 'datetime', 'Not Null', 'Date and time the program was last updated.'),
])

# ── 6. Scholarship Applications ──────────────────────────────────────────────
add_dict_table('Scholarship Application', [
    ('id', 'int', 'Not Null, Primary Key, Auto-Increment', 'Unique identifier for each application.'),
    ('scholarship_id', 'int', 'Not Null, Foreign Key (scholarships.id)', 'Scholarship program being applied to.'),
    ('applicant_id', 'int', 'Not Null, Foreign Key (users.id)', 'Student who submitted the application.'),
    ('application_data', 'json', 'Null', 'Application form responses, including custom fields.'),
    ('documents', 'json', 'Null', 'Document references submitted with the application.'),
    ('status', 'enum(PENDING, UNDER_REVIEW, APPROVED, REJECTED)', 'Not Null, Default: PENDING', 'Current stage of the application in the review workflow.'),
    ('scholar_tag', 'enum(active, at_risk, probation, inactive)', 'Default: active', 'Compliance tag of the scholar after approval.'),
    ('submitted_at', 'datetime', 'Not Null', 'Date and time the application was submitted.'),
    ('reviewed_at', 'datetime', 'Null', 'Date and time the application was reviewed.'),
    ('reviewed_by', 'int', 'Foreign Key (users.id)', 'Staff or admin who reviewed the application.'),
    ('review_notes', 'text', 'Null', 'Comments recorded by the reviewer during evaluation.'),
    ('final_decision_date', 'datetime', 'Null', 'Date and time the final decision was released.'),
    ('approved_at', 'datetime', 'Null', 'Date and time the application was approved.'),
    ('batch_id', 'int', 'Foreign Key (scholarship_batches.id)', 'Batch the approved scholar was assigned to.'),
    ('academic_period_id', 'int', 'Foreign Key (academic_periods.id)', 'Academic period the application belongs to.'),
    ('amount_received', 'decimal(10,2)', 'Null', 'Actual amount released to the scholar.'),
    ('seq_number', 'int', 'Null', 'Sequence number of the scholar within the batch.'),
    ('campus_id', 'int', 'Foreign Key (campuses.id)', 'Campus the application is scoped to.'),
    ('scholar_status', 'varchar(30)', 'Default: active', 'Current status of the scholar in the program.'),
    ('compliance_status', 'varchar(20)', 'Default: compliant', 'Result of the latest monitoring and evaluation check.'),
    ('last_compliance_check', 'datetime', 'Null', 'Date and time of the last compliance evaluation.'),
    ('status_updated_at', 'datetime', 'Null', 'Date and time the scholar status was last changed.'),
    ('renewal_notified_at', 'datetime', 'Null', 'Date and time the scholar was notified about renewal.'),
    ('is_active', 'boolean', 'Default: true', 'Flag indicating whether the scholarship grant is currently active.'),
])

# ── 7. Scholarship Batches ───────────────────────────────────────────────────
add_dict_table('Scholarship Batch', [
    ('id', 'int', 'Not Null, Primary Key, Auto-Increment', 'Unique identifier for each batch.'),
    ('scholarship_id', 'int', 'Not Null, Foreign Key (scholarships.id)', 'Scholarship program the batch belongs to.'),
    ('academic_period_id', 'int', 'Not Null, Foreign Key (academic_periods.id)', 'Academic period the batch is scoped to.'),
    ('batch_name', 'varchar(50)', 'Not Null', 'Display name of the batch (e.g., Batch 1, Batch 1.1).'),
    ('batch_number', 'float', 'Not Null, Default: 1', 'Numeric value used for sorting batches.'),
    ('amount_per_scholar', 'decimal(10,2)', 'Null', 'Monetary allocation per scholar in the batch.'),
    ('total_scholars', 'int', 'Default: 0', 'Total number of scholars in the batch.'),
    ('total_male', 'int', 'Default: 0', 'Number of male scholars in the batch.'),
    ('total_female', 'int', 'Default: 0', 'Number of female scholars in the batch.'),
    ('total_amount', 'decimal(12,2)', 'Default: 0', 'Total fund allocation for the batch.'),
    ('status', 'enum(open, closed, finalized)', 'Default: open', 'Processing state of the batch.'),
    ('notes', 'text', 'Null', 'Additional remarks about the batch.'),
    ('campus_id', 'int', 'Foreign Key (campuses.id)', 'Campus the batch belongs to.'),
    ('created_by', 'int', 'Foreign Key (users.id)', 'Staff or admin who created the batch.'),
    ('created_at', 'datetime', 'Null', 'Date and time the batch was created.'),
    ('updated_at', 'datetime', 'Null', 'Date and time the batch was last updated.'),
])

# ── 8. Documents ─────────────────────────────────────────────────────────────
add_dict_table('Document', [
    ('id', 'int', 'Not Null, Primary Key, Auto-Increment', 'Unique identifier for each uploaded document.'),
    ('user_id', 'int', 'Not Null, Foreign Key (users.id)', 'Student who owns the document.'),
    ('application_id', 'int', 'Foreign Key (scholarship_applications.id)', 'Application the document is attached to, when applicable.'),
    ('original_filename', 'varchar(255)', 'Not Null', 'Name of the file as uploaded by the student.'),
    ('stored_filename', 'varchar(255)', 'Not Null, Unique', 'System-generated filename used on storage.'),
    ('file_path', 'varchar(500)', 'Not Null', 'Local path or URL where the file is stored.'),
    ('file_size', 'int', 'Null', 'File size in bytes.'),
    ('category', 'varchar(50)', 'Null', 'Document category (transcript, good_moral, birth_cert, awards, etc.).'),
    ('file_type', 'varchar(10)', 'Null', 'File format (pdf, docx, jpg, png).'),
    ('description', 'varchar(255)', 'Null', 'Short description of the document.'),
    ('is_verified', 'boolean', 'Not Null, Default: false', 'Flag indicating whether the document passed verification.'),
    ('ctc_detected', 'boolean', 'Null', 'Flag indicating whether a Certified True Copy marking was detected.'),
    ('cloudinary_url', 'varchar(500)', 'Null', 'Permanent public URL of the file on Cloudinary.'),
    ('cloudinary_public_id', 'varchar(255)', 'Null', 'Cloudinary reference used for secure deletion.'),
    ('uploaded_at', 'datetime', 'Not Null', 'Date and time the file was uploaded.'),
    ('updated_at', 'datetime', 'Null', 'Date and time the file was last replaced.'),
])

# ── 9. GWA History ───────────────────────────────────────────────────────────
add_dict_table('GWA History', [
    ('id', 'int', 'Not Null, Primary Key, Auto-Increment', 'Unique identifier for each GWA record.'),
    ('student_id', 'int', 'Not Null, Foreign Key (users.id)', 'Student the GWA record belongs to.'),
    ('gwa', 'float', 'Not Null', 'General Weighted Average recorded for the semester.'),
    ('semester', 'varchar(30)', 'Not Null', 'Semester the GWA was taken (e.g., 1st Semester).'),
    ('school_year', 'varchar(20)', 'Not Null', 'Academic year the GWA was taken (e.g., 2026-2027).'),
    ('recorded_by', 'int', 'Foreign Key (users.id)', 'Staff or admin who recorded the GWA.'),
    ('notes', 'varchar(255)', 'Null', 'Remarks about the GWA entry.'),
    ('recorded_at', 'datetime', 'Not Null', 'Date and time the GWA was recorded.'),
])

# ── 10. Monitoring Submissions ───────────────────────────────────────────────
add_dict_table('Monitoring and Evaluation Submission', [
    ('id', 'int', 'Not Null, Primary Key, Auto-Increment', 'Unique identifier for each M&E submission.'),
    ('user_id', 'int', 'Not Null, Foreign Key (users.id)', 'Scholar who submitted the form.'),
    ('application_id', 'int', 'Not Null, Foreign Key (scholarship_applications.id)', 'Approved application the submission is for.'),
    ('academic_period_id', 'int', 'Foreign Key (academic_periods.id)', 'Academic period the submission covers.'),
    ('original_filename', 'varchar(255)', 'Not Null', 'Name of the uploaded M&E form file.'),
    ('file_url', 'varchar(500)', 'Null', 'URL where the submitted form is stored.'),
    ('cloudinary_public_id', 'varchar(255)', 'Null', 'Cloudinary reference used for secure deletion.'),
    ('local_path', 'varchar(500)', 'Null', 'Local storage path of the file.'),
    ('file_type', 'varchar(10)', 'Null', 'File format (pdf, jpg, jpeg, png).'),
    ('file_size', 'int', 'Null', 'File size in bytes.'),
    ('uploaded_at', 'datetime', 'Not Null', 'Date and time the form was submitted.'),
])

# ── 11. Notifications ────────────────────────────────────────────────────────
add_dict_table('Notification', [
    ('id', 'int', 'Not Null, Primary Key, Auto-Increment', 'Unique identifier for each notification.'),
    ('recipient_id', 'int', 'Not Null, Foreign Key (users.id)', 'User who receives the notification.'),
    ('title', 'varchar(200)', 'Not Null', 'Title or subject of the notification.'),
    ('message', 'text', 'Not Null', 'Body content of the notification or announcement.'),
    ('notification_type', 'enum', 'Not Null', 'Category of notification (application update, announcement, system alert).'),
    ('channel', 'enum(IN_APP, EMAIL, SMS)', 'Not Null, Default: IN_APP', 'Delivery channel used to send the notification.'),
    ('is_read', 'boolean', 'Not Null, Default: false', 'Flag indicating whether the recipient has read the notification.'),
    ('sent_at', 'datetime', 'Not Null', 'Date and time the notification was sent.'),
    ('read_at', 'datetime', 'Null', 'Date and time the notification was read.'),
    ('related_entity_type', 'varchar(50)', 'Null', 'Type of record the notification refers to (scholarship, application).'),
    ('related_entity_id', 'int', 'Null', 'Primary key of the referenced record.'),
    ('academic_period_id', 'int', 'Foreign Key (academic_periods.id)', 'Period the announcement was sent in, used for period-scoped filtering.'),
])

# ── 12. Audit Log ────────────────────────────────────────────────────────────
add_dict_table('Audit Log', [
    ('id', 'int', 'Not Null, Primary Key, Auto-Increment', 'Unique identifier for each audit entry.'),
    ('user_id', 'int', 'Foreign Key (users.id)', 'User who performed the action; Null if the account was deleted.'),
    ('user_name', 'varchar(120)', 'Null', 'Snapshot of the user name that survives account deletion.'),
    ('user_role', 'varchar(20)', 'Null', 'Role of the user at the time of the action (admin, staff, student, super_admin).'),
    ('action', 'varchar(80)', 'Not Null', 'Machine-readable action identifier (e.g., application.approve).'),
    ('category', 'varchar(40)', 'Null', 'Action category (auth, application, scholarship, user, gwa, document, system).'),
    ('description', 'text', 'Null', 'Human-readable detail of what occurred.'),
    ('target_type', 'varchar(40)', 'Null', 'Type of record affected (application, scholarship, user).'),
    ('target_id', 'int', 'Null', 'Primary key of the affected record.'),
    ('ip_address', 'varchar(45)', 'Null', 'IP address the action originated from.'),
    ('timestamp', 'datetime', 'Not Null', 'Date and time the action was logged.'),
])

# ── 13. Chat History ─────────────────────────────────────────────────────────
add_dict_table('AI Chat History', [
    ('id', 'int', 'Not Null, Primary Key, Auto-Increment', 'Unique identifier for each chat message.'),
    ('user_id', 'int', 'Foreign Key (users.id)', 'User who owns the conversation; Null for guest sessions.'),
    ('role', 'enum(user, model)', 'Not Null', 'Sender of the message: user question or AI response.'),
    ('content', 'text', 'Not Null', 'Content of the chat message.'),
    ('created_at', 'datetime', 'Not Null', 'Date and time the message was sent.'),
])

# Save
output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'LSPU_ScholarHub_Data_Dictionary.docx')
doc.save(output_path)
print(f'DOCX saved: {output_path}')
print(f'Entities documented: {TABLE_NUM}')

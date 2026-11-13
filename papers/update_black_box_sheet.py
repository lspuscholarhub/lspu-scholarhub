"""Update the black-box testing sheet to match the CURRENT online system.

Keeps the original docx format (info table + steps table per test case,
headings, instructions, tester info grid, certification) and rewrites only
the cell CONTENT: descriptions, preconditions, steps and expected results.
Saves to a NEW file; the original is not modified.

Run:  python papers/update_black_box_sheet.py
"""
import io, os, sys, copy
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from docx import Document

SRC = r'C:\Users\kirit\Downloads\LSPU_ScholarHub_Black_Box_Testing_Sheet.docx'
OUT = r'C:\Users\kirit\Downloads\Black_Box_Testing_Sheet.docx'

# ── New test-case content for the CURRENT system ─────────────────────────────
# (scenario, description, precondition, [(step, expected_result), ...])

TC = {}

TC['TC-01'] = (
    'Homepage / Landing Page',
    'Verify that the LSPU ScholarHub homepage loads correctly and displays the public information, navigation menu, scholarship highlights, and AI Assistant entry point without errors.',
    'The ScholarHub website is accessible through a supported web browser and no user is logged in.',
    [
        ('Navigate to the ScholarHub website homepage.', 'The homepage loads successfully and displays without a server error.'),
        ('Observe the page while the initial loading completes.', 'Loading completes and the homepage content becomes fully usable.'),
        ('Review the header navigation (Home, Scholarships, AI Assistant, Login, Register) and the footer contact information.', 'All navigation items and footer contact details (location, email, contact number, office hours) are visible and correct.'),
        ('Select the Scholarships navigation link.', 'The scholarship listing page opens showing only open and visible programs; hidden programs are not displayed.'),
        ('Open the AI Assistant from the homepage and ask "What scholarships are currently available?".', 'The AI Assistant replies with the same open programs shown on the public page and does not reveal any hidden program.'),
        ('Reload the homepage and resize the browser window to check responsive behavior.', 'The homepage reloads successfully and remains usable at different browser widths.'),
    ])

TC['TC-02'] = (
    'Applicant Registration with Document Verification',
    'Verify that a new student can register only with valid LSPU documents, that the system validates the COR and Copy of Grades (PDF) through OCR, sends an OTP for email verification, and creates the account with a temporary password.',
    'The tester has a sample Certificate of Registration (COR) and Copy of Grades (COG) in PDF format from the LSPU student portal, with readable name, student ID, year level, birthday, and campus. The student is not yet registered.',
    [
        ('Open the Register page and review the form fields (name, email, phone, course, year level, birthday, campus, student ID).', 'The registration page loads and displays all required fields, including the birthday calendar picker and campus dropdown.'),
        ('Submit the form with one required field left blank.', 'The form is not submitted and a validation message identifies the missing field.'),
        ('Attempt to upload an image file (JPG/PNG) instead of a PDF for the COR or COG.', 'The image file is rejected; only PDF files are accepted.'),
        ('Attempt to upload a PDF file larger than 5 MB.', 'The file is rejected with a clear file-size limit message.'),
        ('Enter a year level, campus, or birthday that is DIFFERENT from what the uploaded documents show, then submit.', 'Registration is blocked with a clear mismatch message (OCR verification of name, student ID, year level, birthday, and campus).'),
        ('Enter all information exactly matching the documents, optionally tick "I am already a scholar in LSPU" with the program name, and submit.', 'The documents pass OCR verification and a 6-digit OTP code is sent to the email address.'),
        ('Enter the correct OTP code.', 'The account is created and verified, and a welcome email containing the temporary password is received.'),
        ('Attempt to register again using the same email or student ID.', 'Registration is blocked with a message that the email or student ID is already registered.'),
    ])

TC['TC-03'] = (
    'User Authentication',
    'Verify that registered users can securely log in and log out, that the temporary password forces a password change, and that invalid credentials are rejected.',
    'An account exists with known credentials. For the temporary-password flow, an account created through registration is used.',
    [
        ('Open the Login page.', 'The login page loads with email and password fields.'),
        ('Log in using the temporary password received by email.', 'The system requires setting a new password before granting access.'),
        ('Attempt to set a weak password (e.g., "abc12345").', 'The weak password is rejected; the policy requires at least 8 characters with uppercase, lowercase, and a number.'),
        ('Set a valid new password.', 'The password is saved and the user is logged in to the role-specific dashboard.'),
        ('Log out from the account.', 'The user is returned to the public landing/login page.'),
        ('Attempt to log in using an incorrect password.', 'Login is rejected with an error message and no session is created.'),
        ('Attempt to submit the login form with blank credentials.', 'The form is not submitted and validation messages appear.'),
    ])

TC['TC-04'] = (
    'Scholarship Listing and Details',
    'Verify that users can browse available scholarship programs and view accurate details, and that hidden or other-campus programs are not shown.',
    'At least one open scholarship program exists for the tester\'s campus (or is university-wide). The tester is logged in as a student.',
    [
        ('Open the Scholarships page.', 'The page lists only open, visible programs available to the student\'s campus; hidden programs do not appear.'),
        ('Observe the campus badges on each program card.', 'Each program shows the correct scope (All Campuses or the specific campus).'),
        ('Select a scholarship program to open its details.', 'The details page shows qualifications, benefits, slots, award amount, deadline, and the Apply option when eligible.'),
        ('Use the search or filter controls (status, campus).', 'The list updates and only matching programs are displayed.'),
        ('Search for a keyword that matches no program.', 'A clean "no results" state is shown without errors.'),
        ('Return to the scholarship list.', 'The full list is displayed again correctly.'),
    ])

TC['TC-05'] = (
    'Online Scholarship Application',
    'Verify that an eligible student can submit an application with a pre-filled form and custom questions, and that the one-public-scholarship-per-period rule is enforced.',
    'The tester is logged in as a verified student whose campus has an open program. The student has no pending or approved public-program application in the current academic period.',
    [
        ('Open an available scholarship and select Apply.', 'The application form opens PRE-FILLED with the student\'s profile data (name, student ID, course, year level, GWA, units, birthday).'),
        ('Review the form sections.', 'Only the program\'s custom questions need answering; no essay and no document upload are required.'),
        ('Submit with a required custom field left blank.', 'Submission is blocked and the missing field is identified.'),
        ('Complete the custom questions and submit the application.', 'A success confirmation appears and the application is listed in My Applications as Pending.'),
        ('Attempt to apply to a second PUBLIC program within the same academic period.', 'The application is blocked with a message that only one public scholarship per period is allowed.'),
        ('Apply to a PRIVATE scholarship program.', 'The application is accepted even with an existing public application.'),
        ('Edit a pending application, save (Resubmit), then click the Back button.', 'The changes are saved, the status remains Pending, and no server error occurs.'),
    ])

TC['TC-06'] = (
    'Registration Document Upload and Replacement',
    'Verify that students can upload COR and Copy of Grades (PDF only), that the system enforces type and size rules, and that replacing a document automatically updates GWA, units, and campus through OCR.',
    'The tester is logged in as a student and has valid COR and COG PDF files (max 5 MB each) available.',
    [
        ('Open My Documents.', 'The page shows the COR and Copy of Grades cards with their submission status.'),
        ('Upload a valid COR PDF file.', 'The file is accepted, marked as Submitted, and opens in a new browser tab when viewed.'),
        ('Upload a valid Copy of Grades PDF file.', 'The file is accepted and the GWA and units enrolled are read automatically from the document and displayed.'),
        ('Attempt to upload a non-PDF file (image or document).', 'The file is rejected; only PDF files are accepted.'),
        ('Attempt to upload a PDF larger than 5 MB.', 'The file is rejected with a file-size message.'),
        ('Attempt to upload the COG file into the COR slot.', 'The upload is blocked because the document type does not match the required document.'),
        ('Replace the Copy of Grades with a newer PDF.', 'The old file is replaced and the GWA, units, and campus on the account update automatically from the new document.'),
    ])

TC['TC-07'] = (
    'Application Status Tracking',
    'Verify that students can track the status of their applications and that private applications are not accessible to other users.',
    'The tester is logged in as a student with at least one submitted application.',
    [
        ('Open My Applications.', 'The page shows centered summary cards (total, pending/under review, approved) and the application list.'),
        ('View an application card.', 'The card shows the program name, status badge, application number, submission date, and the progress tracker (Submitted - Under Review - Decision).'),
        ('Select View Details on an application.', 'The full application details display, including review notes once a decision has been made.'),
        ('Withdraw a pending application.', 'A confirmation dialog appears; after confirming, the status changes to Withdrawn.'),
        ('After staff updates an application status, refresh My Applications.', 'The new status is shown and a notification about the update was received.'),
        ('Attempt to open another student\'s application by changing the URL address.', 'Access is blocked and the user is redirected; no private data is displayed.'),
    ])

TC['TC-08'] = (
    'Scholar Profile Management',
    'Verify that students can view and update their profile information, declare an existing scholarship, and change their password.',
    'The tester is logged in as a student.',
    [
        ('Open My Profile.', 'The profile page displays personal information, academic details, and the campus.'),
        ('Edit the phone number and address, then save.', 'The changes are saved and persist after a page refresh.'),
        ('Set the "I am already a scholar in LSPU" declaration with the program name and save.', 'The declaration is saved and is visible to the Scholarship Office staff.'),
        ('Attempt to enter invalid information (e.g., letters in the phone number).', 'The input is rejected with a validation message.'),
        ('Change the password supplying the correct old password.', 'The password is changed successfully and the new password works on the next login.'),
        ('Attempt to change the password with a wrong old password.', 'The change is rejected with an error message.'),
    ])

TC['TC-09'] = (
    'Scholarship Program Management - Admin/Staff',
    'Verify that authorized staff can create, edit, and configure scholarship programs with custom form fields, scope, funding type, and visibility, and that cross-campus modifications are blocked.',
    'The tester is logged in as staff or admin for a campus.',
    [
        ('Open Scholarships and select Create.', 'The create form opens with all program fields.'),
        ('Enter a negative value in the award amount or slots field.', 'The value is rejected; zero is the minimum allowed.'),
        ('Fill in the title, description, funding type (public/private), scope (campus-specific or university-wide), eligibility, benefits, and custom form fields, then save.', 'The program is created and appears in the list with the correct campus badge.'),
        ('Open the newly created program.', 'All saved details, including the custom form fields, display correctly.'),
        ('Edit an allowed program field and save.', 'The change is saved and reflected in the program details.'),
        ('Create a HIDDEN program limited to specific student IDs.', 'Only the listed students can see the program; other students do not see it.'),
        ('Optionally enable "announce this program" upon creation.', 'Students of the target campus receive the announcement via the selected channels.'),
        ('As campus staff, attempt to edit or delete a program belonging to another campus.', 'The action is blocked with a permission message.'),
    ])

TC['TC-10'] = (
    'Application Review and Approval - Admin/Staff',
    'Verify that staff can review applications, move them through statuses, approve or reject them with notes, and that decisions trigger student notifications.',
    'At least one pending application exists for the staff member\'s campus.',
    [
        ('Open Applications (review queue).', 'Only applications from the staff member\'s campus are listed, with summary count cards.'),
        ('Open an applicant\'s record.', 'The pre-filled profile, custom answers, and OCR-parsed document data are displayed.'),
        ('Set an application to Under Review.', 'The status updates to Under Review and is reflected in the list.'),
        ('Approve an application with review notes.', 'The status becomes Approved; the student receives in-app, email, and SMS notifications; the scholar record is created and auto-assigned to a batch.'),
        ('Reject an application with a reason.', 'The status becomes Rejected; the student receives notifications and may re-apply in a future period.'),
        ('Use the batch selection to approve or reject multiple applications at once.', 'All selected applications are processed and each student is notified.'),
    ])

TC['TC-11'] = (
    'Scholar Monitoring',
    'Verify that staff can monitor scholars\' academic standing and M&E form compliance and update monitoring fields.',
    'At least one approved scholar exists for the campus and an M&E deadline is set for the current period.',
    [
        ('Open Monitoring.', 'The scholars table displays GWA, scholar status, approval date, and the M&E Form column with stat cards on top.'),
        ('Observe the M&E Form badges.', 'Each scholar shows Submitted, Not submitted, or a red Overdue badge when the deadline has passed.'),
        ('Select a Submitted M&E badge.', 'The student\'s uploaded M&E file opens in a new browser tab.'),
        ('Update a scholar\'s GWA or scholar status and save.', 'The change is saved and immediately reflected in the table.'),
        ('Check the M&E Overdue summary card.', 'The count matches the number of scholars with the Overdue badge.'),
        ('Send a renewal reminder to a scholar.', 'The reminder notification is sent successfully.'),
    ])

TC['TC-12'] = (
    'AI Chatbot Assistance',
    'Verify that the AI Assistant answers system-aware questions correctly, personalizes replies per user, and never reveals hidden programs.',
    'The AI Assistant is enabled. The tester has access to both a guest session and a student account.',
    [
        ('Open the AI Assistant as a guest and ask about currently available scholarships.', 'The reply lists only the same open programs shown on the public page and never mentions hidden programs.'),
        ('Log in as a student and ask "What scholarships can I apply to?".', 'The reply is personalized (uses the student\'s name) and lists only programs available to the student\'s campus.'),
        ('Ask about scholarship eligibility rules.', 'The answer correctly reflects system rules, such as the one-public-scholarship-per-period policy.'),
        ('Ask about the student\'s own application status.', 'The reply reflects the student\'s actual application data.'),
        ('Submit an unclear or unrelated question.', 'The assistant responds with a graceful fallback message instead of an error.'),
        ('Leave and reopen the AI Assistant.', 'The previous conversation history is retained.'),
    ])

TC['TC-13'] = (
    'Multi-Channel Notifications',
    'Verify that in-system, email, and SMS notifications are delivered for application events and announcements, including file attachments on announcements.',
    'Notification channels are configured (email enabled; SMS if available). The tester can access a student inbox and phone.',
    [
        ('Submit a scholarship application as a student.', 'An in-system notification appears in the student\'s notification area.'),
        ('Check the student\'s email inbox.', 'An application-received email notification is received.'),
        ('Check the student\'s phone.', 'An SMS notification is received (if SMS is enabled).'),
        ('As staff, send an announcement with an attached PDF and email and SMS options ticked.', 'Students receive the email with the attachment; the SMS is delivered as text.'),
        ('Open the notifications page and use Mark as Read / Mark All as Read.', 'Read states update correctly.'),
        ('After a status change by staff, open the newest notification.', 'The notification content correctly describes the application update.'),
    ])

TC['TC-14'] = (
    'Reports and Analytics',
    'Verify that dashboard statistics and report charts are accurate, campus-scoped, responsive, and exportable.',
    'The tester is logged in as staff or admin with existing application and scholar data.',
    [
        ('Open the dashboard and compare the summary counters with actual records.', 'The application and scholar counts match the underlying data.'),
        ('Open Reports and observe the charts.', 'All charts (GWA distribution, application statuses, scholar status) render correctly.'),
        ('Resize the browser window while viewing the charts.', 'The charts resize responsively without breaking the layout.'),
        ('Switch the campus filter (admin/super admin).', 'All report numbers update to reflect the selected campus scope.'),
        ('Export the report.', 'The export file downloads successfully and its contents match the displayed report.'),
    ])

TC['TC-15'] = (
    'Document Management - Staff',
    'Verify that staff can view, verify, and manage student registration documents securely, and that documents open in a viewable tab rather than forcing a download.',
    'The tester is logged in as staff and at least one student has uploaded COR and COG documents.',
    [
        ('Open a student profile from the directory.', 'The registration documents section lists the COR and Copy of Grades with their status badges.'),
        ('Select View on a document.', 'The document opens in a new browser tab for viewing (not forced download).'),
        ('Verify or unverify a document.', 'The verification badge updates accordingly.'),
        ('Attempt to access another student\'s document by changing the URL address.', 'Access is blocked and the user is redirected.'),
        ('Have the student replace a document, then re-open the staff view.', 'The replaced file is shown and the OCR-updated GWA, units, and campus are reflected.'),
    ])

TC['TC-16'] = (
    'User Management and Role-Based Access Control',
    'Verify that admins can manage user accounts with campus scoping and that protected pages enforce role permissions.',
    'The tester has admin and super admin accounts, plus a student account for negative testing.',
    [
        ('Open Users and observe the campus column and filter.', 'The user list shows each account\'s campus and the filter works.'),
        ('Create a Staff account including the campus field.', 'The account is created and scoped to the selected campus.'),
        ('Change a user\'s role using the role dropdown.', 'A confirmation appears and the role change takes effect.'),
        ('Attempt to change your own role.', 'The action is blocked.'),
        ('Disable a user account, then attempt to log in as that user.', 'Login is blocked while disabled; re-enabling restores access.'),
        ('Attempt to delete your own account or the last admin account.', 'The deletion is blocked with a protective message.'),
        ('As a student, directly enter the URL of an admin page (e.g., /admin/users).', 'Access is blocked and the student is redirected to login or their dashboard.'),
        ('As a campus admin, attempt to open the Periods page.', 'The Periods link is not shown and direct URL access is blocked (Super Admin only).'),
    ])

TC['TC-17'] = (
    'Search and Filter Functions',
    'Verify that search and filtering work correctly across modules, including the scholar declaration filter.',
    'The tester is logged in as staff or admin with multiple student records of varying statuses.',
    [
        ('Open the Students directory and search a valid name or student ID.', 'Only matching records are displayed.'),
        ('Apply the Scholar Declaration filter (Declared / No declaration).', 'The list updates according to the selected declaration status.'),
        ('Apply the campus filter (admin/super admin).', 'Only students of the selected campus are displayed.'),
        ('Combine a keyword with a filter.', 'Results satisfy both the keyword and the filter.'),
        ('Search for a keyword with no matching record.', 'A clean empty state is shown without errors.'),
        ('Clear the search and filters.', 'The full unfiltered list is restored.'),
    ])

TC['TC-18'] = (
    'Role-Based Dashboard Navigation',
    'Verify that each role sees only its own navigation and that the super admin campus switcher scopes every page.',
    'Test accounts exist for student, staff, admin, and super admin roles.',
    [
        ('Log in as a student.', 'The header shows only student items (Dashboard, Scholarships, My Applications, Notifications, AI Assistant, My Scholarship when approved).'),
        ('Log in as staff.', 'The staff navigation is shown with the campus badge; no admin-only links appear.'),
        ('Log in as a campus admin.', 'The full management navigation is shown; the Periods link is NOT displayed.'),
        ('Log in as super admin.', 'The Periods link and the All Campuses switcher are displayed.'),
        ('Switch the campus context to a specific campus.', 'Dashboard, scholarships, applications, monitoring, batches, students, and reports all filter to that campus.'),
        ('Switch back to All Campuses.', 'Data from all campuses is displayed again.'),
    ])

TC['TC-19'] = (
    'Responsive Web Usability',
    'Verify that the system remains usable on smaller screens and different browsers, including the mobile navigation.',
    'A desktop browser with device-emulation tools (or a mobile device) is available.',
    [
        ('Open the homepage on a desktop-sized window.', 'The layout renders correctly at full width.'),
        ('Resize the browser to a tablet width.', 'The layout adjusts without overlapping elements.'),
        ('Resize to a mobile width and open the navigation menu.', 'The hamburger menu opens and all links are reachable.'),
        ('Open the student dashboard and a form at mobile width.', 'Cards and form fields stack correctly and remain usable.'),
        ('Scroll horizontally and vertically through the pages.', 'No unintended horizontal scrolling or clipped content appears.'),
        ('Repeat key checks in another supported browser.', 'The pages behave consistently across browsers.'),
    ])

TC['TC-20'] = (
    'Session Handling and Protected Page Access',
    'Verify that sessions are securely terminated on logout and that protected pages cannot be accessed without authentication or sufficient role.',
    'The tester has valid student and admin accounts and knows the URLs of protected pages.',
    [
        ('Log in with a valid account and open a protected dashboard.', 'The dashboard loads with an active session.'),
        ('Log out from the system.', 'The session is terminated and the user is returned to the public page.'),
        ('Press the browser Back button after logout.', 'The protected page is not displayed; the user is redirected to login.'),
        ('Directly enter the URL of a protected page after logout.', 'Access is blocked and the user is redirected to the login page.'),
        ('Close and reopen the browser, then attempt to access the protected page.', 'Access remains blocked without logging in again.'),
        ('While logged in as a student, attempt to access admin/staff pages by URL.', 'All attempts are blocked by role-based access control.'),
    ])


def set_cell_text(cell, text, ref_run=None):
    """Replace a cell's text, preserving the first run's font when possible."""
    # Remove extra paragraphs
    for p in cell.paragraphs[1:]:
        p._element.getparent().remove(p._element)
    p = cell.paragraphs[0]
    # Remove all runs except the first
    runs = p.runs
    if runs:
        keep = runs[0]
        for r in runs[1:]:
            r._element.getparent().remove(r._element)
        keep.text = text
        if ref_run is not None:
            try:
                keep.font.name = ref_run.font.name
                keep.font.size = ref_run.font.size
            except Exception:
                pass
    else:
        r = p.add_run(text)
        if ref_run is not None:
            try:
                r.font.name = ref_run.font.name
                r.font.size = ref_run.font.size
            except Exception:
                pass


def main():
    doc = Document(SRC)
    tables = doc.tables

    # Walk tables in pairs: info (4x2) then steps (5 cols)
    ti = 0
    updated = 0
    while ti < len(tables):
        tbl = tables[ti]
        if len(tbl.columns) == 2 and len(tbl.rows) == 4:
            tcid = tbl.rows[0].cells[1].text.strip()
            if tcid in TC and ti + 1 < len(tables):
                scenario, description, precondition, steps = TC[tcid]
                steps_tbl = tables[ti + 1]

                # Reference font from an existing data cell
                ref_run = None
                try:
                    r0 = tbl.rows[1].cells[1].paragraphs[0].runs
                    if r0:
                        ref_run = r0[0]
                except Exception:
                    pass

                # Info table: description (row1), scenario (row2), precondition (row3)
                set_cell_text(tbl.rows[1].cells[1], description, ref_run)
                set_cell_text(tbl.rows[2].cells[1], scenario, ref_run)
                set_cell_text(tbl.rows[3].cells[1], precondition, ref_run)

                # Steps table: keep header, replace data rows
                for row in list(steps_tbl.rows)[1:]:
                    row._element.getparent().remove(row._element)
                for n, (detail, expected) in enumerate(steps, 1):
                    row = steps_tbl.add_row()
                    set_cell_text(row.cells[0], str(n), ref_run)
                    set_cell_text(row.cells[1], detail, ref_run)
                    set_cell_text(row.cells[2], expected, ref_run)
                    # Actual Result + Status left blank for testers

                updated += 1
                print(f'{tcid} updated: {len(steps)} steps')
                ti += 2
                continue
        ti += 1

    print(f'\n{updated} test cases updated')
    doc.save(OUT)
    print(f'Saved: {OUT}')


if __name__ == '__main__':
    main()

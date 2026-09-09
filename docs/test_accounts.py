"""Testing policy — READ THIS before writing any test or sweep script.

The owner allows ONLY these live-database accounts to be used for testing:

    Staff  : id 53   (Alfonso, alfonso999castillo@gmail.com)
    Student: id 68   (0123-1543, kierisaacriola224@gmail.com)
    Student: id 51   (0123-1633, ajmaclld@gmail.com)
    Student: id 150  (0123-1714, masaonyx@gmail.com)

Rules:
  1. NEVER create throwaway User/Scholarship/Application rows on the live DB.
     If a synthetic record is unavoidable, create it, use it, and delete it in
     the same run — and attach it to one of the allowed accounts only.
  2. NEVER modify the profile data of any account. When a test must POST a
     profile update, read the account's current values first and post them
     back unchanged.
  3. Other real users' rows are strictly read-only (counts are fine).

Import TEST_* constants from this module in every test script.
"""

ALLOWED_STAFF_IDS = [53]
ALLOWED_STUDENT_IDS = [68, 51, 150]          # 0123-1543, 0123-1633, 0123-1714
ALLOWED_USER_IDS = ALLOWED_STAFF_IDS + ALLOWED_STUDENT_IDS

PRIMARY_STUDENT_ID = 150                     # the owner's main test student
PRIMARY_STAFF_ID = 53


def assert_allowed(user_id):
    if user_id not in ALLOWED_USER_IDS:
        raise PermissionError(
            f'user_id={user_id} is not an approved test account. '
            f'Allowed: {ALLOWED_USER_IDS} (see docs/test_accounts.py)')

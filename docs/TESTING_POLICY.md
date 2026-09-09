# Testing policy — approved accounts only

**Effective immediately.** All testing, sweeps, and simulations on the live
database must use ONLY the accounts below. Do not create new accounts and do
not touch any other user's data.

| Role    | DB id | Student ID | Email                        |
|---------|-------|------------|------------------------------|
| Staff   | 53    | —          | alfonso999castillo@gmail.com |
| Student | 68    | 0123-1543  | kierisaacriola224@gmail.com  |
| Student | 51    | 0123-1633  | ajmaclld@gmail.com           |
| Student | 150   | 0123-1714  | masaonyx@gmail.com           |

Machine-readable source of truth: `docs/test_accounts.py`
(`ALLOWED_STAFF_IDS`, `ALLOWED_STUDENT_IDS`, `PRIMARY_STUDENT_ID = 150`,
`PRIMARY_STAFF_ID = 53`, plus `assert_allowed()` for scripts).

Rules:
1. **No new accounts.** Never register or insert throwaway users on the live DB.
2. **No profile edits.** A test that posts a profile update must read the
   account's current values first and post them back unchanged.
3. **Other users are read-only.** Real students' rows may only be counted or
   read, never modified or deleted.
4. Synthetic records (scholarships/applications) created for a test must be
   attached to an approved account and deleted in the same run.

`docs/error_sweep.py` and `docs/post_sweep.py` already follow this policy.

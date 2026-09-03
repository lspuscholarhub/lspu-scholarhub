"""
Shared GWA label utilities for LSPU ScholarHub.

LSPU Grading Scale (lower = better):
  1.00 – 1.25  Excellent
  1.26 – 1.75  Very Satisfactory
  1.76 – 2.25  Satisfactory
  2.26 – 2.75  Fairly Satisfactory
  2.76 – 3.00  Passed
  3.01 – 3.99  Conditional Failure
  4.00 – 5.00  Failed

Thresholds used for scholar status:
  ≤ 3.00  → active
  ≤ 3.75  → at_risk
  ≤ 4.00  → probation
  > 4.00  → termination_warning
"""

# GWA threshold for at-risk students (used in dashboard stats)
GWA_THRESHOLD = 3.00


def get_gwa_label(gwa):
    """Return (label, css_class) for a given GWA value."""
    if gwa is None:
        return ('Not set', 'text-muted')
    if gwa <= 1.25:
        return ('Excellent', 'text-success')
    if gwa <= 1.75:
        return ('Very Satisfactory', 'text-success')
    if gwa <= 2.25:
        return ('Satisfactory', 'text-success')
    if gwa <= 2.75:
        return ('Fairly Satisfactory', 'text-info')
    if gwa <= 3.00:
        return ('Passed', 'text-warning')
    if gwa < 4.00:
        return ('Conditional Failure', 'text-danger')
    return ('Failed', 'text-danger')


def get_gwa_badge_class(gwa):
    """Return Bootstrap badge class for a GWA value."""
    if gwa is None:
        return 'bg-secondary'
    if gwa <= 1.75:
        return 'bg-success'
    if gwa <= 2.75:
        return 'bg-info'
    if gwa <= 3.00:
        return 'bg-warning text-dark'
    if gwa < 4.00:
        return 'bg-danger'
    return 'bg-dark'


def get_scholar_status(gwa):
    """Determine scholar performance status from GWA."""
    if gwa is None:
        return 'active', 'active'
    if gwa >= 4.00:
        return 'termination_warning', 'inactive'
    if gwa > 3.75:
        return 'probation', 'probation'
    if gwa > 3.00:
        return 'at_risk', 'at_risk'
    return 'active', 'active'

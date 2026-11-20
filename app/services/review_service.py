"""The scholar standing that follows an application decision.

Staff and admin, single review and batch review, all have to answer the same
question: which scholar_status should this decision leave behind? Keeping the
answer here stops the four call sites from drifting apart.

The rule:
  * approve -> the tag the reviewer picked, or 'active' when they picked none
  * reject  -> the tag the reviewer picked, or nothing (leave the standing alone)
"""

# Standings a reviewer may pin on an application from the review sheet.
SCHOLAR_TAGS = ('active', 'at_risk', 'probation', 'inactive')


def scholar_status_after_decision(action, tag=None):
    """Return the scholar_status to write for a decision, or None to leave it.

    ``action`` is the review action ('approve' / 'reject'); ``tag`` is whatever
    the review sheet's tag select submitted, if anything.
    """
    picked = (tag or '').strip()
    if action == 'approve':
        return picked if picked in SCHOLAR_TAGS else 'active'
    if action == 'reject':
        return picked if picked in SCHOLAR_TAGS else None
    return None

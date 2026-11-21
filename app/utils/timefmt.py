"""Campus clock helpers.

Timestamps are stored as naive UTC. The screens read on the campus clock
(PHT, UTC+8); the deployment host has no tz database, so the offset is fixed
rather than looked up — the Philippines has no daylight saving.
"""
from datetime import timedelta

PHT = timedelta(hours=8)


def to_campus(dt):
    """Shift a stored naive-UTC datetime to the campus clock (None-safe)."""
    return (dt + PHT) if dt else None

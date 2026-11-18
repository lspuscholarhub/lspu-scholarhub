"""
API blueprint — kept minimal.

The real chatbot lives at /chatbot/ (chatbot_bp).
This file also hosts the portal webhook, which lets the LSPU portal tell
ScholarHub that one or more student records changed.
"""

import hashlib
import hmac
import json
import os
import time

from flask import Blueprint, jsonify, request

from app import limiter

api_bp = Blueprint('api', __name__)


@api_bp.route('/health', methods=['GET'])
def api_health():
    """Lightweight health check for API consumers."""
    return jsonify({'status': 'ok'})


def _webhook_secret():
    return os.environ.get('PORTAL_WEBHOOK_SECRET') or ''


def _signature_ok(raw_body: bytes, timestamp: str, signature: str) -> bool:
    """HMAC-SHA256 over "<timestamp>.<body>" with the shared secret."""
    if not signature:
        return False
    message = timestamp.encode() + b'.' + raw_body
    expected = hmac.new(_webhook_secret().encode(), message, hashlib.sha256).hexdigest()
    provided = signature.split('=', 1)[-1].strip()
    return hmac.compare_digest(expected, provided)


@api_bp.route('/portal/sync', methods=['POST'])
@limiter.limit('60 per minute')
def portal_sync_webhook():
    """Portal → ScholarHub change notification.

    The portal (or an ICTS scheduler) POSTs the student IDs whose records
    changed. ScholarHub re-reads those records from its own read-only source,
    so the payload never carries data we would have to trust.

        POST /api/portal/sync
        X-Portal-Timestamp: 1734567890
        X-Portal-Signature: sha256=<hex hmac of "<timestamp>.<raw body>">
        {"student_ids": ["0199-0000", "0199-0001"]}

    Disabled unless PORTAL_ENABLED and PORTAL_WEBHOOK_SECRET are set.
    """
    from app.services.portal import is_enabled, sync_students

    if not is_enabled() or not _webhook_secret():
        return jsonify({'error': 'Portal webhook is not configured.'}), 503

    timestamp = request.headers.get('X-Portal-Timestamp', '').strip()
    signature = request.headers.get('X-Portal-Signature', '').strip()
    raw_body = request.get_data(cache=True) or b''

    if not timestamp.isdigit():
        return jsonify({'error': 'Missing or invalid X-Portal-Timestamp.'}), 401
    try:
        skew = abs(time.time() - int(timestamp))
    except (TypeError, ValueError):
        skew = 10 ** 6
    if skew > 300:
        return jsonify({'error': 'Timestamp outside the allowed 5-minute window.'}), 401
    if not _signature_ok(raw_body, timestamp, signature):
        return jsonify({'error': 'Invalid signature.'}), 401

    try:
        payload = json.loads(raw_body.decode('utf-8') or '{}')
    except (UnicodeDecodeError, ValueError):
        return jsonify({'error': 'Body must be JSON.'}), 400

    student_ids = payload.get('student_ids') or []
    if isinstance(student_ids, str):
        student_ids = [student_ids]
    if not isinstance(student_ids, list) or not student_ids:
        return jsonify({'error': 'Provide a non-empty student_ids array.'}), 400
    if len(student_ids) > 200:
        return jsonify({'error': 'Send at most 200 student IDs per request.'}), 400

    try:
        stats = sync_students(student_ids=student_ids, trigger='webhook')
    except Exception:
        # The portal should retry; never leak internals in the response.
        return jsonify({'error': 'Sync failed; retry later.'}), 500

    if stats.get('error'):
        return jsonify({'ok': False, 'stats': stats}), 500
    return jsonify({'ok': True, 'stats': stats}), 200

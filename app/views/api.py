"""
API blueprint — kept minimal.

The real chatbot lives at /chatbot/ (chatbot_bp).
This file exists only so the 'api_bp' registration in __init__.py doesn't break.
"""

from flask import Blueprint, jsonify

api_bp = Blueprint('api', __name__)


@api_bp.route('/health', methods=['GET'])
def api_health():
    """Lightweight health check for API consumers."""
    return jsonify({'status': 'ok'})

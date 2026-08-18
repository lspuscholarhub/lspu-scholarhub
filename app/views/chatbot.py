"""
Chatbot routes for LSPU ScholarHub.
Powered by Google Gemini with persistent chat history.
"""

import os
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session

chatbot_bp = Blueprint('chatbot', __name__)

HISTORY_LIMIT = 30   # max messages loaded from DB per session


def _get_db_history(user_id):
    """Load the last HISTORY_LIMIT messages for a user from the database."""
    from app.models.chat_history import ChatHistory
    rows = (ChatHistory.query
            .filter_by(user_id=user_id)
            .order_by(ChatHistory.created_at.asc())
            .all())
    # Return last HISTORY_LIMIT messages as dicts
    return [r.to_dict() for r in rows[-HISTORY_LIMIT:]]


def _save_message(user_id, role, content):
    """Persist a single message to the database."""
    from app import db
    from app.models.chat_history import ChatHistory
    db.session.add(ChatHistory(user_id=user_id, role=role, content=content))
    db.session.commit()


@chatbot_bp.route('/')
def chatbot_page():
    """Render the chatbot UI."""
    api_configured = bool(os.environ.get('GEMINI_API_KEY', '').strip())
    user_name   = None
    is_verified = False
    db_history  = []

    if session.get('user_id') and session.get('user_type') in ('student', 'guest'):
        try:
            from app.models import User
            u = User.query.get(session['user_id'])
            if u:
                user_name   = u.first_name
                is_verified = u.is_verified
        except Exception:
            pass

    # Load persistent history for logged-in users
    if session.get('user_id'):
        try:
            db_history = _get_db_history(session['user_id'])
        except Exception:
            db_history = []

    return render_template('chatbot/index.html',
                           api_configured=api_configured,
                           user_name=user_name,
                           is_verified=is_verified,
                           db_history=db_history)


@chatbot_bp.route('/chat', methods=['POST'])
def chat():
    """Handle a chat message, persist it, and return an AI response."""
    try:
        data         = request.get_json() or {}
        user_message = data.get('message', '').strip()
        history      = data.get('history', [])
        user_id      = session.get('user_id')

        if not user_message:
            return jsonify({'error': 'Empty message'}), 400

        # Save user message to DB (only for logged-in users)
        if user_id:
            try:
                _save_message(user_id, 'user', user_message)
            except Exception:
                pass

        from app.services.chatbot_service import get_chatbot_response
        result = get_chatbot_response(
            user_message,
            conversation_history=history,
            user_id=user_id,
        )

        reply = result['response']

        # Save bot reply to DB
        if user_id:
            try:
                _save_message(user_id, 'model', reply)
            except Exception:
                pass

        return jsonify({
            'response':    reply,
            'source':      result['source'],
            'category':    result['category'],
            'intent':      result.get('intent', 'general'),
            'suggestions': result.get('suggestions', []),
            'timestamp':   datetime.now().isoformat(),
        })

    except Exception as e:
        return jsonify({
            'response':    ('Sorry, I encountered an error. Please try again or '
                            'contact the scholarship office at (049) 576-1234.'),
            'source':      'error',
            'category':    'error',
            'intent':      'error',
            'suggestions': [],
            'timestamp':   datetime.now().isoformat(),
        }), 500


@chatbot_bp.route('/clear-history', methods=['POST'])
def clear_history():
    """Delete all chat history for the current user."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    try:
        from app import db
        from app.models.chat_history import ChatHistory
        ChatHistory.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@chatbot_bp.route('/api/faq')
def get_faqs():
    """Return FAQ list with live scholarship count."""
    try:
        from app.models import Scholarship
        from app.models.scholarship import ScholarshipStatus
        count = (Scholarship.query
                 .filter_by(status=ScholarshipStatus.ACTIVE)
                 .filter(Scholarship.application_deadline > datetime.utcnow())
                 .count())
    except Exception:
        count = 0

    return jsonify({
        'faqs': {
            "What scholarships are currently available?": "scholarship",
            "How do I apply for a scholarship?":          "application",
            "What documents do I need?":                  "documents",
            "How do I check my application status?":      "status",
            "What are the eligibility requirements?":     "scholarship",
            "How do I get my account verified?":          "account",
            "What is the application deadline?":          "scholarship",
            "Where is the scholarship office?":           "contact",
        },
        'open_scholarship_count': count,
    })

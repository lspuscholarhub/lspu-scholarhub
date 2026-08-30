from flask import Blueprint, render_template, session
from app import db

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Home page — shows live active scholarships, respecting visibility rules."""
    from app.models import Scholarship, User
    from app.models.scholarship import ScholarshipStatus
    from datetime import datetime

    # Get the current student's ID if logged in (needed for visibility check)
    student_id = None
    if session.get('user_type') == 'student':
        user = User.query.get(session['user_id'])
        student_id = user.student_id if user else None

    all_active = (Scholarship.query
                  .filter_by(status=ScholarshipStatus.ACTIVE)
                  .filter(
                      db.or_(
                          Scholarship.application_deadline > datetime.utcnow(),
                          Scholarship.application_deadline.is_(None)
                      )
                  )
                  .order_by(
                      db.case((Scholarship.application_deadline.is_(None), 1), else_=0),
                      Scholarship.application_deadline.asc()
                  )
                  .all())

    # Apply visibility filter:
    # - Admin/staff see everything
    # - Logged-out users and students only see non-hidden scholarships
    #   (or hidden ones they're specifically allowed to see)
    role = session.get('user_type')
    if role in ('admin', 'staff'):
        recent_scholarships = all_active[:4]
    else:
        recent_scholarships = [s for s in all_active if s.is_visible_to(student_id)][:4]

    return render_template('index.html', recent_scholarships=recent_scholarships)

@main_bp.route('/contact')
def contact():
    """Contact page"""
    return render_template('contact.html')

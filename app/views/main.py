from flask import Blueprint, render_template, session, request, flash, redirect, url_for, jsonify
from app import db, limiter

main_bp = Blueprint('main', __name__)

@main_bp.route('/health')
def health():
    """Health check endpoint for uptime monitoring."""
    try:
        from sqlalchemy import text
        with db.engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        return jsonify({'status': 'healthy', 'database': 'connected'}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503


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

@main_bp.route('/contact', methods=['GET', 'POST'])
@limiter.limit('10 per hour')
def contact():
    """Contact page with form that emails the scholarship office."""
    if request.method == 'POST':
        name       = request.form.get('name', '').strip()
        email      = request.form.get('email', '').strip()
        student_id = request.form.get('student_id', '').strip()
        subject    = request.form.get('subject', '').strip()
        message    = request.form.get('message', '').strip()

        if not all([name, email, subject, message]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('main.contact'))

        # Send email to the scholarship office
        try:
            from app.services.notification_service import notification_service
            sid_line = f'<br><strong>Student ID:</strong> {student_id}' if student_id else ''
            html = f"""
            <h2>📩 New Contact Form Message</h2>
            <table style="border-collapse:collapse;">
              <tr><td style="padding:4px 12px 4px 0;font-weight:bold;">From:</td><td>{name}</td></tr>
              <tr><td style="padding:4px 12px 4px 0;font-weight:bold;">Email:</td><td><a href="mailto:{email}">{email}</a></td></tr>
              {sid_line}
              <tr><td style="padding:4px 12px 4px 0;font-weight:bold;">Subject:</td><td>{subject}</td></tr>
            </table>
            <hr>
            <p>{message}</p>
            <hr>
            <p style="color:#888;font-size:.85rem;">Sent via LSPU ScholarHub Contact Form</p>
            """
            notification_service.send_email(
                'lspu.scholarhub@gmail.com',
                f'[ScholarHub Contact] {subject} — {name}',
                html,
            )
            flash('Your message has been sent! We will get back to you soon.', 'success')
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f'Contact form email failed: {e}')
            flash('Your message was received. We will get back to you soon.', 'success')

        return redirect(url_for('main.contact'))

    return render_template('contact.html')

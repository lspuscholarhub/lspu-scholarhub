"""
Scholarship Management Service for LSPU ScholarHub
Handles CRUD operations for scholarships, aligned with the Scholarship model.
"""

from datetime import datetime, timedelta
from app import db
from app.models import Scholarship, ScholarshipApplication, User
from app.models.scholarship import ScholarshipStatus, ApplicationStatus
import logging

logger = logging.getLogger(__name__)


class ScholarshipService:

    def create_scholarship(self, scholarship_data):
        """Create a new scholarship."""
        try:
            scholarship = Scholarship(
                title=scholarship_data['title'],
                description=scholarship_data['description'],
                eligibility_criteria=scholarship_data.get('eligibility_criteria', ''),
                benefits=scholarship_data.get('benefits', ''),
                award_amount=scholarship_data.get('award_amount'),
                max_applicants=scholarship_data.get('max_applicants'),
                application_deadline=datetime.strptime(
                    scholarship_data['application_deadline'], '%Y-%m-%d'
                ),
                status=ScholarshipStatus.ACTIVE,
                created_by=scholarship_data['created_by'],
            )
            db.session.add(scholarship)
            db.session.commit()
            logger.info(f"Scholarship created: {scholarship.title}")
            return {'success': True, 'scholarship': scholarship}
        except Exception as e:
            logger.error(f"Error creating scholarship: {e}")
            db.session.rollback()
            return {'success': False, 'message': str(e)}

    def update_scholarship(self, scholarship_id, scholarship_data):
        """Update an existing scholarship."""
        try:
            scholarship = Scholarship.query.get(scholarship_id)
            if not scholarship:
                return {'success': False, 'message': 'Scholarship not found'}

            scholarship.title                = scholarship_data.get('title', scholarship.title)
            scholarship.description          = scholarship_data.get('description', scholarship.description)
            scholarship.award_amount         = scholarship_data.get('award_amount', scholarship.award_amount)
            scholarship.max_applicants       = scholarship_data.get('max_applicants', scholarship.max_applicants)
            scholarship.eligibility_criteria = scholarship_data.get('eligibility_criteria', scholarship.eligibility_criteria)
            scholarship.benefits             = scholarship_data.get('benefits', scholarship.benefits)

            if scholarship_data.get('application_deadline'):
                scholarship.application_deadline = datetime.strptime(
                    scholarship_data['application_deadline'], '%Y-%m-%d'
                )
            if scholarship_data.get('status'):
                scholarship.status = ScholarshipStatus(scholarship_data['status'])

            db.session.commit()
            logger.info(f"Scholarship updated: {scholarship.title}")
            return {'success': True, 'scholarship': scholarship}
        except Exception as e:
            logger.error(f"Error updating scholarship: {e}")
            db.session.rollback()
            return {'success': False, 'message': str(e)}

    def delete_scholarship(self, scholarship_id):
        """Delete a scholarship (blocked if pending applications exist)."""
        try:
            scholarship = Scholarship.query.get(scholarship_id)
            if not scholarship:
                return {'success': False, 'message': 'Scholarship not found'}

            pending = ScholarshipApplication.query.filter_by(
                scholarship_id=scholarship_id,
                status=ApplicationStatus.PENDING,
            ).count()
            if pending:
                return {
                    'success': False,
                    'message': f'Cannot delete: {pending} pending application(s) exist.',
                }

            db.session.delete(scholarship)
            db.session.commit()
            logger.info(f"Scholarship deleted: {scholarship.title}")
            return {'success': True, 'message': 'Scholarship deleted successfully'}
        except Exception as e:
            logger.error(f"Error deleting scholarship: {e}")
            db.session.rollback()
            return {'success': False, 'message': str(e)}

    def get_all_scholarships(self, include_inactive=False):
        """Return all scholarships, optionally including inactive/closed ones."""
        try:
            query = Scholarship.query
            if not include_inactive:
                query = query.filter_by(status=ScholarshipStatus.ACTIVE)
            scholarships = query.order_by(Scholarship.application_deadline.desc()).all()
            return {'success': True, 'scholarships': scholarships}
        except Exception as e:
            logger.error(f"Error getting scholarships: {e}")
            return {'success': False, 'message': str(e)}

    def get_scholarship_by_id(self, scholarship_id):
        """Return a single scholarship by primary key."""
        try:
            scholarship = Scholarship.query.get(scholarship_id)
            if not scholarship:
                return {'success': False, 'message': 'Scholarship not found'}
            return {'success': True, 'scholarship': scholarship}
        except Exception as e:
            logger.error(f"Error getting scholarship: {e}")
            return {'success': False, 'message': str(e)}

    def get_scholarship_statistics(self, scholarship_id=None):
        """Return application statistics for one or all scholarships."""
        try:
            if scholarship_id:
                scholarship = Scholarship.query.get(scholarship_id)
                if not scholarship:
                    return {'success': False, 'message': 'Scholarship not found'}

                apps     = ScholarshipApplication.query.filter_by(scholarship_id=scholarship_id).all()
                approved = [a for a in apps if a.status == ApplicationStatus.APPROVED]
                stats = {
                    'total_applications': len(apps),
                    'pending':      sum(1 for a in apps if a.status == ApplicationStatus.PENDING),
                    'under_review': sum(1 for a in apps if a.status == ApplicationStatus.UNDER_REVIEW),
                    'approved':     len(approved),
                    'rejected':     sum(1 for a in apps if a.status == ApplicationStatus.REJECTED),
                    'max_applicants':  scholarship.max_applicants,
                    'available_slots': (scholarship.max_applicants - len(approved)) if scholarship.max_applicants else None,
                    'fill_rate': (len(approved) / scholarship.max_applicants * 100) if scholarship.max_applicants else 0,
                }
                return {'success': True, 'statistics': stats}
            else:
                scholarships = Scholarship.query.filter_by(status=ScholarshipStatus.ACTIVE).all()
                apps = ScholarshipApplication.query.all()
                stats = {
                    'total_scholarships': len(scholarships),
                    'total_applications': len(apps),
                    'total_approved': sum(1 for a in apps if a.status == ApplicationStatus.APPROVED),
                    'total_pending':  sum(1 for a in apps if a.status == ApplicationStatus.PENDING),
                    'total_rejected': sum(1 for a in apps if a.status == ApplicationStatus.REJECTED),
                }
                return {'success': True, 'statistics': stats}
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {'success': False, 'message': str(e)}

    def get_upcoming_deadlines(self, days=30):
        """Return active scholarships whose deadline falls within the next N days."""
        try:
            cutoff = datetime.utcnow() + timedelta(days=days)
            scholarships = Scholarship.query.filter(
                Scholarship.status == ScholarshipStatus.ACTIVE,
                Scholarship.application_deadline <= cutoff,
                Scholarship.application_deadline > datetime.utcnow(),
            ).order_by(Scholarship.application_deadline.asc()).all()
            return {'success': True, 'scholarships': scholarships}
        except Exception as e:
            logger.error(f"Error getting upcoming deadlines: {e}")
            return {'success': False, 'message': str(e)}


def add_existing_scholar_to_program(user, scholarship, staff_user_id, notes=None):
    """Add a registered student to a scholarship program directly.

    Creates a pre-approved application — the exact same record a normal approval
    would produce — so the student flows into batches, monitoring, reports and
    the 'My Scholarship' page with no special-casing anywhere downstream.

    Guards (mirroring the normal approval path):
      - student already has an ACTIVE application for this program → rejected
      - public-funding rule: one public scholarship per academic period
      - program must be accepting applications (or capacity is ignored — staff
        override is intentional here since the office controls the award)

    Returns (application, error_message). Exactly one is truthy.
    """
    from app.models import AcademicPeriod, ScholarshipBatch
    from app.services.batch_service import auto_assign_to_batch
    from app.views.scholarship import _active_public_application

    period = AcademicPeriod.get_current()

    dup = ScholarshipApplication.query.filter_by(
        scholarship_id=scholarship.id, applicant_id=user.id)
    if period:
        dup = dup.filter_by(academic_period_id=period.id)
    dup = dup.filter(ScholarshipApplication.status.in_(
        [ApplicationStatus.PENDING, ApplicationStatus.UNDER_REVIEW,
         ApplicationStatus.APPROVED])).first()
    if dup:
        return None, (f'{user.get_full_name()} already has an active application '
                      f'for "{scholarship.title}" in the current period.')

    if scholarship.funding_type == 'public':
        held = _active_public_application(user.id)
        if held:
            return None, (f'{user.get_full_name()} already holds the public scholarship '
                          f'"{held.scholarship.title}" for this academic period. '
                          'Only one public scholarship is allowed per student per period.')

    application = ScholarshipApplication(
        scholarship_id=scholarship.id,
        applicant_id=user.id,
        application_data={
            'source': 'existing_scholar',
            'declared_program': user.existing_scholarship_name,
            'added_by': staff_user_id,
        },
        status=ApplicationStatus.APPROVED,
        scholar_tag='active',
        scholar_status='active',
        submitted_at=datetime.utcnow(),
        reviewed_at=datetime.utcnow(),
        reviewed_by=staff_user_id,
        review_notes=notes or 'Added directly by the Scholarship Office.',
        final_decision_date=datetime.utcnow(),
        approved_at=datetime.utcnow(),
        is_active=True,
        academic_period_id=period.id if period else None,
        campus_id=user.campus_id,
    )
    db.session.add(application)
    db.session.flush()

    scholarship.increment_applicants()

    batch = auto_assign_to_batch(application)
    db.session.commit()

    # Notify the student (non-critical)
    try:
        from app.services.notification_service import notification_service as _ns
        _ns.send_application_status_update(
            user.email, user.phone_number or '', user.id,
            scholarship.title, 'approved',
            'You have been added to this scholarship program by the Scholarship Office.',
        )
    except Exception:
        pass

    return application, None


# Module-level singleton
scholarship_service = ScholarshipService()

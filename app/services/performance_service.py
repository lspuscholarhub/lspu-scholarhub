"""
Scholar Performance Tracking Service for LSPU ScholarHub
Handles scholar performance monitoring and compliance
"""

from datetime import datetime, timedelta
from flask import current_app
from app import db
from app.models import User, ScholarshipApplication, Scholarship
from app.services.notification_service import notification_service
import logging

logger = logging.getLogger(__name__)

class PerformanceService:
    """
    LSPU Grading Scale (lower number = better grade):
      1.00–1.25  Excellent
      1.50–1.75  Very Good
      2.00–2.25  Satisfactory
      2.50–2.75  Fair
      3.00       Passed  ← boundary; above this is at-risk
      4.00       Failed  ← termination warning
      5.00       Failed               ← termination warning

    At-risk threshold: GWA > 3.00
    """
    def __init__(self):
        # LSPU thresholds — higher GWA = worse performance
        self.GWA_GOOD_STANDING  = 3.00   # GWA <= 3.00 → good standing
        self.GWA_WARNING        = 3.00   # GWA > 3.00  → at-risk / warning
        self.GWA_PROBATION      = 3.75   # GWA > 3.75  → probation (between 3.00 and 4.00)
        self.GWA_TERMINATION    = 4.00   # GWA >= 4.00 → termination warning (Failed)

        # Compliance requirements
        self.RENEWAL_DEADLINE_DAYS = 30
        self.DOCUMENT_RESUBMISSION_DAYS = 7
    
    def track_scholar_performance(self, scholar_id, semester_gwa, academic_year, semester):
        """Track and update scholar performance using LSPU GWA scale."""
        try:
            scholar = User.query.get(scholar_id)
            if not scholar:
                return {'success': False, 'message': 'Scholar not found'}
            
            # Get active scholarship
            active_application = ScholarshipApplication.query.filter(
                ScholarshipApplication.applicant_id == scholar_id,
                ScholarshipApplication.status == 'approved',
                ScholarshipApplication.is_active == True
            ).first()
            
            if not active_application:
                return {'success': False, 'message': 'No active scholarship found'}
            
            # Create performance record
            performance_record = {
                'scholar_id': scholar_id,
                'scholarship_id': active_application.scholarship_id,
                'semester_gwa': semester_gwa,
                'academic_year': academic_year,
                'semester': semester,
                'recorded_at': datetime.utcnow(),
                'status': self._determine_performance_status(semester_gwa)
            }
            
            # Update scholar status based on GWA
            status_update = self._update_scholar_status(scholar_id, semester_gwa)
            
            # Check for alerts
            alerts = self._check_performance_alerts(scholar_id, semester_gwa)
            
            # Send notifications if needed
            if alerts:
                self._send_performance_notifications(scholar, active_application, alerts, semester_gwa)
            
            logger.info(f"Performance tracked for scholar {scholar_id}: GWA {semester_gwa}")
            
            return {
                'success': True,
                'performance_record': performance_record,
                'status_update': status_update,
                'alerts': alerts
            }
            
        except Exception as e:
            logger.error(f"Error tracking scholar performance: {str(e)}")
            return {'success': False, 'message': f'Error tracking performance: {str(e)}'}
    
    def _determine_performance_status(self, gwa):
        """
        Determine performance status based on LSPU GWA.
        Lower GWA = better (1.00 is best, 5.00 is worst).
        """
        if gwa <= self.GWA_GOOD_STANDING:
            return 'good_standing'
        elif gwa < self.GWA_PROBATION:
            return 'at_risk'
        elif gwa < self.GWA_TERMINATION:
            return 'probation'
        else:
            return 'termination_warning'
    
    def _update_scholar_status(self, scholar_id, gwa):
        """Update scholar status based on LSPU GWA performance."""
        try:
            scholar = User.query.get(scholar_id)
            active_application = ScholarshipApplication.query.filter(
                ScholarshipApplication.applicant_id == scholar_id,
                ScholarshipApplication.status == 'approved',
                ScholarshipApplication.is_active == True
            ).first()
            
            if not active_application:
                return {'updated': False, 'reason': 'No active scholarship'}
            
            previous_status = active_application.scholar_status
            new_status = None
            
            # LSPU scale: lower = better; at-risk starts above 3.00
            if gwa >= self.GWA_TERMINATION:
                new_status = 'termination_warning'   # 4.00+ (Failed)
            elif gwa > self.GWA_PROBATION:
                new_status = 'probation'              # 3.75 < GWA < 4.00
            elif gwa > self.GWA_GOOD_STANDING:
                new_status = 'at_risk'                # 3.00 < GWA <= 3.75
            else:
                new_status = 'active'                 # GWA <= 3.00 (good standing)
            
            if previous_status != new_status:
                active_application.scholar_status = new_status
                active_application.status_updated_at = datetime.utcnow()
                db.session.commit()
                
                return {
                    'updated': True,
                    'previous_status': previous_status,
                    'new_status': new_status
                }
            
            return {'updated': False, 'reason': 'No status change needed'}
            
        except Exception as e:
            logger.error(f"Error updating scholar status: {str(e)}")
            return {'updated': False, 'reason': str(e)}
    
    def _check_performance_alerts(self, scholar_id, gwa):
        """Check for performance alerts using LSPU GWA scale."""
        alerts = []
        
        if gwa >= self.GWA_TERMINATION:
            alerts.append({
                'type': 'termination_warning',
                'severity': 'critical',
                'message': (
                    f'GWA of {gwa:.2f} is at Failed level. '
                    'Scholarship is at risk of termination.'
                )
            })
        elif gwa > self.GWA_PROBATION:
            alerts.append({
                'type': 'probation',
                'severity': 'high',
                'message': (
                    f'GWA of {gwa:.2f} is above 3.75. Scholar placed on probation.'
                )
            })
        elif gwa > self.GWA_GOOD_STANDING:
            alerts.append({
                'type': 'at_risk',
                'severity': 'medium',
                'message': (
                    f'GWA of {gwa:.2f} exceeds the 3.00 passing threshold. '
                    'Academic improvement is required to maintain scholarship.'
                )
            })
        
        return alerts
    
    def _send_performance_notifications(self, scholar, application, alerts, gwa):
        """Send performance notifications using LSPU GWA terminology."""
        try:
            subject = f"Performance Alert — {scholar.first_name} {scholar.last_name}"
            
            alert_messages = [alert['message'] for alert in alerts]
            message = f"""
            <h2>⚠️ Performance Alert</h2>
            <p>Dear <strong>{scholar.first_name} {scholar.last_name}</strong>,</p>
            <p>We are writing to inform you about your academic performance for your scholarship.</p>
            <p><strong>Current GWA:</strong> {gwa:.2f}</p>
            <p><strong>Scholarship:</strong> {application.scholarship.title}</p>
            <p><strong>Alert(s):</strong></p>
            <ul>
                {''.join([f'<li>{msg}</li>' for msg in alert_messages])}
            </ul>
            <p>Please contact the scholarship office immediately to discuss your academic standing.</p>
            <p>Best regards,<br><strong>LSPU Scholarship Committee</strong></p>
            """
            
            notification_service.send_email(scholar.email, subject, message)
            
            notification_service.create_in_app_notification(
                scholar.id,
                "Performance Alert",
                f"Your GWA ({gwa:.2f}) has triggered a performance alert. Please check your email for details.",
                "performance",
                "/student/performance"
            )
            
        except Exception as e:
            logger.error(f"Error sending performance notifications: {str(e)}")
    
    def check_compliance_requirements(self, scholar_id):
        """Check scholar compliance requirements"""
        try:
            scholar = User.query.get(scholar_id)
            if not scholar:
                return {'success': False, 'message': 'Scholar not found'}
            
            active_application = ScholarshipApplication.query.filter(
                ScholarshipApplication.applicant_id == scholar_id,
                ScholarshipApplication.status == 'approved',
                ScholarshipApplication.is_active == True
            ).first()
            
            if not active_application:
                return {'success': False, 'message': 'No active scholarship found'}
            
            compliance_issues = []
            
            # Check document compliance
            document_issues = self._check_document_compliance(scholar_id)
            if document_issues:
                compliance_issues.extend(document_issues)
            
            # Check renewal deadline
            renewal_issue = self._check_renewal_deadline(active_application)
            if renewal_issue:
                compliance_issues.append(renewal_issue)
            
            # Check grade submission
            grade_issue = self._check_grade_submission(scholar_id)
            if grade_issue:
                compliance_issues.append(grade_issue)
            
            # Update compliance status
            compliance_status = 'compliant' if not compliance_issues else 'non_compliant'
            active_application.compliance_status = compliance_status
            active_application.last_compliance_check = datetime.utcnow()
            db.session.commit()
            
            return {
                'success': True,
                'compliance_status': compliance_status,
                'compliance_issues': compliance_issues
            }
            
        except Exception as e:
            logger.error(f"Error checking compliance: {str(e)}")
            return {'success': False, 'message': f'Error checking compliance: {str(e)}'}
    
    def _check_document_compliance(self, scholar_id):
        """Check document compliance"""
        issues = []
        
        try:
            from app.services.document_service import document_service
            documents = document_service.get_user_documents(scholar_id)
            
            required_documents = ['transcript', 'good_moral']
            
            for doc_type in required_documents:
                doc_found = False
                for doc in documents:
                    if doc['category'] == doc_type:
                        # Check if document is recent (within 6 months)
                        if (datetime.utcnow() - doc['uploaded_at']).days > 180:
                            issues.append({
                                'type': 'document_expired',
                                'severity': 'medium',
                                'message': f'{doc_type.replace("_", " ").title()} document is expired and needs resubmission.',
                                'action_required': 'upload_new_document'
                            })
                        doc_found = True
                        break
                
                if not doc_found:
                    issues.append({
                        'type': 'missing_document',
                        'severity': 'high',
                        'message': f'{doc_type.replace("_", " ").title()} document is missing.',
                        'action_required': 'upload_document'
                    })
            
        except Exception as e:
            logger.error(f"Error checking document compliance: {str(e)}")
        
        return issues
    
    def _check_renewal_deadline(self, application):
        """Check scholarship renewal deadline"""
        try:
            # Assuming renewal deadline is 1 year after approval
            renewal_deadline = application.approved_at + timedelta(days=365)
            days_until_renewal = (renewal_deadline - datetime.utcnow()).days
            
            if days_until_renewal <= self.RENEWAL_DEADLINE_DAYS:
                severity = 'critical' if days_until_renewal <= 7 else 'high'
                
                return {
                    'type': 'renewal_deadline',
                    'severity': severity,
                    'message': f'Scholarship renewal deadline in {days_until_renewal} days.',
                    'action_required': 'renew_scholarship',
                    'deadline': renewal_deadline
                }
            
        except Exception as e:
            logger.error(f"Error checking renewal deadline: {str(e)}")
        
        return None
    
    def _check_grade_submission(self, scholar_id):
        """Check if grades have been submitted for current semester"""
        try:
            # This would typically check against the school's grading system
            # For now, we'll simulate the check
            
            current_semester = self._get_current_semester()
            
            # Simulate grade check (would integrate with actual school system)
            grades_submitted = True  # This would be determined by actual integration
            
            if not grades_submitted:
                return {
                    'type': 'missing_grades',
                    'severity': 'medium',
                    'message': f'Grades for {current_semester} have not been submitted.',
                    'action_required': 'submit_grades'
                }
            
        except Exception as e:
            logger.error(f"Error checking grade submission: {str(e)}")
        
        return None
    
    def _get_current_semester(self):
        """Get current academic semester"""
        now = datetime.utcnow()
        year = now.year
        
        # Simple semester determination (would be more complex in reality)
        if now.month >= 6 and now.month <= 10:
            return f"First Semester {year}"
        elif now.month >= 11 or now.month <= 3:
            return f"Second Semester {year}" if now.month <= 3 else f"Second Semester {year-1}"
        else:
            return f"Inter-Semester {year}"
    
    def get_performance_trends(self, scholar_id):
        """Get performance trends for a scholar"""
        try:
            # This would typically query performance records from database
            # For now, we'll return simulated data
            
            trends = {
                'gpa_trend': [
                    {'semester': 'First Semester 2023', 'gpa': 1.75},
                    {'semester': 'Second Semester 2023', 'gpa': 1.80},
                    {'semester': 'First Semester 2024', 'gpa': 1.65}
                ],
                'status_changes': [
                    {'date': '2023-06-15', 'status': 'active'},
                    {'date': '2024-01-20', 'status': 'warning'},
                    {'date': '2024-03-10', 'status': 'probation'}
                ],
                'compliance_history': [
                    {'date': '2023-06-01', 'status': 'compliant'},
                    {'date': '2024-02-15', 'status': 'non_compliant'},
                    {'date': '2024-03-01', 'status': 'compliant'}
                ]
            }
            
            return {'success': True, 'trends': trends}
            
        except Exception as e:
            logger.error(f"Error getting performance trends: {str(e)}")
            return {'success': False, 'message': f'Error getting trends: {str(e)}'}
    
    def generate_performance_report(self, scholar_id=None, date_range=None):
        """Generate performance report"""
        try:
            if scholar_id:
                # Individual scholar report
                scholar = User.query.get(scholar_id)
                if not scholar:
                    return {'success': False, 'message': 'Scholar not found'}
                
                active_application = ScholarshipApplication.query.filter(
                    ScholarshipApplication.applicant_id == scholar_id,
                    ScholarshipApplication.status == 'approved',
                    ScholarshipApplication.is_active == True
                ).first()
                
                if not active_application:
                    return {'success': False, 'message': 'No active scholarship found'}
                
                report = {
                    'scholar_info': {
                        'name': f"{scholar.first_name} {scholar.last_name}",
                        'email': scholar.email,
                        'student_id': scholar.student_id,
                        'course': scholar.course,
                        'year_level': scholar.year_level
                    },
                    'scholarship_info': {
                        'title': active_application.scholarship.title,
                        'award_amount': active_application.scholarship.award_amount,
                        'status': active_application.scholar_status,
                        'approved_at': active_application.approved_at
                    },
                    'performance_data': self.get_performance_trends(scholar_id),
                    'compliance_data': self.check_compliance_requirements(scholar_id)
                }
                
                return {'success': True, 'report': report}
            
            else:
                # System-wide performance report
                active_scholars = db.session.query(ScholarshipApplication).filter(
                    ScholarshipApplication.status == 'approved',
                    ScholarshipApplication.is_active == True
                ).all()
                
                total_scholars = len(active_scholars)
                active_count = len([s for s in active_scholars if s.scholar_status == 'active'])
                probation_count = len([s for s in active_scholars if s.scholar_status == 'probation'])
                warning_count = len([s for s in active_scholars if s.scholar_status == 'warning'])
                termination_count = len([s for s in active_scholars if s.scholar_status == 'termination_warning'])
                
                report = {
                    'summary': {
                        'total_scholars': total_scholars,
                        'active_scholars': active_count,
                        'on_probation': probation_count,
                        'warnings': warning_count,
                        'termination_warnings': termination_count,
                        'success_rate': (active_count / total_scholars * 100) if total_scholars > 0 else 0
                    },
                    'generated_at': datetime.utcnow()
                }
                
                return {'success': True, 'report': report}
                
        except Exception as e:
            logger.error(f"Error generating performance report: {str(e)}")
            return {'success': False, 'message': f'Error generating report: {str(e)}'}

# Global performance service instance
performance_service = PerformanceService()

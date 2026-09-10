"""
Multi-Channel Notification Service for LSPU ScholarHub
Handles email, SMS, and in-app notifications
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from flask import current_app
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.email_config = {
            'server': os.environ.get('MAIL_SERVER', 'smtp.gmail.com'),
            'port': int(os.environ.get('MAIL_PORT', 587)),
            'username': os.environ.get('MAIL_USERNAME'),
            'password': os.environ.get('MAIL_PASSWORD'),
            'use_tls': os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
        }

    def _get_base_url(self):
        """Get the application's base URL for email links.

        Priority:
          1. BASE_URL environment variable (set in production)
          2. RAILWAY_PUBLIC_DOMAIN (auto-set by Railway)
          3. Flask url_for with _external=True (when request context is available)
          4. Fallback to localhost:5000 (development only)
        """
        # Check for explicitly configured base URL
        base_url = os.environ.get('BASE_URL', '').strip().rstrip('/')
        if base_url:
            return base_url

        # Check Railway's auto-set domain variable
        railway_domain = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '').strip()
        if railway_domain:
            return f'https://{railway_domain}'

        # Try to use Flask's url_for (requires request context)
        try:
            from flask import url_for
            # url_for with _external=True generates the full URL
            return url_for('main.index', _external=True).rstrip('/')
        except RuntimeError:
            # No request context (e.g., called from background thread)
            pass
        except Exception:
            pass

        # Fallback for development
        return 'http://localhost:5000'

    def send_email(self, to_email, subject, message, template_data=None, attachments=None):
        """
        Send email notification.
        Priority:
          1. Resend HTTP API  — if RESEND_API_KEY is set (instant activation, free tier)
          2. Brevo HTTP API   — if BREVO_API_KEY is set (bypasses SMTP port restrictions)
          3. SMTP             — fallback for local development

        attachments: optional list of dicts {'filename': str, 'content_base64': str}
        (base64-encoded by the caller; supported by Brevo and Resend APIs)
        """
        html_content = self._generate_email_html(message, template_data)

        # ── Option 1: Resend API (works instantly on Railway) ─────────────────
        resend_key = os.environ.get('RESEND_API_KEY', '').strip()
        if resend_key:
            return self._send_via_resend_api(to_email, subject, html_content, resend_key,
                                             attachments=attachments)

        # ── Option 2: Brevo HTTP API ──────────────────────────────────────────
        brevo_key = os.environ.get('BREVO_API_KEY', '').strip()
        if brevo_key:
            return self._send_via_brevo_api(to_email, subject, html_content, brevo_key,
                                            attachments=attachments)

        # ── Option 3: SMTP fallback (local dev) ───────────────────────────────
        try:
            if not self.email_config['username'] or not self.email_config['password']:
                logger.warning("Email credentials not configured. Skipping email send.")
                return {'success': False, 'message': 'Email not configured'}

            msg = MIMEMultipart()
            msg['From']    = "LSPU ScholarHub <lspu.scholarhub@gmail.com>"
            msg['To']      = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(html_content, 'html'))

            server = smtplib.SMTP(self.email_config['server'], self.email_config['port'])
            if self.email_config['use_tls']:
                server.starttls()
            server.login(self.email_config['username'], self.email_config['password'])
            server.send_message(msg)
            server.quit()

            logger.info(f"Email sent via SMTP to {to_email}")
            return {'success': True, 'message': 'Email sent successfully'}

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return {'success': False, 'message': f'Email send failed: {str(e)}'}

    def _send_via_resend_api(self, to_email, subject, html_content, api_key, attachments=None):
        """Send email via Resend HTTP API — instant activation, free 3000 emails/month."""
        import urllib.request
        import urllib.error
        import json
        import base64

        body = {
            'from':    'LSPU ScholarHub <onboarding@resend.dev>',
            'to':      [to_email],
            'subject': subject,
            'html':    html_content,
        }
        if attachments:
            body['attachments'] = [
                {'filename': a['filename'], 'content': a['content_base64']}
                for a in attachments
            ]
        payload = json.dumps(body).encode('utf-8')

        credentials = base64.b64encode(f':{api_key}'.encode()).decode()

        req = urllib.request.Request(
            'https://api.resend.com/emails',
            data=payload,
            method='POST',
        )
        req.add_header('Authorization', f'Bearer {api_key}')
        req.add_header('Content-Type',  'application/json')

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = json.loads(resp.read().decode('utf-8'))
                email_id = body.get('id', '')
                logger.info(f"Email sent via Resend to {to_email} | id: {email_id}")
                return {'success': True, 'message': f'Email sent via Resend (id: {email_id})'}

        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read().decode('utf-8'))
                err_msg  = err_body.get('message', str(e))
            except Exception:
                err_msg = str(e)
            logger.error(f"Resend API error {e.code}: {err_msg}")
            return {'success': False, 'message': f'Resend API error {e.code}: {err_msg}'}

        except Exception as e:
            logger.error(f"Resend API request failed: {e}")
            return {'success': False, 'message': f'Resend API failed: {e}'}

    def _send_via_brevo_api(self, to_email, subject, html_content, api_key, attachments=None):
        """Send email via Brevo HTTP API — works on Railway (no SMTP ports needed)."""
        import urllib.request
        import urllib.error
        import json

        body = {
            'sender':   {'name': 'LSPU ScholarHub', 'email': 'lspu.scholarhub@gmail.com'},
            'to':       [{'email': to_email}],
            'subject':  subject,
            'htmlContent': html_content,
        }
        if attachments:
            body['attachment'] = [
                {'name': a['filename'], 'content': a['content_base64']}
                for a in attachments
            ]
        payload = json.dumps(body).encode('utf-8')

        req = urllib.request.Request(
            'https://api.brevo.com/v3/smtp/email',
            data=payload,
            method='POST',
        )
        req.add_header('accept',       'application/json')
        req.add_header('api-key',      api_key)
        req.add_header('content-type', 'application/json')

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = json.loads(resp.read().decode('utf-8'))
                msg_id = body.get('messageId', '')
                logger.info(f"Email sent via Brevo API to {to_email} | id: {msg_id}")
                return {'success': True, 'message': f'Email sent via Brevo (id: {msg_id})'}

        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read().decode('utf-8'))
                err_msg  = err_body.get('message', str(e))
            except Exception:
                err_msg = str(e)
            logger.error(f"Brevo API error {e.code}: {err_msg}")
            return {'success': False, 'message': f'Brevo API error {e.code}: {err_msg}'}

        except Exception as e:
            logger.error(f"Brevo API request failed: {e}")
            return {'success': False, 'message': f'Brevo API failed: {e}'}
    
    def send_sms(self, phone_number, message):
        """
        Send SMS via Semaphore (PH gateway) with Twilio as fallback.

        Priority:
          1. Semaphore — if SEMAPHORE_API_KEY is set (recommended for PH numbers)
          2. Twilio    — if TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN are set
          3. Log only  — if neither is configured (development mode)

        Phone number is normalised to E.164 format (+63XXXXXXXXXX).
        """
        if not phone_number:
            logger.warning('SMS skipped: no phone number provided.')
            return {'success': False, 'message': 'No phone number'}

        # ── Normalise PH number to E.164 ──────────────────────────────────────
        digits = ''.join(c for c in str(phone_number) if c.isdigit())
        if digits.startswith('0') and len(digits) == 11:
            e164 = '+63' + digits[1:]          # 09XXXXXXXXX → +639XXXXXXXXX
        elif digits.startswith('63') and len(digits) == 12:
            e164 = '+' + digits                 # 639XXXXXXXXX → +639XXXXXXXXX
        elif digits.startswith('9') and len(digits) == 10:
            e164 = '+63' + digits               # 9XXXXXXXXX → +639XXXXXXXXX
        else:
            e164 = phone_number                 # use as-is

        semaphore_key = os.environ.get('SEMAPHORE_API_KEY', '').strip()
        twilio_sid    = os.environ.get('TWILIO_ACCOUNT_SID', '').strip()
        twilio_token  = os.environ.get('TWILIO_AUTH_TOKEN', '').strip()
        twilio_from   = os.environ.get('TWILIO_PHONE_NUMBER', '').strip()

        # ── Option 1: Semaphore ───────────────────────────────────────────────
        # Only use Semaphore if key is set AND not empty
        if semaphore_key and len(semaphore_key) > 10:
            result = self._send_via_semaphore(e164, message, semaphore_key)
            if result['success']:
                return result
            # If Semaphore fails, fall through to Twilio
            logger.warning(f'Semaphore failed, trying Twilio: {result["message"]}')

        # ── Option 2: Twilio ──────────────────────────────────────────────────
        if twilio_sid and twilio_token and twilio_from:
            return self._send_via_twilio(e164, message, twilio_sid, twilio_token, twilio_from)

        # ── Option 3: Email fallback — send SMS content via email ────────────
        # When no SMS gateway is configured, deliver the SMS message via email.
        # This demonstrates multi-channel notifications for thesis/demo purposes.
        # Real SMS activates automatically once SEMAPHORE_API_KEY is added to .env
        logger.info(f'[SMS fallback → email] To: {e164} | Message: {message}')

        # Try to find the user by phone number and send via email
        try:
            from app.models import User
            # Strip +63 to match stored format
            search_phone = e164.replace('+63', '0') if e164.startswith('+63') else e164
            user = User.query.filter_by(phone_number=search_phone).first()
            if user and user.email:
                fallback_subject = "LSPU ScholarHub — SMS Notification"
                fallback_body = f"""
                <div style="background:#fff3cd;border:1px solid #ffc107;border-radius:8px;
                            padding:16px;margin-bottom:16px;">
                  <p style="margin:0;font-size:.85rem;color:#856404;">
                    <strong>📱 SMS Notification</strong> — This message was sent to your
                    registered phone number ({search_phone}) via email because the SMS
                    gateway is not yet configured.
                  </p>
                </div>
                <p style="font-size:1rem;">{message}</p>
                """
                self.send_email(user.email, fallback_subject, fallback_body)
                return {
                    'success': True,
                    'message': 'SMS delivered via email fallback',
                    'provider': 'email_fallback',
                }
        except Exception as e:
            logger.warning(f'SMS email fallback failed: {e}')

        return {
            'success': False,
            'message': 'SMS gateway not configured. Add SEMAPHORE_API_KEY to .env to enable real SMS.',
            'provider': 'none',
        }

    def _send_via_semaphore(self, phone, message, api_key):
        """Send SMS via Semaphore PH gateway (https://semaphore.co)."""
        import urllib.request
        import urllib.parse
        import urllib.error
        import json

        sender = os.environ.get('SEMAPHORE_SENDER_NAME', '').strip()

        # Semaphore accepts local PH format (09XXXXXXXXX) or E.164
        ph_local = phone
        if phone.startswith('+63'):
            ph_local = '0' + phone[3:]

        params = {
            'apikey':  api_key,
            'number':  ph_local,
            'message': message,
        }
        if sender:
            params['sendername'] = sender

        payload = urllib.parse.urlencode(params).encode('utf-8')

        try:
            req = urllib.request.Request(
                'https://api.semaphore.co/api/v4/messages',
                data=payload,
                method='POST',
            )
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')

            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode('utf-8')
                data = json.loads(body)

            if isinstance(data, list) and data:
                status = data[0].get('status', '').lower()
                if status in ('pending', 'queued', 'sent', 'success'):
                    logger.info(f'Semaphore SMS sent to {ph_local} | status: {status}')
                    return {'success': True, 'message': f'SMS sent via Semaphore ({status})', 'provider': 'semaphore'}
                else:
                    logger.warning(f'Semaphore status: {status} | response: {data}')
                    return {'success': False, 'message': f'Semaphore: {status}', 'provider': 'semaphore'}
            elif isinstance(data, dict):
                # Error response
                errors = data.get('message', data.get('error', str(data)))
                logger.warning(f'Semaphore error response: {data}')
                return {'success': False, 'message': f'Semaphore: {errors}', 'provider': 'semaphore'}
            else:
                logger.warning(f'Semaphore unexpected response: {data}')
                return {'success': False, 'message': 'Unexpected Semaphore response', 'provider': 'semaphore'}

        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode('utf-8')
                logger.error(f'Semaphore HTTP {e.code}: {body}')
                if e.code == 500:
                    return {
                        'success': False,
                        'message': (
                            'Semaphore HTTP 500 — Your account email is likely not verified yet. '
                            'Log in to semaphore.co and click the verification link in your email. '
                            'Also ensure you have credits (top up at semaphore.co/payments).'
                        ),
                        'provider': 'semaphore',
                    }
                return {'success': False, 'message': f'Semaphore HTTP {e.code}: {body}', 'provider': 'semaphore'}
            except Exception:
                return {'success': False, 'message': f'Semaphore HTTP {e.code}', 'provider': 'semaphore'}

        except Exception as e:
            logger.error(f'Semaphore SMS failed: {e}')
            return {'success': False, 'message': f'Semaphore error: {e}', 'provider': 'semaphore'}

    def _send_via_twilio(self, phone, message, sid, token, from_number):
        """Send SMS via Twilio."""
        import urllib.request
        import urllib.parse
        import urllib.error
        import base64
        import json

        payload = urllib.parse.urlencode({
            'To':   phone,
            'From': from_number,
            'Body': message,
        }).encode('utf-8')

        url = f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json'
        credentials = base64.b64encode(f'{sid}:{token}'.encode()).decode()

        try:
            req = urllib.request.Request(url, data=payload, method='POST')
            req.add_header('Authorization', f'Basic {credentials}')
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')

            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            status = data.get('status', '')
            sid_msg = data.get('sid', '')
            logger.info(f'Twilio SMS sent to {phone} | status: {status} | sid: {sid_msg}')

            if status in ('queued', 'sent', 'delivered', 'accepted'):
                return {'success': True, 'message': f'SMS sent via Twilio ({status})', 'provider': 'twilio'}
            else:
                error_msg = data.get('message', status)
                logger.warning(f'Twilio unexpected status: {status} | {error_msg}')
                return {'success': False, 'message': f'Twilio: {error_msg}', 'provider': 'twilio'}

        except urllib.error.HTTPError as e:
            # Read the error body — Twilio puts the reason here
            try:
                error_body = json.loads(e.read().decode('utf-8'))
                error_msg  = error_body.get('message', str(e))
                error_code = error_body.get('code', e.code)
                logger.error(f'Twilio HTTP {e.code} error: [{error_code}] {error_msg}')

                # Common Twilio error codes with helpful messages
                hints = {
                    21608: 'Phone number is not verified. Add it at console.twilio.com → Verified Caller IDs',
                    21211: 'Invalid "To" phone number format.',
                    21214: 'Phone number is not a mobile number.',
                    20003: 'Authentication failed — check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN.',
                    21606: 'From number cannot send to this destination.',
                }
                hint = hints.get(error_code, '')
                full_msg = f'Twilio error {error_code}: {error_msg}' + (f' — {hint}' if hint else '')
                return {'success': False, 'message': full_msg, 'provider': 'twilio'}
            except Exception:
                logger.error(f'Twilio HTTP error {e.code}: {e}')
                return {'success': False, 'message': f'Twilio HTTP {e.code}: {e}', 'provider': 'twilio'}

        except Exception as e:
            logger.error(f'Twilio SMS failed: {e}')
            return {'success': False, 'message': f'Twilio error: {e}', 'provider': 'twilio'}
    
    def create_in_app_notification(self, user_id, title, message, category='general', action_url=None):
        """Create in-app notification"""
        try:
            from app import db
            from app.models import Notification
            from app.models.notification import NotificationType, NotificationChannel

            # Map category string to NotificationType enum (fall back to SYSTEM_ANNOUNCEMENT)
            type_map = {
                'application': NotificationType.APPLICATION_SUBMITTED,
                'deadline':    NotificationType.DEADLINE_REMINDER,
                'welcome':     NotificationType.NEW_SCHOLARSHIP,
                'performance': NotificationType.SYSTEM_ANNOUNCEMENT,
                'general':     NotificationType.SYSTEM_ANNOUNCEMENT,
            }
            notif_type = type_map.get(category, NotificationType.SYSTEM_ANNOUNCEMENT)

            notification = Notification(
                recipient_id=user_id,
                title=title,
                message=message,
                notification_type=notif_type,
                channel=NotificationChannel.IN_APP,
                is_read=False,
            )
            
            db.session.add(notification)
            db.session.commit()
            
            logger.info(f"In-app notification created for user {user_id}")
            return {'success': True, 'message': 'In-app notification created'}
            
        except Exception as e:
            logger.error(f"Failed to create in-app notification: {str(e)}")
            return {'success': False, 'message': f'Notification creation failed: {str(e)}'}
    
    def send_scholarship_application_received(self, user_email, user_phone, user_id, scholarship_name):
        """Send notification when application is received"""
        subject = f"Application Received - {scholarship_name}"
        message = f"""
        <h2>Application Received</h2>
        <p>Dear Student,</p>
        <p>Your application for <strong>{scholarship_name}</strong> has been successfully received.</p>
        <p><strong>Application Details:</strong></p>
        <ul>
            <li>Scholarship: {scholarship_name}</li>
            <li>Status: Under Review</li>
            <li>Submitted: {datetime.now().strftime('%B %d, %Y')}</li>
        </ul>
        <p>You can track your application status by logging into your LSPU ScholarHub account.</p>
        <p>Best regards,<br>LSPU Scholarship Committee</p>
        """
        
        # Send email
        email_result = self.send_email(user_email, subject, message)
        
        # Send SMS
        sms_message = f"LSPU: Your application for {scholarship_name} has been received. Track status online."
        sms_result = self.send_sms(user_phone, sms_message)
        
        # Create in-app notification
        in_app_result = self.create_in_app_notification(
            user_id, 
            "Application Received", 
            f"Your application for {scholarship_name} has been received and is now under review.",
            "application",
            "/student/applications"
        )
        
        return {
            'email': email_result,
            'sms': sms_result,
            'in_app': in_app_result
        }
    
    def send_application_status_update(self, user_email, user_phone, user_id, scholarship_name, status, notes=None):
        """Send notification when application status changes"""
        status_emoji = {
            'approved': '✅',
            'rejected': '❌',
            'under_review': '📋',
            'pending': '⏳'
        }
        
        subject = f"Application Status Update - {scholarship_name}"
        message = f"""
        <h2>Application Status Update {status_emoji.get(status, '📋')}</h2>
        <p>Dear Student,</p>
        <p>Your application for <strong>{scholarship_name}</strong> has been updated.</p>
        <p><strong>Status:</strong> {status.replace('_', ' ').title()}</p>
        {f'<p><strong>Notes:</strong> {notes}</p>' if notes else ''}
        <p>Please log into your LSPU ScholarHub account for more details.</p>
        <p>Best regards,<br>LSPU Scholarship Committee</p>
        """
        
        # Send email
        email_result = self.send_email(user_email, subject, message)
        
        # Send SMS
        sms_message = f"LSPU: Your {scholarship_name} application status: {status.replace('_', ' ').title()}. Check online for details."
        sms_result = self.send_sms(user_phone, sms_message)
        
        # Create in-app notification
        in_app_message = f"Your {scholarship_name} application status is now: {status.replace('_', ' ').title()}."
        if notes and notes.strip():
            in_app_message += f" Reason: {notes.strip()}"
        in_app_result = self.create_in_app_notification(
            user_id, 
            "Application Status Updated", 
            in_app_message,
            "application",
            "/student/applications"
        )
        
        return {
            'email': email_result,
            'sms': sms_result,
            'in_app': in_app_result
        }
    
    def send_deadline_reminder(self, user_email, user_phone, user_id, scholarship_name, deadline_date):
        """Send deadline reminder notification"""
        days_left = (deadline_date - datetime.now()).days
        
        subject = f"Deadline Reminder - {scholarship_name}"
        message = f"""
        <h2>⏰ Deadline Reminder</h2>
        <p>Dear Student,</p>
        <p>This is a reminder that the application deadline for <strong>{scholarship_name}</strong> is approaching.</p>
        <p><strong>Deadline:</strong> {deadline_date.strftime('%B %d, %Y')}</p>
        <p><strong>Days Remaining:</strong> {days_left} days</p>
        <p>Don't miss this opportunity! Submit your application before the deadline.</p>
        <p><a href="{self._get_base_url()}/scholarship/" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Apply Now</a></p>
        <p>Best regards,<br>LSPU Scholarship Committee</p>
        """
        
        # Send email
        email_result = self.send_email(user_email, subject, message)
        
        # Send SMS
        sms_message = f"LSPU: Reminder! {scholarship_name} deadline in {days_left} days. Apply now!"
        sms_result = self.send_sms(user_phone, sms_message)
        
        # Create in-app notification
        in_app_result = self.create_in_app_notification(
            user_id, 
            "Deadline Reminder", 
            f"{scholarship_name} deadline is in {days_left} days.",
            "deadline",
            "/scholarships"
        )
        
        return {
            'email': email_result,
            'sms': sms_result,
            'in_app': in_app_result
        }
    
    def send_welcome_email(self, user_email, user_phone, user_id, user_name):
        """Send welcome email to new users"""
        subject = "Welcome to LSPU ScholarHub!"
        message = f"""
        <h2>Welcome to LSPU ScholarHub! 🎓</h2>
        <p>Dear {user_name},</p>
        <p>Welcome to the Laguna State Polytechnic University Scholarship Management System!</p>
        <p>With LSPU ScholarHub, you can:</p>
        <ul>
            <li>Browse and apply for various scholarship programs</li>
            <li>Track your application status in real-time</li>
            <li>Upload and manage required documents</li>
            <li>Receive notifications about important updates</li>
            <li>Chat with our AI assistant for instant help</li>
        </ul>
        <p><a href="{self._get_base_url()}/scholarship/" style="background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Explore Scholarships</a></p>
        <p>If you have any questions, feel free to contact our scholarship office or use our 24/7 chatbot assistant.</p>
        <p>Best regards,<br>LSPU Scholarship Committee</p>
        """
        
        # Send email
        email_result = self.send_email(user_email, subject, message)
        
        # Send SMS
        sms_message = f"LSPU: Welcome to ScholarHub! Explore scholarship opportunities at {self._get_base_url()}/scholarship/"
        sms_result = self.send_sms(user_phone, sms_message)
        
        # Create in-app notification
        in_app_result = self.create_in_app_notification(
            user_id, 
            "Welcome to LSPU ScholarHub!", 
            "Start exploring scholarship opportunities and track your applications.",
            "welcome",
            "/scholarships"
        )
        
        return {
            'email': email_result,
            'sms': sms_result,
            'in_app': in_app_result
        }
    
    def _generate_email_html(self, message, template_data=None):
        """Generate HTML email template"""
        if template_data:
            # Simple template substitution
            for key, value in template_data.items():
                message = message.replace(f'{{{key}}}', str(value))
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>LSPU ScholarHub</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #007bff; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f8f9fa; }}
                .footer {{ padding: 20px; text-align: center; background-color: #e9ecef; }}
                .button {{ display: inline-block; padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>LSPU ScholarHub</h1>
                    <p>Scholarship Management System</p>
                </div>
                <div class="content">
                    {message}
                </div>
                <div class="footer">
                    <p><small>© 2024 Laguna State Polytechnic University. All rights reserved.</small></p>
                    <p><small>This is an automated message. Please do not reply to this email.</small></p>
                </div>
            </div>
        </body>
        </html>
        """

# Global notification service instance
notification_service = NotificationService()

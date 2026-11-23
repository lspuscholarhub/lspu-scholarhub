"""
Quick SMS test script.

Sends exactly one real test SMS, only when explicitly requested:
  TEST_SMS_NUMBER=+639171234567 python scripts/dev/test_sms.py --send-sms

Without both the flag and the number it exits without sending anything.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from _guard import require_sms_confirmation

test_number = require_sms_confirmation()

from app import create_app
app = create_app()

with app.app_context():
    from app.services.notification_service import notification_service


    print(f"\nSending test SMS to {test_number}...")
    result = notification_service.send_sms(
        test_number,
        'LSPU ScholarHub: This is a test SMS notification. If you receive this, SMS is working correctly!'
    )
    print(f"Result: {result}")

    # Also show what numbers are in the database
    from app.models import User
    students = User.query.filter_by(user_type='student').all()
    print(f"\nStudent phone numbers in database:")
    for s in students:
        print(f"  {s.get_full_name()} ({s.username}): {s.phone_number or 'NO PHONE'}")

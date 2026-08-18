"""
Quick SMS test script.
Run: py test_sms.py
This sends a test SMS to the verified Twilio number.
"""
import sys
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

from app import create_app
app = create_app()

with app.app_context():
    from app.services.notification_service import notification_service

    # Test with your number — +63 968 365 2615
    test_number = '09683652615'

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

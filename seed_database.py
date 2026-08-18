#!/usr/bin/env python3
"""
Database seeding script for LSPU ScholarHub
Creates initial data for testing and demonstration
"""

import os
from datetime import datetime, timedelta
from app import create_app, db
from app.models import User, Scholarship, ScholarshipApplication, Notification
from werkzeug.security import generate_password_hash

def create_sample_users():
    """Create sample users using the new registration workflow."""
    users = [
        {
            'username':   'admin',
            'email':      'admin@lspu-scholarhub.edu',
            'password':   'admin123',
            'first_name': 'Admin',
            'last_name':  'User',
            'user_type':  'admin',
            'is_active':  True,
            'is_verified': True,
            'student_id': None,
            'year_level': None,
        },
        {
            'username':   '2021-01234',
            'email':      'john.doe@student.lspu.edu',
            'password':   'student123',
            'first_name': 'John',
            'last_name':  'Doe',
            'user_type':  'student',
            'is_active':  True,
            'is_verified': True,
            'student_id': '2021-01234',
            'year_level': '3rd Year',
        },
        {
            'username':   '2022-04567',
            'email':      'jane.smith@student.lspu.edu',
            'password':   'student123',
            'first_name': 'Jane',
            'last_name':  'Smith',
            'user_type':  'student',
            'is_active':  True,
            'is_verified': True,
            'student_id': '2022-04567',
            'year_level': '2nd Year',
        },
        {
            'username':   'staff1',
            'email':      'maria.santos@lspu.edu',
            'password':   'staff123',
            'first_name': 'Maria',
            'last_name':  'Santos',
            'user_type':  'staff',
            'is_active':  True,
            'is_verified': True,
            'student_id': None,
            'year_level': None,
        },
        {
            'username':   'staff2',
            'email':      'jose.reyes@lspu.edu',
            'password':   'staff123',
            'first_name': 'Jose',
            'last_name':  'Reyes',
            'user_type':  'staff',
            'is_active':  True,
            'is_verified': True,
            'student_id': None,
            'year_level': None,
        },
    ]

    for u in users:
        existing = User.query.filter_by(username=u['username']).first()
        if not existing:
            new_user = User(
                username=u['username'],
                email=u['email'],
                first_name=u['first_name'],
                last_name=u['last_name'],
                user_type=u['user_type'],
                is_active=u['is_active'],
                is_verified=u['is_verified'],
                student_id=u.get('student_id'),
                year_level=u.get('year_level'),
            )
            new_user.set_password(u['password'])
            db.session.add(new_user)

    db.session.commit()
    print("Sample users created successfully")

def create_sample_scholarships():
    """Create sample scholarships"""
    scholarships = [
        {
            'title': 'Academic Excellence Scholarship',
            'description': 'For students with outstanding academic performance and high GPA achievements. This scholarship recognizes and rewards students who demonstrate excellence in their studies.',
            'eligibility_criteria': 'Minimum GPA of 1.75, full-time enrollment, good academic standing, no disciplinary record',
            'benefits': 'Financial assistance for tuition fees, book allowance, and recognition certificate',
            'award_amount': 15000.00,
            'max_applicants': 100,
            'application_deadline': datetime(2024, 12, 31),
            'created_by': 1  # Admin user
        },
        {
            'title': 'Financial Aid Grant',
            'description': 'Support for students with demonstrated financial need and academic potential. Provides assistance to deserving students who need financial support.',
            'eligibility_criteria': 'Family income below threshold, minimum GPA of 2.5, full-time enrollment',
            'benefits': 'Tuition assistance, living allowance, and book support',
            'award_amount': 8000.00,
            'max_applicants': 75,
            'application_deadline': datetime(2025, 1, 15),
            'created_by': 1
        },
        {
            'title': 'Sports Scholarship',
            'description': 'For student-athletes who excel in sports and maintain good academic standing. Supports talented athletes in their academic and athletic pursuits.',
            'eligibility_criteria': 'Member of university sports team, minimum GPA of 2.0, regular training attendance',
            'benefits': 'Tuition waiver, sports equipment allowance, training support',
            'award_amount': 12000.00,
            'max_applicants': 30,
            'application_deadline': datetime(2025, 1, 30),
            'created_by': 1
        },
        {
            'title': 'Cultural Arts Scholarship',
            'description': 'For talented students in cultural arts, music, and creative fields. Recognizes and nurtures artistic talents.',
            'eligibility_criteria': 'Audition or portfolio review, minimum GPA of 2.25, active participation in cultural activities',
            'benefits': 'Tuition assistance, art supplies allowance, performance opportunities',
            'award_amount': 10000.00,
            'max_applicants': 40,
            'application_deadline': datetime(2024, 12, 20),
            'created_by': 1
        }
    ]
    
    for scholarship_data in scholarships:
        existing_scholarship = Scholarship.query.filter_by(title=scholarship_data['title']).first()
        if not existing_scholarship:
            scholarship = Scholarship(**scholarship_data)
            db.session.add(scholarship)
    
    db.session.commit()
    print("Sample scholarships created successfully")

def create_sample_applications():
    """Create sample scholarship applications"""
    applications = [
        {
            'scholarship_id': 1,  # Academic Excellence
            'applicant_id': 2,   # John Doe
            'application_data': {
                'gpa': '1.75',
                'course': 'Bachelor of Science in Computer Science',
                'year_level': '3rd Year',
                'essay': 'I am dedicated to academic excellence and have maintained high grades throughout my studies...'
            },
            'status': 'pending'
        },
        {
            'scholarship_id': 2,  # Financial Aid
            'applicant_id': 3,   # Jane Smith
            'application_data': {
                'gpa': '2.8',
                'course': 'Bachelor of Arts in Education',
                'year_level': '2nd Year',
                'family_income': '150000',
                'essay': 'My family faces financial challenges, but I am determined to complete my education...'
            },
            'status': 'under_review'
        }
    ]
    
    for app_data in applications:
        existing_app = ScholarshipApplication.query.filter_by(
            scholarship_id=app_data['scholarship_id'],
            applicant_id=app_data['applicant_id']
        ).first()
        if not existing_app:
            application = ScholarshipApplication(**app_data)
            db.session.add(application)
    
    db.session.commit()
    print("Sample applications created successfully")

def create_sample_notifications():
    """Create sample notifications"""
    from app.models.notification import NotificationType, NotificationChannel

    notifications = [
        {
            'recipient_id': 2,  # John Doe
            'title': 'Application Received',
            'message': 'Your application for Academic Excellence Scholarship has been received successfully.',
            'notification_type': NotificationType.APPLICATION_SUBMITTED,
            'channel': NotificationChannel.IN_APP,
            'related_entity_type': 'scholarship',
            'related_entity_id': 1
        },
        {
            'recipient_id': 3,  # Jane Smith
            'title': 'Application Under Review',
            'message': 'Your Financial Aid Grant application is now under review.',
            'notification_type': NotificationType.SYSTEM_ANNOUNCEMENT,
            'channel': NotificationChannel.IN_APP,
            'related_entity_type': 'scholarship',
            'related_entity_id': 2
        },
        {
            'recipient_id': 2,  # John Doe
            'title': 'New Scholarship Available',
            'message': 'Sports Scholarship is now accepting applications. Apply now!',
            'notification_type': NotificationType.NEW_SCHOLARSHIP,
            'channel': NotificationChannel.IN_APP,
            'related_entity_type': 'scholarship',
            'related_entity_id': 3
        }
    ]
    
    for notif_data in notifications:
        existing_notif = Notification.query.filter_by(
            recipient_id=notif_data['recipient_id'],
            title=notif_data['title']
        ).first()
        if not existing_notif:
            notification = Notification(**notif_data)
            db.session.add(notification)
    
    db.session.commit()
    print("Sample notifications created successfully")

def main():
    """Main seeding function"""
    app = create_app()
    
    with app.app_context():
        print("Starting database seeding...")
        
        # Create tables if they don't exist
        db.create_all()
        
        # Create sample data
        create_sample_users()
        create_sample_scholarships()
        create_sample_applications()
        create_sample_notifications()
        
        print("\nDatabase seeding completed successfully!")
        print("\nSample Login Credentials:")
        print("Admin:   admin    / admin123   (login with username or email)")
        print("Staff:   staff1   / staff123")
        print("Staff:   staff2   / staff123")
        print("Student: 2021-01234 / student123  (login with Student ID or email)")
        print("Student: 2022-04567 / student123  (login with Student ID or email)")

if __name__ == "__main__":
    main()

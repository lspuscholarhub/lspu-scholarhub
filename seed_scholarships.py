"""
Seed the database with the scholarship programs from the Excel reference file.
Run once: py seed_scholarships.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.models import Scholarship, User
from app.models.scholarship import ScholarshipStatus
from datetime import datetime, timedelta

app = create_app()

# Scholarship programs from the Excel: SUMMARY REPORT 2ND SEM AY 2025-2026
SCHOLARSHIPS = [
    {
        'title': 'CHED Tertiary Education Subsidy (TES)',
        'scholarship_type': 'Financial Assistance',
        'award_amount': 10000,
        'description': 'Financial assistance program by CHED for qualified students under RA 10931 (Universal Access to Quality Tertiary Education Act).',
        'eligibility_criteria': 'Filipino citizen, enrolled in LSPU, meeting income requirements.',
        'benefits': '₱10,000 per semester financial assistance.',
    },
    {
        'title': 'CHED Tulong Dunong Program (TDP)',
        'scholarship_type': 'Financial Assistance',
        'award_amount': 7500,
        'description': 'CHED financial assistance for students in private and state universities.',
        'eligibility_criteria': 'Filipino citizen, enrolled in LSPU, meeting TDP requirements.',
        'benefits': '₱7,500 per semester financial assistance.',
    },
    {
        'title': 'CHED Merit Scholarship Program (CMSP) - Full',
        'scholarship_type': 'Merit Scholarship',
        'award_amount': 40000,
        'description': 'Full merit scholarship from CHED for academically excellent students.',
        'eligibility_criteria': 'Must maintain excellent academic standing (GWA requirement).',
        'benefits': '₱40,000 per semester merit scholarship.',
    },
    {
        'title': 'CHED Merit Scholarship Program (CMSP) - Half',
        'scholarship_type': 'Merit Scholarship',
        'award_amount': 20000,
        'description': 'Half merit scholarship from CHED for academically excellent students.',
        'eligibility_criteria': 'Must maintain excellent academic standing (GWA requirement).',
        'benefits': '₱20,000 per semester merit scholarship.',
    },
    {
        'title': 'COSCHO',
        'scholarship_type': 'Financial Assistance',
        'award_amount': 40000,
        'description': 'College Scholarship program for qualified LSPU students.',
        'eligibility_criteria': 'Must be enrolled in LSPU and meet COSCHO requirements.',
        'benefits': '₱40,000 per semester financial assistance.',
    },
    {
        'title': 'DOST Scholarship',
        'scholarship_type': 'Merit Scholarship',
        'award_amount': 45000,
        'description': 'Department of Science and Technology scholarship for students in science and technology courses.',
        'eligibility_criteria': 'Must be enrolled in a DOST-priority course (Science, Technology, Engineering, Mathematics).',
        'benefits': '₱45,000 per semester (tuition + stipend + book allowance).',
    },
    {
        'title': 'Luis Co Chi Kiat Foundation Inc. (LCCKFI)',
        'scholarship_type': 'Financial Assistance',
        'award_amount': 5000,
        'description': 'Private foundation scholarship for deserving LSPU students.',
        'eligibility_criteria': 'Must be enrolled in LSPU and meet foundation requirements.',
        'benefits': '₱5,000 per semester financial assistance.',
    },
    {
        'title': 'IBIDEN Scholarship',
        'scholarship_type': 'Financial Assistance',
        'award_amount': 25000,
        'description': 'Corporate scholarship from IBIDEN Philippines for qualified students.',
        'eligibility_criteria': 'Must be enrolled in LSPU and meet IBIDEN requirements.',
        'benefits': '₱25,000 per semester financial assistance.',
    },
]

with app.app_context():
    # Get admin user to set as creator
    admin = User.query.filter_by(user_type='admin').first()
    if not admin:
        print('ERROR: No admin user found. Create an admin account first.')
        sys.exit(1)

    created = 0
    skipped = 0

    for s_data in SCHOLARSHIPS:
        # Check if already exists
        existing = Scholarship.query.filter_by(title=s_data['title']).first()
        if existing:
            print(f'  [SKIP] "{s_data["title"]}" already exists.')
            skipped += 1
            continue

        scholarship = Scholarship(
            title=s_data['title'],
            scholarship_type=s_data['scholarship_type'],
            category='Government' if 'CHED' in s_data['title'] or 'DOST' in s_data['title'] else 'Private',
            description=s_data['description'],
            eligibility_criteria=s_data['eligibility_criteria'],
            benefits=s_data['benefits'],
            award_amount=s_data['award_amount'],
            application_deadline=datetime(2026, 6, 30),  # End of current semester
            status=ScholarshipStatus.ACTIVE,
            created_by=admin.id,
        )
        db.session.add(scholarship)
        created += 1
        print(f'  [OK]   "{s_data["title"]}" — ₱{s_data["award_amount"]:,.0f}/scholar')

    db.session.commit()
    print(f'\nDone. Created: {created}, Skipped: {skipped}')

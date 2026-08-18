"""
Seed test data: 20 students + 1 staff. All passwords set to 'password'.
Run: py seed_test_data.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()

from app import create_app, db
from app.models import User

app = create_app()

STUDENTS = [
    {'student_id': '0123-0001', 'first_name': 'Maria', 'last_name': 'Santos', 'middle_name': 'Cruz', 'email': 'maria.santos@student.lspu.edu', 'gender': 'Female', 'course': 'Bachelor of Science in Information Technology', 'year_level': '3rd Year', 'town': 'Santa Cruz', 'province': 'Laguna', 'phone_number': '09171000001', 'gwa': 1.75},
    {'student_id': '0123-0002', 'first_name': 'Juan', 'last_name': 'Reyes', 'middle_name': 'Garcia', 'email': 'juan.reyes@student.lspu.edu', 'gender': 'Male', 'course': 'Bachelor of Science in Computer Science', 'year_level': '4th Year', 'town': 'Pagsanjan', 'province': 'Laguna', 'phone_number': '09171000002', 'gwa': 1.50},
    {'student_id': '0123-0003', 'first_name': 'Ana', 'last_name': 'Dela Cruz', 'middle_name': None, 'email': 'ana.delacruz@student.lspu.edu', 'gender': 'Female', 'course': 'Bachelor of Science in Civil Engineering', 'year_level': '2nd Year', 'town': 'Lumban', 'province': 'Laguna', 'phone_number': '09171000003', 'gwa': 2.25},
    {'student_id': '0123-0004', 'first_name': 'Carlos', 'last_name': 'Mendoza', 'middle_name': 'Bautista', 'email': 'carlos.mendoza@student.lspu.edu', 'gender': 'Male', 'course': 'Bachelor of Science in Electrical Engineering', 'year_level': '3rd Year', 'town': 'Pila', 'province': 'Laguna', 'phone_number': '09171000004', 'gwa': 2.50},
    {'student_id': '0123-0005', 'first_name': 'Patricia', 'last_name': 'Villanueva', 'middle_name': 'Lopez', 'email': 'patricia.villanueva@student.lspu.edu', 'gender': 'Female', 'course': 'Bachelor of Elementary Education', 'year_level': '4th Year', 'town': 'Magdalena', 'province': 'Laguna', 'phone_number': '09171000005', 'gwa': 1.25},
    {'student_id': '0123-0006', 'first_name': 'Miguel', 'last_name': 'Ramos', 'middle_name': 'Torres', 'email': 'miguel.ramos@student.lspu.edu', 'gender': 'Male', 'course': 'Bachelor of Science in Accountancy', 'year_level': '2nd Year', 'town': 'Liliw', 'province': 'Laguna', 'phone_number': '09171000006', 'gwa': 2.00},
    {'student_id': '0123-0007', 'first_name': 'Sofia', 'last_name': 'Garcia', 'middle_name': 'Aquino', 'email': 'sofia.garcia@student.lspu.edu', 'gender': 'Female', 'course': 'Bachelor of Science in Nursing', 'year_level': '3rd Year', 'town': 'Majayjay', 'province': 'Laguna', 'phone_number': '09171000007', 'gwa': 1.80},
    {'student_id': '0123-0008', 'first_name': 'Rafael', 'last_name': 'Torres', 'middle_name': None, 'email': 'rafael.torres@student.lspu.edu', 'gender': 'Male', 'course': 'Bachelor of Science in Mathematics', 'year_level': '1st Year', 'town': 'Cavinti', 'province': 'Laguna', 'phone_number': '09171000008', 'gwa': None},
    {'student_id': '0123-0009', 'first_name': 'Isabella', 'last_name': 'Fernandez', 'middle_name': 'Castillo', 'email': 'isabella.fernandez@student.lspu.edu', 'gender': 'Female', 'course': 'Bachelor of Science in Psychology', 'year_level': '2nd Year', 'town': 'Luisiana', 'province': 'Laguna', 'phone_number': '09171000009', 'gwa': 2.75},
    {'student_id': '0123-0010', 'first_name': 'Gabriel', 'last_name': 'Aquino', 'middle_name': 'Reyes', 'email': 'gabriel.aquino@student.lspu.edu', 'gender': 'Male', 'course': 'Bachelor of Science in Mechanical Engineering', 'year_level': '4th Year', 'town': 'Santa Cruz', 'province': 'Laguna', 'phone_number': '09171000010', 'gwa': 3.25},
    {'student_id': '0123-0011', 'first_name': 'Camille', 'last_name': 'Bautista', 'middle_name': 'Navarro', 'email': 'camille.bautista@student.lspu.edu', 'gender': 'Female', 'course': 'Bachelor of Science in Business Administration Major In Financial Management', 'year_level': '3rd Year', 'town': 'Pagsanjan', 'province': 'Laguna', 'phone_number': '09171000011', 'gwa': 1.90},
    {'student_id': '0123-0012', 'first_name': 'Daniel', 'last_name': 'Navarro', 'middle_name': 'Santos', 'email': 'daniel.navarro@student.lspu.edu', 'gender': 'Male', 'course': 'Bachelor of Science in Information Technology', 'year_level': '2nd Year', 'town': 'Lumban', 'province': 'Laguna', 'phone_number': '09171000012', 'gwa': 2.10},
    {'student_id': '0123-0013', 'first_name': 'Angela', 'last_name': 'Lopez', 'middle_name': None, 'email': 'angela.lopez@student.lspu.edu', 'gender': 'Female', 'course': 'Bachelor of Secondary Education Major In English', 'year_level': '4th Year', 'town': 'Pila', 'province': 'Laguna', 'phone_number': '09171000013', 'gwa': 1.60},
    {'student_id': '0123-0014', 'first_name': 'Marco', 'last_name': 'Castillo', 'middle_name': 'Dela Cruz', 'email': 'marco.castillo@student.lspu.edu', 'gender': 'Male', 'course': 'Bachelor of Science in Chemistry', 'year_level': '3rd Year', 'town': 'Magdalena', 'province': 'Laguna', 'phone_number': '09171000014', 'gwa': 2.30},
    {'student_id': '0123-0015', 'first_name': 'Jasmine', 'last_name': 'Rivera', 'middle_name': 'Mendoza', 'email': 'jasmine.rivera@student.lspu.edu', 'gender': 'Female', 'course': 'Bachelor of Science in Hospitality Management', 'year_level': '1st Year', 'town': 'Liliw', 'province': 'Laguna', 'phone_number': '09171000015', 'gwa': None},
    {'student_id': '0123-0016', 'first_name': 'Andrei', 'last_name': 'Gonzales', 'middle_name': 'Ramos', 'email': 'andrei.gonzales@student.lspu.edu', 'gender': 'Male', 'course': 'Bachelor of Science in Computer Engineering', 'year_level': '3rd Year', 'town': 'Majayjay', 'province': 'Laguna', 'phone_number': '09171000016', 'gwa': 1.95},
    {'student_id': '0123-0017', 'first_name': 'Christine', 'last_name': 'Manalo', 'middle_name': 'Garcia', 'email': 'christine.manalo@student.lspu.edu', 'gender': 'Female', 'course': 'Bachelor of Science in Biology', 'year_level': '2nd Year', 'town': 'Cavinti', 'province': 'Laguna', 'phone_number': '09171000017', 'gwa': 2.60},
    {'student_id': '0123-0018', 'first_name': 'Joshua', 'last_name': 'Pascual', 'middle_name': None, 'email': 'joshua.pascual@student.lspu.edu', 'gender': 'Male', 'course': 'Bachelor of Science in Entrepreneurship', 'year_level': '4th Year', 'town': 'Luisiana', 'province': 'Laguna', 'phone_number': '09171000018', 'gwa': 3.50},
    {'student_id': '0123-0019', 'first_name': 'Katrina', 'last_name': 'Soriano', 'middle_name': 'Villanueva', 'email': 'katrina.soriano@student.lspu.edu', 'gender': 'Female', 'course': 'Bachelor of Science in Electronics Engineering', 'year_level': '3rd Year', 'town': 'Santa Cruz', 'province': 'Laguna', 'phone_number': '09171000019', 'gwa': 2.00},
    {'student_id': '0123-0020', 'first_name': 'Paolo', 'last_name': 'Dimaculangan', 'middle_name': 'Fernandez', 'email': 'paolo.dimaculangan@student.lspu.edu', 'gender': 'Male', 'course': 'Bachelor of Science in Criminology', 'year_level': '2nd Year', 'town': 'Pagsanjan', 'province': 'Laguna', 'phone_number': '09171000020', 'gwa': 2.85},
]

STAFF = {
    'username': 'staff2',
    'first_name': 'Elena',
    'last_name': 'Coronel',
    'email': 'elena.coronel@lspu.edu.ph',
}

with app.app_context():
    created_students = 0
    created_staff = 0

    # Create students
    for s in STUDENTS:
        if User.query.filter_by(student_id=s['student_id']).first():
            print(f"  [SKIP] {s['student_id']} already exists")
            continue
        user = User(
            username=s['student_id'],
            email=s['email'],
            first_name=s['first_name'],
            last_name=s['last_name'],
            middle_name=s.get('middle_name'),
            student_id=s['student_id'],
            course=s['course'],
            year_level=s['year_level'],
            gender=s.get('gender'),
            town=s.get('town'),
            province=s.get('province'),
            phone_number=s.get('phone_number'),
            gwa=s.get('gwa'),
            user_type='student',
            is_active=True,
            is_verified=True,
        )
        user.set_password('password')
        db.session.add(user)
        created_students += 1
        print(f"  [OK] {s['student_id']} — {s['first_name']} {s['last_name']} ({s['course'][:30]})")

    # Create staff
    if User.query.filter_by(username=STAFF['username']).first():
        print(f"  [SKIP] Staff '{STAFF['username']}' already exists")
    else:
        staff = User(
            username=STAFF['username'],
            email=STAFF['email'],
            first_name=STAFF['first_name'],
            last_name=STAFF['last_name'],
            user_type='staff',
            is_active=True,
            is_verified=True,
        )
        staff.set_password('password')
        db.session.add(staff)
        created_staff = 1
        print(f"  [OK] Staff: {STAFF['username']} — {STAFF['first_name']} {STAFF['last_name']}")

    db.session.commit()
    print(f"\nDone. Created {created_students} students + {created_staff} staff.")
    print("All passwords: password")

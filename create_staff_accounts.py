#!/usr/bin/env python3
"""
Create sample staff accounts for LSPU ScholarHub
"""

import os
from app import create_app, db
from app.models import User

def create_staff_accounts():
    """Create sample staff accounts"""
    app = create_app()
    
    with app.app_context():
        print("Creating sample staff accounts...")
        
        # Staff Account 1
        staff1 = User(
            username='staff1',
            email='staff1@lspu-scholarhub.edu',
            first_name='Maria',
            last_name='Santos',
            phone_number='+63 912 345 6789',
            user_type='staff',
            is_active=True,
            is_verified=True
        )
        staff1.set_password('staff123')
        
        # Staff Account 2
        staff2 = User(
            username='staff2',
            email='staff2@lspu-scholarhub.edu',
            first_name='Juan',
            last_name='Reyes',
            phone_number='+63 923 456 7890',
            user_type='staff',
            is_active=True,
            is_verified=True
        )
        staff2.set_password('staff123')
        
        try:
            # Check if staff accounts already exist
            existing_staff1 = User.query.filter_by(username='staff1').first()
            existing_staff2 = User.query.filter_by(username='staff2').first()
            
            if not existing_staff1:
                db.session.add(staff1)
                print("Created staff1 account")
            else:
                print("staff1 account already exists")
                
            if not existing_staff2:
                db.session.add(staff2)
                print("Created staff2 account")
            else:
                print("staff2 account already exists")
            
            db.session.commit()
            
            print("\n" + "="*50)
            print("STAFF ACCOUNTS CREATED SUCCESSFULLY")
            print("="*50)
            print("\nSample Staff Credentials:")
            print("1. Username: staff1")
            print("   Password: staff123")
            print("   Name: Maria Santos")
            print("   Email: staff1@lspu-scholarhub.edu")
            print()
            print("2. Username: staff2")
            print("   Password: staff123")
            print("   Name: Juan Reyes")
            print("   Email: staff2@lspu-scholarhub.edu")
            print()
            print("You can now login with these staff credentials!")
            print("="*50)
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating staff accounts: {e}")

if __name__ == "__main__":
    create_staff_accounts()

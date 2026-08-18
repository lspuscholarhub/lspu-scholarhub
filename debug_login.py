#!/usr/bin/env python3
"""
Debug login authentication issues
"""

import os
from app import create_app, db
from app.models import User

def debug_users():
    """Debug user authentication"""
    app = create_app()
    
    with app.app_context():
        print("=== DEBUG: All Users in Database ===")
        users = User.query.all()
        
        for user in users:
            print(f"User ID: {user.id}")
            print(f"Username: {user.username}")
            print(f"Email: {user.email}")
            print(f"Password Hash: {user.password_hash[:50]}...")
            print(f"User Type: {user.user_type}")
            print(f"Is Active: {user.is_active}")
            print(f"Is Verified: {user.is_verified}")
            print("-" * 40)
        
        print(f"\nTotal users found: {len(users)}")
        
        # Test password verification for sample users
        print("\n=== DEBUG: Password Verification Tests ===")
        
        test_credentials = [
            ('admin', 'admin123'),
            ('johndoe', 'student123'),
            ('janesmith', 'student123')
        ]
        
        for username, password in test_credentials:
            user = User.query.filter_by(username=username).first()
            if user:
                print(f"\nTesting: {username} / {password}")
                print(f"User found: {user.username}")
                print(f"Password check result: {user.check_password(password)}")
                if user.check_password(password):
                    print("✓ SUCCESS: Password verification works")
                else:
                    print("✗ FAILED: Password verification failed")
            else:
                print(f"\nUser not found: {username}")

def test_registration_password():
    """Test password hashing and verification"""
    app = create_app()
    
    with app.app_context():
        print("\n=== DEBUG: Password Hashing Test ===")
        
        from werkzeug.security import generate_password_hash, check_password_hash
        
        test_password = "test123"
        hashed = generate_password_hash(test_password)
        print(f"Original password: {test_password}")
        print(f"Hashed password: {hashed}")
        print(f"Verification result: {check_password_hash(hashed, test_password)}")
        
        # Test with wrong password
        print(f"Wrong password test: {check_password_hash(hashed, 'wrong')}")

if __name__ == "__main__":
    debug_users()
    test_registration_password()

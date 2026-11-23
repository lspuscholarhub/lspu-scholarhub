#!/usr/bin/env python3
"""
Debug login authentication issues
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import os
import secrets
from app import create_app, db
from app.models import User


def test_credentials():
    """Accounts to verify, supplied by the environment so no password lives in
    the repo: DEBUG_TEST_CREDENTIALS='admin:secret,johndoe:secret2'."""
    creds = []
    for pair in (os.environ.get('DEBUG_TEST_CREDENTIALS') or '').split(','):
        if ':' in pair:
            username, password = pair.split(':', 1)
            if username.strip() and password.strip():
                creds.append((username.strip(), password.strip()))
    return creds

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
        
        creds = test_credentials()
        if not creds:
            print("\n(No accounts to test — set DEBUG_TEST_CREDENTIALS=user:password "
                  "to run the verification pass.)")

        for username, password in creds:
            user = User.query.filter_by(username=username).first()
            if user:
                print(f"\nTesting: {username}")
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
        
        # A throwaway password: the point is that hashing round-trips, so it
        # never needs to be a known value (or in the source).
        test_password = secrets.token_urlsafe(12)
        hashed = generate_password_hash(test_password)
        print(f"Hashed password: {hashed}")
        print(f"Verification result: {check_password_hash(hashed, test_password)}")
        
        # Test with wrong password
        print(f"Wrong password test: {check_password_hash(hashed, 'wrong')}")

if __name__ == "__main__":
    debug_users()
    test_registration_password()

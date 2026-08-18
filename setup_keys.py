#!/usr/bin/env python3
"""
Simple script to generate secret keys for the LSPU ScholarHub application.
This is completely FREE and uses built-in Python libraries.
"""

import secrets
import string

def generate_secret_key(length=32):
    """Generate a secure random secret key"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_jwt_key(length=64):
    """Generate a secure JWT secret key"""
    return secrets.token_urlsafe(length)

def main():
    print("🔐 LSPU ScholarHub - Secret Key Generator")
    print("=" * 50)
    print()
    
    print("Generated Secret Keys (FREE - no cost):")
    print("-" * 35)
    
    # Generate Flask secret key
    flask_secret = generate_secret_key()
    print(f"SECRET_KEY={flask_secret}")
    print()
    
    # Generate JWT secret key
    jwt_secret = generate_jwt_key()
    print(f"JWT_SECRET_KEY={jwt_secret}")
    print()
    
    print("Instructions:")
    print("1. Copy these keys into your .env file")
    print("2. Replace the placeholder keys with these generated ones")
    print("3. Keep these keys secret and don't share them")
    print("4. These keys are completely free to use!")
    print()
    
    print("Example .env configuration:")
    print("-" * 30)
    print("SECRET_KEY=" + flask_secret)
    print("JWT_SECRET_KEY=" + jwt_secret)
    print("CHATBOT_ENABLED=true")
    print("CHATBOT_TYPE=rule_based")

if __name__ == "__main__":
    main()

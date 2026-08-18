#!/usr/bin/env python3
"""
Fix admin user password - it's stored as plain text instead of hash
"""

import os
from app import create_app, db
from app.models import User

def fix_admin_password():
    """Fix admin user password to use proper hash"""
    app = create_app()
    
    with app.app_context():
        # Find admin user
        admin_user = User.query.filter_by(username='admin').first()
        
        if admin_user:
            print(f"Found admin user: {admin_user.username}")
            print(f"Current password hash: {admin_user.password_hash[:50]}...")
            
            # Set proper password hash
            admin_user.set_password('admin123')
            db.session.commit()
            
            print("Admin password has been fixed with proper hash")
            print("Login should now work with: admin / admin123")
        else:
            print("Admin user not found")

if __name__ == "__main__":
    fix_admin_password()

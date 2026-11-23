#!/usr/bin/env python3
"""
Script to fix .env file with correct database configuration
"""

import os
import shutil

def fix_env_file():
    """Replace old .env with corrected version"""
    
    # File paths
    old_env = '.env'
    new_env = '.env.new'
    
    if os.path.exists(old_env):
        # Backup old file
        shutil.copy2(old_env, f'{old_env}.backup')
        print(f"Backed up {old_env} to {old_env}.backup")
    
    if os.path.exists(new_env):
        # Replace old with new
        shutil.move(new_env, old_env)
        print(f"Replaced {old_env} with corrected configuration")
        print("\nDatabase Configuration Fixed:")
        print("   MYSQL_USER=root")
        print("   MYSQL_PASSWORD=(empty)")
        print("   DATABASE_URL=mysql+pymysql://root:@localhost/lspu_scholarhub")
        print("\nYour application should now work correctly!")
        print("   Restart with: py run.py")
    else:
        print(f"{new_env} not found. Please ensure it was created correctly.")

if __name__ == "__main__":
    fix_env_file()

#!/usr/bin/env python3
"""
Test script to help configure MySQL connection
"""

import pymysql
import getpass

def test_mysql_connection(host='localhost', port=3306, user='root', password='', database='lspu_scholarhub'):
    """Test MySQL connection with given credentials"""
    try:
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset='utf8mb4'
        )
        print(f"SUCCESS: Connected to MySQL database '{database}' as user '{user}'")
        connection.close()
        return True
    except pymysql.err.OperationalError as e:
        print(f"ERROR: {e}")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    print("MySQL Connection Test for LSPU ScholarHub")
    print("=" * 50)
    print()
    
    # Test common configurations
    test_configs = [
        {'user': 'root', 'password': ''},
        {'user': 'root', 'password': 'root'},
        {'user': 'root', 'password': 'password'},
        {'user': 'mysql', 'password': ''},
        {'user': 'mysql', 'password': 'mysql'},
    ]
    
    print("Testing common MySQL configurations...")
    found = False
    
    for config in test_configs:
        print(f"\nTesting: user='{config['user']}', password='{'*' * len(config['password'])}'")
        if test_mysql_connection(**config):
            found = True
            print(f"\nWORKING CONFIGURATION FOUND:")
            print(f"   DATABASE_URL=mysql+pymysql://{config['user']}:{config['password']}@localhost/lspu_scholarhub")
            print(f"   MYSQL_USER={config['user']}")
            print(f"   MYSQL_PASSWORD={config['password']}")
            break
    
    if not found:
        print("\nNo working configuration found among common options.")
        print("\nPlease enter your MySQL credentials manually:")
        
        user = input("MySQL Username (usually 'root'): ").strip()
        password = getpass.getpass("MySQL Password: ").strip()
        
        print(f"\nTesting manual configuration...")
        if test_mysql_connection(user=user, password=password):
            print(f"\nWORKING CONFIGURATION FOUND:")
            print(f"   DATABASE_URL=mysql+pymysql://{user}:{password}@localhost/lspu_scholarhub")
            print(f"   MYSQL_USER={user}")
            print(f"   MYSQL_PASSWORD={password}")
        else:
            print("\nManual configuration also failed.")
            print("\nPossible solutions:")
            print("   1. Check if MySQL service is running")
            print("   2. Verify your MySQL username and password")
            print("   3. Make sure database 'lspu_scholarhub' exists")
            print("   4. Try resetting MySQL root password")

if __name__ == "__main__":
    main()

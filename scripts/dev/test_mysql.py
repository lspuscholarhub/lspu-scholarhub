#!/usr/bin/env python3
"""Test script to help configure MySQL connection.

Set MYSQL_TEST_DATABASE to target another database (for example a scratch one);
it defaults to lspu_scholarhub. Passwords are never printed.
"""

import getpass
import os

import pymysql

DATABASE = os.environ.get('MYSQL_TEST_DATABASE', 'lspu_scholarhub')


def mask(password):
    """Show only whether a password is set, never its value."""
    return '***' if password else '(empty)'


def test_mysql_connection(host='localhost', port=3306, user='root',
                          password='', database=None):
    """Test MySQL connection with given credentials."""
    database = database or DATABASE
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
    print(f"Target database: {DATABASE}")
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
        print(f"\nTesting: user='{config['user']}', password={mask(config['password'])}")
        if test_mysql_connection(**config):
            found = True
            print("\nWORKING CONFIGURATION FOUND:")
            print(f"   DATABASE_URL=mysql+pymysql://{config['user']}:<password>@localhost/{DATABASE}")
            print(f"   MYSQL_USER={config['user']}")
            print(f"   MYSQL_PASSWORD={mask(config['password'])}")
            break

    if not found:
        print("\nNo working configuration found among common options.")
        print("\nPlease enter your MySQL credentials manually:")

        user = input("MySQL Username (usually 'root'): ").strip()
        password = getpass.getpass("MySQL Password: ").strip()

        print("\nTesting manual configuration...")
        if test_mysql_connection(user=user, password=password):
            print("\nWORKING CONFIGURATION FOUND:")
            print(f"   DATABASE_URL=mysql+pymysql://{user}:<password>@localhost/{DATABASE}")
            print(f"   MYSQL_USER={user}")
            print(f"   MYSQL_PASSWORD={mask(password)}")
        else:
            print("\nManual configuration also failed.")
            print("\nPossible solutions:")
            print("   1. Check if MySQL service is running")
            print("   2. Verify your MySQL username and password")
            print(f"   3. Make sure database '{DATABASE}' exists")
            print("   4. Try resetting MySQL root password")


if __name__ == "__main__":
    main()

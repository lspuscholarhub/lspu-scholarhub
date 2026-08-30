"""
Local database migration script.
Run this once to bring your local XAMPP database up to date with Railway.
Usage: py migrate_local.py
Make sure XAMPP MySQL is running first.
"""
from app import create_app, db
from sqlalchemy import text, inspect

app = create_app('development')

MIGRATIONS = [
    # users table
    ("users", "ocr_verified",          "ALTER TABLE users ADD COLUMN ocr_verified TINYINT(1) NULL"),
    ("users", "ocr_result",            "ALTER TABLE users ADD COLUMN ocr_result TEXT NULL"),
    ("users", "cor_cloudinary_id",     "ALTER TABLE users ADD COLUMN cor_cloudinary_id VARCHAR(255) NULL"),
    ("users", "grades_cloudinary_id",  "ALTER TABLE users ADD COLUMN grades_cloudinary_id VARCHAR(255) NULL"),
    # documents table
    ("documents", "cloudinary_url",       "ALTER TABLE documents ADD COLUMN cloudinary_url VARCHAR(500) NULL"),
    ("documents", "cloudinary_public_id", "ALTER TABLE documents ADD COLUMN cloudinary_public_id VARCHAR(255) NULL"),
]

with app.app_context():
    inspector = inspect(db.engine)

    for table, column, sql in MIGRATIONS:
        try:
            existing = [c['name'] for c in inspector.get_columns(table)]
            if column in existing:
                print(f"  SKIP  {table}.{column} — already exists")
            else:
                db.session.execute(text(sql))
                db.session.commit()
                print(f"  ADDED {table}.{column}")
        except Exception as e:
            db.session.rollback()
            print(f"  ERROR {table}.{column}: {e}")

    print("\nDone. Local database is now in sync with Railway.")

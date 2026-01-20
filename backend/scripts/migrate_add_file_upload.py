"""
Migration script to add uploaded_files and external_information columns
Run this script to migrate the database schema
"""
import sqlite3
import os
from pathlib import Path

# Get the database path
backend_dir = Path(__file__).parent.parent
data_dir = backend_dir / "data"
db_path = data_dir / "skill_writer.db"

print(f"Database path: {db_path}")

if not db_path.exists():
    print("Database does not exist. It will be created on first run.")
    exit(0)

# Connect to database
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Check existing columns
cursor.execute("PRAGMA table_info(sessions)")
columns = {row[1] for row in cursor.fetchall()}
print(f"Existing columns: {columns}")

# Add missing columns
migrations = []

if 'uploaded_files' not in columns:
    migrations.append(
        "ALTER TABLE sessions ADD COLUMN uploaded_files TEXT DEFAULT '[]'"
    )
    print("Will add: uploaded_files")

if 'external_information' not in columns:
    migrations.append(
        "ALTER TABLE sessions ADD COLUMN external_information TEXT DEFAULT ''"
    )
    print("Will add: external_information")

if not migrations:
    print("No migrations needed. Schema is up to date.")
else:
    print(f"\nRunning {len(migrations)} migrations...")
    for sql in migrations:
        print(f"  Executing: {sql}")
        cursor.execute(sql)

    conn.commit()
    print("\nMigrations completed successfully!")

conn.close()

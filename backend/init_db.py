"""
init_db.py — Safe database initialization and verification script for DocuMedi.

This script uses SQLAlchemy's Base.metadata.create_all() which creates tables
ONLY if they do not already exist. It NEVER drops or overwrites existing tables or data.
"""

import sys
from sqlalchemy import inspect
from database import engine, Base
import models  # Ensures all ORM models are registered with Base.metadata


def init_and_verify():
    print("=" * 60)
    print("DocuMedi — Safe Database Table Initialization")
    print("=" * 60)

    try:
        # Step 1: Create missing tables safely (checkfirst=True prevents overwriting)
        print("\n[1/3] Creating database tables safely (if not already present)...")
        Base.metadata.create_all(bind=engine, checkfirst=True)
        print(" -> Table creation command executed successfully.")

        # Step 2: Inspect the MySQL database
        print("\n[2/3] Inspecting MySQL database tables...")
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        print(f" -> Existing tables in database: {existing_tables}")

        required_tables = [
            "patients",
            "patient_cases",
            "conversation_messages",
            "patient_notes",
        ]

        missing = [tbl for tbl in required_tables if tbl not in existing_tables]
        if missing:
            print(f" [ERROR] Missing required tables: {missing}")
            sys.exit(1)
        else:
            print(" -> All 4 required tables exist in MySQL!")

        # Step 3: Verify columns and constraints for each table
        print("\n[3/3] Detailed verification of table schemas:")
        for table_name in required_tables:
            columns = inspector.get_columns(table_name)
            pk = inspector.get_pk_constraint(table_name)
            fks = inspector.get_foreign_keys(table_name)

            col_names = [col['name'] for col in columns]
            pk_cols = pk.get('constrained_columns', [])

            print(f"\n Table: '{table_name}'")
            print(f"   Primary Key : {pk_cols}")
            print(f"   Columns ({len(col_names)}) : {', '.join(col_names)}")
            if fks:
                for fk in fks:
                    print(f"   Foreign Key : {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")

        print("\n" + "=" * 60)
        print(" SUCCESS: Database initialized and verified with zero data loss!")
        print("=" * 60)

    except Exception as e:
        print(f"\n [ERROR] Failed to initialize database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    init_and_verify()

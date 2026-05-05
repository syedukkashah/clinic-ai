"""Verify database setup - tables, row counts, schema."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from sqlalchemy import create_engine, text

DB_URL = "postgresql://mediflow:{}@localhost:5432/mediflow".format(
    os.environ.get("POSTGRES_PASSWORD", "mediflow123")
)

engine = create_engine(DB_URL)

with engine.connect() as conn:
    # List tables
    tables = conn.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_type='BASE TABLE' "
        "ORDER BY table_name"
    )).fetchall()
    
    print("=" * 60)
    print("  DATABASE VERIFICATION")
    print("=" * 60)
    print(f"\n  Tables found: {len(tables)}")
    for t in tables:
        count = conn.execute(text(f"SELECT COUNT(*) FROM {t[0]}")).scalar()
        print(f"    - {t[0]}: {count:,} rows")
    
    # Check enums
    print("\n  Enum types:")
    enums = conn.execute(text(
        "SELECT t.typname, e.enumlabel "
        "FROM pg_type t JOIN pg_enum e ON t.oid = e.enumtypid "
        "ORDER BY t.typname, e.enumsortorder"
    )).fetchall()
    
    current_type = None
    for typename, label in enums:
        if typename != current_type:
            current_type = typename
            print(f"    {typename}:")
        print(f"      - {label}")
    
    # Verify doctor IDs are integers
    doctor_ids = conn.execute(text("SELECT id FROM doctors ORDER BY id")).fetchall()
    if doctor_ids:
        print(f"\n  Doctor IDs: {[r[0] for r in doctor_ids]}")
        print(f"  Doctor ID type: {type(doctor_ids[0][0]).__name__}")
    
    print("\n" + "=" * 60)
    print("  Verification complete ✅")
    print("=" * 60)

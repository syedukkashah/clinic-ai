"""
MediFlow Seed Script
====================
Run from the backend/ directory:

    python seed.py

Populates:
  1. doctors      — 11 canonical doctors
  2. patients     — derived from appointments.csv unique patient_ids
  3. appointments — 58k rows from appointments.csv
  4. daily_load   — 28k rows from daily_load.csv

Idempotent: skips any table that already has rows.
"""

import os
import sys
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

# ── Env ──────────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))
except ImportError:
    pass  # dotenv optional — fall back to shell env

DB_URL = "postgresql://mediflow:{}@localhost:5432/mediflow".format(
    os.environ.get("POSTGRES_PASSWORD", "mediflow123")
)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, '..', '..', 'ml_service', 'data')
APPOINTMENTS_CSV = os.path.join(DATA_DIR, 'appointments.csv')
DAILY_LOAD_CSV   = os.path.join(DATA_DIR, 'daily_load.csv')

# ── Canonical doctors ─────────────────────────────────────────────────────────
DOCTORS = [
    {"id": 1,  "name": "Dr. Ahmed Raza",     "specialty": "general",     "avg_consult_duration": 9.0},
    {"id": 2,  "name": "Dr. Sara Malik",     "specialty": "general",     "avg_consult_duration": 11.0},
    {"id": 3,  "name": "Dr. Kamran Iqbal",   "specialty": "general",     "avg_consult_duration": 13.0},
    {"id": 4,  "name": "Dr. Nadia Hussain",  "specialty": "cardiology",  "avg_consult_duration": 18.0},
    {"id": 5,  "name": "Dr. Tariq Butt",     "specialty": "cardiology",  "avg_consult_duration": 15.0},
    {"id": 6,  "name": "Dr. Ayesha Khan",    "specialty": "pediatrics",  "avg_consult_duration": 12.0},
    {"id": 7,  "name": "Dr. Bilal Chaudhry", "specialty": "pediatrics",  "avg_consult_duration": 11.0},
    {"id": 8,  "name": "Dr. Zara Siddiqui",  "specialty": "dermatology", "avg_consult_duration": 10.0},
    {"id": 9,  "name": "Dr. Usman Qureshi",  "specialty": "dermatology", "avg_consult_duration": 11.0},
    {"id": 10, "name": "Dr. Hina Javed",     "specialty": "orthopedics", "avg_consult_duration": 16.0},
    {"id": 11, "name": "Dr. Faisal Sheikh",  "specialty": "orthopedics", "avg_consult_duration": 14.0},
]

BATCH = 500  # rows per INSERT batch


# ── Helpers ───────────────────────────────────────────────────────────────────
def to_none(val):
    """Convert NaN / NaT / None → None for psycopg2."""
    if val is None:
        return None
    if isinstance(val, float) and np.isnan(val):
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    return val


def parse_dt(val):
    if to_none(val) is None:
        return None
    try:
        return pd.to_datetime(val).to_pydatetime()
    except Exception:
        return None


def parse_date(val):
    if to_none(val) is None:
        return None
    try:
        return pd.to_datetime(val).date()
    except Exception:
        return None


def parse_bool(val, default=None):
    v = to_none(val)
    if v is None:
        return default
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, float)):
        return bool(int(v))
    if isinstance(v, str):
        return v.strip().lower() in ('1', 'true', 'yes')
    return default


def derive_status(row) -> str:
    """
    Infer AppointmentStatus from showed_up + actual_start.
    Historical seed data: showed_up=True + actual_start present → Completed
                          showed_up=False → Cancelled
                          otherwise      → Pending
    """
    showed = parse_bool(row.get('showed_up'))
    actual_start = to_none(row.get('actual_start'))
    if showed is False:
        return 'CANCELLED'
    if showed is True and actual_start is not None:
        return 'COMPLETED'
    return 'PENDING'


def batched_insert(conn, sql, records):
    total = len(records)
    for i in range(0, total, BATCH):
        conn.execute(text(sql), records[i:i + BATCH])
        conn.commit()
        done = min(i + BATCH, total)
        print(f"    {done}/{total}", end='\r')
    print()


# ── Step 1: Doctors ───────────────────────────────────────────────────────────
def seed_doctors(conn):
    count = conn.execute(text("SELECT COUNT(*) FROM doctors")).scalar()
    if count:
        print(f"  ⏭  Doctors already seeded ({count} rows). Skipping.")
        return

    conn.execute(
        text("""
            INSERT INTO doctors (id, name, specialty, image_url, is_available, avg_consult_duration)
            VALUES (:id, :name, :specialty, NULL, TRUE, :avg_consult_duration)
        """),
        DOCTORS,
    )
    conn.commit()
    print(f"  ✅ Inserted {len(DOCTORS)} doctors.")


# ── Step 2: Patients ──────────────────────────────────────────────────────────
def seed_patients(conn, df: pd.DataFrame):
    count = conn.execute(text("SELECT COUNT(*) FROM patients")).scalar()
    if count:
        print(f"  ⏭  Patients already seeded ({count} rows). Skipping.")
        return

    unique = df[['patient_id', 'patient_preferred_lang']].drop_duplicates(subset='patient_id')
    records = [
        {
            "id": str(row['patient_id']),
            "name": f"Patient {row['patient_id']}",
            "email": None,
            "phone": None,
            "preferred_lang": str(row.get('patient_preferred_lang', 'en'))[:5],
        }
        for _, row in unique.iterrows()
    ]

    batched_insert(conn, """
        INSERT INTO patients (id, name, email, phone, preferred_lang)
        VALUES (:id, :name, :email, :phone, :preferred_lang)
        ON CONFLICT (id) DO NOTHING
    """, records)
    print(f"  ✅ Inserted {len(records)} patients.")


# ── Step 3: Appointments ──────────────────────────────────────────────────────
def seed_appointments(conn, df: pd.DataFrame):
    count = conn.execute(text("SELECT COUNT(*) FROM appointments")).scalar()
    if count:
        print(f"  ⏭  Appointments already seeded ({count} rows). Skipping.")
        return

    # Valid enum values — guard against dirty CSV data
    VALID_URGENCY = {'ROUTINE', 'MODERATE', 'URGENT'}
    VALID_CHANNEL = {'CHAT', 'VOICE_NOTE', 'WEBRTC_CALL', 'TWILIO_CALL'}

    records = []
    for _, row in df.iterrows():
        urgency = str(row.get('urgency', 'routine')).strip().upper()
        if urgency not in VALID_URGENCY:
            urgency = 'ROUTINE'

        channel = to_none(row.get('booking_channel'))
        if channel is not None:
            channel = str(channel).strip().upper()
            if channel not in VALID_CHANNEL:
                channel = None

        records.append({
            "id": str(row['appointment_id']),
            "patient_id": str(row['patient_id']),
            "doctor_id": int(row['doctor_id']),
            "slot_id": None,                            # no slots in CSV
            "scheduled_at": parse_dt(row.get('scheduled_at')),
            "date": parse_date(row.get('scheduled_date')),
            "time": None,
            "status": derive_status(row),
            "urgency": urgency,
            "reason": None,
            "complaint": to_none(row.get('complaint')),
            "specialty": to_none(row.get('specialty')),
            "patient_age": int(row['patient_age']) if to_none(row.get('patient_age')) is not None else None,
            "booking_channel": channel,
            "booking_lead_days": int(row['booking_lead_days']) if to_none(row.get('booking_lead_days')) is not None else None,
            "predicted_wait_min": 0,
            "is_follow_up": parse_bool(row.get('is_follow_up'), default=False),
            "showed_up": parse_bool(row.get('showed_up')),
            "actual_wait_minutes":float(row['actual_wait_minutes']) if to_none(row.get('actual_wait_minutes')) is not None else None,
            "actual_start": parse_dt(row.get('actual_start')),
            "actual_end": parse_dt(row.get('actual_end')),
        })

    batched_insert(conn, """
        INSERT INTO appointments (
            id, patient_id, doctor_id, slot_id,
            scheduled_at, date, time,
            status, urgency,
            reason, complaint, specialty,
            patient_age, booking_channel, booking_lead_days,
            predicted_wait_min, is_follow_up,
            showed_up, actual_wait_minutes, actual_start, actual_end
        ) VALUES (
            :id, :patient_id, :doctor_id, :slot_id,
            :scheduled_at, :date, :time,
            CAST(:status AS appointmentstatus),
            CAST(:urgency AS urgencylevel),
            :reason, :complaint, :specialty,
            :patient_age,
            CAST(:booking_channel AS bookingchannel),
            :booking_lead_days,
            :predicted_wait_min, :is_follow_up,
            :showed_up, :actual_wait_minutes, :actual_start, :actual_end
        ) ON CONFLICT (id) DO NOTHING
    """, records)
    print(f"  ✅ Inserted {len(records)} appointments.")


# ── Step 4: Daily load ────────────────────────────────────────────────────────
def seed_daily_load(conn):
    count = conn.execute(text("SELECT COUNT(*) FROM daily_load")).scalar()
    if count:
        print(f"  ⏭  Daily load already seeded ({count} rows). Skipping.")
        return

    df = pd.read_csv(DAILY_LOAD_CSV)
    print(f"  Read {len(df)} rows from daily_load.csv")

    records = [
        {
            "doctor_id": int(row['doctor_id']),
            "specialty": str(row['specialty']),
            "scheduled_date": parse_date(row['scheduled_date']),
            "hour_of_day": int(row['hour_of_day']),
            "day_of_week": int(row['day_of_week']),
            "week_of_year": int(row['week_of_year']),
            "is_holiday": parse_bool(row.get('is_holiday'), default=False),
            "is_day_after_holiday":parse_bool(row.get('is_day_after_holiday'), default=False),
            "is_ramadan": parse_bool(row.get('is_ramadan'), default=False),
            "season": to_none(row.get('season')),
            "patient_count": int(row['patient_count']) if to_none(row.get('patient_count')) is not None else 0,
            "lag_1w": float(row['lag_1w'])      if to_none(row.get('lag_1w'))      is not None else None,
            "lag_2w": float(row['lag_2w'])      if to_none(row.get('lag_2w'))      is not None else None,
            "roll_4w_avg": float(row['roll_4w_avg']) if to_none(row.get('roll_4w_avg')) is not None else None,
        }
        for _, row in df.iterrows()
    ]

    batched_insert(conn, """
        INSERT INTO daily_load (
            doctor_id, specialty, scheduled_date, hour_of_day,
            day_of_week, week_of_year,
            is_holiday, is_day_after_holiday, is_ramadan, season,
            patient_count, lag_1w, lag_2w, roll_4w_avg
        ) VALUES (
            :doctor_id, :specialty, :scheduled_date, :hour_of_day,
            :day_of_week, :week_of_year,
            :is_holiday, :is_day_after_holiday, :is_ramadan, :season,
            :patient_count, :lag_1w, :lag_2w, :roll_4w_avg
        ) ON CONFLICT (doctor_id, scheduled_date, hour_of_day) DO NOTHING
    """, records)
    print(f"  ✅ Inserted {len(records)} daily_load rows.")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("  MediFlow Seed Script")
    print("=" * 50)

    print("\nReading appointments.csv...")
    appt_df = pd.read_csv(APPOINTMENTS_CSV)
    print(f"  {len(appt_df)} rows loaded.\n")

    engine = create_engine(DB_URL, echo=False)
    with engine.connect() as conn:
        print("Step 1 — Doctors")
        seed_doctors(conn)

        print("\nStep 2 — Patients")
        seed_patients(conn, appt_df)

        print("\nStep 3 — Appointments")
        seed_appointments(conn, appt_df)

        print("\nStep 4 — Daily load")
        seed_daily_load(conn)

    print("\n" + "=" * 50)
    print("  Seed complete ✅")
    print("=" * 50)


if __name__ == "__main__":
    main()
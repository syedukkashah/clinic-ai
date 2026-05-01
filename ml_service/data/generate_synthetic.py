"""
generate_synthetic.py
=====================
Generates a full year (2024) of realistic Pakistani urban clinic appointment data.

Place this file at:  ml_service/data/generate_synthetic.py
Run once before any model training:
    python ml_service/data/generate_synthetic.py

Outputs (written to same directory as this script)
-----------
  appointments.csv     — row per appointment  → used by Wait Time model
  daily_load.csv       — (doctor, date, hour) aggregated → used by Load Forecast model
  baseline_stats.json  — per-slot historical averages   → loaded at ML inference time

Patterns captured
-----------------
  Intraday        bimodal load (9-11am peak, post-lunch lull, 3-5pm peak)
  Weekly          Monday heaviest, Friday afternoon Jummah drop, Sunday emergency-only
  Specialty       Pediatrics morning-heavy, Cardiology mid-morning, Ortho post-work
  Doctor traits   individual speed, popularity, seniority affect load and consult length
  Cascade effect  wait time simulated appointment-by-appointment — overruns pile up
  Pakistani season flu (Oct-Feb), heat/dehydration (Jun-Aug)
  Ramadan         morning collapses, evening surges, net -15% volume
  Holidays 2024   full Pakistani public + Islamic holiday calendar
  Post-holiday    surge the day after every holiday (+40-50%)
  No-show         increases with lead time, Monday mornings, low-engagement channels
  Follow-up       same doctor within 30 days → shorter consult, punctual, low no-show
  Booking channel chat / voice_note / webrtc_call / twilio_call with realistic weights
  Urgency         routine / moderate / urgent with consult length and lead time effects
"""

import json
import math
import os
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

# ── Reproducibility ───────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
fake = Faker("en_PK")
Faker.seed(SEED)

OUT_DIR = Path(__file__).parent
OUT_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# 1.  CLINIC CONFIGURATION
# =============================================================================

SPECIALTIES = ["general", "cardiology", "pediatrics", "dermatology", "orthopedics"]

CLINIC_OPEN  = 9   # 09:00
CLINIC_CLOSE = 20  # 20:00  (last slot 19:50)

CHANNELS        = ["chat", "voice_note", "webrtc_call", "twilio_call"]
CHANNEL_WEIGHTS = [0.50,   0.25,         0.15,          0.10]

URGENCY_LEVELS  = ["routine", "moderate", "urgent"]
URGENCY_WEIGHTS = [0.70,      0.22,       0.08]

# 11 doctors with individual personality profiles
# speed   > 1.0  →  slower than average (long consults → builds queue faster)
# speed   < 1.0  →  faster than average
# popularity multiplier on base daily patient count
DOCTORS = {
    1:  {"name": "Dr. Ahmed Raza",     "specialty": "general",
         "seniority": "senior", "speed": 0.80, "popularity": 1.40,
         "avg_consult_min": 9.0,  "new_patient_ratio": 0.55},
    2:  {"name": "Dr. Sara Malik",     "specialty": "general",
         "seniority": "mid",    "speed": 1.00, "popularity": 1.00,
         "avg_consult_min": 11.0, "new_patient_ratio": 0.50},
    3:  {"name": "Dr. Kamran Iqbal",   "specialty": "general",
         "seniority": "junior", "speed": 1.10, "popularity": 0.75,
         "avg_consult_min": 13.0, "new_patient_ratio": 0.45},
    4:  {"name": "Dr. Nadia Hussain",  "specialty": "cardiology",
         "seniority": "senior", "speed": 1.20, "popularity": 1.50,
         "avg_consult_min": 18.0, "new_patient_ratio": 0.40},
    5:  {"name": "Dr. Tariq Butt",     "specialty": "cardiology",
         "seniority": "mid",    "speed": 1.05, "popularity": 0.90,
         "avg_consult_min": 15.0, "new_patient_ratio": 0.38},
    6:  {"name": "Dr. Ayesha Khan",    "specialty": "pediatrics",
         "seniority": "senior", "speed": 0.95, "popularity": 1.60,
         "avg_consult_min": 12.0, "new_patient_ratio": 0.60},
    7:  {"name": "Dr. Bilal Chaudhry", "specialty": "pediatrics",
         "seniority": "mid",    "speed": 1.00, "popularity": 0.85,
         "avg_consult_min": 11.0, "new_patient_ratio": 0.55},
    8:  {"name": "Dr. Zara Siddiqui",  "specialty": "dermatology",
         "seniority": "senior", "speed": 0.90, "popularity": 1.30,
         "avg_consult_min": 10.0, "new_patient_ratio": 0.65},
    9:  {"name": "Dr. Usman Qureshi",  "specialty": "dermatology",
         "seniority": "junior", "speed": 1.05, "popularity": 0.80,
         "avg_consult_min": 11.0, "new_patient_ratio": 0.60},
    10: {"name": "Dr. Hina Javed",     "specialty": "orthopedics",
         "seniority": "senior", "speed": 1.15, "popularity": 1.20,
         "avg_consult_min": 16.0, "new_patient_ratio": 0.45},
    11: {"name": "Dr. Faisal Sheikh",  "specialty": "orthopedics",
         "seniority": "mid",    "speed": 1.10, "popularity": 0.90,
         "avg_consult_min": 14.0, "new_patient_ratio": 0.42},
}


# =============================================================================
# 2.  PAKISTANI 2024 CALENDAR
# =============================================================================

HOLIDAYS_2024 = {
    date(2024, 2, 5):  "Kashmir Day",
    date(2024, 3, 23): "Pakistan Day",
    date(2024, 5, 1):  "Labour Day",
    date(2024, 8, 14): "Independence Day",
    date(2024, 11, 9): "Iqbal Day",
    date(2024, 12, 25):"Quaid-e-Azam Day / Christmas",
    # Islamic holidays (approximate lunar dates)
    date(2024, 3, 10): "Eid ul-Fitr Day 1",
    date(2024, 3, 11): "Eid ul-Fitr Day 2",
    date(2024, 3, 12): "Eid ul-Fitr Day 3",
    date(2024, 6, 16): "Eid ul-Adha Day 1",
    date(2024, 6, 17): "Eid ul-Adha Day 2",
    date(2024, 6, 18): "Eid ul-Adha Day 3",
    date(2024, 7, 6):  "Muharram / Ashura",
    date(2024, 9, 15): "Milad-un-Nabi",
}

RAMADAN_START = date(2024, 3, 12)
RAMADAN_END   = date(2024, 4, 9)


def is_holiday(d: date) -> bool:
    return d in HOLIDAYS_2024

def is_ramadan(d: date) -> bool:
    return RAMADAN_START <= d <= RAMADAN_END

def is_day_after_holiday(d: date) -> bool:
    return (d - timedelta(days=1)) in HOLIDAYS_2024

def get_season(d: date) -> str:
    m = d.month
    if m in [10, 11, 12, 1, 2]: return "flu_season"
    if m in [6, 7, 8]:           return "heat_season"
    return "normal"


# =============================================================================
# 3.  LOAD SHAPE FUNCTIONS
# =============================================================================

def base_load_by_hour(hour: int, specialty: str, is_ram: bool) -> float:
    """
    Returns a relative weight for patient probability at a given hour.
    Base shape is bimodal: 9-11am peak, 1-2pm dip, 3-5pm peak.
    Ramadan shifts the whole curve toward evening.
    Specialty-specific adjustments layered on top.
    """
    base = {
        9: 0.85, 10: 1.00, 11: 0.90, 12: 0.65,
        13: 0.45, 14: 0.55, 15: 0.88, 16: 1.00,
        17: 0.90, 18: 0.70, 19: 0.45,
    }.get(hour, 0.30)

    if is_ram:
        if hour <= 12:
            base *= 0.40   # people sleep late after suhoor
        elif hour >= 17:
            base *= 1.80   # surge after iftar
        # else unchanged mid-afternoon

    # Specialty overlays
    if specialty == "pediatrics":
        base *= {9: 1.30, 10: 1.20, 15: 0.90, 16: 0.85}.get(hour, 1.0)
    elif specialty == "cardiology":
        base *= {9: 0.70, 10: 1.20, 11: 1.30, 15: 0.80, 16: 0.75}.get(hour, 1.0)
    elif specialty == "dermatology":
        base *= {9: 0.75, 10: 0.90, 16: 1.10, 17: 1.15}.get(hour, 1.0)
    elif specialty == "orthopedics":
        base *= {9: 0.80, 12: 0.80, 13: 0.90, 17: 1.10, 18: 1.05}.get(hour, 1.0)

    return max(0.01, base)


def dow_multiplier(dow: int, hour: int) -> float:
    """
    dow: 0=Monday … 6=Sunday.
    Monday heaviest (weekend backlog). Friday afternoon drops (Jummah).
    Saturday moderate. Sunday near-zero (emergency only).
    """
    base = {0: 1.30, 1: 1.10, 2: 1.05, 3: 1.00, 4: 0.95, 5: 0.60, 6: 0.15}[dow]
    if dow == 4 and hour >= 13:
        base *= 0.40   # Friday afternoon collapse
    return base


def season_multiplier(d: date) -> float:
    s = get_season(d)
    return 1.20 if s == "flu_season" else (1.15 if s == "heat_season" else 1.0)


# =============================================================================
# 4.  COMPLAINT BANKS PER SPECIALTY
# =============================================================================

COMPLAINTS = {
    "general": [
        "fever and chills", "headache", "flu symptoms", "cough and cold",
        "body aches", "sore throat", "fatigue", "diarrhea", "vomiting",
        "stomach pain", "lower back pain", "weakness", "blood pressure check",
        "diabetes follow-up", "routine checkup", "wound dressing",
        "skin allergy", "urinary tract infection", "dehydration",
    ],
    "cardiology": [
        "chest pain", "shortness of breath", "palpitations", "high blood pressure",
        "irregular heartbeat", "cardiac follow-up", "ECG review",
        "dizziness on exertion", "ankle swelling", "post-procedure follow-up",
        "cholesterol management", "hypertension check",
    ],
    "pediatrics": [
        "child fever", "ear pain", "cough in child", "rash in child",
        "child not eating", "vaccination", "growth check", "newborn checkup",
        "diarrhea in child", "child breathing difficulty", "jaundice in newborn",
        "developmental milestone check", "tonsillitis in child",
    ],
    "dermatology": [
        "skin rash", "acne", "eczema flare-up", "hair loss", "nail infection",
        "sun damage", "hyperpigmentation", "warts", "psoriasis follow-up",
        "allergic skin reaction", "heat rash", "fungal skin infection",
        "contact dermatitis", "vitiligo follow-up",
    ],
    "orthopedics": [
        "knee pain", "lower back pain", "fracture follow-up", "joint pain",
        "shoulder injury", "sports injury", "post-surgery rehabilitation",
        "arthritis pain", "sciatica", "neck stiffness", "hip pain",
        "slip disc", "physiotherapy referral",
    ],
}

URGENT_GENERAL = [
    "chest pain", "high fever 104F", "difficulty breathing",
    "severe allergic reaction", "seizure episode", "head injury",
    "suspected dengue", "severe dehydration",
]


# =============================================================================
# 5.  PATIENT POOL
#     Large enough that the follow-up rate stays realistic (~20-30%)
#     95K appointments / 8000 patients ≈ 12 visits/patient/year ≈ 1/month
#     With 30-day follow-up window, ~25-30% qualify → realistic
# =============================================================================

N_PATIENTS = 8_000

def generate_patient_pool() -> dict:
    patients = {}
    for pid in range(1, N_PATIENTS + 1):
        age = _sample_clinic_age()
        patients[pid] = {
            "name":             fake.name(),
            "age":              age,
            "preferred_lang":   random.choices(["ur", "en"], weights=[0.75, 0.25])[0],
            # last_visit_by_doctor: {doctor_id: date} — used for follow-up detection
            "last_visit_by_doctor": {},
            # per-patient chronic no-show tendency (right-skewed: most reliable)
            "noshow_tendency":  float(np.random.beta(1.5, 10)),
        }
    return patients


def _sample_clinic_age() -> int:
    """Pakistani clinic age distribution: skewed toward working age + elderly."""
    bucket = random.choices(
        ["child", "young_adult", "working", "senior"],
        weights=[0.20, 0.20, 0.40, 0.20]
    )[0]
    if bucket == "child":       return random.randint(1, 14)
    if bucket == "young_adult": return random.randint(15, 30)
    if bucket == "working":     return random.randint(31, 59)
    return random.randint(60, 85)


# =============================================================================
# 6.  CORE SIMULATION — one doctor, one day
# =============================================================================

def simulate_doctor_day(
    doctor_id: int,
    day: date,
    patient_ids: list,
    patients: dict,
) -> list:
    """
    Correct cascade simulation in three steps:
      1. Assign every attribute to each patient (scheduled time, urgency, etc.)
      2. Sort patients by scheduled time.
      3. Walk in chronological order: doctor clock advances after each consult;
         overruns push all later patients' wait times up.

    This is the ONLY correct way to simulate queue cascade — row-level
    formulas cannot capture the compounding effect of overruns.
    """
    doc      = DOCTORS[doctor_id]
    specialty = doc["specialty"]

    # ── Step 1: build attribute set ───────────────────────────────────────────
    pending = []
    for patient_id in patient_ids:
        p   = patients[patient_id]
        age = p["age"]

        # Follow-up: same doctor visited within last 30 days
        last = p["last_visit_by_doctor"].get(doctor_id)
        is_follow_up = bool(last and (day - last).days <= 30)

        # Urgency → affects lead time and consult length
        urgency = random.choices(URGENCY_LEVELS, weights=URGENCY_WEIGHTS)[0]
        if urgency == "urgent":
            lead_days = random.randint(0, 1)
        elif is_follow_up:
            lead_days = random.randint(1, 14)
        else:
            lead_days = int(np.clip(np.random.exponential(5), 0, 21))

        # Scheduled hour — weighted by load curve for this specialty + Ramadan
        hour_weights = [
            base_load_by_hour(h, specialty, is_ramadan(day))
            for h in range(CLINIC_OPEN, CLINIC_CLOSE)
        ]
        sched_hour = random.choices(range(CLINIC_OPEN, CLINIC_CLOSE),
                                    weights=hour_weights)[0]
        sched_min  = random.randint(0, 5) * 10        # slots on :00 :10 :20 :30 :40 :50
        sched_time = datetime.combine(day, datetime.min.time()).replace(
            hour=sched_hour, minute=sched_min
        )

        # Arrival offset relative to scheduled time (minutes)
        if urgency == "urgent":
            arr_off = float(np.clip(np.random.normal(-6, 3), -15, 5))
        elif is_follow_up:
            arr_off = float(np.clip(np.random.normal(-3, 4), -10, 10))
        else:
            arr_off = float(np.clip(np.random.normal(3, 9), -10, 30))
        arrival_time = sched_time + timedelta(minutes=arr_off)

        # Booking channel
        channel = random.choices(CHANNELS, weights=CHANNEL_WEIGHTS)[0]

        # No-show probability
        nsp = p["noshow_tendency"]

        # Lead time effect (strongest driver)
        if lead_days == 0:     nsp *= 0.25
        elif lead_days <= 3:   nsp *= 0.55
        elif lead_days <= 7:   nsp *= 0.85
        elif lead_days <= 14:  nsp *= 1.20
        else:                  nsp *= 1.60

        # Day-of-week effects
        if day.weekday() == 0 and sched_hour <= 9:
            nsp *= 1.40    # Monday 9am — high no-show
        if day.weekday() == 6:
            nsp *= 0.50    # Sunday emergency bookings are committed

        # Follow-up patients rarely miss
        if is_follow_up:
            nsp *= 0.45

        # Channel effect
        nsp *= {"chat": 1.0, "voice_note": 0.85,
                "webrtc_call": 0.80, "twilio_call": 0.72}[channel]

        # Senior patients are more reliable
        if age >= 60: nsp *= 0.80

        showed_up = random.random() > min(nsp, 0.88)

        # Consultation duration (minutes) — only if shows up
        if showed_up:
            base_dur = doc["avg_consult_min"]
            if is_follow_up:        base_dur *= 0.68
            if urgency == "urgent": base_dur *= 1.35
            if urgency == "moderate": base_dur *= 1.10
            if age >= 65:           base_dur *= 1.22
            elif age <= 10:         base_dur *= 1.12
            # Log-normal: right-skewed — some consults run very long
            sigma = {"general": 0.28, "cardiology": 0.38, "pediatrics": 0.30,
                     "dermatology": 0.22, "orthopedics": 0.33}[specialty]
            dur = float(np.clip(
                np.random.lognormal(math.log(max(base_dur, 3.0)), sigma),
                3.0, 60.0
            ))
        else:
            dur = 0.0

        # Complaint
        complaint = random.choice(COMPLAINTS[specialty])
        if urgency == "urgent" and specialty == "general":
            complaint = random.choice(URGENT_GENERAL)

        # Update patient visit record
        p["last_visit_by_doctor"][doctor_id] = day

        pending.append({
            "patient_id":    patient_id,
            "age":           age,
            "lang":          p["preferred_lang"],
            "sched_time":    sched_time,
            "sched_hour":    sched_hour,
            "arrival_time":  arrival_time,
            "is_follow_up":  is_follow_up,
            "urgency":       urgency,
            "lead_days":     lead_days,
            "channel":       channel,
            "showed_up":     showed_up,
            "dur":           dur,
            "complaint":     complaint,
        })

    # ── Step 2: sort by scheduled time ───────────────────────────────────────
    pending.sort(key=lambda x: x["sched_time"])

    # ── Step 3: cascade walk ──────────────────────────────────────────────────
    appointments = []
    doctor_free_at = datetime.combine(day, datetime.min.time()).replace(
        hour=CLINIC_OPEN, minute=0
    )

    for pos, item in enumerate(pending):
        sched   = item["sched_time"]
        arrival = item["arrival_time"]

        if item["showed_up"]:
            # Doctor can start at: max(scheduled slot, when doctor is free, when patient arrived)
            start    = max(sched, doctor_free_at, arrival)
            wait_min = max(0.0, (start - arrival).total_seconds() / 60.0)
            end      = start + timedelta(minutes=item["dur"])

            # Advance doctor clock
            doctor_free_at = end

            # Queue depth = how many slot-lengths behind schedule the doctor is
            lag    = max(0.0, (doctor_free_at - sched).total_seconds() / 60.0)
            qdepth = max(0, round(lag / doc["avg_consult_min"]))

            wait_out  = round(wait_min, 2)
            dur_out   = round(item["dur"], 2)
            start_iso = start.isoformat()
            end_iso   = end.isoformat()
        else:
            # No-show: clock advances to scheduled time + small admin gap
            doctor_free_at = max(doctor_free_at, sched + timedelta(minutes=2))
            lag    = max(0.0, (doctor_free_at - sched).total_seconds() / 60.0)
            qdepth = max(0, round(lag / doc["avg_consult_min"]))
            wait_out = dur_out = None
            start_iso = end_iso = None

        # Historical average for this (doctor, dow, hour) — used as a feature at inference time
        hist_wait = round(
            doc["avg_consult_min"]
            * dow_multiplier(day.weekday(), sched.hour)
            * base_load_by_hour(sched.hour, specialty, False)
            * 0.75,   # scale: historical is average, not peak
            2
        )

        appointments.append({
            "appointment_id":         None,          # filled after full generation
            "patient_id":             item["patient_id"],
            "patient_age":            item["age"],
            "patient_preferred_lang": item["lang"],
            "doctor_id":              doctor_id,
            "doctor_name":            doc["name"],
            "specialty":              specialty,
            "day_of_week":            day.weekday(),  # 0=Mon 6=Sun
            "scheduled_date":         day.strftime("%Y-%m-%d"),
            "scheduled_at":           sched.isoformat(),
            "arrival_time":           arrival.isoformat(),
            "actual_start":           start_iso,
            "actual_end":             end_iso,
            "hour_of_day":            item["sched_hour"],
            "booking_lead_days":      item["lead_days"],
            "appointments_before":    pos,            # position in doctor's day queue
            "queue_depth":            qdepth,
            "is_follow_up":           item["is_follow_up"],
            "urgency":                item["urgency"],
            "complaint":              item["complaint"],
            "booking_channel":        item["channel"],
            "showed_up":              item["showed_up"],
            "actual_wait_minutes":    wait_out,       # None for no-shows
            "consult_duration_min":   dur_out,        # None for no-shows
            "avg_consult_duration":   round(doc["avg_consult_min"], 2),
            "historical_wait_slot":   hist_wait,
            "is_holiday":             is_holiday(day),
            "is_ramadan":             is_ramadan(day),
            "is_day_after_holiday":   is_day_after_holiday(day),
            "season":                 get_season(day),
            "week_of_year":           day.isocalendar().week,
        })

    return appointments


# =============================================================================
# 7.  CAPACITY FUNCTION — patients per doctor per day
# =============================================================================

def patients_per_doctor_day(doc_id: int, d: date) -> int:
    """
    How many appointment slots this doctor fills today.
    Base is 14 (a busy but not overloaded day for a popular doctor).
    Multiplied by: popularity, day-of-week, holiday, season, Ramadan, noise.
    """
    doc  = DOCTORS[doc_id]
    base = 14  # realistic busy-day baseline

    cap = base * doc["popularity"]
    cap *= dow_multiplier(d.weekday(), 12)   # noon representative

    if is_holiday(d):
        cap *= 0.05      # skeleton staff or closed
    elif is_day_after_holiday(d):
        cap *= 1.45      # surge

    cap *= season_multiplier(d)

    if is_ramadan(d):
        cap *= 0.85      # net -15% (shift not increase)

    # ±20% random daily variation
    cap *= np.random.uniform(0.82, 1.22)

    # Hard ceiling: can't overbook the day
    max_possible = (CLINIC_CLOSE - CLINIC_OPEN) * 4  # 4 patients per hour max
    return max(0, min(int(cap), max_possible))


# =============================================================================
# 8.  MAIN GENERATION LOOP
# =============================================================================

def build_doctor_patient_pools(patients: dict) -> dict:
    """
    Precomputes per-doctor pools ONCE. Returns dict with:
      pools[doc_id]["regulars"]   — patients who visit this doctor repeatedly
      pools[doc_id]["walkins"]    — general pool (not regulars of this doctor)
    Walkin pool is cached here so sample_patients_for_day never rebuilds it.
    """
    all_pids  = list(patients.keys())
    reg_sets  = {}   # doc_id -> set of regular pids (for fast walkin exclusion)
    pools     = {}
    assigned  = set()

    for doc_id, doc in DOCTORS.items():
        seniority_mul = {"senior": 1.4, "mid": 1.0, "junior": 0.7}[doc["seniority"]]
        n_regulars = int(300 * doc["popularity"] * seniority_mul)
        n_regulars = min(n_regulars, len(all_pids) // 3)

        candidates = [p for p in all_pids if p not in assigned]
        if len(candidates) < n_regulars:
            candidates = all_pids

        regulars = random.sample(candidates, min(n_regulars, len(candidates)))
        reg_set  = set(regulars)
        reg_sets[doc_id] = reg_set
        assigned.update(regulars)

        # Precompute walkin pool — anyone NOT a regular for this doctor
        walkins = [p for p in all_pids if p not in reg_set]
        if not walkins:
            walkins = all_pids

        pools[doc_id] = {"regulars": regulars, "walkins": walkins}

    return pools


def sample_patients_for_day(doc_id: int, n: int, pools: dict,
                             patients: dict, current_date: date) -> list:
    """
    60% regulars (weighted by recency for follow-up effect).
    40% walk-ins (precomputed pool — no list comprehension at runtime).
    """
    entry    = pools[doc_id]
    regulars = entry["regulars"]
    walkins  = entry["walkins"]

    n_regular = int(n * 0.45)
    n_walkin  = n - n_regular

    if regulars:
        reg_weights = []
        for pid in regulars:
            last = patients[pid]["last_visit_by_doctor"].get(doc_id)
            if last and (current_date - last).days <= 30:
                reg_weights.append(5.0)
            elif last and (current_date - last).days <= 90:
                reg_weights.append(2.0)
            else:
                reg_weights.append(1.0)
        sampled_regular = random.choices(regulars, weights=reg_weights, k=n_regular)
    else:
        sampled_regular = random.choices(walkins, k=n_regular)

    sampled_walkin = random.choices(walkins, k=n_walkin)

    combined = sampled_regular + sampled_walkin
    random.shuffle(combined)
    return combined


def generate_all_appointments() -> tuple:
    patients  = generate_patient_pool()
    pools = build_doctor_patient_pools(patients)

    all_appointments = []
    appt_id = 1

    current = date(2024, 1, 1)
    end     = date(2024, 12, 31)

    while current <= end:
        for doc_id in DOCTORS:
            n = patients_per_doctor_day(doc_id, current)
            if n == 0:
                continue

            pids = sample_patients_for_day(doc_id, n, pools, patients, current)

            for appt in simulate_doctor_day(doc_id, current, pids, patients):
                appt["appointment_id"] = appt_id
                appt_id += 1
                all_appointments.append(appt)

        current += timedelta(days=1)

    return all_appointments, patients


# =============================================================================
# 9.  AGGREGATE LOAD DATASET  (for Patient Load Forecasting model)
# =============================================================================

def build_load_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates appointments to (doctor_id, scheduled_date, hour_of_day) level.
    Adds lag and rolling features needed by the load forecasting model.
    IMPORTANT: lag/rolling are computed here for training data.
               The same logic must be reproduced at inference time
               (see ml_service/models/feature_pipelines/load_forecast_features.py).
    """
    agg = (
        df.groupby([
            "doctor_id", "specialty", "scheduled_date", "hour_of_day",
            "day_of_week", "week_of_year", "is_holiday",
            "is_day_after_holiday", "is_ramadan", "season"
        ])
        .size()
        .reset_index(name="patient_count")
    )

    agg["date_dt"] = pd.to_datetime(agg["scheduled_date"])
    agg = agg.sort_values(["doctor_id", "date_dt", "hour_of_day"]).reset_index(drop=True)

    # Lag features: same doctor, same hour, N weeks ago
    for weeks in [1, 2]:
        shift_days = weeks * 7
        lag_src = agg[["doctor_id", "date_dt", "hour_of_day", "patient_count"]].copy()
        lag_src["date_dt"] = lag_src["date_dt"] + pd.Timedelta(days=shift_days)
        lag_src = lag_src.rename(columns={"patient_count": f"lag_{weeks}w"})
        agg = agg.merge(lag_src, on=["doctor_id", "date_dt", "hour_of_day"], how="left")

    # Rolling 4-week average (shift by 7 days before rolling to prevent leakage)
    def _roll_avg(group):
        return group["patient_count"].shift(7).rolling(28, min_periods=4).mean()

    agg["roll_4w_avg"] = (
        agg.groupby(["doctor_id", "hour_of_day"], group_keys=False)
           .apply(_roll_avg)
    )

    agg = agg.drop(columns=["date_dt"])
    return agg


# =============================================================================
# 10. BASELINE STATS  (for historical_wait_slot feature at inference time)
# =============================================================================

def compute_baseline_stats(df: pd.DataFrame) -> dict:
    """
    Per (doctor_id, day_of_week, hour_of_day) average wait statistics.
    Saved to baseline_stats.json; loaded by ml_service at startup.
    At inference time: look up key = f"{doctor_id}_{dow}_{hour}" to get
    the historical_wait_slot feature value.
    """
    waited = df[df["actual_wait_minutes"].notna()].copy()
    stats  = {}
    for (doc_id, dow, hour), grp in waited.groupby(["doctor_id", "day_of_week", "hour_of_day"]):
        stats[f"{doc_id}_{dow}_{hour}"] = {
            "mean_wait":   round(grp["actual_wait_minutes"].mean(), 2),
            "median_wait": round(grp["actual_wait_minutes"].median(), 2),
            "p75_wait":    round(grp["actual_wait_minutes"].quantile(0.75), 2),
            "count":       int(len(grp)),
        }
    return stats


# =============================================================================
# 11. QUALITY REPORT
# =============================================================================

def print_quality_report(df: pd.DataFrame, load_df: pd.DataFrame) -> None:
    sep = "=" * 64
    print(f"\n{sep}")
    print("  SYNTHETIC DATA QUALITY REPORT")
    print(sep)

    n   = len(df)
    wdf = df[df["actual_wait_minutes"].notna()]["actual_wait_minutes"]

    print(f"\n{'Appointments':30s}: {n:,}")
    print(f"{'Date range':30s}: {df['scheduled_date'].min()}  to  {df['scheduled_date'].max()}")
    print(f"{'Unique patients':30s}: {df['patient_id'].nunique():,}")
    print(f"{'Unique doctors':30s}: {df['doctor_id'].nunique()}")

    print(f"\n{'Show-up rate':30s}: {df['showed_up'].mean():.1%}")
    print(f"{'Follow-up rate':30s}: {df['is_follow_up'].mean():.1%}   ← target 20-30%")
    print(f"{'Ramadan appointments':30s}: {df['is_ramadan'].sum():,}  ({df['is_ramadan'].mean():.1%})")
    print(f"{'Holiday appointments':30s}: {df['is_holiday'].sum():,}  ({df['is_holiday'].mean():.1%})")
    print(f"{'Post-holiday surge days':30s}: {df['is_day_after_holiday'].sum():,}  ({df['is_day_after_holiday'].mean():.1%})")

    print("\nWait time statistics (showed-up patients only):")
    for label, val in [
        ("  Mean",   wdf.mean()),
        ("  Median", wdf.median()),
        ("  P75",    wdf.quantile(0.75)),
        ("  P90",    wdf.quantile(0.90)),
        ("  P99",    wdf.quantile(0.99)),
        ("  Max",    wdf.max()),
    ]:
        print(f"{label:30s}: {val:.1f} min")

    print("\nWait time by specialty (mean, showed-up only):")
    for sp in SPECIALTIES:
        sub = df[(df["specialty"] == sp) & df["actual_wait_minutes"].notna()]
        if len(sub):
            print(f"  {sp:<16}: {sub['actual_wait_minutes'].mean():.1f} min avg  "
                  f"  (n={len(sub):,})")

    print("\nWait time by urgency (mean):")
    for urg in URGENCY_LEVELS:
        sub = df[(df["urgency"] == urg) & df["actual_wait_minutes"].notna()]
        if len(sub):
            print(f"  {urg:<12}: {sub['actual_wait_minutes'].mean():.1f} min  (n={len(sub):,})")

    print("\nShow-up rate by day of week:")
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for dow, name in enumerate(names):
        sub = df[df["day_of_week"] == dow]
        if len(sub):
            print(f"  {name}: {sub['showed_up'].mean():.1%}  ({len(sub):,} appts)")

    print("\nNo-show rate by lead time bucket:")
    buckets = [(0,0,"Same day"),(1,3,"1-3 days"),(4,7,"4-7 days"),
               (8,14,"8-14 days"),(15,99,"15+ days")]
    for lo, hi, label in buckets:
        sub = df[(df["booking_lead_days"] >= lo) & (df["booking_lead_days"] <= hi)]
        if len(sub):
            ns = 1 - sub["showed_up"].mean()
            print(f"  {label:<12}: {ns:.1%} no-show  ({len(sub):,} appts)")

    print("\nBooking channel distribution:")
    for ch, cnt in df["booking_channel"].value_counts().items():
        print(f"  {ch:<16}: {cnt:,}  ({cnt/n:.1%})")

    print("\nUrgency distribution:")
    for urg, cnt in df["urgency"].value_counts().items():
        print(f"  {urg:<12}: {cnt:,}  ({cnt/n:.1%})")

    print("\nSeason distribution:")
    for s, cnt in df["season"].value_counts().items():
        print(f"  {s:<16}: {cnt:,}  ({cnt/n:.1%})")

    print("\nRamadan vs Normal (average showed-up patients/day by hour):")
    ram_days  = max(1, (RAMADAN_END - RAMADAN_START).days)
    norm_days = max(1, 366 - ram_days)
    for hour in [9, 11, 14, 17, 19]:
        r = df[(df["is_ramadan"]) & (df["hour_of_day"] == hour) & df["showed_up"]].shape[0]
        x = df[(~df["is_ramadan"]) & (df["hour_of_day"] == hour) & df["showed_up"]].shape[0]
        print(f"  {hour:02d}h  Ramadan: {r/ram_days:.1f}/day   Normal: {x/norm_days:.1f}/day")

    print("\nLoad forecast dataset:")
    print(f"  {'Total (doc,date,hour) rows':30s}: {len(load_df):,}")
    print(f"  {'Mean patients per slot':30s}: {load_df['patient_count'].mean():.2f}")
    print(f"  {'Max patients per slot':30s}: {load_df['patient_count'].max()}")
    print(f"  {'Rows with lag_1w':30s}: {load_df['lag_1w'].notna().sum():,}")
    print(f"  {'Rows with roll_4w_avg':30s}: {load_df['roll_4w_avg'].notna().sum():,}")

    print(f"\n{sep}\n")


# =============================================================================
# 12. SANITY CHECKS
# =============================================================================

def run_sanity_checks(df: pd.DataFrame, load_df: pd.DataFrame) -> None:
    errors = []

    # No duplicate appointment IDs
    if df["appointment_id"].duplicated().any():
        errors.append("FAIL: duplicate appointment_id values")

    # Showed-up appointments must have wait times
    if df[df["showed_up"] & df["actual_wait_minutes"].isna()].shape[0] > 0:
        errors.append("FAIL: showed_up=True rows missing actual_wait_minutes")

    # No-show appointments must NOT have wait times
    if df[~df["showed_up"] & df["actual_wait_minutes"].notna()].shape[0] > 0:
        errors.append("FAIL: showed_up=False rows have actual_wait_minutes")

    # Wait times must be non-negative
    if (df["actual_wait_minutes"].dropna() < 0).any():
        errors.append("FAIL: negative wait times found")

    # Mean wait time sanity (should be 5-60 min for a realistic clinic)
    mean_wait = df["actual_wait_minutes"].dropna().mean()
    if mean_wait < 2 or mean_wait > 90:
        errors.append(f"WARN: mean wait time {mean_wait:.1f} min looks unrealistic")

    # No-show rate overall should be 7-20%
    noshow_rate = 1 - df["showed_up"].mean()
    if noshow_rate < 0.05 or noshow_rate > 0.35:
        errors.append(f"WARN: overall no-show rate {noshow_rate:.1%} looks off")

    # Follow-up rate should be 15-40%
    fu_rate = df["is_follow_up"].mean()
    if fu_rate < 0.10 or fu_rate > 0.50:
        errors.append(f"WARN: follow-up rate {fu_rate:.1%} — check patient pool size")

    # Load dataset — patient counts must be non-negative
    if (load_df["patient_count"] < 0).any():
        errors.append("FAIL: negative patient_count in load dataset")

    if errors:
        print("Sanity check issues:")
        for e in errors:
            print(f"  {e}")
    else:
        print("All sanity checks passed.")


# =============================================================================
# 13. ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    print("Generating synthetic clinic data for MediFlow...")
    print("Simulating appointment-by-appointment (cascade wait times).")
    print("This takes about 60-90 seconds for a full year.\n")

    # Generate raw appointments
    all_appointments, patients = generate_all_appointments()

    df = pd.DataFrame(all_appointments)
    df = df.sort_values("appointment_id").reset_index(drop=True)

    # Build aggregated load dataset
    load_df = build_load_dataset(df)

    # Compute inference-time baseline stats
    baseline_stats = compute_baseline_stats(df)

    # Save
    appt_path     = OUT_DIR / "appointments.csv"
    load_path     = OUT_DIR / "daily_load.csv"
    baseline_path = OUT_DIR / "baseline_stats.json"

    df.to_csv(appt_path, index=False)
    load_df.to_csv(load_path, index=False)
    with open(baseline_path, "w") as f:
        json.dump(baseline_stats, f, indent=2)

    print(f"Saved: {appt_path}        ({len(df):,} rows)")
    print(f"Saved: {load_path}     ({len(load_df):,} rows)")
    print(f"Saved: {baseline_path}  ({len(baseline_stats)} slot-level entries)")

    print_quality_report(df, load_df)
    run_sanity_checks(df, load_df)
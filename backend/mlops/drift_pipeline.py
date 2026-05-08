"""
Drift Detection Pipeline
========================
Generates synthetic reference + drifted versions of:
  - daily_load.csv  (hourly patient-count aggregates per doctor)
  - appointments.csv (individual appointment records)

Then runs three drift detectors on every feature:
  - PSI  (Population Stability Index) — numerical & categorical
  - KS   (Kolmogorov–Smirnov test)   — numerical only
  - Chi² (Chi-squared test)           — categorical only

Results are saved to /mnt/user-data/outputs/
"""

import numpy as np
import pandas as pd
from scipy import stats
import warnings, os, json
warnings.filterwarnings("ignore")

np.random.seed(42)
OUT = "/mnt/user-data/outputs"
os.makedirs(OUT, exist_ok=True)

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

SPECIALTIES = {
    1: ("Dr. Ahmed Raza",   "general"),
    2: ("Dr. Sara Malik",   "general"),
    3: ("Dr. Usman Tariq",  "cardiology"),
    4: ("Dr. Ayesha Khan",  "pediatrics"),
}

COMPLAINTS = [
    "fever and chills", "cough and cold", "stomach pain", "headache",
    "weakness", "diarrhea", "skin allergy", "flu symptoms",
    "wound dressing", "blood pressure check", "diabetes follow-up",
    "lower back pain", "routine checkup", "dehydration", "sore throat",
]

CHANNELS   = ["chat", "voice_note", "webrtc_call", "twilio_call"]
URGENCY    = ["routine", "moderate", "urgent"]
LANGS      = ["ur", "en"]
SEASONS    = ["flu_season", "normal", "summer"]


# ─────────────────────────────────────────────
# 1. DAILY LOAD  (reference)
# ─────────────────────────────────────────────

def make_daily_load(n_doctors=4, n_weeks=4, drifted=False):
    rows = []
    base_date = pd.Timestamp("2024-02-01")

    for doc_id in range(1, n_doctors + 1):
        specialty = SPECIALTIES[doc_id][1]
        for week in range(n_weeks):
            for dow in range(7):
                date = base_date + pd.Timedelta(weeks=week, days=dow)
                woy  = date.isocalendar().week

                is_holiday          = bool(np.random.rand() < 0.04)
                is_day_after_holiday = bool(np.random.rand() < 0.06)
                is_ramadan          = False
                season              = "flu_season" if date.month in [1,2,12] else "normal"

                # working hours: Mon–Fri dense, Sat sparse, Sun minimal
                if dow < 5:
                    hours = sorted(np.random.choice(range(9, 20), size=np.random.randint(6, 11), replace=False))
                elif dow == 5:
                    hours = sorted(np.random.choice(range(9, 17), size=np.random.randint(3, 7), replace=False))
                else:
                    hours = sorted(np.random.choice(range(10, 15), size=np.random.randint(0, 3), replace=False))

                for h in hours:
                    # DRIFT: patient_count mean shifts from ~2.5 → ~5.5
                    #        hour distribution skews toward afternoon
                    if drifted:
                        mu = 5.5 + (h - 14) * 0.3          # afternoon peak
                    else:
                        mu = 2.5 + (h - 9) * 0.1            # slight morning peak

                    count = max(1, int(np.random.poisson(max(0.5, mu))))

                    rows.append({
                        "doctor_id":            doc_id,
                        "specialty":            specialty,
                        "scheduled_date":       date.date(),
                        "hour_of_day":          h,
                        "day_of_week":          dow,
                        "week_of_year":         woy,
                        "is_holiday":           is_holiday,
                        "is_day_after_holiday": is_day_after_holiday,
                        "is_ramadan":           is_ramadan,
                        "season":               season,
                        "patient_count":        count,
                        "lag_1w":               np.nan if week == 0 else float(count + np.random.randint(-1, 2)),
                        "lag_2w":               np.nan if week < 2  else float(count + np.random.randint(-1, 2)),
                        "roll_4w_avg":          np.nan if week < 3  else round(mu + np.random.uniform(-0.3, 0.3), 4),
                    })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# 2. APPOINTMENTS  (reference)
# ─────────────────────────────────────────────

def make_appointments(n_per_doctor_day=8, n_doctors=4, n_days=20, drifted=False, id_start=1):
    rows = []
    base_date = pd.Timestamp("2024-02-01")
    appt_id   = id_start

    for doc_id in range(1, n_doctors + 1):
        doc_name, specialty = SPECIALTIES[doc_id]
        cumulative_appts = 0

        for d in range(n_days):
            date = base_date + pd.Timedelta(days=d)
            dow  = date.dayofweek
            woy  = date.isocalendar().week

            is_holiday           = bool(np.random.rand() < 0.04)
            is_day_after_holiday = bool(np.random.rand() < 0.06)
            is_ramadan           = False
            season               = "flu_season" if date.month in [1, 2, 12] else "normal"

            n_slots = max(0, int(np.random.normal(n_per_doctor_day, 2)))
            if dow == 6: n_slots = max(0, n_slots // 3)

            hour_cursor = pd.Timestamp(str(date.date()) + " 09:00:00")

            for slot in range(n_slots):
                patient_id  = np.random.randint(100, 9000)
                patient_age = int(np.clip(np.random.lognormal(3.5, 0.5), 1, 90))
                lang        = np.random.choice(LANGS, p=[0.7, 0.3])

                lead_days   = int(np.random.exponential(5))
                scheduled_at = hour_cursor + pd.Timedelta(minutes=np.random.randint(0, 30))
                arrival_offset = pd.Timedelta(minutes=int(np.random.normal(2, 8)))
                arrival_time   = scheduled_at + arrival_offset

                hour_of_day = scheduled_at.hour

                # DRIFT: show_up rate drops 75% → 45%
                show_up_prob = 0.45 if drifted else 0.78
                showed_up = bool(np.random.rand() < show_up_prob)

                if showed_up:
                    # DRIFT: wait times balloon from ~8 min → ~25 min
                    wait_mu = 25.0 if drifted else 8.0
                    wait    = max(0.0, round(np.random.exponential(wait_mu), 2))

                    # DRIFT: consult duration shrinks 10 min → 6 min (rushed)
                    dur_mu  = 6.0 if drifted else 10.0
                    dur     = max(1.0, round(np.random.normal(dur_mu, 2.5), 2))

                    actual_start = arrival_time + pd.Timedelta(minutes=wait)
                    actual_end   = actual_start + pd.Timedelta(minutes=dur)
                    actual_wait  = wait
                    consult_dur  = dur
                else:
                    actual_start = pd.NaT
                    actual_end   = pd.NaT
                    actual_wait  = np.nan
                    consult_dur  = np.nan

                # DRIFT: urgency skews toward urgent
                if drifted:
                    urgency = np.random.choice(URGENCY, p=[0.35, 0.40, 0.25])
                else:
                    urgency = np.random.choice(URGENCY, p=[0.65, 0.25, 0.10])

                # DRIFT: booking channel shifts away from chat toward calls
                if drifted:
                    channel = np.random.choice(CHANNELS, p=[0.15, 0.25, 0.35, 0.25])
                else:
                    channel = np.random.choice(CHANNELS, p=[0.40, 0.25, 0.20, 0.15])

                is_follow_up = bool(np.random.rand() < 0.20)
                queue_depth  = int(np.random.poisson(2))

                avg_consult  = round(10 + np.random.normal(0, 2), 2)
                hist_wait    = round(7 + np.random.normal(0, 1.5), 2)

                rows.append({
                    "appointment_id":       appt_id,
                    "patient_id":           patient_id,
                    "patient_age":          patient_age,
                    "patient_preferred_lang": lang,
                    "doctor_id":            doc_id,
                    "doctor_name":          doc_name,
                    "specialty":            specialty,
                    "day_of_week":          dow,
                    "scheduled_date":       date.date(),
                    "scheduled_at":         scheduled_at,
                    "arrival_time":         arrival_time,
                    "actual_start":         actual_start,
                    "actual_end":           actual_end,
                    "hour_of_day":          hour_of_day,
                    "booking_lead_days":    lead_days,
                    "appointments_before":  cumulative_appts,
                    "queue_depth":          queue_depth,
                    "is_follow_up":         is_follow_up,
                    "urgency":              urgency,
                    "complaint":            np.random.choice(COMPLAINTS),
                    "booking_channel":      channel,
                    "showed_up":            showed_up,
                    "actual_wait_minutes":  actual_wait,
                    "consult_duration_min": consult_dur,
                    "avg_consult_duration": avg_consult,
                    "historical_wait_slot": hist_wait,
                    "is_holiday":           is_holiday,
                    "is_ramadan":           is_ramadan,
                    "is_day_after_holiday": is_day_after_holiday,
                    "season":               season,
                    "week_of_year":         woy,
                })

                appt_id      += 1
                cumulative_appts += 1
                hour_cursor   += pd.Timedelta(minutes=np.random.randint(10, 30))

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# 3. DRIFT DETECTORS
# ─────────────────────────────────────────────

def psi_score(ref, cur, bins=10):
    """Population Stability Index. >0.2 = major drift."""
    combined = np.concatenate([ref, cur])
    breakpoints = np.percentile(combined, np.linspace(0, 100, bins + 1))
    breakpoints = np.unique(breakpoints)
    if len(breakpoints) < 3:
        return 0.0

    ref_counts = np.histogram(ref, bins=breakpoints)[0] + 1e-4
    cur_counts = np.histogram(cur, bins=breakpoints)[0] + 1e-4
    ref_pct = ref_counts / ref_counts.sum()
    cur_pct = cur_counts / cur_counts.sum()

    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def psi_categorical(ref_series, cur_series):
    """PSI for categorical columns."""
    categories = set(ref_series) | set(cur_series)
    ref_pct = {c: (ref_series == c).mean() + 1e-4 for c in categories}
    cur_pct = {c: (cur_series == c).mean() + 1e-4 for c in categories}
    return float(sum(
        (cur_pct[c] - ref_pct[c]) * np.log(cur_pct[c] / ref_pct[c])
        for c in categories
    ))


def run_drift_detection(ref_df, cur_df, dataset_name):
    results = []

    numerical_cols   = ref_df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = ref_df.select_dtypes(include=["object", "bool", "category"]).columns.tolist()

    # — Numerical: PSI + KS —
    for col in numerical_cols:
        r = ref_df[col].dropna().values
        c = cur_df[col].dropna().values
        if len(r) < 5 or len(c) < 5:
            continue

        psi  = psi_score(r, c)
        ks_stat, ks_p = stats.ks_2samp(r, c)

        results.append({
            "dataset":    dataset_name,
            "feature":    col,
            "type":       "numerical",
            "PSI":        round(psi, 4),
            "PSI_status": "🔴 DRIFT" if psi > 0.2 else ("🟡 WARNING" if psi > 0.1 else "🟢 OK"),
            "KS_stat":    round(ks_stat, 4),
            "KS_pvalue":  round(ks_p, 4),
            "KS_status":  "🔴 DRIFT" if ks_p < 0.05 else "🟢 OK",
            "Chi2_stat":  None,
            "Chi2_pvalue": None,
            "Chi2_status": None,
        })

    # — Categorical: PSI + Chi² —
    for col in categorical_cols:
        r = ref_df[col].astype(str).dropna()
        c = cur_df[col].astype(str).dropna()

        psi = psi_categorical(r, c)

        cats = sorted(set(r) | set(c))
        r_counts = np.array([(r == cat).sum() for cat in cats]) + 1e-4
        c_counts = np.array([(c == cat).sum() for cat in cats]) + 1e-4
        c_counts_expected = r_counts / r_counts.sum() * c_counts.sum()
        chi2, chi2_p = stats.chisquare(c_counts, f_exp=c_counts_expected)

        results.append({
            "dataset":    dataset_name,
            "feature":    col,
            "type":       "categorical",
            "PSI":        round(psi, 4),
            "PSI_status": "🔴 DRIFT" if psi > 0.2 else ("🟡 WARNING" if psi > 0.1 else "🟢 OK"),
            "KS_stat":    None,
            "KS_pvalue":  None,
            "KS_status":  None,
            "Chi2_stat":  round(chi2, 4),
            "Chi2_pvalue": round(chi2_p, 4),
            "Chi2_status": "🔴 DRIFT" if chi2_p < 0.05 else "🟢 OK",
        })

    return pd.DataFrame(results)


# ─────────────────────────────────────────────
# 4. GENERATE & RUN
# ─────────────────────────────────────────────

print("Generating daily_load datasets...")
dl_ref    = make_daily_load(drifted=False)
dl_drift  = make_daily_load(drifted=True)

print(f"  Reference : {len(dl_ref)} rows")
print(f"  Drifted   : {len(dl_drift)} rows")

print("\nGenerating appointments datasets...")
ap_ref   = make_appointments(drifted=False, id_start=1)
ap_drift = make_appointments(drifted=True,  id_start=10000)

print(f"  Reference : {len(ap_ref)} rows")
print(f"  Drifted   : {len(ap_drift)} rows")

# Save CSVs
dl_ref.to_csv(f"{OUT}/ref_daily_load.csv",    index=False)
dl_drift.to_csv(f"{OUT}/drifted_daily_load.csv", index=False)
ap_ref.to_csv(f"{OUT}/ref_appointments.csv",  index=False)
ap_drift.to_csv(f"{OUT}/drifted_appointments.csv", index=False)

print("\nRunning drift detection...")
dl_results = run_drift_detection(dl_ref, dl_drift, "daily_load")
ap_results = run_drift_detection(ap_ref, ap_drift, "appointments")

all_results = pd.concat([dl_results, ap_results], ignore_index=True)
all_results.to_csv(f"{OUT}/drift_report.csv", index=False)


# ─────────────────────────────────────────────
# 5. PRETTY PRINT SUMMARY
# ─────────────────────────────────────────────

print("\n" + "="*70)
print("  DRIFT DETECTION REPORT")
print("="*70)

for dataset in ["daily_load", "appointments"]:
    subset = all_results[all_results["dataset"] == dataset]
    print(f"\n📊  Dataset: {dataset.upper()}")
    print(f"{'Feature':<28} {'Type':<12} {'PSI':>6}  {'PSI':^9}  {'KS/Chi²':>8}  {'Status'}")
    print("-"*70)

    for _, row in subset.sort_values("PSI", ascending=False).iterrows():
        stat_val   = row["KS_stat"] if row["type"] == "numerical" else row["Chi2_stat"]
        stat_label = f"KS={stat_val:.3f}" if row["type"] == "numerical" else f"X²={stat_val:.1f}"
        stat_status = row["KS_status"] if row["type"] == "numerical" else row["Chi2_status"]

        print(f"{row['feature']:<28} {row['type']:<12} {row['PSI']:>6.3f}  "
              f"{row['PSI_status']:^9}  {stat_label:>10}  {stat_status or ''}")

# Summary counts
drifted_features = all_results[
    (all_results["PSI_status"] == "🔴 DRIFT") |
    (all_results["KS_status"]  == "🔴 DRIFT") |
    (all_results["Chi2_status"] == "🔴 DRIFT")
]["feature"].unique()

print("\n" + "="*70)
print(f"  SUMMARY: {len(drifted_features)} drifted features detected")
print("="*70)
for f in drifted_features:
    row = all_results[all_results["feature"] == f].iloc[0]
    print(f"  • {f} ({row['dataset']})  PSI={row['PSI']:.3f}")

print(f"\nFiles saved to: {OUT}/")
print("  ref_daily_load.csv       — reference daily load")
print("  drifted_daily_load.csv   — drifted daily load")
print("  ref_appointments.csv     — reference appointments")
print("  drifted_appointments.csv — drifted appointments")
print("  drift_report.csv         — full feature-level report")

import pandas as pd
import numpy as np

FEATURE_COLS = [
    "day_of_week", "hour_of_day", "week_of_year",
    "is_holiday", "day_after_holiday", "lag_1w", "lag_2w", "roll_4w"
]

def build_load_features(df_appointments: pd.DataFrame) -> pd.DataFrame:
    """
    Build features for patient load forecasting from raw appointments.
    """
    if df_appointments.empty:
        return pd.DataFrame()

    # a. Aggregate to (doctor_id, scheduled_date, hour_of_day) level
    group_cols = ["doctor_id", "specialty", "scheduled_date", "hour_of_day", "day_of_week"]
    agg_df = df_appointments.groupby(group_cols, dropna=False).size().reset_index(name="patient_count")

    # b. Sort chronologically
    agg_df = agg_df.sort_values(["doctor_id", "scheduled_date", "hour_of_day"]).reset_index(drop=True)

    # c. Create time_key
    agg_df["time_key"] = pd.to_datetime(agg_df["scheduled_date"]) + pd.to_timedelta(agg_df["hour_of_day"], unit="h")

    # d. Build lag features per (doctor_id, hour_of_day) group
    # Using shift(7) because 7 days = 1 week ago same hour
    def add_lags(group):
        group = group.sort_values("scheduled_date")
        group["lag_1w"] = group["patient_count"].shift(7)
        group["lag_2w"] = group["patient_count"].shift(14)
        group["roll_4w"] = group["patient_count"].shift(1).rolling(window=4, min_periods=2).mean()
        return group
        
    agg_df = agg_df.groupby(["doctor_id", "hour_of_day"], group_keys=False).apply(add_lags)

    # e. Add calendar features
    agg_df["week_of_year"] = pd.to_datetime(agg_df["scheduled_date"]).dt.isocalendar().week.astype(int)
    
    # f. Intra-day features
    agg_df["is_morning"] = agg_df["hour_of_day"].between(8, 12).astype(int)
    agg_df["is_afternoon"] = agg_df["hour_of_day"].between(13, 17).astype(int)
    agg_df["is_evening"] = agg_df["hour_of_day"].between(18, 20).astype(int)
    
    # Cyclical hour encoding
    agg_df["hour_sin"] = np.sin(2 * np.pi * agg_df["hour_of_day"] / 24)
    agg_df["hour_cos"] = np.cos(2 * np.pi * agg_df["hour_of_day"] / 24)

    try:
        holidays_df = pd.read_csv("data/holidays.csv")
        holidays_df["date"] = pd.to_datetime(holidays_df["date"])
        agg_df["date_dt"] = pd.to_datetime(agg_df["scheduled_date"])
        
        # is_holiday
        agg_df["is_holiday"] = agg_df["date_dt"].isin(holidays_df["date"]).astype(int)
        
        # day_after_holiday
        holidays_df["day_after"] = holidays_df["date"] + pd.Timedelta(days=1)
        agg_df["day_after_holiday"] = agg_df["date_dt"].isin(holidays_df["day_after"]).astype(int)
        
        agg_df = agg_df.drop(columns=["date_dt"])
    except FileNotFoundError:
        agg_df["is_holiday"] = 0
        agg_df["day_after_holiday"] = 0

    # g. Call dropna()
    agg_df = agg_df.dropna(subset=["lag_1w", "lag_2w", "roll_4w"]).reset_index(drop=True)

    # h. Return final columns
    final_cols = [
        "doctor_id", "specialty", "scheduled_date", "day_of_week", "hour_of_day", "week_of_year",
        "is_morning", "is_afternoon", "is_evening", "hour_sin", "hour_cos",
        "is_holiday", "day_after_holiday", "lag_1w", "lag_2w", "roll_4w", "patient_count"
    ]
    return agg_df[final_cols]


def get_lag_value(doctor_id: int, date: str, hour: int, weeks_back: int, db_conn) -> float:
    """Queries doctor_hourly_actuals table for lag value."""
    try:
        from sqlalchemy import text
        target_date = (pd.Timestamp(date) - pd.Timedelta(weeks=weeks_back)).strftime("%Y-%m-%d")
        query = "SELECT patient_count FROM doctor_hourly_actuals WHERE doctor_id = :doctor_id AND date = :target_date AND hour_of_day = :hour"
        result = db_conn.execute(text(query), {"doctor_id": doctor_id, "target_date": target_date, "hour": hour}).fetchone()
        return float(result[0]) if result else 0.0
    except Exception:
        return 0.0


def get_rolling_avg(doctor_id: int, date: str, hour: int, db_conn, weeks: int = 4) -> float:
    """Queries doctor_hourly_actuals for the last N weeks same doctor same hour."""
    try:
        from sqlalchemy import text
        target_dates = [(pd.Timestamp(date) - pd.Timedelta(weeks=w)).strftime("%Y-%m-%d") for w in range(1, weeks + 1)]
        params = {"doctor_id": doctor_id, "hour": hour}
        date_list_str = ", ".join([f"'{d}'" for d in target_dates])
        query = f"SELECT AVG(patient_count) FROM doctor_hourly_actuals WHERE doctor_id = :doctor_id AND date IN ({date_list_str}) AND hour_of_day = :hour"
        result = db_conn.execute(text(query), params).fetchone()
        return float(result[0]) if result and result[0] is not None else 0.0
    except Exception:
        return 0.0


def build_inference_feature_row(doctor_id: int, date: str, hour: int, db_conn, specialty: str, trained_columns: list) -> pd.DataFrame:
    """Builds a single-row DataFrame for inference matching training feature columns exactly."""
    lag_1w = get_lag_value(doctor_id, date, hour, 1, db_conn)
    lag_2w = get_lag_value(doctor_id, date, hour, 2, db_conn)
    roll_4w = get_rolling_avg(doctor_id, date, hour, db_conn)
    
    date_dt = pd.Timestamp(date)
    day_of_week = date_dt.dayofweek
    week_of_year = date_dt.isocalendar().week
    
    is_morning = 1 if 8 <= hour <= 12 else 0
    is_afternoon = 1 if 13 <= hour <= 17 else 0
    is_evening = 1 if 18 <= hour <= 20 else 0
    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)

    is_holiday = 0
    day_after_holiday = 0
    try:
        holidays_df = pd.read_csv("data/holidays.csv")
        holidays_df["date"] = pd.to_datetime(holidays_df["date"])
        is_holiday = int(date_dt in holidays_df["date"].values)
        day_after_holiday = int(date_dt in (holidays_df["date"] + pd.Timedelta(days=1)).values)
    except FileNotFoundError:
        pass
        
    row_dict = {
        "day_of_week": day_of_week,
        "hour_of_day": hour,
        "week_of_year": week_of_year,
        "is_morning": is_morning,
        "is_afternoon": is_afternoon,
        "is_evening": is_evening,
        "hour_sin": hour_sin,
        "hour_cos": hour_cos,
        "is_holiday": is_holiday,
        "day_after_holiday": day_after_holiday,
        "lag_1w": lag_1w,
        "lag_2w": lag_2w,
        "roll_4w": roll_4w
    }
    
    doc_col = f"doctor_id_{doctor_id}"
    spec_col = f"specialty_{specialty}"
    
    for col in trained_columns:
        if col not in row_dict:
            row_dict[col] = 0
            
    if doc_col in row_dict:
        row_dict[doc_col] = 1
    if spec_col in row_dict:
        row_dict[spec_col] = 1
        
    df = pd.DataFrame([row_dict])
    
    return df[trained_columns]


import pandas as pd
import numpy as np

FEATURE_COLS = [
    "day_of_week", "hour_of_day", "week_of_year",
    "is_morning", "is_afternoon", "is_evening", "hour_sin", "hour_cos",
    "is_holiday", "is_day_after_holiday", "is_ramadan", "season", 
    "lag_1w", "lag_2w", "roll_4w_avg"
]

def inject_zero_load_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Injects zero-load rows for all combinations of (doctor_id, scheduled_date, hour_of_day).
    """
    if df.empty:
        return df

    # 1. Get unique doctors & specialties
    doctor_specialties = df[['doctor_id', 'specialty']].drop_duplicates()
    
    # 2. Get date range from data
    df["date_dt"] = pd.to_datetime(df["scheduled_date"])
    dates = pd.date_range(start=df["date_dt"].min(), end=df["date_dt"].max())
    
    # 3. Hours to forecast (8 to 20)
    hours = list(range(8, 21))

    # 4. Create Cartesian product grid
    grid = pd.MultiIndex.from_product(
        [doctor_specialties['doctor_id'], dates, hours],
        names=['doctor_id', 'date_dt', 'hour_of_day']
    ).to_frame(index=False)
    
    # 5. Join back specialty
    grid = grid.merge(doctor_specialties, on='doctor_id', how='left')
    grid['scheduled_date'] = grid['date_dt'].dt.strftime('%Y-%m-%d')
    
    # 6. Recreate time features for the dense grid
    grid['day_of_week'] = grid['date_dt'].dt.dayofweek
    grid['week_of_year'] = grid['date_dt'].dt.isocalendar().week.astype(int)
    
    try:
        holidays_df = pd.read_csv("data/holidays.csv")
        holidays_df["date"] = pd.to_datetime(holidays_df["date"])
        grid["is_holiday"] = grid["date_dt"].isin(holidays_df["date"]).astype(int)
        holidays_df["day_after"] = holidays_df["date"] + pd.Timedelta(days=1)
        grid["is_day_after_holiday"] = grid["date_dt"].isin(holidays_df["day_after"]).astype(int)
    except FileNotFoundError:
        grid["is_holiday"] = 0
        grid["is_day_after_holiday"] = 0

    ramadan_start = pd.Timestamp("2024-03-12")
    ramadan_end = pd.Timestamp("2024-04-09")
    grid["is_ramadan"] = ((grid["date_dt"] >= ramadan_start) & (grid["date_dt"] <= ramadan_end)).astype(int)
    
    def get_season(month):
        if month in [10, 11, 12, 1, 2]: return "flu_season"
        if month in [6, 7, 8]: return "heat_season"
        return "normal"
    grid["season"] = grid["date_dt"].dt.month.apply(get_season)

    # 7. Merge actual patient counts
    actual_counts = df[['doctor_id', 'date_dt', 'hour_of_day', 'patient_count']].copy()
    merged = pd.merge(grid, actual_counts, on=['doctor_id', 'date_dt', 'hour_of_day'], how='left')
    merged['patient_count'] = merged['patient_count'].fillna(0)
    
    # 8. Recompute lags on dense grid
    merged = merged.sort_values(["doctor_id", "date_dt", "hour_of_day"]).reset_index(drop=True)
    
    def add_lags(group):
        group = group.sort_values("date_dt")
        group["lag_1w"] = group["patient_count"].shift(7)
        group["lag_2w"] = group["patient_count"].shift(14)
        group["roll_4w_avg"] = group["patient_count"].shift(1).rolling(window=28, min_periods=4).mean()
        return group

    merged = merged.groupby(["doctor_id", "hour_of_day"], group_keys=False).apply(add_lags)
    merged = merged.drop(columns=["date_dt"])
    merged = merged.dropna(subset=["lag_1w"]).reset_index(drop=True)
    
    # 9. Add intra-day cyclical features
    merged["is_morning"] = merged["hour_of_day"].between(8, 12).astype(int)
    merged["is_afternoon"] = merged["hour_of_day"].between(13, 17).astype(int)
    merged["is_evening"] = merged["hour_of_day"].between(18, 20).astype(int)
    merged["hour_sin"] = np.sin(2 * np.pi * merged["hour_of_day"] / 24)
    merged["hour_cos"] = np.cos(2 * np.pi * merged["hour_of_day"] / 24)
    
    return merged

def load_daily_load_csv(path: str) -> pd.DataFrame:
    """Loads daily_load.csv and injects zero rows to make grid dense."""
    df = pd.read_csv(path)
    return inject_zero_load_rows(df)

def build_load_features(df_appointments: pd.DataFrame) -> pd.DataFrame:
    """
    (Legacy) Build features for patient load forecasting from raw appointments.
    """
    if df_appointments.empty:
        return pd.DataFrame()

    group_cols = ["doctor_id", "specialty", "scheduled_date", "hour_of_day", "day_of_week"]
    agg_df = df_appointments.groupby(group_cols, dropna=False).size().reset_index(name="patient_count")
    
    # Forward to new injection pipeline
    return inject_zero_load_rows(agg_df)


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
    roll_4w_avg = get_rolling_avg(doctor_id, date, hour, db_conn, weeks=4)
    
    date_dt = pd.Timestamp(date)
    day_of_week = date_dt.dayofweek
    week_of_year = date_dt.isocalendar().week
    
    is_morning = 1 if 8 <= hour <= 12 else 0
    is_afternoon = 1 if 13 <= hour <= 17 else 0
    is_evening = 1 if 18 <= hour <= 20 else 0
    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)

    is_holiday = 0
    is_day_after_holiday = 0
    try:
        holidays_df = pd.read_csv("data/holidays.csv")
        holidays_df["date"] = pd.to_datetime(holidays_df["date"])
        is_holiday = int(date_dt in holidays_df["date"].values)
        is_day_after_holiday = int(date_dt in (holidays_df["date"] + pd.Timedelta(days=1)).values)
    except FileNotFoundError:
        pass
        
    ramadan_start = pd.Timestamp("2024-03-12")
    ramadan_end = pd.Timestamp("2024-04-09")
    is_ramadan = int(ramadan_start <= date_dt <= ramadan_end)
    
    def get_season(month):
        if month in [10, 11, 12, 1, 2]: return "flu_season"
        if month in [6, 7, 8]: return "heat_season"
        return "normal"
    season = get_season(date_dt.month)

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
        "is_day_after_holiday": is_day_after_holiday,
        "is_ramadan": is_ramadan,
        "season": season,
        "lag_1w": lag_1w,
        "lag_2w": lag_2w,
        "roll_4w_avg": roll_4w_avg
    }
    
    doc_col = f"doctor_id_{doctor_id}"
    spec_col = f"specialty_{specialty}"
    season_col = f"season_{season}"
    
    for col in trained_columns:
        if col not in row_dict:
            row_dict[col] = 0
            
    if doc_col in row_dict:
        row_dict[doc_col] = 1
    if spec_col in row_dict:
        row_dict[spec_col] = 1
    if season_col in row_dict:
        row_dict[season_col] = 1
        
    df = pd.DataFrame([row_dict])
    
    return df[trained_columns]

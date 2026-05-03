import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch

with patch("model_loader.mlflow"):
    from main import app
    from mlops.drift_baselines import compute_kl_divergence, load_baseline_distribution
    from load_features import build_load_features

@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session

@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

def test_build_load_features_aggregates_correctly():
    # Create small synthetic appointments
    dates = [datetime(2024, 1, i).strftime("%Y-%m-%d") for i in range(1, 31)]
    records = []
    for _ in range(200):
        records.append({
            "doctor_id": 1,
            "specialty": "general",
            "scheduled_date": np.random.choice(dates),
            "hour_of_day": np.random.randint(8, 20),
            "day_of_week": 0,
        })
    df = pd.DataFrame(records)
    
    res = build_load_features(df)
    
    assert "patient_count" in res.columns
    assert "lag_1w" in res.columns
    assert res.isna().sum().sum() == 0
    # Assert aggregated (no row-level data)
    assert len(res) <= 30 * 12

def test_build_load_features_time_split_is_chronological():
    dates = [datetime(2024, 1, i).strftime("%Y-%m-%d") for i in range(1, 31)]
    records = []
    for _ in range(500):
        records.append({
            "doctor_id": 1,
            "specialty": "general",
            "scheduled_date": np.random.choice(dates),
            "hour_of_day": np.random.randint(8, 20),
            "day_of_week": 0,
        })
    df = pd.DataFrame(records)
    res = build_load_features(df)
    
    sorted_dates = sorted(res["scheduled_date"].unique())
    split_date = sorted_dates[int(len(sorted_dates) * 0.85)]
    
    train = res[res["scheduled_date"] < split_date]
    val = res[res["scheduled_date"] >= split_date]
    
    assert train["scheduled_date"].max() < val["scheduled_date"].min()

@pytest.mark.asyncio
@patch("main.get_current_model_version", return_value="1")
@patch("main.patient_load_model")
@patch("main.trained_columns", [])
@patch("main.get_db")
@patch("load_features.build_inference_feature_row")
async def test_load_forecast_endpoint_returns_correct_schema(mock_build, mock_get_db, mock_model, mock_version, async_client):
    mock_model.predict.return_value = np.array([3, 4, 7, 8, 6, 5, 4, 3, 4, 5, 6, 5, 4])
    
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.run_sync = AsyncMock(return_value=pd.DataFrame([{"a": 1} for _ in range(13)]))
    mock_get_db.return_value = mock_session
    
    from database import get_db
    app.dependency_overrides[get_db] = lambda: mock_session
    
    import main
    original_model = main.patient_load_model
    main.patient_load_model = mock_model
    
    try:
        response = await async_client.post(
            "/predict/patient-load",
            json={"doctor_id": 1, "date": "2025-06-15", "specialty": "general"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "forecast" in data
        assert isinstance(data["forecast"], dict)
        for h in range(8, 21):
            assert str(h) in data["forecast"]
            assert data["forecast"][str(h)] >= 0
        assert 8 <= data["peak_hour"] <= 20
        assert data["peak_hour_patients"] >= 0
    finally:
        main.patient_load_model = original_model
        app.dependency_overrides.pop(get_db, None)

@pytest.mark.asyncio
async def test_load_forecast_past_date_returns_400(async_client):
    import main
    mock_model = MagicMock()
    original_model = main.patient_load_model
    main.patient_load_model = mock_model
    try:
        response = await async_client.post(
            "/predict/patient-load",
            json={"doctor_id": 1, "date": "2020-01-01", "specialty": "general"}
        )
        assert response.status_code == 400
    finally:
        main.patient_load_model = original_model

@pytest.mark.asyncio
async def test_load_forecast_model_not_loaded_returns_503(async_client):
    import main
    original_model = main.patient_load_model
    main.patient_load_model = None
    try:
        response = await async_client.post(
            "/predict/patient-load",
            json={"doctor_id": 1, "date": "2025-06-15", "specialty": "general"}
        )
        assert response.status_code == 503
    finally:
        main.patient_load_model = original_model

def test_compute_kl_divergence_identical_distributions():
    p = np.random.normal(5, 1, 1000)
    q = np.random.normal(5, 1, 1000)
    res = compute_kl_divergence(p, q)
    assert res < 0.05

def test_compute_kl_divergence_different_distributions_above_threshold():
    p = np.random.normal(5, 1, 1000)
    q = np.random.normal(10, 2, 1000)
    res = compute_kl_divergence(p, q)
    assert res > 0.1

def test_load_baseline_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_baseline_distribution("nonexistent_model")

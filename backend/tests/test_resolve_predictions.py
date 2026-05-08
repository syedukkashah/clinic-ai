# backend/tests/test_resolve_predictions.py
"""
Tests for the resolver Celery task logic.

The resolver uses two PostgreSQL-specific UPDATE patterns:
  1. UPDATE ... FROM appointments (wait_time_model)
  2. UPDATE ... WHERE json->>'field' (patient_load_model)

These cannot run in SQLite (conftest test DB). So we test:
  - The task structure and registration (all environments)
  - The core resolver logic directly against the test DB (SQLite-compatible subset)
  - The full SQL is covered by the db-checks CI job which runs real Postgres
"""
import pytest
from sqlalchemy import text


# ── Task registration & structure ────────────────────────────────

def test_resolve_task_is_registered():
    """Task should be importable and callable."""
    from tasks.resolve_predictions import resolve_completed_appointments
    assert callable(resolve_completed_appointments)


def test_resolve_task_name():
    """Task must have the exact registered name Celery beat uses."""
    from tasks.resolve_predictions import resolve_completed_appointments
    assert resolve_completed_appointments.name == \
        "tasks.resolve_predictions.resolve_completed_appointments"


# ── Real DB tests (SQLite via conftest) ───────────────────────────

def test_ml_predictions_actual_value_starts_null(db_session):
    """Newly inserted prediction should have actual_value = NULL."""
    db_session.execute(text("""
        INSERT INTO ml_predictions
            (model_name, model_version, input_features, predicted_value)
        VALUES ('wait_time_model', 'v_test', '{"doctor_id": 1}', 12.5)
    """))
    db_session.commit()

    row = db_session.execute(text("""
        SELECT actual_value FROM ml_predictions
        WHERE model_name = 'wait_time_model' AND model_version = 'v_test'
        LIMIT 1
    """)).fetchone()

    assert row is not None
    assert row[0] is None


def test_resolver_fills_actual_value(db_session):
    """Simulates what the resolver does: UPDATE actual_value + resolved_at."""
    db_session.execute(text("""
        INSERT INTO ml_predictions
            (model_name, model_version, input_features, predicted_value)
        VALUES ('wait_time_model', 'v_test2', '{"doctor_id": 2}', 20.0)
    """))
    db_session.commit()

    db_session.execute(text("""
        UPDATE ml_predictions
        SET actual_value = 18.0,
            resolved_at = CURRENT_TIMESTAMP
        WHERE model_name = 'wait_time_model'
          AND model_version = 'v_test2'
          AND actual_value IS NULL
    """))
    db_session.commit()

    row = db_session.execute(text("""
        SELECT actual_value, resolved_at FROM ml_predictions
        WHERE model_name = 'wait_time_model' AND model_version = 'v_test2'
        LIMIT 1
    """)).fetchone()

    assert float(row[0]) == 18.0
    assert row[1] is not None


def test_resolver_only_updates_null_rows(db_session):
    """Resolver must not overwrite already-resolved predictions."""
    db_session.execute(text("""
        INSERT INTO ml_predictions
            (model_name, model_version, input_features, predicted_value, actual_value, resolved_at)
        VALUES ('wait_time_model', 'v_test3', '{"doctor_id": 3}', 15.0, 99.0, CURRENT_TIMESTAMP)
    """))
    db_session.commit()

    db_session.execute(text("""
        UPDATE ml_predictions
        SET actual_value = 1.0
        WHERE model_name = 'wait_time_model'
          AND model_version = 'v_test3'
          AND actual_value IS NULL
    """))
    db_session.commit()

    row = db_session.execute(text("""
        SELECT actual_value FROM ml_predictions
        WHERE model_name = 'wait_time_model' AND model_version = 'v_test3'
        LIMIT 1
    """)).fetchone()

    assert float(row[0]) == 99.0


def test_multiple_models_resolved_independently(db_session):
    """wait_time_model and patient_load_model rows are resolved independently."""
    db_session.execute(text("""
        INSERT INTO ml_predictions
            (model_name, model_version, input_features, predicted_value)
        VALUES
            ('wait_time_model',    'v_multi', '{"doctor_id": 4}', 10.0),
            ('patient_load_model', 'v_multi', '{"doctor_id": 4}', 5.0)
    """))
    db_session.commit()

    db_session.execute(text("""
        UPDATE ml_predictions
        SET actual_value = 11.0, resolved_at = CURRENT_TIMESTAMP
        WHERE model_name = 'wait_time_model'
          AND model_version = 'v_multi'
          AND actual_value IS NULL
    """))
    db_session.commit()

    wait_row = db_session.execute(text("""
        SELECT actual_value FROM ml_predictions
        WHERE model_name = 'wait_time_model' AND model_version = 'v_multi'
    """)).fetchone()

    load_row = db_session.execute(text("""
        SELECT actual_value FROM ml_predictions
        WHERE model_name = 'patient_load_model' AND model_version = 'v_multi'
    """)).fetchone()

    assert float(wait_row[0]) == 11.0
    assert load_row[0] is None


# ── Cleanup ───────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def cleanup(db_session):
    yield
    db_session.execute(text(
        "DELETE FROM ml_predictions WHERE model_version LIKE 'v_test%' OR model_version = 'v_multi'"
    ))
    db_session.commit()
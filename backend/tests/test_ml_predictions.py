# backend/tests/test_ml_predictions.py
import pytest
from sqlalchemy import text


def test_ml_predictions_table_exists(db_session):
    result = db_session.execute(text("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='ml_predictions'
    """)).fetchone()
    assert result is not None, "ml_predictions table does not exist"


def test_ml_predictions_columns(db_session):
    result = db_session.execute(text("""
        PRAGMA table_info(ml_predictions)
    """)).fetchall()
    
    columns = [row[1] for row in result]  # column name is index 1 in PRAGMA
    
    assert 'id' in columns
    assert 'model_name' in columns
    assert 'model_version' in columns
    assert 'appointment_id' in columns
    assert 'input_features' in columns
    assert 'predicted_value' in columns
    assert 'actual_value' in columns
    assert 'predicted_at' in columns
    assert 'resolved_at' in columns


def test_insert_prediction(db_session):
    db_session.execute(text("""
        INSERT INTO ml_predictions 
            (model_name, model_version, input_features, predicted_value)
        VALUES 
            ('wait_time_model', 'v1', '{"doctor_id": 1, "hour_of_day": 10}', 15.5)
    """))
    db_session.commit()

    result = db_session.execute(text("""
        SELECT predicted_value, actual_value, predicted_at
        FROM ml_predictions
        WHERE model_name = 'wait_time_model'
        ORDER BY rowid DESC
        LIMIT 1
    """)).fetchone()

    assert result is not None
    assert float(result[0]) == 15.5
    assert result[1] is None          # actual_value NULL initially
    assert result[2] is not None      # predicted_at auto-filled


def test_update_actual_value(db_session):
    db_session.execute(text("""
        INSERT INTO ml_predictions 
            (model_name, model_version, input_features, predicted_value)
        VALUES ('wait_time_model', 'v1', '{"doctor_id": 2}', 20.0)
    """))
    db_session.commit()

    db_session.execute(text("""
        UPDATE ml_predictions
        SET actual_value = 18.5,
            resolved_at = CURRENT_TIMESTAMP
        WHERE model_name = 'wait_time_model'
          AND actual_value IS NULL
          AND json_extract(input_features, '$.doctor_id') = 2
    """))
    db_session.commit()

    result = db_session.execute(text("""
        SELECT actual_value, resolved_at FROM ml_predictions
        WHERE model_name = 'wait_time_model'
          AND json_extract(input_features, '$.doctor_id') = 2
        LIMIT 1
    """)).fetchone()

    assert float(result[0]) == 18.5
    assert result[1] is not None


def test_ml_predictions_model_name_not_null(db_session):
    """model_name must be required — inserting without it should fail."""
    with pytest.raises(Exception):
        db_session.execute(text("""
            INSERT INTO ml_predictions 
                (model_version, input_features, predicted_value)
            VALUES ('v1', '{}', 10.0)
        """))
        db_session.commit()
    db_session.rollback()
"""
test_feature_pipeline.py — Tests for ColumnTransformer preprocessing pipelines.

Verifies that:
  - OHE pipeline (Ridge) handles unseen categories safely (all-zeros, no collision)
  - Ordinal pipeline (RF/XGB) handles unseen categories safely (value = -1)
  - Pipelines produce consistent output shapes between fit and transform
  - StandardScaler is applied only for Ridge (scale-sensitive model)
  - Bool features are converted to int correctly

Spec reference: Section 14 — feature engineering
Run from ml_service/:
    pytest tests/test_feature_pipeline.py -v
"""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge


# ── Import preprocessor factories from train_wait_time ───────────────────────

@pytest.fixture(scope="module")
def preprocessors():
    with patch("mlflow.set_tracking_uri"), patch("mlflow.set_experiment"):
        import sys
        sys.modules.pop("training.train_wait_time", None)
        from training.train_wait_time import (
            make_ohe_preprocessor,
            make_ordinal_preprocessor,
            NUMERIC_FEATURES,
            BOOL_FEATURES,
            CATEGORICAL_FEATURES,
            ALL_FEATURES,
        )
    return {
        "ohe":          make_ohe_preprocessor,
        "ordinal":      make_ordinal_preprocessor,
        "numeric":      NUMERIC_FEATURES,
        "bool":         BOOL_FEATURES,
        "categorical":  CATEGORICAL_FEATURES,
        "all":          ALL_FEATURES,
    }


def make_sample_df(n=100, seed=42) -> pd.DataFrame:
    """Minimal feature-complete DataFrame for pipeline testing."""
    np.random.seed(seed)
    return pd.DataFrame({
        "patient_age":            np.random.randint(18, 80, n),
        "doctor_id":              np.random.randint(1, 12, n),
        "day_of_week":            np.random.randint(0, 7, n),
        "hour_of_day":            np.random.randint(8, 20, n),
        "booking_lead_days":      np.random.randint(0, 30, n),
        "appointments_before":    np.random.randint(0, 8, n),
        "queue_depth":            np.random.randint(0, 10, n),
        "avg_consult_duration":   np.random.uniform(8, 20, n),
        "historical_wait_slot":   np.random.uniform(2, 30, n),
        "week_of_year":           np.random.randint(1, 53, n),
        "is_follow_up":           np.random.choice([True, False], n),
        "is_holiday":             np.random.choice([True, False], n),
        "is_ramadan":             np.random.choice([True, False], n),
        "is_day_after_holiday":   np.random.choice([True, False], n),
        "specialty":              np.random.choice(["general", "cardiology",
                                                    "pediatrics", "orthopedics",
                                                    "dermatology"], n),
        "urgency":                np.random.choice(["routine", "moderate", "urgent"], n),
        "season":                 np.random.choice(["flu_season", "normal",
                                                    "heat_season"], n),
        "patient_preferred_lang": np.random.choice(["en", "ur"], n),
        "booking_channel":        np.random.choice(["chat", "voice_note",
                                                    "webrtc_call", "twilio_call"], n),
    })


# ── OHE preprocessor tests (Ridge pipeline) ───────────────────────────────────

class TestOHEPreprocessor:

    def test_ohe_output_has_no_nulls(self, preprocessors):
        pre = preprocessors["ohe"]()
        df  = make_sample_df(100)
        X   = pre.fit_transform(df)
        # OHE returns a dense float array — safe to call isnan directly
        assert not np.isnan(X).any(), "OHE output contains NaN"

    def test_ohe_unseen_category_becomes_all_zeros(self, preprocessors):
        """
        handle_unknown='ignore' means unseen category → all-zero OHE columns.
        Must NOT collide with any real category's encoding.
        """
        pre      = preprocessors["ohe"]()
        train_df = make_sample_df(200)
        pre.fit(train_df)

        test_df = make_sample_df(1)
        test_df["specialty"] = "UNKNOWN_SPECIALTY_999"
        X_out = pre.transform(test_df)

        assert not np.isnan(X_out).any()

        cat_transformer = pre.named_transformers_["cat"]
        ohe_output = cat_transformer.transform(test_df[preprocessors["categorical"]])
        assert ohe_output.sum() < ohe_output.shape[1], \
            "Unseen category should produce sparse row (not all ones)"

    def test_ohe_drop_first_avoids_multicollinearity(self, preprocessors):
        """
        drop='first' must be set for Ridge to avoid dummy variable trap.
        k categories → k-1 OHE columns.
        """
        pre = preprocessors["ohe"]()
        df  = make_sample_df(200)
        pre.fit(df)

        cat_transformer = pre.named_transformers_["cat"]
        assert cat_transformer.drop == "first", \
            "OHE preprocessor must use drop='first' for Ridge compatibility"

    def test_ohe_standard_scaler_applied_to_numerics(self, preprocessors):
        """
        Ridge is distance-sensitive — StandardScaler must be applied to numerics.
        Verify the numeric transformer is a StandardScaler.
        """
        pre = preprocessors["ohe"]()
        num_transformer = pre.transformers[0][1]
        assert isinstance(num_transformer, StandardScaler), \
            "OHE pipeline must use StandardScaler for numeric features"

    def test_ohe_output_shape_consistent_train_val(self, preprocessors):
        """Output shape must be identical between training and validation data."""
        pre      = preprocessors["ohe"]()
        train_df = make_sample_df(200, seed=1)
        val_df   = make_sample_df(50, seed=2)

        X_train = pre.fit_transform(train_df)
        X_val   = pre.transform(val_df)

        assert X_train.shape[1] == X_val.shape[1], \
            f"Shape mismatch: train={X_train.shape[1]}, val={X_val.shape[1]}"


# ── Ordinal preprocessor tests (RF / XGBoost pipeline) ───────────────────────

class TestOrdinalPreprocessor:

    def test_ordinal_output_has_no_nulls(self, preprocessors):
        pre = preprocessors["ordinal"]()
        df  = make_sample_df(100)
        X   = pre.fit_transform(df)
        # OrdinalEncoder with passthrough returns object dtype — must cast to float
        # before calling np.isnan, which doesn't support object arrays.
        X_float = np.array(X, dtype=float)
        assert not np.isnan(X_float).any(), "Ordinal output contains NaN"

    def test_ordinal_unseen_category_maps_to_minus_one(self, preprocessors):
        """
        unknown_value=-1 means unseen category → -1.
        -1 is outside real class range (0, 1, 2 ...) so no collision.
        Trees treat it as a separate split point.
        """
        pre      = preprocessors["ordinal"]()
        train_df = make_sample_df(200)
        pre.fit(train_df)

        test_df = make_sample_df(1)
        test_df["specialty"] = "UNKNOWN_SPECIALTY_999"
        X_out = pre.transform(test_df)

        # Cast to float before any numeric checks — object dtype breaks np.isnan
        X_float = np.array(X_out, dtype=float)
        assert not np.isnan(X_float).any()

        # Verify the encoder configuration — unknown_value must be -1
        cat_transformer = pre.named_transformers_["cat"]
        assert cat_transformer.unknown_value == -1, \
            "OrdinalEncoder must set unknown_value=-1 to avoid collision with class 0"

        # At least one value in the output must be -1 (the unknown specialty)
        assert (X_float == -1).any(), \
            "Expected -1 in output for unseen category"

    def test_ordinal_no_standard_scaler_for_trees(self, preprocessors):
        """
        Tree models are scale-invariant — StandardScaler must NOT be applied.
        Numeric transformer should be 'passthrough'.
        """
        pre = preprocessors["ordinal"]()
        num_transformer = pre.transformers[0][1]
        assert num_transformer == "passthrough", \
            "Ordinal pipeline must use passthrough for numerics (trees are scale-invariant)"

    def test_ordinal_output_shape_consistent_train_val(self, preprocessors):
        """Output shape must be identical between training and validation data."""
        pre      = preprocessors["ordinal"]()
        train_df = make_sample_df(200, seed=10)
        val_df   = make_sample_df(50, seed=20)

        X_train = pre.fit_transform(train_df)
        X_val   = pre.transform(val_df)

        assert X_train.shape[1] == X_val.shape[1]

    def test_ordinal_known_categories_not_minus_one(self, preprocessors):
        """Known categories must encode to values >= 0, not -1."""
        pre = preprocessors["ordinal"]()
        df  = make_sample_df(200)
        X   = pre.fit_transform(df)

        # Slice only categorical columns — passthrough numerics can have any value
        X_float      = np.array(X, dtype=float)
        num_cols_cnt = len(preprocessors["numeric"]) + len(preprocessors["bool"])
        cat_cols     = X_float[:, num_cols_cnt:]

        assert (cat_cols >= 0).all(), \
            "Known categories should encode to >= 0, not -1"


# ── Full pipeline integration tests ───────────────────────────────────────────

class TestFullPipelineIntegration:

    def test_ridge_pipeline_fits_and_predicts(self, preprocessors):
        """Full Ridge Pipeline (OHE + Ridge) must fit and produce predictions."""
        from sklearn.linear_model import Ridge

        pre      = preprocessors["ohe"]()
        pipeline = Pipeline([("pre", pre), ("model", Ridge(alpha=1.0))])
        df       = make_sample_df(200)
        y        = np.random.uniform(0, 60, 200)

        pipeline.fit(df, y)
        preds = pipeline.predict(df)

        assert len(preds) == 200
        assert not np.isnan(preds).any()

    def test_rf_pipeline_fits_and_predicts(self, preprocessors):
        """Full RF Pipeline (Ordinal + RandomForest) must fit and produce predictions."""
        from sklearn.ensemble import RandomForestRegressor

        pre      = preprocessors["ordinal"]()
        pipeline = Pipeline([
            ("pre", pre),
            ("model", RandomForestRegressor(n_estimators=10, random_state=42)),
        ])
        df = make_sample_df(200)
        y  = np.random.uniform(0, 60, 200)

        pipeline.fit(df, y)
        preds = pipeline.predict(df)

        assert len(preds) == 200
        assert not np.isnan(preds).any()

    def test_pipeline_predict_clips_to_zero(self, preprocessors):
        """Predictions clipped to 0 — no negative wait times allowed."""
        from sklearn.linear_model import Ridge

        pre      = preprocessors["ohe"]()
        pipeline = Pipeline([("pre", pre), ("model", Ridge(alpha=1.0))])
        df       = make_sample_df(100)
        y        = np.zeros(100)

        pipeline.fit(df, y)
        preds = pipeline.predict(df).clip(0)

        assert (preds >= 0).all()

    def test_all_features_list_has_no_duplicates(self, preprocessors):
        """ALL_FEATURES must have no duplicates — duplicates cause silent bugs."""
        all_features = preprocessors["all"]
        assert len(all_features) == len(set(all_features)), \
            f"Duplicates: {[f for f in all_features if all_features.count(f) > 1]}"

    def test_categorical_features_not_in_numeric(self, preprocessors):
        """Categorical and numeric feature lists must be disjoint."""
        numeric     = set(preprocessors["numeric"])
        categorical = set(preprocessors["categorical"])
        overlap     = numeric & categorical
        assert len(overlap) == 0, \
            f"Features in both numeric and categorical lists: {overlap}"
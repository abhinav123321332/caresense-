"""Saved feature contract; estimator-specific imputation belongs to training."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.utils.validation import check_is_fitted

from .features import FEATURE_VERSION, build_features, feature_dictionary


class FeaturePipeline(TransformerMixin, BaseEstimator):
    """Validate and order causal features while preserving missing values.

    ``fit`` must receive only sampled training features. It records the exact
    feature contract and training row count, without learning any imputation or
    population statistic. XGBoost receives NaNs natively; baseline estimators
    fit their own imputation/scaling on the same training rows.
    """

    def fit(self, X: pd.DataFrame, y=None):
        self.feature_names_in_ = np.asarray(list(feature_dictionary()), dtype=object)
        self.n_features_in_ = len(self.feature_names_in_)
        self.feature_version_ = FEATURE_VERSION
        self.training_rows_seen_ = len(X)
        self.transform_features(X)
        return self

    def transform_features(self, X: pd.DataFrame) -> np.ndarray:
        check_is_fitted(self, "feature_names_in_")
        if not isinstance(X, pd.DataFrame):
            raise TypeError("Features must be a named pandas DataFrame")
        if X.columns.duplicated().any():
            raise ValueError("Duplicate engineered feature columns")
        required = set(self.feature_names_in_)
        if set(X.columns) != required:
            raise ValueError(f"Feature schema mismatch: missing={sorted(required - set(X.columns))}; extra={sorted(set(X.columns) - required)}")
        try:
            array = X.loc[:, self.feature_names_in_].to_numpy(dtype=np.float32)
        except (ValueError, TypeError) as exc:
            raise ValueError("Engineered features must be numeric") from exc
        if np.isinf(array).any():
            raise ValueError("Infinite engineered features are not accepted")
        return array

    def transform_history(self, patient_history: pd.DataFrame) -> np.ndarray:
        return self.transform_features(build_features(patient_history))

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        return self.transform_features(X)

    def get_feature_names_out(self, input_features=None):
        check_is_fitted(self, "feature_names_in_")
        return self.feature_names_in_.copy()

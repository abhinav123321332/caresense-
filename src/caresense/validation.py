"""Structural validation shared by dataset loading and inference."""
from __future__ import annotations

import numpy as np
import pandas as pd
from .schema import INPUT_COLUMNS, TARGET, COLUMNS


def validate_patient_history(frame: pd.DataFrame, require_label: bool = False) -> pd.DataFrame:
    """Return numeric data without imputing or removing unusual measurements.

    Missing measurements are accepted. Missing features, unknown columns,
    duplicate/nonincreasing hour coordinates, nonfinite values, nonnumeric
    fields and invalid binary labels are rejected. No resampling occurs.
    """
    if not isinstance(frame, pd.DataFrame):
        frame = pd.DataFrame(frame)
    if frame.empty:
        raise ValueError("Patient history must contain at least one row")
    if frame.columns.duplicated().any():
        raise ValueError("Duplicate column names")
    expected = COLUMNS if require_label else INPUT_COLUMNS
    missing = set(expected) - set(frame.columns)
    extra = set(frame.columns) - set(COLUMNS)
    if missing or extra:
        raise ValueError(f"Invalid schema: missing={sorted(missing)}, extra={sorted(extra)}")
    columns = COLUMNS if TARGET in frame else INPUT_COLUMNS
    try:
        numeric = frame.loc[:, columns].apply(pd.to_numeric, errors="raise").astype(float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Measurements must be numeric or null") from exc
    if np.isinf(numeric.to_numpy()).any():
        raise ValueError("Infinite measurements are not permitted")
    hours = numeric["ICULOS"].to_numpy()
    if not np.isfinite(hours).all() or (hours < 1).any() or (np.diff(hours) <= 0).any():
        raise ValueError("ICULOS must be finite, positive and strictly increasing")
    if not np.all(hours == np.round(hours)):
        raise ValueError("ICULOS must contain integer hourly coordinates")
    for name in ["Gender", "Unit1", "Unit2"]:
        if not numeric[name].dropna().isin([0, 1]).all():
            raise ValueError(f"{name} must contain 0, 1 or missing values")
    if TARGET in numeric and not numeric[TARGET].isin([0, 1]).all():
        raise ValueError("SepsisLabel must contain only 0 and 1, without missing labels")
    return numeric

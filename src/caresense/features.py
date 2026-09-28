"""Deterministic, patient-local causal features shared by training and inference.

Windows are open on the left and closed on the right: (t-window, t]. Gaps
are handled using ICULOS coordinates, never by treating row offsets as hours.
No fitted statistic, target or future observation enters this module.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .schema import AUDIT_BOUNDS, INPUT_COLUMNS, LABS, VITALS
from .validation import validate_patient_history

HISTORY_SIGNALS = VITALS + ["Lactate", "WBC"]
TEMPORAL_SIGNALS = ["HR", "O2Sat", "MAP", "Resp", "Lactate", "WBC"]
WINDOWS = (3, 6, 12, 24)
FEATURE_VERSION = "causal-hourly-v1"


def feature_dictionary() -> dict[str, dict]:
    """Ordered feature definitions; ordering is part of the artifact contract."""
    result = {}
    for name in INPUT_COLUMNS:
        result[name] = {"source": name, "operation": "current",
                        "definition": "Current observation; absent or outside documented mechanical bounds becomes NaN.",
                        "bounds": list(AUDIT_BOUNDS[name]) if name in AUDIT_BOUNDS else None}
    for name in VITALS + LABS:
        result[f"{name}_missing"] = {"source": name, "operation": "missing",
                                     "definition": "1 if current observation is missing after mechanical cleaning, otherwise 0."}
    for name in INPUT_COLUMNS:
        if name in AUDIT_BOUNDS:
            result[f"{name}_out_of_range"] = {"source": name, "operation": "out_of_range",
                                              "bounds": list(AUDIT_BOUNDS[name]),
                                              "definition": "1 for observed value outside inclusive mechanical bounds; missing observations give 0."}
    for name in HISTORY_SIGNALS:
        expiry = 6 if name in VITALS else 24
        result[f"{name}_last"] = {"source": name, "operation": "last_observed", "maximum_age_hours": expiry,
                                  "definition": "Most recent valid observation at or before t, retained through maximum age; otherwise NaN."}
        result[f"{name}_hours_since_last"] = {"source": name, "operation": "recency",
                                              "definition": "Actual hours since latest valid observation, even if expired for carry-forward; NaN before first valid measurement."}
    for name in ["Lactate", "WBC"]:
        result[f"{name}_previous"] = {"source": name, "operation": "previous_observed", "maximum_age_hours": 24,
                                      "definition": "Latest valid observation strictly before current hour; NaN if none within 24 hours. At a measurement hour this is the preceding measurement."}
    for name in TEMPORAL_SIGNALS:
        for window in WINDOWS:
            result[f"{name}_mean_{window}h"] = {"source": name, "operation": "mean", "window_hours": window,
                                                "definition": "Mean of actual valid measurements in (t-window,t]; at least one observation."}
        for operation in ["min", "max", "std", "count"]:
            result[f"{name}_{operation}_6h"] = {"source": name, "operation": operation, "window_hours": 6,
                                                "definition": ("Sample standard deviation of actual valid observations in (t-6,t]; at least two observations." if operation == "std" else
                                                               "Count of actual valid observations in (t-6,t]; zero means no observations." if operation == "count" else
                                                               f"{operation.title()} of actual valid observations in (t-6,t]; at least one observation.")}
        result[f"{name}_delta_6h"] = {"source": name, "operation": "delta", "lag_hours": 6,
                                      "definition": "Bounded carried value at t minus bounded carried value available at exact hour t-6; both required. Vital carry limit 6h, lab limit 24h. No observation after t-6 enters the historical endpoint."}
        result[f"{name}_trend_6h"] = {"source": name, "operation": "least_squares_slope", "window_hours": 6,
                                      "definition": "Least-squares slope per actual ICULOS hour using valid measurements in (t-6,t]; at least two observations at distinct hours."}
    return result


def save_feature_dictionary(path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"version": FEATURE_VERSION, "features": feature_dictionary()}, indent=2), encoding="utf-8")


def _last_at(hours: np.ndarray, values: np.ndarray, query: np.ndarray, max_age: int,
             strictly_before: bool = False) -> tuple[np.ndarray, np.ndarray]:
    present = np.isfinite(values)
    observed_hours, observed = hours[present], values[present]
    result = np.full(len(query), np.nan, dtype=np.float64)
    ages = result.copy()
    if len(observed):
        indices = np.searchsorted(observed_hours, query, side="left" if strictly_before else "right") - 1
        available = indices >= 0
        ages[available] = query[available] - observed_hours[indices[available]]
        retained = available & (ages <= max_age)
        result[retained] = observed[indices[retained]]
    return result, ages


def _prefix(values: np.ndarray) -> np.ndarray:
    return np.concatenate([np.zeros((1, values.shape[1])), np.cumsum(values, axis=0)], axis=0)


def build_features(history: pd.DataFrame) -> pd.DataFrame:
    """Generate float32 predictors for every supplied patient hour, in order.

    A label column is tolerated by shared structural validation but discarded
    before construction. It can never become a predictor. Input is not changed.
    """
    raw = validate_patient_history(history).loc[:, INPUT_COLUMNS]
    hours = raw["ICULOS"].to_numpy(dtype=np.float64)
    if not np.array_equal(hours, np.round(hours)):
        raise ValueError("ICULOS must contain exact integer hourly coordinates")
    clean = raw.to_numpy(dtype=np.float64, copy=True)
    data = {}
    invalid = {}
    for column, name in enumerate(INPUT_COLUMNS):
        values = clean[:, column]
        if name in AUDIT_BOUNDS:
            lower, upper = AUDIT_BOUNDS[name]
            invalid[name] = (values < lower) | (values > upper)
            values[invalid[name]] = np.nan
        data[name] = values
    for name in VITALS + LABS:
        data[f"{name}_missing"] = ~np.isfinite(data[name])
    for name in INPUT_COLUMNS:
        if name in invalid:
            data[f"{name}_out_of_range"] = invalid[name]
    for name in HISTORY_SIGNALS:
        data[f"{name}_last"], data[f"{name}_hours_since_last"] = _last_at(
            hours, data[name], hours, 6 if name in VITALS else 24)
    for name in ["Lactate", "WBC"]:
        data[f"{name}_previous"], _ = _last_at(hours, data[name], hours, 24, strictly_before=True)

    observed = np.column_stack([data[name] for name in TEMPORAL_SIGNALS])
    valid = np.isfinite(observed)
    safe = np.where(valid, observed, 0.0)
    counts = _prefix(valid.astype(np.float64))
    sums, squares = _prefix(safe), _prefix(safe ** 2)
    # Center coordinates on this patient's first hour to keep moment arithmetic
    # stable when histories start later in the ICU stay.
    time = (hours - hours[0])[:, None]
    time_sums = _prefix(np.where(valid, time, 0.0))
    time_squares = _prefix(np.where(valid, time ** 2, 0.0))
    products = _prefix(safe * time)
    end = np.arange(1, len(hours) + 1)
    window_stats = {}
    for window in WINDOWS:
        start = np.searchsorted(hours, hours - window, side="right")
        count = counts[end] - counts[start]
        total = sums[end] - sums[start]
        means = np.divide(total, count, out=np.full_like(total, np.nan), where=count > 0)
        window_stats[window] = (start, count, total)
        for column, name in enumerate(TEMPORAL_SIGNALS):
            data[f"{name}_mean_{window}h"] = means[:, column]
    start, count, total = window_stats[6]
    total_squared = squares[end] - squares[start]
    variance_numerator = total_squared - np.divide(total ** 2, count, out=np.zeros_like(total), where=count > 0)
    variance = np.divide(np.maximum(variance_numerator, 0), count - 1,
                         out=np.full_like(total, np.nan), where=count > 1)
    sx = time_sums[end] - time_sums[start]
    sxx = time_squares[end] - time_squares[start]
    sxy = products[end] - products[start]
    slope_denominator = count * sxx - sx ** 2
    slopes = np.divide(count * sxy - sx * total, slope_denominator,
                       out=np.full_like(total, np.nan), where=(count > 1) & (slope_denominator > 0))
    minimum = np.full_like(observed, np.nan)
    maximum = np.full_like(observed, np.nan)
    # A six-hour window has at most six rows because hours are strict integers.
    for offset in range(6):
        row = np.arange(len(hours)) - offset
        exists = row >= start
        safe_row = np.maximum(row, 0)
        values = np.where(exists[:, None], observed[safe_row], np.nan)
        minimum = np.fmin(minimum, values)
        maximum = np.fmax(maximum, values)
    for column, name in enumerate(TEMPORAL_SIGNALS):
        data[f"{name}_min_6h"] = minimum[:, column]
        data[f"{name}_max_6h"] = maximum[:, column]
        data[f"{name}_std_6h"] = np.sqrt(variance[:, column])
        data[f"{name}_count_6h"] = count[:, column]
        old, _ = _last_at(hours, data[name], hours - 6, 6 if name in VITALS else 24)
        data[f"{name}_delta_6h"] = data[f"{name}_last"] - old
        data[f"{name}_trend_6h"] = slopes[:, column]
    result = pd.DataFrame(data, index=history.index).loc[:, list(feature_dictionary())].astype(np.float32)
    if np.isinf(result.to_numpy()).any():
        raise ValueError("Feature conversion produced infinity; measurements are outside supported numeric magnitude")
    return result

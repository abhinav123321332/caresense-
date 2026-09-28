import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.exceptions import NotFittedError

from caresense.features import build_features, feature_dictionary
from caresense.preprocessing import FeaturePipeline
from caresense.schema import INPUT_COLUMNS


def history(hours):
    frame = pd.DataFrame(np.nan, index=range(len(hours)), columns=INPUT_COLUMNS)
    frame["ICULOS"] = hours
    return frame


@pytest.mark.parametrize("seed", range(4))
def test_random_missing_and_gapped_history_is_prefix_invariant(seed):
    rng = np.random.default_rng(seed)
    hours = np.cumsum(rng.integers(1, 5, size=36))
    frame = history(hours)
    for name, center in [("HR", 90), ("O2Sat", 94), ("MAP", 70), ("Resp", 20), ("Lactate", 3), ("WBC", 10)]:
        values = center + rng.normal(size=len(frame))
        values[rng.random(len(frame)) < .45] = np.nan
        frame[name] = values
    frame.index = np.arange(100, 136) * 3
    original = frame.copy(deep=True)
    full = build_features(frame)
    for end in [1, 2, 7, 15, 29, 36]:
        prefix = build_features(frame.iloc[:end])
        pd.testing.assert_frame_equal(prefix, full.iloc[:end])
    pd.testing.assert_frame_equal(frame, original)


def test_future_values_cannot_backfill_missing_history():
    frame = history([1, 2, 3, 7, 9])
    frame.loc[4, ["HR", "Lactate", "WBC"]] = [150, 9, 30]
    result = build_features(frame)
    for name in ["HR", "Lactate", "WBC"]:
        assert result.loc[:3, f"{name}_last"].isna().all()
        assert result.loc[:3, f"{name}_mean_24h"].isna().all()
        assert result.loc[:3, f"{name}_count_6h"].eq(0).all()


def test_target_permutation_and_input_order_do_not_change_features():
    frame = history([1, 2, 4, 7, 10])
    frame.HR = [80, np.nan, 100, 90, 110]
    expected = build_features(frame)
    frame["SepsisLabel"] = [0, 0, 1, 1, 1]
    first = build_features(frame)
    frame.SepsisLabel = [1, 0, 1, 0, 1]
    pd.testing.assert_frame_equal(first, build_features(frame.loc[:, list(frame.columns)[::-1]]))
    pd.testing.assert_frame_equal(first, expected)
    assert "SepsisLabel" not in first


def test_actual_elapsed_hours_control_rolling_windows_and_trends():
    frame = history([1, 4, 7, 8, 15])
    frame.HR = [72, 78, 84, 86, 100]  # Exactly 70 + 2 * hour.
    result = build_features(frame)
    assert result.HR_count_6h.tolist() == [1, 2, 2, 3, 1]
    assert result.loc[2, "HR_mean_6h"] == 81  # Hour 1 is excluded at hour 7.
    assert result.loc[3, "HR_min_6h"] == 78
    assert result.loc[3, "HR_max_6h"] == 86
    assert result.loc[3, "HR_trend_6h"] == pytest.approx(2)
    assert result.loc[3, "HR_std_6h"] == pytest.approx(np.std([78, 84, 86], ddof=1))
    assert np.isnan(result.loc[4, "HR_trend_6h"])
    assert result.loc[3, "HR_delta_6h"] == 14  # At hour 2 only hour 1 was available.
    assert result.loc[4, "HR_delta_6h"] == 14  # Exact hour 9 uses last observed hour 8.


def test_labs_use_24h_carry_actual_6h_endpoint_and_previous_measurement():
    frame = history([1, 5, 7, 10, 29, 30])
    frame.Lactate = [2, 5, np.nan, np.nan, np.nan, 8]
    result = build_features(frame)
    assert np.isnan(result.loc[1, "Lactate_delta_6h"])
    assert result.loc[2, "Lactate_delta_6h"] == 3
    assert result.loc[3, "Lactate_delta_6h"] == 3
    assert result.loc[4, "Lactate_last"] == 5  # Inclusive 24h maximum age.
    assert result.loc[4, "Lactate_hours_since_last"] == 24
    assert result.loc[5, "Lactate_delta_6h"] == 3
    assert result.loc[1, "Lactate_previous"] == 2
    assert result.loc[2, "Lactate_previous"] == 5
    assert np.isnan(result.loc[5, "Lactate_previous"])


def test_carry_expiry_retains_recency_but_not_measurement():
    frame = history([1, 7, 8, 25, 26])
    frame.loc[0, ["HR", "Lactate"]] = [80, 2]
    result = build_features(frame)
    assert result.loc[1, "HR_last"] == 80
    assert np.isnan(result.loc[2, "HR_last"])
    assert result.loc[2, "HR_hours_since_last"] == 7
    assert result.loc[3, "Lactate_last"] == 2
    assert np.isnan(result.loc[4, "Lactate_last"])
    assert result.loc[4, "Lactate_hours_since_last"] == 25


@pytest.mark.parametrize("hours", [[1], [10], [1, 3, 5]])
def test_short_and_all_missing_history_preserves_unknowns(hours):
    result = build_features(history(hours))
    assert result.Lactate_missing.eq(1).all()
    assert result.Lactate_last.isna().all()
    assert result.Lactate_delta_6h.isna().all()
    assert result.HR_std_6h.isna().all()
    assert result.HR_trend_6h.isna().all()
    assert result.HR_count_6h.eq(0).all()
    assert not np.isinf(result.to_numpy()).any()


def test_unusual_readings_are_flagged_not_clipped_and_bounds_are_inclusive():
    frame = history([1, 2, 3, 4])
    frame.HR = [0, 350, 351, np.nan]
    frame.O2Sat = [-1, 100, 101, np.nan]
    frame.Lactate = [0, 50, 51, np.nan]
    frame.HospAdmTime = [-100, -100, -100, -100]
    result = build_features(frame)
    assert result.HR_out_of_range.tolist() == [0, 0, 1, 0]
    assert result.O2Sat_out_of_range.tolist() == [1, 0, 1, 0]
    assert result.Lactate_out_of_range.tolist() == [0, 0, 1, 0]
    assert result.loc[0, "HR"] == 0
    assert result.loc[1, "HR"] == 350
    assert np.isnan(result.loc[2, "HR"])
    assert result.loc[2, "HR_last"] == 350
    assert result.HospAdmTime.eq(-100).all()
    assert frame.loc[2, "HR"] == 351


def test_feature_pipeline_requires_fit_and_preserves_order_and_missingness(tmp_path):
    training = history([1, 2, 3])
    training.HR = [80, 90, 100]
    train_features = build_features(training)
    pipeline = FeaturePipeline()
    with pytest.raises(NotFittedError):
        pipeline.transform(train_features)
    pipeline.fit(train_features)
    expected = train_features.to_numpy(dtype=np.float32)
    np.testing.assert_equal(pipeline.transform(train_features.iloc[:, ::-1]), expected)
    np.testing.assert_equal(pipeline.get_feature_names_out(), list(feature_dictionary()))
    assert pipeline.training_rows_seen_ == 3
    evaluation = history([1])
    evaluation.HR = 300
    assert pipeline.transform_history(evaluation)[0, 0] == 300
    assert pipeline.training_rows_seen_ == 3
    assert np.isnan(pipeline.transform_history(evaluation)[0, list(feature_dictionary()).index("Lactate")])
    path = tmp_path / "pipeline.joblib"
    joblib.dump(pipeline, path)
    restored = joblib.load(path)
    np.testing.assert_equal(restored.transform_history(training), expected)


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "infinite", "text"])
def test_feature_pipeline_rejects_broken_contract(mutation):
    original = build_features(history([1]))
    pipeline = FeaturePipeline().fit(original)
    broken = original.copy()
    if mutation == "missing":
        broken = broken.drop(columns="HR")
    elif mutation == "extra":
        broken["SepsisLabel"] = 1
    elif mutation == "duplicate":
        broken = pd.concat([broken, broken[["HR"]]], axis=1)
    elif mutation == "infinite":
        broken.loc[0, "HR"] = np.inf
    else:
        broken["HR"] = "invalid"
    with pytest.raises(ValueError):
        pipeline.transform(broken)

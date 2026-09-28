# Leakage audit

Status: **passed**

Patient separation, duplicate-record separation, causal feature prefixes, target permutation, onset exclusion, and held-out population completeness were checked programmatically.

```json
{
  "status": "passed",
  "checks": {
    "one_partition_per_patient": true,
    "raw_sha256_groups_crossing_partitions": 0,
    "record_sha256_groups_crossing_partitions": 0,
    "target_or_outcome_features_absent": true,
    "prepared_populations": {
      "train": {
        "hours": 160000,
        "positive_hours": 1578,
        "patients": 27449
      },
      "validation_selection": {
        "hours": 78059,
        "positive_hours": 763,
        "patients": 1999
      },
      "validation_calibration": {
        "hours": 77137,
        "positive_hours": 726,
        "patients": 1991
      },
      "validation_threshold": {
        "hours": 77533,
        "positive_hours": 780,
        "patients": 2000
      },
      "test": {
        "hours": 232838,
        "positive_hours": 2235,
        "patients": 5985
      }
    },
    "real_training_patient_prefix_checks": 80,
    "real_patient_target_permutation_checks": 20,
    "preprocessing_design": "Feature engineering is patient-local and deterministic. Baseline imputation/scaling fits only sampled training hours; XGBoost uses missing values natively.",
    "validation_roles": "Disjoint patient partitions for selection, calibration and threshold choice; all are distinct from test.",
    "test_contamination_design": "The fixed run config precedes fitting. train.py writes frozen_decisions.json before reading test features or predicting test outcomes. Test labels are used here only to verify protocol integrity, not select model settings.",
    "saved_preprocessing_training_row_count_verified": true,
    "frozen_configuration_hash": "676972cccc084bab178a4c9e2e14d2b9bdb86334a97069ee4ee36e3c4683c99a"
  },
  "failures": [],
  "limits": [
    "Patient IDs identify provided records; cross-admission identity cannot be verified from the released schema.",
    "No absolute dates are supplied for a chronological split; this is random internal patient validation.",
    "Measurement patterns and availability can encode hospital workflow and treatment effects; these are not eliminated by patient separation."
  ]
}
```
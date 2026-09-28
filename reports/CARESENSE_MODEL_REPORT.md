# CARESENSE MODEL REPORT

Generated UTC: 2026-09-25T16:56:27.916385+00:00

CareSense is an AI-assisted early-warning research prototype. Probabilities refer to the retrospective target described below; this is not a diagnostic device or clinically validated operating system.

| Stage | Recorded execution status |
| --- | --- |
| Dataset audit | verified |
| Prepared data | verified |
| Model experiment | completed |
| Leakage audit | passed |
| Measured test results | Available |

Measured model results below are read from the completed model_metrics.json artifact; source code and synthetic test fits are not counted as official model results. Recorded experiment completion (UTC): 2026-09-23T02:01:36.321280+00:00.

**The preserved prototype tiers are unsuitable for sensitive early warning in this experiment.** The XGBoost Watch boundary detects fewer than 1% of positive test hours; higher boundaries are at least as restrictive. The actual counts below must accompany any dashboard use of these tiers. They remain unchanged and are not clinically validated.

| XGBoost prototype comparator | True-positive hours | Positive test hours | All alert hours | Sensitivity |
| --- | --- | --- | --- | --- |
| >= 0.30 | 5 | 2,235 | 6 | 0.0022 |
| >= 0.50 | 0 | 2,235 | 0 | 0.0000 |
| > 0.75 | 0 | 2,235 | 0 | 0.0000 |

## 1. Dataset description

The [official PhysioNet 2019 Sepsis Challenge training release](https://physionet.org/content/challenge-2019/1.0.0/) contains hourly ICU observations from two released sources. Only its training directory is used. The required census is A = 20,336, B = 20,000, total = 40,336; these requirements are distinct from the verified measurements below. Each patient file supplies 40 predictors and SepsisLabel. No real nursing notes, original event timestamps or confirmed oxygen-treatment indicator are supplied.

## 2. Dataset audit

Recorded audit status: **verified**. The recorded audit checked raw files for schema, time order, numeric domains, row quality, duplicate records and label dynamics. Available findings are in [dataset_audit.json](dataset_audit.json), with patient-level provenance in patient_metadata.csv (original experiment workspace) and raw_file_manifest.csv (original experiment workspace).

| Audit measure | Observed value |
| --- | --- |
| Hourly rows | 1,552,210 |
| Structurally invalid patients | 0 |
| Patients with unusual formatting | 0 |
| Identical raw-record groups | 0 |
| Identical numeric-record groups | 0 |
| Duplicate full rows | 0 |
| Repeated measurements ignoring time/label | 93,849 |
| Missing hourly coordinates | 0 |
| Patients with hourly gaps | 0 |
| Patients starting after ICU hour 1 | 8,793 |

Repeated measurement values at distinct hours are not necessarily duplicate records and are not removed merely for repeating.

| Column | Missing % | Minimum | Maximum | Mean | Median | Out of bounds |
| --- | --- | --- | --- | --- | --- | --- |
| HR | 9.8826 | 20.0000 | 280.0000 | 84.5814 | 83.5000 | 0 |
| O2Sat | 13.0611 | 20.0000 | 100.0000 | 97.1940 | 98.0000 | 0 |
| Temp | 66.1627 | 20.9000 | 50.0000 | 36.9772 | 37.0000 | 2 |
| SBP | 14.5770 | 20.0000 | 300.0000 | 123.7505 | 121.0000 | 0 |
| MAP | 12.4513 | 20.0000 | 300.0000 | 82.4001 | 80.0000 | 0 |
| DBP | 31.3459 | 20.0000 | 300.0000 | 63.8306 | 62.0000 | 53 |
| Resp | 15.3546 | 1.0000 | 100.0000 | 18.7265 | 18.0000 | 0 |
| EtCO2 | 96.2868 | 10.0000 | 100.0000 | 32.9577 | 33.0000 | 0 |
| BaseExcess | 94.5790 | -32.0000 | 100.0000 | -0.6899 | 0.0000 | Not bounded |
| HCO3 | 95.8106 | 0.0000 | 55.0000 | 24.0755 | 24.0000 | Not bounded |
| FiO2 | 91.6658 | -50.0000 | 4,000.0000 | 0.5548 | 0.5000 | 32 |
| pH | 93.0697 | 6.6200 | 7.9300 | 7.3789 | 7.3800 | 0 |
| PaCO2 | 94.4401 | 10.0000 | 100.0000 | 41.0219 | 40.0000 | Not bounded |
| SaO2 | 96.5494 | 23.0000 | 100.0000 | 92.6542 | 97.0000 | 0 |
| AST | 98.3776 | 3.0000 | 9,961.0000 | 260.2234 | 41.0000 | Not bounded |
| BUN | 93.1344 | 1.0000 | 268.0000 | 23.9155 | 17.0000 | Not bounded |
| Alkalinephos | 98.3932 | 7.0000 | 3,833.0000 | 102.4837 | 74.0000 | Not bounded |
| Calcium | 94.1161 | 1.0000 | 27.9000 | 7.5575 | 8.3000 | Not bounded |
| Chloride | 95.4603 | 26.0000 | 145.0000 | 105.8279 | 106.0000 | Not bounded |
| Creatinine | 93.9044 | 0.1000 | 46.6000 | 1.5107 | 0.9400 | Not bounded |
| Bilirubin_direct | 99.8074 | 0.0100 | 37.5000 | 1.8362 | 0.4450 | Not bounded |
| Glucose | 82.8943 | 10.0000 | 988.0000 | 136.9323 | 127.0000 | Not bounded |
| Lactate | 97.3299 | 0.2000 | 31.0000 | 2.6467 | 1.8000 | 0 |
| Magnesium | 93.6896 | 0.2000 | 9.8000 | 2.0515 | 2.0000 | Not bounded |
| Phosphate | 95.9863 | 0.2000 | 18.8000 | 3.5442 | 3.3000 | Not bounded |
| Potassium | 90.6891 | 1.0000 | 27.5000 | 4.1355 | 4.1000 | Not bounded |
| Bilirubin_total | 98.5092 | 0.1000 | 49.6000 | 2.1141 | 0.9000 | Not bounded |
| TroponinI | 99.0477 | 0.0100 | 440.0000 | 8.2901 | 0.3000 | Not bounded |
| Hct | 91.1460 | 5.5000 | 71.7000 | 30.7941 | 30.3000 | 0 |
| Hgb | 92.6176 | 2.2000 | 32.0000 | 10.4308 | 10.3000 | 0 |
| PTT | 97.0559 | 12.5000 | 250.0000 | 41.2312 | 32.4000 | Not bounded |
| WBC | 93.5932 | 0.1000 | 440.0000 | 11.4464 | 10.3000 | 0 |
| Fibrinogen | 99.3402 | 34.0000 | 1,760.0000 | 287.3857 | 250.0000 | Not bounded |
| Platelets | 94.0595 | 1.0000 | 2,322.0000 | 196.0139 | 181.0000 | Not bounded |
| Age | 0.0000 | 14.0000 | 100.0000 | 62.0095 | 64.0000 | 0 |
| Gender | 0.0000 | 0.0000 | 1.0000 | 0.5593 | 1.0000 | 0 |
| Unit1 | 39.4251 | 0.0000 | 1.0000 | 0.4966 | 0.0000 | 0 |
| Unit2 | 39.4251 | 0.0000 | 1.0000 | 0.5034 | 1.0000 | 0 |
| HospAdmTime | 0.0005 | -5,366.8600 | 23.9900 | -56.1251 | -6.0300 | Not bounded |
| ICULOS | 0.0000 | 1.0000 | 336.0000 | 26.9950 | 21.0000 | 0 |
| SepsisLabel | 0.0000 | 0.0000 | 1.0000 | 0.0180 | 0.0000 | Not bounded |

Mechanical bounds identify suspect observations; they are not diagnostic limits. All raw columns are parsed as float64, with binary and integer-hour domains validated separately.

| Distribution | N | Median | 25th percentile | 75th percentile | Minimum | Maximum |
| --- | --- | --- | --- | --- | --- | --- |
| Stay length in observed rows | 40,336 | 38.0000 | 24.0000 | 47.0000 | 8.0000 | 336.0000 |
| Age | 40,336 | 63.1100 | 51.0000 | 74.0000 | 14.0000 | 100.0000 |

## 3. Number of patients

| Source | Verified patients | Observed rows | Eventual-positive patients |
| --- | --- | --- | --- |
| training_setA | 20,336 | 790,215 | 1,790 |
| training_setB | 20,000 | 761,995 | 1,142 |

Total audited patient files: **40,336**. Census verified: **True**. Primary-ineligible records are retained in the assignment manifest and excluded from primary model fitting/evaluation.

## 4. Class distribution

| Population | Positive | Negative | Positive percentage |
| --- | --- | --- | --- |
| All released observed hours | 27,916 | 1,524,294 | 1.7985 |
| Released patient records | 2,932 | 37,404 | 7.2689 |

| Prepared partition | Eligible patients | Fitting/evaluation hours | Positive hours | Negative hours |
| --- | --- | --- | --- | --- |
| train | 27,935 | 160,000 | 1,578 | 158,422 |
| validation_selection | 1,999 | 78,059 | 763 | 77,296 |
| validation_calibration | 1,991 | 77,137 | 726 | 76,411 |
| validation_threshold | 2,000 | 77,533 | 780 | 76,753 |
| test | 5,985 | 232,838 | 2,235 | 230,603 |

All eligible validation and test hours retain their observed prevalence. Training uses a uniform sample without replacement capped at 160,000 eligible hours; the same rows are supplied to all models. The sampling manifest is training_sample.csv (original experiment workspace).

```json
{
  "method": "Uniform global eligible-hour index sampling without replacement; equivalent uniform-subset distribution to reservoir sampling.",
  "candidate_hours": 1073722,
  "cap": 160000,
  "sampled_hours": 160000,
  "seed": 2019,
  "sample_order": "Patient ID ascending, then original ICULOS ascending",
  "all_history_used_before_sampling": true,
  "patient_coverage": 27449,
  "positive_hours": 1578,
  "sample_manifest_sha256": "adaa2ea16ada42a68af2fe3fa00db153f8795adc31565c0c7acd9c458c3c8edb"
}
```

## 5. Data preprocessing

Shared validation requires the documented input columns and strictly increasing positive integer ICULOS coordinates. Current measurements outside documented mechanical bounds become missing in the model features, with explicit out-of-range flags; raw files are unchanged. Missing values are not interpreted as normal. Current missingness and historical availability remain separate. Vital carry-forward expires after six hours and Lactate/WBC carry-forward after 24 hours. No backward fill or future interpolation occurs. Logistic Regression fits continuous median imputation and scaling, plus binary most-frequent imputation, on the common training sample. Random Forest fits median imputation there. XGBoost receives missing values natively and is not scaled. Persisted contracts and estimators are reloaded for inference.

## 6. Patient-level split

Complete patient records are assigned with seed **2,019** to approximately 70% train, 15% validation and 15% test, stratifying by source and eventual label. Matching raw or numeric hashes form indivisible connected groups. The validation share is split into distinct selection, calibration and threshold patients. Rounded counts and duplicate groups may prevent exact proportions.

| Partition | All assigned patients | Primary eligible | Primary ineligible | Eventual positive | Left censored |
| --- | --- | --- | --- | --- | --- |
| train | 28,235 | 27,935 | 300 | 2,053 | 300 |
| validation_selection | 2,018 | 1,999 | 19 | 147 | 19 |
| validation_calibration | 2,017 | 1,991 | 26 | 147 | 26 |
| validation_threshold | 2,016 | 2,000 | 16 | 146 | 16 |
| test | 6,050 | 5,985 | 65 | 439 | 65 |

Manifest: patient_split.csv (original experiment workspace). SHA-256: `3f1e41c901fc6371b749af1d11b3152d6aa695b52352eee82c6dadf42cd48a09`. Per-source/eventual-label counts are in split_summary.json (original experiment workspace). Patient assignment occurs before learned preprocessing.

## 7. Temporal feature engineering

The recorded preparation generated **176** predictors. Windows use actual ICULOS hours and the interval (t-window, t], not row offsets. HR, O2Sat, MAP, Resp, Lactate and WBC have 3/6/12/24-hour means; six-hour minimum, maximum, sample standard deviation, observed count, change and least-squares slope. Six-hour deltas require a causal value available at t-6, with explicit carry expiry. Unavailable histories remain missing. Lactate and WBC include current values, missingness, prior measured values, bounded last values, recency, change and trend. Complete definitions and bounds are in [feature_dictionary.json](../artifacts/feature_dictionary.json). Each sampled training hour is constructed from the full patient history before row selection.

## 8. Target definition

The supplied SepsisLabel becomes positive six hours before the Challenge's retrospective onset; it is not shifted a second time. For an observed contiguous 0->1 transition, label-implied onset is first-positive ICULOS + 6. Only hours strictly before that onset enter the primary experiment. Nonseptic records retain their released observation period. First-row-positive stays, reversing labels and uncertain transitions are excluded from the primary cohort. Onset is inferred from labels rather than independently observed clinical adjudication, and may be beyond the final released measurement. These assumptions narrow the population.

```json
{
  "left_censored_patients": 426,
  "nonmonotonic_label_patients": 0,
  "observed_contiguous_transition_patients": 2506,
  "inferred_onset_within_observation_patients": 2491,
  "primary_eligible_patients": 39910,
  "primary_rows": 1539289,
  "primary_positive_rows": 14995,
  "positive_hours_per_sepsis_patient": {
    "n": 2932,
    "min": 1.0,
    "max": 10.0,
    "mean": 9.521145975443384,
    "median": 10.0,
    "p05": 8.0,
    "p25": 9.0,
    "p75": 10.0,
    "p95": 10.0
  }
}
```

## 9. Logistic Regression results

Held-out test cohort: **5,985 eligible patients**, **232,838 hours**, **2,235 positive hours**.

| Output | AUROC | Average precision | Brier score |
| --- | --- | --- | --- |
| raw | 0.7932 | 0.0597 | 0.1763 |
| calibrated | 0.7932 | 0.0597 | 0.0093 |

The principal discrimination/calibration results above use all eligible model hours. The inference interface withholds a prediction when the entire clinical history is empty after cleaning; demographics alone do not make a history available. Missing laboratories alone do not prevent prediction.

| Inference coverage measure | Measured value |
| --- | --- |
| Eligible model hours | 232,838 |
| Hours with clinical history | 227,846 |
| Withheld empty-history hours | 4,992 |
| Coverage fraction | 0.9786 |

Calibrated results restricted to inference-available hours:

| Hours | Positive hours | AUROC | Average precision | Brier score |
| --- | --- | --- | --- | --- |
| 227,846 | 2,235 | 0.7894 | 0.0597 | 0.0095 |

Research threshold chosen for maximum F1 on validation/threshold: **p >= 0.055975**. 

Test confusion counts:

```json
{
  "TN": 228998,
  "FP": 1605,
  "FN": 2027,
  "TP": 208
}
```

Recorded training warnings: none recorded.

## 10. Random Forest results

Held-out test cohort: **5,985 eligible patients**, **232,838 hours**, **2,235 positive hours**.

| Output | AUROC | Average precision | Brier score |
| --- | --- | --- | --- |
| raw | 0.7908 | 0.0507 | 0.0656 |
| calibrated | 0.7908 | 0.0507 | 0.0093 |

The principal discrimination/calibration results above use all eligible model hours. The inference interface withholds a prediction when the entire clinical history is empty after cleaning; demographics alone do not make a history available. Missing laboratories alone do not prevent prediction.

| Inference coverage measure | Measured value |
| --- | --- |
| Eligible model hours | 232,838 |
| Hours with clinical history | 227,846 |
| Withheld empty-history hours | 4,992 |
| Coverage fraction | 0.9786 |

Calibrated results restricted to inference-available hours:

| Hours | Positive hours | AUROC | Average precision | Brier score |
| --- | --- | --- | --- | --- |
| 227,846 | 2,235 | 0.7861 | 0.0507 | 0.0095 |

Research threshold chosen for maximum F1 on validation/threshold: **p >= 0.077986**. 

Test confusion counts:

```json
{
  "TN": 228816,
  "FP": 1787,
  "FN": 2047,
  "TP": 188
}
```

Recorded training warnings: none recorded.

## 11. XGBoost results

Held-out test cohort: **5,985 eligible patients**, **232,838 hours**, **2,235 positive hours**.

| Output | AUROC | Average precision | Brier score |
| --- | --- | --- | --- |
| raw | 0.8364 | 0.0881 | 0.0091 |
| calibrated | 0.8364 | 0.0881 | 0.0091 |

The principal discrimination/calibration results above use all eligible model hours. The inference interface withholds a prediction when the entire clinical history is empty after cleaning; demographics alone do not make a history available. Missing laboratories alone do not prevent prediction.

| Inference coverage measure | Measured value |
| --- | --- |
| Eligible model hours | 232,838 |
| Hours with clinical history | 227,846 |
| Withheld empty-history hours | 4,992 |
| Coverage fraction | 0.9786 |

Calibrated results restricted to inference-available hours:

| Hours | Positive hours | AUROC | Average precision | Brier score |
| --- | --- | --- | --- | --- |
| 227,846 | 2,235 | 0.8328 | 0.0881 | 0.0093 |

Research threshold chosen for maximum F1 on validation/threshold: **p >= 0.063594**. 

Test confusion counts:

```json
{
  "TN": 227016,
  "FP": 3587,
  "FN": 1725,
  "TP": 510
}
```

Recorded training warnings: none recorded.

The primary estimator is XGBoost. Candidate choice uses selection-subset average precision, with the first listed configuration resolving ties; this is independent of test outcomes.

| Candidate | Depth | Positive weight | Selection average precision | Selected |
| --- | --- | --- | --- | --- |
| 0 | 3 | 1.0000 | 0.0928 | True |
| 1 | 4 | 1.0000 | 0.0872 | False |
| 2 | 3 | 10.0197 | 0.0769 | False |

| Measured test difference | Difference in AUROC | Difference in average precision |
| --- | --- | --- |
| XGBoost minus Logistic Regression | 0.0432 | 0.0283 |
| XGBoost minus Random Forest | 0.0456 | 0.0374 |

These differences have no patient-bootstrap confidence intervals and do not establish superiority or clinical benefit. No model is declared best from accuracy.

## 12. AUROC

| Model | Raw test | Calibrated test |
| --- | --- | --- |
| Logistic Regression | 0.7932 | 0.7932 |
| Random Forest | 0.7908 | 0.7908 |
| XGBoost | 0.8364 | 0.8364 |

AUROC compares rank discrimination. The population contains correlated hourly observations; this is not patient-level discrimination.

## 13. PR-AUC

| Model | Raw test | Calibrated test |
| --- | --- | --- |
| Logistic Regression | 0.0597 | 0.0597 |
| Random Forest | 0.0507 | 0.0507 |
| XGBoost | 0.0881 | 0.0881 |

PR-AUC uses **average precision**, not trapezoidal PR area. Test prevalence is shown with every model's context in [model_metrics.json](model_metrics.json); it is the reference for interpreting average precision.

## 14. Precision

| Model | Operating point | Probability comparator | Test precision |
| --- | --- | --- | --- |
| Logistic Regression | Prototype | >= 0.300000 | 0.0833 |
| Logistic Regression | Prototype | >= 0.500000 | 0.0000 |
| Logistic Regression | Prototype | > 0.750000 | 0.0000 |
| Logistic Regression | Validation-selected max F1 | >= 0.055975 | 0.1147 |
| Random Forest | Prototype | >= 0.300000 | 0.6667 |
| Random Forest | Prototype | >= 0.500000 | 0.0000 |
| Random Forest | Prototype | > 0.750000 | 0.0000 |
| Random Forest | Validation-selected max F1 | >= 0.077986 | 0.0952 |
| XGBoost | Prototype | >= 0.300000 | 0.8333 |
| XGBoost | Prototype | >= 0.500000 | 0.0000 |
| XGBoost | Prototype | > 0.750000 | 0.0000 |
| XGBoost | Validation-selected max F1 | >= 0.063594 | 0.1245 |

Prototype tiers remain Lower p<0.30; Watch 0.30 <= p<0.50; Elevated 0.50 <= p <= 0.75; Critical p>0.75. Exactly 0.75 is Elevated. These are prototype settings, not clinically optimal thresholds. Precision with no predicted positives is encoded as zero by the evaluation implementation; accompanying confusion counts identify that undefined-denominator situation.

## 15. Recall

| Model | Operating point | Probability comparator | Test recall |
| --- | --- | --- | --- |
| Logistic Regression | Prototype | >= 0.300000 | 0.0004 |
| Logistic Regression | Prototype | >= 0.500000 | 0.0000 |
| Logistic Regression | Prototype | > 0.750000 | 0.0000 |
| Logistic Regression | Validation-selected max F1 | >= 0.055975 | 0.0931 |
| Random Forest | Prototype | >= 0.300000 | 0.0009 |
| Random Forest | Prototype | >= 0.500000 | 0.0000 |
| Random Forest | Prototype | > 0.750000 | 0.0000 |
| Random Forest | Validation-selected max F1 | >= 0.077986 | 0.0841 |
| XGBoost | Prototype | >= 0.300000 | 0.0022 |
| XGBoost | Prototype | >= 0.500000 | 0.0000 |
| XGBoost | Prototype | > 0.750000 | 0.0000 |
| XGBoost | Validation-selected max F1 | >= 0.063594 | 0.2282 |

| Model | Alternative objective | Requested target | Frozen threshold | Validation precision | Validation recall | Test precision | Test recall |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Logistic Regression | recall_at_target_precision | 0.2000 | 0.1482 | 0.2000 | 0.0128 | 0.2327 | 0.0210 |
| Logistic Regression | precision_at_target_recall | 0.8000 | 0.0081 | 0.0242 | 0.8051 | 0.0219 | 0.7705 |
| Random Forest | recall_at_target_precision | 0.2000 | 0.1329 | 0.2143 | 0.0192 | 0.1306 | 0.0197 |
| Random Forest | precision_at_target_recall | 0.8000 | 0.0065 | 0.0189 | 0.8013 | 0.0189 | 0.8268 |
| XGBoost | recall_at_target_precision | 0.2000 | 0.1250 | 0.2377 | 0.0372 | 0.2253 | 0.0541 |
| XGBoost | precision_at_target_recall | 0.8000 | 0.0068 | 0.0254 | 0.8000 | 0.0248 | 0.8103 |

Alternative thresholds are selected only on validation/threshold. A validation target need not be achieved on test. Unattainable targets remain explicit.

## 16. F1

| Model | Operating point | Probability comparator | Test F1 |
| --- | --- | --- | --- |
| Logistic Regression | Prototype | >= 0.300000 | 0.0009 |
| Logistic Regression | Prototype | >= 0.500000 | 0.0000 |
| Logistic Regression | Prototype | > 0.750000 | 0.0000 |
| Logistic Regression | Validation-selected max F1 | >= 0.055975 | 0.1028 |
| Random Forest | Prototype | >= 0.300000 | 0.0018 |
| Random Forest | Prototype | >= 0.500000 | 0.0000 |
| Random Forest | Prototype | > 0.750000 | 0.0000 |
| Random Forest | Validation-selected max F1 | >= 0.077986 | 0.0893 |
| XGBoost | Prototype | >= 0.300000 | 0.0045 |
| XGBoost | Prototype | >= 0.500000 | 0.0000 |
| XGBoost | Prototype | > 0.750000 | 0.0000 |
| XGBoost | Validation-selected max F1 | >= 0.063594 | 0.1611 |

The research maximum-F1 threshold is chosen on validation/threshold and frozen before test access; test F1 is not optimized.

## 17. Sensitivity

| Model | Operating point | Probability comparator | Test sensitivity |
| --- | --- | --- | --- |
| Logistic Regression | Prototype | >= 0.300000 | 0.0004 |
| Logistic Regression | Prototype | >= 0.500000 | 0.0000 |
| Logistic Regression | Prototype | > 0.750000 | 0.0000 |
| Logistic Regression | Validation-selected max F1 | >= 0.055975 | 0.0931 |
| Random Forest | Prototype | >= 0.300000 | 0.0009 |
| Random Forest | Prototype | >= 0.500000 | 0.0000 |
| Random Forest | Prototype | > 0.750000 | 0.0000 |
| Random Forest | Validation-selected max F1 | >= 0.077986 | 0.0841 |
| XGBoost | Prototype | >= 0.300000 | 0.0022 |
| XGBoost | Prototype | >= 0.500000 | 0.0000 |
| XGBoost | Prototype | > 0.750000 | 0.0000 |
| XGBoost | Validation-selected max F1 | >= 0.063594 | 0.2282 |

Sensitivity is the same positive-class quantity as recall, TP/(TP+FN), at each stated threshold.

| XGBoost prototype comparator | True-positive hours | Positive test hours | All alert hours | Sensitivity |
| --- | --- | --- | --- | --- |
| >= 0.30 | 5 | 2,235 | 6 | 0.0022 |
| >= 0.50 | 0 | 2,235 | 0 | 0.0000 |
| > 0.75 | 0 | 2,235 | 0 | 0.0000 |

A high precision based on very few alerts does not offset the missed positive hours. Zero alert hours means that no positive hour was detected at that boundary.

## 18. Specificity

| Model | Operating point | Probability comparator | Test specificity |
| --- | --- | --- | --- |
| Logistic Regression | Prototype | >= 0.300000 | 1.0000 |
| Logistic Regression | Prototype | >= 0.500000 | 1.0000 |
| Logistic Regression | Prototype | > 0.750000 | 1.0000 |
| Logistic Regression | Validation-selected max F1 | >= 0.055975 | 0.9930 |
| Random Forest | Prototype | >= 0.300000 | 1.0000 |
| Random Forest | Prototype | >= 0.500000 | 1.0000 |
| Random Forest | Prototype | > 0.750000 | 1.0000 |
| Random Forest | Validation-selected max F1 | >= 0.077986 | 0.9923 |
| XGBoost | Prototype | >= 0.300000 | 1.0000 |
| XGBoost | Prototype | >= 0.500000 | 1.0000 |
| XGBoost | Prototype | > 0.750000 | 1.0000 |
| XGBoost | Validation-selected max F1 | >= 0.063594 | 0.9844 |

Specificity is TN/(TN+FP). Full TN/FP/FN/TP counts for every operating point are retained in [model_metrics.json](model_metrics.json).

## 19. Calibration if available

Completed model-calibration results are recorded below. Each estimator is frozen and its sigmoid calibrator is fitted on separate calibration patients at natural prevalence. The sigmoid operates on raw-score logits clipped with epsilon 1e-7. Calibration-fit metrics are descriptive of the calibration fit population; test metrics below assess held-out calibration. A monotone calibration does not establish clinical risk validity.

| Model | Raw test | Calibrated test |
| --- | --- | --- |
| Logistic Regression | 0.1763 | 0.0093 |
| Random Forest | 0.0656 | 0.0093 |
| XGBoost | 0.0091 | 0.0091 |

Ten-bin expected calibration error:

| Model | Raw test | Calibrated test |
| --- | --- | --- |
| Logistic Regression | 0.3635 | 0.0008 |
| Random Forest | 0.2215 | 0.0004 |
| XGBoost | 0.0004 | 0.0006 |

XGBoost test reliability bins (empty bins remain unavailable):

| Output | Bin lower | Bin upper | Hours | Mean probability | Observed positive fraction |
| --- | --- | --- | --- | --- | --- |
| raw | 0.0000 | 0.1000 | 230,270 | 0.0085 | 0.0081 |
| raw | 0.1000 | 0.2000 | 2,352 | 0.1318 | 0.1297 |
| raw | 0.2000 | 0.3000 | 188 | 0.2302 | 0.2128 |
| raw | 0.3000 | 0.4000 | 22 | 0.3447 | 0.5455 |
| raw | 0.4000 | 0.5000 | 6 | 0.4692 | 0.8333 |
| raw | 0.5000 | 0.6000 | 0 | Unavailable | Unavailable |
| raw | 0.6000 | 0.7000 | 0 | Unavailable | Unavailable |
| raw | 0.7000 | 0.8000 | 0 | Unavailable | Unavailable |
| raw | 0.8000 | 0.9000 | 0 | Unavailable | Unavailable |
| raw | 0.9000 | 1.0000 | 0 | Unavailable | Unavailable |
| calibrated | 0.0000 | 0.1000 | 231,609 | 0.0083 | 0.0087 |
| calibrated | 0.1000 | 0.2000 | 1,182 | 0.1254 | 0.1717 |
| calibrated | 0.2000 | 0.3000 | 41 | 0.2354 | 0.4146 |
| calibrated | 0.3000 | 0.4000 | 6 | 0.3562 | 0.8333 |
| calibrated | 0.4000 | 0.5000 | 0 | Unavailable | Unavailable |
| calibrated | 0.5000 | 0.6000 | 0 | Unavailable | Unavailable |
| calibrated | 0.6000 | 0.7000 | 0 | Unavailable | Unavailable |
| calibrated | 0.7000 | 0.8000 | 0 | Unavailable | Unavailable |
| calibrated | 0.8000 | 0.9000 | 0 | Unavailable | Unavailable |
| calibrated | 0.9000 | 1.0000 | 0 | Unavailable | Unavailable |

Prototype-threshold validation results are stored in the threshold section of [frozen_decisions.json](../artifacts/frozen_decisions.json). The displayed tiers must be assessed against the observed alert counts and sensitivity, not against probability labels alone. The tiers are not changed by research-threshold selection.

## 20. Lead-time analysis

| Model | Point | Comparator | Eligible septic | Any pre-onset alert | No alert | Alert in 1-12h | Conditional 1-12h median (h) | Nonseptic ever alerted | Nonseptic denominator |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Logistic Regression | watch | >= 0.300000 | 374 | 3 | 371 | 2 | 7.0000 | 4 | 5,611 |
| Logistic Regression | elevated | >= 0.500000 | 374 | 0 | 374 | 0 | Unavailable | 3 | 5,611 |
| Logistic Regression | critical | > 0.750000 | 374 | 0 | 374 | 0 | Unavailable | 3 | 5,611 |
| Logistic Regression | research_max_f1 | >= 0.055975 | 374 | 72 | 302 | 59 | 11.0000 | 80 | 5,611 |
| Random Forest | watch | >= 0.300000 | 374 | 3 | 371 | 3 | 6.0000 | 0 | 5,611 |
| Random Forest | elevated | >= 0.500000 | 374 | 0 | 374 | 0 | Unavailable | 0 | 5,611 |
| Random Forest | critical | > 0.750000 | 374 | 0 | 374 | 0 | Unavailable | 0 | 5,611 |
| Random Forest | research_max_f1 | >= 0.077986 | 374 | 100 | 274 | 77 | 10.0000 | 27 | 5,611 |
| XGBoost | watch | >= 0.300000 | 374 | 3 | 371 | 2 | 3.5000 | 0 | 5,611 |
| XGBoost | elevated | >= 0.500000 | 374 | 0 | 374 | 0 | Unavailable | 0 | 5,611 |
| XGBoost | critical | > 0.750000 | 374 | 0 | 374 | 0 | Unavailable | 0 | 5,611 |
| XGBoost | research_max_f1 | >= 0.063594 | 374 | 144 | 230 | 130 | 11.0000 | 63 | 5,611 |

| Model | Point | First-alert detected N | Median lead (h) | 25th percentile | 75th percentile | Alert in 1-6h | Alert in 6-12h | Alert >12h early | Control alert hours /100h |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Logistic Regression | watch | 3 | 40.0000 | 22.5000 | 59.0000 | 1 | 1 | 2 | 0.0038 |
| Logistic Regression | elevated | 0 | Unavailable | Unavailable | Unavailable | 0 | 0 | 0 | 0.0014 |
| Logistic Regression | critical | 0 | Unavailable | Unavailable | Unavailable | 0 | 0 | 0 | 0.0014 |
| Logistic Regression | research_max_f1 | 72 | 37.0000 | 9.7500 | 69.7500 | 54 | 45 | 52 | 0.1382 |
| Random Forest | watch | 3 | 6.0000 | 6.0000 | 6.5000 | 2 | 3 | 0 | 0.0000 |
| Random Forest | elevated | 0 | Unavailable | Unavailable | Unavailable | 0 | 0 | 0 | 0.0000 |
| Random Forest | critical | 0 | Unavailable | Unavailable | Unavailable | 0 | 0 | 0 | 0.0000 |
| Random Forest | research_max_f1 | 100 | 35.0000 | 15.7500 | 85.2500 | 67 | 54 | 79 | 0.0461 |
| XGBoost | watch | 3 | 5.0000 | 3.5000 | 63.5000 | 2 | 0 | 1 | 0.0000 |
| XGBoost | elevated | 0 | Unavailable | Unavailable | Unavailable | 0 | 0 | 0 | 0.0000 |
| XGBoost | critical | 0 | Unavailable | Unavailable | Unavailable | 0 | 0 | 0 | 0.0000 |
| XGBoost | research_max_f1 | 144 | 38.5000 | 16.0000 | 85.2500 | 119 | 101 | 116 | 0.1103 |

Lead times are conditional on detection and omit missed patients; detection and miss denominators are shown explicitly. The 1-12-hour window is an experimental reporting window, not proof of useful intervention time. The 1-6 and 6-12-hour intervals overlap at six hours and are not additive categories. A very early first alert can be a false alarm. Hourly alert burden counts repeated alerts with no cooldown; it is distinct from threshold crossings. Label-implied onset beyond the recorded sequence is included in the eligible cohort and must be interpreted separately.

All recorded lead-time analyses apply the inference withholding policy: an empty clinical-history prefix cannot trigger an alert. Patient denominators retain missed cases, including cases without an available alerting history; the main hourly discrimination tables above use all eligible model hours.

At the frozen XGBoost research threshold, **130 of 374 eligible septic patients** had an alert in the experimental 1-12-hour window. The median within-window lead was **11.0 hours**, with interquartile range 6.0-12.0 hours, conditional on those detections. The separate first-alert median of 38.5 hours includes much earlier alerts and must not be described as useful warning time. 230 patients had no pre-onset alert at all.

Separate within-observation/beyond-observation lead-time results are not present in the current metrics artifact.

## 21. SHAP analysis

A completed global SHAP analysis is recorded below. Global explanations use a fitted XGBoost TreeExplainer on a seeded sample from validation/selection. Contributions explain the **uncalibrated raw margin (log odds)**; they sum with the expected value to that margin, not to the displayed calibrated probability. Missingness features can encode workflow patterns and are not causal effects.

| Measured explanation item | Value |
| --- | --- |
| Explanation sample partition | validation_selection |
| Explanation sample hours | 1,000 |
| Maximum additivity error | 0.00000572 |

| Feature | Mean absolute SHAP | Native XGBoost importance |
| --- | --- | --- |
| ICULOS | 0.4881 | 0.0968 |
| Lactate_hours_since_last | 0.1788 | 0.0331 |
| Temp_last | 0.1770 | 0.0152 |
| HospAdmTime | 0.1559 | 0.0098 |
| Unit1 | 0.1486 | 0.0152 |
| MAP_mean_24h | 0.0819 | 0.0094 |
| HR_trend_6h | 0.0699 | 0.0091 |
| Resp_mean_24h | 0.0613 | 0.0132 |
| FiO2 | 0.0574 | 0.0217 |
| O2Sat_std_6h | 0.0542 | 0.0078 |
| WBC_last | 0.0512 | 0.0081 |
| Resp_std_6h | 0.0476 | 0.0065 |
| WBC_delta_6h | 0.0463 | 0.0078 |
| HR_max_6h | 0.0421 | 0.0104 |
| SBP_hours_since_last | 0.0354 | 0.0123 |

The full ranking is in [feature_importance.csv](feature_importance.csv), with explanation settings in [shap_config.json](../artifacts/shap_config.json). Local inference explanations are calculated from the saved estimator and the same causal feature pipeline. No clinical narrative or ranking is substituted for fitted-model contributions.

The five highest recorded mean-absolute contributions are `ICULOS`, `Lactate_hours_since_last`, `Temp_last`, `HospAdmTime`, `Unit1`. Time, care-location and measurement-recency features rank prominently. This is evidence of the model's reliance on temporal and workflow context, not proof of a biological mechanism. Such dependencies may change across sites and workflows; rankings have not been rearranged to favor clinical variables.

Clinical-score context uses explicitly incomplete proxies on identical complete-case rows:

| Model | Proxy | Available hours | Total hours | Positive hours | Proxy AUROC | Model same-row AUROC | Proxy AP | Model same-row AP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Logistic Regression | qsofa_2_component_proxy | 186,045 | 232,838 | 1,749 | 0.5814 | 0.7903 | 0.0118 | 0.0573 |
| Logistic Regression | news2_scale1_vitals_subtotal | 70,668 | 232,838 | 651 | 0.6347 | 0.7916 | 0.0156 | 0.0535 |
| Random Forest | qsofa_2_component_proxy | 186,045 | 232,838 | 1,749 | 0.5814 | 0.7836 | 0.0118 | 0.0475 |
| Random Forest | news2_scale1_vitals_subtotal | 70,668 | 232,838 | 651 | 0.6347 | 0.7784 | 0.0156 | 0.0453 |
| XGBoost | qsofa_2_component_proxy | 186,045 | 232,838 | 1,749 | 0.5814 | 0.8302 | 0.0118 | 0.0745 |
| XGBoost | news2_scale1_vitals_subtotal | 70,668 | 232,838 | 651 | 0.6347 | 0.8408 | 0.0156 | 0.0705 |

The qSOFA proxy omits altered mentation. NEWS2 is only a five-vital Scale 1 subtotal and omits consciousness/new confusion, oxygen treatment and prescribed saturation-scale choice. Missing components are not imputed as normal; ordinal scores are not probabilities. These comparisons cannot establish superiority over full clinical scores.

The two-component qSOFA proxy sums one point for Resp >=22 and one for SBP <=100, and is unavailable unless both current observations pass the numerical checks. The NEWS2 subtotal sums the five component bins below, requiring every current component; it uses no carry-forward or imputation. Fractional measurements use the documented continuous extension of the published integer bins.

| Component | Measurement interval : subtotal points |
| --- | --- |
| Resp | <=8:3; >8..11:1; >11..20:0; >20..24:2; >24:3 |
| O2Sat | <=91:3; >91..93:2; >93..95:1; >95:0 |
| SBP | <=90:3; >90..100:2; >100..110:1; >110..<220:0; >=220:3 |
| HR | <=40:3; >40..50:1; >50..90:0; >90..110:1; >110..130:2; >130:3 |
| Temp | <=35:3; >35..36:1; >36..38:0; >38..39:1; >39:2 |

Recorded clinical-score sources: [qSOFA source](https://jamanetwork.com/journals/jama/fullarticle/2492881); [NEWS2 scoring chart](https://www.rcp.ac.uk/media/alxev00t/news2-chart-1_the-news-scoring-system_0_0.pdf).

## 22. Leakage audit

Recorded status: **passed**.

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

The audit checks patient and duplicate-record separation, target-independent causal prefixes, onset exclusion and complete evaluation populations. Post-training checks inspect saved training-row counts and the frozen configuration. These checks cannot establish identity linkage beyond the released record identifiers.

## 23. Limitations

The experiment design uses a random internal patient holdout from two historical ICU sources, not external, chronological or prospective validation. Cross-admission patient linkage and original timestamps are unavailable. Repeated patient hours are statistically dependent; no patient-bootstrap confidence intervals are computed. The 160,000-hour uniform fitting cap and three-candidate XGBoost search limit attainable performance and introduce sampling variation. Calibration is internal and target-specific. Pre-onset censoring and uncertain-onset exclusions narrow applicability. Label-implied onset, onsets after observation, sparse labs and measurement/treatment workflows can affect results. Broad numerical bounds are mechanical cleaning rules. Incomplete clinical proxies cannot support superiority claims. Nursing-note NLP is not implemented or trained; this dataset supplies no real nursing notes. Retrospective discrimination, calibration and alert timing do not establish treatment benefit, mortality improvement, clinical thresholds or deployability. Any deployment would require further validation and governance.

The Critical-tier checklist is static clinician reference content from the [SSC Hour-1 Bundle, 2019](https://www.sccm.org/SCCM/media/SCCM/PDFs/Surviving-Sepsis-Campaign-Hour-1-Bundle.pdf), with a separate link to the [current SSC adult guidelines](https://www.sccm.org/survivingsepsiscampaign/guidelines-and-resources/surviving-sepsis-campaign-adult-guidelines). The stored reference metadata records guideline year 2026 as verified on 2026-09-22. The historical checklist must not be presented as the current guideline, a patient-specific treatment order, or evidence of bundle eligibility. A model Critical state does not diagnose sepsis. No delivered physical bedside alert is established by a model output or API alert request.

## 24. Reproducibility instructions

README.md (original experiment workspace) supplies setup, download, audit, preparation, fitting, leakage verification, report generation and inference/API commands. [METHODOLOGY.md](METHODOLOGY.md) records the planned experiment; [experiment_config.json](../experiment_config.json) records fixed settings. Raw audit, split/sample hashes and the pinned dependency list support repeatability. Existing prepared data and consumed test sets are protected from silent overwrite/reselection.

| Artifact | File status (existence alone is not validation) |
| --- | --- |
| models/caresense_xgboost.json | Present |
| models/caresense_xgboost.pkl | Present |
| models/logistic_regression.pkl | Present |
| models/random_forest.pkl | Present |
| artifacts/preprocessing_pipeline.pkl | Present |
| artifacts/feature_names.json | Present |
| artifacts/model_metadata.json | Present |
| artifacts/threshold_config.json | Present |
| artifacts/shap_config.json | Present |
| artifacts/frozen_decisions.json | Present |
| reports/test_access.json | Present |
| reports/training_sample.csv | Present |

Recorded software versions:

```json
{
  "numpy": "2.3.5",
  "pandas": "3.0.1",
  "scikit-learn": "1.9.1",
  "xgboost": "3.4.1",
  "shap": "0.52.0",
  "pyarrow": "25.0.1"
}
```

Execution-test/API evidence:

```json
{
  "status": "passed",
  "consolidated_utc": "2026-09-25T16:56:27.902713+00:00",
  "notice": "Prior executed results are consolidated here with their original timestamps; no fitting or test rerun is implied by the consolidation date.",
  "unit_tests": {
    "status": "passed",
    "tests": 227,
    "failures": 0,
    "errors": 0,
    "skipped": 0,
    "duration_seconds": 30.624,
    "run_started": "2026-09-23T13:38:33.652641+05:30",
    "source": "reports/pytest_results.xml",
    "warnings_observed": 5,
    "warnings_note": "Dependency deprecation warnings in Starlette/AnyIO and SHAP/Matplotlib; no test failures."
  },
  "source_unchanged_since_test_run": true,
  "frozen_artifact_hashes_reverified": 13,
  "saved_model_inference": {
    "status": "passed",
    "verified_utc": "2026-09-23T08:02:51.319632+00:00",
    "synthetic_patients": 5,
    "causal_prefix_predictions": 60,
    "source": "reports/inference_checks.json"
  },
  "live_api": {
    "status": "passed",
    "verified_utc": "2026-09-23T08:08:48.270526+00:00",
    "transport": "real localhost HTTP / uvicorn",
    "request_count": 34,
    "source": "reports/api_checks.json",
    "verification_server_stopped": true
  },
  "dependency_check": {
    "status": "passed",
    "output": "No broken requirements found."
  },
  "physical_hardware_tested": false,
  "clinical_validation_established": false
}
```

Saved-model inference evidence is separately recorded in inference_checks.json (original experiment workspace); synthetic demonstration outputs are not test-set performance measurements.

Measured evaluation plots: [ROC, precision-recall and calibration curves](evaluation_curves.png). See the plot's stated cohort and source artifacts.

## 25. Recommended next development step

After the reported leakage and inference/API checks pass, build the CareSense dashboard against the existing saved-model API. Display the measured calibrated probability, unchanged prototype tier, current hour, contributing feature values and raw-margin explanation caveat. Route every simulation through the same causal history pipeline. The frontend should expose missing-data and model-version context. Pursue independent temporal/external validation and patient-bootstrap uncertainty before considering clinical evaluation.

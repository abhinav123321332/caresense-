# CARESENSE prespecified experimental methodology

Protocol date: 2026-09-22. Status at drafting: planned experiment, before verified full-dataset counts, model fitting, or held-out evaluation. This document specifies decisions; it does not assert that execution or validation has occurred. Actual counts, deviations, software versions, fitted configurations and results must be reported in the execution artifacts and final model report.

## Specification and scope

The working specification is `CareSense_Solution_Document.md`, saved from the user-authorized master prompt; `SPEC_PROVENANCE.md` records its origin. The separate concept document supplies context, and the master prompt governs this backend milestone. No dashboard is part of this experiment.

CARESENSE is an AI-assisted early-warning research prototype. The output is model-estimated risk for a specified retrospective target, not a diagnosis or an independently validated clinical probability. Clinical decisions remain with qualified professionals.

## Data access and verification gate

Use only the official PhysioNet 2019 public training directory, retaining immutable raw files. Expected file counts are A: 20,336; B: 20,000; total: 40,336. These are required counts, not a statement that this execution has verified them. Stop and investigate discrepancies before training. Verify the 40 predictor columns plus `SepsisLabel` against every file. [Official dataset description](https://physionet.org/content/challenge-2019/1.0.0/)

The audit must describe row counts, numeric types, missingness, distribution summaries, label prevalence, positive patients, stay lengths, ages, suspect values, duplicate rows, malformed files, and ICULOS continuity. Report anomalies separately from deterministic preprocessing decisions. Absence of a measurement is not evidence of a normal result. The dataset supplies hourly ICU measurements, not original event timestamps or nursing notes.

## Outcome and eligible hours

PhysioNet defines `SepsisLabel = 1` beginning six hours before its retrospective onset and continuing afterward. Do not shift this label another six hours. Where a 0-to-1 transition is observed, derive `onset_hour = first_positive_ICULOS + 6`; use the supplied label only on hours strictly before that derived onset. This is the primary six-hour early-warning framing. [Official target definition](https://physionet.org/content/challenge-2019/1.0.0/)

First-row-positive records have left-censored transitions; their onset cannot be determined precisely. Exclude them from the primary training/evaluation and lead-time cohorts and report their counts by split. This exclusion is a methodological inference, not an official Challenge rule. Validate binary, monotonic labels. Report label-implied onsets after record end, and identify onset as derived from labels rather than independently observed clinical truth.

For nonseptic records, retain the observed eligible hourly sequence. Results concern the released observation period; they do not prove absence of sepsis after observation ends. Do not use eventual positive status, onset, future length of stay or target-derived information as model inputs. Eventual status is permitted for split stratification only.

## Patient partitioning

Assign complete patient files to approximately 70% training, 15% validation and 15% test with a fixed reproducible seed. Stratify by source A/B and eventual positive-label status. Use source-prefixed patient identifiers. Save the full assignment manifest, counts and seed before fitting.

Partition validation patients into three disjoint subsets for:

1. **Selection:** compare prespecified XGBoost candidates using average precision.
2. **Calibration:** fit the selected XGBoost probability calibration.
3. **Thresholds:** evaluate prototype tiers and choose separately named experimental operating thresholds.

Use approximately equal shares of validation, preserving strata as closely as feasible; exact integer counts must be recorded. No patient may appear in two partitions, including the three validation subsets. Splitting takes place before learned preprocessing. Eligible-hour exclusion is applied consistently after patient assignment and its effect is reported.

The test patients stay untouched during fitting, candidate choice, calibration, threshold selection, feature selection and debugging decisions informed by outcomes. Open the test results only after these choices are frozen. If a necessary correction occurs after test inspection, disclose that the test has been seen and avoid representing repeated selection as a fresh holdout.

## Prespecified resource limitation and sampling

Environment inspection reported approximately 8 GB total memory and less than 1 GB free physical memory at planning time. The experiment therefore caps model-fitting data at **160,000 eligible training hours** using a seeded uniform reservoir. If fewer eligible hours exist, use all of them. Record the realized sample, seed, patient coverage and positive count.

The reservoir is restricted to training patients. Construct each sampled row from its complete causal patient prefix, including earlier unsampled hours. Sampling must not truncate history, rebalance outcomes, admit validation/test records, or use future measurements. The same sampled training hours are used for Logistic Regression, Random Forest and all XGBoost candidates. Fit learned preprocessing on the training sample only; no statistics are estimated from validation or test.

Evaluate **all eligible hours** from each validation subset and from test at their natural observed prevalence. Do not subsample evaluation hours for performance metrics. A separately disclosed, seeded explanation sample may be used for expensive global SHAP summaries; its size and selection must be recorded and it cannot determine model selection.

This limits computation but also limits the experiment: the fitted models do not use all training hours; sparse events, short histories or particular patient patterns may be underrepresented by chance; longer stays contribute more potential rows; results may vary with the reservoir seed. This run cannot establish full-data attainable performance. No oversampling-generated prevalence may be presented as test prevalence.

## Causal preprocessing and feature construction

Validate names, numeric input types and ordered hourly history. Apply one documented deterministic policy for invalid values, with provenance retained; audit values rather than silently changing the raw dataset. For missing observations, distinguish current missingness from historical availability. Forward filling, if used, operates only within the patient prefix; no backward fill or interpolation using future values is permitted. Document any carry-forward expiration.

Use current measurements, missingness indicators, bounded historical rolling statistics, six-hour deltas and causal trends. Investigate 3-, 6-, 12- and 24-hour windows without an uncontrolled feature expansion. Lactate and WBC require explicit current/history, change, trend and missingness handling. A six-hour feature requires the stated historical support; an unavailable history cannot be represented as a measured zero change.

Save the exact feature names and definitions. Logistic Regression uses training-fitted numerical imputation and scaling as needed. XGBoost does not require normalization. Any learned imputation used by Random Forest is likewise fitted only on training data. Training and inference must call the same validation and feature-generation code and reload the same saved fitted objects.

## Models and selection

Fit reproducible Logistic Regression and Random Forest comparisons on the common sample. Record complete estimator parameters, convergence information and class weighting. Do not rank models by accuracy alone.

For the primary XGBoost experiment, evaluate **three** conservative configurations spanning tree depths 3 and 4 and class weighting of either no positive weighting or `sqrt(n_negative / n_positive)`, computed from the sampled training target. Record the three exact parameter dictionaries before fitting. Learning rate, estimator limits, regularization, row/column sampling, early-stopping policy and seed must be explicit in the saved configuration. Do not silently enlarge the search after viewing results.

Select the candidate with the greatest **selection-subset average precision**, using a deterministic recorded tie-break rule. Average precision is the declared PR-AUC convention; do not substitute trapezoidal area without identifying the difference. The small fixed search is a compute-limited comparison, not an exhaustive optimization. Test outcomes cannot affect configuration choice or the choice to report a candidate.

## Calibration and thresholds

Freeze the selected estimator, then fit sigmoid calibration of its logit on the separate calibration patients using their full eligible hours and natural prevalence. Probability clipping for a finite logit must use a fixed recorded epsilon. Do not refit the base model after calibrating it unless calibration is repeated on an independent appropriate cohort.

Report calibration using Brier score and probability-bin reliability summaries; report before/after values where implemented. Calibration is internal and target-specific. Calibration does not establish clinical applicability, especially outside these ICU sources. Class weighting can distort the underlying estimator probabilities; calibrated output must be distinguished from its uncalibrated score.

The prototype tiers remain exactly:

| Probability | Tier |
|---|---|
| `p < 0.30` | Lower risk / not elevated |
| `0.30 <= p < 0.50` | Watch |
| `0.50 <= p <= 0.75` | Elevated |
| `p > 0.75` | Critical |

Thus **exactly 0.75 is Elevated**; Critical requires a strict greater-than comparison. Assess each tier boundary with its actual comparator on the threshold subset. Do not silently convert Critical to `p >= 0.75`. These thresholds are prototype settings, not clinical operating points.

Choose any alternative operating thresholds using only the threshold subset and a prespecified, recorded objective. For recall-at-selected-precision and precision-at-selected-recall, record the requested target, selected threshold and achieved validation operating point. If the target is unattainable, report that rather than selecting a misleading threshold. Apply the frozen alternative to test; never optimize the threshold on test or claim it is clinically optimal.

## Metrics and alert timing

Report AUROC, average precision, precision, recall/sensitivity, specificity, F1, confusion counts and calibration, with patient/row counts and prevalence. Each threshold-based metric must name its threshold and comparator. Report denominators and undefined metrics transparently. Hour-level summaries weight observed hours and are not patient-level performance measures. If confidence intervals are generated, resample patients rather than treating hourly rows as independent.

For each eligible septic patient, calculate lead time from label-implied onset to the first pre-onset threshold alert. Report the median and distribution among detected patients together with all eligible septic patients, detected count and no-alert count. Separately report alerts within 1–6 and 6–12 hours before onset and alerts earlier than 12 hours. A large lead time from a very early false alert is not evidence of useful warning. State whether onset beyond the recorded sequence is included, and report that subgroup separately where present.

Report nonseptic patients ever alerted and hourly alert burden. Define threshold crossing versus repeated elevated hours and any alert cooldown. The Challenge's timing-sensitive utility is an optional additional metric; its official protocol must be identified and altered-cohort results must not be represented as leaderboard-comparable. [Original Challenge paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC6964870/)

## Clinical-score comparisons

Full qSOFA is unavailable because altered mentation is absent. An explicitly named `qsofa_2_component_proxy` may sum `Resp >= 22` and `SBP <= 100`, requiring both inputs. Do not infer normal mentation. The original qSOFA concerns poor outcomes among patients with suspected infection, especially outside the ICU; its clinical task differs from the present target. [Sepsis-3 consensus](https://jamanetwork.com/journals/jama/fullarticle/2492881)

Full NEWS2 is unavailable because consciousness/new confusion, confirmed oxygen supplementation and prescribed oxygen-scale selection are missing. A named `news2_scale1_vitals_subtotal` may include Resp, O2Sat, SBP, HR and Temp and must remain labelled incomplete. Missing FiO2 does not establish room air. Score only complete sets of the required available variables, or expose explicit missing-component status rather than silently substituting normal values. [RCP NEWS2](https://www.rcp.ac.uk/resources/national-early-warning-score-news-2/), [RCP incomplete-score and oxygen-scale guidance](https://www.rcp.ac.uk/media/umzn4ntq/news2_additional-guidance-002-_0.pdf)

Use the official scoring bins with a documented convention for fractional hourly aggregates. Evaluate the model on the same complete-case subset used for each proxy and report coverage. A comparison with an incomplete proxy cannot establish clinical superiority to the full score. [RCP scoring chart](https://www.rcp.ac.uk/media/alxev00t/news2-chart-1_the-news-scoring-system_0_0.pdf)

## Explanations, reproducibility and leakage checks

Use actual fitted-model SHAP values, not manually ranked clinical stories. Verify TreeExplainer additivity against the explained output. Raw-margin SHAP contributions describe the underlying model's log odds; they do not add directly to a calibrated probability. Explain both the displayed probability and the SHAP output scale accurately. Missingness contributions may reflect measurement/workflow patterns and are not causal claims.

Required checks cover disjoint patient assignments; causal prefix invariance; exclusion of target/future-derived predictors; training-only preprocessing; disjoint selection/calibration/threshold patients; and test isolation. Include boundaries at 0.30, 0.50 and 0.75, short histories, all-missing laboratories, unusual inputs, saved-model reload and API calls through the same inference pipeline. A leakage failure must be corrected before reporting performance.

Save model files, preprocessing, feature names, thresholds, calibration parameters, sample/split manifests, configuration, software versions and dataset verification artifacts. Keep actual execution results in the final model report, including failures and deviations. Nursing-note demonstrations, if present, must be explicitly synthetic/proof-of-concept and must not alter the core data-trained predictor. A treatment checklist may only be static, source-linked reference content; the model does not issue personalized treatment orders.

## Interpretation limits

The principal evaluation is an internal patient holdout from two publicly released ICU sources. It is not external validation, prospective validation, assessment of treatment benefit or regulatory evidence. Patient assignment prevents overlap of the supplied records but cannot establish identity linkage beyond released identifiers. Random splitting across the same sources may preserve site and measurement-workflow patterns. Pre-onset censoring and first-row-positive exclusions narrow the applicable population. Historical treatment and ordering practices may influence predictors and outcome ascertainment.

The memory-driven training cap, fixed small candidate search, selective laboratory availability, label-derived onset, repeated-hour dependence and incomplete clinical-score comparators must accompany every interpretation of measured results. Clinical usefulness, mortality improvement and deployability cannot be inferred from retrospective discrimination, calibration or lead time alone.

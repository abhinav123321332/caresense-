"""The published 40 predictors and target; no inferred clinical variables."""

VITALS = ["HR", "O2Sat", "Temp", "SBP", "MAP", "DBP", "Resp", "EtCO2"]
LABS = ["BaseExcess", "HCO3", "FiO2", "pH", "PaCO2", "SaO2", "AST", "BUN",
        "Alkalinephos", "Calcium", "Chloride", "Creatinine", "Bilirubin_direct",
        "Glucose", "Lactate", "Magnesium", "Phosphate", "Potassium",
        "Bilirubin_total", "TroponinI", "Hct", "Hgb", "PTT", "WBC",
        "Fibrinogen", "Platelets"]
STATIC_FEATURES = ["Age", "Gender", "Unit1", "Unit2", "HospAdmTime", "ICULOS"]
INPUT_COLUMNS = VITALS + LABS + STATIC_FEATURES
TARGET = "SepsisLabel"
COLUMNS = INPUT_COLUMNS + [TARGET]
EXPECTED_COUNTS = {"training_setA": 20336, "training_setB": 20000}

# Broad mechanical plausibility flags, not clinical normal ranges and not
# exclusion criteria. Preserve raw data; train-time cleaning is explicit.
AUDIT_BOUNDS = {
    "HR": (0, 350), "O2Sat": (0, 100), "Temp": (20, 45),
    "SBP": (0, 350), "MAP": (0, 300), "DBP": (0, 250),
    "Resp": (0, 100), "EtCO2": (0, 150), "FiO2": (0, 1),
    "pH": (6, 8), "SaO2": (0, 100), "Age": (0, 120),
    "Gender": (0, 1), "Unit1": (0, 1), "Unit2": (0, 1),
    "Hct": (0, 100), "Hgb": (0, 40), "Lactate": (0, 50),
    "WBC": (0, 500), "ICULOS": (1, 10000),
}

"""Real TreeSHAP explanations of the underlying XGBoost margin.

Contributions are uncalibrated log odds, never percentages of calibrated risk.
Positive monotonic sigmoid calibration preserves their directional meaning.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .features import feature_dictionary


class TreeShapExplainer:
    def __init__(self, model, feature_names: list[str]):
        import shap

        self.model = model
        self.feature_names = list(feature_names)
        self.definitions = feature_dictionary()
        self.explainer = shap.TreeExplainer(model, model_output="raw",
                                            feature_perturbation="tree_path_dependent")

    def explain(self, features: pd.DataFrame, top_n: int = 10) -> dict:
        if not isinstance(top_n, int) or isinstance(top_n, bool) or not 1 <= top_n <= len(self.feature_names):
            raise ValueError(f"top_n must be an integer from 1 to {len(self.feature_names)}")
        if len(features) != 1 or list(features.columns) != self.feature_names:
            raise ValueError("Local explanation requires one row in the saved feature order")
        matrix = features.to_numpy(dtype=np.float32)
        values = np.asarray(self.explainer.shap_values(matrix, check_additivity=True), dtype=float)
        if values.shape != matrix.shape or not np.isfinite(values).all():
            raise ValueError("Unexpected or nonfinite binary TreeSHAP output")
        base_values = np.asarray(self.explainer.expected_value, dtype=float).reshape(-1)
        if len(base_values) != 1 or not np.isfinite(base_values).all():
            raise ValueError("Expected one finite binary-model SHAP base value")
        base = float(base_values[0])
        margin = float(np.asarray(self.model.predict(matrix, output_margin=True)).reshape(-1)[0])
        residual = abs(base + float(values.sum()) - margin)
        if not np.isfinite(margin) or residual > 1e-3:
            raise ValueError(f"SHAP failed model-margin additivity verification: {residual}")
        contributions = values[0]
        ranked = np.argsort(-np.abs(contributions), kind="stable")[:top_n]
        top = []
        for index in ranked:
            name, value, contribution = self.feature_names[index], float(matrix[0, index]), float(contributions[index])
            definition = self.definitions[name]
            top.append({"feature": name, "value": value if np.isfinite(value) else None,
                        "shap_value": contribution, "magnitude": abs(contribution),
                        "direction": ("increases risk" if contribution > 0 else "decreases risk" if contribution < 0 else "no contribution"),
                        "source": definition["source"], "operation": definition["operation"],
                        "units": "uncalibrated log odds"})
        return {"method": "TreeExplainer", "units": "uncalibrated log odds", "top_features": top,
                "base_value": base, "model_margin": margin, "sum_all_contributions": float(contributions.sum()),
                "sum_displayed_contributions": float(contributions[ranked].sum()),
                "additivity_absolute_error": residual, "feature_count": len(self.feature_names),
                "note": "All SHAP contributions plus the base value recover the underlying XGBoost log odds. They do not sum to the calibrated risk probability. Directions reflect the increasing calibration transform; they are model associations, not causal effects."}

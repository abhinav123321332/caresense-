"""Held-out sigmoid calibration, serialized with each trained estimator."""
import numpy as np
from sklearn.linear_model import LogisticRegression


class SigmoidCalibrator:
    def fit(self, probabilities, y):
        p = np.asarray(probabilities, dtype=float)
        y = np.asarray(y, dtype=int)
        if set(np.unique(y)) != {0, 1}:
            raise ValueError("Calibration requires both classes on held-out patients")
        self.model_ = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000)
        self.model_.fit(self._logit(p), y)
        if self.model_.coef_[0, 0] <= 0:
            raise ValueError("Calibration is not increasing; investigate model before inference")
        self.n_rows_ = len(y)
        return self

    @staticmethod
    def _logit(p):
        p = np.clip(np.asarray(p, dtype=float), 1e-7, 1 - 1e-7)
        return np.log(p / (1 - p)).reshape(-1, 1)

    def predict(self, probabilities):
        return self.model_.predict_proba(self._logit(probabilities))[:, 1]

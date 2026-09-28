"""Prototype display tiers; these are not clinically validated thresholds."""
from __future__ import annotations

import math
from numbers import Real


PROTOTYPE_THRESHOLDS = {"watch": 0.30, "elevated": 0.50, "critical_strictly_above": 0.75}


def risk_tier(probability: float) -> str:
    if isinstance(probability, bool) or not isinstance(probability, Real):
        raise ValueError("Risk probability must be a finite number in [0, 1]")
    p = float(probability)
    if not math.isfinite(p) or not 0 <= p <= 1:
        raise ValueError("Risk probability must be a finite number in [0, 1]")
    if p > 0.75:
        return "Critical"
    if p >= 0.50:
        return "Elevated"
    if p >= 0.30:
        return "Watch"
    return "Lower"


def risk_output(probability: float) -> dict:
    tier = risk_tier(probability)
    status = {"Lower": "Model-estimated lower risk", "Watch": "Model-estimated risk: watch",
              "Elevated": "Model-estimated elevated risk", "Critical": "Model-estimated critical risk"}[tier]
    return {"risk_probability": float(probability), "risk_tier": tier,
            "risk_status": status, "status": status}

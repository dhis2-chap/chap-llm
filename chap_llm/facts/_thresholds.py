"""Classification thresholds for evaluation metrics.

NOTE: These thresholds are preliminary and have NOT been validated by domain
experts. They will be calibrated by the reference group (CLIM-1881).

The only mathematically grounded boundary is CRPS_NORM_BASELINE = 1.0:
crps_norm > 1.0 means the model is worse than a naive baseline, as defined
by chap-core's normalization. All other values below are estimates.
"""

# ── CRPS (lower is better) ─────────────────────────────────────────────────
# crps_norm = CRPS / (max - min of all observed values in the dataset)
# > 1.0 is mathematically worse than naive baseline (chap-core definition)
CRPS_NORM_BASELINE = 1.0   # grounded: worse than baseline above this
CRPS_NORM_GOOD = 0.8       # TODO: validate with reference group (CLIM-1881)

# ── Calibration: ratio_above_truth (ideal = 0.5) ──────────────────────────
# Share of forecast samples above the observed value.
# 0.5 = perfectly unbiased. Outside the band = systematically biased.
RATIO_CALIBRATED_LOW = 0.4   # TODO: validate
RATIO_CALIBRATED_HIGH = 0.6  # TODO: validate

# ── Coverage (should match the stated interval width) ─────────────────────
# coverage_10_90 should be ~0.80 (80% of actuals inside the 10-90% interval)
# coverage_25_75 should be ~0.50 (50% of actuals inside the 25-75% interval)
COVERAGE_10_90_GOOD = 0.75   # TODO: validate
COVERAGE_10_90_LOW = 0.60    # TODO: validate
COVERAGE_25_75_GOOD = 0.45   # TODO: validate
COVERAGE_25_75_LOW = 0.35    # TODO: validate

# ── Outbreak detection ─────────────────────────────────────────────────────
SENSITIVITY_HIGH = 0.7   # TODO: validate — depends heavily on disease and context
SENSITIVITY_LOW = 0.5    # TODO: validate

# ── Data sufficiency ───────────────────────────────────────────────────────
# Below this, outbreak metrics (sensitivity/specificity) are unreliable.
MIN_OUTBREAKS_TO_JUDGE = 5   # TODO: validate with reference group (CLIM-1881)
MIN_EVALUATED_TO_JUDGE = 10  # TODO: validate

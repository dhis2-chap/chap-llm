"""Classification thresholds for evaluation metrics.

NOTE: These thresholds are preliminary and have NOT been validated by domain
experts. They will be calibrated by the reference group (CLIM-1881).

crps_norm = CRPS / (max_observed - min_observed). There is no mathematically
grounded "good" boundary — all bands below are placeholders until the
reference group sets them.
"""

# ── CRPS (lower is better) ─────────────────────────────────────────────────
# crps_norm = CRPS / (max_observed - min_observed in the forecast cells).
# It expresses the average forecast error as a fraction of the observed range.
# chap-core defines no "good" threshold — all bands below are placeholders.
# TODO: validate ALL bands with reference group (CLIM-1881)
CRPS_NORM_GOOD = 0.8       # TODO: placeholder — reference group must set this
CRPS_NORM_MODERATE = 1.5   # TODO: placeholder — reference group must set this

# ── Calibration: ratio_above_truth (ideal = 0.5) ──────────────────────────
# Share of forecast samples above the observed value.
# 0.5 = perfectly unbiased. Outside the band = systematically biased.
RATIO_CALIBRATED_LOW = 0.4   # TODO: validate
RATIO_CALIBRATED_HIGH = 0.6  # TODO: validate

# ── Coverage (should match the stated interval width) ─────────────────────
# coverage_10_90 nominal = 0.80: 80% of actuals should fall inside the 10–90% interval
# coverage_25_75 nominal = 0.50: 50% of actuals should fall inside the 25–75% interval
# chap-core: "higher is better, up to the target" — beyond the target = overdispersed.
# Classify by absolute distance from nominal in BOTH directions.
COVERAGE_10_90_NOMINAL = 0.80
COVERAGE_25_75_NOMINAL = 0.50
COVERAGE_GOOD_TOLERANCE = 0.10    # TODO: validate with reference group (CLIM-1881)
COVERAGE_MODERATE_TOLERANCE = 0.20  # TODO: validate

# ── Outbreak detection: sensitivity = TP / (TP + FN) ─────────────────────
# "Of all real outbreaks, how many did the model catch?"
SENSITIVITY_HIGH = 0.7   # TODO: validate — depends heavily on disease and context
SENSITIVITY_LOW = 0.5    # TODO: validate

# ── False alarm rate: specificity = TN / (TN + FP) ───────────────────────
# "Of all non-outbreak weeks, how many were correctly not alarmed?"
# Different metric from sensitivity — needs its own thresholds.
SPECIFICITY_HIGH = 0.7   # TODO: validate with reference group (CLIM-1881)
SPECIFICITY_LOW = 0.5    # TODO: validate

# ── Data sufficiency ───────────────────────────────────────────────────────
# Below these, outbreak metrics are unreliable.
MIN_OUTBREAKS_TO_JUDGE = 5          # TODO: validate with reference group (CLIM-1881)
MIN_NON_OUTBREAKS_TO_JUDGE = 5      # TODO: validate
MIN_EVALUATED_TO_JUDGE = 10         # TODO: validate

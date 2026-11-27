"""Classification bands used by the facts layer.

PROVISIONAL. These are our own interpretation bands, not chap-core's (chap-core
owns the *outbreak/alert* thresholds, which we reuse via the adapter). Whether one
set of bands is valid across diseases, countries and temporal resolutions is an
open question for the reference group. Keep every band here so it can be changed
(or made configurable) in one place.
"""

# crps_norm = CRPS / (max - min of observed values in the dataset).
# Typical real-world values range from ~0.1 to >2.0.
# TODO: validate with reference group (CLIM-1881) — these are placeholders only.
CRPS_NORM_LOW_ERROR = 0.3           # below -> "low_error"
CRPS_NORM_MODERATE_ERROR = 0.6      # below -> "moderate_error", else "high_error"

# ratio_above_truth: share of samples above the observed value. 0.5 = unbiased.
BIAS_TOLERANCE = 0.1                # |ratio - 0.5| <= tol -> "unbiased"

# Prediction-interval coverage: nominal 0.80 (10-90) and 0.50 (25-75).
COVERAGE_NOMINAL_10_90 = 0.80
COVERAGE_NOMINAL_25_75 = 0.50
COVERAGE_TOLERANCE = 0.1

# Sensitivity / specificity bands.
RATE_HIGH = 0.8                     # >= -> "high"
RATE_MODERATE = 0.5                 # >= -> "moderate", else "low"

# Evidence thresholds (below these, rates are flagged as unreliable).
MIN_EVENTS_FOR_RATE = 5             # outbreaks (sensitivity) / non-outbreaks (specificity)
MIN_EVALUATED = 30                  # evaluated (location, period) cells
MIN_SPLITS = 3

# Horizon trend: crps at longest horizon / crps at shortest horizon.
# TODO: validate with reference group (CLIM-1881) — depends on disease and temporal resolution.
HORIZON_DEGRADATION_RATIO = 1.25

"""Facts layer for evaluation results.

Takes an EvaluationResult contract and returns a source_facts dict ready
for the prompt builder. All classification happens here — the LLM receives
only finished facts, never raw numbers to interpret.

No imports from chap-core. No LLM calls.
"""

from __future__ import annotations

from typing import Literal

from chap_llm.contracts.evaluation import EvaluationResult
from chap_llm.facts._anonymize import anonymize_locations
from chap_llm.facts._thresholds import (
    COVERAGE_10_90_GOOD,
    COVERAGE_10_90_LOW,
    COVERAGE_25_75_GOOD,
    COVERAGE_25_75_LOW,
    CRPS_NORM_BASELINE,
    CRPS_NORM_GOOD,
    MIN_EVALUATED_TO_JUDGE,
    MIN_OUTBREAKS_TO_JUDGE,
    RATIO_CALIBRATED_HIGH,
    RATIO_CALIBRATED_LOW,
    SENSITIVITY_HIGH,
    SENSITIVITY_LOW,
)

Audience = Literal["epidemiologist", "district_health_officer", "decision_maker"]


# ── classifiers ───────────────────────────────────────────────────────────────

def _crps_quality(crps_norm: float | None) -> str:
    """Classify overall accuracy from crps_norm."""
    if crps_norm is None:
        return "unknown"
    if crps_norm <= CRPS_NORM_GOOD:
        return "good"
    if crps_norm <= CRPS_NORM_BASELINE:
        return "moderate"
    return "poor"


def _calibration(ratio: float) -> str:
    """Classify forecast bias from ratio_above_truth."""
    if RATIO_CALIBRATED_LOW <= ratio <= RATIO_CALIBRATED_HIGH:
        return "well_calibrated"
    if ratio < RATIO_CALIBRATED_LOW:
        return "overestimates"   # most samples above truth → model predicts too high
    return "underestimates"      # most samples below truth → model predicts too low


def _coverage_quality(coverage_10_90: float, coverage_25_75: float) -> str:
    """Classify interval coverage."""
    if coverage_10_90 >= COVERAGE_10_90_GOOD and coverage_25_75 >= COVERAGE_25_75_GOOD:
        return "good"
    if coverage_10_90 >= COVERAGE_10_90_LOW and coverage_25_75 >= COVERAGE_25_75_LOW:
        return "moderate"
    return "poor"


def _sensitivity_level(sensitivity: float | None, n_outbreaks: int) -> str:
    """Classify outbreak detection rate."""
    if n_outbreaks < MIN_OUTBREAKS_TO_JUDGE:
        return "too_few_outbreaks"
    if sensitivity is None:
        return "unknown"
    if sensitivity >= SENSITIVITY_HIGH:
        return "high"
    if sensitivity >= SENSITIVITY_LOW:
        return "moderate"
    return "low"


def _specificity_level(specificity: float | None, n_non_outbreaks: int) -> str:
    """Classify false alarm rate."""
    if n_non_outbreaks < MIN_OUTBREAKS_TO_JUDGE:
        return "too_few_non_outbreaks"
    if specificity is None:
        return "unknown"
    if specificity >= SENSITIVITY_HIGH:
        return "high"
    if specificity >= SENSITIVITY_LOW:
        return "moderate"
    return "low"


# ── public API ────────────────────────────────────────────────────────────────

def classify_evaluation(
    result: EvaluationResult,
    audience: Audience,
) -> dict:
    """Classify an EvaluationResult into a source_facts dict for the prompt.

    Args:
        result:   EvaluationResult from the adapter.
        audience: One of "epidemiologist", "district_health_officer",
                  "decision_maker".

    Returns:
        A flat dict of facts. All location names are anonymized.
        The dict is filtered to the fields relevant for the audience.
    """
    loc_map = anonymize_locations(result.locations)
    m = result.global_metrics
    o = result.outbreak_metrics
    c = o.counts
    n_outbreaks = c.tp + c.fn
    n_non_outbreaks = c.tn + c.fp

    # ── core facts (all audiences) ────────────────────────────────────────
    facts: dict = {
        # metadata
        "model_name": result.model_name,
        "model_version": result.model_version,
        "n_locations": len(result.locations),
        "n_splits": result.n_splits,
        "max_horizon": result.max_horizon,
        "baseline_years_used": o.alert_policy.baseline_years_used,
        "baseline_years_requested": o.alert_policy.baseline_years_requested,
        "alert_strategy": o.alert_policy.strategy,
        "alert_quantile": o.alert_policy.quantile,
        "alert_exceedance_threshold": o.alert_policy.exceedance_threshold,
        "n_evaluated": o.n_evaluated,

        # accuracy
        "crps": m.crps,
        "mae": m.mae,
        "crps_quality": _crps_quality(m.crps_norm),
        "beats_baseline": (m.crps_norm < CRPS_NORM_BASELINE) if m.crps_norm is not None else None,

        # calibration
        "ratio_above_truth": m.ratio_above_truth,
        "calibration": _calibration(m.ratio_above_truth),

        # coverage
        "coverage_10_90": m.coverage_10_90,
        "coverage_25_75": m.coverage_25_75,
        "coverage_quality": _coverage_quality(m.coverage_10_90, m.coverage_25_75),

        # outbreak detection
        "n_outbreaks": n_outbreaks,
        "n_non_outbreaks": n_non_outbreaks,
        "tp": c.tp, "fp": c.fp, "fn": c.fn, "tn": c.tn,
        "sensitivity": o.sensitivity,
        "specificity": o.specificity,
        "sensitivity_level": _sensitivity_level(o.sensitivity, n_outbreaks),
        "specificity_level": _specificity_level(o.specificity, n_non_outbreaks),

        # anonymized locations
        "location_map": loc_map,
    }

    # ── audience filter ───────────────────────────────────────────────────
    return _filter_for_audience(facts, audience)


def _filter_for_audience(facts: dict, audience: Audience) -> dict:
    """Remove fields not relevant for the given audience."""

    # decision_maker: high-level only — no raw metric values
    if audience == "decision_maker":
        remove = {
            "crps", "mae", "ratio_above_truth",
            "coverage_10_90", "coverage_25_75",
            "tp", "fp", "fn", "tn",
            "sensitivity", "specificity",
            "alert_quantile", "alert_exceedance_threshold",
            "baseline_years_requested",
        }
        return {k: v for k, v in facts.items() if k not in remove}

    # district_health_officer: operational — no crps_norm internals
    if audience == "district_health_officer":
        remove = {
            "crps", "ratio_above_truth",
            "coverage_10_90", "coverage_25_75",
            "alert_quantile", "alert_exceedance_threshold",
        }
        return {k: v for k, v in facts.items() if k not in remove}

    # epidemiologist: everything
    return facts

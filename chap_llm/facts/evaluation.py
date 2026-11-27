"""Facts layer for evaluation results.

Turns an ``EvaluationResult`` into a classified, anonymized, audience-filtered
facts dict. Everything here is plain code: no LLM call, no prose.

Conventions for the returned dict:
- A key that is *absent* means "not relevant for this audience".
- A value of ``None`` means "missing in the data" (never 0 or "").
- Every classification is a machine-readable code; the prompt turns it into words.
- No real location names and no raw case counts (privacy boundary, see
  ARCHITECTURE.md "Privacy").
"""

from __future__ import annotations

from typing import Any, Optional

from chap_llm.contracts.audience import Audience, validate_audience
from chap_llm.contracts.evaluation import (
    EvaluationResult,
    HorizonResult,
    MetricSet,
    OutbreakMetrics,
)
from chap_llm.facts import _thresholds as t
from chap_llm.facts._anonymize import location_aliases

DECIMALS = 3


def _r(x: Optional[float]) -> Optional[float]:
    return None if x is None else round(x, DECIMALS)


# ── Classifiers (pure functions, individually tested) ─────────────────────────


def classify_error(crps_norm: Optional[float]) -> str:
    """Classify forecast accuracy from crps_norm (CRPS / observed range, lower is better)."""
    if crps_norm is None:
        return "unknown"
    if crps_norm < t.CRPS_NORM_LOW_ERROR:
        return "low_error"
    if crps_norm < t.CRPS_NORM_MODERATE_ERROR:
        return "moderate_error"
    return "high_error"


def classify_bias(ratio_above_truth: float) -> str:
    """Classify systematic forecast bias from ratio_above_truth.

    ratio_above_truth = share of samples above the observed value (0.5 = unbiased).
    Above 0.5 + tolerance → overestimates; below 0.5 − tolerance → underestimates.
    """
    if ratio_above_truth > 0.5 + t.BIAS_TOLERANCE:
        return "overestimates"
    if ratio_above_truth < 0.5 - t.BIAS_TOLERANCE:
        return "underestimates"
    return "unbiased"


def classify_coverage(observed: float, nominal: float) -> str:
    """Classify prediction-interval coverage by distance from the nominal target.

    Too wide → overdispersed (uninformative); too narrow → underdispersed (overconfident).
    """
    if observed > nominal + t.COVERAGE_TOLERANCE:
        return "intervals_too_wide"
    if observed < nominal - t.COVERAGE_TOLERANCE:
        return "intervals_too_narrow"
    return "well_calibrated"


def classify_rate(rate: Optional[float], n_events: int, too_few_code: str) -> str:
    """Classify sensitivity/specificity.

    ``unknown``  -> rate is None (no events at all; must never be read as 0 or 1)
    ``too_few_*`` -> a rate exists but rests on too few events to judge
    """
    if rate is None:
        return "unknown"
    if n_events < t.MIN_EVENTS_FOR_RATE:
        return too_few_code
    if rate >= t.RATE_HIGH:
        return "high"
    if rate >= t.RATE_MODERATE:
        return "moderate"
    return "low"


def classify_horizon_trend(per_horizon: list[HorizonResult]) -> str:
    """Does error grow with forecast horizon? Compares CRPS at the shortest and
    longest horizon."""
    if len(per_horizon) < 2:
        return "unknown"
    ordered = sorted(per_horizon, key=lambda h: h.horizon_distance)
    first, last = ordered[0].metrics.crps, ordered[-1].metrics.crps
    if first <= 0:
        return "unknown"
    return "degrades_with_horizon" if last / first >= t.HORIZON_DEGRADATION_RATIO else "stable"


# ── Section builders ──────────────────────────────────────────────────────────


def _metadata(r: EvaluationResult) -> dict[str, Any]:
    return {
        "model_name": r.model_name,
        "model_version": r.model_version,
        "n_splits": r.n_splits,
        "max_horizon": r.max_horizon,
        "n_locations": len(r.locations),
    }


def _accuracy(m: MetricSet, with_numbers: bool) -> dict[str, Any]:
    out: dict[str, Any] = {"error_level": classify_error(m.crps_norm)}
    if with_numbers:
        out |= {"crps": _r(m.crps), "crps_norm": _r(m.crps_norm), "mae": _r(m.mae)}
    return out


def _calibration(m: MetricSet, with_numbers: bool) -> dict[str, Any]:
    out: dict[str, Any] = {"bias": classify_bias(m.ratio_above_truth)}
    if with_numbers:
        out["ratio_above_truth"] = _r(m.ratio_above_truth)
    return out


def _interval_coverage(m: MetricSet) -> dict[str, Any]:
    return {
        "coverage_10_90": _r(m.coverage_10_90),
        "coverage_10_90_nominal": t.COVERAGE_NOMINAL_10_90,
        "coverage_10_90_class": classify_coverage(m.coverage_10_90, t.COVERAGE_NOMINAL_10_90),
        "coverage_25_75": _r(m.coverage_25_75),
        "coverage_25_75_nominal": t.COVERAGE_NOMINAL_25_75,
        "coverage_25_75_class": classify_coverage(m.coverage_25_75, t.COVERAGE_NOMINAL_25_75),
    }


def _horizons(r: EvaluationResult) -> dict[str, Any]:
    return {
        "trend": classify_horizon_trend(r.per_horizon),
        "by_horizon": [
            {
                "horizon_distance": h.horizon_distance,
                "n_evaluated": h.n_evaluated,
                "crps": _r(h.metrics.crps),
                "mae": _r(h.metrics.mae),
                "bias": classify_bias(h.metrics.ratio_above_truth),
            }
            for h in sorted(r.per_horizon, key=lambda h: h.horizon_distance)
        ],
    }


def _locations(r: EvaluationResult) -> list[dict[str, Any]]:
    alias = location_aliases(r.locations)
    return [
        {
            "location": alias[loc.location],
            "n_evaluated": loc.n_evaluated,
            "crps": _r(loc.metrics.crps),
            "mae": _r(loc.metrics.mae),
            "bias": classify_bias(loc.metrics.ratio_above_truth),
            "coverage_10_90_class": classify_coverage(
                loc.metrics.coverage_10_90, t.COVERAGE_NOMINAL_10_90
            ),
        }
        for loc in sorted(r.per_location, key=lambda x: alias[x.location])
    ]


def _outbreak(o: OutbreakMetrics, *, with_counts: bool, with_rates: bool) -> dict[str, Any]:
    c = o.counts
    n_outbreaks, n_non_outbreaks = c.tp + c.fn, c.tn + c.fp
    p = o.alert_policy
    out: dict[str, Any] = {
        "n_outbreaks": n_outbreaks,
        "n_non_outbreaks": n_non_outbreaks,
        "n_alerts": c.tp + c.fp,
        "n_evaluated": o.n_evaluated,
        "sensitivity_status": classify_rate(o.sensitivity, n_outbreaks, "too_few_outbreaks"),
        "specificity_status": classify_rate(o.specificity, n_non_outbreaks, "too_few_non_outbreaks"),
    }
    if with_rates:
        out |= {"sensitivity": _r(o.sensitivity), "specificity": _r(o.specificity)}
    if with_counts:
        out["counts"] = {"tp": c.tp, "fp": c.fp, "fn": c.fn, "tn": c.tn}
    out["alert_policy"] = {  # always stated: the threshold strategy changes conclusions
        "strategy": p.strategy,
        "quantile": p.quantile,
        "baseline_years_requested": p.baseline_years_requested,
        "baseline_years_used": p.baseline_years_used,
        "exceedance_threshold": p.exceedance_threshold,
        "source": p.source,
    }
    return out


def _caveats(r: EvaluationResult) -> list[str]:
    """Machine-readable limitation codes. The prompt phrases them."""
    o, c = r.outbreak_metrics, r.outbreak_metrics.counts
    n_outbreaks, n_non_outbreaks = c.tp + c.fn, c.tn + c.fp
    codes = ["backtest_only"]  # explains past performance, not live alerts
    if o.alert_policy.baseline_years_used < o.alert_policy.baseline_years_requested:
        codes.append("short_baseline")
    if n_outbreaks == 0:
        codes.append("no_outbreaks")
    elif n_outbreaks < t.MIN_EVENTS_FOR_RATE:
        codes.append("few_outbreaks")
    if n_non_outbreaks == 0:
        codes.append("no_non_outbreaks")
    elif n_non_outbreaks < t.MIN_EVENTS_FOR_RATE:
        codes.append("few_non_outbreaks")
    if o.n_evaluated < t.MIN_EVALUATED:
        codes.append("small_evaluation_sample")
    if r.n_splits < t.MIN_SPLITS:
        codes.append("few_splits")
    if r.model_version is None:
        codes.append("model_version_unknown")
    return codes


# ── Public entry point ────────────────────────────────────────────────────────


def build_evaluation_facts(result: EvaluationResult, audience: str) -> dict[str, Any]:
    """Classify an evaluation and select the facts the given audience needs.

    The returned dict is JSON-serializable and is what goes into both the prompt
    and ``ExplanationResponse.source_facts``.
    """
    aud: Audience = validate_audience(audience)
    g = result.global_metrics
    facts: dict[str, Any] = {
        "audience": aud,
        "result_type": "evaluation",
        "metadata": _metadata(result),
    }

    if aud == "epidemiologist":
        facts["accuracy"] = _accuracy(g, with_numbers=True)
        facts["calibration"] = _calibration(g, with_numbers=True)
        facts["interval_coverage"] = _interval_coverage(g)
        facts["horizons"] = _horizons(result)
        facts["locations"] = _locations(result)
        facts["outbreak_detection"] = _outbreak(
            result.outbreak_metrics, with_counts=True, with_rates=True
        )
    elif aud == "district_health_officer":
        facts["accuracy"] = _accuracy(g, with_numbers=False)
        facts["calibration"] = _calibration(g, with_numbers=False)
        facts["outbreak_detection"] = _outbreak(
            result.outbreak_metrics, with_counts=True, with_rates=True
        )
    else:  # decision_maker: classes only, no metric jargon or counts
        facts["accuracy"] = _accuracy(g, with_numbers=False)
        facts["calibration"] = _calibration(g, with_numbers=False)
        facts["outbreak_detection"] = _outbreak(
            result.outbreak_metrics, with_counts=False, with_rates=False
        )

    facts["caveats"] = _caveats(result)
    return facts

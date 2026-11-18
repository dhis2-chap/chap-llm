"""Tests for the evaluation facts layer.

Uses hand-made EvaluationResult objects — no .nc file needed.
Run: uv run pytest tests/ -v
"""

from chap_llm.contracts.evaluation import (
    AlertPolicyInfo,
    EvaluationResult,
    HorizonResult,
    LocationResult,
    MetricSet,
    OutbreakCounts,
    OutbreakMetrics,
)
from chap_llm.facts.evaluation import classify_evaluation
from chap_llm.facts._anonymize import anonymize_locations


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_result(
    crps=0.5, crps_norm=0.75, mae=10.0,
    ratio=0.5, cov_10_90=0.80, cov_25_75=0.50,
    sensitivity=0.8, specificity=0.9,
    tp=8, fp=1, fn=2, tn=9,
    locations=("Vientiane", "Attapeu", "Luang"),
) -> EvaluationResult:
    policy = AlertPolicyInfo(
        strategy="percentile", quantile=0.75,
        baseline_years_requested=5, baseline_years_used=3,
        exceedance_threshold=0.5, source="local_default",
    )
    metrics = MetricSet(
        crps=crps, crps_norm=crps_norm, mae=mae,
        ratio_above_truth=ratio,
        coverage_10_90=cov_10_90, coverage_25_75=cov_25_75,
    )
    outbreak = OutbreakMetrics(
        counts=OutbreakCounts(tp=tp, fp=fp, fn=fn, tn=tn),
        n_evaluated=tp + fp + fn + tn,
        sensitivity=sensitivity, specificity=specificity,
        alert_policy=policy,
    )
    loc_metrics = MetricSet(crps=crps, crps_norm=None, mae=mae,
                            ratio_above_truth=ratio,
                            coverage_10_90=cov_10_90, coverage_25_75=cov_25_75)
    return EvaluationResult(
        model_name="test_model", model_version="1.0",
        n_splits=2, max_horizon=4,
        locations=list(locations),
        global_metrics=metrics,
        per_location=[LocationResult(location=l, n_evaluated=5, metrics=loc_metrics)
                      for l in locations],
        per_horizon=[HorizonResult(horizon_distance=i, n_evaluated=5, metrics=loc_metrics)
                     for i in range(1, 5)],
        outbreak_metrics=outbreak,
    )


# ── anonymization ─────────────────────────────────────────────────────────────

def test_anonymize_replaces_all_names():
    mapping = anonymize_locations(["Vientiane", "Attapeu", "Luang"])
    assert set(mapping.values()) == {"District A", "District B", "District C"}
    assert "Vientiane" not in mapping.values()


def test_anonymize_is_deterministic():
    m1 = anonymize_locations(["B", "A"])
    m2 = anonymize_locations(["B", "A"])
    assert m1 == m2


def test_anonymize_sorts_before_labelling():
    # sorted: A → District A, B → District B
    mapping = anonymize_locations(["B", "A"])
    assert mapping["A"] == "District A"
    assert mapping["B"] == "District B"


# ── classification ────────────────────────────────────────────────────────────

def test_crps_quality_good():
    facts = classify_evaluation(_make_result(crps_norm=0.75), "epidemiologist")
    assert facts["crps_quality"] == "good"
    assert facts["beats_baseline"] is True


def test_crps_quality_moderate():
    facts = classify_evaluation(_make_result(crps_norm=0.95), "epidemiologist")
    assert facts["crps_quality"] == "moderate"
    assert facts["beats_baseline"] is True


def test_crps_quality_poor():
    facts = classify_evaluation(_make_result(crps_norm=1.1), "epidemiologist")
    assert facts["crps_quality"] == "poor"
    assert facts["beats_baseline"] is False


def test_calibration_well_calibrated():
    facts = classify_evaluation(_make_result(ratio=0.5), "epidemiologist")
    assert facts["calibration"] == "well_calibrated"


def test_calibration_overestimates():
    # ratio < 0.4: most samples above truth → model predicts too high
    facts = classify_evaluation(_make_result(ratio=0.3), "epidemiologist")
    assert facts["calibration"] == "overestimates"


def test_calibration_underestimates():
    facts = classify_evaluation(_make_result(ratio=0.7), "epidemiologist")
    assert facts["calibration"] == "underestimates"


def test_sensitivity_too_few_outbreaks():
    # tp=1, fn=1 → n_outbreaks=2, below MIN_OUTBREAKS_TO_JUDGE
    facts = classify_evaluation(
        _make_result(tp=1, fn=1, fp=5, tn=5, sensitivity=0.5),
        "epidemiologist",
    )
    assert facts["sensitivity_level"] == "too_few_outbreaks"


def test_sensitivity_high():
    facts = classify_evaluation(
        _make_result(tp=8, fn=2, sensitivity=0.8),
        "epidemiologist",
    )
    assert facts["sensitivity_level"] == "high"


# ── audience filter ───────────────────────────────────────────────────────────

def test_epidemiologist_gets_raw_crps():
    facts = classify_evaluation(_make_result(), "epidemiologist")
    assert "crps" in facts
    assert "ratio_above_truth" in facts


def test_decision_maker_no_raw_metrics():
    facts = classify_evaluation(_make_result(), "decision_maker")
    assert "crps" not in facts
    assert "mae" not in facts
    assert "ratio_above_truth" not in facts
    # but gets qualitative facts
    assert "crps_quality" in facts
    assert "sensitivity_level" in facts


def test_district_manager_no_crps_raw():
    facts = classify_evaluation(_make_result(), "district_health_officer")
    assert "crps" not in facts
    # but gets mae and counts
    assert "mae" in facts
    assert "tp" in facts


def test_location_map_in_all_audiences():
    for audience in ("epidemiologist", "district_health_officer", "decision_maker"):
        facts = classify_evaluation(_make_result(), audience)
        assert "location_map" in facts
        # real names must not appear as values
        for real_name in ("Vientiane", "Attapeu", "Luang"):
            assert real_name not in facts["location_map"].values()

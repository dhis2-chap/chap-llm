"""Tests for the evaluation facts layer.

Hand-made EvaluationResult objects are used for edge cases; the real Laos
eval.nc is used for end-to-end checks and the privacy check.
"""

import json
from pathlib import Path

import pytest

from chap_llm.adapter.evaluation import load_evaluation
from chap_llm.contracts.audience import AUDIENCES
from chap_llm.contracts.evaluation import (
    AlertPolicyInfo,
    EvaluationResult,
    HorizonResult,
    LocationResult,
    MetricSet,
    OutbreakCounts,
    OutbreakMetrics,
)
from chap_llm.facts import build_evaluation_facts, location_aliases
from chap_llm.facts.evaluation import (
    classify_bias,
    classify_coverage,
    classify_error,
    classify_horizon_trend,
    classify_rate,
)

NC_FILE = Path(__file__).parent.parent.parent / "chap-core" / "eval.nc"


def make_metrics(**kw) -> MetricSet:
    base = dict(
        crps=10.0, crps_norm=None, mae=12.0,
        ratio_above_truth=0.5, coverage_10_90=0.8, coverage_25_75=0.5,
    )
    return MetricSet(**(base | kw))


def make_result(
    *, tp=8, fp=2, fn=2, tn=18, sens="auto", spec="auto",
    baseline_used=5, n_splits=6, version="1.0", locations=("Vientiane", "Attapeu"),
    n_evaluated=30, horizons=((1, 10.0), (3, 10.0)), global_kw=None,
) -> EvaluationResult:
    sens = tp / (tp + fn) if sens == "auto" and tp + fn else (None if sens == "auto" else sens)
    spec = tn / (tn + fp) if spec == "auto" and tn + fp else (None if spec == "auto" else spec)
    return EvaluationResult(
        model_name="chap_ewars_v2", model_version=version, n_splits=n_splits,
        max_horizon=3, locations=list(locations),
        global_metrics=make_metrics(crps_norm=0.1, **(global_kw or {})),
        per_location=[
            LocationResult(location=l, n_evaluated=10, metrics=make_metrics())
            for l in locations
        ],
        per_horizon=[
            HorizonResult(horizon_distance=h, n_evaluated=10, metrics=make_metrics(crps=c))
            for h, c in horizons
        ],
        outbreak_metrics=OutbreakMetrics(
            counts=OutbreakCounts(tp=tp, fp=fp, fn=fn, tn=tn),
            n_evaluated=n_evaluated, sensitivity=sens, specificity=spec,
            alert_policy=AlertPolicyInfo(
                strategy="percentile", quantile=0.75, baseline_years_requested=5,
                baseline_years_used=baseline_used, exceedance_threshold=0.5,
                source="local_default",
            ),
        ),
    )


# ── Classifiers ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("x,expected", [
    (None, "unknown"), (0.1, "low_error"), (0.4, "moderate_error"), (0.8, "high_error"),
])
def test_classify_error(x, expected):
    assert classify_error(x) == expected


@pytest.mark.parametrize("x,expected", [
    (0.5, "unbiased"), (0.59, "unbiased"), (0.8, "overestimates"), (0.2, "underestimates"),
])
def test_classify_bias(x, expected):
    assert classify_bias(x) == expected


@pytest.mark.parametrize("obs,nom,expected", [
    (0.8, 0.8, "well_calibrated"), (0.5, 0.8, "intervals_too_narrow"),
    (0.95, 0.8, "intervals_too_wide"),
])
def test_classify_coverage(obs, nom, expected):
    assert classify_coverage(obs, nom) == expected


def test_classify_rate_none_is_unknown_not_low():
    assert classify_rate(None, 0, "too_few_outbreaks") == "unknown"


def test_classify_rate_too_few_events_takes_precedence_over_band():
    assert classify_rate(1.0, 2, "too_few_outbreaks") == "too_few_outbreaks"


@pytest.mark.parametrize("rate,expected", [(0.9, "high"), (0.6, "moderate"), (0.2, "low")])
def test_classify_rate_bands(rate, expected):
    assert classify_rate(rate, 20, "x") == expected


def test_horizon_trend():
    degr = make_result(horizons=((1, 5.0), (3, 10.0)))
    assert classify_horizon_trend(degr.per_horizon) == "degrades_with_horizon"
    stable = make_result(horizons=((1, 10.0), (3, 10.5)))
    assert classify_horizon_trend(stable.per_horizon) == "stable"
    single = make_result(horizons=((1, 10.0),))
    assert classify_horizon_trend(single.per_horizon) == "unknown"


# ── Anonymization ─────────────────────────────────────────────────────────────

def test_location_aliases_are_deterministic_and_order_independent():
    a = location_aliases(["B", "A", "C"])
    assert a == {"A": "District A", "B": "District B", "C": "District C"}
    assert location_aliases(["C", "A", "B"]) == a


def test_location_aliases_beyond_26():
    a = location_aliases([f"loc{i:02d}" for i in range(28)])
    assert a["loc25"] == "District Z"
    assert a["loc26"] == "District AA"
    assert len(set(a.values())) == 28


# ── Outbreak facts: unknown / too few / caveats ───────────────────────────────

def test_specificity_none_gives_unknown_and_caveat():
    facts = build_evaluation_facts(make_result(tp=6, fp=0, fn=0, tn=0), "epidemiologist")
    ob = facts["outbreak_detection"]
    assert ob["specificity"] is None
    assert ob["specificity_status"] == "unknown"
    assert "no_non_outbreaks" in facts["caveats"]


def test_few_outbreaks_flagged():
    facts = build_evaluation_facts(make_result(tp=2, fp=1, fn=1, tn=20), "district_health_officer")
    assert facts["outbreak_detection"]["sensitivity_status"] == "too_few_outbreaks"
    assert "few_outbreaks" in facts["caveats"]


def test_short_baseline_and_missing_version_caveats():
    facts = build_evaluation_facts(
        make_result(baseline_used=2, version=None), "decision_maker"
    )
    assert "short_baseline" in facts["caveats"]
    assert "model_version_unknown" in facts["caveats"]
    assert facts["metadata"]["model_version"] is None


def test_backtest_only_caveat_always_present():
    for aud in AUDIENCES:
        assert "backtest_only" in build_evaluation_facts(make_result(), aud)["caveats"]


def test_alert_policy_always_stated():
    for aud in AUDIENCES:
        pol = build_evaluation_facts(make_result(), aud)["outbreak_detection"]["alert_policy"]
        assert pol["quantile"] == 0.75 and pol["baseline_years_used"] == 5


# ── Audience filtering ────────────────────────────────────────────────────────

def test_unknown_audience_raises():
    with pytest.raises(ValueError):
        build_evaluation_facts(make_result(), "journalist")


def test_epidemiologist_gets_full_detail():
    f = build_evaluation_facts(make_result(), "epidemiologist")
    assert {"accuracy", "calibration", "interval_coverage", "horizons", "locations"} <= f.keys()
    assert f["accuracy"]["crps"] == 10.0
    assert f["outbreak_detection"]["counts"] == {"tp": 8, "fp": 2, "fn": 2, "tn": 18}


def test_manager_gets_alert_facts_but_no_metric_numbers():
    f = build_evaluation_facts(make_result(), "district_health_officer")
    assert "interval_coverage" not in f and "locations" not in f
    assert "crps" not in f["accuracy"]
    assert f["outbreak_detection"]["sensitivity"] == 0.8


def test_decision_maker_gets_classes_only():
    f = build_evaluation_facts(make_result(), "decision_maker")
    dumped = json.dumps(f)
    for key in ("crps", "mae", "ratio_above_truth", "sensitivity\"", "counts"):
        assert key not in dumped
    assert f["outbreak_detection"]["sensitivity_status"] == "high"


# ── Privacy ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("audience", AUDIENCES)
def test_no_real_location_names_in_facts(audience):
    names = ("Vientiane", "Attapeu")
    facts = build_evaluation_facts(make_result(locations=names), audience)
    dumped = json.dumps(facts)
    for name in names:
        assert name not in dumped


def test_epidemiologist_locations_use_placeholders():
    f = build_evaluation_facts(make_result(), "epidemiologist")
    assert [l["location"] for l in f["locations"]] == ["District A", "District B"]


def test_facts_are_json_serializable_and_rounded():
    f = build_evaluation_facts(make_result(global_kw={"crps": 1 / 3}), "epidemiologist")
    assert json.loads(json.dumps(f)) == f
    assert f["accuracy"]["crps"] == 0.333


# ── End to end on real Laos data ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def laos():
    return load_evaluation(NC_FILE)


@pytest.mark.parametrize("audience", AUDIENCES)
def test_laos_facts_build_and_hide_locations(laos, audience):
    f = build_evaluation_facts(laos, audience)
    dumped = json.dumps(f)
    for name in laos.locations:
        assert name not in dumped


def test_laos_known_quirks_surface_as_caveats(laos):
    f = build_evaluation_facts(laos, "epidemiologist")
    assert f["outbreak_detection"]["specificity_status"] == "unknown"
    assert {"short_baseline", "no_non_outbreaks", "few_splits"} <= set(f["caveats"])

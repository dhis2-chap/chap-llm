"""Tests for the evaluation adapter.

Run from the chap-llm repo root:
    uv run pytest tests/ -v
"""

from pathlib import Path

import pandas as pd
import pytest

from chap_llm.adapter.evaluation import load_evaluation

NC_FILE = Path(__file__).parent.parent.parent / "chap-core" / "eval.nc"


@pytest.fixture(scope="module")
def result():
    return load_evaluation(NC_FILE)


@pytest.fixture(scope="module")
def metrics_csv():
    csv = Path(__file__).parent.parent.parent / "chap-core" / "metrics.csv"
    return pd.read_csv(csv).iloc[0]


# ── Test 1: global crps and mae match metrics.csv ─────────────────────────────

def test_global_crps_matches_metrics_csv(result, metrics_csv):
    assert result.global_metrics.crps == pytest.approx(
        metrics_csv["crps"], rel=1e-9
    )


def test_global_mae_matches_metrics_csv(result, metrics_csv):
    assert result.global_metrics.mae == pytest.approx(
        metrics_csv["mae"], rel=1e-9
    )


# ── Test 2: per-location crps and mae, weighted-averaged, equal global ────────

def test_per_location_crps_averages_to_global(result):
    loc_mean = sum(r.metrics.crps for r in result.per_location) / len(result.per_location)
    assert loc_mean == pytest.approx(result.global_metrics.crps, rel=1e-6)


def test_per_location_mae_averages_to_global(result):
    loc_mean = sum(r.metrics.mae for r in result.per_location) / len(result.per_location)
    assert loc_mean == pytest.approx(result.global_metrics.mae, rel=1e-6)


# ── Test 3: specificity is None when no non-outbreak periods exist ─────────────

def test_specificity_is_none_when_all_periods_are_outbreaks(result):
    """With the Laos subset (2 test periods, all 6 cells are outbreaks),
    there are no true-negatives or false-positives, so tn + fp == 0
    and specificity must be None — not 0 or any other value."""
    c = result.outbreak_metrics.counts
    assert (c.tn + c.fp) == 0, "precondition: no non-outbreak cells"
    assert result.outbreak_metrics.specificity is None


# ── Test 4: baseline_years_used == 2 for Laos data (requested 5) ──────────────

def test_baseline_years_used(result):
    """filter_to_baseline(baseline_years=5) on the Laos dataset returns only
    2010 and 2011 — data starts 2010 and last complete year before splits is 2011."""
    assert result.outbreak_metrics.alert_policy.baseline_years_used == 2

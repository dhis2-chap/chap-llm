"""Adapter: reads a chap eval .nc file and returns an EvaluationResult contract.

Imports only from chap_core — no reimplementation of metrics, thresholds or
scoring logic.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from chap_core.assessment.evaluation import Evaluation
from chap_core.assessment.flat_representations import DataDimension
from chap_core.assessment.metrics import available_metrics, calculate_metrics
from chap_core.assessment.outbreak_metrics.scoring import (
    _splits,
    binary_confusion,
    label_cells,
)
from chap_core.assessment.thresholds.params import PercentileParams
from chap_core.assessment.thresholds.percentile import filter_to_baseline
from chap_core.database.alert_tables import AlertLevel

from chap_llm.contracts.evaluation import (
    AlertPolicyInfo,
    EvaluationResult,
    HorizonResult,
    LocationResult,
    MetricSet,
    OutbreakCounts,
    OutbreakMetrics,
)

# ── default alert policy ───────────────────────────────────────────────────────
_QUANTILE: float = 0.75
_BASELINE_YEARS_REQUESTED: int = 5
_EXCEEDANCE_THRESHOLD: float = 0.5

_SCALAR_METRIC_IDS = [
    "crps",
    "crps_norm",
    "mae",
    "ratio_above_truth",
    "coverage_10_90",
    "coverage_25_75",
]

_SLICE_METRIC_IDS = [          # crps_norm excluded — not meaningful per slice
    "crps",
    "mae",
    "ratio_above_truth",
    "coverage_10_90",
    "coverage_25_75",
]


# ── helpers ────────────────────────────────────────────────────────────────────

def _metric_set_global(values: dict) -> MetricSet:
    return MetricSet(
        crps=values["crps"],
        crps_norm=values.get("crps_norm"),
        mae=values["mae"],
        ratio_above_truth=values["ratio_above_truth"],
        coverage_10_90=values["coverage_10_90"],
        coverage_25_75=values["coverage_25_75"],
    )


def _metric_set_slice(values: dict) -> MetricSet:
    return MetricSet(
        crps=values["crps"],
        crps_norm=None,
        mae=values["mae"],
        ratio_above_truth=values["ratio_above_truth"],
        coverage_10_90=values["coverage_10_90"],
        coverage_25_75=values["coverage_25_75"],
    )


def _per_location(
    obs: pd.DataFrame,
    fc: pd.DataFrame,
    historical_df: pd.DataFrame | None,
) -> list[LocationResult]:
    detailed = available_metrics["crps"](
        historical_observations=historical_df
    ).get_detailed_metric(obs, fc)
    n_per_loc = (
        detailed.dropna(subset=["metric"])
        .groupby("location")
        .size()
        .to_dict()
    )

    results = []
    for metric_id in _SLICE_METRIC_IDS:
        metric_cls = available_metrics[metric_id]
        metric_obj = metric_cls(historical_observations=historical_df)
        df = metric_obj.get_metric(obs, fc, dimensions=(DataDimension.location,))
        for _, row in df.iterrows():
            results.append((row["location"], metric_id, row["metric"]))

    loc_values: dict[str, dict] = {}
    for loc, metric_id, value in results:
        loc_values.setdefault(loc, {})[metric_id] = value

    return [
        LocationResult(
            location=loc,
            n_evaluated=n_per_loc.get(loc, 0),
            metrics=_metric_set_slice(values),
        )
        for loc, values in sorted(loc_values.items())
    ]


def _per_horizon(
    obs: pd.DataFrame,
    fc: pd.DataFrame,
    historical_df: pd.DataFrame | None,
) -> list[HorizonResult]:
    detailed = available_metrics["crps"](
        historical_observations=historical_df
    ).get_detailed_metric(obs, fc)
    n_per_hor = (
        detailed.dropna(subset=["metric"])
        .groupby("horizon_distance")
        .size()
        .to_dict()
    )

    results = []
    for metric_id in _SLICE_METRIC_IDS:
        metric_cls = available_metrics[metric_id]
        metric_obj = metric_cls(historical_observations=historical_df)
        df = metric_obj.get_metric(
            obs, fc, dimensions=(DataDimension.horizon_distance,)
        )
        for _, row in df.iterrows():
            results.append((int(row["horizon_distance"]), metric_id, row["metric"]))

    hor_values: dict[int, dict] = {}
    for hor, metric_id, value in results:
        hor_values.setdefault(hor, {})[metric_id] = value

    return [
        HorizonResult(
            horizon_distance=hor,
            n_evaluated=n_per_hor.get(hor, 0),
            metrics=_metric_set_slice(values),
        )
        for hor, values in sorted(hor_values.items())
    ]


def _baseline_years_used(
    all_obs: pd.DataFrame,
    fc: pd.DataFrame,
    baseline_years: int,
) -> int:
    splits = _splits(fc)
    min_years = baseline_years

    for split_date in splits["split"].unique():
        observed_at = all_obs["time_period"].map(
            lambda p: pd.Timestamp(str(p)[:4] + "-" + str(p)[4:] + "-01")
        )
        history = all_obs[observed_at < split_date]
        if history.empty:
            continue
        windowed = filter_to_baseline(history, baseline_years=baseline_years)
        years_used = windowed["time_period"].str[:4].nunique()
        min_years = min(min_years, years_used)

    return min_years


def _outbreak_metrics(
    all_obs: pd.DataFrame,
    fc: pd.DataFrame,
    level: AlertLevel,
    baseline_years_used: int,
) -> OutbreakMetrics:
    labelled = label_cells(all_obs, fc, levels=[level])
    from chap_core.assessment.outbreak_metrics.scoring import score

    groups = score(labelled, n_levels=1, group_by=[])
    g = groups[0]
    c = binary_confusion(labelled[labelled["level"] == 0])

    sensitivity = c.tp / (c.tp + c.fn) if (c.tp + c.fn) > 0 else None
    specificity = c.tn / (c.tn + c.fp) if (c.tn + c.fp) > 0 else None

    policy_info = AlertPolicyInfo(
        strategy="percentile",
        quantile=_QUANTILE,
        baseline_years_requested=_BASELINE_YEARS_REQUESTED,
        baseline_years_used=baseline_years_used,
        exceedance_threshold=_EXCEEDANCE_THRESHOLD,
        source="local_default",
    )

    return OutbreakMetrics(
        counts=OutbreakCounts(tp=c.tp, fp=c.fp, fn=c.fn, tn=c.tn),
        n_evaluated=g.n_cells,
        sensitivity=sensitivity,
        specificity=specificity,
        alert_policy=policy_info,
    )


# ── public API ─────────────────────────────────────────────────────────────────

def load_evaluation(nc_path: str | Path) -> EvaluationResult:
    """Read a chap eval .nc file and return an EvaluationResult contract.

    Args:
        nc_path: Path to the NetCDF evaluation file produced by ``chap eval``.

    Returns:
        EvaluationResult with global, per-location and per-horizon metrics,
        plus outbreak counts using a local-default alert policy
        (75th-percentile threshold, exceedance 0.5).
    """
    evaluation = Evaluation.from_file(Path(nc_path))
    flat = evaluation.to_flat()

    obs = pd.DataFrame(flat.observations)
    fc = pd.DataFrame(flat.forecasts)
    hist = pd.DataFrame(flat.historical_observations) if flat.historical_observations is not None else pd.DataFrame()
    historical_df = pd.concat([hist, obs], ignore_index=True) if not hist.empty else None

    import xarray as xr
    ds = xr.open_dataset(nc_path)
    attrs = ds.attrs
    ds.close()

    raw_version = attrs.get("model_version", "unknown")
    model_version = None if raw_version in ("unknown", "", None) else raw_version

    split_periods = attrs.get("split_periods", [])
    if isinstance(split_periods, str):
        import json
        split_periods = json.loads(split_periods)
    n_splits = len(split_periods)

    max_horizon = int(fc["horizon_distance"].max()) if not fc.empty else 1
    locations = sorted(obs["location"].unique().tolist())

    global_values = calculate_metrics(
        evaluation=evaluation,
        metric_ids=_SCALAR_METRIC_IDS,
    )
    global_metrics = _metric_set_global(global_values)

    per_location = _per_location(obs, fc, historical_df)
    per_horizon = _per_horizon(obs, fc, historical_df)

    all_obs = pd.concat([hist, obs], ignore_index=True) if not hist.empty else obs.copy()

    level = AlertLevel(
        name="alert",
        output_code="1",
        threshold_params=PercentileParams(
            type="percentile",
            quantile=_QUANTILE,
            baseline_years=_BASELINE_YEARS_REQUESTED,
        ),
        exceedance_threshold=_EXCEEDANCE_THRESHOLD,
    )

    baseline_yrs = _baseline_years_used(all_obs, fc, _BASELINE_YEARS_REQUESTED)
    outbreak_metrics = _outbreak_metrics(all_obs, fc, level, baseline_yrs)

    return EvaluationResult(
        model_name=attrs.get("model_name", ""),
        model_version=model_version,
        n_splits=n_splits,
        max_horizon=max_horizon,
        locations=locations,
        global_metrics=global_metrics,
        per_location=per_location,
        per_horizon=per_horizon,
        outbreak_metrics=outbreak_metrics,
    )

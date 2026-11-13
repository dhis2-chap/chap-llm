from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel

class AlertPolicyInfo(BaseModel):
    strategy: Literal["percentile"]
    quantile: float
    baseline_years_requested: int
    baseline_years_used: int        # min over all splits from filter_to_baseline()
    exceedance_threshold: float
    source: Literal["local_default"]

class OutbreakCounts(BaseModel):
    tp: int
    fp: int
    fn: int
    tn: int

class OutbreakMetrics(BaseModel):
    counts: OutbreakCounts
    n_evaluated: int
    sensitivity: Optional[float]    # None if tp + fn == 0
    specificity: Optional[float]    # None if tn + fp == 0
    alert_policy: AlertPolicyInfo

class MetricSet(BaseModel):
    crps: float
    crps_norm: Optional[float]      # None in per_location and per_horizon
    mae: float
    ratio_above_truth: float
    coverage_10_90: float
    coverage_25_75: float

class LocationResult(BaseModel):
    location: str
    n_evaluated: int
    metrics: MetricSet              # crps_norm = None

class HorizonResult(BaseModel):
    horizon_distance: int
    n_evaluated: int
    metrics: MetricSet              # crps_norm = None

class EvaluationResult(BaseModel):
    schema_version: Literal["0.1"] = "0.1"

    # metadata
    model_name: str
    model_version: Optional[str]    # None if "unknown"
    n_splits: int
    max_horizon: int
    locations: list[str]

    # metrics
    global_metrics: MetricSet
    per_location: list[LocationResult]
    per_horizon: list[HorizonResult]

    # alerts
    outbreak_metrics: OutbreakMetrics

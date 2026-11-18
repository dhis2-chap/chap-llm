# ARCHITECTURE.md

LLM-based building blocks that explain Chap ML results to different audiences.

## Design order

We define the contract before building the adapter. The contract is the stable interface the rest of the system depends on. Adapters (CLI now, REST API later) only fill it.

```mermaid
flowchart LR
    S1([1. Inspect Chap output\nmetrics.csv, .nc structure,\nchap-core functions])
    S2[/2. Design contract\nPydantic models per result type/]
    S3[3. Build adapter\nfills the contract]
    S4[4. Facts layer, prompts,\nLLM client, output check]
    S5{{5. Eval harness\ntests the pipeline}}

    S1 --> S2 --> S3 --> S4 --> S5
    S2 -.hand-made test objects.-> S4
```

## Runtime data flow

```mermaid
flowchart LR
    Input([Chap output\n.nc / API / LIME])
    B[Adapter\nreads Chap output\ncalls chap-core APIs]
    A[/Contract\nPydantic objects/]
    C[Facts layer\nclassifies in code\nfilters by audience]
    D[Prompt builder\naudience profile\n+ selected facts]
    E[LLM client\nprovider-agnostic]
    F[Output check\nnumbers match facts\nfallback on failure]
    G([ExplanationResponse\ntext + chart_data\n+ source_facts])
    H{{Eval harness\noffline: deterministic checks,\nLLM-as-judge, human calibration}}

    Input --> B --> A --> C --> D --> E --> F --> G
    H -.tests.-> C
    H -.tests.-> G
```

| Layer | Responsibility | Must NOT |
|---|---|---|
| Adapter | Read Chap output, call Chap's own code, fill the contract | Interpret results, call an LLM |
| Contract | Pydantic models: the only format the rest of the system knows | Contain prose |
| Facts layer | Turn numbers into facts in code ("underestimates", "too few outbreaks to judge") | Call an LLM |
| Prompt | Audience profile + template + selected facts | Compute anything |
| LLM client | Provider-agnostic call, structured JSON output | Be tied to one vendor |
| Output check | Verify numbers and alert status in the text match the input; fallback | |
| Eval harness | Deterministic checks → LLM-as-judge with rubric → human calibration | |

## Principles

1. **Code computes, the LLM phrases.** The LLM only receives finished facts.
2. **One contract, audience as a parameter.** Adaptation happens in the facts layer and prompt, not in separate contracts.
3. **One adapter per data source**, with one function per result type and shared helpers.
4. **Reuse chap-core.** Metrics, thresholds and scoring come from Chap's own functions.
5. **Build one vertical slice first** (evaluation end to end) before adding alerts and XAI.
6. **Honesty about uncertainty**, including uncertainty in the threshold itself.
7. **chap_llm returns JSON, frontend renders.** No PNG or HTML generated here.

## Audiences

Audience is a parameter passed by the caller — never inferred automatically.

| Value | Reader | Focus |
|---|---|---|
| `epidemiologist` | Technical — understands CRPS, sensitivity, baselines | Full metric detail, caveats, methodology |
| `district_health_officer` | Operational — acts on alerts | Whether the model can be trusted for decisions, what alerts mean |
| `decision_maker` | Strategic — allocates resources | High-level reliability, what the system does and doesn't know |

The facts layer filters which facts are included per audience. The prompt template sets tone and detail level.

## Response contract

Every LLM endpoint returns an `ExplanationResponse`:

```python
class ExplanationResponse(BaseModel):
    audience: Literal["epidemiologist", "district_health_officer", "decision_maker"]
    result_type: Literal["evaluation", "xai", "alarm"]
    explanation_text: str          # natural language, written by the LLM
    chart_data: dict | None        # structured JSON for the frontend to render
    source_facts: dict             # the facts dict passed to the LLM — for audit and output check
```

`source_facts` is the structured dict the facts layer produced and the prompt injected. It is returned alongside the text so the output check can verify that numbers in `explanation_text` match `source_facts`. It is also useful for debugging prompts.

## Sequence: evaluation explanation request

```mermaid
sequenceDiagram
    actor Caller as Caller\n(CLI / Modeling App)
    participant A as Adapter\nload_evaluation()
    participant CC as chap-core\n(calculate_metrics etc.)
    participant F as Facts layer
    participant L as LLM client
    participant OC as Output check

    Caller->>A: nc_path, audience
    A->>CC: Evaluation.from_file(), calculate_metrics(),\nlabel_cells(), binary_confusion()
    CC-->>A: raw metric values
    A-->>F: EvaluationResult (Pydantic)
    F->>F: classify metrics, filter by audience
    F-->>L: source_facts dict + prompt
    L-->>OC: explanation_text
    OC->>OC: verify numbers in text match source_facts
    OC-->>Caller: ExplanationResponse\n(text + chart_data + source_facts)
```

## Adapter

```
chap_llm/adapter/
    evaluation.py    load_evaluation(nc_path) → EvaluationResult    ✅ done
    alarm.py         load_alarm(...)           → AlarmResult         (after evaluation slice)
    xai.py           load_xai(...)             → XAIResult           (after inspecting LIME output)
```

Both a CLI adapter (reads `.nc` files) and an API adapter (reads live `AlertPolicy` from chap-core REST API) share the same contracts. API adapter is deferred until the CLI slice works end to end.

`load_evaluation()` steps: open and validate the `.nc` file → `calculate_metrics()` (global, per location, per horizon) → thresholds and alerts via `label_cells()` / `score()` with an in-memory `AlertLevel` → metadata → contract.

Chap imports used:
```python
from chap_core.assessment.evaluation import Evaluation
from chap_core.assessment.metrics import available_metrics, calculate_metrics
from chap_core.assessment.outbreak_metrics.scoring import label_cells, score, binary_confusion
from chap_core.database.alert_tables import AlertLevel
from chap_core.assessment.thresholds.params import PercentileParams
from chap_core.assessment.thresholds.percentile import filter_to_baseline
```

## How Chap defines things (verified in chap-core v2.7.0.dev0)

- `.nc` contents: `forecast` [location × time_period × horizon_distance × sample], `observed` [location × time_period], `historical_observed`
- **Outbreak** = observed cases > threshold. Threshold: 75th percentile of same month over baseline window (default).
- **Exceeds** = share of forecast samples above the threshold (a probability).
- **Alert** = exceeds ≥ `exceedance_threshold` (0.5 default).
- **Short baseline:** `filter_to_baseline()` uses whatever years are available; silently truncates.
- **`ratio_above_truth`** = share of samples above the observed value. 0.5 = unbiased.
- **`crps_norm`** = CRPS / (max − min) of all observed values in the dataset. Not comparable per location.
- `metrics.csv` from `chap export-metrics` aggregates all locations and horizons; not used by the adapter.

## Decisions

| Decision | Reason |
|---|---|
| Build against chap-core v2.7.0.dev0 (editable install) | Code read = code run |
| Do not use `outbreak_detection.py` (mean + 2×std) | Removed from dev; current Chap uses `AlertPolicy` |
| Alerts use `local_default` policy (percentile 75, baseline 5 years, exceedance 0.5) | No DB/API yet; recorded explicitly in the contract via `AlertPolicyInfo.source` |
| Adapter reads `.nc`, not `metrics.csv` | The CSV loses per-location and per-horizon detail |
| Contract includes `n_outbreaks`, `n_alerts`, `n_evaluated` | Rates on few events are misleading without counts |
| `baseline_years_used` computed from actual data, not header | Header `historical_context_periods` overstates the data available |
| XAI contract designed only after inspecting LIME output | Avoid designing for an unseen format |
| Provider-agnostic LLM client | Chap runs locally in countries; data sovereignty and cost |
| `source_facts` returned in every response | Enables output check and prompt debugging without re-running |
| chap_llm returns JSON, frontend renders | Separation of concerns; Modeling App uses Highcharts |
| Local LLM or Claude API with anonymized data only | Data sovereignty — no raw case data or identifiable locations to external API |

## Privacy — what is sent to an external LLM

**Rule: nothing identifiable or raw leaves the system when using an external LLM provider.**

The facts layer is the privacy boundary. Everything passed to the LLM client must already be anonymized and aggregated. The LLM client itself does no anonymization — it only sends what the facts layer gives it.

### What must be anonymized before the LLM call

| Data type | Raw form | Anonymized form |
|---|---|---|
| Location names | "Vientiane", "Attapeu" | "District A", "District B" (or omitted) |
| Model name | "chap_ewars_v2" | can be kept — not health data |
| Case counts | 142 cases | never sent — only derived metrics |
| Metric values | CRPS=0.45, MAE=12.3 | kept as-is — aggregated, not individual |
| Sensitivity/specificity | 0.80 / None | kept — no individual records |
| Baseline years | 2010–2011 | kept — calendar metadata only |
| Split dates | "2012-11-01" | kept — temporal metadata only |
| Alert counts | tp=4, fp=1 | kept — aggregated counts |

### Two deployment modes

```
Mode A — fully local (strict)
  facts layer → Ollama/Mistral on the same server
  Nothing leaves the country. Works offline.
  No anonymization needed — model runs locally.

Mode B — external with anonymization (pragmatic)
  facts layer → anonymizer → Claude API (or other)
  Location names replaced. Raw counts never included.
  Only aggregated, classified metrics are sent.
```

The caller sets the mode via the LLM client configuration. The facts layer output is identical in both modes — the anonymizer is a thin wrapper applied only in Mode B before the prompt is built.

### What the prompt MAY contain (Mode B)

- Metric values: CRPS, MAE, ratio_above_truth, coverage, sensitivity, specificity
- Qualitative classifications: "moderate accuracy", "low sensitivity"
- Counts: n_splits, n_evaluated, tp, fp, fn, tn
- Temporal metadata: n years of baseline, max horizon
- Anonymized location placeholders if per-location breakdown is included
- Audience identifier

### What the prompt must NEVER contain (Mode B)

- Real location names or district identifiers
- Raw case counts (individual or aggregate)
- Patient-level or individual-level data of any kind
- Model training data

## Keeping up with chap-core changes

Three kinds of change can happen in chap-core, and each requires a different response.

### Type 1 — Format change (file structure, variable names, API)

Only the adapter is affected. The contract, facts layer, prompts and eval harness notice nothing.

**How we handle it:** the adapter is the only place that imports from chap-core. Update the adapter, re-run tests. Everything else stays the same.

**Example already seen:** between v2.5.1 and v2.7.0, outbreak metrics were removed from the CLI. Only the adapter needed updating.

### Type 2 — Meaning change (how metrics or "outbreak" is defined)

This is dangerous because it can pass silently. The adapter still fills the contract, but the numbers mean something different and explanations become wrong without anything crashing.

**How we protect against it:**

1. **Use chap-core's own functions** (`calculate_metrics()`, `score()`, `label_cells()`) instead of reimplementing. When Chap changes its definition, we follow automatically.
2. **Include metadata in the contract.** `EvaluationResult` carries `schema_version`, `model_version`, and `AlertPolicyInfo` (strategy, quantile, baseline years, exceedance threshold). Every explanation states what it is built on.
3. **Contract tests against real output (golden files).** If numbers change after a chap-core update, the test fails immediately. See `tests/test_evaluation_adapter.py` — it compares against `chap-core/metrics.csv`.
4. **Pin the chap-core version and upgrade deliberately.** `pyproject.toml` uses an editable install from the clone. Upgrading the clone is a conscious act, not an accident.

### Type 3 — New result types or new audience needs

A normal evolution, not a breaking change.

**How we handle it:** add new fields as `Optional` in the contract. Old code continues to work. New code can use the new fields. Never remove or rename existing fields without a version bump in `schema_version`.

## Known limitations

- Laos example data has only ~3 years of history; thresholds are unstable.
- `specificity` can be `None` (no non-outbreak periods in test window). Never explain as "no false alarms".
- `crps_norm` is not comparable between locations in the same dataset.
- Backtests explain past performance; real alerts come from `chap predict` or the API.
- Threshold strategy changes conclusions significantly — explanations must always state the strategy used.

## Open questions

See `QUESTIONS.md` (gitignored, local) for the full list. Key open items:

1. Exact Highcharts JSON schema the Modeling App frontend expects for `chart_data`.
2. REST API or CLI or both as the delivery mechanism for chap_llm.
3. Which fields count as "identifying" for the privacy/anonymization rule?
4. LIME: should chap_llm call `explain_lime()` itself, or consume pre-computed output?

## Status

- [x] chap-core v2.7.0.dev0 installed from clone; example evaluation run
- [x] `load_evaluation()` — global, per-location, per-horizon metrics, alert data, metadata
- [x] Tests: global metrics match `metrics.csv`; per-location averages match global; `specificity=None` case; short-baseline flag
- [ ] Facts layer for evaluation (all three audiences)
- [ ] Prompt templates (all three audiences)
- [ ] Provider-agnostic LLM client
- [ ] `ExplanationResponse` contract + output check
- [ ] Eval harness (deterministic → LLM-as-judge → human calibration)
- [ ] `load_alarm()` + alarm facts + alarm prompt
- [ ] Run `chap explain-lime`, design XAI contract, `load_xai()`

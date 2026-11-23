# chap-llm

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

AI-driven natural language explanations of [Chap](https://chap.dhis2.org) model results for epidemiologists, district health managers, and decision-makers.

Part of the [Chap modeling platform](https://github.com/dhis2-chap/chap-core). Tracked under [CLIM-1880](https://dhis2.atlassian.net/browse/CLIM-1880).

## What it does

`chap-llm` sits between chap-core and the Modeling App frontend:

1. **Reads** evaluation results from chap-core (`.nc` backtest files)
2. **Classifies** metrics in code — accuracy, calibration, outbreak detection
3. **Anonymizes** location names before any external call
4. **Generates** a natural language explanation via a provider-agnostic LLM client
5. **Returns** structured JSON — explanation text + chart data for the frontend to render

All numbers are classified in code before the LLM call. The LLM only phrases finished facts, never interprets raw data.

## Pipeline

```
Input (.nc file)
    → Adapter          reads chap-core output
    → Contract         Pydantic models (stable interface)
    → Facts layer      classifies metrics in code, anonymizes locations
    → Prompt builder   injects facts + audience into template
    → LLM client       provider-agnostic: local LLM or Claude API
    → Output check     verifies numbers in text match source_facts
    → ExplanationResponse (explanation_text + chart_data + source_facts)
```

## Three audiences

Audience is a parameter — never inferred automatically.

| Value | Reader | Gets |
|---|---|---|
| `epidemiologist` | Technical — understands CRPS, sensitivity | Full metric detail, caveats, methodology |
| `district_health_manager` | Operational — acts on alerts | Whether the model can be trusted, what alerts mean |
| `decision_maker` | Strategic — allocates resources | High-level reliability, what the system does and doesn't know |

## Privacy

The facts layer is the privacy boundary. Nothing identifiable is sent to an external LLM — only anonymized, aggregated metrics. Location names are always replaced with neutral placeholders ("District A", "District B", ...).

Two deployment modes:
- **Local LLM** (on-premise) — nothing leaves the country
- **Claude API** — only anonymized, aggregated metrics sent; no raw case counts, no location names

## Status

| Component | Status |
|---|---|
| Adapter (`load_evaluation`) | ✅ Done |
| Contract (Pydantic models) | ✅ Done |
| Facts layer + anonymization | ✅ Done |
| Prompt builder | 🔜 Next |
| LLM client (provider-agnostic) | 🔜 Next |
| Output check | 🔜 Next |
| Eval harness | 🔜 Next |

## Development

Requires Python ≥ 3.13 and [uv](https://docs.astral.sh/uv/).

```bash
# Clone with chap-core as a sibling directory
git clone https://github.com/dhis2-chap/chap-llm
git clone https://github.com/dhis2-chap/chap-core

# Install dependencies
cd chap-llm
uv sync

# Run tests
uv run pytest tests/ -v
```

## Issues

File bug reports and feature requests at [dhis2-chap/chap-llm/issues](https://github.com/dhis2-chap/chap-llm/issues) or in Jira under [CLIM-1880](https://dhis2.atlassian.net/browse/CLIM-1880).

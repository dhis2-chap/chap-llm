# chap-llm

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)

LLM-based building blocks that explain [Chap](https://chap.dhis2.org/) model results to different audiences — epidemiologists, district health officers, and decision makers.

## What it does

Chap produces ML model evaluations, explainability results (LIME), and alarm events. `chap-llm` takes those outputs and generates natural-language explanations tailored to the reader's role and knowledge level.

**Pipeline:**

```
Chap output → Adapter → Contract → Facts layer → Prompt → LLM → Output check
```

The facts layer classifies all numbers in code before anything reaches the LLM. The LLM only phrases — it never interprets raw numbers.

## Audiences

| Value | Reader | Gets |
|---|---|---|
| `epidemiologist` | Technical — knows CRPS, sensitivity, baselines | Full metric detail, caveats, methodology |
| `district_health_officer` | Operational — acts on alerts | Operational summary, counts, alert context |
| `decision_maker` | Strategic — allocates resources | High-level reliability, what the model does and doesn't know |

## Privacy

The facts layer is the privacy boundary. Location names are replaced with neutral placeholders (`District A`, `District B`, …) before any data leaves the system. Raw case counts and individual-level data are never sent to an external LLM.

## Development

Requires [uv](https://docs.astral.sh/uv/) and a local clone of [chap-core](https://github.com/dhis2-chap/chap-core) at `../chap-core`.

```bash
uv sync --extra dev
uv run pytest tests/ -v
```

## Contributing

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for design decisions and pipeline details.

Use the PR template in `.github/PULL_REQUEST_TEMPLATE.md` when opening a pull request.

Issues: [https://github.com/dhis2-chap/chap-llm/issues](https://github.com/dhis2-chap/chap-llm/issues)

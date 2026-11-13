# CLAUDE.md

Les `ARCHITECTURE.md` før du foreslår design eller skriver kode.
Sjekk `FINDINGS.md` (gitignored, lokal) for funn fra tidligere økter.

## Ikke-forhandlingsbare regler

- **Ikke endre chap-core.** Kun lesing og import.
- **Gjenbruk chap-core.** Metrikker, terskler og scoring reimplementeres ikke.
- **Koden regner, LLM-en formulerer.** Alle tall og klassifiseringer gjøres i kode (facts-laget) før LLM-kallet.
- **Ingen leverandørbinding.** LLM-klienten støtter lokal LLM og ekstern API — ikke lås til én.
- **Privacy.** Send aldri rå case-tall eller lokasjonsnavn til ekstern LLM. Kun pre-aggregerte metrikker.
- **Test før du går videre.** Ny kode → pytest-tester → grønt → neste steg.
- **Visualisering.** `chap_llm` returnerer JSON. Frontend renderer. Ingen PNG/HTML her.

## Konvensjoner

- Python ≥ 3.13, Pydantic v2, pytest, uv
- `Optional` for felt som kan mangle — aldri `0` eller tom streng som fravær
- Pipeline-rekkefølge: `adapter → contract → facts → prompt → LLM → check → eval`

## Jira og PR

- Se `.claude/commands/jira.md` for prosjekt, komponenter og labels.
- PR reviewer: Knut Rand. Følg chap-core sin PR-mal (Summary / Review needed / Test plan).

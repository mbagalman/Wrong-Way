# Wrong-Way Developer Guide

## Prerequisites
- Python 3.12+

## Environment
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Local run
```bash
streamlit run app.py
```

## Debugging and deterministic runs
- The simulation uses `SimulationConfig.seed` for deterministic behavior.
- Use fixed seeds for reproducible bug reports.
- To debug one run quickly:
```bash
python main.py        # repo-root shim
wrong-way-cli         # installed console script (after pip install -e .)
```
Both invoke `wrong_way.cli.main` — they print the same seven-line summary.

## Test commands
```bash
pytest
ruff check .
```

## Core interfaces
- `SimulationConfig`
- `ObserverConfig`
- `Event`
- `RunResult`
- `BatchSummary`

These are defined in `src/wrong_way/config.py` and are treated as the shared contract across simulation, analytics, UI, and tests.

## Design rationale
For the original creative brief — motivation, mode design, metric definitions, tone — see [`DESIGN_NOTES.md`](DESIGN_NOTES.md).

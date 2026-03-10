# Wrong-Way

**The Other Elevator Always Wins** is a small teaching simulator that makes students feel elevator frustration first, then explains it with statistics.

## What it demonstrates
- Inspection paradox and long-gap exposure
- Directional asymmetry in elevator flow
- Perception inflation: actual wait vs perceived wait

## Quick start

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
streamlit run app.py
```

## One-command setup + launch (macOS/Linux)

```bash
python3.12 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]" && streamlit run app.py
```

## Run tests

```bash
source .venv/bin/activate
pytest
```

## Project layout
- `src/wrong_way/simulation_core.py` event queue clock
- `src/wrong_way/elevator_mode.py` elevator simulation and wrong-way logic
- `src/wrong_way/metrics.py` perceived wait / rage / belief metrics
- `src/wrong_way/analytics.py` batch statistics and heatmap data
- `src/wrong_way/ui_streamlit.py` classroom-facing app
- `tests/` unit and integration coverage

## Notes
- Elevator Mode is MVP.
- Subway Mode is planned in V2.
- Use fixed seeds for reproducibility in demos and tests.

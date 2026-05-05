# Contributing

1. Create and activate a Python 3.12+ virtual environment (CI tests against 3.12 and 3.13).
2. Install dependencies:
```bash
pip install -e ".[dev]"
```
3. Run checks before opening a PR:
```bash
ruff check .
pytest
```
4. For reproducible bug reports, include your simulation seed and profile.

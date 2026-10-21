# Contributing

Install Python 3.11–3.13 and run:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test,web,web-test]' build
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q
```

Core physics belongs in `spinfreq/`; reproducible application configuration and
calculations belong in `config.py` and `jobs.py`. CLI and web adapters must call
that shared runner. Keep HTTP/worker dependencies optional for package users.
Use SI quantities in saved configurations and label presentation conversions.

Independent scientific checks live in `benchmarks/`; reference inputs, provenance,
plots and accepted results live in `validation/`. Keep published benchmark paths
stable: scripts share imports and reports contain reproduction commands. Store
exploratory runs, downloaded runtimes and build outputs under ignored `results/`,
`build/` or `dist/`. Do not replace reference results with new output silently.

Changes to a physical operator require an analytical or independent-solver
comparison, residual checks and an explanation of the affected validation scope.
Tests must cover numerical failures as well as successful calculations. New
web lifecycle behavior requires real subprocess tests; use `scripts/browser_smoke.py`
for UI/worker/download checks. Run `python -m build` before proposing a release.

The [release plan](docs/releases/RELEASE_PLAN.md) records gates and remaining blockers.
Original project code is MIT licensed. External reference data retain their
upstream terms and attribution; see [data provenance](docs/science/DATA_PROVENANCE.md).

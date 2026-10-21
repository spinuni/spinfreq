# Downloads and installation

Current source candidate: **0.1.0rc2**, Python 3.11–3.13, MIT license. A stable 0.1.0 release, PyPI package and native application installers have **not** been published. Source installation is the available distribution route. No GPU or MuMax3 installation is required for the CPU solver.

## Get the source

[Download the main-branch source ZIP](https://github.com/spinuni/spinfreq/archive/refs/heads/main.zip) or clone with Git:

```bash
git clone https://github.com/spinuni/spinfreq.git
cd spinfreq
git rev-parse HEAD
```

The ZIP and branch are moving development snapshots, not immutable release artifacts. Save the revision for reproducibility. Review the [changelog](https://github.com/spinuni/spinfreq/blob/main/CHANGELOG.md) and [license](https://github.com/spinuni/spinfreq/blob/main/LICENSE).

## Install the package or application

Create a virtual environment with `python -m venv .venv`. On Linux/WSL2/macOS use:

```bash
.venv/bin/python -m pip install -e '.[web]'
.venv/bin/spinfreq-web
```

On Windows PowerShell use:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[web]'
.\.venv\Scripts\spinfreq-web.exe
```

For only the numerical Python package and CLI, omit `[web]`. Install `.[test]` for physics tests, or `.[test,web,web-test]` for HTTP/browser checks. The [manual](manual.html) walks through a first simulation.

| Platform | Documentation and web preview | Protected web computation |
| --- | --- | --- |
| Linux / WSL2 | Available | Enabled by default |
| Native Windows | Available | Experimental `--mode compute`; native qualification pending |
| macOS | Available; local execution not yet verified here | Not implemented |

Direct Python/CLI computations do not use the protected web supervisor. Platform availability of dependencies and memory remain relevant. Preview can export inputs for a Linux/WSL2 machine.

## Example inputs

These files use the same schema as the application and can be downloaded without a running simulation worker:

- [prism-fmr.json](downloads/prism-fmr.json): fast single-cell susceptibility.
- [periodic-fmr.json](downloads/periodic-fmr.json): periodic uniform-film FMR.
- [confined-skyrmion.json](downloads/confined-skyrmion.json): coarse 2 nm matched-reference example; refine before quoting continuum frequencies.

## Build distributions and an offline website

From a source checkout:

```bash
python -m pip install build '.[docs]'
python -m build
python scripts/build_site.py --export results/site
```

`dist/` receives a wheel and source archive. These locally built files are not signed or published release assets. The site export contains the homepage, handbook, assets and example inputs; it can be hosted on a static server or browsed offline. It contains no simulation backend. Its simulator link opens a separately launched local service.

Before publishing: review native Windows evidence, supported-platform checks and scientific scope, then publish immutable artifacts with versioned provenance. See the [release plan](https://github.com/spinuni/spinfreq/blob/main/docs/releases/RELEASE_PLAN.md). Public hosting and release publication remain separate from installing this local application.

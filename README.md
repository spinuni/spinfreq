<p align="center"><img src="spinfreq/web/static/spinfreq-logo.png" width="180" alt="SpinFreq provisional logo"></p>

# SpinFreq

Frequency-domain micromagnetics for thin films: magnetic equilibria, linear
resonances and weak-field response. A Python research package with a local web
interface. Current candidate: **0.1.0rc2**, MIT licensed.

## 1. Start here

| Goal | Read next |
| --- | --- |
| Browse the complete handbook | Run `spinfreq-web`: Manual · Theory · API · Downloads · Validation |
| Install and launch on Windows, Linux or macOS | [Quick start](docs/getting-started/README.md) |
| Use the browser interface | [Web guide](docs/guides/WEB.md) |
| Run a reproducible example | [Example configurations](examples/README.md) |
| Use the Python API and advanced workflows | [User guide](docs/guides/USAGE.md) |

```bash
python -m pip install -e '.[web]'
spinfreq-web
```

Open **http://127.0.0.1:8000**. On Linux/WSL2, the workbench can run bounded
simulations using that machine's CPU and RAM. On native Windows/macOS, it opens
as a landing page and configuration preview: explore presets, edit parameters,
validate and download SI JSON. Windows also offers experimental native computation with `--mode compute`,
using Job Objects; native CI qualification remains pending. macOS workers are
not implemented. Use `--mode landing` to preview on any platform.

## 2. Understand the science

- [Physics and solver reference](docs/reference/PHYSICS.md): models, equations,
  units, limitations and research workflows.
- [Validation evidence](validation/README.md): analytical, FMR, DMI, skyrmion and
  driven-response comparisons, with native data and plots.
- [Scientific assessment](docs/science/VALIDATION_AND_RELEASE.md): what the
  evidence establishes and what remains open.

All models use one magnetization vector through thickness. The web workflow is
linear and dense, limited to small problems. Mesh convergence is required;
nonlinear combs and thickness-dependent modes are not validated by this workflow.

## 3. Develop and release

- [Architecture](docs/development/ARCHITECTURE.md) and [contributing](CONTRIBUTING.md).
- [Release milestones](docs/releases/RELEASE_PLAN.md) and [changelog](CHANGELOG.md).
- [Benchmark scripts](benchmarks/README.md), [citation](CITATION.cff) and
  [data provenance](docs/science/DATA_PROVENANCE.md).
- [Provisional visual identity](docs/branding/README.md).

```text
spinfreq/      Numerical library, shared job API, CLI and web
examples/      Runnable SI input configurations
docs/         Getting started → guides → science/reference → development/releases
benchmarks/    Independent scientific comparison scripts
validation/    Accepted evidence, grouped by validation family
scripts/       Application and release checks
tests/         Physics, configuration and lifecycle regressions
```

`results/`, `build/` and `dist/` contain ignored local runs and build outputs.
Start from the [documentation map](docs/README.md) for the complete reading order.
Package publication and public web hosting remain separate release milestones.

The [website and handbook sources](docs/handbook/README.md) can also be exported
as a self-contained static site with `python scripts/build_site.py --export results/site`
after installing `.[docs]`. This export documents the simulator; computations
use the separately running local application.

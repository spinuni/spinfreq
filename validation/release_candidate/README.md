# 0.1.0rc1 application qualification

This report qualifies the small application examples and delivery path. It does
not expand the physical thickness/mesh envelope established by the independent
[scientific reports](../README.md). Package publication, a release tag and public
hosting remain separate [milestones](../../docs/releases/RELEASE_PLAN.md).

## Examples and measured resources

`presets.json` records three independent installed-CLI executions from temporary
working directories, using one BLAS/OpenMP thread. Python 3.12.14, NumPy 2.4.4,
SciPy 1.17.1 and Matplotlib 3.10.8 were used on this cloud CPU.

| Example | Calculation wall time | Process peak RSS | Frequency comparison |
| --- | --- | --- | --- |
| Periodic FMR | 0.599 s | 101.6 MiB | Uniform analytical pole, relative error <2e−16 |
| Single-cell prism | 0.503 s | 94.7 MiB | Elliptical Gilbert analytical pole, relative error <2e−16 |
| Confined skyrmion | 2.411 s | 155.5 MiB | Three independent OOMMF poles, worst relative error 0.0181% |

Wall time covers `run_job`, excluding interpreter/import startup. Process CPU
time and peak RSS include startup. Measurements are single runs on this host;
they are not a public-server throughput guarantee. The acceptance bounds are
120 s wall time and 1 GiB measured RSS. Web worker virtual address space has a
separate 2 GiB cap. Preset frequency targets are 1e−10 relative for analytical
FMR and 0.2% for the matched coarse-grid OOMMF poles. All gates pass.

The skyrmion example is **2 nm**, not the separately qualified 1 nm mesh. The
first three coarse/fine poles differ measurably, as documented in the mesh study.
This comparison checks correct application wiring for the matched discrete
problem. It does not turn that example into a continuum-converged prediction.

## Browser and lifecycle

`browser.json` records a real system Chromium run through the interface:
select prism, edit sampling, submit, wait for its subprocess, load three images
and download/inspect `results.zip`. There are no JavaScript errors and no mobile
horizontal overflow at 390 px. [Desktop](desktop.png) and [mobile](mobile.png)
screenshots are retained. The downloaded config hash matches the measured job.

The automated suite contains **105 passing tests** with web extras. New tests
exercise strict configuration parsing, analytical job frequencies, artifact
hashes, failed-equilibrium/large-amplitude rejection, real worker isolation,
queue/retention limits, cancellation, timeout, disk exhaustion, exclusive storage
ownership, server-crash parent-death handling and restart recovery. Browser smoke
is additional to that unit/integration count.

Wheel/sdist checks install the wheel with extras in an independent environment,
run the suite from outside both checkout and unpacked sdist with importlib test
loading, execute the installed CLI and serve installed web assets. This prevents
the source checkout from hiding missing wheel files. The package supports Python
3.11–3.13 in CI; the local checks use 3.12. Hosted CI has not been inferred from
local outcomes. The GitHub Actions API is inaccessible from this workspace, so
its results must be reviewed on GitHub before a release tag/publication.

## Reproduce

```bash
python -m pip install -e '.[test,web,web-test]' build
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q
python scripts/validate_presets.py --output results/release-presets
spinfreq-web --data-dir results/web-check --port 8000
# Another shell; use an installed Chromium or Playwright's downloaded browser:
python scripts/browser_smoke.py --output results/browser-check
python -m build
```

Use fresh output directories. Runtime arrays and downloaded ZIPs are kept in
ignored `results/`; accepted numerical measurements and screenshots are retained
here. M6 publication and M7 public-service operations remain pending.

## Hierarchy and platform-preview update

The repository now uses a four-level documentation map and groups the original
analytical data under `validation/analytical/`. Existing numerical data are
retained byte-for-byte. The homepage includes the provisional SpinFreq logo.
The [preview report](preview/README.md) records browser validation without a Linux
worker. Seven portable test cases verify capability selection, native-compatible
imports, configuration validation/export and refusal to start simulation jobs in
preview. Native Windows CI is configured; its hosted outcome is not claimed.

## rc2 runtime continuation

The rc1 application measurements above remain historical evidence. Candidate
`0.1.0rc2` separates platform runtimes and adds experimental native Windows
Job Objects. Its [runtime ledger](windows/README.md) records Linux regression
and browser evidence and the still-open native Windows qualification gate.

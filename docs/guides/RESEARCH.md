# Local research workflows

SpinFreq is a Python/CLI scientific tool. A web server is optional. The first
research workflow targets deterministic single-layer equilibria and linear
spectra, with the same energy and LLG operators used in the independent
validation suite. New studies need physical and numerical convergence checks.

## Run an experiment from a file

Install from a checkout with `python -m pip install -e .`. The package provides
`spinfreq` for one job and `spinfreq-study` for a parameter study. All JSON
quantities are SI. Set `OPENBLAS_NUM_THREADS=1` and `OMP_NUM_THREADS=1` before
launching small dense problems to avoid BLAS thread overhead.

```bash
spinfreq-study --config examples/studies/fmr-field-sweep.json --dry-run
spinfreq-study --config examples/studies/fmr-field-sweep.json --output results/field-sweep
spinfreq-study --config examples/studies/fmr-damping-sweep.json --output results/damping-sweep
```

The first example follows six bias fields from 50 to 300 mT; the second changes
Gilbert damping. They use a one-cell periodic uniform film, deliberately simple
enough for independent analytical frequency, linewidth and complex-response
checks. They do not validate device geometries. Use a fresh output directory.

## Define a study in Python

```python
from dataclasses import replace
from spinfreq import StudyConfig, run_study
from spinfreq.config import presets

base = replace(presets()["confined-skyrmion"], points=101)
experiment = StudyConfig(base, {"field_T.2": [0.0, 0.025, 0.05]},
                         continuation=True)
report = run_study(experiment, "results/skyrmion-bias")
print(report["status"])
```

This is an edited research configuration, not an automatically qualified field
range. A skyrmion can collapse or become unstable; inspect every equilibrium.
The 2 nm preset needs spatial refinement before continuum frequencies are quoted.

The JSON equivalent has `schema_version: 1`, a full `base` JobConfig, an `axes`
object, and boolean `continuation`. For example, the axes object can contain
`"field_T.2": [0.0, 0.025, 0.05]` or `"material.D": [0.002, 0.003]`.
Nested numeric paths select material fields or Cartesian vector components:
`.0 = x`, `.1 = y`, `.2 = z`. Geometry and sweep scalar fields such as `nx`,
`dx_m` and `points` can also vary in independent studies. Unknown paths,
nonfinite inputs and any invalid expanded case are rejected before execution.
There is a limit of 1024 sequential cases; this bounds study count, not RAM.
Use `--dry-run` to validate and inspect the full parameter order without running
calculations or creating output. `spinfreq --version` and `spinfreq-study --version`
print the installed package version.

## Independent cases and continuation

With `continuation=False`, every case starts from the base configuration's
seed. Multiple axes form a Cartesian product in alphabetical parameter-name
order, with the last axis varying fastest. Supplied value order is retained.
A failed case is recorded while the remaining independent cases continue.

With `continuation=True`, exactly one field or material axis is allowed; the
mesh stays fixed. The first case uses the configured seed. Every subsequent
case starts from the preceding case's saved equilibrium, then relaxes again
at the new parameters. The scan stops on failure and retains later cases as
pending. It does not jump over the failure or silently reseed.

Order is physical: up and down scans can follow different local states. Values
may repeat, for example `[0.0, 0.025, 0.05, 0.025, 0.0]`. This supports a path
through parameter space, but does not prove ground states or switching fields.
Spectral continuation rejects unstable/sign-uncertain states, so it is not a
general hysteresis-loop or switching solver. The study runner exports frequency ranks; optional [mode tracking](MODE_TRACKING.md)
compares spatial patterns with explicit uncertainty flags. It does not identify
magnetic phases.

## Inspect and reproduce results

```text
study.json                     Input, numerical implementation, cases and attempts
cases.csv                      Parameters, status, poles, torque, energy, topology and mean m
poles.csv                      All positive poles, decay rates and linewidth estimates
spectra.png / spectra.pdf      Sampled absorption curves, one per successful case
cases/0000/attempt-0000/        Full reproducible single-job artifacts
```

`frequency_rank` is a sorted frequency index at each case, **not** a tracked
mode identity. The pole linewidth `−Re(λ)/π` in Hz is the isolated weakly damped
power-peak estimate; overlapping resonances require full-response fits. Each
case includes complex spatial modes and response arrays for deeper analysis.
Mean magnetization is dimensionless. CSV parameter columns use SI units.
No failed case contributes spectral rows or curves.

Every job now saves `initial.npy`, including built-in seeds. The summary records
its SHA-256 and whether it came from a supplied state. The job manifest and ZIP
include it, making the initial magnetic condition explicit rather than inferred
from a seed label.

## Resume without mixing results

```bash
spinfreq-study --config examples/studies/fmr-field-sweep.json --output results/field-sweep --resume
```

Resume requires the same study, numerical source hashes, Python, NumPy, SciPy
and package version. It verifies every artifact of completed cases, including
the archive, before reusing them. Changed input, code or a modified result file
causes refusal; choose a new directory to compare implementations.

Failed and interrupted attempts are kept. A retry uses a new attempt directory,
and continuation restarts from the last verified predecessor. This does not
extend library cell limits or guarantee a previously failed physical state will
succeed. Numerical failures produce a nonzero CLI exit status. Aggregated tables
are regenerated from committed case records, so incomplete runs can be resumed.

An exclusive `.study.lock` prevents concurrent writers. Normal exit and Ctrl+C
release it. After a hard kill or machine failure, first verify that no process
is writing, then remove that lock manually before resuming. Do not edit the
ledger to force reuse of incompatible results. Checksums detect accidental
modification; they are not signatures authenticating an untrusted dataset.

## Start from an existing texture

```bash
spinfreq --config my-film.json --initial-state previous/equilibrium.npy --output results/restarted
spinfreq --config my-film.json --initial-state previous/equilibrium.ovf --output results/restarted-ovf
```

```python
from spinfreq import JobConfig, load_initial_state, run_job

config = JobConfig.load("my-film.json")
m = load_initial_state("previous/equilibrium.ovf", config)
result = run_job(config, "results/restarted-python", initial_m=m)
```

NPY must contain finite real unit vectors with shape `(ny, nx, 3)`; it carries
no cell dimensions, so the user must match them. OVF2 additionally checks the
cell spacings, thickness and metre mesh unit. OVF magnetization in A/m is not
silently converted to unit vectors. Regrid/normalize explicitly with a documented
procedure if needed. The supplied texture overrides the configured seed but
still undergoes relaxation and all spectral checks. It is an initial condition,
not a frozen equilibrium or automatic claim of a validated preset. The browser
workflow does not currently upload initial states or run studies.

## Research acceptance checklist

At fixed device dimensions refine the mesh; do not change cell size alone and
call that a convergence study. Track texture/topology and inspect spatial modes,
not just the lowest frequency. Refine frequency spacing near narrow poles and
compare drive/observation symmetry. Tighten static and linear residuals, test
weak-drive scaling and retain the exact field/material scan order. Compare an
independent temporal solver with matching boundary conditions and discretization.
For a changed model, repeat the relevant standard problems before a device study.

See the [research roadmap](../development/RESEARCH_ROADMAP.md) for physical and
numerical capabilities still needed for broader spintronics applications.

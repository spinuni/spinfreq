# Runnable SI configurations

**New to SpinFreq? Run `spinfreq-demo` first.** It explains the calculation and
opens a single-cell spectrum. Follow the [first-result tutorial](../docs/getting-started/README.md)
for platform-specific installation and help interpreting plots.

**Installed from a wheel? No checkout is needed for the examples.** Run
`spinfreq-examples --list` and choose a template:

```bash
spinfreq-examples --name localized-source --output my-experiment
```

Open `my-experiment/README.md`, edit its configuration and use the printed
check/run commands. `run.py --check` validates without calculating. Projects
find their inputs independently of the terminal's current directory, and the
default result folder is inside the project. Existing projects/results are
preserved. Study templates create `study.json`; other templates create
`configuration.json`. The same eight recipes below are bundled with the wheel.

Then choose a small uniform film, a confined skyrmion, a spatial source/detector,
or a parameter study below. Commands run from the repository root; use
`.venv/bin/` or `.\.venv\Scripts\` executable paths if the environment is not active.

| File | Purpose | Scope |
| --- | --- | --- |
| `periodic-fmr.json` | Uniform periodic film, weak x drive | Uniform mode checked analytically; no finite edges |
| `prism-fmr.json` | Elliptical single-cell prism response | Analytic damped Gilbert susceptibility, not spatially resolved film modes |
| `confined-skyrmion.json` | 40 × 40 × 1 nm square, 2 nm cells, bond DMI | Matched independent OOMMF model; coarse grid requires refinement for continuum values |

```bash
spinfreq --config examples/prism-fmr.json --output results/prism
spinfreq --preset confined-skyrmion --write-config my-skyrmion.json
# Edit SI quantities in my-skyrmion.json, then:
spinfreq --config my-skyrmion.json --output results/my-skyrmion
```

Outputs must use an empty directory. Configurations have `schema_version: 1`;
unknown properties, duplicate JSON keys, nonfinite values and unsupported model
settings fail explicitly. `model` is `periodic` or `confined`; the latter selects
`bond` or `mumax` DMI edges. The web queue applies stricter computation bounds than
the core dense solvers. Edited inputs are research configurations; check their
equilibrium, stability, amplitude and mesh convergence.

## Spatial spectroscopy

- [Localized source and detector](spectroscopy/localized-source.json): Gaussian field and source/detector/mean probes.
- [Wavevector-selective measurement](spectroscopy/wavevector-probe.json): circularly polarized plane-wave drive and matching/opposite/mean probes.

```bash
spinfreq --config examples/spectroscopy/localized-source.json --output results/localized
```

See [profile coordinates, phase and normalization](../docs/guides/SPECTROSCOPY.md).

After the simulation, compare x/y/z source polarizations without relaxing again:

```bash
spinfreq-susceptibility --job results/localized --output results/localized-tensor
```

Open `results/localized-tensor/susceptibility.png`. The
[tensor tutorial](../docs/guides/SUSCEPTIBILITY.md) explains CSV/NPZ outputs,
modal coupling and the equivalent Windows commands.

## Local parameter studies

- [FMR field scan](studies/fmr-field-sweep.json): six fields with equilibrium continuation.
- [FMR damping scan](studies/fmr-damping-sweep.json): three independent damping values.
- [Skyrmion field path](studies/skyrmion-field-path.json): 0 → 25 → 50 mT with continuation on the coarse matched 2 nm model.

```bash
spinfreq-study --config examples/studies/fmr-field-sweep.json --output results/field-sweep
```

Study files use a separate schema with `base`, `axes` and `continuation`; do not
pass them to `spinfreq --config`. See the [research guide](../docs/guides/RESEARCH.md).

After a fixed-mesh one-axis scan, compare spatial mode shapes:

```bash
spinfreq-track --study results/field-sweep --output results/tracking
```

The
[mode-matching guide](../docs/guides/MODE_TRACKING.md) explains provisional branch
IDs, near-degeneracy flags and choosing the number of modes.

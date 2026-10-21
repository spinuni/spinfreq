# User manual

SpinFreq computes thin-film equilibria, linear modes and weak-field spectra on a CPU. Start with a small FMR problem, then change geometry and material. A skyrmion seed alone does not establish a stable skyrmion.

## Install and launch

Use Python 3.11–3.13. Until a release is published, install from the [source repository](https://github.com/spinuni/spinfreq). See [Downloads](downloads.html) for platform-specific commands and release status.

```bash
git clone https://github.com/spinuni/spinfreq.git
cd spinfreq
python -m venv .venv
# Linux / WSL2 / macOS:
.venv/bin/python -m pip install -e '.[web]'
.venv/bin/spinfreq-web
```

On Windows PowerShell, replace the last two commands with:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[web]'
.\.venv\Scripts\spinfreq-web.exe
```

Open **http://127.0.0.1:8000**. The browser is the interface; Python uses the CPU and RAM of the machine running the server. Linux/WSL2 enables computation automatically. Windows defaults to preview; `--mode compute` opts into experimental native Windows workers. Native Windows qualification remains pending. macOS offers preview only for the protected web queue. Stop the server with Ctrl+C.

## Your first simulation

1. Open the [workbench](workbench) and choose **prism-fmr**. This single-cell rectangular prism is a fast susceptibility example, not a resolved skyrmion.
2. Keep the preset geometry and material. Set 21 frequency points for a quick sweep, or retain 101 for more detail.
3. Run the simulation. The queue progresses through relaxation, eigenmodes and frequency response. Preview installations can validate and export the configuration instead.
4. Check the job status and numerical diagnostics before interpreting plots. Download `results.zip` and retain it with your notes.
5. Compare absorption maxima with positive-frequency poles in `modes.csv`. A sparse sweep can miss a narrow resonance; mode frequency and the highest sampled point need not coincide.

The same configuration works without a browser:

```bash
spinfreq --preset prism-fmr --write-config prism.json
spinfreq --config prism.json --output results/my-first-prism
```

Use a new output directory for every shared-API job. Existing files cause refusal rather than mixing runs. CLI calculations run directly; the web worker resource limits do not apply to direct CLI or Python calls.

## Choose the physical model

| Model | Geometry and operators | Use for |
| --- | --- | --- |
| `Film` / `periodic` | Periodic x/y, spectral derivatives, thickness-averaged film demagnetization | Repeating textures and uniform-film FMR |
| `ConfinedFilm` / `confined` | Finite rectangle, finite differences, cell-averaged Newell demagnetization | Edge effects, prisms and confined skyrmions |
| `BlochChain` | Periodic chain with Bloch phase and finite transverse width | Wavevector-resolved collective modes through Python |

All models assume uniform magnetization through thickness. The reproducible JSON/web workflow exposes the first two models. Bloch, nonlinear time integration and specialized matrix-free studies use the [advanced guide](https://github.com/spinuni/spinfreq/blob/main/docs/guides/USAGE.md).

## Configuration and units

JSON uses SI units, whereas labelled web fields can use nm and GHz. Exported JSON always uses metres, hertz and tesla. Unknown keys, duplicate JSON keys, unsupported schema versions and nonfinite values are rejected.

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1`; configuration format, independent of package version |
| `model`, `nx`, `ny` | `periodic` or `confined`, positive cell counts |
| `dx_m`, `dy_m`, `thickness_m` | Cell spacing and uniform film thickness in m |
| `material.Ms`, `.A`, `.D`, `.K` | A/m, J/m, J/m² and J/m³; signed interfacial DMI and uniaxial anisotropy |
| `material.alpha`, `.gamma` | Dimensionless Gilbert damping; positive gyromagnetic magnitude in rad/(s T) |
| `field_T`, `drive_T` | Three Cartesian components in T; static bias and real harmonic drive |
| `seed`, `seed_radius_m`, `seed_wall_m` | `uniform` or `skyrmion` and seed dimensions |
| `dmi_boundary` | `bond` or `mumax` for confined films; periodic requires `bond` |
| `fmin_Hz`, `fmax_Hz`, `points` | Inclusive linear frequency sweep; at least two samples |
| `torque_tolerance_T`, `maxiter` | Stationarity target and initial relaxation iteration budget |

The `mumax` boundary option is a physical boundary discretization, not a MuMax3 dependency. It differs from the `bond` default in reproducible presets; always report the selected boundary. Python `ConfinedFilm` defaults to `mumax`, so set it explicitly when comparing with a JSON job.

Download complete validated [example inputs](downloads.html#example-inputs) rather than guessing omitted defaults. For a skyrmion, start from `confined-skyrmion`: its 2 nm grid is a matched comparison example and needs refinement for continuum accuracy.

## Read the results

| Artifact | Interpretation |
| --- | --- |
| `configuration.json`, `summary.json` | Full input, versions, source hashes, torque, stability margin, residuals and response amplitude |
| `equilibrium.npy`, `equilibrium.ovf` | Unit-vector field; NumPy shape `(ny, nx, 3)`; OVF interchange |
| `modes.csv`, `modes.npz` | Complex eigenvalues and spatial eigenvectors; both conjugate branches |
| `response.csv`, `response.npz` | Driven sweep and complex magnetization response |
| `spectrum.png`, `equilibrium.png`, `mode.png` | Plot previews, not substitutes for numerical data |
| `manifest.json`, `results.zip` | Artifact hashes and portable run bundle |

The harmonic convention is `exp(+i 2π f t)`; negative eigenvalue real parts indicate decay. Mode normalization is arbitrary; driven response has physical dimensionless amplitude. See [Theory](theory.html) before comparing phases or linewidths with other solvers.

## Diagnose and refine

Failed relaxation: inspect the saved equilibrium and torque; improve the seed or increase relaxation effort before computing spectra. Uncertain/unstable eigenvalues: inspect neutral modes and equilibrium accuracy; do not reinterpret a rejected spectrum as a resonance. Excess response amplitude: decrease the drive; the shared job runner rejects maximum vector amplitude above 0.05. Resource failure: reduce cell count or sweep points and inspect the job error. Cancellation stops the worker; cancel a running job before deleting it.

The default web queue allows 400 cells, 201 frequencies and 3000 relaxation iterations; it runs one worker at a time with at most four pending/running and sixteen retained jobs. Workers have a 120 s wall-time budget, 60 s CPU budget and 2 GiB memory limit. Memory accounting differs between Linux and Windows. These are resource bounds, not physical accuracy guarantees.

For a research result, refine cell size at fixed dimensions, verify that equilibrium topology persists, tighten static and linear residuals, and refine the frequency sampling relative to damping. Compare spatial modes as well as frequencies. Test supercell size for periodic textures and magnetic-image convergence for Bloch calculations. Halving a weak drive should halve response and quarter absorbed power. Record the full configuration, package/source version, convergence changes and independent reference. Consult [Validation](validation.html) for the evidence and remaining limits.

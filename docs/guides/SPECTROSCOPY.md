# Spatial excitation and observation

Local experiment files can specify where a harmonic field acts, its complex
polarization, and where the response is measured. The operators and equilibrium
remain those of the selected periodic or confined single-layer model. Changing
excitation/probe symmetry changes mode visibility, while intrinsic linear poles
belong to the same equilibrium.
Profiles weight excitation and measurement; all configured cells remain magnetic.

## Run the examples

From a source checkout installed with `python -m pip install -e .`:

```bash
spinfreq --config examples/spectroscopy/localized-source.json --output results/localized
spinfreq --config examples/spectroscopy/wavevector-probe.json --output results/wavevector
```

The localized example is a 64 × 32 × 1 nm periodic film with 8 nm lateral cells.
A Gaussian source near x = 16 nm drives the film; probes measure a weighted
source region, a rectangular detector near x = 48 nm, and the whole-film mean.
It illustrates measurement definitions, not a converged physical device.

The second example excites a phase-dependent plane wave on a periodic strip.
Matching and opposite-wavevector probes distinguish the Fourier components.
A commensurate nonzero wavevector cancels in the whole-film mean even when
its spatial response is substantial. Refine the mesh for a physical study.

## Complex polarization and time convention

The exact drive is

```text
b(x,y) = w(x,y) [drive_T + i drive_imag_T]
Bac(x,y,t) = Re[b(x,y) exp(+i 2π f t)].
```

`drive_T` is the three-component real phasor part, in tesla. Optional
`drive_imag_T` is the imaginary part, also in tesla; it defaults to zero.
For example, `drive_T = [1e-6,0,0]` and `drive_imag_T = [0,-1e-6,0]` give
`Bx = 1 μT cos(ωt)` and `By = 1 μT sin(ωt)` for a uniform envelope. With the
implemented +z-equilibrium LLG convention this is the co-rotating polarization.
Changing equilibrium direction changes the relevant helicity.

One shared scalar spatial profile multiplies the complete polarization vector.
Component-dependent arbitrary field arrays remain available through the
low-level `film.response`/`ModalResponse` Python interfaces. The recipe interface
does not implement current-induced torques or transport measurements.

## Spatial profile definitions

Coordinates are measured in metres from the lower-left film corner. Samples
are at cell centres: `x = (ix+0.5) dx`, `y = (iy+0.5) dy`. The optional
`drive_profile` object uses one of these definitions:

| `kind` | Required fields | Sampled envelope |
| --- | --- | --- |
| `uniform` | None | 1 |
| `rectangle` | `center_m: [cx,cy]`, `size_m: [sx,sy]` | 1 inside the box, 0 outside; lower boundaries included, upper excluded |
| `gaussian` | `center_m: [cx,cy]`, `sigma_m: [σx,σy]` | `exp(-0.5 ((x-cx)/σx)² - 0.5 ((y-cy)/σy)²)` |
| `plane_wave` | `k_rad_m: [kx,ky]` | `exp(+i (kx x + ky y))` |

All kinds optionally accept `phase_rad`, multiplying the envelope by
`exp(+i phase_rad)`. Widths and sigmas must be positive. A profile without any
resolved cell, or with nonfinite values, is rejected before execution. Fields
irrelevant to the selected kind are rejected to expose input mistakes.

Excitation profiles are sampled without peak or integral renormalization.
A Gaussian centre between cells therefore has sampled peak below one. A box
narrower than a cell may select no samples. Phase and physical coordinates are
retained in the input and exact sampled fields are exported.

In a periodic model the sampled source pattern repeats with the simulation
cell. For a pure Fourier component, use `kx Lx = 2π n` and `ky Ly = 2π m`.
An incommensurate sampled phase creates a discontinuity across the periodic
seam. A plane-wave drive on a confined rectangle is an imposed field pattern;
finite boundaries still determine its modes.

## Probe definitions and normalization

Optional `probes` is a list of at most 16 uniquely named probes:

```json
{
  "probes": [
    {"name": "mean"},
    {"name": "detector", "profile": {
      "kind": "rectangle", "center_m": [4.8e-8, 1.6e-8], "size_m": [1.6e-8, 3.2e-8]
    }}
  ]
}
```

Each probe has a spatial profile using the definitions above. For every
frequency it measures the three Cartesian components

```text
s_p(f) = Σcells conj(w_p) δm(f) / Σcells |w_p|.
```

Uniform probes give spatial means. Positive rectangle/Gaussian profiles give
weighted averages. A complex plane-wave probe extracts the matching Fourier
coefficient because its phase is conjugated. This L1 normalization is invariant
to multiplying the weights by a positive constant. It does not amplify the
excitation or convert a magnetization response to susceptibility.

When `probes` is omitted, one uniform probe named `mean` is used. An explicit
list defines exactly those probes; include a uniform entry to retain that
measurement. `response.csv` always retains the original whole-film mean.
Probe names start with a letter and contain up to 48 letters, digits, `_` or `-`.

## Reproducible output

| File | Contents |
| --- | --- |
| `excitation.npy` | Actual complex drive b in T, shape `(ny,nx,3)` |
| `response.npz` | Full complex `delta_m`, frequencies, total power and the polarization prefactor `drive_T` |
| `observations.npz` | `probe_names`, raw complex `weights`, L1 `normalization`, `frequencies_Hz`, and complex `delta_m` shaped `(nf,nprobe,3)` |
| `observations.csv` | One row per frequency/probe, with real and imaginary x/y/z components |
| `summary.json` | Probe names, normalization/time convention and maximum drive component |

All new files are covered by the normal result manifest and ZIP. The complete
configuration retains profile recipes and polarization. Existing schema-1
uniform-real inputs keep their meaning and original configuration hashes;
unused optional fields are omitted from normalized JSON. Study resume checks
numerical source changes, so use a new output directory after upgrading code.

## Analyze a detector signal

```python
import numpy as np

with np.load("results/localized/observations.npz", allow_pickle=False) as data:
    detector = list(data["probe_names"]).index("detector")
    f_GHz = data["frequencies_Hz"] / 1e9
    signal = data["delta_m"][:, detector, 0]
    amplitude = np.abs(signal)
    phase_rad = np.angle(signal)
    transfer_per_T = signal / 1e-6
```

Phase becomes ill-conditioned when the detected amplitude approaches zero.

Here the transfer function is normalized to the example's 1 μT source
prefactor, not its sampled peak. It depends on the chosen source and detector
profiles. A full susceptibility tensor requires independent basis drives with
consistent excitation/observation definitions. The current JSON job executes
one drive polarization per run. The optional
[tensor analysis command](SUSCEPTIBILITY.md) assembles the independent x/y/z
responses from a completed job with the same source/probe definitions.

Absorbed power is summed over all cells with the actual local complex drive:
`P = -Ms Vcell ω Im Σ(conj(b)·δm)/2`. It differs from a local detector amplitude.
Check numerical residuals, weak-drive scaling, frequency resolution, spatial
resolution and source/probe symmetry before interpreting peaks.

## Python construction and parameter studies

```python
from dataclasses import replace
from spinfreq import JobConfig, Probe, SpatialProfile, run_job

base = JobConfig.load("examples/spectroscopy/localized-source.json")
detector = Probe("spot", SpatialProfile("gaussian", center_m=(48e-9, 16e-9),
                                      sigma_m=(8e-9, 8e-9)))
config = replace(base, probes=(detector,))
run_job(config, "results/spot-detector")
```

Profiles and probes are retained in the base of a `StudyConfig`.
`drive_imag_T.0/1/2` are supported numeric study axes alongside the existing
real-drive components. These are independent polarization studies;
equilibrium continuation remains restricted to a single field/material axis.
The web JSON API accepts the same validated recipes; dedicated profile editing
controls are outside this local-research change.

The [spectroscopy qualification](../../validation/spatial_spectroscopy/README.md)
documents analytical polarized/finite-k checks, Fourier cancellation and local
drive scaling. It does not broaden the underlying single-layer physics model.

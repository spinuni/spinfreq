# Compare field polarizations and modal coupling

Use this after [your first simulation](../getting-started/README.md). A spectrum
answers “what does this drive excite?” A transfer tensor additionally answers
“how would the response change if the field pointed in x, y or z?” It reuses
one equilibrium and one dense eigenbasis for the three independent source
polarizations. It does not run a new relaxation for each polarization.

## Run a small example

Open a terminal in the installed source checkout. These commands use CPU
Python on Windows, Linux and macOS; no GPU or browser worker is required.
Use new output folder names if you have already run them.

Windows PowerShell:

```powershell
.\.venv\Scripts\spinfreq.exe --preset prism-fmr --output results/polarization-demo
.\.venv\Scripts\spinfreq-susceptibility.exe --job results/polarization-demo --output results/polarization-tensor
```

Linux/macOS:

```bash
.venv/bin/spinfreq --preset prism-fmr --output results/polarization-demo
.venv/bin/spinfreq-susceptibility --job results/polarization-demo --output results/polarization-tensor
```

If the new command is missing, update the checkout and reinstall with your
virtual environment's Python: `python -m pip install -e .`. On Windows the exact
executable is `.\.venv\Scripts\python.exe`; on Linux/macOS it is `.venv/bin/python`.

Open **susceptibility.png** in the second folder. Each panel shows the norm of
the observed vector per tesla for one source polarization. A panel can be zero:
a field parallel to a uniformly aligned magnetization has no first-order torque.
These panels show response amplitude, not absorbed power.

For spatial measurements, replace the first command's preset with
`--config examples/spectroscopy/localized-source.json` or
`--config examples/spectroscopy/wavevector-probe.json`. The analysis uses the
saved source envelope and all configured probes. This is the same workflow as
the small example; larger dense meshes need more memory and time.

## Read the outputs

| File | Contents |
| --- | --- |
| `susceptibility.png`, `.pdf` | Polarization comparison, one curve per probe |
| `susceptibility.csv` | Long table: frequency, probe, observed component, drive component, real and imaginary transfer in 1/T |
| `susceptibility.npz` | Full complex tensor, signed eigenvalues, full tensor residues, source/probe weights, original drive, reconstructed observations and numerical residuals |
| `modal_coupling.npz`, `.csv` | Complex residues contracted with the original drive, for every signed mode, probe and observed xyz component; units 1/s |
| `summary.json`, `manifest.json` | Conventions, diagnostics, source-job and implementation hashes, versions and output checksums |

Tensor axes are **(frequency, probe, observed xyz, drive xyz)**. Residue axes are
**(signed mode, probe, observed xyz, drive xyz)**. Frequency is in Hz and signed
eigenvalues are rates in 1/s. NPZ files use standard NumPy arrays; load them
with `allow_pickle=False`. CSV contains all nine components, including zeros.
Mode indices belong to this analysis; match eigenvalues rather than assuming
they share the sorted row order of the original job's `modes.csv`.

```python
import numpy as np

with np.load("results/polarization-tensor/susceptibility.npz", allow_pickle=False) as data:
    tensor = data["tensor_per_T"]
    # Predict this weak elliptical field, with the same spatial envelope:
    b_T = np.array([1e-6, 1e-6j, 0])
    observed_delta_m = np.einsum("fpij,j->fpi", tensor, b_T)
```

A tensor is a linear derivative. Its unit-tesla normalization does **not** mean
a finite 1 T AC drive was physically simulated. Check full spatial amplitudes
with `prepared.response` before assuming a proposed field remains weak; a small
probe signal alone can hide large local motion. The original job's weak-drive
gate applies to its original drive, not every new polarization or amplitude.

## Definition and theory

With time dependence `exp(+iωt)`, source envelope s and probe weights w:

```
δm_observed,p,i = Σj T_p,i,j(f) b_j
T_p,i,j = [Σcells conj(w_p) δm_i(s e_j)] / Σcells |w_p|
```

The source is not normalized; the probe has conjugated L1 normalization. Thus
T is a **B-based source-to-probe transfer tensor in 1/T**, not generally a local
material susceptibility or dimensionless H-based susceptibility. For uniform
source/probe it is the spatially averaged response per tesla. Conversion to
M/H conventions requires the magnetization and field-unit factors appropriate
to the comparison.

If J = V diag(λ) V⁻¹ is the damped tangent-space LLG operator, F maps a field in
tesla to the tangent forcing rate, and C is the weighted observation:

```
T(f) = C V diag[1/(iω − λ)] V⁻¹ F
R_n = (C V)_n (V⁻¹ F)_n
T(f) = Σn R_n / (iω − λ_n)
```

The inverse right-eigenvector basis is essential for a nonnormal damped
operator. Residues are invariant under rescaling/rephasing an individual
nondegenerate eigenvector. Keep both signed branches for reconstruction.
At exactly degenerate poles, the **sum over the degenerate subspace** is
invariant; its individual residues depend on the eigenbasis. Near-degenerate
or ill-conditioned poles also require caution. Automatic subspace grouping
is not implemented. Complex residues interfere; their norms are not independent
absorbed powers or universal mode probabilities. A mode can be absent from a
measurement because the source, detector, or both have zero coupling.

## Provenance and boundaries

`spinfreq-susceptibility` checks all original job artifact hashes, successful
status and current numerical source hashes before rebuilding the operator from
the saved equilibrium. It checks shifted-system residuals and reconstructs the
original observed drive response. If numerical sources changed, create a fresh
simulation. Analysis does not modify the original folder. Hashes establish
integrity, not authenticity of an untrusted downloaded job.

The low-level Python function `susceptibility(prepared, frequencies_Hz,
source_weights=None, probe_weights=None)` returns a dictionary with the tensor,
residues, eigenvalues and residuals. Defaults are uniform source and mean probe.
It checks response residuals but does not implement the full job runner's
stability and amplitude gates. Rebuild `ModalResponse` after changing physics.

[Analytical tensor evidence](../../validation/susceptibility/README.md) covers
uniform and finite-k periodic Gilbert response, all components, complex
polarization reconstruction and modal gauge/degenerate-group invariance.
This does not add nonlinear response, thickness modes or current torques.

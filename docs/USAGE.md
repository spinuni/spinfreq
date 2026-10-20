# Using spinfreq

`spinfreq` solves thin-film micromagnetics using energy relaxation, linearized LLG eigenmodes, forced frequency response, Bloch bands and nonlinear time dynamics. Every model assumes a single magnetization vector through the film thickness. Choose the geometry before selecting a solver: a periodic lattice and a confined film are different physical systems.

## 1. Install and verify

From a local checkout:

```bash
cd spinfreq
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
```

In the prepared cloud environment:

```bash
cd /workspace/spinfreq
source /workspace/venvs/spinfreq/bin/activate
export MPLCONFIGDIR=/workspace/.cache/matplotlib
mkdir -p "$MPLCONFIGDIR"
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest -q
```

Use the existing checkout; a cloud task is already isolated. No Git worktree or running web/database service is needed. NumPy and SciPy provide the CPU solvers; Matplotlib writes headless PNG/PDF figures. MuMax3 is optional and requires a separate CUDA-capable runtime.

Single BLAS threads usually reduce overhead for these small dense systems. Increase parallelism only after measuring it; each process may allocate its own dense matrices. The prepared environment uses Python 3.12 with NumPy 2.4.4, SciPy 1.17.1 and Matplotlib 3.10.8. Project dependency ranges permit other supported versions; record versions for reproducible comparisons.

For the broader validation suite, published OOMMF FMR data, DMI benchmark priorities and the planned package/web release requirements, see [Validation and release](VALIDATION_AND_RELEASE.md). The external FMR benchmark is documented [here](../validation/fmr_standard_problem/README.md); it downloads reference data only when `--fetch-reference` is explicitly requested. A public web interface is not yet implemented.

## 2. Units and array layout

| Quantity | Python API unit | Example |
|---|---|---|
| `nx`, `ny` | integer cell counts | `40, 40` |
| `dx`, `dy`, `thickness` | m | `1e-9` |
| `Ms` | A/m | `580e3` |
| `A` | J/m | `15e-12` |
| `D` | J/m² | `3e-3` |
| `K` | J/m³ | `0.6e6` |
| `field_T`, `drive_T` | T, three Cartesian components | `(0, 0, 0.1)` |
| `alpha` | dimensionless Gilbert damping | `0.001` |
| `gamma` | rad/(s T), positive magnitude | `1.7595e11` |
| response frequencies | Hz | `17.2e9` |
| Bloch wavevector `k_rad_m` | rad/m | `0.05e9` |
| energy | J, total simulation cell | returned by `energy()` |
| absorbed power | W | returned by `absorbed_power()` |

Magnetization is a **unit vector**, stored as `(ny, nx, 3)`. The last axis is `(mx, my, mz)`; x is array axis 1, y is axis 0. It is not magnetization in A/m. Responses and eigenmodes have an extra leading frequency/mode axis and are complex. Nonlinear recordings have leading time axis; the recorded component list may contain only x/z or just z.

Specify `dy` explicitly for rectangular cells; otherwise it equals `dx`. Physical dimensions are `nx*dx` and `ny*dy`. The field API uses tesla, not A/m or oersted. For `H` in A/m, use `B=mu0*H` for the applied field. DMI is interfacial, not bulk chiral DMI. Positive `K` favors the z axis.

Cell counts are positive integers, including 1 and 2. Sampled-field derivative diagnostics return zero along singleton axes; open-axis MuMax DMI ghost boundaries are retained. A nonzero Bloch phase still produces exchange and DMI across a one-cell period. A two-cell confined diagnostic uses first-order differences. A one-cell axis represents uniform magnetization within that cell and still needs the intended boundary conditions. See the [DMI standard report](../validation/dmi_standard_problem/README.md#1-single-cell-axes-and-boundary-conditions) for the transverse-periodic wire example and the resulting difference from an open wire.

## 3. Choose a geometry

| Class | Boundary conditions | Spatial operators | Intended workflow |
|---|---|---|---|
| `Film` | periodic x and y | spectral exchange/DMI; thickness-averaged Fourier demag | ideal infinite 2D lattice, analytical checks, quick CLI demo |
| `ConfinedFilm` | finite x and y | finite-difference exchange/DMI; zero-padded cell-averaged Newell demag | isolated skyrmion, finite array, MuMax-oriented comparisons |
| `BlochChain` | infinite periodic x; finite/open y | finite differences; image-summed Newell demag with Bloch phase | intrinsic bands of a 1D chain |

`ConfinedFilm(dmi_boundary='mumax')` uses the MuMax3 default natural DMI ghost-spin extrapolation. In MuMax language this corresponds to `OpenBC=false` with `SetPBC(0,0,0)`. `OpenBC` controls its DMI edge prescription; it is not the periodic-boundary switch. `dmi_boundary='bond'` exposes the simpler bond-energy boundary and will change edge-dependent frequencies.

`BlochChain(images=32)` retains images from −32 to +32 along x. Test `images=64` before quoting small frequency differences. The Newell evaluation uses cell-volume averages near a source and stable Gauss quadrature at large separations. All three classes include exchange, interfacial DMI, uniaxial anisotropy, Zeeman and demagnetization. `demag=False` is intended for controlled analytical tests, not for silently approximating the paper.

Image convergence depends on physical extent `images*nx*dx`, not only the image count. A single-cell 2 nm x period needs many more images than a 40 nm skyrmion period. The DMI strip benchmark tests 512 versus 1024 images at 2 nm. For propagation with `exp(i k x-i omega t)`, select negative-imaginary eigenvalues and report `-Im(lambda)/(2*pi)`; the API's `frequencies_Hz` property continues to use `Im(lambda)/(2*pi)`. Both branches are retained. State the phase convention before comparing a nonreciprocal dispersion.

No class resolves z-dependent modes, multilayers, thermal noise, spin-transfer torque or nonrectangular meshes. The periodic `Film` demag approximation is not the same discretization as the MuMax-compatible confined model.

## 4. Quick periodic demonstration

```bash
spinfreq --nx 12 --ny 12 --cell-nm 4 --thickness-nm 1 \
  --field-t 0.1 --seed skyrmion --fmin-ghz 0.1 --fmax-ghz 100 \
  --points 101 --output results/periodic_demo
```

This CLI selects `Film`, not `ConfinedFilm` or `BlochChain`. Its material defaults are Ms=580 kA/m, A=15 pJ/m, D=3 mJ/m², **K=0.8 MJ/m³**, alpha=0.02 and gamma=1.760859e11. They differ from Liu 2024; use the paper benchmark scripts below for that study.

| CLI option | Meaning | Default |
|---|---|---|
| `--nx`, `--ny` | cell counts | 12, 12 |
| `--cell-nm` | square in-plane cell size | 4 nm |
| `--thickness-nm` | uniform film thickness | 1 nm |
| `--field-t` | static z-directed field | 0.1 T |
| `--seed` | `skyrmion` or `uniform` | `skyrmion` |
| `--fmin-ghz`, `--fmax-ghz` | forced sweep bounds | 0.1, 100 GHz |
| `--points` | frequency samples | 101 |
| `--maxiter` | relaxation iteration limit | 2000 |
| `--output` | result directory | `results` |

The command relaxes, checks convergence, computes the full spectrum, sweeps an x-directed 0.1 mT linear drive and plots absorption. A failed relaxation saves the equilibrium candidate/summary and stops before spectral analysis. Reusing an output directory overwrites generated outputs; use distinct directories for parameter studies. Existing output files alone do not establish that the latest run finished successfully.

## 5. Build and relax a confined film

```python
import numpy as np
from spinfreq import ConfinedFilm, Material, lattice_seed

material = Material(Ms=580e3, A=15e-12, D=3e-3,
                    K=0.6e6, alpha=0.001, gamma=1.7595e11)
film = ConfinedFilm(nx=40, ny=40, dx=1e-9, thickness=1e-9,
                    material=material, field_T=(0, 0, 0),
                    dmi_boundary='mumax')
initial = lattice_seed(film)  # 40 nm cell, 8 nm radius, 3 nm wall-width seed
relaxed = film.relax(initial, maxiter=5000, tolerance_T=1e-5)
if not relaxed.converged:
    raise RuntimeError(f"Residual torque field: {relaxed.torque_T:g} T")
np.save('equilibrium.npy', relaxed.m)
print(relaxed.energy_J, relaxed.torque_T, relaxed.iterations)
```

The seed is not an equilibrium. Relaxation minimizes energy with normalized spins and an analytical tangent gradient. It can preserve a skyrmion, collapse it, or converge to a metastable state. Convergence is determined by the maximum transverse effective field `|m×B_eff|`, in tesla. The default threshold is 10 μT. A minimizer's own success message does not override the physical residual check.

For an array with `columns` and `rows`, dimensions must match the chosen lattice spacing:

```python
columns, rows = 3, 1
array = ConfinedFilm(nx=40*columns, ny=40*rows, dx=1e-9,
                     material=material, field_T=(0, 0, 0))
seed = lattice_seed(array, columns=columns, rows=rows, period_m=40e-9)
```

A uniform initial state is `m=np.zeros(film.shape); m[...,2]=1`. DMI at natural boundaries can cant even a nominally uniform confined film. Check a magnetization plot, energy, residual and topology. Open-boundary topological charge is not necessarily an integer because magnetization at the boundary is not constant; Q≈−0.91 for the matched single-film benchmark is not by itself evidence of collapse.

## 6. Eigenmodes and interpretation

```python
spectrum = film.modes(relaxed.m)
positive = np.flatnonzero(spectrum.frequencies_Hz > 0)
print(spectrum.frequencies_Hz[positive] / 1e9)
print(spectrum.eigenvalues.real.max())
mode = spectrum.modes[positive[0]]  # (ny,nx,3), complex
```

The convention is `delta_m(t)=Re[v exp(lambda*t)]`. Frequency is `Im(lambda)/(2*pi)` and decay rate is `-Re(lambda)`. Negative-frequency partners are retained. **Positive real eigenvalues mean an instability**, even when the static torque is small. A relaxed saddle point is not a stable magnetic state. Exactly or nearly zero modes may represent translations or weak mesh pinning; report their residuals and convergence rather than treating every small frequency as a physical resonance.

Eigenvectors have arbitrary normalization and global phase. Their amplitude maps describe mode shape, not the response to a specified drive. To compare phase maps, choose a consistent global phase and mask pixels with negligible amplitude. Clockwise/counterclockwise labels also depend on the temporal branch and coordinate convention.

Full dense solves are for small systems: `Film` limits dense matrices to 1024 cells; `ConfinedFilm` limits assembly to 4096. The matched 40×40 film has 3200 tangent coordinates and is practical here. The limit is a guard, not a guarantee that the largest allowed calculation is cheap. Dense matrices scale as N² and full eigenanalysis as N³.

## 7. Forced response in frequency space

```python
f = np.linspace(15e9, 20e9, 201)
drive = (0, 0, 1e-6)
delta_m = film.response(relaxed.m, f, drive_T=drive)
power = film.absorbed_power(f, delta_m, drive)
```

The drive convention is `B_ac(t)=Re[b exp(+i*2*pi*f*t)]`; solve `(i*omega*I-J)u=F*b`. `drive_T` can be a three-vector or a spatial `(ny,nx,3)` field, and may be complex to represent phase/polarization. `delta_m` is dimensionless. The power formula uses the **same drive** used for the response and returns total cycle-averaged watts.

Check that `max(abs(delta_m))` is much less than one. The solver is linear and cannot generate harmonics or frequency-comb teeth. Positive damping avoids singular undamped resonances. A uniform drive can miss symmetry-forbidden modes; eigenfrequency lines need not coincide with every visible absorption peak.

For larger confined systems:

```python
delta_m = film.response_iterative(relaxed.m, [17e9],
                                 drive_T=(0,0,1e-6), rtol=1e-7, maxiter=200)
```

This uses a matrix-free GMRES solve and checks the true residual. Failure raises an error; it does not return a falsely converged response. Near resonances or in large arrays convergence can be slow. The complete-eigenbasis acceleration in `benchmarks/liu2024.py` is tested against direct response, but must not be used with a truncated Bloch spectrum.

## 8. 1D-chain Bloch bands and Fig. 2

```python
from spinfreq import BlochChain

chain = BlochChain(nx=40, ny=40, dx=1e-9, thickness=1e-9,
                   material=material, field_T=(0,0,0), images=32)
equilibrium = chain.relax(lattice_seed(chain), maxiter=6000)
if not equilibrium.converged:
    raise RuntimeError('Chain equilibrium did not converge')
k = 0.5 * np.pi / chain.period_m
bands = chain.bloch_modes(equilibrium.m, k,
                          count=12, target_Hz=15e9, tolerance=1e-9)
print(bands.frequencies_Hz / 1e9)
```

The Bloch boundary is `delta_m(x+a)=exp(i*k*a)*delta_m(x)`. The full micromagnetic field is retained, including image-summed nonlocal dipolar coupling. The equilibrium is x-periodic; its perturbation can have any Bloch wavevector. Complex matrix-vector products are essential; replacing them with real FFT results would break this calculation.

For a=40 nm, the first Brillouin zone is **−0.07854 to +0.07854 rad/nm**, and reciprocal spacing is **0.15708 rad/nm**. The paper's wider ±0.5 rad/nm axis is an unfolded plot. Do not confuse angular wavevector `k` with cycles/nm; they differ by `2*pi`.

`count` is the number of eigenvalues nearest the complex shift `i*2*pi*target_Hz`, including negative/near-zero modes. It is not a requested count of positive branches. The method assembles a dense unit-cell matrix, factors its shifted version and uses ARPACK. Check the returned frequency range and `chain.last_eigen_residuals`; increase counts/targets to look for additional bands. A truncated spectrum cannot certify global band gaps.

Reproduce the Fig. 2 comparison:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python benchmarks/liu2024_fig2.py
# Reuse raw arrays only after equilibrium/grid/current-operator residual checks:
OPENBLAS_NUM_THREADS=1 python benchmarks/liu2024_fig2.py --reuse
# An exploratory cheaper run, explicitly a different resolution/sampling:
OPENBLAS_NUM_THREADS=1 python benchmarks/liu2024_fig2.py \
  --meshes 20 --k-points 9 --output results/fig2_exploratory
```

Defaults are 20×20 and 40×40 meshes, 17 signed k points, 32 images each side and a 64-image convergence check. Outputs are under `validation/liu2024/fig2`. The plotted intrinsic mode weights are not the finite-chain pulse FFT intensity. See the [Fig. 2 report](../validation/liu2024/fig2/README.md): the FM gap and shifted upper onset agree closely, while the open-width infinite-chain breathing/gyration intervals do not fully reproduce the quoted paper ranges. Failed comparisons are retained as failed; no material parameters are fitted to hide them.

## 9. Nonlinear time dynamics

For a short workflow check:

```bash
OPENBLAS_NUM_THREADS=1 python benchmarks/liu2024_dynamics.py \
  --case chain-comb --columns 3 --cell-nm 2 --duration-ns 0.1 \
  --output results/chain_smoke
```

This has 10 GHz FFT bins and **cannot validate** a 0.3 GHz comb. The full pulse protocol is:

```bash
OPENBLAS_NUM_THREADS=1 python benchmarks/liu2024_dynamics.py \
  --case single-sinc-x --cell-nm 1 --duration-ns 40 --sample-ps 5 \
  --output results/single_pulse
```

Cases and defaults:

| `--case` | Geometry | Excitation |
|---|---|---|
| `single-sinc-x` | 40×40 nm finite film | x sinc, 5 mT, 50 GHz cutoff |
| `single-sinc-z` | same | z sinc, 5 mT, 50 GHz cutoff |
| `chain-sinc` | `--columns` skyrmions, one row | x sinc, left 40 nm strip, 50 GHz cutoff |
| `chain-comb` | same | x harmonic, 13.4 GHz |
| `array-sinc` | 19×19 skyrmions | x sinc, left strip, 30 GHz cutoff |
| `array-comb` | same | x harmonic, 20 GHz |

All cases default to 1 nm cells, 40 ns, 5 ps samples and 5 mT drive. Sinc center is 1 ns. The 2D source width and reuse of 40 ns for comb runs are documented assumptions. The paper does not state the exact 1D chain length: `--columns` is required. `--amplitude-mt 1` selects the weaker comparison drive. `--discard-ns`, `--window rectangular|hann` and `--components 0 2` control analysis/storage. Components 0,1,2 denote x,y,z. Array cases default to z-only storage; other cases record x,z.

DOP853 integrates full nonlinear LLG with adaptive internal steps. **Sampling interval is not the integrator step.** Default tolerances are rtol=1e-7 and atol=1e-9. For custom accuracy use `spinfreq.dynamics.integrate` and change `rtol`, `atol` and `max_step_s`; rerun to check convergence. It validates spin norms before normalizing recorded samples, and records the maximum drift. No artificial mixing term is inserted.

A custom recording callback receives sample indices and fields:

```python
from spinfreq.dynamics import integrate, harmonic_drive, left_strip

times = np.arange(200) * 5e-12
trace = np.lib.format.open_memmap('trajectory.npy', mode='w+', dtype=np.float32,
                                shape=(len(times), film.ny, film.nx, 3))
def record(indices, fields):
    trace[indices] = fields

trajectory = integrate(film, relaxed.m, times,
                       drive=harmonic_drive(5e-3, 13.4e9,
                                            mask=left_strip(film, 20e-9)),
                       rtol=1e-8, atol=1e-10,
                       recorder=record, chunk_samples=128)
trace.flush()
```

For this example, the source strip must fit your film. The returned `Trajectory` contains sample times, spatial mean magnetization, norm error and RHS evaluation count; the full cell data are stored only through the callback. Memory-mapped recordings keep sample storage out of RAM, but disk and computation costs still scale with cell/sample count. A 19×19 array with 1 nm cells and 8000 z-only float32 samples needs about **18.5 GB** just for its trajectory.

## 10. FFT spectra and f–kx maps

Per-cell FFTs preserve opposite-phase standing modes:

```python
from spinfreq.dynamics import cell_spectrum, space_time_spectrum

stored = np.load('trajectory.npy', mmap_mode='r')
f, amplitude, power = cell_spectrum(times, stored, component=2,
                                    discard_s=0, window='hann')
k, f, fk_power = space_time_spectrum(times, stored[...,2], dx_m=film.dx,
                                     time_window='hann', space_window='hann')
```

For scalar `(time,y,x)` recordings, call `cell_spectrum(..., component=None)`. `amplitude` is the mean per-cell one-sided magnitude; `power` is mean per-cell amplitude squared. Neither is W or a spectral density. The f–kx result is `(frequency, kx)`, averaged across y **after** temporal and spatial transforms. Averaging the magnetization first can cancel antiphase modes. Space/time windows are independent and reported with the result.

Frequency bins are `1/(N*dt)`. With 8000 samples at 5 ps, Δf=0.025 GHz and Nyquist=100 GHz. With 0.1 ns of data, Δf=10 GHz. After discarding a transient, recalculate resolution from the retained length. The rectangular window matches an unwindowed FFT but has stronger leakage; Hann reduces leakage while broadening peaks. Compare amplitudes only under the same window and normalization.

Spatial bins are `2*pi/Lx`. For a 400 nm chain, Δkx=0.015708 rad/nm, corresponding to the paper's 400 nm wavelength. A finite chain supports standing-wave mixtures; it is not identical to a single Bloch eigenmode.

To analyze the nonlinear runner's recorded data:

```bash
python benchmarks/liu2024_fk.py results/chain_run/trajectory.npy \
  --summary results/chain_run/summary.json --component 2 \
  --time-window hann --space-window hann --output results/chain_fk
```

Use component 0 for a ferromagnetic transverse spectrum; linear δmz is zero for an exactly perpendicular uniform magnetization. The component must have been recorded. This creates a genuine time/space FFT map; it does not create a validation pass merely because a plot exists. For a finite-chain paper Fig. 2-style pulse run, first execute `--case chain-sinc --columns <actual count>` with matching geometry and enough observation time.

## 11. Read outputs and export MuMax3 inputs

| Workflow | Important files | Interpretation |
|---|---|---|
| periodic CLI | `equilibrium.npy`, `summary.json`, `modes.npz`, `response.npz`, `spectrum.png` | full periodic spectrum and forced response |
| Fig. 1 | `frequencies.csv`, `summary.json`, comparison PNG/PDF, `single_*.npz` | direct paper-frequency comparison; raw eigenmodes |
| Fig. 2 | `bands_*.csv`, `fm_eigenvalues.csv`, `summary.json`, PNG/PDF, `bloch_*.npz` | targeted Bloch bands, physical/numerical comparison status |
| nonlinear runner | `equilibrium.npy`, `trajectory.npy`, `summary.json`, `spectrum_*.csv` | adaptive evolution with stored component list and timing |
| f–kx analyzer | `space_time_fft.npz`, `fk.csv`, PNG/PDF, `summary.json` | spatial angular wavevector, frequency and power |

Read an eigenarray:

```python
raw = np.load('validation/liu2024/single_40.npz')
m = raw['m']
f_GHz = raw['eigenvalues'].imag / (2*np.pi*1e9)
spatial_modes = raw['modes']
```

Large raw arrays/trajectories are ignored by Git. CSVs, figures and validation reports are retained. Raw Bloch files contain `m`, `k_rad_m`, `eigenvalues` and `modes`; the targeted mode count differs from full eigenarrays. Read nonlinear `summary.json` before indexing `trajectory.npy`: z-only recordings use channel 0 for physical component z.

OVF exchange:

```python
from spinfreq.ovf import write_ovf, read_ovf
write_ovf('equilibrium.ovf', relaxed.m, film.dx, film.dy, film.thickness)
m, metadata = read_ovf('equilibrium.ovf')
```

The reader supports rectangular single-layer, three-component OVF2 text/binary4/binary8, checks counts and binary sentinels, and extracts MuMax time stamps. Use magnetization snapshots, not B-field files, as unit-vector initial states.

Generate the full single-film reference input and seed together:

```bash
python benchmarks/export_mumax.py --output results/mumax_single
# On a CUDA machine:
cd results/mumax_single
mumax3 run.mx3
```

For a localized finite-chain pulse, supply geometry explicitly:

```bash
python benchmarks/export_mumax.py --columns 10 --rows 1 \
  --drive sinc-x --frequency-ghz 50 --source-width-nm 40 \
  --output results/mumax_chain
```

The example count 10 is not an established author parameter. For a comb use `--drive harmonic --frequency-ghz 13.4`. For the paper's 2D lattice use `--columns 19 --rows 19 --drive harmonic --frequency-ghz 20`. Generated inputs are independent reference templates, not the authors' original files.

```bash
python benchmarks/analyze_mumax.py path/to/run.out --component 2 \
  --output results/mumax_spectrum
```

The analyzer requires numbered `m*.ovf` fields and actual uniform timestamps. Spatially averaged `table.txt` is insufficient for mode profiles or standing-wave spectra. Generation and parsing were tested here; MuMax3 execution itself was not performed without CUDA.

## 12. Validation and troubleshooting

Run the analytical suite with `python benchmarks/validate.py` and the matched Fig. 1 suite with `python benchmarks/liu2024.py`. The latter uses the paper's constants explicitly; importing the generic `Material()` defaults does not select them. Fig. 2 is a separate comparison whose summary currently records partial agreement and failed range checks. Frequency-comb/standing-wave validation remains separate from linear bands.

- **Relaxation fails:** inspect the residual, iteration limit and state. Try supported initial states and adequate resolution; do not override equilibrium tolerance just to force a spectrum.
- **Positive growth rate:** a saddle/unstable equilibrium or unresolved numerical issue. Inspect modes and convergence before claiming absorption of a stable lattice.
- **Near-zero branch changes strongly with mesh:** translations and grid pinning may dominate. Compare absolute shifts and mode shape; relative error alone is misleading near zero.
- **GMRES/ARPACK fails:** the target may be difficult or the spectrum too incomplete. Preserve the failure, change count/target or use a small direct calculation to diagnose it. Do not describe missing branches as band gaps.
- **OOM or long runs:** use the unit-cell Bloch solver for intrinsic 1D bands, bounded sample recordings for time dynamics, and representative small runs before full arrays. Mesh coarsening changes physics and must be labeled.
- **Wrong GHz or wavevector scale:** Hz→GHz divides by 1e9; rad/m→rad/nm also divides by 1e9. A quantity in cycles/nm must be multiplied by 2*pi first.
- **Phase map disagrees globally:** remove arbitrary phase, match temporal branch/polarity and mask zero-amplitude pixels. A global offset is not a mode discrepancy.
- **Plot cache errors:** set `MPLCONFIGDIR` to a writable directory before importing Matplotlib.
- **Literature disagreement:** match model, static field, lattice, boundaries, numerical mesh, damping and excitation. Do not fit material constants while calling the result an independent validation.

For new quantitative results, retain parameter metadata, check mesh/image/time convergence, inspect equilibrium and mode character, and compare against an independent solver. A zero-test run, a successful process, a plot or matching one frequency does not establish full physical validation.

## 13. Refine equilibria and test boundary hypotheses

For near-zero modes, the default energy-minimization stopping criterion can leave a residual too large to assess weak growth/decay reliably. Use the public residual-based refinement before linearizing:

```python
from spinfreq import refine_equilibrium
refined = refine_equilibrium(film, relaxed.m, tolerance_T=1e-8, maxiter=40)
if not refined.converged:
    raise RuntimeError(refined.message)
spectrum = film.modes(refined.m)
```

Refinement uses normalized tangent coordinates and Newton/Krylov root finding. It preserves frozen spins when the model supplies a free-spin mask. It solves the static torque equations and can converge to a saddle; eigenvalue/stability checks remain necessary. It is not a replacement for first finding an appropriate local energy minimum.

For Bloch modes, `last_eigen_residuals` contains normalized residuals and `last_eigen_absolute_residuals` contains residuals in s⁻¹. Inspect absolute residuals for near-zero eigenvalues: a small residual divided by a large exchange matrix norm alone does not establish their accuracy. The periodic kernel now uses a circular x convolution of the Bloch envelope, open-y zero padding and Hermitian displacement pairing. This preserves cell-translation symmetry at each wavevector even with a finite image sum. The cache marker invalidates older Bloch arrays.

```bash
# Independent magnetostatics and analytical helix checks
OPENBLAS_NUM_THREADS=1 python benchmarks/standard_checks.py
# Default 2 nm screen skips widths that are not resolved by that cell size
OPENBLAS_NUM_THREADS=1 python benchmarks/liu2024_conditions.py
# Refine promising cases to the paper mesh, including the explicit midpoint probe
OPENBLAS_NUM_THREADS=1 python benchmarks/liu2024_conditions.py \
  --cases natural_w40 pinned2_w44 pinned2_w46 --cell-nm 1 --k-points 5 \
  --output validation/liu2024/conditions/refined
OPENBLAS_NUM_THREADS=1 python benchmarks/liu2024_conditions.py \
  --cases pinned2_w45 --cell-nm 1 --k-points 5 \
  --output validation/liu2024/conditions/midpoint
OPENBLAS_NUM_THREADS=1 python benchmarks/check_condition_images.py
python benchmarks/condition_mode_character.py
python benchmarks/summarize_conditions.py
```

The benchmark `PinnedChain` freezes +z boundary rows and removes their tangent degrees of freedom. It supports relaxation and Bloch modes for this study; do not use inherited generic dynamics/response methods as a frozen-spin time solver. Its 2 nm fixed layer is kept physically 2 nm thick across mesh refinement, not one row at every resolution. The 44 nm case has a 40 nm free region plus 2 nm magnetic buffers on each side. The 45 and 46 nm widths are explicit sensitivity probes, not parameters supplied by the authors.

See [the condition report](../validation/liu2024/conditions/README.md) for the numerical corrections, standard checks, mode-character evidence and remaining upper-band/neutral-mode disagreements. Full Standard Problem 4 switching dynamics, exact author geometry and full source-dependent paper response are not validated by the prism-factor checks.

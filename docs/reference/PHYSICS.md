# Physics, solvers and research workflows

## Physics and conventions

The energy contains exchange `A |∇m|²`, interfacial DMI `D[mz div(m) - m·∇mz]`, uniaxial anisotropy `-K mz²`, Zeeman `-Ms B·m` and demagnetizing energy. For the periodic `Film` class, derivatives and the exchange Laplacian use Fourier operators. Nyquist odd derivatives vanish. The demagnetizing kernel is the thickness-averaged uniform-through-thickness film kernel: `Nzz=(1-exp(-|k|t))/(|k|t)`, with longitudinal in-plane component `1-Nzz`. At zero wavevector, `Nzz=1`. Mixed Nyquist coefficients are symmetrized to preserve a real self-adjoint field. This periodic model does not resolve edges or nonperiodic boundaries; use `ConfinedFilm` for finite rectangles. No current model resolves z-dependent modes or multilayers.

`B_eff = -(1/Ms) δE/δm` is in tesla. LLG is

`dm/dt = -gamma/(1+alpha²) [m×B_eff + alpha m×(m×B_eff)]`.

Relaxation minimizes energy with normalized spins and an analytical projected gradient. It finds a local stationary state; it neither guarantees a ground state nor proves dynamical stability. Check maximum transverse field, topology, and positive real eigenvalues (instabilities). The analytical LLG Jacobian is projected onto two orthonormal tangent directions per cell. Eigenvalues use `exp(lambda t)`; positive imaginary parts give positive frequencies, and negative real parts give decay. Both conjugate branches are saved.

For `B_ac(t)=Re[b exp(+i omega t)]`, solve `(i omega I - J) u = F b`. Response amplitudes are dimensionless magnetization perturbations. Absorbed power is `-Ms V omega Im(sum(conj(b)·delta_m))/2`. It can be negative for unstable equilibria. A uniform drive excites only modes with compatible symmetry at lattice wavevector zero. Local mode amplitudes and absorption peaks need not have identical visibility. The response is linear: check that amplitudes remain much less than one. Undamped poles may produce singular solves; use physical positive damping.

## Python API

```python
import numpy as np
from spinfreq import Film, Material, skyrmion_lattice

film = Film(nx=12, ny=12, dx=4e-9, thickness=1e-9,
            material=Material(Ms=580e3, A=15e-12, D=3e-3,
                              K=0.8e6, alpha=0.02),
            field_T=(0, 0, 0.1))
relaxed = film.relax(skyrmion_lattice(film))
if not relaxed.converged:
    raise RuntimeError(relaxed.message)
spectrum = film.modes(relaxed.m)
f = np.linspace(0.1e9, 100e9, 101)
response = film.response(relaxed.m, f, drive_T=(1e-4, 0, 0))
power = film.absorbed_power(f, response, (1e-4, 0, 0))
```

Spatially varying and complex polarized drives of shape `(ny,nx,3)` are supported. Material parameters are illustrative, not a fit to a specified sample. For other DMI chirality use the appropriate seed helicity and D sign.

## Validation and limits

Tests exercise the energy derivative including DMI and dipolar terms, uniform-film perpendicular Kittel frequency and damping, exchange dispersion, driven resonance and positive absorption, the analytical Jacobian against finite differences, relaxation and equilibrium guards, and the topological charge of a resolved seed.

Full eigenmode/direct-response solvers explicitly assemble a dense `2N × 2N` Jacobian. The periodic class limits assembly to 1024 cells and the confined/Bloch classes to 4096 cells. Confined matrix-free response and targeted Bloch shift-invert modes are also available. Start with 12×12; finer meshes become expensive. Production calculations require mesh/cell-size and supercell convergence, validation against an independent solver, and a sparse/matrix-free solver for larger grids. A coarse-grid demo alone does not establish quantitatively converged skyrmion frequencies. Nonlinear time response and Bloch-wave bands are implemented in separate workflows. Thermal fluctuations and z-dependent thickness modes remain unsupported.

## Literature-oriented validation and plots

Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python benchmarks/validate.py` to regenerate analytical Kittel, dipole/exchange and complex-susceptibility comparisons, plus skyrmion mesh convergence, absorption and mode maps. See [validation/README.md](../../validation/README.md) for references, equations, results and comparison limits. Figures are provided as PNG and vector PDF, with CSV source data. The coarse 12×12 low-frequency mode is a mesh-sensitive feature; use the convergence study before quoting skyrmion frequencies.

The **[Baker et al. FMR standard comparison](../../validation/fmr_standard_problem/README.md)** uses the authors' published OOMMF data, independently of Liu. On the finest 3 nm lateral mesh, its two visible low-mode frequencies agree within 0.18% of fitted OOMMF poles, fitted linewidths within 0.4%, and complex y-mode overlaps exceed 0.98. This uses one uniform z layer versus the reference's two layers; it does not validate z-dependent modes. Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python benchmarks/fmr_standard_problem.py --fetch-reference` for the 5, 4 and 3 nm lateral meshes, plots, CSVs and fit diagnostics.

The **[Cortés-Ortuño et al. DMI standard comparison](../../validation/dmi_standard_problem/README.md)** adds single-cell-axis support, pointwise agreement with published MuMax3/OOMMF/Fidimag wire profiles, an analytical signed-k dispersion test, and Bloch-strip comparisons with saved MuMax3 fit summaries. It reproduces the apparent reduction of 3 to about 2.62 mJ/m² from the authors' asymmetric quadratic fit, while direct ±k pairs recover about 2.99 mJ/m². Boundary choices and mesh convergence are explicit. The [new independent CPU OOMMF comparison](../../validation/dmi_temporal/README.md) adds two executed 4 ns ringdowns: full complex Fourier traces agree within 0.058%, four signed-k FFT peaks agree, and halving the initial perturbation quarters power. It also identifies and fixes a one-bin even-length FFT labeling bias in the reference analysis. The original finite-strip pulse and full historical band disagreement remain open. Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python benchmarks/dmi_standard_problem.py --fetch-reference --check` for plots, CSVs and checks; `--skip-dispersion` selects the smaller static/analytical suite used in CI.

The **[two-field skyrmion OOMMF comparison](../../validation/skyrmion_temporal/README.md)** validates noncollinear equilibrium profiles, full spatial ringdown and complex vector modes at 0 and 50 mT. Two executed 8 ns references agree with linear reconstruction within 0.0086%; all six mode MACs exceed 0.998 and independently fitted frequencies agree within 0.019%. A separate mesh study shows that the matched 2 nm reference grid needs refinement; the 1 to 0.8 nm pair changes the first three poles by at most 0.648%. Raw spatial snapshots, hash-checked reanalysis, plots and CPU execution commands are included. The [new fine-grid continuation](../../validation/skyrmion_fine/README.md) supplies the missing 1 nm external dynamics; the supported thickness envelope remains open.

The [fine-grid continuation](../../validation/skyrmion_fine/README.md) executes both fields at 1 nm resolution and combines their passing dynamics with the 1 to 0.8 nm refinement. Full spatial errors stay below 0.0096%, six mode MACs exceed 0.997, and fitted frequencies agree within 0.008%. Qualification applies to the stated single-layer square-film model; general thickness and parameter envelopes remain open.

`ModalResponse` now reuses a complete eigenbasis for dense frequency queries and reconstructs exact linear startup transients for smoothly ramped multitone drives. It checks basis reconstruction and true solve residuals. In the [201-frequency reuse comparison](../../validation/response_reuse/README.md), measured CPU time is 8.07× lower including preparation, with full-field differences below 2.4e−12. Dense memory limits remain. See the [usage guide](../guides/USAGE.md#7-forced-response-in-frequency-space).

The [independent multitone drive comparison](../../validation/driven_response/README.md) now tests complex susceptibility at six frequencies near two resonances, smooth turn-on and drive halving. The mean transient agrees within 0.0048%, phasors within 0.14% and phase within 0.008 degrees. Power scales by 1/4. This is the matched 2 nm problem; the fine-grid ringdowns above address spatial refinement separately.

## Liu 2024 MuMax3 benchmark

The [paper validation](../../validation/liu2024/README.md) adds a finite-film `ConfinedFilm` model with nearest-neighbor exchange, MuMax-compatible DMI boundary ghosts and Newell cell-averaged demagnetization. With the paper's 40×40×1 nm geometry, 1 nm cells, material and damping, the three single-skyrmion frequencies agree within 0.3% of Fig. 1. Run `OPENBLAS_NUM_THREADS=1 python benchmarks/liu2024.py` for comparison figures and CSVs.

Full nonlinear LLG, localized sinc/harmonic fields, per-cell FFTs, bounded sample recording and OVF interchange are available for array work. See `benchmarks/liu2024_dynamics.py`, `benchmarks/export_mumax.py` and `benchmarks/analyze_mumax.py`. The paper's nonlinear frequency comb has not yet been validated; matching single-skyrmion frequencies does not establish comb reproduction. The original `Film` class retains its periodic spectral model.

## 1D collective excitations: Fig. 2

Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python benchmarks/liu2024_fig2.py` for independent FM checks and wavevector-resolved 1D-chain calculations. See the [Fig. 2 report](../../validation/liu2024/fig2/README.md) for numerical convergence, plots and explicit disagreements with the reported band ranges. `benchmarks/liu2024_fk.py` produces time/space FFT maps from finite-array recordings. Intrinsic Bloch weights and pulse-driven FFT intensity are distinguished.

## Boundary hypotheses and independent checks

The [condition study](../../validation/liu2024/conditions/README.md) tests widths, DMI edges and fixed buffers without fitting material constants. Pinned-strip hypotheses bring the low bands close to the paper, while upper-band and near-zero-mode limitations remain explicit. It also fixes periodic Bloch demag symmetry and introduces `refine_equilibrium` for more accurate static residuals. Independent prism surface integrals and continuum/finite-difference DMI helix checks are available in `benchmarks/standard_checks.py`.

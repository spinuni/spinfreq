# spinfreq

Micromagnetic simulator for thin films with linear eigenmodes, forced frequency response, 1D Bloch bands and nonlinear LLG dynamics. `Film` models periodic x/y lattices, `ConfinedFilm` models finite rectangles, and `BlochChain` models x-periodic chains with open y boundaries. SI units throughout; magnetization is uniform through the thickness.

See the **[detailed usage guide](docs/USAGE.md)** for installation, model selection, API examples, units, outputs, paper benchmarks and MuMax3 exchange.

## Install and run

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
spinfreq --nx 12 --ny 12 --cell-nm 4 --thickness-nm 1 --points 101
```

In the prepared cloud environment, activate `/workspace/venvs/spinfreq/bin/activate` instead. Set `MPLCONFIGDIR=/workspace/.cache/matplotlib` for writable plotting caches. Generated files are saved in `results/`: equilibrium magnetization, summary with residual torque and approximate topological charge, complex eigenmodes, complex driven response, absorbed power and a spectrum plot. A nonconverged relaxation exits with an error before computing frequencies. Negative topological charge near -1 identifies the default resolved seed; collapse to a uniform state is possible and must be checked in `summary.json`.

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

Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python benchmarks/validate.py` to regenerate analytical Kittel, dipole/exchange and complex-susceptibility comparisons, plus skyrmion mesh convergence, absorption and mode maps. See [validation/README.md](validation/README.md) for references, equations, results and comparison limits. Figures are provided as PNG and vector PDF, with CSV source data. The coarse 12×12 low-frequency mode is a mesh-sensitive feature; use the convergence study before quoting skyrmion frequencies.

## Liu 2024 MuMax3 benchmark

The [paper validation](validation/liu2024/README.md) adds a finite-film `ConfinedFilm` model with nearest-neighbor exchange, MuMax-compatible DMI boundary ghosts and Newell cell-averaged demagnetization. With the paper's 40×40×1 nm geometry, 1 nm cells, material and damping, the three single-skyrmion frequencies agree within 0.3% of Fig. 1. Run `OPENBLAS_NUM_THREADS=1 python benchmarks/liu2024.py` for comparison figures and CSVs.

Full nonlinear LLG, localized sinc/harmonic fields, per-cell FFTs, bounded sample recording and OVF interchange are available for array work. See `benchmarks/liu2024_dynamics.py`, `benchmarks/export_mumax.py` and `benchmarks/analyze_mumax.py`. The paper's nonlinear frequency comb has not yet been validated; matching single-skyrmion frequencies does not establish comb reproduction. The original `Film` class retains its periodic spectral model.

## 1D collective excitations: Fig. 2

Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python benchmarks/liu2024_fig2.py` for independent FM checks and wavevector-resolved 1D-chain calculations. See the [Fig. 2 report](validation/liu2024/fig2/README.md) for numerical convergence, plots and explicit disagreements with the reported band ranges. `benchmarks/liu2024_fk.py` produces time/space FFT maps from finite-array recordings. Intrinsic Bloch weights and pulse-driven FFT intensity are distinguished.

## Boundary hypotheses and independent checks

The [condition study](validation/liu2024/conditions/README.md) tests widths, DMI edges and fixed buffers without fitting material constants. Pinned-strip hypotheses bring the low bands close to the paper, while upper-band and near-zero-mode limitations remain explicit. It also fixes periodic Bloch demag symmetry and introduces `refine_equilibrium` for more accurate static residuals. Independent prism surface integrals and continuum/finite-difference DMI helix checks are available in `benchmarks/standard_checks.py`.

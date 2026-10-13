# spinfreq

Reference micromagnetic simulator for periodic thin films, with **both** linear eigenmodes and forced frequency-domain response. SI units throughout. The film is discretized in x/y and magnetization is assumed uniform through its thickness. One skyrmion per periodic rectangular cell describes an infinite rectangular lattice; it is not an isolated skyrmion or automatically a triangular ground state.

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

The energy contains exchange `A |∇m|²`, interfacial DMI `D[mz div(m) - m·∇mz]`, uniaxial anisotropy `-K mz²`, Zeeman `-Ms B·m` and demagnetizing energy. Derivatives and the exchange Laplacian use periodic Fourier operators. Nyquist odd derivatives vanish. The demagnetizing kernel is the thickness-averaged uniform-through-thickness film kernel: `Nzz=(1-exp(-|k|t))/(|k|t)`, with longitudinal in-plane component `1-Nzz`. At zero wavevector, `Nzz=1`. Mixed Nyquist coefficients are symmetrized to preserve a real self-adjoint field. This model does not resolve z-dependent modes, edges, substrates, multilayers or nonperiodic boundaries.

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

The current solver explicitly assembles a dense `2N × 2N` Jacobian and uses dense eigenvalue/response solvers; it is a small-system reference implementation, limited to 1024 cells. Start with 12×12; finer meshes become expensive. Production calculations require mesh/cell-size and supercell convergence, validation against an independent solver, and a sparse/matrix-free solver for larger grids. A coarse-grid demo alone does not establish quantitatively converged skyrmion frequencies. Thermal fluctuations, nonlinear response and Bloch-wave band dispersion are not implemented.

# Liu et al. 2024: MuMax3 paper validation

Source: uploaded *Low-lying magnon frequency comb in skyrmion crystals*, X. Liu et al., Physical Review B **110**, 184413 (2024), DOI https://doi.org/10.1103/PhysRevB.110.184413. Reference frequencies are transcribed from Fig. 1 and Sec. III, not digitized or fitted. The paper itself is not redistributed here.

## Matching the model

The earlier periodic 48 nm calculation with Ku=0.8 MJ/m³, Bz=0.1 T and alpha=0.02 does not represent this paper. This benchmark uses:

| Parameter | Value | Source |
|---|---:|---|
| Film dimensions | 40×40×1 nm | Fig. 1 / Sec. III |
| Cell dimensions | 1×1×1 nm | Sec. III |
| Ms | 580 kA/m | Sec. III |
| Exchange A | 15 pJ/m | Sec. III |
| Interfacial DMI D | 3 mJ/m² | Sec. III |
| Perpendicular Ku | 0.6 MJ/m³ | Sec. III |
| Gilbert alpha | 0.001 | Sec. III |
| Static field | 0 T | Assumption: none stated |
| Gamma | 1.7595×10¹¹ rad/(s T) | Inspected MuMax3 default, not specified by authors |
| Boundary | Finite rectangle, MuMax default DMI ghosts | Assumption; author script unavailable |

The new `ConfinedFilm` uses nearest-neighbor exchange, central interfacial DMI, finite/open magnetostatics, and MuMax-compatible DMI boundary extrapolation. In MuMax terminology **`OpenBC=false` is the default natural DMI boundary**; it does not mean periodic boundaries. `SetPBC(0,0,0)` disables periodic boundaries. The default stencil is independently tested against the four-neighbor field in MuMax's `cuda/dmi.cu`. The simpler variational bond boundary remains available as `dmi_boundary='bond'`, but is not used for paper comparisons.

MuMax3 source inspected at commit `f284051153d1513523043fe42654e283c6e21464`:

- [DMI stencil](https://github.com/mumax/3/blob/f284051153d1513523043fe42654e283c6e21464/cuda/dmi.cu), SHA256 `12966b393b480ae864d454ee8b1613f36631d6427144378fb8241aa2298173b1`.
- [Gamma default](https://github.com/mumax/3/blob/f284051153d1513523043fe42654e283c6e21464/engine/torque.go).
- [Boundary default](https://github.com/mumax/3/blob/f284051153d1513523043fe42654e283c6e21464/engine/exchange.go).

This inspected source version is not claimed to be the exact version used in 2024. The demag kernel is the Newell rectangular-cell volume average, convolved with zero padding; cube self-demag, trace, symmetry, energy gradient and distant dipole behavior are tested. For separations beyond 40 cell lengths, double-cell Gauss quadrature replaces cancellation-prone Newell differences (relative truncation scales as `(cell/r)^4`). Thickness is one cell; xz/yz components vanish by symmetry. This is substantially closer to MuMax's cell geometry than the earlier periodic thickness-averaged kernel.

## Achieved: Fig. 1 eigenfrequencies

| Mode (paper label) | Paper GHz | spinfreq GHz | Difference |
|---|---:|---:|---:|
| 1, CCW gyration | 1.9 | 1.897045 | 0.156% |
| 2, breathing | 17.2 | 17.175745 | 0.141% |
| 3, CW gyration | 39.1 | 38.988850 | 0.284% |

At the paper's 1 nm grid the residual transverse field is 0.759 μT and all computed modes have negative growth rates. Our acceptance criterion is **1% per reported mode**, chosen for this project; the authors do not specify a validation tolerance. No parameters were fitted to these three frequencies. The infinite-film FMR formula gives **37.5277 GHz**, consistent with the paper's 37.5 GHz to its stated precision.

These are linearized LLG eigenfrequencies compared with peaks from the paper's finite-amplitude time-domain simulation. They are not a reproduction of the full 5 mT, 40 ns spectrum or a bitwise comparison with a MuMax run. The difference of the third mode exceeds the paper's 0.025 GHz FFT bin, so sub-bin spectral agreement is not claimed. The 2 nm run is included to expose discretization changes; matching the paper's 1 nm mesh is not a continuum-convergence claim.

Figures (PNG and vector PDF):

- `fig1_frequencies`: paper values versus independent eigenvalues, plus mesh dependence.
- `fig1_amplitude_phase`: equilibrium, normalized |δmz| and phase; phases below 3% of maximum amplitude are masked. The two gyration modes have opposite phase windings; absolute phase is arbitrary. Paper CW/CCW names are reference labels, not an independently validated handedness convention.
- `fig1_linear_absorption`: uniform x/z drives of **1 μT**, complete-eigenbasis response, with the paper frequencies marked. This is a linear absorption plot, not the arbitrary-unit 5 mT pulse FFT in Fig. 1(b). Mode amplitudes are independently normalized, not compared with arbitrary literature units.

CSV values and `summary.json` are tracked. Full eigenarrays are reproducible, locally retained in `single_*.npz`, and ignored in Git.

```bash
cd /workspace/spinfreq
source /workspace/venvs/spinfreq/bin/activate
export MPLCONFIGDIR=/workspace/.cache/matplotlib
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python benchmarks/liu2024.py
OPENBLAS_NUM_THREADS=1 python -m pytest -q
```

The 40×40 grid has 3200 tangent coordinates. Complete dense eigendecomposition fits this machine and was executed; large array calculations use matrix-free response or nonlinear time dynamics instead. The matrix-free GMRES path checks true residuals and raises on nonconvergence; it has not been benchmarked on the complete 19×19 array.

## Implemented: nonlinear excitation and cell-resolved FFT

`spinfreq.dynamics` now integrates full nonlinear LLG with adaptive DOP853, checks spin-norm drift and records samples in bounded chunks. The initial integration step is limited using exchange stiffness. Per-cell spectra are averaged **after** the FFT: averaging magnetization first would cancel standing modes of opposite phase. FFT output records window choice, transient discard, amplitude normalization and actual bin spacing. It is not a spectral density or absorbed-power measurement.

Paper protocol defaults:

- Single skyrmion: x or z sinc drive, 5 mT, 50 GHz cutoff, t0=1 ns, 40 ns observation, 5 ps sampling; 0.025 GHz FFT bins.
- 1D array: 40 nm period, left 40 nm source, x sinc cutoff 50 GHz; comb drive 13.4 GHz at 1 or 5 mT. **Chain length must be supplied**; the text does not specify it.
- 2D array: 19×19 skyrmions, 40 nm lattice spacing, x sinc cutoff 30 GHz; comb drive 20 GHz, 5 mT. Source width is assumed to be 40 nm; the paper only depicts it. The general 40 ns sampling protocol is reused as an explicit assumption because a separate comb duration is not given.

A nonlinear 3-skyrmion, 2 nm-cell, **0.1 ns smoke run** was executed. `nonlinear_smoke.json` records it. Its 10 GHz bins cannot resolve a 0.3 GHz comb, so it demonstrates startup/integration/recording/FFT only. The integrator also passes an independent exact, large-angle, damped macrospin solution. No 0.3/0.6 GHz comb is claimed from this short run.

```bash
# Exact single-skyrmion pulse protocol; this CPU time-domain run can be slow.
OPENBLAS_NUM_THREADS=1 python benchmarks/liu2024_dynamics.py --case single-sinc-x

# Supply chain length explicitly; 10 below is an illustrative choice, not established author geometry.
OPENBLAS_NUM_THREADS=1 python benchmarks/liu2024_dynamics.py --case chain-comb --columns 10

# Full reported 2D lattice; z-only recording defaults to ~18.5 GB for 40 ns.
# Prefer a CUDA machine and MuMax export for this expensive array run.
OPENBLAS_NUM_THREADS=1 python benchmarks/liu2024_dynamics.py --case array-comb
```

The CPU script does not silently substitute a coarse grid or shorter duration. Float32 sample storage reduces disk use; integration uses float64. Both time-step/tolerance convergence and observation-length convergence are required before interpreting sidebands. The full 40 ns single/chain/2D nonlinear runs have **not** been executed here.

## MuMax3 cross-validation inputs

OVF2 text and binary-4/binary-8 readers and a text writer support exchanging equilibria and sample fields. A generated single-film template is retained under `benchmarks/mumax/`. Generate a seed and executable input together:

```bash
python benchmarks/export_mumax.py --output results/mumax_single
# On a CUDA/MuMax3 machine, cd into that directory and run: mumax3 run.mx3

# Example chain; count is explicit, as above.
python benchmarks/export_mumax.py --columns 10 --drive harmonic --frequency-ghz 13.4 --source-width-nm 40 --output results/mumax_chain

# Reported 2D lattice, with explicitly assumed source width.
python benchmarks/export_mumax.py --columns 19 --rows 19 --drive harmonic --frequency-ghz 20 --source-width-nm 40 --output results/mumax_array

# Analyze actual MuMax snapshots, checking mesh and timestamps.
python benchmarks/analyze_mumax.py path/to/run.out --component 2 --output results/mumax_fft
```

The analyzer requires numbered magnetization snapshots, not just spatially averaged `table.txt`. Its FFT uses actual OVF simulation timestamps and rejects irregular sampling. The templates were generated and inspected against MuMax source; **they were not executed in MuMax3** because this environment has no CUDA device or MuMax3 runtime. GPU outputs or the authors' scripts are needed for a direct solver-to-solver comparison.

## Still outstanding

Fig. 2 has now been evaluated with a Bloch-chain solver, with partial agreement and failed band-endpoint checks: see [the Fig. 2 report](fig2/README.md). Still outstanding: quantitative Fig. 2 reproduction and Fig. 3 standing-wave validation; Fig. 4's 0.3 GHz comb; Fig. 5's 0.6 GHz comb and damping dependence; matched 40 ns finite-amplitude spectra; time-step/run-length convergence; independent MuMax output comparison. These are separately marked as unvalidated in the summary. A linear solver cannot create nonlinear frequency mixing; the new nonlinear path is necessary, but its existence is not evidence that those results have been reproduced.

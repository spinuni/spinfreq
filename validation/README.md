# Validation and literature comparison

See the [validation/release assessment](../docs/VALIDATION_AND_RELEASE.md) for physics gates and selected MuMax3/OOMMF/Fidimag/Nmag papers beyond skyrmion frequency combs. The [external FMR standard comparison](fmr_standard_problem/README.md) now checks two visible frequencies, fitted decay linewidths and complex spatial mode overlaps against published OOMMF data. The analytical results below remain the foundation; application-specific agreement does not validate every geometry or parameter range.

Run from the repository root:

```bash
source /workspace/venvs/spinfreq/bin/activate
export MPLCONFIGDIR=/workspace/.cache/matplotlib
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python benchmarks/validate.py
python -m pytest -q
```

The script writes CSV data, PNG previews, vector PDF figures, raw NPZ arrays and `summary.json`. Single BLAS threads avoid overhead for these small dense systems. Raw NPZ arrays are reproducible and excluded from Git; figures, CSVs and summaries are retained. `--analytical-only` omits the skyrmion calculations. Output directories should be dedicated to the selected run; failed runs must not be interpreted using a previous summary.

## What is validated

- **Kittel uniform-film resonance**: both in-plane and perpendicular saturated configurations with zero damping and zero anisotropy. In-plane `f=gamma sqrt(B(B+mu0 Ms))/(2pi)`; perpendicular `f=gamma (B-mu0 Ms)/(2pi)`. The plotted perpendicular horizontal axis is the effective field `B-mu0 Ms`.
- **Perpendicular dipole/exchange dispersion**: fundamental thickness mode, zero damping, zero DMI and anisotropy. `f(k)=gamma sqrt(h(h+mu0 Ms(1-F)))/(2pi)`, where `h=B-mu0 Ms+2A k²/Ms`, `F=(1-exp(-kt))/(kt)`. This is the thickness-averaged approximation represented by this solver, not the full thickness-mode eigenproblem. Sorted eigenfrequency multisets are compared because degenerate Fourier modes can mix.
- **Complex Gilbert susceptibility**: an independent macrospin expression, `chi_xx=gamma (gamma B+i alpha omega)/[(gamma B+i alpha omega)²-omega²]`, checked against forced response with demagnetization disabled. This checks amplitude, phase and linewidth, not just peak frequency.
- **Skyrmion grid convergence**: fixed 48×48 nm periodic cell, 1 nm thickness, Bz=0.1 T, Ms=580 kA/m, A=15 pJ/m, D=3 mJ/m², K=0.8 MJ/m³ and alpha=0.02. Change resolution rather than cell size. Each mesh tests both the centered seed and a half-cell shifted seed, selects the lowest-energy dynamically stable candidate, and records energies and growth rates of both in `summary.json`. This avoids presenting a symmetric grid-pinning saddle as a stable equilibrium.
- **Skyrmion absorption and mode maps**: x- and z-directed uniform AC fields, amplitude 10 μT, at 16×16 resolution. Maps show an arbitrary but documented eigenvector phase; their absolute amplitudes are not driven amplitudes. Frequency ranks alone do not establish mode identities across crossings.

## Literature anchors and scope

1. C. Kittel, *On the Theory of Ferromagnetic Resonance Absorption*, Physical Review **73**, 155 (1948). https://doi.org/10.1103/PhysRev.73.155 — uniform-resonance analytical comparison.
2. B. A. Kalinikos and A. N. Slavin, *Theory of dipole-exchange spin wave spectrum for ferromagnetic films with mixed exchange boundary conditions*, Journal of Physics C **19**, 7013 (1986). https://doi.org/10.1088/0022-3719/19/35/014 — film spin-wave theory; our comparison uses the uniform thickness-mode limit, not every branch in that work.
3. M. Mochizuki, *Spin-Wave Modes and Their Intense Excitation Effects in Skyrmion Crystals*, Physical Review Letters **108**, 017601 (2012). https://doi.org/10.1103/PhysRevLett.108.017601 — context for polarization-dependent skyrmion-crystal excitations. Its microscopic chiral-magnet model and lattice are different from this interfacial-DMI rectangular thin-film model. No numerical frequency agreement with that paper is claimed.

These citations are reference anchors; external paper/metadata access was blocked by the current network policy during this run. No digitized literature data are plotted. The analytical lines are calculated from the stated formulas. A direct skyrmion-paper comparison requires a specified paper, matching material parameters, geometry/lattice, DMI convention and field, plus reference data and mode identification. Current defaults are illustrative, not an experimental fit.

## Interpreting convergence

The earlier 12×12 result at 3.82 GHz is not a converged finite-frequency resonance: the lowest mode tends toward zero with refinement, consistent with diminishing grid pinning of a translation mode. That interpretation needs mode tracking for a definitive classification. Weak positive growth rates occurred for some centered-grid solutions; half-cell shifted candidates remove them on the meshes where this was observed. The higher modes near 20 and 54 GHz converge much faster. Inspect the final-step errors in `summary.json`; they are a resolution comparison, not an uncertainty bound. Supercell/lattice-size convergence and an independent micromagnetic solver comparison remain outstanding.

## Results from this run

All four analytical relative errors are below `4.3e-13`. At 24×24 cells, the selected stable state has Q≈−0.999998. The first three positive frequencies are approximately 0.00154, 20.0579 and 53.8913 GHz. Between 20×20 and 24×24, the latter two change by 0.164% and 0.00357%, respectively. The near-zero branch remains poorly converged in relative terms and should not be quoted as a finite-frequency physical resonance. The response figure uses the explicitly stated 16×16 mesh, so its peaks should be compared to that mesh's eigenfrequencies rather than the 24×24 values.

# Fig. 2: collective excitations of a 1D skyrmion chain

This benchmark evaluates Fig. 2(b,c) and the linear collective-excitation discussion in Sec. III A of Liu et al., PRB **110**, 184413 (2024). It does not claim reproduction of Fig. 3 standing-wave profiles or the nonlinear frequency comb of Sec. III B.

**Result: partial agreement. The full Fig. 2 validation has not passed.** The numerical model is independently tested and the main discrepancies remain visible in the figures, CSVs and `summary.json`.

## Calculations actually executed

1. Independent uniform infinite-film LLG eigenvalues versus the dipole/exchange formula, using the paper material constants and damping.
2. An infinite x-periodic skyrmion chain with **40 nm period, 40 nm open width and 1 nm thickness**. Both 2 nm and the paper's 1 nm in-plane meshes were run. The equilibrium is relaxed, not imported from single-skyrmion results.
3. Seventeen signed Bloch wavevectors spanning the first Brillouin zone, at each mesh. Each point solves a targeted 12-eigenvalue LLG problem near 15 GHz, with full cellwise exchange/DMI and nonlocal magnetostatics.
4. Image-sum convergence from ±32 to ±64 neighboring periods, with re-relaxation at 64 images and checks at `ka/pi=0,0.5,1`.
5. A same-width ferromagnetic Bloch strip, relaxed with the same DMI boundary prescription, to separate finite-edge effects from the uniform infinite-film reference.
6. Additional finite 3- and 5-skyrmion chains at 2 nm resolution to diagnose whether simply adding end boundaries recovers the breathing-band top. These are diagnostics, not paper-resolution validation runs.

The raw eigenpairs were first computed directly. After a report-serialization correction, the report was regenerated using `--reuse`: cached equilibria, k grids and every eigenvector were rechecked against the current physical operator. Reported cache timings are not fresh eigensolver timings. Raw arrays are retained locally and ignored in Git; figures, CSVs and reports are tracked.

## Numerical results and comparisons

| Quantity | Paper | This calculation | Assessment |
|---|---:|---:|---|
| Uniform infinite-film FMR | 37.5 GHz | 37.52765 GHz | 0.0737% difference |
| Lowest upper-chain branch at k=0 | 34.5 GHz | 34.66624 GHz | 0.482% difference; mode character not fully classified |
| Gyration interval | 0.1–4 GHz | 0–1.93278 GHz | Quoted endpoints not reproduced |
| Breathing interval | 13.4–20.4 GHz | 13.07865–16.66720 GHz | Lower edge 2.40% low; upper edge 18.30% low |
| Finite-width FM control at k=0 | No matched boundary-specific value | 38.35823 GHz | Different from the infinite-film FMR reference |

The infinite-film numerical dispersion matches its independent analytical formula with maximum relative error **9.33e-15**. This validates numerical units, exchange/dipolar linear dynamics and the FM control, not the full skyrmion geometry.

The largest ±32→±64 image change is **3.83e-5 GHz**, far smaller than the breathing-band discrepancy. At 1 nm the equilibrium residual is **1.36 μT**. No growing modes are found in the targeted eigenpairs; this does not certify the entire uncomputed high-frequency spectrum. Positive/negative k frequencies agree within numerical precision. All candidate collective bands remain below the uniform FM resonance, reproducing the qualitative appearance of low-frequency branches.

At k=0 the 1 nm lowest branch is near-zero and nonoscillatory under the chosen damping, so it is recorded as **0 GHz** with an explicit flag. It is not discarded or replaced by a fitted finite gap. Infinite-chain translation symmetry and residual grid pinning make this a different limit from a finite chain with pinned ends. Matching the paper's nonzero low-frequency cutoff requires its exact geometry and boundary setup.

The 2→1 nm changes in the breathing endpoints are about 0.260 and 0.286 GHz. They do not account for the roughly 3.73 GHz discrepancy at the reported upper endpoint. Image truncation is ruled out at the sampled checks; finer-than-paper mesh convergence is not claimed. `finite_chain_diagnostic.json` records the open-end checks at 2 nm; their mode intervals cannot be substituted for a 1 nm paper result. At 2 nm the 3-cell chain gives breathing candidates at 13.650, 15.535 and 17.612 GHz; the 5-cell chain spans 13.180–17.388 GHz. Adding these finite ends does not recover 20.4 GHz in this diagnostic. Regenerate with `OPENBLAS_NUM_THREADS=1 python benchmarks/liu2024_finite_chain_check.py`.

## Figures and data

- `fig2_dispersion.png/.pdf`: FM quadratic reference plus numerical infinite-film dipole/exchange modes, and the skyrmion chain's unfolded intrinsic Fourier mode weights.
- `fig2_band_comparison.png/.pdf`: directly computed candidate branches on the first Brillouin zone, with both meshes and the paper's quoted reference ranges. The breathing disagreement is intentionally visible.
- `bands_20.csv`, `bands_40.csv`: signed wavevectors, branch frequencies, growth-rate diagnostics and near-zero flags.
- `fm_eigenvalues.csv`: all numerical versus analytical eigenfrequency pairs for the FM test.
- `fm_kx.csv`: the ky=0 infinite-film comparison.
- `unfolded_intensity.csv`: frequency rows and angular wavevector columns for the intrinsic mode map.
- `summary.json`: parameters, convergence, fits, acceptance checks and the explicit overall failed result.

The intrinsic weight is the spatial Fourier weight of each eigenvector, broadened by **0.12 GHz for visualization only**. The plotted map is not the source-dependent 5 mT sinc-pulse FFT intensity in the paper. It includes all three vector components and sums squared magnitudes over transverse rows. The spectrum is targeted/incomplete, so apparent blank areas do not prove global magnonic band gaps. The upper branch can hybridize with local skyrmion motion; the term “upper branch” avoids asserting its identity from frequency alone.

## Wavevector conventions

For period a=40 nm, the first Brillouin zone is ±pi/a = **±0.07854 rad/nm**. The reciprocal spacing is 2pi/a = **0.15708 rad/nm**. Eigenvectors obey `delta_m(x+a)=exp(i k a) delta_m(x)`.

The wide ±0.5 rad/nm plot is unfolded by evaluating Fourier weights at `q=k+G`. The physical wavevector scale is computed from the stated lattice period. No pixel positions from the paper's plot were digitized, rescaled or treated as exact numerical data. Branch curves versus `ka/pi` are also provided to make the first-zone comparison clear.

## Published-fit inconsistency

The text prints `fg=c1+2*c2*cos(ka)` with c1=1.15 GHz, c2=−0.5 GHz. Taken literally, this spans **0.15–2.15 GHz**, not the quoted 0.1–4 GHz interval.

It also prints `fb=sqrt(c3+2*c4*cos(ka))` with c3=294.9 GHz², c4=124 GHz². Taken literally, it spans **6.848–23.300 GHz**, not 13.4–20.4 GHz. This was checked against the rendered PDF, not just text extraction. A factor/convention/typographical difference is possible, but its correction is not established from the document. The benchmark preserves the literal coefficients and the independently quoted ranges as separate references.

For characterization only, fitting these two nearest-neighbor expressions to **our numerical bands** gives c1≈1.1860 GHz, c2≈−0.41452 GHz, c3≈220.990 GHz² and c4≈26.311 GHz². RMS frequency residuals are 0.122 and 0.0856 GHz. These are fits to our data, not fitted material parameters or proof of literature agreement.

## Acceptance and remaining diagnosis

Project criteria are 1% for the uniform FM and shifted-upper onset, 5% for each quoted collective-band endpoint, and 0.01 GHz for image convergence. These tolerances are chosen here, not specified by the authors. The two endpoint checks fail; `full_fig2_validation_passed` is false. A paper-resolution mesh and no growing computed modes are additional checks, not proof of complete stability.

The exact finite-chain length, transverse/boundary constraints and the author's simulation files are not supplied by the PDF. Our infinite-chain/open-width approximation is explicit. Matching single-skyrmion Fig. 1 frequencies did not establish that this is the same Fig. 2 array geometry. A finite-width FM control shows that boundary choice materially affects frequencies. A separate fully periodic spectral-film diagnostic gave a different breathing frequency; it was not substituted to force agreement.

Next required evidence for quantitative reproduction is the authors' MuMax3 input or equivalent explicit boundary/geometry information, followed by a matched finite-chain space/time FFT. No CUDA/MuMax3 execution is claimed here. The available finite-chain runner and f–kx analyzer provide that comparison path without inventing the missing setup.

## Reproduce and use

```bash
cd /workspace/spinfreq
source /workspace/venvs/spinfreq/bin/activate
export MPLCONFIGDIR=/workspace/.cache/matplotlib
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python benchmarks/liu2024_fig2.py
# Revalidate and reuse the raw eigenpairs:
OPENBLAS_NUM_THREADS=1 python benchmarks/liu2024_fig2.py --reuse
```

For an actual finite-chain time/space FFT, supply the chain count explicitly:

```bash
# 10 is an example, not established author geometry. Full 40 ns CPU runs can be expensive.
OPENBLAS_NUM_THREADS=1 python benchmarks/liu2024_dynamics.py --case chain-sinc \
  --columns 10 --cell-nm 1 --duration-ns 40 --sample-ps 5 --output results/chain_pulse
python benchmarks/liu2024_fk.py results/chain_pulse/trajectory.npy \
  --summary results/chain_pulse/summary.json --component 2 --output results/chain_fk
```

The FFT implementation is tested against a traveling wave with known frequency/wavevector and opposite-phase transverse rows. A short recorded-array workflow was also analyzed, but its 10 GHz frequency bins do not validate the paper's low-frequency spectrum. See the [full usage guide](../../../docs/USAGE.md) for model selection, units, recordings and output interpretation.

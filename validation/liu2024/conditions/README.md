# Physical assumptions, solver corrections and standard checks

We tested nine explicit geometry/boundary hypotheses while keeping **all paper material constants, the 40 nm lattice period, 1 nm thickness, damping and zero static field fixed**. Eight cases were screened at 2 nm; promising cases and a midpoint probe were evaluated at the paper's 1 nm mesh. No material constant was fitted. These are sensitivity experiments, not evidence that the authors used the selected geometry.

## Main result

Pinned transverse buffer layers bring the low-frequency bands much closer to the quoted paper ranges:

| 1 nm calculation | Gyration maximum (GHz) | Breathing interval (GHz) | Lowest upper candidate at k=0 (GHz) |
|---|---:|---:|---:|
| Paper quoted values | 4.0 | 13.4–20.4 | 34.5 |
| Natural 40 nm strip | 1.933 | 13.079–16.667 | 34.666 |
| 44 nm strip, 2 nm pinned edges | 4.164 | 14.356–21.785 | 34.041 |
| 45 nm strip, 2 nm pinned edges | **4.022** | **13.801–21.383** | 32.547 |
| 46 nm strip, 2 nm pinned edges | **3.860** | **13.271–20.981** | 31.225 |

The 46 nm case matches the breathing endpoints within **0.96% and 2.85%**. Its gyration maximum differs by 3.50%. The 45 nm case matches the gyration maximum within **0.55%** and breathing endpoints within **2.99% and 4.82%**. The 44 nm case preserves the upper onset more closely (1.33% low) but overestimates both breathing endpoints.

This exposes a tradeoff: no tested condition simultaneously reproduces all quoted bands, the shifted upper onset and the nonzero gyration cutoff. The infinite-chain lowest mode remains near zero rather than the paper's 0.1 GHz. Matching frequency intervals also does not prove the complete dispersion shape or finite-source intensity. The paper's literal fitted coefficients remain inconsistent with its quoted ranges; both are preserved in the baseline report.

Refined intervals use five positive wavevectors (`ka/pi=0,0.25,0.5,0.75,1`); the baseline Fig. 2 scan retains 17 signed points. These are sampled ranges, not a complete high-resolution band or gap certification.

**Full paper validation remains false.** Pinned buffers are a plausible missing constraint that explains much of the low-band discrepancy, but they are not established by the PDF or an author script.

## Conditions and selection

The coarse screen covered natural transverse widths of 30, 40 and 60 nm, open DMI edges at 40 nm, and 2 nm fixed +z edge layers at total widths of 40, 44, 46 and 50 nm. The 30 nm natural-strip initial states did not yield a stable computed k=0 spectrum and were not presented as successful equilibria. Wider natural strips and open DMI edges did not resolve the breathing-band top.

A 44 nm pinned strip has a **40 nm free region plus a 2 nm magnetic buffer on each side**. This is a concrete interpretation of an unstated pinned boundary outside an active region. The 46 nm case brackets the width sensitivity. The 45 nm case was added as an adaptive midpoint after examining 44/46 nm results. Its close agreement is exploratory geometric matching, not an independent author validation. The pinned thickness stays physically 2 nm under refinement: one row at 2 nm resolution, two rows at 1 nm.

Each condition tests x-position offsets of 0, 0.25 and 0.5 cells. Unit spins are relaxed, then statically refined; a negative-growth k=0 candidate is selected among these seeds before scanning the remaining wavevectors. Frozen boundary spins are removed from the Jacobian's tangent degrees of freedom, rather than generating zero rows and spurious frozen-spin eigenvalues. All scanned growth rates and rejected seeds are retained in the JSON files.

The provisional breathing modes have 0.95–0.97 normalized overlap with the radial derivative of equilibrium mz and are the strongest radial modes among the computed positive-frequency modes below 50 GHz at k=0. This checks that the agreement was not obtained by relabeling an unrelated frequency peak. It is not a full crossing-aware tracking algorithm for every k.

## Numerical issues found and corrected

### Exact periodic Bloch convolution

The previous doubled-x Toeplitz convolution of a finite image sum was Hermitian but not exactly equivariant under shifting the repeating cell. For a 5×4-cell random field, the relative cyclic-shift error was 8.24e-6 with ±4 images and 3.03e-9 with ±32 images. Those small errors can affect near-zero modes.

The corrected solver uses a **circular x convolution of the periodic Bloch envelope**, zero padding only in y, and Hermitian displacement pairing. The same errors are now **2.65e-16 and 2.40e-16**. Tests cover ordinary and phase-twisted translations, Hermiticity, opposite-k conjugation and exchange dispersion. New Bloch raw arrays carry a physics-version marker; pre-correction arrays are rejected by `--reuse`. The baseline Fig. 2 scan and its plots were regenerated with the corrected operator.

### Residual-based equilibrium refinement

Energy relaxation typically stopped around 1 μT transverse field. This was sufficient for GHz optical modes but too loose for weak translation modes: some pinned candidates had positive small growth rates even after minimizer convergence.

The new public `spinfreq.refine_equilibrium` solves the projected static field equations in normalized tangent coordinates using Newton/Krylov iterations. It preserves frozen spins and independently checks the physical torque. Representative residuals dropped below 3 nT; the final 45/46 nm states have about **0.180/0.415 nT** residuals. Refinement does not guarantee a minimum: computed growth rates still need checking.

Both normalized and absolute Bloch eigenvector residuals are available. For the 45 nm k=0 low modes, absolute residuals are approximately 0.02–0.1 s⁻¹. This is a more useful accuracy diagnostic near zero than normalization by the large exchange-matrix norm alone.

### Remaining neutral-mode sensitivity

The 45 nm image check changes optical frequencies by at most **6.50e-5 GHz** when moving from ±32 to ±64 images. However, its near-zero translation eigenvalue changes from weak decay (about −1012 s⁻¹) to weak growth (**+4827 s⁻¹**) at k=0. This is retained in `midpoint/image_convergence.json`; infinite-chain neutral-mode stability is **not certified**. The optical-band agreement is robust at these image counts, while the neutral mode needs additional convergence and the actual finite-chain constraints. It must not be used to claim a stable paper-equivalent ground state.

## Independent micromagnetic checks

`benchmarks/standard_checks.py` computes rectangular-prism magnetometric demagnetizing factors from **independent Coulomb surface-charge integration**, with a Duffy transformation to remove the self-surface singularity. It does not call Newell functions. Quadrature orders 160 and 256 are compared.

| Uniform specimen, dimensions in nm | Surface-integral Nx | Ny | Nz | Largest simulator absolute error |
|---|---:|---:|---:|---:|
| 5×5×5 cube | 1/3 | 1/3 | 1/3 | 5.0e-16 |
| 40×40×1 film | 0.03519867 | 0.03519867 | 0.92960266 | 4.6e-12 |
| 500×125×3 specimen | 0.00917967 | 0.03817612 | 0.95264421 | 1.3e-11 |

The third specimen is the geometry of µMAG Standard Problem 4. **Only its uniform-specimen magnetostatics is checked here, not the standard problem's nonuniform switching trajectory.** No CUDA/MuMax3 comparison is claimed.

The continuum DMI helix also passes: with A=15 pJ/m and D=3 mJ/m², its pitch is `4*pi*A/|D| = 62.83185 nm`, energy density is `−D²/(4A) = −150000 J/m³`, and the spectral solver matches the energy to 2.22e-16 relative error. The bulk torque is about 3.26e-14 T. Neighboring permitted winding numbers have higher energy.

A separate finite-difference check uses `tan(theta)=−D*h/(2A)` and the exact discrete energy `2A(1−cos(theta))/h² + D*sin(theta)/h`. The Bloch finite-difference operator matches this energy and bulk stationarity. Physical open-y edge torque is explicitly excluded from the bulk check. Existing Kittel, Gilbert susceptibility, nonlinear macrospin and exchange benchmarks also remain in the test suite.

## Artifacts and provenance

- `fine_conditions.png/.pdf`: all four 1 nm branch comparisons and paper reference intervals.
- `comparison.csv/.json`: aggregate values, errors, material constants and caveats.
- `summary_2nm.json`, `conditions_2nm.png/.pdf`: coarse screen.
- `refined/summary_1nm.json`: corrected/refined 40, 44 and 46 nm cases.
- `midpoint/summary_1nm.json`: the explicitly adaptive 45 nm case.
- `midpoint/image_convergence.json`: optical convergence and the sign-sensitive neutral eigenvalue.
- `mode_character.json`: radial-mode overlaps.
- `periodicity_check.json`: observed pre/post-correction shift errors.
- `standard_checks/summary.json`: independent gold standards.
- `legacy_image_sum/`: pre-correction exploratory diagnostics, retained as provenance and excluded from final comparisons. These are not current validation evidence.

Large raw eigenarrays are kept locally and ignored by Git. Source material constants are recorded per condition. The dense small-unit-cell calculations were actually run; no long nonlinear finite-chain source experiment was substituted for them.

## Reproduce

From the repository root, with the project environment active:

```bash
export MPLCONFIGDIR=/workspace/.cache/matplotlib
OPENBLAS_NUM_THREADS=1 python benchmarks/standard_checks.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python benchmarks/liu2024_conditions.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python benchmarks/liu2024_conditions.py \
  --cases natural_w40 pinned2_w44 pinned2_w46 --cell-nm 1 --k-points 5 \
  --output validation/liu2024/conditions/refined
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python benchmarks/liu2024_conditions.py \
  --cases pinned2_w45 --cell-nm 1 --k-points 5 \
  --output validation/liu2024/conditions/midpoint
OPENBLAS_NUM_THREADS=1 python benchmarks/check_condition_images.py
python benchmarks/condition_mode_character.py
python benchmarks/summarize_conditions.py
OPENBLAS_NUM_THREADS=1 python -m pytest -q
```

The default coarse screen automatically skips widths not divisible by the chosen cell size, including 45 nm at 2 nm cells. `--no-refine` reproduces the earlier equilibrium-accuracy diagnostics; it should not be used as the current near-zero-mode workflow.

The next decisive comparison is a matched finite-chain simulation with confirmed transverse and longitudinal constraints and spatial/time FFT data. Its nonzero cutoff, exact dispersion, continuum onset and source intensities cannot be established from these assumed infinite-chain geometries alone. See the [usage guide](../../../docs/USAGE.md) for the API and data conventions.

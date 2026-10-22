# Source/probe susceptibility tensors

[Report](report.json) · [PNG comparison](tensor-validation.png) ·
[PDF comparison](tensor-validation.pdf)

Reproduce with:

```bash
python benchmarks/susceptibility_tensor.py --check --output results/tensor-validation
python -m pytest tests/test_susceptibility.py -q
```

The benchmark compares every component of the complex B-based tensor against
an independently assembled physical-coordinate 2×2 Gilbert system embedded in
xyz. It covers uniform and one finite-k periodic mode (64 × 16 nm film,
8 × 2 cells of 8 nm, thickness/material/bias from `periodic-fmr`), including
exchange and the thin-film finite-k demagnetizing factor. Frequencies span
0–150 GHz in 501 samples; x/y diagonal and cross-response imaginary parts
are plotted. Full computed/reference NPZ arrays are generated when rerunning.
The committed report records benchmark and numerical source hashes.

Observed full-tensor relative errors were **4.58e-14 or less** for uniform
response and **5.15e-14 or less** for finite-k response. All-pole modal residue
reconstruction errors were below **2e-16**; shifted-system residuals were below
**2.56e-13**. CI thresholds are respectively 1e-9, 1e-9 and 1e-7.

Additional tests check longitudinal zeros, arbitrary elliptical polarization,
Fourier selection/cancellation, complex probe phases, eigenvector scale/phase
invariance, exactly degenerate group sums, completed-job integrity and rejection
after numerical source changes. The synthetic degenerate zero operator tests
algebra only; it is not presented as a stable magnetic equilibrium.

This is analytical linear periodic validation. It is not an independent
MuMax3/OOMMF temporal comparison, continuum mesh convergence, nonlinear
susceptibility, arbitrary geometry or a qualification of all device regimes.

Product checks on Linux also covered the full regression suite (185 passed,
5 platform-specific skips before four additional frequency-input cases), all
13 final tensor tests, the same 13 tests against the installed wheel outside
the checkout, the installed simulation/analysis commands, and the eight-page
static website in Chromium. Native Windows/macOS tensor CLI checks are added
to CI; their execution has not been observed in this environment.

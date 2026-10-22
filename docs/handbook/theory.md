# Theory and numerical methods

SpinFreq linearizes the Landau–Lifshitz–Gilbert equation around a numerically relaxed magnetic texture. It solves eigenmodes and harmonic response directly in frequency space. This avoids a time-series Fourier transform for linear spectra; it still requires a sufficiently resolved spatial model and an accurate equilibrium.

## Energy and units

Write **m = M/Ms**, with unit norm in each cell. A and D denote exchange and interfacial DMI; K is the perpendicular uniaxial anisotropy. In SI units the energy is

```text
E = ∫ [ A |∇m|² + D (mz ∇·m − m·∇mz)
        − K mz² − Ms Bext·m − (Ms/2) Bdemag[m]·m ] dV.
Beff = −(1/Ms) δE/δm.
```

The functional derivative is an energy-density derivative; discrete cell derivatives include the cell volume. Fields are **B in tesla**, not H in A/m. Do not insert a second μ0 into Zeeman or LLG. The demagnetizing field already includes μ0. Positive K favors out-of-plane magnetization. The D sign and the definition above fix chirality; match conventions when importing parameters.

## Spatial discretization

`Film` uses periodic Fourier derivatives in x/y. Its uniform-through-thickness magnetostatic tensor has `Nzz = (1 − exp(−|k|t))/(|k|t)` and an in-plane longitudinal component `1 − Nzz`; at k = 0, `Nzz = 1`. Odd Nyquist derivatives vanish; mixed Nyquist terms are symmetrized to maintain a real self-adjoint field. This is a periodic film, not an isolated rectangle.

`ConfinedFilm` uses nearest-neighbor exchange and interfacial DMI, with Newell cell-averaged magnetostatic tensors and nonperiodic convolution. The `bond` boundary follows the truncated bond energy. The `mumax` option adds the corresponding DMI edge-ghost treatment. These choices can alter edge textures and modes; report them explicitly. `BlochChain` applies phase factors to translated cells and sums a finite number of magnetic images; test image convergence independently.

Every cell spans the full thickness. Thickness changes the averaged demagnetizing kernel and volume, but does not introduce z-dependent magnetization, thickness standing waves, multilayers or a general 3D solver.

## LLG and equilibrium

With positive gyromagnetic magnitude γ and Gilbert damping α:

```text
dm/dt = −γ/(1+α²) [ m × Beff + α m × (m × Beff) ].
```

Energy minimization uses normalized spins and a projected analytical gradient. Optional equilibrium refinement improves stationarity. The maximum transverse field `|m × Beff|`, in tesla, is the torque diagnostic. A locally minimized texture is not proof of the global ground state. Tight torque alone is not proof of dynamic stability.

## Tangent-space eigenproblem

At equilibrium m0, choose two orthonormal vectors per cell forming a basis Q perpendicular to m0. To first order, `δm = Q u`; longitudinal changes are second order. Differentiating the full LLG, including the equilibrium-field terms, yields

```text
du/dt = J u + F b(t),      J = Qᵀ [d(LLG)/dm at m0] Q.
J vn = λn vn,             δmn(t) ∝ Q vn exp(λn t).
```

There are 2N coordinates for N cells. For a positive-imaginary eigenvalue, `fn = Im(λn)/(2π)` and decay rate `κn = −Re(λn)`. Stable modes decay; positive real parts imply growth. A well-isolated weakly damped pole has power-linewidth approximately `κn/π` in Hz, but overlapping or asymmetric driven peaks need a full response fit.

Damped operators can be nonnormal. `ModalResponse` uses the inverse right-eigenvector matrix, not a conjugate transpose, to obtain modal weights. It verifies force reconstruction and shifted-system residuals. Poor conditioning and modes near zero require special care; the job runner reports a conservative numerical sign margin, not a rigorous stability certificate.

## Harmonic response and absorption

Use `Bac(t) = Re[b exp(+iωt)]`, with ω = 2πf. Then

```text
(iω I − J) uω = F b,
δmω = Q uω,
Pabs = −(Ms Vcell ω/2) Im Σcells [ b* · δmω ].
```

The power is in watts, summed over cells. Response is dimensionless δm; divide by a defined drive reference to form a B-based transfer function in T⁻¹. Convert carefully when comparing H-based susceptibility. JSON jobs support complex polarization and uniform, rectangular, Gaussian or plane-wave spatial profiles. Named observation probes compute `sum(conj(w) δm)/sum(abs(w))`. Exact sampled fields and weights are exported; see the [spatial spectroscopy guide](https://github.com/spinuni/spinfreq/blob/main/docs/guides/SPECTROSCOPY.md). Arbitrary component-dependent complex spatial drives remain available through the low-level Python API.

A mode can exist without a visible absorption peak if its overlap with the drive or observation is small. Uniform drive in a periodic texture probes lattice wavevector zero. Complex phases depend on drive convention and time origin. To compare with `exp(−iωt)`, conjugate the corresponding real-system response consistently.

## Cost and physical limits

The optional [tensor analysis](https://github.com/spinuni/spinfreq/blob/main/docs/guides/SUSCEPTIBILITY.md)
reuses this operator for x/y/z source polarizations. With J = V diag(λ) V⁻¹,
weighted observation C and source forcing F, its B-based transfer is
`T(f) = C V diag[1/(iω−λ)] V⁻¹ F`, in 1/T. The residue of signed mode n is
`R_n = (C V)_n (V⁻¹ F)_n`, in 1/(T s). Residues are complex and interfere;
they are not separate absorbed powers. At degenerate poles only their summed
subspace contribution is invariant. Both signed branches are needed to
reconstruct the tensor. Unit-tesla normalization denotes a linear derivative;
new finite drives still require full-field small-signal checks.

Full dense eigenanalysis stores a 2N × 2N matrix and scales approximately as N³ in work and N² in matrix memory. Reusing an eigenbasis accelerates repeated sweeps but does not remove dense storage or conditioning limits. Library assembly limits are 1024 periodic cells and 4096 confined/Bloch cells; the web cap is 400. Specialized confined iterative response and targeted Bloch modes exist in Python and have separate convergence requirements.

The linear solver does not generate nonlinear harmonics, a nonlinear frequency comb, thermal noise, current-driven torque or switching. A linear sum of tones and its startup transient are still linear. The separate nonlinear time integrator is a research workflow and does not establish validation of these omitted mechanisms.

## Scientific foundations and traceability

The implementation follows standard LLG dynamics and Newell cell-averaged magnetostatics, rather than wrapping a temporal solver. Relevant foundations include Gilbert, IEEE Transactions on Magnetics **40**, 3443–3449 (2004), and Newell, Williams & Dunlop, Journal of Geophysical Research **98**, 9551–9555 (1993). MuMax3 is described by Vansteenkiste et al., AIP Advances **4**, 107133 (2014), DOI [10.1063/1.4899186](https://doi.org/10.1063/1.4899186); it is an independent reference, not a SpinFreq dependency.

See the [validation evidence](validation.html) for analytical tests and independent OOMMF/MuMax3 comparisons. The [implementation reference](https://github.com/spinuni/spinfreq/blob/main/docs/reference/PHYSICS.md) links benchmark-specific details and unresolved disagreements. Reference data retain their original attribution and licenses.

# Validation and first release: package and web application

The recommended first release is a **CPU linear micromagnetics research tool for
rectangular thin films with uniform magnetization through the thickness**.
Provide the Python package and a web application using the same validated
calculation API. Frequency response, damped eigenmodes and supported 1D Bloch
calculations belong in that scope. Nonlinear dynamics can remain an explicitly
experimental API workflow until its own external comparisons are complete.

**Readiness: research preview; neither a validated general-purpose MuMax3
replacement nor a deployed web application.** A package build is possible, but
several physics and delivery gates below remain open. The version string
`0.1.0` in `pyproject.toml` is not evidence of a published release.

## 1. Literature selected by physics, not by one target paper

Sources were checked against the authors' repositories, simulator source and
input files on 2026-10-15, with the DMI reference extended on 2026-10-20. Publisher/arXiv hosts were inaccessible from this
environment; the linked primary repositories provided the reproducible inputs
and, for Baker and Cortés-Ortuño, reference data. Solver attribution below is
limited to what those sources establish. Two CPU OOMMF 4 ns DMI runs and two 8 ns skyrmion runs were executed on 2026-10-20;
their [DMI reference](../../validation/dmi_temporal/README.md) and
[skyrmion reference](../../validation/skyrmion_temporal/README.md) are archived.
No new MuMax3 simulation was executed here.

| Paper / primary source | Temporal solver or reference | What to compare | Fit to the current solver |
| --- | --- | --- | --- |
| **Baker et al., “Proposal of a micromagnetic standard problem for ferromagnetic resonance simulations,” JMMM 421, 428–439 (2017), [DOI](https://doi.org/10.1016/j.jmmm.2016.08.009), [author inputs and OOMMF/Nmag data](https://github.com/fangohr/micromagnetic-standard-problem-ferromagnetic-resonance)** | OOMMF and Nmag; author reference traces and spatial arrays | Equilibrium, visible and dark modes, frequency, decay, phase/amplitude maps, FFT processing | **First external frequency/linewidth benchmark.** Implemented here with a disclosed one-layer approximation of their two-layer discretization. |
| **Cortés-Ortuño et al., “Proposal for a micromagnetic standard problem for materials with Dzyaloshinskii–Moriya interaction,” NJP 20, 113015 (2018), [DOI](https://doi.org/10.1088/1367-2630/aaea1c), [author scripts and data](https://github.com/fangohr/paper-supplement-standard-problem-dmi), [dataset DOI](https://doi.org/10.5281/zenodo.1174311)** | MuMax3, OOMMF, Fidimag, with additional finite-element comparisons | 1D boundary canting; 2D skyrmion profile; 3D texture; signed-wavevector spin-wave dispersion and DMI nonreciprocity | **1D static profiles now verified.** Singleton axes and an explicit transverse-periodic wire are supported. Bloch-strip results match saved MuMax3 fit summaries; new CPU OOMMF complex traces pass at two wavevector magnitudes. The original finite-strip pulse and broader temporal dispersion remain open. Disk masks, bulk/D2d DMI and the 3D cylinder remain unsupported. |
| **Vansteenkiste et al., “The design and verification of MuMax3,” AIP Advances 4, 107133 (2014), [DOI](https://doi.org/10.1063/1.4899186), [official source](https://github.com/mumax/3), [official SP4 example](https://mumax.github.io/examples.html#ex_SP4)** | MuMax3 verification suite; classic μMAG problems | Demag, exchange, damping, numerical convergence; SP4 switching if nonlinear dynamics are advertised | **Foundation and integration checks.** Existing uniform-prism factors do not constitute SP4 trajectory validation. SP5 current-driven motion needs missing spin torque. |
| **Rohart and Thiaville, “Skyrmion confinement in ultrathin film nanostructures in the presence of Dzyaloshinskii-Moriya interaction,” PRB 88, 184422 (2013), [DOI](https://doi.org/10.1103/PhysRevB.88.184422), [related OOMMF extension and references](https://github.com/joommf/oommf-extension-dmi-cnv), [Fidimag/OOMMF comparison inputs](https://github.com/computationalmodelling/fidimag/tree/master/examples/micromagnetic/PRB_88_184422)** | The linked OOMMF/Fidimag implementations supply reproducible related checks; a later extension's sign convention is not automatically the original paper's | Natural DMI edges, radius/profile, chirality and confinement | **Static prerequisite for skyrmion spectra.** Our helix and stencil tests are partial evidence. Circular confinement and independent radius/profile comparisons are open. |
| **Moon et al., “Spin-wave propagation in the presence of interfacial Dzyaloshinskii-Moriya interaction,” PRB 88, 184404 (2013), [DOI](https://doi.org/10.1103/PhysRevB.88.184404), [theory versus temporal solvers in the DMI standard notebook](https://github.com/fangohr/paper-supplement-standard-problem-dmi/blob/master/notebooks/spin_waves_dmi.ipynb)** | The linked Cortés-Ortuño notebook compares Moon's dispersion with OOMMF/Fidimag/MuMax3 | Sign and slope of `f(k)-f(-k)`, dispersion minimum, field dependence | **Analytical companion to the DMI dynamics gate.** The original Moon article's solver is not inferred from the later notebook. |
| **Liu et al., “Low-lying magnon frequency comb in skyrmion crystals,” PRB 110, 184413 (2024), [DOI](https://doi.org/10.1103/PhysRevB.110.184413), [our report](../../validation/liu2024/README.md)** | MuMax3 in the attached paper | Isolated-skyrmion modes; collective bands; nonlinear comb only in a separate nonlinear tier | **One application family.** Isolated modes agree within 0.3%; full collective-band reproduction and nonlinear comb remain unvalidated. Geometry hypotheses are exploratory. |

Use analytical Kittel, dipole/exchange dispersion and Gilbert susceptibility as
the first tier, the FMR and DMI standard problems as independent implementation
comparisons, and several skyrmion applications as the final tier. Fitting one
paper's material constants until a peak matches would not substitute for these
tiers.

The DMI reference MuMax3 spin-wave input is particularly informative: a
2000×200×1 nm strip, 2×2×1 nm cells, `Ms=0.86 MA/m`, `A=13 pJ/m`, a signed
interfacial DMI input of `-3 mJ/m²`, `B_y=0.4 T`, `alpha=0.01` and a localized
4 ns excitation. Its 100,000 lateral cells exceed our dense assembly limits.
The D sign must be translated from the **energy convention**, not copied by
symbol name alone. The [new DMI report](../../validation/dmi_standard_problem/README.md)
uses x-translation symmetry to reduce the interior-strip eigenproblem to one
x cell and the full transverse mesh. At 2 nm this is 200 tangent coordinates.
Its asymmetric quadratic fit reproduces the notebook's apparent |D| near
2.62 mJ/m² from fixed nominal |D|=3 mJ/m²; direct low-k ±k pairs recover about
2.99 mJ/m². A driven finite-array FFT intensity map still requires separate data.

## 2. New external result: the FMR standard problem

[Detailed result, plots and commands](../../validation/fmr_standard_problem/README.md).
The new benchmark reads the authors' pinned, SHA-256-checked OOMMF data. It
computes our equilibrium and full damped Jacobian, then reconstructs a small
field-rotation ringdown as `exp(J t) u0`, directly in the eigenbasis. It does
not integrate our nonlinear LLG to manufacture a second reference.

At 3 nm lateral spacing, the two visible eigenfrequencies are **8.25264 and
11.23406 GHz**, versus **8.25 and 11.25 GHz** raw OOMMF FFT bins. Their complex
y-component mode overlaps (MAC) are **0.99988 and 0.98029**. Refining lateral
spacing from 4 to 3 nm changes those frequencies by **0.00375% and 0.00136%**.
The reference FFT bin spacing is 0.05 GHz; sub-bin accuracy needs a trace fit,
not extra printed digits on a bin position.

A three-damped-sinusoid fit to the independent OOMMF mean trace also supplies
sub-bin pole frequencies and linewidths. It is repeated over four starting
times; the finest-grid discrepancies are **0.172% and 0.057%** in fitted
frequency and **0.295% and 0.396%** in fitted pole linewidth. Fit sensitivity and
limitations are saved in `summary.json`. Higher
modes and arbitrary damping values are not validated by those two comparisons.
The one-z-layer approximation cannot establish agreement for z-dependent modes
or reproduce the exact 3D standard problem.

## 3. Required physics evidence for v0.1

The thresholds below are **proposed project acceptance criteria**, not tolerances
claimed by the papers. Use the larger of the stated frequency tolerance and a
documented reference uncertainty. Do not relax a criterion after seeing a failed
result without recording the scientific reason.

| Gate | Required evidence | Current evidence / missing work |
| --- | --- | --- |
| P1. Energy and linearization | Energy/field derivatives; analytic Jacobian versus finite differences on noncollinear states; norm/tangent constraints; matrix-free versus dense action | Existing tests cover these. Preserve them in CI. |
| P2. Analytic baselines | Kittel orientations, exchange/dipolar dispersion, complex susceptibility including phase and positive absorption, damping | Existing analytic reports and tests pass. Extend field, damping and material sweeps before claiming a broad accuracy envelope. |
| P3. Independent finite-film FMR | Visible frequencies within 1%; complex mode MAC >0.95; linewidth within 5% with a credible extraction method; final lateral refinement <0.5% | New Baker/OOMMF benchmark supplies the two visible low-mode comparisons. Exact z-resolved replication and wider parameter sweeps remain outside that result. |
| P4. Interfacial DMI and propagation | Independent static canting/profile; chirality under `D -> -D`; signed `f(k)` versus temporal data; nonreciprocity slope within 2% after mesh convergence | Published MuMax3/OOMMF/Fidimag 1D profiles, D reversal, continuum refinement and analytical signed dispersion pass. MuMax strip fit summaries agree within 0.12%; the tested finest low-band mesh change is 0.4565%. Two executed CPU OOMMF ringdowns match full complex traces within 0.058% at two wavevector magnitudes, with all four signed-k peaks matching. A proven even-N FFT row-reversal bias explains part of the old offset. Full finite-strip curves, wider convergence and the remaining historical OOMMF/Fidimag band differences are open: **P4 is not fully closed**. |
| P5. Noncollinear dynamics | At least one skyrmion case with independent equilibrium/profile and complex mode fields, plus two fields or sizes; frequencies within 2% after refinement; no material fitting | New independent CPU OOMMF skyrmions at 0 and 50 mT validate profiles, full spatial traces (error <0.0086%) and six complex mode fields (MAC >0.998); fitted frequencies agree within 0.019%. The subsequent independent 1 nm runs at both fields pass, with spatial errors <0.0096%, MAC >0.997 and fitted frequency errors <0.008%. Joint qualification matches them to the 1 to 0.8 nm refinement (<0.648% change). This supplies the stated P5 evidence for this square-film model; general thickness/parameter envelopes remain open. Full agreement with Liu Fig. 2 is not a universal release gate. |
| P6. Driven response and the linear regime | External small-drive complex response/decay; peak positions and phase; halving drive halves δm and quarters power; repeat near two resonances | Analytic macrospin checks and external OOMMF complex ringdown/initial-amplitude halving pass (power ratio 1/4). Independent 2 nm multitone OOMMF drives now test six frequencies near two resonances, with complex errors <0.14%, phase errors <0.008 degrees, startup trace error <0.0048% and field-halving/power-quartering checks. Tighter angular-error and explicit timestep-refinement reruns test numerical convergence. Fine-grid driven sweeps and a wider amplitude/parameter envelope remain open. Compare like excitation and like observable. |
| P7. Stability and band completeness | Physical static residual; absolute and relative eigen residuals; growth-rate error bounds near zero; targeted-mode count/shift convergence and branch overlap tracking | Root refinement and Bloch residual checks exist. Neutral-mode certification, automatic tracking and completeness checks are open. Do not present a targeted subset as a proven band gap. |
| P8. Supported envelope | Fixed-size mesh refinement; finite-size/image convergence; reference z refinement at representative thicknesses; measured time/RAM | Individual convergence studies exist, including a two-field noncollinear 2 to 0.8 nm study. Coarse-grid frequency shifts reach several percent; the finest pair passes its 1% target. The 1 nm independent dynamics now pass at both fields. A general thickness/grid/parameter envelope remains open. |

For finite-time comparisons, choose the observation duration before measuring
error: `Δf = 1/T`. Account for window broadening, transient removal, excitation
symmetry and local versus spatially averaged signals. A dark mode can be absent
from a uniform-drive spectrum and still be a valid eigenmode. Near degeneracies,
compare mode subspaces rather than forcing a unique mode ordering.

For a nonnormal damped Jacobian, mode populations require left/right information
or an actual inverse of the right-mode basis; a conjugate transpose generally
does not invert it. Compare a resolvent or reconstructed signal as well as
eigenvalues. The FMR benchmark's ringdown helper is checked against an independent
matrix exponential on an elliptical damped system.

## 4. Limitations and improvements in priority order

| Limitation found in the code | Consequence | Recommended improvement / verification |
| --- | --- | --- |
| Full modes, direct response and Bloch shift-invert assemble dense matrices | `O(N²)` storage and `O(N³)` factorization; targeted Bloch extraction still pays for dense LU | Add matrix-free targeted modes and a tested preconditioned inner solve. Use FFT demag action plus an exchange/local-field preconditioner; validate residuals and agreement with small dense cases before claiming speedups. |
| Direct response refactorizes a shifted matrix at every frequency; GMRES has no preconditioner | Fine resonant sweeps are expensive, and iterative convergence can deteriorate around narrow poles | `ModalResponse` now reuses the full eigenbasis and an inverse factorization, with true-residual checks. A measured 201-point small-system sweep uses 8.07× less CPU including preparation. Large-system preconditioned/rational Krylov methods remain open. |
| Single magnetization value through z in every class | No perpendicular standing spin waves, surface asymmetry, multilayer hybridization or 3D textures | Establish thickness validity against z-refined OOMMF/MuMax3 first. Add multilayer/z cells only if needed; do not label 10 nm universally safe because two FMR modes agree. |
| Periodic `Film` uses spectral operators/continuum film demag; confined/Bloch use FD/cell-averaged Newell demag | Same grid and constants are not necessarily the same discrete problem | Compare discrete operators when matching a solver and continuum limits when matching physics. Include FD dispersion and boundary settings in run metadata. |
| Only homogeneous material, easy-z anisotropy, interfacial DMI and rectangular occupied meshes | Disk/vortex, patterned antidot, bulk-DMI and heterogeneous-interface papers cannot be copied faithfully | Prioritize occupancy masks with correct exchange/DMI edge treatment for disk benchmarks. Later add arbitrary anisotropy axes and material regions. Reject unsupported inputs clearly. |
| Singleton axes retain the boundary prescription of their geometry | A finite open one-cell transverse axis has MuMax ghost terms; its profile differs from the standard's transverse-PBC wire | Single-cell axes are now supported. Use the documented rotated `BlochChain(nx=1,ny=100)` for the transverse-periodic wire; preserve and report the open-axis alternative. General boundary selection remains a future API improvement. |
| Equilibrium is a local stationary state; targeted spectra cannot certify all instability directions | A converged optimizer or one positive-frequency branch is insufficient evidence of stability | Check the tangent energy Hessian or an appropriate full/matrix-free stability bound; classify neutral modes using absolute numerical error. Keep the near-neutral pinned-chain issue visible. |
| Modes are sorted by frequency or benchmark windows, without general branch tracking | Crossings can look like gaps; a mode can be mistaken for another after refinement | Implement overlap/subspace tracking, driven oscillator strengths and residual-aware mode labels. |
| Linear frequency-domain formulation | No amplitude-dependent shifts, harmonic mixing, switching or frequency comb generation in that solver | State small-signal limits in the UI/API. Keep nonlinear time-domain workflows separate; harmonic balance would be a later research feature, not implied by existing LLG integration. |
| No thermal noise, STT/SOT, spin pumping, magnetoelasticity or experimental disorder | Many current-driven, finite-temperature or hybrid-mode papers are outside scope | Exclude these claims from v0.1; select benchmarks whose Hamiltonian and dynamics we actually implement. |

The 100,000-cell DMI strip above would require **320 GB for one real dense
Jacobian**, or **640 GB for one complex matrix**, before work arrays. Our
4096-cell confined/Bloch cap allows a single 512 MiB real or 1 GiB complex
matrix, also before copies, factorization and eigenvectors. These caps are
implementation limits, not safe web-service quotas.

Dense reference calculations should remain available after adding scalable
methods: they are useful for validating new algorithms. Frequency methods are
especially useful for small-signal poles and narrow linewidths, but are not
automatically faster when every mode or hundreds of fresh dense solves are
requested.

## 5. Delivery gates for the package and web application

The current candidate implementation and milestone dependencies are recorded in
[RELEASE_PLAN.md](../releases/RELEASE_PLAN.md). Earlier local-check counts below describe
their respective updates, not the current suite total.

| Delivery gate | Evidence required before public deployment | Status |
| --- | --- | --- |
| D1. Build and install | Wheel and sdist build; fresh-environment installation; run the installed CLI outside the repository; tests on supported Python versions | Workflow added for Python 3.11–3.13, external FMR regression gates and distribution smoke checks. Local results are recorded separately; remote CI is not assumed to have run. |
| D2. Reproducible jobs | One serializable configuration/schema for materials, geometry, boundaries, solver and drive; save package/git version, dependency versions, units, tolerances, seeds, residuals and machine limits | Implemented in `JobConfig`/`run_job`: strict versioned SI inputs, periodic/confined model selection, full materials, config/source hashes, package/dependency versions, residuals and resource records. CLI and web share the runner. |
| D3. User-visible numerical status | Failed relaxation/solve rejects spectral output; distinguish unstable, neutral/uncertain and stable; display drive size and convergence limits | Shared runner now rejects failed torque/eigen/response checks, unstable/uncertain numerical growth signs and excessive linear amplitudes. UI and downloads expose diagnostics. Rigorous neutral-mode certification and general branch tracking remain open. |
| D4. Web computation lifecycle | Background worker, bounded queue, measured RAM/CPU/time/disk limits, progress, cancellation, timeout recovery; heavy jobs do not execute inside an HTTP request | Implemented for local Linux: one bounded subprocess, queue/storage caps, progress/cancel/delete, CPU/address-space/file/wall/disk controls, exclusive supervisor and restart recovery. Host-specific public-service budgets remain open. |
| D5. Web reproducibility and results | Three vetted presets; editable SI-labelled parameters; plots of equilibrium/modes/response; download config, JSON, CSV and array/OVF outputs | Implemented: three checked presets, editable SI-labelled inputs/full JSON, plots and config/JSON/CSV/NPZ/OVF/ZIP exports. Edited inputs are explicitly research configurations; matched coarse-grid scope is visible. |
| D6. Web service tests | Browser-to-worker-to-download smoke test; malformed/oversized-job rejection; isolation of job inputs/results; simultaneous jobs, cancellation and restart tests | Local real-worker tests cover queue capacity, isolation, cancellation, timeout, malformed/oversized jobs and restart recovery. Real Chromium submits through the UI, verifies plots and downloads results. Public load/access-control checks remain open. |
| D7. Release provenance | Owner-selected license; citation metadata; supported-model statement; versioned example results; tag/changelog; dependency/environment record and release artifacts | Owner selected MIT; LICENSE, CITATION.cff, changelog and candidate version `0.1.0rc2` added. Tag, package publication and public hosted application remain pending; a GitHub push is not those deliverables. |

Local delivery checks passed on Python 3.12.14: 42 tests in the development
environment (NumPy 2.4.4, SciPy 1.17.1, Matplotlib 3.10.8); 42 tests from the
unpacked source distribution in a fresh environment (NumPy 2.5.4, SciPy 1.18.1,
Matplotlib 3.11.2); isolated wheel/sdist builds; installed CLI execution from
`/tmp`; and `pip check`. The hash-checked reference download path was also
exercised. Python 3.11/3.13 and hosted CI outcomes are not inferred from these
local checks. Source distributions include benchmark scripts and comparison
reports; large intermediate NPZ arrays and downloaded external references are
excluded.

The 2026-10-20 DMI update expands the suite to **56 passing tests** in both the
development environment and the fresh NumPy 2.5.4/SciPy 1.18.1 installation.
Wheel/sdist builds, installed singleton-axis CLI execution, reference-download
verification and the DMI static/analytical reference regression also pass.
CI now includes that smaller DMI regression; the multi-mesh strip report was
computed locally. These checks retain the explicit open P4 items above.

The subsequent CPU OOMMF comparison expands the suite to **65 passing tests**.
Two independent 4 ns runs verify complex traces (maximum discrepancy 0.0575%),
all four signed-k FFT peaks and initial-amplitude scaling. Native reference files
and source/executable hashes are archived. The new CI job verifies those hashes
and recomputes the frequency comparison; it does not build or execute OOMMF.
The even/odd FFT branch regression now protects signed-wavevector extraction.
See the [report](../../validation/dmi_temporal/README.md) for the reduced periodic
geometry and the remaining full-strip and forced-response requirements.

The two-field skyrmion update adds full spatial OOMMF snapshots, independent
pole fits, complex vector mode maps, failed coarse-mesh and passing fine-pair
studies. All **68 tests** pass locally. Native scalar/spatial reference archives
are included in the sdist; the new CI job verifies their hashes and recomputes
the comparisons. New OOMMF MIFs correctly disable checkpointing with -1;
0 requested per-step checkpoints and led to rejected corrupt spatial outputs
in exploratory runs. The accepted references contain complete readable fields.
See the [report](../../validation/skyrmion_temporal/README.md) for numerical results,
reproduction commands and remaining fine-grid qualification.

The fine-grid continuation executes 1 nm ringdowns at both fields and supplies
joint qualification against the 1 to 0.8 nm study. Separate multitone OOMMF
runs test weak-field amplitude, phase, startup and halving around two resonances.
Their settings and numerical-control study are documented in the
[fine-grid](../../validation/skyrmion_fine/README.md) and
[driven-response](../../validation/driven_response/README.md) reports.
`ModalResponse` adds a reusable full-basis API, exact raised-cosine transients,
and true residual checks; analytic elliptical susceptibility and independent
linear time integration test its phase and nonnormal-basis treatment.

The current continuation passes **73 tests** in both the development environment
and a fresh wheel installation tested from the unpacked source distribution.
Wheel/sdist builds, installed CLI execution outside the checkout and `pip check`
also pass. Fine-grid and driven native references have been restored, hash-checked
and reanalyzed in the fresh environment. The explicit timestep cap increases
OOMMF steps from 62,761 to 164,001; complex phasors change by less than 1e−9
relative. The angular-error-only check is reported separately because it does
not substantially refine the accepted timesteps. These are local checks;
Python 3.11/3.13 and hosted CI outcomes remain to be observed.

Do not make a particular cloud provider a physics dependency. First define the
worker's compute budget and result-storage requirements, then choose hosting.
The browser should request a validated configuration and inspect results; the
package should own the physics.

## 6. Practical sequence

The [first-version release plan](../releases/RELEASE_PLAN.md) now tracks M1–M7. Repository
organization, MIT/citation metadata, shared execution and the bounded local web
workbench are implemented. The [candidate report](../../validation/release_candidate/README.md)
records example frequencies, resource measurements, browser checks and package
checks. Observe hosted CI before tagging/publishing the package. Public web
hosting still needs a host, access/TLS policy and operational measurements there.

Retain all independent physics regressions. Broaden the advertised envelope only
after qualifying thickness/mesh/drive changes; keep matrix-free scaling,
neutral-mode certification and branch tracking as separate improvements. Full
nonlinear combs, thermal/current-driven problems and 3D thickness modes become
release blockers only if included in the advertised supported scope.

## Native Windows candidate continuation

`0.1.0rc2` adds an explicitly experimental Windows Job Object runtime while
retaining automatic preview on Windows and normal Linux computation. Platform
resource/lifecycle qualification is tracked in the
[Windows report](../../validation/release_candidate/windows/README.md); no new
physics or thickness envelope is inferred from this platform implementation.
